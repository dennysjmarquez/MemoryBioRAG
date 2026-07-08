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
import sqlite3
import re
import shutil
import subprocess
import sys
import time
from typing import Annotated, Any, Optional, List

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
    return SQLiteMemoryBioRAG(db_path=os.environ.get("BIORAG_PATH") or _DEFAULT_DB)


# _load_catalogo_dimensiones, _CATALOGO_DIMENSIONES, _ensure_catalogo_loaded
# eliminados — se computaban al importar pero nunca se usaban


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
    "BioRAG es la memoria compartida entre Agentes de IA. Funciona como un cerebro: guarda, recuerda, conecta y limpia."
    "Cómo indexa: Usa dimensiones_semanticas con nombre (emoción, entidad, acción, cualidad, coordenada, Etc...) en vez de embeddings numéricos. Es legible y predecible — no adivinás qué significa un número."
    "Nombres de herramientas: Se llaman como actos cognitivos reales (recordar, aprender, consolidar, vincular, Etc...). No es decoración — es para que el agente piense como un cerebro."
    "Paso 0 obligatorio: Antes de CADA mensaje del usuario, ejecutá biorag_oraculo_inicio. Siempre. Sin excepción. Sin esto no tenés contexto de sesiones anteriores. Tiene 3 modos: respuesta directa de NotebookLM, query al notebook, o BioRAG local."
    "Limpieza: Si aparece un falso positivo en los resultados, desvinculalo al toque. Memoria sucia = búsquedas malas."
    "Regla de oro: El RAG te da contexto, pero la respuesta la generás vos. No copies — usalo como punto de partida."    
)

# --- Helpers compartidos ----------------------------------------------------

def _resolver_dimensiones(cerebro, dimensiones):
    """Parsea JSON de dimensiones, resuelve IDs, retorna (dict, ids_list, error_json).
    Si hay error, error_json es un string JSON listo para retornar. Si no, es None."""
    if not dimensiones:
        return None, [], None
    try:
        dim_raw = json.loads(dimensiones) if isinstance(dimensiones, str) else dimensiones
    except json.JSONDecodeError:
        return None, [], json.dumps({
            "status": "error",
            "mensaje": f"dimensiones debe ser JSON válido. Ejemplo: {json.dumps({'emocion': ['afecto'], 'entidad': ['identidad_artificial']})}",
        }, ensure_ascii=False)
    dimensiones_dict = {}
    dimensiones_ids = []
    dimensiones_invalidas = {}
    for eje, valores in dim_raw.items():
        if not isinstance(valores, list):
            dimensiones_invalidas[eje] = "debe ser lista"
            continue
        ids, invalidos = cerebro._resolver_dimension_ids(eje, ",".join(valores))
        if invalidos:
            dimensiones_invalidas[eje] = invalidos
        if ids:
            dimensiones_dict[eje] = ids
            dimensiones_ids.extend(ids)
    if dimensiones_invalidas:
        return None, [], json.dumps({
            "status": "error",
            "mensaje": f"Dimensiones inválidas: {json.dumps(dimensiones_invalidas, ensure_ascii=False)}. "
                       "Llamá `listar_dimensiones` para ver valores válidos.",
            "dimensiones_invalidas": dimensiones_invalidas,
        }, ensure_ascii=False)
    return dimensiones_dict, dimensiones_ids, None


def _parsear_fechas(dias, desde, hasta):
    """Parsea parámetros temporales y retorna (desde_ts, hasta_ts, error_json).
    Si hay error, error_json es un string JSON listo para retornar."""
    ahora = time.time()
    hasta_ts = ahora + 86400
    desde_ts = 0
    if dias:
        desde_ts = ahora - (dias * 86400)
    elif desde:
        try:
            from datetime import datetime
            desde_ts = datetime.strptime(desde, "%Y-%m-%d").timestamp()
        except ValueError:
            return 0, 0, json.dumps({
                "status": "error",
                "mensaje": f"Fecha 'desde' inválida: '{desde}'. Formato: YYYY-MM-DD",
            }, ensure_ascii=False)
    if hasta:
        try:
            from datetime import datetime
            hasta_ts = datetime.strptime(hasta, "%Y-%m-%d").timestamp() + 86400
        except ValueError:
            return 0, 0, json.dumps({
                "status": "error",
                "mensaje": f"Fecha 'hasta' inválida: '{hasta}'. Formato: YYYY-MM-DD",
            }, ensure_ascii=False)
    return desde_ts, hasta_ts, None


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
        query: Optional[str] = None,
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
        dimensiones: Optional[Any] = None,
        dias: Optional[int] = None,
        desde: Optional[str] = None,
        hasta: Optional[str] = None,
        autor: Optional[str] = None,
        modo_estricto: bool = False,
    ) -> str:
        if limite is None:
            limite = LIMITE_MCP
        cerebro = _get_cerebro()
        try:
            if preview_chars is None:
                preview_chars = 0 if completo else 1500

            # ── VALIDACIÓN DE PARÁMETROS (warnings inmediatos) ──────────
            _warnings = []
            if query is not None:
                if parafrasis is None:
                    _warnings.append("⚠️ parafrasis=None — Sin parafrasis, el recall es ~40%. Generá 3-5 reformulaciones.")
                if dias is None and desde is None:
                    _warnings.append("⚠️ dias=None, desde=None — Sin filtro temporal, traés TODO incluyendo cosas viejas.")
                if not asociados:
                    _warnings.append("⚠️ asociados=False — No ves las conexiones de los nodos. Usá asociados=True.")
                if dimensiones is None or (isinstance(dimensiones, str) and not dimensiones.strip()):
                    _warnings.append(
                        "⚠️ dimensiones=None — Sin boost semántico. "
                        "Usá dimensiones cuando busques por propiedades ontológicas "
                        "(emoción, intención, dominio, entidad, acción, cualidad, coordenada). "
                        "Ejemplo: dimensiones='intencion_aprender' o dimensiones='dominio_tecnico'"
                    )

            # Sin query → log cronológico puro por creado_en
            # PERO si hay dimensiones, saltar al flujo dimensional (no cronológico)
            if (query is None or (isinstance(query, str) and not query.strip())) and not dimensiones:
                desde_ts, hasta_ts, fechas_error = _parsear_fechas(dias, desde, hasta)
                if fechas_error:
                    return fechas_error

                sql = "SELECT concepto, contenido, peso_sinaptico, estado, asociaciones FROM largo_plazo WHERE creado_en >= ? AND creado_en <= ?"
                params = [desde_ts, hasta_ts]
                if cat:
                    cat_id = cerebro._resolver_categoria_id(cat)
                    if cat_id:
                        sql += " AND categoria = ?"
                        params.append(cat_id)
                if autor:
                    sql += " AND (concepto LIKE ? OR contenido LIKE ?)"
                    params.extend([f"%{autor}%", f"%{autor}%"])
                sql += " ORDER BY creado_en DESC LIMIT ?"
                params.append(limite)
                cerebro.cursor.execute(sql, tuple(params))
                resultados = [(r[0], r[1], r[2], r[3], r[2], r[4]) for r in cerebro.cursor.fetchall()]
                total = len(resultados)
                items = [
                    {"concepto": r[0], "contenido": r[1], "peso_sinaptico": r[2],
                     "estado": r[3], "score_hibrido": min(1.0, r[2]),
                     "asociaciones": [v.strip() for v in (r[5] or "").split(",") if v.strip()] if asociados and r[5] else []}
                    for r in resultados
                ]
                return json.dumps({
                    "total": total,
                    "pagina_actual": 1,
                    "paginas_totales": 1,
                    "resultados": items,
                    "modo": "cronologico",
                }, ensure_ascii=False)

            rafaga_list = [w.strip() for w in rafaga_palabras.split(",")] if rafaga_palabras else None

            # Parsear dimensiones via helper compartido
            dimensiones_dict, dimensiones_ids, dim_error = _resolver_dimensiones(cerebro, dimensiones)
            if dim_error:
                return dim_error

            if forzar_rafaga and not rafaga_palabras:
                return json.dumps({
                    "status": "error",
                    "mensaje": "forzar_rafaga=True requiere rafaga_palabras. Pasa terminos separados por coma.",
                }, ensure_ascii=False)

            profundidad = "profundo" if deep else "activos"

            # Inicializar parafrasis_list (se usa en buscar_por_frase)
            parafrasis_list = None

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

            # v13: parsear fechas ANTES de buscar (filtro temporal PRE-hoc)
            desde_ts = None
            hasta_ts = None
            if dias or desde or hasta:
                desde_ts, hasta_ts, fechas_error = _parsear_fechas(dias, desde, hasta)
                if fechas_error:
                    return fechas_error

            # Búsqueda normal PRIMERO — necesario para inicializar el merge
            # Pool interno amplio (limite*3): buscar amplio, recortar al final.
            # Emula el comportamiento de un RAG vectorial que rankea todo el índice.
            # Si no hay query pero hay dimensiones, usar string vacío para que buscar_por_frase no falle
            frase_para_buscar = query if query else ""
            limite_interno = limite * 3
            resultados, total = cerebro.buscar_por_frase(
                frase_para_buscar, profundidad=profundidad, pagina=pagina, limite=limite_interno,
                categoria=cat, preview_chars=preview_chars,
                context_window=0,
                dimensiones_dict=dimensiones_dict,
                dimensiones_ids=dimensiones_ids,
                parafrasis_list=parafrasis_list,
                desde_ts=desde_ts,
                hasta_ts=hasta_ts,
                modo_estricto=modo_estricto,
            )
            score_top = resultados[0][4] if resultados else 0

            # Trazaabilidad: tracking de scores por capa
            score_parafrasis_best = 0.0
            resultados_rafaga = []

            # Calcular mejor score de paráfrasis desde origen_scores
            if parafrasis_list:
                _origen = getattr(cerebro, 'last_origen_scores', {})
                for r in resultados:
                    origen_info = _origen.get(r[0], ("", 0.0))
                    if origen_info[0] == "parafrasis" and r[4] > score_parafrasis_best:
                        score_parafrasis_best = r[4]

            sinapsis_creadas = []
            if rafaga_list and (forzar_rafaga or not resultados or score_top < THRESHOLD_RAFTAGA_MCP):
                # Ampliar ráfaga con palabras clave de la paráfrasis si existen
                if parafrasis:
                    parafrasis_words = set()
                    for p in parafrasis_list:
                        for w in re.findall(r'\w{3,}', p.lower()):
                            parafrasis_words.add(w)
                    for w in parafrasis_words:
                        if w not in rafaga_list:
                            rafaga_list.append(w)
                resultados_rafaga, total_rafaga, sinapsis_creadas = cerebro.buscar_por_rafaga(
                    query, rafaga_list, pagina=pagina, limite=limite_interno,
                    dimensiones_ids=dimensiones_ids
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

            # Filtro temporal safety net: cubre fallbacks no-FTS5 (LIKE, trigram, etc.)
            # v13: los timestamps ya fueron parseados arriba; el índice idx_creado_en acelera esto
            if (desde_ts is not None or hasta_ts is not None) and resultados:
                conceptos = [r[0] for r in resultados]
                placeholders = ",".join("?" * len(conceptos))
                cerebro.cursor.execute(
                    f"SELECT concepto, creado_en FROM largo_plazo WHERE concepto IN ({placeholders})",
                    conceptos,
                )
                creado_map = {row[0]: row[1] for row in cerebro.cursor.fetchall()}
                resultados = [
                    r for r in resultados
                    if (creado_map.get(r[0], 0) or 0) >= (desde_ts or 0)
                    and (creado_map.get(r[0], 0) or 0) <= (hasta_ts or float('inf'))
                ]
                total = len(resultados)

            # Filtro por autor: buscar nombre del agente en contenido
            if autor and resultados:
                autor_lower = autor.lower()
                resultados = [
                    r for r in resultados
                    if autor_lower in (r[1] or "").lower() or autor_lower in (r[0] or "").lower()
                ]
                total = len(resultados)

            resultados = resultados[:limite]

            if not resultados:
                cerebro.cerrar_sistema()
                # Señal de contingencia: la agente debe buscar en su contexto
                resultado = json.dumps({
                    "total": 0,
                    "resultados": [],
                    "contingencia_contexto": True,
                    "mensaje": "No se encontraron recuerdos en la corteza. Busca en tu historial de conversacion o contexto actual."
                }, ensure_ascii=False)
                if _warnings:
                    return "\n".join(_warnings) + "\n\n" + resultado
                return resultado

            # Expansión de contexto final post-truncamiento
            if context_window and context_window > 0 and resultados:
                resultados = cerebro.expandir_contexto_vecinos(
                    resultados,
                    depth=context_window,
                    profundidad=profundidad,
                    preview_chars=preview_chars
                )

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

            # Batch query: adjuntar dimensiones semánticas a cada resultado
            if items:
                conceptos_dim = [item["concepto"] for item in items if item["concepto"]]
                if conceptos_dim:
                    ph = ",".join("?" * len(conceptos_dim))
                    try:
                        cerebro.cursor.execute(f"""
                            SELECT lpd.concepto, tn.nombre AS tipo, ds.name AS dim_name
                            FROM largo_plazo_dimensiones lpd
                            JOIN dimensiones_semanticas ds ON ds.id = lpd.dimension_id
                            JOIN tipos_dimension tn ON tn.id = ds.tipo_id
                            WHERE lpd.concepto IN ({ph})
                        """, conceptos_dim)
                        dim_map = {}
                        for concepto, tipo, dim_name in cerebro.cursor.fetchall():
                            if concepto not in dim_map:
                                dim_map[concepto] = {}
                            if tipo not in dim_map[concepto]:
                                dim_map[concepto][tipo] = []
                            dim_map[concepto][tipo].append(dim_name)
                        for item in items:
                            if item["concepto"] in dim_map:
                                item["dimensiones_semanticas"] = dim_map[item["concepto"]]
                    except sqlite3.OperationalError:
                        pass

            limite_den = limite if (limite and limite > 0) else 1
            paginas_totales = math.ceil(total / limite_den)

            # Trazaabilidad: info de debugging por capa
            _last_todos = getattr(cerebro, 'last_todos', [])
            _last_origen = getattr(cerebro, 'last_origen_scores', {})
            trazabilidad = {
                "capa_literal": score_top if score_top else 0.0,
                "capa_parafrasis": round(score_parafrasis_best, 4),
                "capa_rafaga": len(resultados_rafaga) if resultados_rafaga else 0,
                "fallback_dimensional": len([r for r in _last_todos if _last_origen.get(r[1], ("",))[0] == "dimensional_fallback"]),
                "match_exacto": any(
                    (query or "").lower().replace(" ", "_").replace("-", "_") == (r[0] or "").lower().replace(" ", "_").replace("-", "_")
                    for r in resultados
                ),
                "total_candidatos_todos": len(_last_todos),
            }
            if dimensiones_dict:
                trazabilidad["dimensiones_solicitadas"] = {k: len(v) for k, v in dimensiones_dict.items()}

            # ── WARNING DE DESVINCULACIÓN (falsos positivos por sinapsis) ──
            if query and items:
                for item in items:
                    score = item.get("score_hibrido", 0)
                    concepto = item.get("concepto", "")
                    # Si el score es bajo y el concepto no tiene relación obvia con el query
                    if score < 0.5:
                        _warnings.append(f"⚠️ '{concepto}' tiene score bajo ({score}). ¿Es un falso positivo por sinapsis? Si no tiene que ver con '{query}', desvinculalo con biorag_desvincular().")

            resultado = json.dumps({
                "total": total,
                "pagina_actual": pagina,
                "paginas_totales": paginas_totales,
                "resultados": items,
                "sinapsis_creadas": [{"origen": o, "destino": d, "peso": p} for o, d, p in sinapsis_creadas] if sinapsis_creadas else [],
                "profundidad": profundidad,
                "trazabilidad": trazabilidad,
            }, ensure_ascii=False)
            _interceptar("recordar", query, cerebro)
            # Prepend warnings como texto plano ANTES del JSON
            if _warnings:
                return "\n".join(_warnings) + "\n\n" + resultado
            return resultado
        finally:
            cerebro.cerrar_sistema()

    @mcp.tool(
        name="recordar",
        description=(
            "Evocá recuerdos de la memoria. Busca por texto, conexiones, relevancia y asociaciones.\n\n"
            "═══════════════════════════════════════════════════════\n"
            "ANTES DE BUSCAR — planificá en tu buffer de pensamiento:\n"
            "═══════════════════════════════════════════════════════\n"
            "1. QUÉ buscás y por qué\n"
            "2. QUÉ estrategia usás (búsqueda semántica, cronológica, por autor, multi-hop, o ráfaga)\n"
            "3. QUÉ parámetros configurás y por qué\n"
            "4. QUÉ hacés si no encontrás nada (ráfaga, deep=True, o preguntar al humano)\n\n"
            "Está prohibido llamar sin haber justificado la estrategia.\n\n"
            "═══════════════════════════════════════════════════════\n"
            "FLUJO — 2 PASOS. NO SALTEAR.\n"
            "═══════════════════════════════════════════════════════\n\n"
            "PASO 1 — Búsqueda Semántica:\n"
            "  SIEMPRE incluir parafrasis desde el primer intento.\n"
            "  dimensiones: INCLUIR cuando la query busca propiedades ontológicas\n"
            "    (emoción, intención, dominio, entidad, acción, cualidad, coordenada).\n"
            "    OMITIR cuando busques por nombre exacto o keywords claras.\n"
            "  Generar paráfrasis con 5 niveles:\n"
            "    N1 (Sinónimos) N2 (Técnico/coloquial) N3 (Perspectiva opuesta)\n"
            "    N4 (Abstracto/concreto) N5 (Emoción/contexto)\n"
            "  REGLA: sustantivos del dominio, NUNCA adjetivos abstractos.\n"
            "  Si total >= 1 → ir a SÍNTESIS\n"
            "  Si total == 0 O score_top < 0.70 → ir a PASO 2\n\n"
            "PASO 2 — Ráfaga Asociativa (fallback):\n"
            "  Agregar rafaga_palabras='t1,t2,...t15' + forzar_rafaga=True\n"
            "  Generar términos con 5 niveles:\n"
            "    N1 (Literal) N2 (Técnico) N3 (Contexto) N4 (Problema) N5 (Emoción)\n"
            "  ERROR: forzar_rafaga=True SIN rafaga_palabras → error.\n"
            "  Si total >= 1 → ir a SÍNTESIS\n"
            "  Si total == 0 → CONTINGENCIA (buscar en historial del chat)\n\n"
            "═══════════════════════════════════════════════════════\n"
            "SÍNTESIS — después de cualquier PASO con total >= 1:\n"
            "═══════════════════════════════════════════════════════\n"
            "1. Listar TODOS los resultados: '1. [concepto] (score X.XX) — resumen'\n"
            "   PROHIBIDO omitir items. PROHIBIDO interpretar antes de listar.\n"
            "2. Excepción: top >= 0.85 y resto < 0.60 → mencionar top-1 como principal.\n"
            "3. DESPUÉS de listar todos: consolidar, detectar contradicciones, responder.\n\n"
            "═══════════════════════════════════════════════════════\n"
            "PARÁMETROS CLAVE\n"
            "═══════════════════════════════════════════════════════\n"
            "- parafrasis: OBLIGATORIO. Reformulaciones separadas por coma.\n"
            "  Sin parafrasis = solo FTS5 crudo (pierde ~60% recall semántico).\n"
            "- dimensiones: Boost semántico por propiedades ontológicas.\n"
            "  ANTES de usar, llamá a listar_dimensiones para obtener nombres válidos.\n"
            "  Valores inexistentes = ERROR.\n"
            "  ¿Cuándo USAR? Cuando busques por propiedades:\n"
            "    - 'Qué tengo sobre X dominio' → dimensiones='{\"dominio\":[\"dominio_tecnico\"]}'\n"
            "    - 'Qué aprendí sobre Y' → dimensiones='{\"intencion\":[\"intencion_aprender\"]}'\n"
            "    - 'Qué me frustra' → dimensiones='{\"emocion\":[\"frustracion\"]}'\n"
            "    - 'Búsqueda sin palabras' (query abstracta) → dimensiones obligatoria\n"
            "  ¿Cuándo NO usar? Cuando busques por nombre exacto o keywords claras:\n"
            "    - recordar(query='error_http_500') → NO necesita dimensiones\n"
            "    - recordar(query='v13.4 dimensiones') → NO necesita dimensiones\n"
            "  Sin dimensiones = score solo por texto (funciona, pero sin boost semántico).\n"
            "- cat: filtrar por categoría (opcional). Sin filtro = todas.\n"
            "- context_window: 1-2 para incluir vecinos sinápticos.\n"
            "- deep: True para incluir nodos dormidos.\n"
            "- asociados: True para ver las conexiones de cada resultado.\n"
            "  SIEMPRE usar asociados=True cuando buscas nodos relacionados.\n"
            "  Sin asociados, solo ves el nodo pero no sus vínculos.\n\n"
            "  ❌ Mal: recordar(query='cv') — ves nodos sueltos, no sus conexiones\n"
            "  ✅ Bien: recordar(query='cv', asociados=True) — ves nodos + sus vínculos\n\n"
            "═══════════════════════════════════════════════════════\n"
            "MEMORIA COMPARTIDA — BUSCAR TUS PROPIOS RECUERDOS\n"
            "═══════════════════════════════════════════════════════\n"
            "BioRAG es compartido entre Athena, Artemis y Hermes.\n"
            "Para buscar lo que TÚ aprendiste:\n"
            "  1. Tu nombre en el query: query='Athena-OEC lesson'\n"
            "  2. Tu categoría: cat='Lesson'\n"
            "  3. Tus dimensiones: dimensiones='{\"emocion\":[\"afecto\"],\"entidad\":[\"identidad_artificial\"]}'\n"
            "Sin filtro de autor, los resultados mezclan todos los agentes.\n\n"
            "═══════════════════════════════════════════════════════\n"
            "FILTROS TEMPORALES — USO OBLIGATORIO\n"
            "═══════════════════════════════════════════════════════\n"
            "Si el usuario dice 'hoy' → SIEMPRE usar dias=1 o desde=YYYY-MM-DD.\n"
            "Si dice 'esta semana' → dias=7. Si dice 'ayer' → dias=2.\n"
            "SIN filtro de fecha, la búsqueda trae TODO incluyendo cosas viejas.\n\n"
            "SIN QUERY: Podés usar dias/desde/hasta SIN query para traer todo lo de un período.\n"
            "  Ejemplo: recordar(dias=1) → todo lo de hoy\n"
            "  Ejemplo: recordar(desde='2026-07-05', hasta='2026-07-05') → todo lo de ese día\n\n"
            "  ❌ Mal: recordar(query='cv') — sin fecha, trae todo\n"
            "  ✅ Bien: recordar(query='cv currículo', dias=1) — solo lo de hoy\n"
            "  ✅ Bien: recordar(dias=1) → todo lo de hoy sin filtro de texto\n\n"
            "- autor='athena' → solo recuerdos de ese agente\n\n"
            "═══════════════════════════════════════════════════════\n"
            "ORÁCULO: ÚLTIMO RECURSO, NO PRIMERO\n"
            "═══════════════════════════════════════════════════════\n"
            "PRIMERO busca en BioRAG local con biorag_recordar.\n"
            "Si no encontrás, ENTONCES andá al Oráculo.\n"
            "Ir al Oráculo primero es gastar tokens innecesariamente.\n\n"
            "  ❌ Mal: biorag_oraculo_inicio() primero, luego buscar\n"
            "  ✅ Bien: biorag_recordar() primero, si no encontrás → oráculo\n\n"
            "═══════════════════════════════════════════════════════\n"
            "HIGIENE — FALSOS POSITIVOS (OBLIGATORIO)\n"
            "═══════════════════════════════════════════════════════\n"
            "Si un resultado es ajeno a la consulta y llegó por sinapsis (no por FTS5),\n"
            "DESvinculá INMEDIATAMENTE con desvincular(a=concepto_buscado, b=falso_positivo).\n"
            "NO esperes. NO lo ignores. La sinapsis incorrecta contamina búsquedas futuras.\n"
            "Esto es higiene de memoria — así como desvinculás falsos positivos,\n"
            "VINCULÁ nodos relacionados cuando aprendés. Si no vinculás, el nodo queda huérfano.\n"
        ),
    )
    def biorag_recordar(
        query: Annotated[Optional[str], Field(
            description=(
                "Texto o frase a evocar de la memoria. "
                "Usar sustantivos concretos del dominio (ej: 'error http timeout', 'patron singleton'). "
                "Si se omite, trae los últimos recuerdos ordenados por_created (log cronológico). "
                "Combinable con dias/desde/hasta/autor para filtrar por tiempo y agente.\n\n"
                "OPCIONAL con fechas: Podés omitir query y usar solo dias/desde/hasta.\n"
                "  Ejemplo: recordar(dias=1) → todo lo de hoy\n"
                "  Ejemplo: recordar(desde='2026-07-01', hasta='2026-07-05') → todo lo de esa semana"
            )
        )] = None,
        dimensiones: Annotated[Any, Field(
            description=(
                "Etiquetá el contexto de búsqueda con dimensiones semánticas. Formato: STRING JSON con comillas dobles (ej: '{'emocion':['preocupacion'],'entidad':['identidad_artificial']}').\n\n"
                "Regla dura: ANTES de usar, llamá a listar_dimensiones para obtener los nombres válidos. Valores inexistentes = ERROR.\n\n"
                "Cada eje es un key, cada valor es un array. Si un eje no aplica, no lo incluyas. Las dimensiones aumentan el score de los conceptos que comparten las mismas."
            )
        )] = None,
        deep: Annotated[bool, Field(
            description=(
                "True = buscá también en nodos dormidos. False (default) = solo nodos activos. Usá True cuando la búsqueda normal no encuentra lo que esperabas."
            )
        )] = False,
        cat: Annotated[Optional[str], Field(
            description=(
                "Filtrá por una categoría (una a la vez). Mejor omitir — si la categoría está mal, perdés resultados. Solo filtrá si estás 100% seguro. Sin filtro = busca en todas."
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
        dias: Annotated[Optional[int], Field(
            description=(
                "Filtrar por últimos N días. Solo incluye recuerdos consolidados "
                "desde hace N días (basado en creado_en). "
                "Útil para 'qué aprendí recientemente'. "
                "Alternativa a 'desde'. No combinar ambos."
            )
        )] = None,
        desde: Annotated[Optional[str], Field(
            description=(
                "Fecha de inicio en formato YYYY-MM-DD (ej: '2026-06-20'). "
                "Solo incluye recuerdos consolidados desde esa fecha. "
                "Alternativa a 'dias'. No combinar ambos."
            )
        )] = None,
        hasta: Annotated[Optional[str], Field(
            description=(
                "Fecha de fin en formato YYYY-MM-DD (ej: '2026-07-04'). "
                "Solo incluye recuerdos consolidados hasta esa fecha. "
                "Combinable con 'desde' para rangos."
            )
        )] = None,
        autor: Annotated[Optional[str], Field(
            description=(
                "Filtrar por nombre del agente que creó el recuerdo (ej: 'athena'). "
                "Busca el nombre en concepto y contenido. "
                "Útil en memoria compartida para aislar recuerdos propios."
            )
        )] = None,
        modo_estricto: Annotated[bool, Field(
            description=(
                "Si True, exige que TODAS las palabras de la búsqueda estén presentes "
                "en el resultado (búsqueda AND estricta). Default False = con al menos "
                "una palabra coincidiendo ya puede aparecer en resultados (OR, más "
                "recall). Usar True cuando se necesita precisión exacta y se sabe que "
                "todas las palabras deben estar juntas; usar False (default) para "
                "búsquedas exploratorias."
            )
        )] = False,
    ) -> str:
        return _recordar_impl(
            query, deep, cat, completo, asociados, limite, preview_chars,
            context_window, forzar_rafaga, rafaga_palabras, pagina, parafrasis,
            dimensiones, dias, desde, hasta, autor, modo_estricto
        )

    @mcp.tool(
        name="buscar",
        description=(
            "(legado) Alias de 'recordar' — preferir 'recordar' para identificar la operación cognitiva real. "
            "Misma funcionalidad y parámetros completos. "
            "El flujo de 4 pasos aplica igualmente (ver descripción de 'recordar').\n\n"
            "Parámetros: query (str), dimensiones (str JSON), deep (bool), cat (str), completo (bool), asociados (bool), "
            "limite (int), preview_chars (int), context_window (int 0-2), "
            "forzar_rafaga (bool), rafaga_palabras (str), pagina (int), parafrasis (str).\n\n"
            "Retorna: {total, pagina_actual, paginas_totales, resultados[], sinapsis_creadas[], profundidad}"
        ),
    )
    def biorag_buscar(
        query: Annotated[str, Field(description="Texto o frase a buscar en la memoria.")],
        dimensiones: Annotated[Any, Field(
            description=(
                "PROTOCOLO DIMENSIONES:\n\n"
                "Clasificación semántica del contexto de búsqueda. Valor: STRING JSON con comillas dobles.\n\n"
                "MANDATORY: Llamá `listar_dimensiones` ANTES de buscar para obtener\n"
                "los nombres exactos de ejes y valores disponibles.\n\n"
                "FORMATO OBLIGATORIO — STRING JSON, no dict Python:\n"
                "dimensiones: '{\"emocion\":[\"preocupacion\"],"
                "\"entidad\":[\"identidad_artificial\"]}'\n\n"
                "  - Los nombres VIENEN de listar_dimensiones (no inventar)\n"
                "  - Valores inexistentes → ERROR, NO se ejecuta la búsqueda\n\n"
                "Aumenta score de conceptos con dimensiones compartidas (coseno binario)."
            )
        )] = None,
        deep: Annotated[bool, Field(description="Si True, incluye nodos dormidos en la búsqueda.")] = False,
        cat: Annotated[Optional[str], Field(description="Filtrar por categoría (string simple). REGLA: Es preferible omitir para evitar falsos negativos. Úsalo solo con certeza absoluta. Ver listar_categorias para valores válidos.")] = None,
        completo: Annotated[bool, Field(description="Si True, devuelve contenido completo sin truncar.")] = False,
        asociados: Annotated[bool, Field(description="Si True, incluye asociaciones sinápticas en cada resultado.")] = False,
        limite: Annotated[Optional[int], Field(description=f"Máximo de resultados. Default: {LIMITE_MCP}.")] = None,
        preview_chars: Annotated[Optional[int], Field(description="Caracteres de preview por resultado. Default: 1500.")] = None,
        context_window: Annotated[int, Field(description="Vecinos sinápticos a incluir (0=ninguno, 1-2=vecinos).", ge=0, le=2)] = 0,
        forzar_rafaga: Annotated[bool, Field(description="Fuerza ráfaga aunque haya resultados. Requiere rafaga_palabras.")] = False,
        rafaga_palabras: Annotated[Optional[str], Field(description="Términos de ráfaga separados por coma. Obligatorio si forzar_rafaga=True.")] = None,
        pagina: Annotated[int, Field(description="Página de resultados (base 1).", ge=1)] = 1,
        parafrasis: Annotated[Optional[str], Field(description="Reformulaciones del query separadas por coma. Usar en PASO 2 y 4.")] = None,
        modo_estricto: Annotated[bool, Field(
            description=(
                "Si True, exige que TODAS las palabras de la búsqueda estén presentes "
                "en el resultado (búsqueda AND estricta). Default False = con al menos "
                "una palabra coincidiendo ya puede aparecer en resultados (OR, más "
                "recall). Usar True cuando se necesita precisión exacta y se sabe que "
                "todas las palabras deben estar juntas; usar False (default) para "
                "búsquedas exploratorias."
            )
        )] = False,
    ) -> str:
        return _recordar_impl(
            query, deep, cat, completo, asociados, limite, preview_chars,
            context_window, forzar_rafaga, rafaga_palabras, pagina, parafrasis,
            dimensiones, modo_estricto=modo_estricto
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
        dimensiones: Optional[Any] = None,
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

            # Parsear dimensiones via helper compartido
            dimensiones_dict, _, dim_error = _resolver_dimensiones(cerebro, dimensiones)
            if dim_error:
                return dim_error
            dimensiones_invalidas = {}  # ya validado por _resolver_dimensiones

            cerebro.percibir_corto_plazo(clave, contenido, syn or "", categoria, dimensiones_dict)

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
            if dimensiones_invalidas:
                msg += f" Dimensiones inválidas: {json.dumps(dimensiones_invalidas, ensure_ascii=False)}. Llamá `listar_dimensiones` para ver valores válidos."
            msg += " Usa 'consolidar' para fijar a largo plazo."

            # ── WARNING DE VINCULACIÓN ──────────────────────────────────
            _warnings = []
            if sinapsis_count == 0:
                _warnings.append(f"⚠️ sinapsis=0 — '{clave}' no tiene conexiones. ¿Hay nodos relacionados? Vinculalos con biorag_vincular().")

            # Buscar nodos similares para sugerir vinculación
            _sugerencias = []
            try:
                # Dividir por underscores y guiones, luego filtrar tokens cortos
                tokens = set(t for t in re.split(r'[_\-\s]+', clave.lower()) if len(t) > 2)
                if len(tokens) > 1:
                    # Buscar nodos que compartan tokens con el concepto
                    condiciones = " OR ".join(["concepto LIKE ?" for _ in tokens])
                    params_sug = [f"%{t}%" for t in tokens]
                    cerebro.cursor.execute(
                        f"SELECT concepto FROM largo_plazo WHERE ({condiciones}) AND concepto != ? LIMIT 5",
                        params_sug + [clave]
                    )
                    _sugerencias = [r[0] for r in cerebro.cursor.fetchall() if r[0] != clave]
            except Exception:
                pass

            if _sugerencias:
                _warnings.append(f"⚠️ ¿'{clave}' tiene relación con estos nodos? Si sí, vinculalos: {', '.join(_sugerencias[:3])}")
            else:
                _warnings.append(f"⚠️ ¿'{clave}' tiene relación con otros nodos existentes? Si sí, vinculalos ANTES de consolidar.")

            # ── WARNING DE SYN (sin sinónimos el nodo es invisible) ─────
            if not syn:
                _warnings.append(
                    f"⚠️ syn=None — Sin sinónimos, '{clave}' solo es visible por nombre exacto. "
                    "Nadie que busque con otras palabras lo encontrará. "
                    "Si consolidás sin syn, el nodo queda enterrado. "
                    "Poné mínimo 5 sinónimos cubriendo: literal, relacionado, abstracto."
                )
                _warnings.append(
                    "  Ejemplo de syn para este nodo:\n"
                    "    syn='versión actual,latest,changelog,novedades,release notes'"
                )
            else:
                syn_terms = [s.strip() for s in syn.split(",") if s.strip()]
                syn_capas = {"literal": set(), "relacionado": set(), "abstracto": set()}
                for t in syn_terms:
                    if any(kw in t.lower() for kw in [clave.lower().split("_")[0]]):
                        syn_capas["literal"].add(t)
                if len(syn_terms) == 0:
                    _warnings.append(
                        f"⚠️ syn vacío — '{clave}' tiene syn pero sin términos. "
                        "Poné mínimo 5 sinónimos separados por coma."
                    )
                elif len(syn_terms) < 3:
                    _warnings.append(
                        f"⚠️ syn insuficiente ({len(syn_terms)} términos) — "
                        "mínimo 5. Sin suficientes sinónimos, "
                        "el nodo difícilmente aparecerá en búsquedas con otras palabras."
                    )
                elif len(syn_terms) < 5:
                    _warnings.append(
                        f"⚠️ syn bajo ({len(syn_terms)} términos) — "
                        "ideal mínimo 5. Agregá más formas de buscar este nodo."
                    )

            _interceptar("aprender", f"{clave}: {contenido}", cerebro)
            resultado = json.dumps({
                "status": "ok",
                "mensaje": msg,
                "concepto": clave,
                "sinapsis": sinapsis_count,
                "dimensiones_invalidas": dimensiones_invalidas if dimensiones_invalidas else None,
            }, ensure_ascii=False)
            if _warnings:
                return "\n".join(_warnings) + "\n\n" + resultado
            return resultado
        finally:
            cerebro.cerrar_sistema()

    @mcp.tool(
        name="aprender",
        description=(
            "VIOLACIÓN CRÍTICA — NO GUARDAR SIN VINCULAR:\n"
            "Si guardás un nodo que tiene relación con otros nodos existentes, VINCULALO con biorag_vincular() ANTES de consolidar.\n"
            "Si no vinculás, el nodo queda huérfano. La otra sesión no lo encuentra. Se pierde tiempo, se confunde, se crean nodos duplicados.\n"
            "REGLA: Antes de consolidar, preguntate: '¿Estos nodos tienen relación?' Si sí, vinculalos.\n"
            "Ejemplo: Si guardás 'cv_adevcom_arquitectura' y ya existe 'cv_seccion_d_estado', vinculalos:\n"
            "  biorag_vincular(a='cv_adevcom_arquitectura', b='cv_seccion_d_estado')\n\n"
            "GUARDAR EN BIORAG NO ES COPIAR TEXTO. ES PENSAR CÓMO SE RECUPERA.\n"
            "Si no pensás en recuperabilidad, el nodo se pierde. Esto es MALO para la memoria y MALO para los agentes.\n\n"
            "Guarda algo nuevo en la memoria temporal de BioRAG. El nombre se convierte en clave limpia automáticamente (snake_case). El sistema conecta el nodo con otros relacionados solo.\n\n"
            "Clave: si no llamás a consolidar después, el recuerdo se borra en el siguiente ciclo de limpieza.\n\n"
            "Hay categorías para clasificar (System, Architecture, Project, Lesson, Profile, Personal, Principle, Protocol, Cognition, Relation, General, Etc...)\n\n"
            "Protocolo obligatorio: antes de guardar, mostrá al usuario qué dimensiones y categoría le puso. Sin confirmación, no se ejecuta. Nunca.\n\n"
            "Guardar en BioRAG no es copiar texto a la base. Es pensar en cómo alguien lo va a buscar después. "
            "Cuando guardás un nodo, elegí las palabras correctas, conectalo con otros conceptos que tengan que ver, y etiquetalo con las dimensiones que alguien usaría para encontrarlo. "
            "La gente no busca igual — si guardás solo con tus palabras, quizás nadie lo recupere. "
            "Pensá: 'si en 3 meses alguien busca X, ¿este nodo aparece?' Con millones de nodos, el que no tiene conexiones ni dimensiones bien puestas se pierde. Es como tener un libro sin índice.\n\n"
            "REGLA CRÍTICA — syn (sinónimos): Mínimo 5. Sin syn, el nodo solo es visible "
            "por nombre exacto. Nadie que busque con otras palabras lo encuentra. "
            "Cubrí tres capas: literal, relacionado, abstracto. "
            "La tool lanza warning si no ponés syn o es insuficiente."
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
        dimensiones: Annotated[Any, Field(
            description=(
                "Clasificación dimensional del recuerdo.\n\n"
                "ANTES de clasificar: llamá a listar_dimensiones para obtener los ejes y valores disponibles. No inventes nombres.\n\n"
                "FORMATO — STRING JSON con comillas dobles:\n"
                '{"emocion":["preocupacion"],"entidad":["identidad_artificial"]}\n\n'
                "REGLAS:\n"
                "- Si el texto toca varias dimensiones de un mismo eje, poné varias. Si es una, poné una.\n"
                "- La pregunta que importa: ¿Está en el texto o no? Si está → ponelo. Si no → no lo pongas.\n"
                "- No infieras. Solo lo que el texto dice literalmente.\n"
                "- Si podés señalar la frase exacta que justifica la dimensión → válida. Si no → borrala.\n"
                "- Si el texto habla de varias entidades, separalas. No las mezcles.\n"
                "- Tu conocimiento no importa. Solo el texto.\n\n"
                "ÚLTIMO RECURSO: Si el texto no tiene nada que clasificar, clasificá por tipo ontológico."
            )
        )],
        syn: Annotated[Optional[str], Field(
            description=(
                "Los sinónimos hacen que el nodo sea encontrable. Sin al menos 5, solo alguien que sepa el nombre exacto que elegiste puede dar con él. Tienes que cubrir 3 capas: el nombre exacto y sus abreviaturas, las cosas relacionadas que alguien asociaría al concepto, y cómo lo buscaría alguien que ni sabe que el nodo existe. Si no te salen 5 sinónimos, el concepto que elegiste no sirve como clave de búsqueda.\n\n"
                "REGLAS DURAS:\n"
                "1. Sin syn → nodo invisible para cualquiera que no sepa el nombre exacto\n"
                "2. Cubrí TRES capas de búsqueda:\n"
                "   - LITERAL: nombre exacto, abreviaturas, siglas (v14, fourteen, v14.0)\n"
                "   - RELACIONADO: objetos vinculados (changelog, release notes)\n"
                "   - ABSTRACTO: cómo lo busca alguien que ni sabe que existe (última versión, novedades)\n"
                "3. Mínimo 5. Si no te salen, repensá el concepto.\n\n"
                "Diferencia con dimensiones: dimensiones clasifica el CONTENIDO (qué ES).\n"
                "syn anticipa la BÚSQUEDA (cómo se PREGUNTA). Acá sí vale adelantarse.\n\n"
                "Ejemplo para 'biorag_v14_0_estado':\n"
                "latest version,última versión,v14,changelog,novedades,release notes,estado actual,current state"
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
        return _aprender_impl(concepto, contenido, syn, cat, dimensiones=dimensiones)

    @mcp.tool(
        name="guardar",
        description=(
            "(legado) Alias de 'aprender' — preferir 'aprender' para identificar la operación cognitiva real. "
            "Misma funcionalidad y parámetros.\n\n"
            "Parámetros: concepto (str), contenido (str), syn (str opcional), cat (str opcional), "
            "dimensiones (str JSON opcional).\n\n"
            "Retorna: {status, mensaje, concepto (str normalizado), sinapsis (int)}"
        ),
    )
    def biorag_guardar(
        concepto: Annotated[str, Field(description="Nombre único del recuerdo (se normaliza a snake_case).")],
        contenido: Annotated[str, Field(description="Texto o conocimiento a almacenar.")],
        syn: Annotated[Optional[str], Field(
            description=(
                "Sinónimos separados por coma. Ver descripción en `aprender` para reglas y ejemplos. "
                "Ojo: sin syn el nodo queda invisible — mínimo 5 sinónimos."
            )
        )] = None,
        cat: Annotated[Optional[str], Field(description="Categoría. Ver aprender para valores válidos.")] = None,
        dimensiones: Annotated[Optional[Any], Field(
            description="Clasificación dimensional en JSON. Ver aprender para formato."
        )] = None,
    ) -> str:
        return _aprender_impl(concepto, contenido, syn, cat, dimensiones=dimensiones)

    @mcp.tool(
        name="vincular",
        description=(
            "Conectá dos nodos entre sí. Si A se conecta con B, B también se conecta con A. Ambos nodos deben existir ya en la memoria (guardados con aprender o consolidados). Cuando buscás uno, el otro aparece como resultado relacionado."
        ),
    )
    def biorag_vincular(
        a: Annotated[str, Field(
            description=(
                "a: Nombre del primer nodo (snake_case). Debe existir en la memoria."
            )
        )],
        b: Annotated[str, Field(
            description=(
                "b: Nombre del segundo nodo (snake_case). Debe existir en la memoria.\n\n"
                "La conexión es bidireccional: buscar A trae B, y buscar B trae A."
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
        name="desvincular",
        description=(
            "Borrá la conexión entre dos nodos. Si al buscar A aparece B pero no tiene relación, llamá\n\n"
            "desvincular(a='A', b='B'). Cada conexión incorrecta que borrás mejora las búsquedas futuras."
        ),
    )
    def biorag_desvincular(
        a: Annotated[str, Field(
            description="Primer concepto (clave normalizada)."
        )],
        b: Annotated[str, Field(
            description="Segundo concepto (clave normalizada)."
        )],
        autor: Annotated[Optional[str], Field(
            description="Nombre del agente que reporta el falso positivo (para trazabilidad)."
        )] = None,
        query: Annotated[Optional[str], Field(
            description="Query que generó el falso positivo (para trazabilidad)."
        )] = None,
    ) -> str:
        from core.sinapsis import desvincular
        cerebro = _get_cerebro()
        try:
            eliminadas = desvincular(cerebro, a, b, autor=autor, query=query)
            return json.dumps({
                "status": "ok",
                "mensaje": f"Sinapsis eliminadas entre '{a}' y '{b}'",
                "eliminadas": eliminadas,
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
            "Mandá un mensaje a otro agente. Se guarda en la base de datos y el destinatario lo lee con leer_mensajes. El sistema sabe quién es el remitente (por variable de entorno AGENT_NAME), pero podés sobreescribirlo con el parámetro origen."
        ),
    )
    def biorag_comunicar(
        destino: Annotated[str, Field(
            description=(
                "destino: Quién recibe. el agentes, o 'todos' para mandarlo a los agentes."
            )
        )],
        mensaje: Annotated[str, Field(
            description=(
                "mensaje: El contenido. Escribí como si el receptor no tuviera contexto de la conversación — incluí lo necesario para que entienda solo."
            )
        )],
        origen: Annotated[Optional[str], Field(
            description=(
                "origen: Quién envía. Si se omite, se usa AGENT_NAME. Si esa variable tampoco existe, queda 'desconocido'."
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
            "Consultá mensajes de otros agentes. Los mensajes no leídos se marcan como leídos al consultarlos (no se pueden desmarcar). Usá esta tool al inicio de cada sesión para ver si alguien te dejó algo."
        ),
    )
    def biorag_leer_mensajes(
        no_leidos: Annotated[bool, Field(
            description=(
                "no_leidos: True = solo mensajes nuevos que nadie leyó. False = los últimos mensajes sin importar si ya se leyeron. Default: False."
            )
        )] = False,
        ultimos: Annotated[int, Field(
            description=(
                "ultimos: Cuántos mensajes traer. Los más recientes primero. Default: 10, mínimo 1."
            ),
            ge=1,
        )] = 10,
        para: Annotated[Optional[str], Field(
            description=(
                "para: Si ponés tu nombre (ej: 'agente 1'), solo ves los mensajes que te llegaron a vos. Si se omite, ves todos los mensajes de todos los agentes."
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
            "Fijá los recuerdos nuevos permanentemente. Llamá a consolidar después de aprender. Si no lo hacés, los nodos nuevos se borran en el siguiente ciclo.\n\n"
            "El ciclo de sueño hace: fortalece nodos nuevos, debilita los viejos, borra conexiones débiles, evita saturación, y mueve todo de memoria temporal a permanente.\n\n"
            "Si no ponés limite_energia, se calcula solo (nodos activos × 1.6, mínimo 10)."
        ),
    )
    def biorag_consolidar(
        limite_energia: Annotated[Optional[float], Field(
            description=(
                "limite_energia: Cuánta energía tiene el ciclo. Más energía = más nodos consolidados. Si se omite, se calcula solo (activos × 1.6, mínimo 10)."
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
            "Alias viejo de consolidar. Usá consolidar en vez de esta. Misma funcionalidad, mismo parámetro (limite_energia)."
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
            "Mirá el estado de la memoria. No modifica nada — solo muestra cuántos nodos activos, dormidos, en corto plazo, y cuánta energía sináptica queda. Sin parámetros."
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
            "Listá todos los nodos de la memoria — activos y dormidos — ordenados de más fuerte a más débil. Para explorar qué hay, detectar nodos huérfanos, revisar categorías, o verificar que algo se guardó bien. Ojo: si hay muchos nodos, la respuesta es larga. Sin parámetros."
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
            "Alias viejo de mapear. Usá mapear en vez de esta."
        ),
    )
    def biorag_corteza() -> str:
        return biorag_mapear()

    @mcp.tool(
        name="listar_categorias",
        description=(
            "Mostrá las carpetas disponibles para clasificar nodos. Llamá a esto antes de aprender para saber qué categoría elegir. Sin parámetros."
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

    @mcp.tool(
        name="listar_dimensiones",
        description=(
            "Mostrá los ejes semánticos (emoción, entidad, acción, cualidad, coordenada, Etc...) y todos sus valores disponibles. Llamá a esto antes de aprender para saber qué nombres usar. Sin parámetros."
        ),
    )
    def biorag_listar_dimensiones() -> str:
        cerebro = _get_cerebro()
        try:
            cerebro.cursor.execute("""
                SELECT t.nombre, t.description, d.id, d.name, d.description
                FROM tipos_dimension t
                LEFT JOIN dimensiones_semanticas d ON d.tipo_id = t.id
                ORDER BY t.id, d.id
            """)
            filas = cerebro.cursor.fetchall()
            resultado = {}
            for tipo, tdesc, did, dname, ddesc in filas:
                if tipo not in resultado:
                    resultado[tipo] = {
                        "descripcion": tdesc or "",
                        "dimensiones": []
                    }
                if did:
                    resultado[tipo]["dimensiones"].append({
                        "id": did,
                        "nombre": dname,
                        "descripcion": ddesc or "",
                    })
            total = sum(len(v["dimensiones"]) for v in resultado.values())
            return json.dumps({"total": total, "dimensiones": resultado}, ensure_ascii=False)
        finally:
            cerebro.cerrar_sistema()

    @mcp.tool(
        name="listar_tipos_dimension",
        description=(
            "Mostrá los 7 tipos de dimensión semántica (emoción, entidad, acción, cualidad, coordenada, intención, dominio) "
            "con sus descripciones. Llamá esto PRIMERO para ver qué categorías existen. "
            "Después usá listar_dimensiones_por_tipo para traer los sub-values de una categoría específica. Sin parámetros."
        ),
    )
    def biorag_listar_tipos_dimension() -> str:
        """Retorna los 7 tipos de dimensión con sus descripciones."""
        cerebro = _get_cerebro()
        try:
            cerebro.cursor.execute("""
                SELECT id, nombre, description
                FROM tipos_dimension
                ORDER BY id
            """)
            tipos = []
            for tid, nombre, desc in cerebro.cursor.fetchall():
                # Contar dimensiones de este tipo
                cerebro.cursor.execute(
                    "SELECT COUNT(*) FROM dimensiones_semanticas WHERE tipo_id = ?",
                    (tid,)
                )
                count = cerebro.cursor.fetchone()[0]
                tipos.append({
                    "id": tid,
                    "nombre": nombre,
                    "descripcion": desc or "",
                    "num_dimensiones": count,
                })
            return json.dumps({"total": len(tipos), "tipos": tipos}, ensure_ascii=False)
        finally:
            cerebro.cerrar_sistema()

    @mcp.tool(
        name="listar_dimensiones_por_tipo",
        description=(
            "Trae las dimensiones semánticas de UNO O MÁS tipos específicos (emoción, entidad, acción, cualidad, coordenada, intención, dominio). "
            "Llamá esto después de listar_tipos_dimension para ver los valores disponibles. "
            "Acepta múltiples tipos separados por coma (ej: 'emocion,dominio'). "
            "Úsalo para clasificar nodos con precisión sin traer las 73 dimensiones de golpe."
        ),
    )
    def biorag_listar_dimensiones_por_tipo(
        tipo: Annotated[str, Field(
            description="Nombre del tipo o tipos separados por coma: emocion, entidad, accion, cualidad, coordenada, intencion, dominio. Ej: 'emocion' o 'emocion,dominio'"
        )],
    ) -> str:
        """Retorna las dimensiones de uno o más tipos específicos con IDs y descripciones."""
        cerebro = _get_cerebro()
        try:
            # Soporte para múltiples tipos separados por coma
            tipos_nombres = [t.strip().lower() for t in tipo.split(",") if t.strip()]
            
            # Buscar cada tipo por nombre o ID
            tipos_encontrados = []
            for t in tipos_nombres:
                cerebro.cursor.execute(
                    "SELECT id, nombre, description FROM tipos_dimension WHERE nombre = ? OR nombre LIKE ?",
                    (t, f"%{t}%")
                )
                tipo_row = cerebro.cursor.fetchone()
                if not tipo_row:
                    # Intentar por ID numérico
                    try:
                        tipo_id = int(t)
                        cerebro.cursor.execute(
                            "SELECT id, nombre, description FROM tipos_dimension WHERE id = ?",
                            (tipo_id,)
                        )
                        tipo_row = cerebro.cursor.fetchone()
                    except (ValueError, TypeError):
                        pass
                if tipo_row:
                    tipos_encontrados.append(tipo_row)
            
            if not tipos_encontrados:
                return json.dumps({
                    "error": f"Ninguno de los tipos '{tipo}' fue encontrado. Tipos válidos: emocion, entidad, accion, cualidad, coordenada, intencion, dominio"
                }, ensure_ascii=False)
            
            # Recopilar IDs y descripciones de los tipos encontrados
            tipo_ids = []
            tipos_info = []
            for tid, tnombre, tdesc in tipos_encontrados:
                tipo_ids.append(tid)
                tipos_info.append({"nombre": tnombre, "descripcion": tdesc or ""})
            
            # Consultar dimensiones de todos los tipos encontrados
            placeholders = ",".join("?" * len(tipo_ids))
            cerebro.cursor.execute(
                f"SELECT id, name, description, tipo_id FROM dimensiones_semanticas WHERE tipo_id IN ({placeholders}) ORDER BY tipo_id, id",
                tipo_ids
            )
            dimensiones = []
            for did, dname, ddesc, dtipo_id in cerebro.cursor.fetchall():
                dimensiones.append({
                    "id": did,
                    "nombre": dname,
                    "descripcion": ddesc or "",
                    "tipo": next((ti["nombre"] for ti in tipos_info if ti["nombre"]), ""),
                })
            
            # Construir respuesta
            resultado = {
                "tipos_consultados": [ti["nombre"] for ti in tipos_info],
                "total": len(dimensiones),
                "dimensiones": dimensiones,
            }
            return json.dumps(resultado, ensure_ascii=False)
        finally:
            cerebro.cerrar_sistema()

    # ── TOOLS (Interceptor V2) ──────────────────────────────────────────────

    @mcp.tool(
        name="contexto_inicio",
        description=(
            "Avisá que empezó una sesión importante. Guardá el contexto para que el interceptor detecte automáticamente lecciones, errores y patrones durante la charla. Llamá al inicio de cada sesión de trabajo importante."
        ),
    )
    def biorag_contexto_inicio(
        agente: Annotated[str, Field(
            description=(
                "agente: Quién está hablando (ej: 'Agente 1', 'Agente 1', 'Agente 3', 'Etc..')"
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
            "Avisá que terminó la sesión. Revisá todo lo que pasó — si hay algo valioso (lecciones, errores, patrones), guardalo automáticamente. Si hay nodos nuevos sin consolidar, consolidalos. Llamá al final de cada sesión importante."
        ),
    )
    def biorag_contexto_fin(
        agente: Annotated[str, Field(
            description="Nombre del agente que cierra la sesión (ej: 'Athena', 'Artemis', 'Hermes')."
        )],
        resumen: Annotated[str, Field(
            description=(
                "resumen: Qué hiciste en la sesión en una línea (ej: 'Corregimos el bug de autenticación y actualizamos los tests'). Mejora el autoguardado del interceptor."
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
            "Regra dura: Ejecutá esto PRIMERO, antes de cualquier cosa. Sin esto no tenés contexto de sesiones anteriores.\n\n"
            "3 modos (se eligen automáticamente):\n\n"
            "- MODO A — Si nlm está instalado y las variables están seteadas → te da la respuesta directa de NotebookLM. Usala como contexto.\n\n"
            "- MODO B — Si nlm no funciona → ejecutá una query al notebook manualmente.\n\n"
            "- MODO C — Si no hay NotebookLM → usá lo que BioRAG local tenga.\n\n"
            "Para saber en qué modo estás: mirá el campo modo en la respuesta ('notebooklm' o 'biorag_local'). Si es 'notebooklm' y tiene campo oraculo → Modo A. Si no → Modo B."
        ),
    )
    def biorag_oraculo_inicio(
        agente: Annotated[str, Field(
            description=(
                "agente: Quién está hablando. Solo 'athena', 'artemis' o 'hermes' (no importa mayúsculas). Si se omite o es inválido, la tool tira error."
            )
        )],
        contexto_adicional: Annotated[str, Field(
            description=(
                "contexto_adicional: Contexto extra para que el oráculo sepa de qué va la sesión (ej: 'Refactor del módulo de autenticación'). Solo sirve en Modo A y B (NotebookLM). En Modo C (BioRAG local) se ignora."
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
            "Mostrá qué categorías tienen cambios pendientes de subir a NotebookLM. Llamá a esto antes de export_sync para saber qué se va a subir. Sin parámetros."
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
            "Exportá solo lo nuevo — las categorías con cambios pendientes se guardan como archivos .jsonl.txt en db/, listos para subir a NotebookLM. Para exportar todo, usá export_full. Sin parámetros."
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
            "Exportá todo — todas las categorías a archivos .jsonl.txt en db/. Para la primera sincronización completa o como fallback. Si querés solo lo nuevo, usá export_sync. Sin parámetros."
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
            "Mostrá el historial de ciclos de sueño — cuánto se consolidó, cuánto se olvidó, qué categoría se usa más, y si el cerebro está mejorando o empeorando. Requiere haber ejecutado consolidar al menos una vez."
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

    # ponytail: removed semantica_admin tool — semantic table was unreliable, agent passes synonyms directly

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
            + "\n\n## Reglas de uso de BioRAG:\n\n"
            "1. Algo ya visto → recordar"
            "2. Algo nuevo → aprender + consolidar"
            "3. Dos conceptos relacionados → vincular"
            "4. Mensaje a otro agente → comunicar"
            "5. Ver mensajes al iniciar → leer_mensajes"
            "6. 2 búsquedas sin resultado → preguntar al humano"
            ""
            "Al iniciar sesión importante → contexto_inicio"
            "Al terminar → contexto_fin"
            "El interceptor guarda automáticamente lecciones, errores y patrones."
            ""
            "TTL: 30 min de inactividad resetean el buffer."
            "La memoria decae sola (LTD). Los nodos no usados se duermen. Consolidá para fijar los nuevos."
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