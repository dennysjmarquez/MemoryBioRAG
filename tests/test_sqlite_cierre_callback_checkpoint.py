"""No permitir que un callback del checkpoint espere su propio cierre."""

import os
import subprocess
import sys


def test_checkpoint_con_callback_no_reentra_cierre(tmp_path):
    """Un subprocess aísla el posible deadlock y limita la espera de la prueba."""
    programa = r'''
import sys
from core.sqlite import constants
from core.memory_store import SQLiteMemoryBioRAG
constants._effective_sqlite_version = lambda: (3, 51, 3)
motor = SQLiteMemoryBioRAG(sys.argv[1])
motor.conn.execute("CREATE TABLE ejemplo (valor TEXT)")
motor.conn.execute("INSERT INTO ejemplo VALUES ('dato')")
motor.conn.commit()
rechazos = []

def progreso():
    if motor._closing and not rechazos:
        try:
            motor.cerrar_sistema()
        except RuntimeError as exc:
            rechazos.append(str(exc))
    return 0

motor.conn.set_progress_handler(progreso, 1)
motor.cerrar_sistema()
assert len(rechazos) == 1, rechazos
assert "propio cierre" in rechazos[0], rechazos
assert motor._closed and not motor._closing and motor._closing_owner is None
'''
    entorno = os.environ.copy()
    entorno.update(BIORAG_SQLITE_GUARD="1", BIORAG_SQLITE_FORCE_OPEN="0")
    resultado = subprocess.run(
        [sys.executable, "-c", programa, str(tmp_path / "memoria.db")],
        env=entorno, capture_output=True, text=True, timeout=15,
    )
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
