#!/usr/bin/env python3
"""
T2 — Schema `sustantivos_clave` (RF-4, RF-6, RF-7, RF-15).

Verifica que la columna `sustantivos_clave` exista en corto_plazo y largo_plazo,
que la FTS5 trigram tenga 4 columnas, que el trigger `_au` la incluya en el INSERT
a FTS, y que la consolidación propague el campo de corto → largo (sobrescribiendo
solo si corto tiene valor, preservando si está vacío).

Criterios "Hecho cuando" de T2 (tasks.md):
  - sqlite3 memory_biorag.db ".schema corto_plazo" muestra sustantivos_clave TEXT DEFAULT ''
  - sqlite3 memory_biorag.db ".schema largo_plazo" muestra sustantivos_clave TEXT DEFAULT ''
  - largo_plazo_fts tiene 4 columnas: concepto, contenido, sinonimos, sustantivos_clave
  - Trigger _au (AFTER UPDATE) incluye sustantivos_clave en el INSERT a FTS5
  - Test de consolidación: nodo con sustantivos_clave="a,b" en corto_plazo aparece en largo_plazo tras consolidar
  - Test consolidación: nodo con sustantivos_clave="" en corto_plazo NO sobrescribe el de largo_plazo
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.memory_store import SQLiteMemoryBioRAG


@pytest.fixture()
def cerebro(tmp_path):
    return SQLiteMemoryBioRAG(str(tmp_path / "schema.db"))


def _crear_db_schema_viejo(db_path):
    """Construye una DB completa y la DEGRADA al estado pre-T2: sin columna sustantivos_clave
    y FTS5 trigram de 3 columnas. Reinstanciar dispara la migración ALTER condicional + rebuild FTS."""
    import sqlite3
    cerebro = SQLiteMemoryBioRAG(str(db_path))
    cerebro.cursor.execute(
        "INSERT INTO largo_plazo (concepto, contenido, categoria) VALUES ('nodo_viejo', 'contenido legacy', 1)"
    )
    # Degradar schema (simula estado anterior a la migración v25)
    # Orden crítico: primero dropear triggers del FTS — si quedan activos, el DROP COLUMN
    # falla ("error in trigger ... after drop column") y la columna nunca se elimina.
    cerebro.cursor.execute("DROP TRIGGER IF EXISTS largo_plazo_ai")
    cerebro.cursor.execute("DROP TRIGGER IF EXISTS largo_plazo_ad")
    cerebro.cursor.execute("DROP TRIGGER IF EXISTS largo_plazo_au")
    try:
        cerebro.cursor.execute("ALTER TABLE largo_plazo DROP COLUMN sustantivos_clave")
        cerebro.cursor.execute("ALTER TABLE corto_plazo DROP COLUMN sustantivos_clave")
    except sqlite3.OperationalError:
        pass
    cerebro.cursor.execute("DROP TABLE IF EXISTS largo_plazo_fts")
    cerebro.cursor.execute("""CREATE VIRTUAL TABLE largo_plazo_fts USING fts5(
        concepto, contenido, sinonimos, tokenize='trigram')""")
    cerebro.conn.commit()
    cerebro.conn.close()
    return db_path


def test_migracion_db_vieja_agrega_columnas(tmp_path):
    """RF-15: una DB pre-T2 (sin la columna y FTS 3-col) se migra al instanciar:
    columnas agregadas y FTS4 reconstruida; nodo viejo queda con sustantivos_clave vacío (""), sin backfill."""
    db_path = _crear_db_schema_viejo(tmp_path / "vieja.db")
    cerebro = SQLiteMemoryBioRAG(str(db_path))
    # Columnas presentes tras migración
    for tabla in ("corto_plazo", "largo_plazo"):
        assert "sustantivos_clave" in _cols(cerebro, tabla), f"Migración no agregó columna en {tabla}"
    # FTS reconstruida con 4 columnas
    for col in ("concepto", "contenido", "sinonimos", "sustantivos_clave"):
        assert col in _cols(cerebro, "largo_plazo_fts"), f"FTS migrada sin columna {col}"
    # Nodo legacy sin backfill (RF-15)
    row = cerebro.cursor.execute(
        "SELECT sustantivos_clave FROM largo_plazo WHERE concepto = 'nodo_viejo'"
    ).fetchone()
    assert row[0] == "", f"RF-15 violado: backfill inesperado {row[0]!r}"


def _cols(cerebro, tabla):
    return {row[1] for row in cerebro.cursor.execute(f"PRAGMA table_info({tabla})").fetchall()}


def _insertar_corto(cerebro, concepto, contenido, sustantivos_clave):
    """Inserta directo en corto_plazo controlando la columna sustantivos_clave (categoria=1)."""
    cerebro.cursor.execute(
        "INSERT INTO corto_plazo (concepto, contenido, timestamp, sinonimos, categoria, sustantivos_clave) "
        "VALUES (?, ?, 1000.0, '', 1, ?)",
        (concepto, contenido, sustantivos_clave),
    )
    cerebro.conn.commit()


def test_schema_corto_plazo_tiene_columna(cerebro):
    """Criterio T2: corto_plazo tiene columna sustantivos_clave."""
    assert "sustantivos_clave" in _cols(cerebro, "corto_plazo")


def test_schema_largo_plazo_tiene_columna(cerebro):
    """Criterio T2: largo_plazo tiene columna sustantivos_clave."""
    assert "sustantivos_clave" in _cols(cerebro, "largo_plazo")


def test_fts_tiene_4_columnas(cerebro):
    """Criterio T2: largo_plazo_fts tiene concepto, contenido, sinonimos, sustantivos_clave."""
    cols = _cols(cerebro, "largo_plazo_fts")
    for col in ("concepto", "contenido", "sinonimos", "sustantivos_clave"):
        assert col in cols, f"Falta columna {col} en largo_plazo_fts"


def test_trigger_au_incluye_sustantivos_clave(cerebro):
    """Criterio T2: trigger largo_plazo_au inserta sustantivos_clave en FTS5."""
    row = cerebro.cursor.execute(
        "SELECT sql FROM sqlite_master WHERE type='trigger' AND name='largo_plazo_au'"
    ).fetchone()
    assert row is not None, "No existe trigger largo_plazo_au"
    assert "sustantivos_clave" in row[0], "Trigger _au no incluye sustantivos_clave en el INSERT FTS"


def _consolidar(cerebro):
    cerebro.ciclo_sueno_consolidacion()
    cerebro.conn.commit()


def test_consolidacion_propaga_sustantivos_clave(cerebro):
    """Criterio T2: nodo con sustantivos_clave='a,b' en corto_plazo aparece en largo_plazo tras consolidar."""
    _insertar_corto(cerebro, "nodo_cons", "contenido con tema", "a,b")
    _consolidar(cerebro)
    row = cerebro.cursor.execute(
        "SELECT sustantivos_clave FROM largo_plazo WHERE concepto = 'nodo_cons'"
    ).fetchone()
    assert row is not None, "Nodo no consolidado en largo_plazo"
    assert row[0] == "a,b", f"Esperado 'a,b', obtenido {row[0]!r}"


def test_consolidacion_no_sobrescribe_si_vacio(cerebro):
    """Criterio T2: nodo con sustantivos_clave='' en corto_plazo NO sobrescribe el de largo_plazo."""
    cerebro.cursor.execute(
        "INSERT INTO largo_plazo (concepto, contenido, categoria, sinonimos, creado_en, ultimo_acceso, sustantivos_clave) "
        "VALUES ('nodo_pre', 'contenido previo', 1, '', 1000.0, 1000.0, 'x,y')",
    )
    _insertar_corto(cerebro, "nodo_pre", "actualización sin sustantivos", "")
    _consolidar(cerebro)
    row = cerebro.cursor.execute(
        "SELECT sinonimos, sustantivos_clave FROM largo_plazo WHERE concepto = 'nodo_pre'"
    ).fetchone()
    assert row is not None, "Nodo debió seguir existiendo en largo_plazo"
    assert row[1] == "x,y", f"largo_plazo NO debía sobrescribirse; obtenido {row[1]!r}"


def test_consolidacion_sobrescribe_si_valor_nuevo(cerebro):
    """RF-6/CL-6: si corto_plazo tiene valor nuevo, reemplaza el de largo_plazo."""
    cerebro.cursor.execute(
        "INSERT INTO largo_plazo (concepto, contenido, categoria, sinonimos, creado_en, ultimo_acceso, sustantivos_clave) "
        "VALUES ('nodo_act', 'contenido previo', 1, '', 1000.0, 1000.0, 'x,y')",
    )
    _insertar_corto(cerebro, "nodo_act", "actualización con tema nuevo", "z,w")
    _consolidar(cerebro)
    row = cerebro.cursor.execute(
        "SELECT sustantivos_clave FROM largo_plazo WHERE concepto = 'nodo_act'"
    ).fetchone()
    assert row[0] == "z,w", f"Esperado 'z,w' (sobrescritura), obtenido {row[0]!r}"


def test_consolidacion_fts_indexa_sustantivos_clave(cerebro):
    """RF-7: nodo consolidado con sustantivos_clave queda indexado en la FTS5 de largo_plazo."""
    _insertar_corto(cerebro, "nodo_fts", "contenido con servidor", "servidor,timeout")
    _consolidar(cerebro)
    row = cerebro.cursor.execute(
        "SELECT s.sustantivos_clave FROM largo_plazo_fts s "
        "JOIN largo_plazo l ON s.rowid = l.rowid WHERE l.concepto = 'nodo_fts'"
    ).fetchone()
    assert row is not None, "Nodo sin fila en largo_plazo_fts"
    assert row[0] == "servidor,timeout", f"FTS no indexó sustantivos_clave; obtenido {row[0]!r}"