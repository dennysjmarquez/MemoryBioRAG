"""Shared utilities and singleton accessors for core.mcp_server."""

import os
import logging
from typing import Optional, Dict
from core.memory_service import get_cerebro as _svc_get_cerebro
from core.memory_store import SQLiteMemoryBioRAG
from middleware.auto_guardado import registrar_accion, analizar_y_autoguardar

logger = logging.getLogger("BioRAG.MCP")

_sesiones_activas: dict[str, float] = {}  # agente → timestamp de contexto_inicio

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
