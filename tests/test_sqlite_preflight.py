"""Pruebas del aviso de runtime en la puerta de entrada.

Qué fijan: que el problema del WAL-reset bug se comunique **al arrancar** y no a
mitad del trabajo, y que el aviso no se dispare cuando no hay riesgo.

Motivo (incidente real, 2026-11-11): el usuario instaló el sistema, el agente no
podía guardar, y el error solo apareció cuando pidió recordar algo. La regla
existía en el camino de escritura, pero nadie la anunciaba antes.
"""
from __future__ import annotations

import sqlite3

import pytest

from core.sqlite import constants as _cfg
from core.sqlite import preflight


def _base_en(tmp_path, nombre: str, modo: str):
    ruta = tmp_path / nombre
    conn = sqlite3.connect(ruta)
    try:
        conn.execute(f"PRAGMA journal_mode={modo}")
        conn.execute("CREATE TABLE t (v TEXT)")
        conn.commit()
    finally:
        conn.close()
    return ruta


def _simular_version(monkeypatch, version):
    monkeypatch.setattr(_cfg, "_effective_sqlite_version", lambda: version)
    monkeypatch.setattr(preflight, "_effective_sqlite_version", lambda: version)


def test_avisa_al_arrancar_con_runtime_vulnerable_y_base_en_wal(tmp_path, monkeypatch):
    """El caso del incidente: 3.45.1 y la base en WAL. Debe avisar al arrancar."""
    _simular_version(monkeypatch, (3, 45, 1))
    ruta = _base_en(tmp_path, "wal.db", "WAL")

    resultado = preflight.comprobar_runtime(ruta)

    assert resultado.vulnerable is True
    assert resultado.base_en_wal is True
    assert resultado.mensaje is not None
    # El mensaje debe decir qué hacer, no solo qué falla.
    assert "pip" in resultado.mensaje, "debe aclarar que no se arregla con pip"
    assert "sqlite_version" in resultado.mensaje, "debe dar el comando de comprobación"
    assert "3.51.3" in resultado.mensaje, "debe nombrar una versión corregida"


def test_no_impide_arrancar(tmp_path, monkeypatch):
    """Informa, no bloquea: dejar al usuario sin servicio no es aceptable."""
    _simular_version(monkeypatch, (3, 45, 1))
    ruta = _base_en(tmp_path, "wal.db", "WAL")

    resultado = preflight.comprobar_runtime(ruta)

    assert resultado.bloqueante is False, "el aviso de runtime no debe bloquear el arranque"


def test_no_avisa_si_la_base_no_esta_en_wal(tmp_path, monkeypatch):
    """Sin WAL no hay riesgo del WAL-reset bug, aunque el runtime sea viejo."""
    _simular_version(monkeypatch, (3, 45, 1))
    ruta = _base_en(tmp_path, "delete.db", "DELETE")

    resultado = preflight.comprobar_runtime(ruta)

    assert resultado.vulnerable is True
    assert resultado.base_en_wal is False
    assert resultado.ok is True, "no debe avisar si la base no está en WAL"


@pytest.mark.parametrize("version", [(3, 51, 3), (3, 50, 7), (3, 44, 6), (3, 52, 0)])
def test_no_avisa_con_runtimes_corregidos(tmp_path, monkeypatch, version):
    """Las versiones con el arreglo, incluidas las de backport, no avisan."""
    _simular_version(monkeypatch, version)
    ruta = _base_en(tmp_path, "wal.db", "WAL")

    resultado = preflight.comprobar_runtime(ruta)

    assert resultado.vulnerable is False
    assert resultado.ok is True


def test_avisa_si_la_base_todavia_no_existe(tmp_path, monkeypatch):
    """Sin archivo no se puede saber el modo: se avisa con matiz, sin bloquear."""
    _simular_version(monkeypatch, (3, 45, 1))

    resultado = preflight.comprobar_runtime(tmp_path / "no_existe.db")

    assert resultado.base_en_wal is None
    assert resultado.mensaje is not None
    assert resultado.bloqueante is False
    assert "no existe" in resultado.mensaje.lower()


def test_no_avisa_en_el_camino_normal_sin_base(tmp_path, monkeypatch):
    """Con un runtime corregido, ni siquiera se lee la cabecera de la base."""
    _simular_version(monkeypatch, (3, 51, 3))

    resultado = preflight.comprobar_runtime(tmp_path / "no_existe.db")

    assert resultado.ok is True
    assert resultado.version == (3, 51, 3)


def test_anunciar_escribe_en_stderr_y_no_en_stdout(tmp_path, monkeypatch, capsys):
    """El aviso va a stderr: stdout es el canal del protocolo MCP por stdio.

    Escribir el aviso en stdout rompería el handshake del cliente.
    """
    _simular_version(monkeypatch, (3, 45, 1))
    ruta = _base_en(tmp_path, "wal.db", "WAL")

    preflight.anunciar_si_hay_problema(ruta)
    capturado = capsys.readouterr()

    assert "SQLite 3.45.1" in capturado.err
    assert capturado.out == "", "stdout debe quedar limpio para el protocolo MCP"
