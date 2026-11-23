#!/usr/bin/env python3
"""Transport stdio del servidor FastMCP real, sin lanzar el daemon global.

Solo es un launcher aislado para el harness QA: requiere BIORAG_PATH dentro
 de BIORAG_QA_TEMP_ROOT y registra las tools MCP normales sin cambiar su código.
"""
from __future__ import annotations

import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    db_value = os.environ.get("BIORAG_PATH")
    temp_value = os.environ.get("BIORAG_QA_TEMP_ROOT")
    if not db_value or not temp_value:
        raise SystemExit("Se requieren BIORAG_PATH y BIORAG_QA_TEMP_ROOT explícitos")
    db_path = Path(db_value).resolve()
    temp_root = Path(temp_value).resolve()
    try:
        db_path.relative_to(temp_root)
    except ValueError as exc:
        raise SystemExit("Guardrail: BIORAG_PATH está fuera del temporal QA") from exc

    fixed_time = float(os.environ.get("BIORAG_QA_RELOJ_FIJO", "1793059200.0"))
    time.time = lambda: fixed_time

    from core.mcp_server.server import _build_server, _proteger_canal_stdio

    _proteger_canal_stdio()
    app = _build_server()
    app.run(transport="stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
