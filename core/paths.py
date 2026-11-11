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


def _canonicalize_db_path(path: str | os.PathLike[str]) -> str:
    """Normaliza un path de archivo sin crear directorios ni abrir la DB."""
    value = os.fsdecode(os.fspath(path))
    if value == ":memory:" or value.startswith("file:"):
        # SQLite URI tiene semántica propia (query params, mode=ro/memory):
        # no se reescribe como ruta del filesystem.
        return value
    expanded = os.path.expanduser(value)
    return os.path.normcase(os.path.realpath(os.path.abspath(expanded)))


def resolve_db_path(explicit: str | os.PathLike[str] | None = None) -> str:
    """Devuelve el path SQLite efectivo como ruta canónica.

    Orden: argumento explícito → BIORAG_PATH → MemoryBioRAG_Data/memory_biorag.db.
    Una ruta relativa se interpreta desde el cwd del consumidor. No crea el
    archivo ni directorios; `:memory:` y SQLite file-URI se conservan intactos.
    """
    if explicit:
        selected = explicit
    else:
        selected = os.environ.get("BIORAG_PATH") or DEFAULT_DB
    return _canonicalize_db_path(selected)
