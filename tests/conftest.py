"""
tests/conftest.py — Aislamiento automático de base de datos y estado DMN para pytest (Fix F-T1).

Garantiza que toda ejecución de `pytest` (local o en CI) opere sobre una copia
temporal aislada del snapshot y NUNCA toque ni mute la base de datos viva
ni `estado_hormiga.json` en el espacio de trabajo.
"""

import os
import shutil
import tempfile
import pytest

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SNAPSHOT = os.path.join(_RAIZ, "snapshots", "qa_escape_qcr_20260811.db")


@pytest.fixture(scope="session", autouse=True)
def _aislar_base_datos_para_tests():
    """Aísla base de datos y estado de DMN/hormiguita para la sesión de pytest."""
    created_tmp = None
    orig_biorag_path = os.environ.get("BIORAG_PATH")
    orig_dmn_path = os.environ.get("BIORAG_DMN_ESTADO_PATH")

    tmp_dir = tempfile.mkdtemp(prefix="biorag_pytest_")
    created_tmp = tmp_dir

    if "BIORAG_PATH" not in os.environ:
        if os.path.exists(_SNAPSHOT):
            tmp_db = os.path.join(tmp_dir, "pytest_memory.db")
            shutil.copyfile(_SNAPSHOT, tmp_db)
            os.environ["BIORAG_PATH"] = tmp_db

    if "BIORAG_DMN_ESTADO_PATH" not in os.environ:
        tmp_hormiga = os.path.join(tmp_dir, "estado_hormiga.json")
        with open(tmp_hormiga, "w", encoding="utf-8") as f:
            f.write('{"frontier": [], "visitados_hoy": [], "visitados_total": [], "vacios_cognitivos": []}')
        os.environ["BIORAG_DMN_ESTADO_PATH"] = tmp_hormiga

    yield

    if orig_biorag_path is not None:
        os.environ["BIORAG_PATH"] = orig_biorag_path
    else:
        os.environ.pop("BIORAG_PATH", None)

    if orig_dmn_path is not None:
        os.environ["BIORAG_DMN_ESTADO_PATH"] = orig_dmn_path
    else:
        os.environ.pop("BIORAG_DMN_ESTADO_PATH", None)

    if created_tmp and os.path.exists(created_tmp):
        try:
            shutil.rmtree(created_tmp)
        except Exception:
            pass

