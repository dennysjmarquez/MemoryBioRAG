"""Guardas de la división de `core/sqlite_runtime.py` en `core/sqlite/`.

Estas pruebas vigilan dos fallos reales que aparecieron al mover el código.
No comprueban estilo: comprueban que no vuelvan.
"""
from __future__ import annotations

import ast
import sqlite3
from pathlib import Path

import pytest

from core import sqlite_runtime
from core.sqlite import constants as _sqlite_config

PAQUETE = Path(__file__).resolve().parents[1] / "core" / "sqlite"
MODULOS = ["constants", "epoch", "pair_guard", "tracking", "journal", "opening"]


def _usar_version(monkeypatch, version):
    monkeypatch.setattr(_sqlite_config, "_effective_sqlite_version", lambda: version)


def test_close_libera_el_wal_de_una_conexion_fallida(tmp_path, monkeypatch):
    """Un cursor sin cerrar mantiene bloqueada la base.

    `execute()` crea un cursor por sentencia y no lo cierra. Ese cursor
    mantiene viva la conexión hasta que pasa el recolector, y mientras tanto
    el `-wal` no se consolida: la siguiente apertura falla con
    "database is locked". `close()` debe cerrarlos y liberar el archivo.
    """
    _usar_version(monkeypatch, (3, 45, 1))
    path = tmp_path / "bloqueo.db"
    owner = sqlite3.connect(path, timeout=0)
    owner.execute("PRAGMA journal_mode=WAL")
    owner.execute("CREATE TABLE t (v TEXT)")
    owner.execute("INSERT INTO t VALUES ('intacto')")
    owner.commit()

    monkeypatch.setenv("BIORAG_SQLITE_FORCE_OPEN", "1")
    # La transición de journal falla porque otro cliente tiene la base abierta.
    with pytest.raises(sqlite_runtime.UnsafeSQLiteJournalModeError):
        sqlite_runtime.open_writer(path, allow_existing_journal_transition=True)
    owner.close()

    # Sin cerrar los cursores, aquí llegaría "database is locked".
    conn = sqlite_runtime.open_writer(path, allow_existing_journal_transition=True)
    try:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "delete"
    finally:
        conn.close()


def test_los_modulos_del_paquete_cargan_sin_errores():
    """Cada módulo importa por separado, sin depender del orden."""
    for modulo in MODULOS:
        __import__(f"core.sqlite.{modulo}")


def test_la_fachada_reexporta_lo_publico():
    """Los consumidores importan de `core.sqlite_runtime`, no de dentro."""
    for nombre in sqlite_runtime.__all__:
        assert hasattr(sqlite_runtime, nombre), f"falta {nombre} en la fachada"
    assert sqlite_runtime.open_writer.__module__ == "core.sqlite.opening"


def test_el_paquete_no_tiene_dependencias_circulares():
    """El grafo va en un solo sentido: opening → ... → config."""
    orden = {m: i for i, m in enumerate(MODULOS)}
    for modulo in MODULOS:
        arbol = ast.parse((PAQUETE / f"{modulo}.py").read_text())
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.ImportFrom) and nodo.module:
                partes = nodo.module.split(".")
                if len(partes) == 3 and partes[:2] == ["core", "sqlite"]:
                    destino = partes[2]
                    assert orden[destino] < orden[modulo], (
                        f"{modulo} importa de {destino}, que va después: "
                        "se rompe la dirección única de dependencias"
                    )


def test_ningun_modulo_interno_es_importado_desde_fuera():
    """Solo la fachada se usa desde el código del producto.

    Las pruebas quedan fuera del alcance: algunas necesitan parchear la versión
    del motor dentro de un subproceso, y eso exige importar el módulo donde se
    lee. Eso es legítimo en una prueba; en el motor, no.
    """
    raiz = Path(__file__).resolve().parents[1]
    permitidos = {PAQUETE / f"{m}.py" for m in MODULOS}
    permitidos.add(raiz / "core" / "sqlite_runtime.py")

    for archivo in raiz.rglob("*.py"):
        if archivo in permitidos or "node_modules" in archivo.parts:
            continue
        if "tests" in archivo.parts:
            continue
        try:
            texto = archivo.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        if "from core.sqlite." not in texto and "import core.sqlite." not in texto:
            continue
        for modulo in MODULOS:
            assert f"core.sqlite.{modulo} " not in texto, (
                f"{archivo} importa de core.sqlite.{modulo} directamente; "
                "debe usar la fachada core.sqlite_runtime"
            )
