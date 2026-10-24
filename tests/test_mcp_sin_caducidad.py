"""Decisión de Dennys: BioRAG no esconde recuerdos por fecha salvo que se pida.

El corte duro por antigüedad (BIORAG_STALE_HARD_CUTOFF) queda en 0 por defecto.
Se comprueba en un proceso limpio, sin la variable en el entorno.
"""
import os
import subprocess
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _cutoff(env_extra=None):
    env = {k: v for k, v in os.environ.items() if k != "BIORAG_STALE_HARD_CUTOFF"}
    env.update(env_extra or {})
    out = subprocess.run(
        [sys.executable, "-c", "from core.mcp_server._shared import STALE_HARD_CUTOFF_DAYS as x; print(x)"],
        cwd=RAIZ, env=env, capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr[-2000:]
    return int(out.stdout.strip().splitlines()[-1])


def test_por_defecto_no_se_esconde_nada_por_fecha():
    assert _cutoff() == 0


def test_el_usuario_puede_pedirlo_explicitamente():
    assert _cutoff({"BIORAG_STALE_HARD_CUTOFF": "365"}) == 365
