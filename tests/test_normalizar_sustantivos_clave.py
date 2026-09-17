#!/usr/bin/env python3
"""
T1 — RF-10: normalización central de sustantivos_clave.

Verifica la función `normalizar_sustantivos_clave` de `core/memory_store.py`:
lowercase, quitar tildes (á→a, é→e, í→i, ó→o, ú→u), preservar ñ, strip de
espacios alrededor de comas, colapsar comas múltiples, dedup preservando orden.

Criterios "Hecho cuando" de T1 (spec RF-10, plan §C):
  - normalizar_sustantivos_clave("Servidor, Backend,, TIMEOUT") == "servidor,backend,timeout"
  - normalizar_sustantivos_clave("conexión, Pingüino") == "conexion,pinguino"
  - ñ preservada ("ñandú" -> "ñandu", no "nandu")
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.memory_store import normalizar_sustantivos_clave


def test_basico_lowercase_trim_dedup():
    """Criterio T1: 'Servidor, Backend,, TIMEOUT' -> 'servidor,backend,timeout'."""
    assert normalizar_sustantivos_clave("Servidor, Backend,, TIMEOUT") == "servidor,backend,timeout"


def test_tildes_eliminadas_y_enie_preservada():
    """Criterio T1: 'conexión, Pingüino' -> 'conexion,pinguino'."""
    assert normalizar_sustantivos_clave("conexión, Pingüino") == "conexion,pinguino"


def test_n_acentos_y_enie():
    """'ñandú, corazón' -> 'ñandu,corazon': ú->u, ó->o, ñ preservada."""
    r = normalizar_sustantivos_clave("ñandú, corazón")
    assert r == "ñandu,corazon"
    assert "ñ" in r  # ñ preservada


def test_dedup_preserva_orden():
    """Duplicados se eliminan conservando la primera aparición."""
    assert normalizar_sustantivos_clave("a,b,a,c,b") == "a,b,c"


def test_espacios_adyacentes_a_comas():
    """Espacios alrededor de comas se eliminan."""
    assert normalizar_sustantivos_clave(" servidor ,  backend ,timeout ") == "servidor,backend,timeout"


def test_vacio_no_excepcion():
    """String vacío retorna '' sin excepción."""
    assert normalizar_sustantivos_clave("") == ""


def test_solo_comas_y_espacios():
    """Solo comas/espacios retorna '' (sin términos válidos)."""
    assert normalizar_sustantivos_clave("  , , ,  ") == ""