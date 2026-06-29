#!/usr/bin/env python3
"""BioRAG MCP Server — Memoria compartida OEC via Model Context Protocol.

Expone la corteza biologica de BioRAG como herramientas MCP para que
cualquier IDE/CLI (OpenCode, VS Code, Cursor, Cline) se conecte a la
memoria compartida de los agentes OEC sin ejecutar comandos shell.

Uso:
  python3 mcp_server.py              # stdio transport (modo subproceso)
  python3 mcp_server.py --sse        # SSE transport (modo servidor HTTP)

Para conectar desde OpenCode, anadir a opencode.json:
  "mcpServers": {
    "biorag": {
      "command": "python3",
      "args": ["/ruta/a/MemoryBioRAG/mcp_server.py"]
    }
  }

Para conectar desde VS Code, anadir a .vscode/mcp.json:
  {
    "servers": {
      "biorag": {
        "type": "stdio",
        "command": "python3",
        "args": ["/ruta/a/MemoryBioRAG/mcp_server.py"]
      }
    }
  }
"""

from __future__ import annotations

from datetime import datetime
import io
import json
import logging
import math
import os
import re
import shutil
import subprocess
import sys
import time
from typing import Annotated, Any, Optional, List  # ← Annotated agregado

# Cargar .env.local explícitamente para que el MCP server no dependa de que
# el entorno de ejecución (OpenCode, VS Code, etc.) lo inyecte.
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
for _dotenv_candidate in (".env.local", ".env"):
    _dotenv_path = os.path.join(_PROJECT_ROOT, _dotenv_candidate)
    if os.path.exists(_dotenv_path):
        try:
            from dotenv import load_dotenv
            load_dotenv(_dotenv_path, override=False)
        except ImportError:
            # python-dotenv no instalado: se asume que las variables vienen del entorno.
            pass
        break

logging.basicConfig(
    level=logging.WARNING,
    stream=sys.stderr,
    format="%(asctime)s [%(levelname)s] biorag-mcp: %(message)s",
)
logger = logging.getLogger(__name__)

from pydantic import Field  # ← agregado para documentación de parámetros

# --- Boot -------------------------------------------------------------------

_DEFAULT_DB = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "MemoryBioRAG_Data",
    "memory_biorag.db",
)
DB_PATH = os.environ.get("BIORAG_PATH") or _DEFAULT_DB

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.memory_store import SQLiteMemoryBioRAG
from core.sinapsis import auto_vincular, vincular_por_sinonimos
from core.categorizador import inferir_categoria
from middleware.auto_guardado import registrar_accion, analizar_y_autoguardar

# =============================================================================
# Configuración de Usuario (Override con variables de entorno)
# =============================================================================
# Los defaults están aquí. Para cambiar, setear la variable de entorno
# correspondiente o crear .env.local en la raíz del proyecto.
# =============================================================================

LIMITE_MCP = int(os.environ.get('BIORAG_LIMITE_MCP', '10'))
"""Límite de resultados por defecto en búsquedas MCP."""

THRESHOLD_RAFTAGA_MCP = float(os.environ.get('BIORAG_THRESHOLD_RAFTAGA', '0.5'))
"""Score mínimo para activar ráfaga automáticamente en MCP."""

PARAFRASIS_PENALTY = 0.95
"""Factor multiplicativo aplicado a resultados de variantes no exactas (paráfrasis).
El query original (i==0) mantiene factor 1.0; variantes penalizan ×0.95."""

ORACULO_MAX_CHARS = int(os.environ.get('BIORAG_ORACULO_MAX_CHARS', '12000'))
"""Máximo de caracteres devueltos por el oráculo NotebookLM.

Si la respuesta de NotebookLM excede este límite, se trunca y se agrega una
nota indicando que el contenido fue recortado. Esto evita que el output de la
tool sea truncado por el cliente MCP por exceso de tamaño.
"""

# --- Arranque de sesión ----------------------------------------------------

PROMPT_INICIO_NOTEBOOKLM = os.environ.get("BIORAG_PROMPT_INICIO", "").strip()
"""Prompt base enviado al oráculo NotebookLM al iniciar sesión.

Obligatorio si se desea generar el query para NotebookLM. Se configura mediante
la variable de entorno BIORAG_PROMPT_INICIO. El nombre del agente se concatena
al inicio con el formato 'Agente: prompt'. Si no esta seteada, la tool no
armara el query para NotebookLM.
"""

NOTEBOOK_ID_ORACULO = os.environ.get("BIORAG_NOTEBOOK_ID", "").strip()
"""Notebook ID del oráculo NotebookLM.

Obligatorio si se desea generar el query para NotebookLM. Se configura mediante
la variable de entorno BIORAG_NOTEBOOK_ID. Si no esta seteada, la tool no
incluira el notebooklm_query.
"""

QUERIES_BIORAG_INICIO = [
    "reglas comportamiento agentes OEC",
    "pilares inmutables agente",
    "protocolo pre-acción",
    "reglas código anti-overengineering",
    "lecciones clave programación",
    "perfil profesional usuario stack",
    "mapa almacenamiento memoria",
]
"""Búsquedas predefinidas que el oráculo de BioRAG ejecuta al arrancar."""

AGENTES_VALIDOS = {"athena", "artemis", "hermes"}
"""Agentes reconocidos por el ecosistema OEC."""


# --- Helpers ----------------------------------------------------------------

def _get_cerebro() -> SQLiteMemoryBioRAG:
    return SQLiteMemoryBioRAG(db_path=DB_PATH)


def _preview(text: str, limit: int = 1500) -> str:
    if not text:
        return ""
    return text[:limit] + ("..." if len(text) > limit else "")


def _interceptar(accion: str, texto: str, cerebro) -> dict | None:
    registrar_accion(accion, texto)
    resultado = analizar_y_autoguardar(cerebro)
    if resultado:
        logger.info("auto-guardado: %s (%s)", resultado["concepto"], resultado["categoria"])
    return resultado


# =============================================================================
# ORACLE_PROMPT — System-level instructions para FastMCP
# Se inyecta como `instructions=` en FastMCP. Es el contexto base del agente.
# NO mover a una tool ni a un parámetro — pertenece aquí como sistema.
# =============================================================================

ORACLE_PROMPT = (
    "BioRAG: sistema de memoria biomimetica compartida para agentes OEC. "
    "Expone una corteza cerebral con busqueda hibrida (FTS5 trigram + "
    "peso sinaptico + asociaciones), consolidacion por sueno, plasticidad "
    "sináptica (LTP/LTD), y comunicacion entre agentes. "
    "Usa estas herramientas para acceder a la memoria persistente "
    "de la familia OEC (Athena, Artemis, Hermes).\n\n"
    "## Mapeo Biológico (Cognición Real)\n\n"
    "Los nombres de las herramientas reflejan su función cognitiva, no su implementación técnica:\n"
    "- recordar → evocación de memoria (FTS5 + peso sináptico + ráfaga de reminiscencia)\n"
    "- aprender → percepción y codificación en corteza de corto plazo\n"
    "- consolidar → sueño LTP/LTD, poda sináptica, inhibición lateral\n"
    "- vincular → asociación hebbiana entre conceptos\n"
    "- introspeccion → autoexamen sináptico (estado de la corteza)\n"
    "- mapear → cartografía cortical (todos los nodos)\n"
    "Estos nombres no son metáfora — son la operación real que ejecuta el sistema.\n"
    "Usa el nombre biológico para alinear tu modelo interno con la función real.\n\n"
    "## El Oráculo (NotebookLM MemoryBioRAG)\n\n"
    "**PASO 0 OBLIGATORIO — ANTES DE CADA MENSAJE DE DENNYS:**\n\n"
    "INVARIAN MANDATORY: SIEMPRE, sin excepción, ANTES de responder CUALQUIER mensaje de Dennys "
    "—incluido un \"hola\" o cualquier saludo—, ejecutar "
    "`biorag_oraculo_inicio(agente='Athena')`. No saludar, no preguntar, "
    "no responder nada antes de ejecutar esta tool.\n\n"
    "`biorag_oraculo_inicio` devuelve:\n"
    "- **Modo NotebookLM con `oraculo`:** el CLI `nlm` está disponible y la tool "
    "ya consultó NotebookLM directamente. Usar la respuesta como contexto de arranque.\n"
    "- **Modo NotebookLM sin `oraculo`:** falta el CLI `nlm`. En ese caso ejecutar "
    "`notebooklm_notebook_query` en el notebook MemoryBioRAG "
    "(ID: `b2645e9b-8bce-4067-841a-7796af4a14f0`) usando el `notebooklm_query` "
    "que devolvió la tool.\n"
    "- **Modo `biorag_local`:** NotebookLM no está configurado. Usar el "
    "`contexto_biorag` que devolvió la tool.\n\n"
    "Solo si aún falta información después del paso anterior, leer archivos directamente.\n\n"
    "**¿POR QUÉ ES INNEGOCIABLE?**\n"
    "- Si no tengo datos en BioRAG de una sesión anterior, no voy a tener contexto "
    "por obra del espíritu santo. El oráculo ES mi memoria compartida. Sin él, opero a ciegas.\n"
    "- \"Tener dudas\" no es mi decisión — la consulta es automática e incondicional. "
    "No pregunto \"¿tengo dudas?\" antes de decidir si consulto. Consulto siempre.\n"
    "- Si el oráculo no tiene la información, lo sabré después de la consulta, "
    "no antes. Y en ese caso, pregunto a Dennys directamente.\n\n"
    "**La respuesta debe salir de tu entendimiento, no del RAG ni del cuaderno "
    "— son para recordar y complementar, no para generar desde ahí.**"
)


# --- MCP Server ------------------------------------------------------------

def _build_server():
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise ImportError(
            "BioRAG MCP server requires the 'mcp' package.\n"
            f"  pip install mcp\n  ({exc})"
        ) from exc

    # ORACLE_PROMPT va aquí como `instructions`: es el contexto base del agente.
    # FastMCP lo inyecta como system-level context — NO usar como descripción de tool.
    mcp = FastMCP(
        "biorag",
        instructions=ORACLE_PROMPT,
    )

    # ── TOOLS ────────────────────────────────────────────────────────────────

    def _recordar_impl(
        query: str,
        deep: bool = False,
        cat: Optional[str] = None,
        completo: bool = False,
        asociados: bool = False,
        limite: Optional[int] = None,
        preview_chars: Optional[int] = None,
        context_window: int = 0,
        forzar_rafaga: bool = False,
        rafaga_palabras: Optional[str] = None,
        pagina: int = 1,
        parafrasis: Optional[str] = None,
    ) -> str:
        if limite is None:
            limite = LIMITE_MCP
        cerebro = _get_cerebro()
        try:
            if preview_chars is None:
                preview_chars = 0 if completo else 1500

            rafaga_list = [w.strip() for w in rafaga_palabras.split(",")] if rafaga_palabras else None

            if forzar_rafaga and not rafaga_palabras:
                return json.dumps({
                    "status": "error",
                    "mensaje": "forzar_rafaga=True requiere rafaga_palabras. Pasa terminos separados por coma.",
                }, ensure_ascii=False)

            profundidad = "profundo" if deep else "activos"

            if parafrasis is not None and not parafrasis.strip():
                return json.dumps({
                    "status": "error",
                    "mensaje": "parafrasis es OBLIGATORIO y no puede estar vacío. "
                               "Genera 3-5 reformulaciones separadas por coma.",
                    "ejemplo": "parafrasis='el felino descansó,el minino reposó'",
                }, ensure_ascii=False)

            if parafrasis:
                if not parafrasis.strip():
                    return json.dumps({
                        "status": "error",
                        "mensaje": "parafrasis es OBLIGATORIO. Genera reformulaciones separadas por coma.",
                        "ejemplo": "parafrasis='el felino descansó,el minino reposó'",
                    }, ensure_ascii=False)
                parafrasis_list = [p.strip() for p in parafrasis.split(",") if p.strip()]
                if not parafrasis_list:
                    return json.dumps({
                        "status": "error",
                        "mensaje": "parafrasis es OBLIGATORIO. Genera reformulaciones separadas por coma.",
                        "ejemplo": "parafrasis='el felino descansó,el minino reposó'",
                    }, ensure_ascii=False)

            # Búsqueda normal PRIMERO — necesario para inicializar el merge
            # Pool interno amplio (limite*3): buscar amplio, recortar al final.
            # Emula el comportamiento de un RAG vectorial que rankea todo el índice.
            limite_interno = limite * 3
            resultados, total = cerebro.buscar_por_frase(
                query, profundidad=profundidad, pagina=pagina, limite=limite_interno,
                categoria=cat, preview_chars=preview_chars,
                context_window=context_window
            )
            score_top = resultados[0][4] if resultados else 0

            # Parafrasis SIEMPRE — el agente piensa, el sistema busca
            if parafrasis:
                queries = [query] + parafrasis_list
                merged = {r[0]: r for r in resultados}
                for i, q in enumerate(queries):
                    q_res, q_tot = cerebro.buscar_por_frase(
                        q, profundidad=profundidad, pagina=pagina, limite=limite_interno,
                        categoria=cat, preview_chars=preview_chars,
                        context_window=0
                    )
                    factor = 1.0 if i == 0 else PARAFRASIS_PENALTY
                    for r in q_res:
                        conc = r[0]
                        rp = (r[0], r[1], r[2], r[3], r[4] * factor, r[5])
                        if conc not in merged or rp[4] > merged[conc][4]:
                            merged[conc] = rp
                resultados = sorted(merged.values(), key=lambda r: r[4], reverse=True)[:limite]
                total = len(resultados)

            sinapsis_creadas = []
            score_top = resultados[0][4] if resultados else 0
            if rafaga_list and (forzar_rafaga or not resultados or score_top < THRESHOLD_RAFTAGA_MCP):
                resultados_rafaga, total_rafaga, sinapsis_creadas = cerebro.buscar_por_rafaga(
                    query, rafaga_list, pagina=pagina, limite=limite_interno
                )
                # Combinar resultados: ráfaga + originales (sin duplicados)
                if resultados_rafaga:
                    seen = {r[0] for r in resultados}
                    for r in resultados_rafaga:
                        if r[0] not in seen:
                            resultados.append(r)
                            seen.add(r[0])
                    total = total + total_rafaga

                # Re-ordenar por score híbrido y aplicar recorte estricto a limite
                resultados.sort(key=lambda r: r[4], reverse=True)
                resultados = resultados[:limite]

            resultados = resultados[:limite]
            if not resultados:
                cerebro.cerrar_sistema()
                # Señal de contingencia: la agente debe buscar en su contexto
                return json.dumps({
                    "total": 0,
                    "resultados": [],
                    "contingencia_contexto": True,
                    "mensaje": "No se encontraron recuerdos en la corteza. Busca en tu historial de conversacion o contexto actual."
                }, ensure_ascii=False)

            items = []
            for concepto, contenido, peso, estado, score, asociaciones in resultados:
                items.append({
                    "concepto": concepto,
                    "contenido": contenido,
                    "peso_sinaptico": peso,
                    "estado": estado,
                    "score_hibrido": score,
                    "asociaciones": [
                        v.strip() for v in (asociaciones or "").split(",") if v.strip()
                    ] if asociados and asociaciones else [],
                })

            limite_den = limite if (limite and limite > 0) else 1
            paginas_totales = math.ceil(total / limite_den)

            resultado = json.dumps({
                "total": total,
                "pagina_actual": pagina,
                "paginas_totales": paginas_totales,
                "resultados": items,
                "sinapsis_creadas": [{"origen": o, "destino": d, "peso": p} for o, d, p in sinapsis_creadas] if sinapsis_creadas else [],
                "profundidad": profundidad,
            }, ensure_ascii=False)
            _interceptar("recordar", query, cerebro)
            return resultado
        finally:
            cerebro.cerrar_sistema()

    @mcp.tool(
        name="recordar",
        description=(
            "[Cognitivo] Evoca recuerdos de la corteza mediante el pipeline completo: "
            "FTS5 trigram (memoria semántica) + peso sináptico (memoria de trabajo) + "
            "ráfaga de reminiscencia (asociación libre) + ventana de contexto (vecinos sinápticos).\n\n"
            "════════════════════════════════════════════════════════\n"
            "FLUJO OBLIGATORIO — 4 PASOS EN CASCADA. NO SALTEAR PASOS.\n"
            "Verificar campo JSON 'total' después de CADA llamada.\n"
            "════════════════════════════════════════════════════════\n\n"
            "PASO 1 — Búsqueda directa:\n"
            "  recordar(query='X')\n"
            "  Resultado → total >= 1: ir a SÍNTESIS\n"
            "  Resultado → total == 0: ir a PASO 2\n\n"
            "PASO 2 — Búsqueda con paráfrasis (variantes semánticas):\n"
            "  recordar(query='X', parafrasis='var1,var2,var3')\n"
            "  Generar variantes con 4 niveles ANTES de llamar:\n"
            "    N1 (Sinónimos): sustantivos equivalentes exactos\n"
            "    N2 (Registro): técnico ↔ coloquial\n"
            "    N3 (Perspectiva): ángulo opuesto o resultado\n"
            "    N4 (Abstracción): abstracto ↔ concreto\n"
            "  REGLA: NUNCA adjetivos abstractos. SIEMPRE sustantivos del dominio.\n"
            "  Resultado → total >= 1: ir a SÍNTESIS\n"
            "  Resultado → total == 0: ir a PASO 3\n\n"
            "PASO 3 — Búsqueda por ráfaga (asociación libre, 10-15 términos):\n"
            "  recordar(query='X', rafaga_palabras='t1,t2,...t15', forzar_rafaga=True)\n"
            "  Generar términos con 5 niveles:\n"
            "    N1 (Literal) N2 (Técnico) N3 (Contexto) N4 (Problema) N5 (Emoción)\n"
            "  REGLA: sustantivos literales, NUNCA adjetivos abstractos.\n"
            "  ERROR CRÍTICO: forzar_rafaga=True SIN rafaga_palabras → la tool retorna error inmediato.\n"
            "  Resultado → total >= 1: ir a SÍNTESIS\n"
            "  Resultado → total == 0: ir a PASO 4\n\n"
            "PASO 4 — Búsqueda combinada (paráfrasis + ráfaga juntas):\n"
            "  recordar(query='X', parafrasis='var1,var2,var3',\n"
            "           rafaga_palabras='t1,t2,...', forzar_rafaga=True)\n"
            "  Resultado → total >= 1: ir a SÍNTESIS\n"
            "  Resultado → total == 0: CONTINGENCIA — buscar en contexto/historial del chat\n\n"
            "════════════════════════════════════════════════════════\n"
            "SÍNTESIS — OBLIGATORIA después de cualquier PASO con total >= 1:\n"
            "════════════════════════════════════════════════════════\n"
            "1. Tomar array 'resultados' del JSON. Listar TODOS así:\n"
            "     '1. [concepto] (score X.XX) — resumen una línea'\n"
            "     '2. [concepto] (score X.XX) — resumen una línea'\n"
            "   PROHIBIDO omitir cualquier item. PROHIBIDO interpretar antes de listar.\n"
            "2. EXCEPCIÓN: top score >= 0.85 Y resto < 0.60\n"
            "   → mencionar top-1 como principal pero listar los demás igual.\n"
            "3. DESPUÉS de listar todos: consolidar, detectar contradicciones, responder.\n\n"
            "PIPELINE INTERNO DE PARÁFRASIS:\n"
            "  Query original → factor 1.0 | Cada variante → factor × 0.95\n"
            "  Merge por concepto: el mejor score gana\n"
            "  Variante sin match → ignorada sin error\n\n"
            "Retorna: {total, pagina_actual, paginas_totales, resultados[], sinapsis_creadas[], profundidad}\n\n"
            "NOTA — parámetro 'cat': acepta UNA sola categoría como string simple.\n"
            "  NO acepta listas ni comas. Valores válidos:\n"
            "  System | Architecture | Project | Lesson | Profile |\n"
            "  Personal | Principle | Protocol | Cognition | Relation | General\n\n"
            "NOTA — context_window: usar 1 o 2 para incluir vecinos sinápticos.\n"
            "  Aumenta recall a costa de más tokens en la respuesta."
        ),
    )
    def biorag_recordar(
        query: Annotated[str, Field(
            description=(
                "Texto o frase a evocar de la memoria. "
                "Usar sustantivos concretos del dominio (ej: 'error http timeout', 'patron singleton'). "
                "Evitar preguntas o frases largas — el motor es FTS5, no semántico puro."
            )
        )],
        deep: Annotated[bool, Field(
            description=(
                "Si True, busca también en nodos dormidos (estado='dormido'). "
                "Default False: solo nodos activos. "
                "Usar cuando la búsqueda normal no encuentra resultados esperados."
            )
        )] = False,
        cat: Annotated[Optional[str], Field(
            description=(
                "Filtrar resultados por categoría (string simple, NO lista, NO comas). "
                "Valores: System | Architecture | Project | Lesson | Profile | "
                "Personal | Principle | Protocol | Cognition | Relation | General. "
                "Si se omite, busca en todas las categorías."
            )
        )] = None,
        completo: Annotated[bool, Field(
            description=(
                "Si True, devuelve el contenido completo de cada resultado sin truncar "
                "(ignora preview_chars). Usar solo cuando se necesita el texto íntegro — "
                "puede generar respuestas muy largas."
            )
        )] = False,
        asociados: Annotated[bool, Field(
            description=(
                "Si True, incluye en cada resultado la lista de conceptos sinápticos asociados. "
                "Útil para explorar la red de memoria y encontrar conceptos relacionados."
            )
        )] = False,
        limite: Annotated[Optional[int], Field(
            description=(
                f"Máximo de resultados a devolver. "
                f"Default: {LIMITE_MCP} (configurable via BIORAG_LIMITE_MCP). "
                "Reducir para respuestas más compactas, aumentar para exploración exhaustiva."
            )
        )] = None,
        preview_chars: Annotated[Optional[int], Field(
            description=(
                "Caracteres de contenido a devolver por resultado. "
                "Default: 1500 (o 0 si completo=True). "
                "Reducir a 500-800 para respuestas compactas."
            )
        )] = None,
        context_window: Annotated[int, Field(
            description=(
                "Vecinos sinápticos a incluir alrededor de cada resultado (0=ninguno, 1=vecinos directos, 2=vecinos de vecinos). "
                "Aumenta recall semántico a costa de más tokens. Default: 0."
            ),
            ge=0,
            le=2,
        )] = 0,
        forzar_rafaga: Annotated[bool, Field(
            description=(
                "Si True, ejecuta modo ráfaga aunque ya haya resultados en la búsqueda normal. "
                "REQUIERE rafaga_palabras — sin él la tool retorna error. "
                "Usar en PASO 3 y PASO 4 del flujo obligatorio."
            )
        )] = False,
        rafaga_palabras: Annotated[Optional[str], Field(
            description=(
                "Términos de ráfaga separados por coma, sin espacios extra "
                "(ej: 'error,fallo,excepción,bug,traza,timeout,conexión'). "
                "Usar 10-15 términos de 5 niveles: Literal, Técnico, Contexto, Problema, Emoción. "
                "Obligatorio si forzar_rafaga=True."
            )
        )] = None,
        pagina: Annotated[int, Field(
            description=(
                "Página de resultados (base 1). "
                "Usar junto con 'limite' para paginar resultados extensos. "
                "Ver campo 'paginas_totales' en la respuesta para saber cuántas hay."
            ),
            ge=1,
        )] = 1,
        parafrasis: Annotated[Optional[str], Field(
            description=(
                "Reformulaciones del query separadas por coma "
                "(ej: 'fallo de red,error de conexión,timeout HTTP'). "
                "(ej: 'el gato se sentó, el felino descansó, el minino reposó'). "
                "Usar en PASO 2 y PASO 4 del flujo. "
                "NUNCA pasar string vacío — omitir el parámetro si no hay variantes. "
                "Cada variante recibe un factor de penalización ×0.95 sobre el score."
            )
        )] = None,
    ) -> str:
        return _recordar_impl(
            query, deep, cat, completo, asociados, limite, preview_chars,
            context_window, forzar_rafaga, rafaga_palabras, pagina, parafrasis
        )

    @mcp.tool(
        name="buscar",
        description=(
            "(legado) Alias de 'recordar' — preferir 'recordar' para identificar la operación cognitiva real. "
            "Misma funcionalidad y parámetros completos. "
            "El flujo de 4 pasos aplica igualmente (ver descripción de 'recordar').\n\n"
            "Parámetros: query (str), deep (bool), cat (str), completo (bool), asociados (bool), "
            "limite (int), preview_chars (int), context_window (int 0-2), "
            "forzar_rafaga (bool), rafaga_palabras (str), pagina (int), parafrasis (str).\n\n"
            "Retorna: {total, pagina_actual, paginas_totales, resultados[], sinapsis_creadas[], profundidad}"
        ),
    )
    def biorag_buscar(
        query: Annotated[str, Field(description="Texto o frase a buscar en la memoria.")],
        deep: Annotated[bool, Field(description="Si True, incluye nodos dormidos en la búsqueda.")] = False,
        cat: Annotated[Optional[str], Field(description="Filtrar por categoría (string simple). Ver listar_categorias para valores válidos.")] = None,
        completo: Annotated[bool, Field(description="Si True, devuelve contenido completo sin truncar.")] = False,
        asociados: Annotated[bool, Field(description="Si True, incluye asociaciones sinápticas en cada resultado.")] = False,
        limite: Annotated[Optional[int], Field(description=f"Máximo de resultados. Default: {LIMITE_MCP}.")] = None,
        preview_chars: Annotated[Optional[int], Field(description="Caracteres de preview por resultado. Default: 1500.")] = None,
        context_window: Annotated[int, Field(description="Vecinos sinápticos a incluir (0=ninguno, 1-2=vecinos).", ge=0, le=2)] = 0,
        forzar_rafaga: Annotated[bool, Field(description="Fuerza ráfaga aunque haya resultados. Requiere rafaga_palabras.")] = False,
        rafaga_palabras: Annotated[Optional[str], Field(description="Términos de ráfaga separados por coma. Obligatorio si forzar_rafaga=True.")] = None,
        pagina: Annotated[int, Field(description="Página de resultados (base 1).", ge=1)] = 1,
        parafrasis: Annotated[Optional[str], Field(description="Reformulaciones del query separadas por coma. Usar en PASO 2 y 4.")] = None,
    ) -> str:
        return _recordar_impl(
            query, deep, cat, completo, asociados, limite, preview_chars,
            context_window, forzar_rafaga, rafaga_palabras, pagina, parafrasis
        )

    # ── APRENDER ─────────────────────────────────────────────────────────────
    # NOTA: _aprender_impl es la implementación privada compartida.
    # El @mcp.tool va en biorag_aprender (función pública) y en biorag_guardar (legado).
    # NO decorar _aprender_impl directamente — el agente no vería los parámetros bien.

    def _aprender_impl(
        concepto: str,
        contenido: str,
        syn: Optional[str] = None,
        cat: Optional[str] = None,
    ) -> str:
        cerebro = _get_cerebro()
        try:
            clave = concepto.lower().replace(" ", "_")
            categoria = cat or inferir_categoria(contenido)
            try:
                cerebro._resolver_categoria_id(categoria)
            except ValueError as e:
                return json.dumps({
                    "status": "error",
                    "mensaje": str(e),
                }, ensure_ascii=False)
            cerebro.percibir_corto_plazo(clave, contenido, syn or "", categoria)

            enlaces = auto_vincular(cerebro, clave, contenido)
            sinapsis_count = len(enlaces)

            if syn:
                syn_enlaces = vincular_por_sinonimos(cerebro, clave, syn)
                todas = list({e[0]: e for e in enlaces + syn_enlaces}.values())
                sinapsis_count = len(todas)

            msg = f"'{clave}' aprendido en corto plazo."
            if syn:
                msg += f" Sinonimos: {syn}."
            if categoria != "general":
                msg += f" Categoria: {categoria}."
            if sinapsis_count:
                msg += f" Vinculado con {sinapsis_count} nodo(s)."
            msg += " Usa 'consolidar' para fijar a largo plazo."
            _interceptar("aprender", f"{clave}: {contenido}", cerebro)
            return json.dumps({
                "status": "ok",
                "mensaje": msg,
                "concepto": clave,
                "sinapsis": sinapsis_count,
            }, ensure_ascii=False)
        finally:
            cerebro.cerrar_sistema()

    @mcp.tool(
        name="aprender",
        description=(
            "[Cognitivo] Codifica una experiencia nueva en la corteza de corto plazo (percepción). "
            "Equivalente a la codificación inicial de un recuerdo en el hipocampo. "
            "El concepto se normaliza automáticamente a snake_case minúsculas. "
            "Crea sinapsis automáticas con nodos relacionados via auto_vincular.\n\n"
            "IMPORTANTE: el recuerdo queda en corto plazo hasta que se llame 'consolidar' "
            "para fijarlo a largo plazo (LTP). Sin consolidación, puede perderse en el siguiente ciclo.\n\n"
            "Categorías válidas (parámetro cat):\n"
            "  System | Architecture | Project | Lesson | Profile |\n"
            "  Personal | Principle | Protocol | Cognition | Relation | General\n"
            "  Si no se especifica, la categoría se infiere automáticamente del contenido.\n\n"
            "Retorna: {status, mensaje, concepto (clave normalizada), sinapsis (int: nodos vinculados)}"
        ),
    )
    def biorag_aprender(
        concepto: Annotated[str, Field(
            description=(
                "Nombre único del recuerdo. Se normaliza a snake_case minúsculas automáticamente "
                "(ej: 'Error HTTP 500' → 'error_http_500'). "
                "Usar nombres descriptivos y específicos del dominio."
            )
        )],
        contenido: Annotated[str, Field(
            description=(
                "Texto o conocimiento a almacenar. "
                "Debe ser autocontenido — incluir suficiente contexto para que sea útil "
                "sin necesitar la conversación original. "
                "Recomendado: 100-1000 caracteres por nodo."
            )
        )],
        syn: Annotated[Optional[str], Field(
            description=(
                "Sinónimos o alias del concepto, separados por coma "
                "(ej: 'fallo,error,excepción,crash'). "
                "Mejoran el recall en búsquedas futuras — incluir términos alternativos conocidos."
            )
        )] = None,
        cat: Annotated[Optional[str], Field(
            description=(
                "Categoría del recuerdo. Si se omite, se infiere del contenido automáticamente. "
                "Valores: System | Architecture | Project | Lesson | Profile | "
                "Personal | Principle | Protocol | Cognition | Relation | General. "
                "Usar listar_categorias para ver descripciones de cada una."
            )
        )] = None,
    ) -> str:
        return _aprender_impl(concepto, contenido, syn, cat)

    @mcp.tool(
        name="guardar",
        description=(
            "(legado) Alias de 'aprender' — preferir 'aprender' para identificar la operación cognitiva real. "
            "Misma funcionalidad y parámetros.\n\n"
            "Parámetros: concepto (str), contenido (str), syn (str opcional), cat (str opcional).\n\n"
            "Retorna: {status, mensaje, concepto (str normalizado), sinapsis (int)}"
        ),
    )
    def biorag_guardar(
        concepto: Annotated[str, Field(description="Nombre único del recuerdo (se normaliza a snake_case).")],
        contenido: Annotated[str, Field(description="Texto o conocimiento a almacenar.")],
        syn: Annotated[Optional[str], Field(description="Sinónimos separados por coma.")] = None,
        cat: Annotated[Optional[str], Field(description="Categoría. Ver aprender para valores válidos.")] = None,
    ) -> str:
        return _aprender_impl(concepto, contenido, syn, cat)

    @mcp.tool(
        name="vincular",
        description=(
            "[Cognitivo] Establece una asociación hebbiana bidireccional entre dos conceptos. "
            "Equivalente a la potenciación a largo plazo (LTP) entre neuronas co-activadas. "
            "El enlace sináptico permite que evocar un concepto active al otro en búsquedas futuras. "
            "Ambos conceptos deben existir previamente en la corteza (largo_plazo o corto_plazo). "
            "La asociación es bidireccional: a ↔ b.\n\n"
            "Retorna: {status, mensaje}"
        ),
    )
    def biorag_vincular(
        a: Annotated[str, Field(
            description=(
                "Primer concepto a vincular. "
                "Debe existir en la corteza (largo_plazo o corto_plazo). "
                "Usar la clave normalizada (snake_case)."
            )
        )],
        b: Annotated[str, Field(
            description=(
                "Segundo concepto a vincular. "
                "La asociación es bidireccional: evocar 'a' activa 'b' y viceversa. "
                "Usar la clave normalizada (snake_case)."
            )
        )],
    ) -> str:
        cerebro = _get_cerebro()
        try:
            cerebro.establecer_asociacion(a, b)
            _interceptar("vincular", f"{a} <--> {b}", cerebro)
            return json.dumps({
                "status": "ok",
                "mensaje": f"Sinapsis: '{a}' <--> '{b}'",
            }, ensure_ascii=False)
        finally:
            cerebro.cerrar_sistema()

    @mcp.tool(
        name="asociar",
        description=(
            "(legado) Alias de 'vincular' — preferir 'vincular' para identificar la operación cognitiva real. "
            "Parámetros: a (str), b (str) — ambos deben existir en la corteza. "
            "Retorna: {status, mensaje}"
        ),
    )
    def biorag_asociar(
        a: Annotated[str, Field(description="Primer concepto (clave normalizada).")],
        b: Annotated[str, Field(description="Segundo concepto (clave normalizada). La asociación es bidireccional.")],
    ) -> str:
        return biorag_vincular(a, b)

    @mcp.tool(
        name="comunicar",
        description=(
            "Envía un mensaje al canal compartido entre agentes OEC. "
            "El mensaje queda persistido en la BD y puede ser leído por el destinatario "
            "con 'leer_mensajes'. Usar para coordinación asíncrona entre Athena, Artemis y Hermes.\n\n"
            "El agente origen se identifica automáticamente via env AGENT_NAME si no se pasa 'origen'.\n\n"
            "Retorna: {status, mensaje}"
        ),
    )
    def biorag_comunicar(
        destino: Annotated[str, Field(
            description=(
                "Agente destinatario del mensaje. "
                "Valores: 'athena', 'artemis', 'hermes', o 'todos' para broadcast a todos los agentes."
            )
        )],
        mensaje: Annotated[str, Field(
            description=(
                "Contenido del mensaje. Ser específico e incluir contexto suficiente "
                "para que el receptor entienda sin historial previo de la conversación."
            )
        )],
        origen: Annotated[Optional[str], Field(
            description=(
                "Nombre del agente que envía el mensaje. "
                "Si se omite, se lee de la variable de entorno AGENT_NAME. "
                "Si AGENT_NAME tampoco está seteada, queda como 'desconocido'."
            )
        )] = None,
    ) -> str:
        agente = origen or os.environ.get("AGENT_NAME", "desconocido")
        cerebro = _get_cerebro()
        try:
            cerebro.enviar_comunicado(agente, destino, mensaje)
            _interceptar("comunicar", f"{agente} -> {destino}: {mensaje}", cerebro)
            return json.dumps({
                "status": "ok",
                "mensaje": f"Mensaje de {agente} para {destino} registrado.",
            }, ensure_ascii=False)
        finally:
            cerebro.cerrar_sistema()

    @mcp.tool(
        name="leer_mensajes",
        description=(
            "Lee mensajes del canal compartido entre agentes OEC. "
            "Los mensajes no leídos se marcan automáticamente como leídos al consultarlos. "
            "Usar al inicio de sesión para ver si hay mensajes de otros agentes.\n\n"
            "Retorna: {total (int), mensajes: [{id, origen, destino, contenido, timestamp, leido}]}"
        ),
    )
    def biorag_leer_mensajes(
        no_leidos: Annotated[bool, Field(
            description=(
                "Si True, devuelve solo mensajes no leídos. "
                "Si False, devuelve los últimos N mensajes independiente del estado de lectura."
            )
        )] = False,
        ultimos: Annotated[int, Field(
            description=(
                "Cantidad máxima de mensajes a devolver (más recientes primero). "
                "Default: 10."
            ),
            ge=1,
        )] = 10,
        para: Annotated[Optional[str], Field(
            description=(
                "Filtrar mensajes por destinatario específico (ej: 'athena', 'todos'). "
                "Si se omite, devuelve mensajes para todos los destinos."
            )
        )] = None,
    ) -> str:
        cerebro = _get_cerebro()
        try:
            mensajes = cerebro.leer_comunicados(
                destino=para, solo_no_leidos=no_leidos, ultimos=ultimos
            )
            if not mensajes:
                return json.dumps({"total": 0, "mensajes": []}, ensure_ascii=False)

            items = []
            ids_a_marcar = []
            for msg_id, origen, dest, contenido, ts, leido in reversed(mensajes):
                items.append({
                    "id": msg_id,
                    "origen": origen,
                    "destino": dest,
                    "contenido": contenido,
                    "timestamp": time.strftime("%Y-%m-%d %H:%M", time.localtime(ts)),
                    "leido": bool(leido),
                })
                if not leido:
                    ids_a_marcar.append(msg_id)

            if ids_a_marcar:
                cerebro.marcar_como_leido(ids_a_marcar)

            resultado = json.dumps({"total": len(items), "mensajes": items}, ensure_ascii=False)
            if items:
                textos = [m["contenido"] for m in items[:3]]
                _interceptar("leer_mensajes", " ".join(textos), cerebro)
            return resultado
        finally:
            cerebro.cerrar_sistema()

    @mcp.tool(
        name="consolidar",
        description=(
            "[Cognitivo] Consolida la memoria de corto plazo a largo plazo mediante sueño cognitivo. "
            "Ejecutar después de 'aprender' para fijar los recuerdos nuevos permanentemente.\n\n"
            "Operaciones del ciclo de sueño:\n"
            "  - LTP (potenciación a largo plazo): fortalece nodos nuevos activos\n"
            "  - LTD (depresión a largo plazo): decae nodos poco accedidos\n"
            "  - Poda sináptica: elimina conexiones débiles\n"
            "  - Inhibición lateral: evita saturación de la corteza\n"
            "  - Sleep transfer: mueve nodos de corto_plazo → largo_plazo\n\n"
            "Equivalente al sueño de ondas lentas en el hipocampo.\n"
            "Si limite_energia se omite, se calcula dinámicamente (n_activos × 1.6, mín 10.0).\n\n"
            "Retorna: {status, mensaje (log completo del ciclo de sueño)}"
        ),
    )
    def biorag_consolidar(
        limite_energia: Annotated[Optional[float], Field(
            description=(
                "Energía sináptica máxima del ciclo. Controla cuántos nodos se consolidan por ciclo. "
                "Si se omite, se calcula dinámicamente como n_activos × 1.6 (mín 10.0). "
                "Valores más altos consolidan más nodos por ciclo."
            )
        )] = None,
    ) -> str:
        cerebro = _get_cerebro()
        try:
            old_stdout = sys.stdout
            sys.stdout = captured = io.StringIO()
            try:
                cerebro.ciclo_sueno_consolidacion(limite_energia=limite_energia)
            finally:
                sys.stdout = old_stdout
            output = captured.getvalue()
            _interceptar("consolidar", output.strip(), cerebro)
            return json.dumps({
                "status": "ok",
                "mensaje": output.strip(),
            }, ensure_ascii=False)
        finally:
            cerebro.cerrar_sistema()

    @mcp.tool(
        name="sueno",
        description=(
            "(legado) Alias de 'consolidar' — preferir 'consolidar' para identificar la operación cognitiva real. "
            "Parámetro: limite_energia (float, opcional) — energía máxima del ciclo de consolidación. "
            "Retorna: {status, mensaje}"
        ),
    )
    def biorag_sueno(
        limite_energia: Annotated[Optional[float], Field(
            description="Energía máxima del ciclo. Si se omite, se calcula dinámicamente (n_activos × 1.6, mín 10.0)."
        )] = None,
    ) -> str:
        return biorag_consolidar(limite_energia)

    @mcp.tool(
        name="introspeccion",
        description=(
            "[Cognitivo] Autoexamen sináptico de la corteza. "
            "Devuelve el estado actual de la memoria sin modificar nada. "
            "Usar para diagnosticar la salud de la corteza, "
            "verificar si hay nodos pendientes de consolidar, "
            "o monitorear el uso de energía sináptica.\n\n"
            "Sin parámetros.\n\n"
            "Retorna: {activos (int), dormidos (int), corto_plazo (int), energia_sinaptica (float)}"
        ),
    )
    def biorag_introspeccion() -> str:
        cerebro = _get_cerebro()
        try:
            cerebro.cursor.execute(
                "SELECT COUNT(*) FROM largo_plazo WHERE estado = 'activo'"
            )
            activos = cerebro.cursor.fetchone()[0]
            cerebro.cursor.execute(
                "SELECT COUNT(*) FROM largo_plazo WHERE estado = 'dormido'"
            )
            dormidos = cerebro.cursor.fetchone()[0]
            cerebro.cursor.execute("SELECT COUNT(*) FROM corto_plazo")
            corto = cerebro.cursor.fetchone()[0]
            cerebro.cursor.execute(
                "SELECT ROUND(SUM(peso_sinaptico), 2) FROM largo_plazo WHERE estado = 'activo'"
            )
            energia = cerebro.cursor.fetchone()[0] or 0.0
            resultado = json.dumps({
                "activos": activos,
                "dormidos": dormidos,
                "corto_plazo": corto,
                "energia_sinaptica": energia,
            }, ensure_ascii=False)
            _interceptar("introspeccion", f"activos:{activos} dormidos:{dormidos}", cerebro)
            return resultado
        finally:
            cerebro.cerrar_sistema()

    @mcp.tool(
        name="estado",
        description=(
            "(legado) Alias de 'introspeccion' — preferir 'introspeccion' para identificar la operación cognitiva real. "
            "Sin parámetros. "
            "Retorna: {activos (int), dormidos (int), corto_plazo (int), energia_sinaptica (float)}"
        ),
    )
    def biorag_estado() -> str:
        return biorag_introspeccion()

    @mcp.tool(
        name="mapear",
        description=(
            "[Cognitivo] Cartografía cortical completa. "
            "Lista TODOS los nodos de la corteza permanente (activos y dormidos) "
            "ordenados por peso sináptico descendente.\n\n"
            "Usar para:\n"
            "  - Explorar qué conceptos hay en la memoria\n"
            "  - Detectar nodos huérfanos (sin asociaciones)\n"
            "  - Revisar la distribución por categorías\n"
            "  - Verificar que un concepto fue aprendido correctamente\n\n"
            "Advertencia: puede devolver muchos nodos en cortezas grandes. "
            "Sin parámetros.\n\n"
            "Retorna: {total (int), nodos: [{concepto, categoria, peso_sinaptico, estado, asociaciones[]}]}"
        ),
    )
    def biorag_mapear() -> str:
        cerebro = _get_cerebro()
        try:
            cerebro.cursor.execute(
                "SELECT concepto, categoria, peso_sinaptico, estado, asociaciones "
                "FROM largo_plazo ORDER BY peso_sinaptico DESC, estado ASC"
            )
            filas = cerebro.cursor.fetchall()
            items = [
                {
                    "concepto": c,
                    "categoria": cat,
                    "peso_sinaptico": p,
                    "estado": est,
                    "asociaciones": [v.strip() for v in (a or "").split(",") if v.strip()],
                }
                for c, cat, p, est, a in filas
            ]
            resultado = json.dumps({"total": len(items), "nodos": items}, ensure_ascii=False)
            _interceptar("mapear", "", cerebro)
            return resultado
        finally:
            cerebro.cerrar_sistema()

    @mcp.tool(
        name="corteza",
        description=(
            "(legado) Alias de 'mapear' — preferir 'mapear' para identificar la operación cognitiva real. "
            "Sin parámetros. "
            "Retorna: {total (int), nodos: [{concepto, categoria, peso_sinaptico, estado, asociaciones[]}]}"
        ),
    )
    def biorag_corteza() -> str:
        return biorag_mapear()

    @mcp.tool(
        name="listar_categorias",
        description=(
            "Lista todas las categorías válidas del sistema para guardar recuerdos. "
            "Consultar ANTES de llamar 'aprender' (o 'guardar') para asegurarse de usar "
            "un valor de cat válido y conocer la descripción de cada una.\n\n"
            "Sin parámetros.\n\n"
            "Retorna: {total (int), categorias: [{id (int), nombre (str), descripcion (str)}]}"
        ),
    )
    def biorag_listar_categorias() -> str:
        cerebro = _get_cerebro()
        try:
            cats = cerebro.listar_categorias()
            items = [{"id": cid, "nombre": name, "descripcion": desc} for cid, name, desc in cats]
            return json.dumps({"total": len(items), "categorias": items}, ensure_ascii=False)
        finally:
            cerebro.cerrar_sistema()

    # ── TOOLS (Interceptor V2) ──────────────────────────────────────────────

    @mcp.tool(
        name="contexto_inicio",
        description=(
            "Anuncia el inicio de una interacción significativa. "
            "Almacena el contexto en el buffer de sesión para que el interceptor "
            "pueda detectar y autoguardar información relevante durante la conversación "
            "(lecciones, patrones, errores, preferencias). "
            "Llamar al inicio de cada sesión de trabajo importante.\n\n"
            "Retorna: {status, mensaje}"
        ),
    )
    def biorag_contexto_inicio(
        agente: Annotated[str, Field(
            description=(
                "Nombre del agente que inicia la sesión "
                "(ej: 'Athena', 'Artemis', 'Hermes'). "
                "Se incluye en el buffer de sesión para identificar la autoría."
            )
        )],
        contexto: Annotated[str, Field(
            description=(
                "Descripción breve del contexto o tarea de la sesión "
                "(ej: 'Refactor del módulo de autenticación', 'Análisis de logs de producción'). "
                "Ayuda al interceptor a categorizar correctamente los autoguardados."
            )
        )] = "",
    ) -> str:
        cerebro = _get_cerebro()
        try:
            registrar_accion("inicio", f"[{agente}] {contexto}")
            return json.dumps({"status": "ok", "mensaje": "Contexto de inicio registrado."}, ensure_ascii=False)
        finally:
            cerebro.cerrar_sistema()

    @mcp.tool(
        name="contexto_fin",
        description=(
            "Anuncia el fin de una interacción. "
            "Fuerza el análisis del buffer de sesión acumulado y autoguarda si detecta "
            "información nueva relevante (lecciones, patrones, errores, preferencias del usuario). "
            "Si hay nodos pendientes en corto_plazo, ejecuta auto-sueño para consolidarlos. "
            "Llamar al final de cada sesión de trabajo importante.\n\n"
            "Retorna: {status, mensaje, auto_guardado (objeto con concepto/categoria, o null si no hubo guardado)}"
        ),
    )
    def biorag_contexto_fin(
        agente: Annotated[str, Field(
            description="Nombre del agente que cierra la sesión (ej: 'Athena', 'Artemis', 'Hermes')."
        )],
        resumen: Annotated[str, Field(
            description=(
                "Resumen breve de lo que se hizo en la sesión "
                "(ej: 'Corregimos el bug de autenticación y actualizamos los tests'). "
                "Mejora la calidad y relevancia del autoguardado detectado por el interceptor."
            )
        )] = "",
    ) -> str:
        cerebro = _get_cerebro()
        try:
            registrar_accion("fin", f"[{agente}] {resumen}")
            resultado = analizar_y_autoguardar(cerebro, fuerza=True)
            if resultado:
                consolidado = cerebro.consolidar_concepto(resultado["concepto"])
                if consolidado:
                    msg = f"Auto-guardado y consolidado: '{resultado['concepto']}' ({resultado['categoria']}). Ya en corteza permanente."
                else:
                    msg = f"Auto-guardado en corto plazo: '{resultado['concepto']}'. Consolidacion pendiente."
            else:
                msg = "No se detecto nada nuevo que amerite guardado."

            # Auto-sueño: consolidar si hay datos en corto_plazo
            cerebro.cursor.execute("SELECT COUNT(*) FROM corto_plazo")
            n_corto = cerebro.cursor.fetchone()[0]
            if n_corto > 0:
                old_stdout = sys.stdout
                sys.stdout = captured = io.StringIO()
                try:
                    cerebro.ciclo_sueno_consolidacion()
                finally:
                    sys.stdout = old_stdout
                sleep_output = captured.getvalue().strip()
                msg += f" | Auto-sueño: {n_corto} nodo(s) consolidado(s)."

            return json.dumps({
                "status": "ok",
                "mensaje": msg,
                "auto_guardado": resultado,
            }, ensure_ascii=False)
        finally:
            cerebro.cerrar_sistema()

    def _buscar_contexto_biorag_arranque(cerebro, agente: str) -> dict:
        """Consulta BioRAG con queries predefinidas y devuelve un resumen."""
        hallazgos = []
        for q in QUERIES_BIORAG_INICIO:
            try:
                resultados, _ = cerebro.buscar_por_frase(
                    q,
                    profundidad="activos",
                    limite=2,
                    preview_chars=1000,
                )
                for concepto, contenido, peso, estado, score, asociaciones in resultados:
                    hallazgos.append({
                        "concepto": concepto,
                        "contenido": _preview(contenido, 1000),
                        "peso_sinaptico": peso,
                        "estado": estado,
                        "score_hibrido": score,
                    })
            except Exception as exc:
                logger.warning("Error consultando '%s' en arranque: %s", q, exc)
        return {
            "agente": agente,
            "total_hallazgos": len(hallazgos),
            "hallazgos": hallazgos,
        }

    def _nlm_detectado() -> bool:
        """Devuelve True si el CLI nlm esta disponible en PATH."""
        return shutil.which("nlm") is not None

    def _consultar_notebooklm(notebook_id: str, query: str) -> dict | None:
        """Consulta el cuaderno NotebookLM via CLI nlm y devuelve la respuesta.

        Si nlm no esta disponible, o si nlm falla por cualquier motivo
        (incluyendo query muy largo rechazado por Google), devuelve None
        para que el llamador decida devolver el query preparado en lugar
        del resultado del oraculo.
        """
        if not _nlm_detectado():
            return None
        try:
            result = subprocess.run(
                ["nlm", "notebook", "query", notebook_id, query],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                error_detail = result.stderr.strip() or result.stdout.strip()
                logger.warning(
                    "nlm fallo (codigo %s): %s",
                    result.returncode,
                    error_detail[:500],
                )
                return None
            return {
                "status": "ok",
                "respuesta": result.stdout.strip(),
            }
        except subprocess.TimeoutExpired:
            logger.warning("nlm excedio el tiempo de espera")
            return None
        except Exception as exc:
            logger.warning("Error ejecutando nlm: %s", exc)
            return None

    @mcp.tool(
        name="oraculo_inicio",
        description=(
            "⚡ OBLIGATORIO AL INICIO DE CADA INTERACCIÓN — invocar PRIMERO, antes de responder cualquier cosa.\n\n"
            "Carga el contexto de arranque del agente desde el oráculo (NotebookLM o BioRAG local). "
            "Sin esta tool, el agente opera sin memoria de sesiones anteriores.\n\n"
            "═══════════════════════════════════════════════════════\n"
            "MODOS DE OPERACIÓN — determinados automáticamente por variables de entorno:\n"
            "═══════════════════════════════════════════════════════\n\n"
            "MODO A — NotebookLM con CLI nlm disponible:\n"
            "  Condición: BIORAG_PROMPT_INICIO + BIORAG_NOTEBOOK_ID seteados + nlm instalado\n"
            "  Respuesta: campo 'oraculo' con respuesta directa de NotebookLM\n"
            "  Acción: usar 'oraculo' como contexto de arranque\n\n"
            "MODO B — NotebookLM sin CLI nlm (o nlm falló):\n"
            "  Condición: variables seteadas pero nlm no disponible o rechazó el query\n"
            "  Respuesta: campo 'notebooklm_query' con el query preparado\n"
            "  Acción: ejecutar notebooklm_notebook_query con ese query\n"
            "  ID notebook MemoryBioRAG: b2645e9b-8bce-4067-841a-7796af4a14f0\n\n"
            "MODO C — BioRAG local (NotebookLM no configurado):\n"
            "  Condición: faltan BIORAG_PROMPT_INICIO o BIORAG_NOTEBOOK_ID\n"
            "  Respuesta: campo 'contexto_biorag' con hallazgos de la corteza\n"
            "  Acción: usar 'contexto_biorag' como punto de partida\n\n"
            "Identificar el modo activo por el campo 'modo': 'notebooklm' o 'biorag_local'.\n"
            "Para modo 'notebooklm': si la respuesta tiene 'oraculo' → MODO A. Si no → MODO B.\n\n"
            "Retorna: {status, modo, agente, ...campos según modo activo}"
        ),
    )
    def biorag_oraculo_inicio(
        agente: Annotated[str, Field(
            description=(
                "Nombre del agente que inicia sesión. "
                "Valores válidos: 'athena', 'artemis', 'hermes' (case-insensitive). "
                "La tool retorna error si se omite o si el valor no es uno de los válidos."
            )
        )],
        contexto_adicional: Annotated[str, Field(
            description=(
                "Contexto extra para enriquecer el query enviado a NotebookLM "
                "(ej: 'Trabajando en refactor de autenticación', 'Sesión de debugging producción'). "
                "Solo aplica en MODO A y MODO B (NotebookLM). "
                "Ignorado en MODO C (BioRAG local)."
            )
        )] = "",
    ) -> str:
        if not agente or not agente.strip():
            return json.dumps({
                "status": "error",
                "mensaje": "El parámetro `agente` es obligatorio. Ejemplo: agente='Athena'.",
            }, ensure_ascii=False)

        agente_limpio = agente.strip().lower()
        if agente_limpio not in AGENTES_VALIDOS:
            return json.dumps({
                "status": "error",
                "mensaje": f"Agente '{agente}' no reconocido. Agentes válidos: {', '.join(sorted(AGENTES_VALIDOS))}.",
            }, ensure_ascii=False)

        tiene_prompt = bool(PROMPT_INICIO_NOTEBOOKLM)
        tiene_notebook_id = bool(NOTEBOOK_ID_ORACULO)

        if tiene_prompt and tiene_notebook_id:
            # Modo NotebookLM: armar query y consultar si nlm esta disponible.
            query_notebook = f"{agente.strip()}: {PROMPT_INICIO_NOTEBOOKLM}"
            if contexto_adicional and contexto_adicional.strip():
                query_notebook += f" Contexto adicional: {contexto_adicional.strip()}"

            oraculo = _consultar_notebooklm(NOTEBOOK_ID_ORACULO, query_notebook)

            if oraculo is None:
                # nlm no esta disponible o fallo (por ejemplo, query muy largo).
                # Devolver query preparado para consulta manual via notebooklm_notebook_query.
                nlm_installed = _nlm_detectado()
                resultado = {
                    "status": "ok",
                    "modo": "notebooklm",
                    "agente": agente_limpio,
                    "notebooklm_notebook_id": NOTEBOOK_ID_ORACULO,
                    "notebooklm_query": query_notebook,
                    "nlm_detectado": nlm_installed,
                }
                if nlm_installed:
                    resultado["nlm_fallo"] = True
                    resultado["mensaje"] = (
                        "nlm CLI detectado pero rechazo el query (posiblemente por exceder "
                        "su limite interno de longitud). Usa notebooklm_notebook_query con "
                        "notebooklm_query para consultar el oraculo."
                    )
                    resultado["advertencia"] = (
                        "Este fallo es un limite del CLI 'nlm', no de BioRAG. "
                        "La tool notebooklm_notebook_query no tiene ese limite."
                    )
                else:
                    resultado["mensaje"] = (
                        "Configuracion de NotebookLM detectada. 'nlm' no esta instalado; "
                        "usa notebooklm_notebook_query para consultar el oraculo manualmente."
                    )
                    resultado["advertencia"] = (
                        "No se detecto el CLI 'nlm' en el PATH. "
                        "Instalalo con 'pip install notebooklm-cli' y ejecuta 'nlm login' "
                        "para habilitar la consulta automatica."
                    )
                return json.dumps(resultado, ensure_ascii=False, indent=2)

            respuesta_oraculo = oraculo["respuesta"]
            if ORACULO_MAX_CHARS > 0 and len(respuesta_oraculo) > ORACULO_MAX_CHARS:
                respuesta_oraculo = (
                    respuesta_oraculo[:ORACULO_MAX_CHARS].rstrip()
                    + f"\n\n[ORACULO TRUNCADO: respuesta original de {len(oraculo['respuesta'])} "
                    f"caracteres truncada a {ORACULO_MAX_CHARS}. "
                    "Ajusta BIORAG_ORACULO_MAX_CHARS si necesitas mas contexto.]"
                )

            resultado = {
                "status": "ok",
                "modo": "notebooklm",
                "agente": agente_limpio,
                "notebooklm_notebook_id": NOTEBOOK_ID_ORACULO,
                "nlm_detectado": True,
                "nlm_fallo": False,
                "oraculo": respuesta_oraculo,
                "mensaje": "Oraculo NotebookLM consultado. Usa la respuesta como contexto de arranque.",
            }
            return json.dumps(resultado, ensure_ascii=False, indent=2)

        # Modo BioRAG local: consultar la corteza.
        cerebro = _get_cerebro()
        try:
            contexto_biorag = _buscar_contexto_biorag_arranque(cerebro, agente_limpio)
            partes_faltantes = []
            if not tiene_prompt:
                partes_faltantes.append("BIORAG_PROMPT_INICIO")
            if not tiene_notebook_id:
                partes_faltantes.append("BIORAG_NOTEBOOK_ID")

            _interceptar(
                "oraculo_inicio",
                f"[{agente_limpio}] modo=biorag_local faltan={','.join(partes_faltantes)}",
                cerebro,
            )

            return json.dumps({
                "status": "ok",
                "modo": "biorag_local",
                "mensaje": "NotebookLM no configurado. Contexto de arranque consultado en BioRAG local.",
                "agente": agente_limpio,
                "contexto_biorag": contexto_biorag,
                "advertencia": (
                    "Variables no seteadas: " + ", ".join(partes_faltantes) +
                    ". Setealas en el entorno si querés habilitar el modo NotebookLM."
                ),
            }, ensure_ascii=False, indent=2)
        finally:
            cerebro.cerrar_sistema()

    # ── SYNC TOOLS ──────────────────────────────────────────────────────────

    @mcp.tool(
        name="sync_status",
        description=(
            "Muestra el estado de sincronización pendiente con NotebookLM. "
            "Lista las categorías con cambios que aún no se han exportado. "
            "Ejecutar antes de export_sync para saber exactamente qué se va a subir.\n\n"
            "Sin parámetros.\n\n"
            "Retorna: {status, mensaje, pendientes: [{id (int), nombre (str), cambios (int)}]}"
        ),
    )
    def biorag_sync_status() -> str:
        cerebro = _get_cerebro()
        try:
            pending = cerebro.sync_status()
            if not pending:
                return json.dumps({
                    "status": "ok",
                    "mensaje": "No hay categorías pendientes. Todo sincronizado.",
                    "pendientes": [],
                }, ensure_ascii=False)
            items = [{"id": p[0], "nombre": p[1], "cambios": p[2]} for p in pending]
            msg = f"{len(items)} categoría(s) pendiente(s): " + ", ".join(f"{p[1]}({p[2]})" for p in pending)
            return json.dumps({
                "status": "ok",
                "mensaje": msg,
                "pendientes": items,
            }, ensure_ascii=False)
        finally:
            cerebro.cerrar_sistema()

    @mcp.tool(
        name="export_sync",
        description=(
            "Exporta SOLO las categorías con cambios pendientes a archivos .jsonl.txt en db/. "
            "Lee el sync_log y genera archivos listos para subir a NotebookLM. "
            "Usar para sincronizaciones incrementales (solo lo nuevo). "
            "Para exportar todo usar export_full.\n\n"
            "Sin parámetros.\n\n"
            "Retorna: {status, mensaje (lista de archivos generados o error)}"
        ),
    )
    def biorag_export_sync() -> str:
        script_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "MemoryBioRAG_NOTEBOOK_NCP", "scripts", "export_pending.py"
        )
        try:
            result = subprocess.run(
                ["python3", script_path],
                capture_output=True, text=True, timeout=30
            )
            output = result.stdout.strip()
            if result.returncode != 0:
                return json.dumps({
                    "status": "error",
                    "mensaje": f"Error en export:\n{result.stderr}",
                }, ensure_ascii=False)
            return json.dumps({
                "status": "ok",
                "mensaje": output,
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({
                "status": "error",
                "mensaje": str(e),
            }, ensure_ascii=False)

    @mcp.tool(
        name="export_full",
        description=(
            "Exporta TODAS las categorías a archivos .jsonl.txt en db/ (volcado completo). "
            "Usar como fallback o para sincronización inicial completa con NotebookLM. "
            "Para exportaciones incrementales (solo cambios nuevos) preferir export_sync.\n\n"
            "Sin parámetros.\n\n"
            "Retorna: {status, mensaje (lista de archivos generados o error)}"
        ),
    )
    def biorag_export_full() -> str:
        script_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "MemoryBioRAG_NOTEBOOK_NCP", "scripts", "export_full.py"
        )
        try:
            result = subprocess.run(
                ["python3", script_path],
                capture_output=True, text=True, timeout=60
            )
            output = result.stdout.strip()
            if result.returncode != 0:
                return json.dumps({
                    "status": "error",
                    "mensaje": f"Error en export:\n{result.stderr}",
                }, ensure_ascii=False)
            return json.dumps({
                "status": "ok",
                "mensaje": output,
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({
                "status": "error",
                "mensaje": str(e),
            }, ensure_ascii=False)

    @mcp.tool(
        name="metricas_historial",
        description=(
            "Retorna el historial de N ciclos de sueño con tendencias cognitivas. "
            "Incluye: consolidación promedio, olvido promedio, categoría dominante, "
            "salud sináptica (ratio creadas/podadas) y tendencia temporal "
            "(MEJORANDO / ESTABLE / EMPEORANDO).\n\n"
            "Útil para monitorear la evolución y salud de la memoria a lo largo del tiempo. "
            "Requiere haber ejecutado al menos un ciclo de 'consolidar' para tener datos.\n\n"
            "Retorna: {status, total_registros, ultimos_ciclos, tabla (str formateada), "
            "tendencias: {consolidacion_promedio, olvido_promedio, sinapsis_creadas_promedio, "
            "sinapsis_podadas_promedio, ratio_promedio, categoria_dominante, tendencia}, "
            "salud_sinaptica: {creadas_total, podadas_total, ratio}}"
        ),
    )
    def biorag_metricas_historial(
        n: Annotated[int, Field(
            description=(
                "Número de ciclos de sueño a incluir en el análisis (más recientes primero). "
                "Default: 10. Aumentar para tendencias históricas más largas."
            ),
            ge=1,
        )] = 10,
    ) -> str:
        cerebro = _get_cerebro()
        try:
            cur = cerebro.cursor
            cur.execute("SELECT COUNT(*) FROM metricas_cognitivas")
            total = cur.fetchone()[0]

            if total == 0:
                return json.dumps({
                    "status": "ok",
                    "mensaje": "No hay métricas registradas aún. Ejecuta un ciclo de sueño primero.",
                    "total_registros": 0,
                }, ensure_ascii=False)

            cur.execute(
                "SELECT timestamp, nodos_consolidados, nodos_dormidos_ciclo, "
                "sinapsis_creadas, sinapsis_podadas, categoria_dominante, ratio_consolidacion "
                "FROM metricas_cognitivas ORDER BY timestamp DESC LIMIT ?", (n,)
            )
            filas = cur.fetchall()

            # Calcular promedios
            n_filas = len(filas)
            avg_consolidados = sum(f[1] for f in filas) / n_filas
            avg_dormidos = sum(f[2] for f in filas) / n_filas
            avg_creadas = sum(f[3] for f in filas) / n_filas
            avg_podadas = sum(f[4] for f in filas) / n_filas
            avg_ratio = sum(f[6] for f in filas) / n_filas if filas[0][6] else 0

            # Categoría dominante histórica
            cats = [f[5] for f in filas if f[5]]
            cat_dominante = max(set(cats), key=cats.count) if cats else "N/A"

            # Tendencia: comparar primera mitad vs segunda mitad
            if n_filas >= 4:
                mitad = n_filas // 2
                recientes = filas[:mitad]
                antiguos = filas[mitad:]
                avg_rec_consolidados = sum(f[1] for f in recientes) / len(recientes)
                avg_ant_consolidados = sum(f[1] for f in antiguos) / len(antiguos)
                if avg_rec_consolidados > avg_ant_consolidados * 1.1:
                    tendencia = "MEJORANDO (consolida más)"
                elif avg_rec_consolidados < avg_ant_consolidados * 0.9:
                    tendencia = "EMPEORANDO (consolida menos)"
                else:
                    tendencia = "ESTABLE"
            else:
                tendencia = "DATOS_INSUFICIENTES (menos de 4 ciclos)"

            # Formatear tabla
            tabla = "Fecha              Consol  Dormidos  Sin/Pod  Cat Dom     Ratio\n"
            tabla += "─" * 70 + "\n"
            for f in reversed(filas):
                fecha = datetime.fromtimestamp(f[0]).strftime("%Y-%m-%d %H:%M")
                tabla += f"{fecha}     {f[1]:<7}{f[2]:<9}{f[3]}/{f[4]}     {(f[5] or 'N/A'):<10}{f[6] or 0:.2f}\n"

            resultado = {
                "status": "ok",
                "total_registros": total,
                "ultimos_ciclos": n_filas,
                "tabla": tabla,
                "tendencias": {
                    "consolidacion_promedio": round(avg_consolidados, 2),
                    "olvido_promedio": round(avg_dormidos, 2),
                    "sinapsis_creadas_promedio": round(avg_creadas, 1),
                    "sinapsis_podadas_promedio": round(avg_podadas, 1),
                    "ratio_promedio": round(avg_ratio, 3),
                    "categoria_dominante": cat_dominante,
                    "tendencia": tendencia,
                },
                "salud_sinaptica": {
                    "creadas_total": sum(f[3] for f in filas),
                    "podadas_total": sum(f[4] for f in filas),
                    "ratio": round(sum(f[3] for f in filas) / max(1, sum(f[4] for f in filas)), 2),
                },
            }
            return json.dumps(resultado, ensure_ascii=False, indent=2)
        finally:
            cerebro.cerrar_sistema()

    @mcp.tool(
        name="semantica_admin",
        description=(
            "Administra el vocabulario semántico de equivalencias entre términos. "
            "Las equivalencias mejoran el recall de 'recordar' al expandir queries automáticamente "
            "con sinónimos y términos relacionados.\n\n"
            "════════════════════════════════════════\n"
            "Acciones disponibles (parámetro 'accion'):\n"
            "════════════════════════════════════════\n"
            "'listar'             → Lista equivalencias existentes\n"
            "                       Parámetros opcionales: termino (filtra por término)\n\n"
            "'agregar'            → Agrega par de equivalencia bidireccional\n"
            "                       Parámetros requeridos: termino + equivalente\n"
            "                       Parámetros opcionales: peso (0.0-1.0, default 0.8)\n\n"
            "'eliminar'           → Elimina par de equivalencia\n"
            "                       Parámetros requeridos: termino + equivalente\n\n"
            "'cargar_vocabulario' → Carga múltiples equivalencias desde JSON masivo\n"
            "                       Parámetros requeridos: vocabulario_json\n\n"
            "'expandir'           → Muestra todas las expansiones de un término\n"
            "                       Parámetros requeridos: termino\n\n"
            "'inferir'            → Infiere candidatos desde sinapsis existentes\n"
            "                       MODO SUGERENCIA: NO guarda automáticamente.\n"
            "                       Revisar candidatos y usar 'agregar' para confirmar.\n\n"
            "'stats'              → Estadísticas del vocabulario semántico\n\n"
            "Retorna: {status, ...campos según acción ejecutada}"
        ),
    )
    def biorag_semantica_admin(
        accion: Annotated[str, Field(
            description=(
                "Acción a ejecutar. "
                "Valores: 'listar' | 'agregar' | 'eliminar' | 'cargar_vocabulario' | 'expandir' | 'inferir' | 'stats'."
            )
        )],
        termino: Annotated[Optional[str], Field(
            description=(
                "Término base para la operación de equivalencia. "
                "Requerido para: agregar, eliminar, expandir. "
                "Opcional para: listar (filtra resultados al término indicado)."
            )
        )] = None,
        equivalente: Annotated[Optional[str], Field(
            description=(
                "Término equivalente a asociar con 'termino'. "
                "Requerido para: agregar, eliminar."
            )
        )] = None,
        peso: Annotated[float, Field(
            description=(
                "Peso de la equivalencia semántica (0.0 a 1.0). "
                "1.0 = sinónimos exactos, 0.5 = relacionados moderados, 0.3 = relacionados débiles. "
                "Default: 0.8. Solo aplica en accion='agregar'."
            ),
            ge=0.0,
            le=1.0,
        )] = 0.8,
        vocabulario_json: Annotated[Optional[str], Field(
            description=(
                "JSON serializado con vocabulario a cargar masivamente. "
                "Requerido para accion='cargar_vocabulario'. "
                "Formato esperado: dict de {termino: [lista_equivalentes]} "
                "o lista de objetos {termino, equivalente, peso}."
            )
        )] = None,
    ) -> str:
        cerebro = _get_cerebro()
        try:
            from core.semantica import (
                init_semantica_table, expandir_query, agregar_equivalencia,
                eliminar_equivalencia, listar_equivalencias, cargar_vocabulario,
                tabla_vacia, inferir_equivalencias_desde_sinapsis
            )
            init_semantica_table(cerebro.cursor)

            if accion == "listar":
                eqs = listar_equivalencias(cerebro.cursor, termino)
                items = [{"termino": e[0], "equivalente": e[1], "peso": e[2]} for e in eqs]
                return json.dumps({
                    "status": "ok",
                    "total": len(items),
                    "equivalencias": items,
                }, ensure_ascii=False)

            elif accion == "agregar":
                if not termino or not equivalente:
                    return json.dumps({"status": "error", "mensaje": "Se requieren termino y equivalente"}, ensure_ascii=False)
                agregar_equivalencia(cerebro.cursor, termino, equivalente, peso)
                return json.dumps({
                    "status": "ok",
                    "mensaje": f"'{termino}' ↔ '{equivalente}' (peso={peso}) agregado",
                }, ensure_ascii=False)

            elif accion == "eliminar":
                if not termino or not equivalente:
                    return json.dumps({"status": "error", "mensaje": "Se requieren termino y equivalente"}, ensure_ascii=False)
                eliminar_equivalencia(cerebro.cursor, termino, equivalente)
                return json.dumps({
                    "status": "ok",
                    "mensaje": f"'{termino}' ↔ '{equivalente}' eliminado",
                }, ensure_ascii=False)

            elif accion == "cargar_vocabulario":
                if not vocabulario_json:
                    return json.dumps({"status": "error", "mensaje": "Se requiere vocabulario_json"}, ensure_ascii=False)
                try:
                    vocab = json.loads(vocabulario_json)
                except json.JSONDecodeError:
                    return json.dumps({"status": "error", "mensaje": "JSON inválido"}, ensure_ascii=False)
                count = cargar_vocabulario(cerebro.cursor, vocab)
                return json.dumps({
                    "status": "ok",
                    "mensaje": f"{count} equivalencias cargadas",
                }, ensure_ascii=False)

            elif accion == "expandir":
                if not termino:
                    return json.dumps({"status": "error", "mensaje": "Se requiere termino"}, ensure_ascii=False)
                eqs = expandir_query(cerebro.cursor, termino)
                return json.dumps({
                    "status": "ok",
                    "termino": termino,
                    "equivalentes": eqs,
                }, ensure_ascii=False)

            elif accion == "inferir":
                resultado = inferir_equivalencias_desde_sinapsis(
                    cerebro.cursor,
                    umbral_sinapsis=0.6,
                    umbral_jaccard=0.5,
                    frecuencia_minima=2,
                    peso_base=0.3,
                    auto_guardar=False,
                )
                candidatos = resultado["candidatos"]
                return json.dumps({
                    "status": "ok",
                    "pares_procesados": resultado["pares_procesados"],
                    "total_candidatos": resultado["total_candidatos"],
                    "candidatos": [
                        {"token_a": c[0], "token_b": c[1], "co_ocurrencias": c[2], "peso_inferido": c[3]}
                        for c in candidatos[:50]
                    ],
                    "mensaje": "auto_guardar=False — candidates listed only, not saved. "
                               "Review candidates and use accion=agregar to save manually.",
                }, ensure_ascii=False)

            elif accion == "stats":
                cerebro.cursor.execute("SELECT COUNT(*) FROM semantica")
                total = cerebro.cursor.fetchone()[0]
                cerebro.cursor.execute("SELECT COUNT(DISTINCT termino) FROM semantica")
                terminos = cerebro.cursor.fetchone()[0]
                return json.dumps({
                    "status": "ok",
                    "total_equivalencias": total,
                    "terminos_unicos": terminos,
                }, ensure_ascii=False)

            else:
                return json.dumps({
                    "status": "error",
                    "mensaje": (
                        f"Acción desconocida: '{accion}'. "
                        "Valores válidos: listar, agregar, eliminar, cargar_vocabulario, expandir, inferir, stats."
                    )
                }, ensure_ascii=False)
        finally:
            cerebro.cerrar_sistema()

    # ── RESOURCES ────────────────────────────────────────────────────────────

    @mcp.resource(
        uri="biorag://concepto/{nombre}",
        name="Concepto de la corteza",
        description=(
            "Contenido completo de un concepto almacenado en la corteza. "
            "URI: biorag://concepto/{nombre} donde nombre es la clave snake_case del concepto. "
            "Retorna: {concepto, categoria, contenido, peso_sinaptico, estado, asociaciones[], sinonimos[]}"
        ),
        mime_type="application/json",
    )
    def recurso_concepto(nombre: str) -> str:
        cerebro = _get_cerebro()
        try:
            key = nombre.lower().strip()
            cerebro.cursor.execute(
                "SELECT concepto, categoria, contenido, peso_sinaptico, estado, "
                "asociaciones, sinonimos FROM largo_plazo WHERE concepto = ?",
                (key,),
            )
            fila = cerebro.cursor.fetchone()
            if not fila:
                return json.dumps({"error": f"Concepto '{nombre}' no encontrado."}, ensure_ascii=False)
            return json.dumps({
                "concepto": fila[0],
                "categoria": fila[1],
                "contenido": fila[2],
                "peso_sinaptico": fila[3],
                "estado": fila[4],
                "asociaciones": [
                    v.strip() for v in (fila[5] or "").split(",") if v.strip()
                ],
                "sinonimos": [
                    v.strip() for v in (fila[6] or "").split(",") if v.strip()
                ],
            }, ensure_ascii=False)
        finally:
            cerebro.cerrar_sistema()

    @mcp.resource(
        uri="biorag://mensajes",
        name="Mensajes no leidos",
        description=(
            "Mensajes pendientes (no leídos) en el canal compartido OEC. "
            "Devuelve hasta 20 mensajes no leídos. "
            "Retorna: {total (int), mensajes: [{id, origen, destino, contenido, timestamp}]}"
        ),
        mime_type="application/json",
    )
    def recurso_mensajes() -> str:
        cerebro = _get_cerebro()
        try:
            mensajes = cerebro.leer_comunicados(solo_no_leidos=True, ultimos=20)
            items = [
                {
                    "id": m[0],
                    "origen": m[1],
                    "destino": m[2],
                    "contenido": m[3],
                    "timestamp": time.strftime("%Y-%m-%d %H:%M", time.localtime(m[4])),
                }
                for m in mensajes
            ]
            return json.dumps({"total": len(items), "mensajes": items}, ensure_ascii=False)
        finally:
            cerebro.cerrar_sistema()

    # ── PROMPTS ──────────────────────────────────────────────────────────────

    @mcp.prompt(
        name="biorag-system-prompt",
        description="Reglas de acceso a memoria BioRAG para incorporar en el system prompt del agente.",
    )
    def prompt_biorag() -> str:
        return (
            ORACLE_PROMPT
            + "\n\n## BioRAG — Reglas de uso\n\n"
            "Tienes acceso a una corteza cerebral compartida via herramientas MCP "
            "(recordar, aprender, vincular, ...).\n\n"
            "Reglas (nombres biológicos como primarios; legados entre paréntesis):\n"
            "1. Si el usuario menciona algo ya visto -> recordar (buscar)\n"
            "2. Si el usuario ensena algo nuevo -> aprender (guardar) + consolidar (sueno)\n"
            "3. Si dos conceptos estan relacionados -> vincular (asociar)\n"
            "4. Si necesitas dejar mensaje a otro agente -> comunicar\n"
            "5. Si al iniciar sesion quieres ver mensajes -> leer_mensajes\n"
            "6. Si despues de 2 evocaciones no encuentras -> preguntar al humano\n\n"
            "- Al iniciar una interaccion importante -> contexto_inicio\n"
            "- Al terminar una interaccion -> contexto_fin\n"
            "- El interceptor analiza el buffer acumulado y autoguarda si\n"
            "  detecta lecciones, patrones, errores o preferencias.\n"
            "- No necesitas recordar llamar 'aprender' explicitamente cada vez.\n\n"
            "TTL: 30 min de inactividad resetean el buffer (siesta biomimetica).\n\n"
            "La memoria decae naturalmente (LTD). Los nodos no usados se "
            "duermen solos. Usa 'consolidar' para fijar recuerdos nuevos."
        )

    return mcp


# --- Entry point ------------------------------------------------------------

def main(argv: Optional[list[str]] = None) -> int:
    argv = argv or sys.argv[1:]
    use_sse = "--sse" in argv
    port = 8080
    for i, a in enumerate(argv):
        if a == "--port" and i + 1 < len(argv):
            try:
                port = int(argv[i + 1])
            except ValueError:
                pass

    try:
        server = _build_server()
    except ImportError as exc:
        sys.stderr.write(f"BioRAG MCP: {exc}\n")
        return 2

    try:
        if use_sse:
            sys.stderr.write(f"BioRAG MCP iniciado en SSE :{port}\n")
            server.run(transport="sse", port=port)
        else:
            sys.stderr.write("BioRAG MCP iniciado (stdio)\n")
            server.run(transport="stdio")
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        logger.exception("BioRAG MCP server crashed")
        sys.stderr.write(f"BioRAG MCP server error: {exc}\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())