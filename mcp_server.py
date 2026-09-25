#!/usr/bin/env python3
"""Shim raíz hacia core/mcp_server/server.py para compatibilidad hacia atrás."""
import sys
from core.mcp_server.server import _build_server, main

__all__ = ["_build_server", "main"]

if __name__ == "__main__":
    sys.exit(main())