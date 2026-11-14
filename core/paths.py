"""Resolución canónica de DB_PATH.

POR QUÉ: MCP, CLI y dashboard históricamente resolvían la ruta de la SQLite
por su cuenta (cwd, constantes locales, env). Eso produce DBs divergentes:
enseñás por una interfaz y otra no ve las consecuencias. Una sola función
es la fuente de verdad para el path efectivo.
"""
from __future__ import annotations

import os

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB = os.path.join(_PROJECT_ROOT, "MemoryBioRAG_Data", "memory_biorag.db")


def project_root() -> str:
    """Raíz del repositorio (padre de core/)."""
    return _PROJECT_ROOT


def resolve_db_path(explicit: str | None = None) -> str:
    """Devuelve el path SQLite efectivo.

    Orden: argumento explícito → BIORAG_PATH → MemoryBioRAG_Data/memory_biorag.db.
    No crea el archivo; solo resuelve la ruta. `:memory:` se respeta tal cual.
    """
    if explicit:
        return explicit
    env = os.environ.get("BIORAG_PATH")
    if env:
        return env
    return DEFAULT_DB
