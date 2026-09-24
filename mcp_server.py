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
import threading
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

from core.paths import resolve_db_path
from core.memory_service import get_cerebro as _svc_get_cerebro

_DEFAULT_DB = resolve_db_path()
DB_PATH = _DEFAULT_DB

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.memory_store import SQLiteMemoryBioRAG
from core.sinapsis import auto_vincular, vincular_por_sinonimos, _tokenizar, _peso_similitud
from core.categorizador import inferir_categoria
from middleware.auto_guardado import registrar_accion, analizar_y_autoguardar

# Warmup silencioso de WordNet para eliminar latencia en primera query
try:
    from core.clasificador_wordnet import obtener_lexnames_query
    obtener_lexnames_query("test")
except Exception:
    pass

# =============================================================================
# Configuración de Usuario (Override con variables de entorno)
# =============================================================================
# Los defaults están aquí. Para cambiar, setear la variable de entorno
# correspondiente o crear .env.local en la raíz del proyecto.
# =============================================================================

PARAFRASIS_PENALTY = 0.95
"""Factor multiplicativo aplicado a resultados de variantes no exactas (paráfrasis).
El query original (i==0) mantiene factor 1.0; variantes penalizan ×0.95."""


from core.mcp_server._shared import (
    _get_cerebro,
    _interceptar,
    _sesiones_activas,
)


# _load_catalogo_dimensiones, _CATALOGO_DIMENSIONES, _ensure_catalogo_loaded
# eliminados — se computaban al importar pero nunca se usaban



# --- MCP Server ------------------------------------------------------------


from core.mcp_server import communication as _mcp_communication
from core.mcp_server import catalog as _mcp_catalog
from core.mcp_server import synapses as _mcp_synapses
from core.mcp_server import concept_hub_tools as _mcp_concept_hub_tools
from core.mcp_server import introspection as _mcp_introspection
from core.mcp_server import consolidation as _mcp_consolidation
from core.mcp_server import daemon as _mcp_daemon
from core.mcp_server import session as _mcp_session
from core.mcp_server import oracle as _mcp_oracle
from core.mcp_server import sync as _mcp_sync
from core.mcp_server import calibrar as _mcp_calibrar
from core.mcp_server import resources as _mcp_resources
from core.mcp_server import prompt as _mcp_prompt
from core.mcp_server import write as _mcp_write
from core.mcp_server import search as _mcp_search
from core.mcp_server.prompt import ORACLE_PROMPT


def _build_server():
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise ImportError(
            "BioRAG MCP server requires the 'mcp' 1.x package (mcp>=1.0.0,<2).\n"
            f"  pip install 'mcp>=1.0.0,<2'\n  ({exc})"
        ) from exc

    # ORACLE_PROMPT va aquí como `instructions`: es el contexto base del agente.
    # FastMCP lo inyecta como system-level context — NO usar como descripción de tool.
    mcp = FastMCP(
        "biorag",
        instructions=ORACLE_PROMPT,
    )

    # ── Submódulos extraídos (Fase 2) ────────────────────────────────────────
    _mcp_communication.register(mcp)
    _mcp_catalog.register(mcp)
    _mcp_synapses.register(mcp)
    _mcp_concept_hub_tools.register(mcp)
    _mcp_introspection.register(mcp)
    _mcp_consolidation.register(mcp)
    _mcp_daemon.register(mcp)
    _mcp_session.register(mcp)
    _mcp_oracle.register(mcp)
    _mcp_sync.register(mcp)
    _mcp_calibrar.register(mcp)
    _mcp_resources.register(mcp)
    _mcp_prompt.register(mcp)
    _mcp_write.register(mcp)
    _mcp_search.register(mcp)

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

    # El MCP es el guardián del daemon: al arrancar cualquier consola,
    # verifica que la hormiguita esté viva y la spawnea si hace falta.
    # El daemon es un proceso detachado que sobrevive al cierre de la sesión.
    try:
        from core.daemon_lifecycle import ensure_daemon_alive
        import threading

        def _spawn_daemon_bg() -> None:
            # Corre en el hilo de fondo: el try/except tiene que estar ACÁ
            # adentro, porque una excepción lanzada dentro del target de un
            # Thread vive en un contexto de ejecución distinto al del hilo
            # que llamó a .start() — un except afuera de threading.Thread(...)
            # solo captura fallos al crear/arrancar el hilo, no lo que pasa
            # una vez que ya está corriendo.
            try:
                ensure_daemon_alive(intervalo_horas=0.5)
            except Exception as exc:
                logger.warning("No se pudo verificar/spawnear el daemon: %s", exc)

        # ensure_daemon_alive() puede bloquear hasta ~5s (spawn_daemon_detached
        # espera el PID file del daemon en loop de 0.5s x10). Eso retrasaba
        # el handshake MCP (initialize) del transport stdio, causando
        # "context deadline exceeded" en el cliente. Se corre en background
        # para que server.run(transport="stdio") arranque a responder de
        # inmediato; el daemon igual queda spawneado (proceso detachado,
        # no depende de que este hilo termine).
        threading.Thread(target=_spawn_daemon_bg, daemon=True).start()
    except Exception as exc:
        logger.warning("No se pudo verificar/spawnear el daemon: %s", exc)

    try:
        if use_sse:
            sys.stderr.write(f"BioRAG MCP iniciado en SSE :{port}\n")
            server.settings.port = port
            server.run(transport="sse")
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