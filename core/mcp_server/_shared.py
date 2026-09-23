"""Shared utilities and singleton accessors for core.mcp_server."""

import os
import logging
from typing import Optional, Dict
from core.memory_service import get_cerebro as _svc_get_cerebro
from core.memory_store import SQLiteMemoryBioRAG
from middleware.auto_guardado import registrar_accion, analizar_y_autoguardar

logger = logging.getLogger("BioRAG.MCP")

_sesiones_activas: Dict[str, float] = {}


def _get_cerebro() -> SQLiteMemoryBioRAG:
    """Reusa la corteza (singleton). No reconstruir 6–11s por tool."""
    return _svc_get_cerebro(os.environ.get("BIORAG_PATH") or None)


def _interceptar(accion: str, texto: str, cerebro) -> Optional[dict]:
    registrar_accion(accion, texto)
    resultado = analizar_y_autoguardar(cerebro)
    if resultado:
        logger.info("auto-guardado: %s (%s)", resultado["concepto"], resultado["categoria"])
    return resultado
