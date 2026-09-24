"""Shared utilities and singleton accessors for core.mcp_server."""

import os
import json
import logging
from typing import Optional, Dict
from core.memory_service import get_cerebro as _svc_get_cerebro
from core.memory_store import SQLiteMemoryBioRAG
from middleware.auto_guardado import registrar_accion, analizar_y_autoguardar

logger = logging.getLogger("BioRAG.MCP")

_sesiones_activas: dict[str, float] = {}  # agente → timestamp de contexto_inicio

LIMITE_MCP = int(os.environ.get('BIORAG_LIMITE_MCP', '10'))
"""Límite de resultados por defecto en búsquedas MCP."""

THRESHOLD_RAFTAGA_MCP = float(os.environ.get('BIORAG_THRESHOLD_RAFTAGA', '0.5'))
"""Score mínimo para activar ráfaga automáticamente en MCP."""

STALE_DAYS = int(os.environ.get('BIORAG_STALE_DAYS', '90'))
"""Días después de los cuales un nodo se marca como 'stale' (obsoleto).
Resultados stale no se entregan como información vigente.
Protegidos: categories Principle, Profile, Personal, Relation no se marcan stale."""

STALE_HARD_CUTOFF_DAYS = int(os.environ.get('BIORAG_STALE_HARD_CUTOFF', '365'))
"""Días después de los cuales un nodo se excluye de resultados (a menos que
esté en categoría protegida). 0 = sin cutoff."""

MAX_ASOCIACIONES_FLAT = int(os.environ.get('BIORAG_MAX_ASOCIACIONES_FLAT', '12'))
"""Máximo de nombres de asociaciones planas expuestos por nodo en la respuesta de
recordar/buscar. El campo `asociaciones` de cada resultado se devuelve como objeto
{total, items, truncada}: total es el conteo REAL de conexiones del nodo (nunca se
pierde información), items es la lista acotada a este límite, y truncada indica si
hay más que no se muestran. Con asociaciones_max=0 el agente pide la lista completa
del nodo que le interesa (consulta dirigida), evitando que hubs de 130-167 conexiones
inflen el JSON y disparen el truncado del cliente MCP. La tabla `sinapsis` (fuente
canónica) y la columna `largo_plazo.asociaciones` quedan intactas — es decisión de
serialización. Ver mcp_server.py _serializar_asociaciones.
"""

VENTANA_CORRECCION = int(os.environ.get('BIORAG_VENTANA_CORRECCION_SEGUNDOS', '900'))
"""Ventana de corrección en caliente (default 900s = 15min). Nodos más jóvenes se pueden actualizar directamente; más viejos requieren nodo nuevo + vincular."""

ORACULO_MAX_CHARS = int(os.environ.get('BIORAG_ORACULO_MAX_CHARS', '12000'))
"""Máximo de caracteres devueltos por el oráculo NotebookLM.

Si la respuesta de NotebookLM excede este límite, se trunca y se agrega una
nota indicando que el contenido fue recortado. Esto evita que el output de la
tool sea truncado por el cliente MCP por exceso de tamaño.
"""

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

AGENTES_VALIDOS = set()
"""Agentes reconocidos por el sistema (vacío = permite cualquier agente)."""


def _get_cerebro() -> SQLiteMemoryBioRAG:
    """Reusa la corteza (singleton). No reconstruir 6–11s por tool."""
    return _svc_get_cerebro(os.environ.get("BIORAG_PATH") or None)


def _interceptar(accion: str, texto: str, cerebro) -> Optional[dict]:
    registrar_accion(accion, texto)
    resultado = analizar_y_autoguardar(cerebro)
    if resultado:
        logger.info("auto-guardado: %s (%s)", resultado["concepto"], resultado["categoria"])
    return resultado


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

    if not isinstance(dim_raw, dict):
        return None, [], json.dumps({
            "status": "error",
            "mensaje": "dimensiones debe ser un objeto JSON (diccionario) con comillas dobles. Ejemplo: {\"emocion\": [\"afecto\"]}",
        }, ensure_ascii=False)

    dimensiones_dict = {}
    dimensiones_ids = []
    dimensiones_invalidas = {}
    for eje, valores in dim_raw.items():
        if not isinstance(valores, list):
            dimensiones_invalidas[eje] = "debe ser lista"
            continue

        valores_filtrados = []
        for val in valores:
            if isinstance(val, str):
                valores_filtrados.append(val)
            else:
                dimensiones_invalidas[eje] = f"elemento inválido de tipo {type(val).__name__} (debe ser string)"

        if eje in dimensiones_invalidas:
            continue

        ids, invalidos = cerebro._resolver_dimension_ids(eje, ",".join(valores_filtrados))
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
