"""Regresión D15 (olvido proporcional al tiempo) y D19 (sinónimos en orden estable).

D15: el LTD del ciclo de sueño restaba una "noche" de olvido entera en CADA llamada a
consolidar, sin mirar el tiempo transcurrido. Con el uso real (~4.8 ciclos/día, mediana
23 min) la memoria dormía cientos de nodos por ciclo. Ahora el olvido se escala por el
tiempo desde el ciclo anterior (fracción de una noche de 24 h).

D19: search.py cortaba los 5 primeros sinónimos WordNet de un ``set``; el orden de un set
de strings depende de PYTHONHASHSEED, así que el mismo query daba resultados distintos
entre procesos. Ahora el orden es determinista (relevancia WordNet).
"""
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from core.memory import consolidation as C
from core.memory import constants
from core.memory_store import SQLiteMemoryBioRAG

RAIZ = Path(__file__).resolve().parents[1]


@pytest.fixture
def cerebro(tmp_path, monkeypatch):
    monkeypatch.setenv("BIORAG_NEURONA", "0")
    c = SQLiteMemoryBioRAG(str(tmp_path / "ltd.db"))
    yield c
    c.cerrar_sistema()


def _ultimo_ciclo_hace(c, segundos):
    c.cursor.execute("DELETE FROM metricas_cognitivas")
    c.cursor.execute("INSERT INTO metricas_cognitivas (timestamp) VALUES (?)", (time.time() - segundos,))
    c.conn.commit()


def _nodo_volatil(c, concepto="nodo_volatil_ltd", peso=0.30):
    c.cursor.execute(
        "INSERT INTO largo_plazo (concepto, contenido, peso_sinaptico, estado, prioridad, ultimo_acceso) "
        "VALUES (?, ?, ?, 'activo', 5, ?)",
        (concepto, "contenido sin protección para medir el olvido", peso, time.time() - 30 * 86400),
    )
    c.conn.commit()
    return concepto


def _peso(c, concepto):
    return c.cursor.execute("SELECT peso_sinaptico FROM largo_plazo WHERE concepto = ?", (concepto,)).fetchone()[0]


# ───────────────────────── D15: fracción de noche ─────────────────────────

def test_sin_ciclo_previo_es_noche_completa(cerebro):
    cerebro.cursor.execute("DELETE FROM metricas_cognitivas")
    assert C.fraccion_de_noche(cerebro) == 1.0


def test_fraccion_proporcional_al_tiempo(cerebro):
    _ultimo_ciclo_hace(cerebro, 6 * 3600)
    assert C.fraccion_de_noche(cerebro) == pytest.approx(0.25, abs=0.01)
    _ultimo_ciclo_hace(cerebro, 3 * 86400)
    assert C.fraccion_de_noche(cerebro) == 1.0  # nunca más de una noche por ciclo


def test_flag_apagado_restaura_comportamiento_previo(cerebro, monkeypatch):
    monkeypatch.setattr(constants, "LTD_POR_TIEMPO", False)
    _ultimo_ciclo_hace(cerebro, 60)
    assert C.fraccion_de_noche(cerebro) == 1.0


def test_consolidar_seguido_casi_no_olvida(cerebro):
    """Dos consolidar con un minuto de diferencia ya no restan dos noches de olvido."""
    concepto = _nodo_volatil(cerebro)
    _ultimo_ciclo_hace(cerebro, 60)
    cerebro.ciclo_sueno_consolidacion()
    perdido = 0.30 - _peso(cerebro, concepto)
    assert 0 <= perdido < 0.005, perdido
    assert cerebro.cursor.execute(
        "SELECT estado FROM largo_plazo WHERE concepto = ?", (concepto,)).fetchone()[0] == "activo"


def test_una_noche_completa_olvida_como_antes(cerebro, monkeypatch):
    """Con 24 h o más desde el ciclo anterior el olvido es idéntico al de antes del fix."""
    a = _nodo_volatil(cerebro, "nodo_a")
    _ultimo_ciclo_hace(cerebro, 2 * 86400)
    cerebro.ciclo_sueno_consolidacion()
    peso_nuevo = _peso(cerebro, a)

    monkeypatch.setattr(constants, "LTD_POR_TIEMPO", False)
    b = _nodo_volatil(cerebro, "nodo_b")
    cerebro.ciclo_sueno_consolidacion()
    peso_viejo = _peso(cerebro, b)

    assert peso_nuevo < 0.30
    assert peso_nuevo == peso_viejo


# ───────────────────────── D19: sinónimos estables ─────────────────────────

_SCRIPT = (
    "import sys; sys.path.insert(0, %r)\n"
    "from core.fallback_simbolico import expandir_query_wordnet_ordenada, _verificar_wordnet\n"
    "print(_verificar_wordnet(), expandir_query_wordnet_ordenada(['version', 'real', 'casa'])[:12])\n"
) % str(RAIZ)


def test_sinonimos_iguales_con_cualquier_hashseed():
    salidas = set()
    for semilla in ("0", "4", "5", "11"):
        env = dict(os.environ, PYTHONHASHSEED=semilla)
        r = subprocess.run([sys.executable, "-c", _SCRIPT], env=env, capture_output=True, text=True, timeout=120)
        assert r.returncode == 0, r.stderr
        salidas.add(r.stdout.strip().splitlines()[-1])
    assert len(salidas) == 1, salidas


def test_orden_respeta_query_y_excluye_originales():
    from core.fallback_simbolico import (
        _verificar_wordnet, expandir_palabra_wordnet, expandir_palabra_wordnet_ordenada,
        expandir_query_wordnet, expandir_query_wordnet_ordenada,
    )
    if not _verificar_wordnet():
        pytest.skip("WordNet no disponible")
    tokens = ["version", "real"]
    orden = expandir_query_wordnet_ordenada(tokens)
    assert len(orden) == len(set(orden))
    assert not set(tokens) & set(orden)
    # Mismo conjunto que la versión no ordenada (no cambia QUÉ sinónimos hay, solo su orden).
    assert set(orden) == expandir_query_wordnet(set(tokens))
    assert set(expandir_palabra_wordnet_ordenada("version")) == set(expandir_palabra_wordnet("version"))
    # Los del primer token van antes que los exclusivos del segundo.
    primeros = expandir_palabra_wordnet_ordenada("version")
    if primeros:
        assert orden[0] == primeros[0]
