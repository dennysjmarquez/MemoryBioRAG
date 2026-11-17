"""Resolución canónica de DB_PATH.

POR QUÉ: MCP, CLI y dashboard históricamente resolvían la ruta de la SQLite
por su cuenta (cwd, constantes locales, env). Eso produce DBs divergentes:
enseñás por una interfaz y otra no ve las consecuencias. Una sola función
es la fuente de verdad para el path efectivo.

El destino canónico para una instalación nueva está fuera del repositorio, en
~/.biorag/memory_biorag.db (multiplataforma: Windows %USERPROFILE%/.biorag,
macOS/Linux ~/.biorag). La resolución sigue respetando primero un argumento
explícito y BIORAG_PATH, y conserva el fallback a la ruta legacy si existe;
por tanto, un override puede apuntar deliberadamente dentro del repositorio.
"""
from __future__ import annotations

import os
from pathlib import Path

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LEGACY_DB = os.path.join(_PROJECT_ROOT, "MemoryBioRAG_Data", "memory_biorag.db")
_USER_HOME_DB = os.path.join(str(Path.home()), ".biorag", "memory_biorag.db")
DEFAULT_DB = _USER_HOME_DB


def project_root() -> str:
    """Raíz del repositorio (padre de core/)."""
    return _PROJECT_ROOT


def legacy_db_path() -> str:
    """Ruta histórica legacy de la base de datos dentro del repo."""
    return _LEGACY_DB


def user_db_path() -> str:
    """Ruta canónica de la base de datos viva del usuario en ~/.biorag/."""
    return _USER_HOME_DB


def resolve_db_path(explicit: str | None = None) -> str:
    """Devuelve el path SQLite efectivo.

    Orden de prioridad:
      1. Argumento explícito si se provee.
      2. Variable de entorno BIORAG_PATH.
      3. Base en ~/.biorag/memory_biorag.db si existe.
      4. Base legacy en MemoryBioRAG_Data/memory_biorag.db si aún no ha sido migrada.
      5. DEFAULT_DB (~/.biorag/memory_biorag.db).

    No crea el archivo; solo resuelve la ruta. `:memory:` se respeta tal cual.
    """
    if explicit:
        return explicit
    env = os.environ.get("BIORAG_PATH")
    if env:
        return env
    if os.path.exists(_USER_HOME_DB):
        return _USER_HOME_DB
    if os.path.exists(_LEGACY_DB):
        return _LEGACY_DB
    return DEFAULT_DB
