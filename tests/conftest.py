"""
tests/conftest.py — Aislamiento automático de base de datos para pytest (Fix F-T1).

Garantiza que toda ejecución de `pytest` (local o en CI) opere sobre una copia
temporal aislada del snapshot y NUNCA toque ni mute `MemoryBioRAG_Data/memory_biorag.db`.
"""

import os
import shutil
import sqlite3
import tempfile
import pytest

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SNAPSHOT = os.path.join(_RAIZ, "snapshots", "qa_escape_qcr_20260811.db")


@pytest.fixture(scope="session", autouse=True)
def _aislar_base_datos_para_tests():
    """Si no hay BIORAG_PATH explícito, crea una copia temporal del snapshot."""
    created_tmp = None
    if "BIORAG_PATH" not in os.environ:
        if os.path.exists(_SNAPSHOT):
            tmp_dir = tempfile.mkdtemp(prefix="biorag_pytest_")
            tmp_db = os.path.join(tmp_dir, "pytest_memory.db")
            shutil.copyfile(_SNAPSHOT, tmp_db)
            # Solo la copia desechable de tests puede cambiar journal. Un snapshot
            # WAL no es compatible con escritores SQLite vulnerables; normalizar
            # esta copia evita que tests distintos compartan accidentalmente WAL.
            from core.sqlite_runtime import is_wal_reset_vulnerable
            if is_wal_reset_vulnerable():
                conn = sqlite3.connect(tmp_db)
                try:
                    if conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal":
                        conn.execute("PRAGMA journal_mode=DELETE")
                finally:
                    conn.close()
            os.environ["BIORAG_PATH"] = tmp_db
            created_tmp = tmp_dir
    
    yield

    if created_tmp and os.path.exists(created_tmp):
        try:
            shutil.rmtree(created_tmp)
        except Exception:
            pass
