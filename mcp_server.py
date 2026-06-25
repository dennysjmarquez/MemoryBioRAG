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

import json
import logging
import os
import re
import shutil
import subprocess
import sys
import time
from typing import Any, Optional, List

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
            
            # Búsqueda normal primero
            resultados, total = cerebro.buscar_por_frase(
                query, profundidad=profundidad, limite=limite,
                categoria=cat, preview_chars=preview_chars,
                context_window=context_window
            )
            
            # Activar ráfaga si hay palabras Y: se fuerza explícitamente,
            # O 0 resultados, O score del top resultado < threshold (fallback).
            sinapsis_creadas = []
            score_top = resultados[0][4] if resultados else 0
            if rafaga_list and (forzar_rafaga or not resultados or score_top < THRESHOLD_RAFTAGA_MCP):
                resultados_rafaga, total_rafaga, sinapsis_creadas = cerebro.buscar_por_rafaga(
                    query, rafaga_list, limite=limite
                )
                # Combinar resultados: ráfaga + originales (sin duplicados)
                if resultados_rafaga:
                    seen = {r[1] for r in resultados}
                    for r in resultados_rafaga:
                        if r[1] not in seen:
                            resultados.append(r)
                            seen.add(r[1])
                    total = len(resultados)
            
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

            resultado = json.dumps({
                "total": total,
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
            "FLUJO OBLIGATORIO EN 3 PASOS: "
            "PASO 1: Enviar la frase del usuario. Si es abstracta/poetica, interpretar y agregar 3-5 palabras clave al final. "
            "PASO 2: Si PASO 1 da 0 resultados O score del top < 0.5, usar rafaga_palabras con terminos de expansion. PARA GENERAR LA RAFAGA: "
            "No busques sinonimos. Busca lo que el usuario NECESITA pero no supo pedir. "
            "Usa 5 niveles de expansion: "
            "NIVEL 1 (Literal): sinonimos tecnicos exactos. "
            "NIVEL 2 (Tecnico): terminos del dominio relacionados. "
            "NIVEL 3 (Contexto): donde/para que se usa. "
            "NIVEL 4 (Problema): que problema resuelve. "
            "NIVEL 5 (Emocion/Prioridad): urgencia o contexto personal. "
            "Genera los terminos que necesites por nivel (sin limite tecnico). "
            "El sistema valida automaticamente las palabras contra la DB antes de buscar. "
            "PASO 3: Si PASO 2 da 0 resultados o puro ruido, buscar en el contexto del chat y guardar. "
            "DESPUES DE CADA PASO: Leer los resultados y explicar al usuario con tus propias palabras que encontraste. "
            "Si encontraste algo parecido pero no exacto, decir: 'No encontre X pero encontre Y que dice que...'. "
            "Ejemplo PASO 1: recordar(query='dias relax frente al oceano playa vacaciones') "
            "Ejemplo PASO 2: recordar(query='dias relax frente al oceano', rafaga_palabras='playa,mar,costa,verano,descanso,sol,arena,olas') "
            "FORZAR RAFAGA: por defecto la rafaga es un fallback (solo corre si 0 resultados o score top < 0.5). "
            "Si queres invocarla SIEMPRE como herramienta cognitiva de primera linea (pensar como humano que insiste en recordar), "
            "pasa forzar_rafaga=True junto con rafaga_palabras = 'termino1,termino2,...' (string separado por comas). "
            "IMPORTANTE: forzar_rafaga=True SIN rafaga_palabras devuelve ERROR. Siempre pasar ambos juntos. "
            "Ejemplo: recordar(query='...', rafaga_palabras='termino1,termino2', forzar_rafaga=True). "
            "Contexto: usar context_window=1 o 2 para incluir vecinos por sinapsis junto a cada resultado principal."
        ),
    )
    def biorag_recordar(
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
    ) -> str:
        return _recordar_impl(query, deep, cat, completo, asociados, limite, preview_chars, context_window, forzar_rafaga, rafaga_palabras)

    @mcp.tool(
        name="buscar",
        description="(legado) Busca recuerdos — prefiere 'recordar' para identificar la operación cognitiva real.",
    )
    def biorag_buscar(
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
    ) -> str:
        return _recordar_impl(query, deep, cat, completo, asociados, limite, preview_chars, context_window, forzar_rafaga, rafaga_palabras)

    @mcp.tool(
        name="aprender",
        description=(
            "[Cognitivo] Codifica una experiencia en la corteza de corto plazo (percepción). "
            "Equivalente a la codificación inicial de un recuerdo en el hipocampo. "
            "Cat validas: System, Architecture, Project, Lesson, Profile, "
            "Personal, Principle, Protocol, Cognition, Relation, General. "
            "Usa 'consolidar' despues para fijar a largo plazo (LTP)."
        ),
    )
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

    def biorag_aprender(
        concepto: str,
        contenido: str,
        syn: Optional[str] = None,
        cat: Optional[str] = None,
    ) -> str:
        return _aprender_impl(concepto, contenido, syn, cat)

    @mcp.tool(
        name="guardar",
        description="(legado) Guarda un recuerdo — prefiere 'aprender' para identificar la operación cognitiva.",
    )
    def biorag_guardar(
        concepto: str,
        contenido: str,
        syn: Optional[str] = None,
        cat: Optional[str] = None,
    ) -> str:
        return _aprender_impl(concepto, contenido, syn, cat)

    @mcp.tool(
        name="vincular",
        description=(
            "[Cognitivo] Establece una asociación hebbiana entre dos conceptos en la corteza. "
            "Equivalente a la potenciación a largo plazo (LTP) entre neuronas co-activadas. "
            "Crea un enlace sináptico bidireccional que permite que evocar uno active al otro."
        ),
    )
    def biorag_vincular(a: str, b: str) -> str:
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
        description="(legado) Asocia dos conceptos — prefiere 'vincular' para identificar la operación cognitiva.",
    )
    def biorag_asociar(a: str, b: str) -> str:
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
        name="comunicar",
        description=(
            "Envia un mensaje a otro agente OEC (athena, artemis, hermes, todos). "
            "Identificate con AGENT_NAME."
        ),
    )
    def biorag_comunicar(destino: str, mensaje: str, origen: Optional[str] = None) -> str:
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
        description="Lee mensajes del canal compartido entre agentes OEC.",
    )
    def biorag_leer_mensajes(
        no_leidos: bool = False,
        ultimos: int = 10,
        para: Optional[str] = None,
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
            "Aplica LTP (potenciación a largo plazo) a recuerdos nuevos, "
            "LTD (depresión a largo plazo) por decaimiento, "
            "duerme nodos débiles, e inhibición lateral para evitar saturación. "
            "Equivalente al sueño de ondas lentas en el hipocampo. "
            "limite_energia: opcional, defecto dinamico (n_activos * 1.6, min 10.0)."
        ),
    )
    def biorag_consolidar(limite_energia: Optional[float] = None) -> str:
        cerebro = _get_cerebro()
        try:
            import io
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
        description="(legado) Ciclo de sueño — prefiere 'consolidar' para identificar la operación cognitiva.",
    )
    def biorag_sueno(limite_energia: Optional[float] = None) -> str:
        return biorag_consolidar(limite_energia)

    @mcp.tool(
        name="introspeccion",
        description=(
            "[Cognitivo] Autoexamen sináptico de la corteza. "
            "Retorna el estado actual: número de nodos activos, dormidos, "
            "corto plazo y energía sináptica total. "
            "Equivalente a la introspección metacognitiva del estado de la memoria."
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
        description="(legado) Estado de la corteza — prefiere 'introspeccion' para identificar la operación cognitiva.",
    )
    def biorag_estado() -> str:
        return biorag_introspeccion()

    @mcp.tool(
        name="mapear",
        description=(
            "[Cognitivo] Cartografía cortical — lista todos los nodos de la corteza permanente "
            "(activos y dormidos) con sus categorías, pesos sinápticos y asociaciones. "
            "Equivalente a visualizar el mapa completo de la memoria a largo plazo."
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
        description="(legado) Lista nodos de la corteza — prefiere 'mapear' para identificar la operación cognitiva.",
    )
    def biorag_corteza() -> str:
        return biorag_mapear()

    @mcp.tool(
        name="listar_categorias",
        description=(
            "Lista las categorias validas para guardar recuerdos. "
            " Retorna id, nombre y descripcion de cada categoria. "
            "Usar ANTES de 'aprender' (o 'guardar') para saber que cat es valido."
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
            "Anuncia el inicio de una interaccion significativa. "
            "Almacena el contexto en el buffer de sesion para que el "
            "interceptor pueda autoguardar si detecta algo importante."
        ),
    )
    def biorag_contexto_inicio(agente: str, contexto: str = "") -> str:
        cerebro = _get_cerebro()
        try:
            registrar_accion("inicio", f"[{agente}] {contexto}")
            return json.dumps({"status": "ok", "mensaje": "Contexto de inicio registrado."}, ensure_ascii=False)
        finally:
            cerebro.cerrar_sistema()

    @mcp.tool(
        name="contexto_fin",
        description=(
            "Anuncia el fin de una interaccion. Fuerza el analisis del "
            "buffer de sesion acumulado y autoguarda si detecta algo nuevo."
        ),
    )
    def biorag_contexto_fin(agente: str, resumen: str = "") -> str:
        cerebro = _get_cerebro()
        try:
            registrar_accion("fin", f"[{agente}] {resumen}")
            resultado = analizar_y_autoguardar(cerebro, fuerza=True)
            if resultado:
                consolidado = cerebro.consolidar_concepto(resultado["concepto"])
                if consolidado:
                    msg = f"Auto-guardado y consolidado: '{resultado['concepto']}' ({resultado['categoria']}). Ya en corteza permanente."
                else:
                    msg = f"Auto-guardado en corto plazo: '{resultado['concepto']}'). Consolidacion pendiente."
            else:
                msg = "No se detecto nada nuevo que amerite guardado."

            # Auto-sueño: consolidar si hay datos en corto_plazo
            cerebro.cursor.execute("SELECT COUNT(*) FROM corto_plazo")
            n_corto = cerebro.cursor.fetchone()[0]
            if n_corto > 0:
                import io
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
                # Cualquier fallo de nlm se trata como "usar fallback".
                # Guardamos el mensaje de error en logs para diagnostico, pero no
                # propagamos el error al agente.
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
            "OBLIGATORIO AL INICIAR SESIÓN CON TU USUARIO: invocá esta herramienta "
            "PRIMERO, antes de responder cualquier otra cosa. Sin excepciones. "
            "Proporcioná el parámetro obligatorio `agente` con tu nombre "
            "(por ejemplo: Athena, Artemis, Hermes, o el nombre que use tu agente). "
            "Comportamiento: "
            "SI las variables de entorno BIORAG_PROMPT_INICIO y BIORAG_NOTEBOOK_ID "
            "están seteadas, esta herramienta opera en MODO NOTEBOOKLM. "
            "Intenta consultar NotebookLM directamente via CLI 'nlm'. "
            "Si la respuesta contiene 'oraculo', ese es el resultado del oraculo. "
            "Si la respuesta tiene modo='notebooklm' pero NO contiene 'oraculo', "
            "significa que 'nlm' no esta disponible o que el query excedio el limite "
            "interno del CLI 'nlm'; en ese caso usa notebooklm_query para consultar "
            "NotebookLM manualmente con notebooklm_notebook_query. "
            "SI alguna de esas variables falta, opera en MODO BIORAG LOCAL: "
            "consulta la corteza de BioRAG y devuelve reglas, lecciones, "
            "protocolos y perfil del usuario. NO consulta NotebookLM. "
            "NO asumas contexto de sesiones anteriores. "
            "Siempre llamá a esta herramienta al inicio de cada interacción significativa."
        ),
    )
    def biorag_oraculo_inicio(agente: str, contexto_adicional: str = "") -> str:
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
        description="Muestra categorías pendientes de sincronizar a NotebookLM.",
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
            "Exporta SOLO categorías pendientes a .jsonl.txt en db/. "
            "Lee sync_log y genera archivos para subir a NotebookLM. "
            "Retorna lista de archivos a subir."
        ),
    )
    def biorag_export_sync() -> str:
        import subprocess
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
            "Export completo: genera .jsonl.txt de TODAS las categorías. "
            "Fallback para volcado completo. Retorna lista de archivos generados."
        ),
    )
    def biorag_export_full() -> str:
        import subprocess
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
            "Retorna los últimos N ciclos de sueño con tendencias: "
            "consolidación promedio, olvido promedio, categoría dominante, "
            "salud sináptica. Útil para monitorear evolución de la memoria."
        ),
    )
    def biorag_metricas_historial(n: int = 10) -> str:
        cerebro = _get_cerebro()
        try:
            from datetime import datetime

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
            "Administra el vocabulario semántico: listar equivalencias, "
            "agregar/eliminar pares, cargar vocabulario desde JSON. "
            "Permite que 'auto' encuentre 'vehículo' sin embeddings."
        ),
    )
    def biorag_semantica_admin(
        accion: str,
        termino: Optional[str] = None,
        equivalente: Optional[str] = None,
        peso: float = 0.8,
        vocabulario_json: Optional[str] = None,
    ) -> str:
        cerebro = _get_cerebro()
        try:
            from core.semantica import (
                init_semantica_table, expandir_query, agregar_equivalencia,
                eliminar_equivalencia, listar_equivalencias, cargar_vocabulario,
                tabla_vacia
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
                return json.dumps({"status": "error", "mensaje": f"Acción desconocida: {accion}"}, ensure_ascii=False)
        finally:
            cerebro.cerrar_sistema()

    # ── RESOURCES ────────────────────────────────────────────────────────────

    @mcp.resource(
        uri="biorag://concepto/{nombre}",
        name="Concepto de la corteza",
        description="Contenido completo de un concepto almacenado en la corteza.",
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
        description="Mensajes pendientes en el canal compartido OEC.",
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
