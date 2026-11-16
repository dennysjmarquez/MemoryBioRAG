"""Regression coverage for the empty-corpus search baseline edge case."""

import sqlite3

import pytest

from core.memory import synapses
from core.memory.growth_stable_fts import asegurar_indice_referencia
from core.memory.search import _corte_rowid_positivo
from core.memory_store import SQLiteMemoryBioRAG
from core.similitud_conceptual import (
    _rowid_corte_positivo,
    buscar_por_similitud_latente,
)


_BASELINE_KEYS = (
    "search_baseline_rowid",
    "search_baseline_sinapsis_rowid",
)


def _insert_memory_and_edge(connection):
    cursor = connection.cursor()
    cursor.execute(
        "INSERT INTO largo_plazo "
        "(concepto, contenido, estado, peso_sinaptico) "
        "VALUES (?, ?, 'activo', 0.5)",
        ("manzana_despues", "manzana jugosa madura"),
    )
    memory_rowid = cursor.lastrowid
    cursor.execute(
        "INSERT INTO sinapsis "
        "(origen, destino, peso, tipo, creado_en) "
        "VALUES (?, ?, 0.9, 'test', 1)",
        ("manzana_despues", "vecino_despues"),
    )
    edge_rowid = cursor.lastrowid
    connection.commit()
    return memory_rowid, edge_rowid


@pytest.mark.parametrize("stale_cutoff", [None, 0, -7, "not-a-rowid"])
def test_empty_database_does_not_freeze_invalid_cutoffs_and_later_rows_are_visible(
    tmp_path, stale_cutoff
):
    db = SQLiteMemoryBioRAG(str(tmp_path / "empty.db"))
    try:
        assert db._search_baseline_rowid is None
        assert db._search_baseline_sinapsis_rowid is None
        persisted = dict(db.cursor.execute(
            "SELECT clave, valor FROM data WHERE clave IN (?, ?)", _BASELINE_KEYS
        ).fetchall())
        assert persisted == {}

        _insert_memory_and_edge(db.conn)
        # Stale, absent, invalid, and non-positive in-memory values are all
        # equivalent to no rowid cutoff in each retrieval path.
        db._search_baseline_rowid = stale_cutoff
        db._search_baseline_sinapsis_rowid = stale_cutoff
        assert _corte_rowid_positivo(stale_cutoff) is None
        assert synapses._baseline_sinapsis_positivo(db) is None
        assert _rowid_corte_positivo(stale_cutoff) is None

        results, _ = db.buscar_por_frase("manzana", limite=10)
        assert "manzana_despues" in [row[0] for row in results]
        assert any(
            row[0] == "vecino_despues"
            for row in synapses._aristas_locales_acotadas(db, "manzana_despues")
        )
        latent_results = buscar_por_similitud_latente(
            db.cursor,
            "manzana",
            limite=10,
            cerebro=db,
            baseline_rowid=stale_cutoff,
            edge_rowid_max=stale_cutoff,
        )
        assert any(
            row[1] == "manzana_despues"
            for _, row in latent_results
        )
    finally:
        db.cerrar_sistema()


@pytest.mark.parametrize("legacy_value", ["0", "-3", "not-a-rowid"])
def test_legacy_nonpositive_or_invalid_metadata_is_removed_while_tables_are_empty(
    tmp_path, legacy_value
):
    path = tmp_path / "legacy-empty-zero.db"
    empty_db = SQLiteMemoryBioRAG(str(path))
    empty_db.cerrar_sistema()

    connection = sqlite3.connect(path)
    assert asegurar_indice_referencia(connection, 0)
    connection.executemany(
        "INSERT OR REPLACE INTO data (clave, valor, descripcion) VALUES (?, ?, ?)",
        (
            ("search_baseline_rowid", legacy_value, "legacy empty-memory cutoff"),
            ("search_baseline_sinapsis_rowid", legacy_value, "legacy empty-edge cutoff"),
        ),
    )
    connection.commit()
    connection.close()

    db = SQLiteMemoryBioRAG(str(path))
    try:
        assert db._search_baseline_rowid is None
        assert db._search_baseline_sinapsis_rowid is None
        assert db._search_baseline_fts_ready is False
        persisted = db.cursor.execute(
            "SELECT clave FROM data WHERE clave IN (?, ?)", _BASELINE_KEYS
        ).fetchall()
        assert persisted == []

        _insert_memory_and_edge(db.conn)
        results, _ = db.buscar_por_frase("manzana", limite=10)
        assert "manzana_despues" in [row[0] for row in results]
    finally:
        db.cerrar_sistema()


@pytest.mark.parametrize("legacy_value", ["0", "-3", "not-a-rowid"])
def test_legacy_nonpositive_or_invalid_metadata_is_repaired_when_rows_exist(
    tmp_path, legacy_value
):
    path = tmp_path / "legacy-zero.db"
    empty_db = SQLiteMemoryBioRAG(str(path))
    empty_db.cerrar_sistema()

    connection = sqlite3.connect(path)
    # Reproduce the old startup path: it created reference FTS indexes at cutoff
    # zero, then memories and edges were appended without refreshing those indexes.
    assert asegurar_indice_referencia(connection, 0)
    memory_rowid, edge_rowid = _insert_memory_and_edge(connection)
    connection.executemany(
        "INSERT OR REPLACE INTO data (clave, valor, descripcion) VALUES (?, ?, ?)",
        (
            ("search_baseline_rowid", legacy_value, "legacy empty-memory cutoff"),
            ("search_baseline_sinapsis_rowid", legacy_value, "legacy empty-edge cutoff"),
        ),
    )
    connection.commit()
    connection.close()

    db = SQLiteMemoryBioRAG(str(path))
    try:
        assert db._search_baseline_rowid == memory_rowid > 0
        assert db._search_baseline_sinapsis_rowid == edge_rowid > 0
        assert db._search_baseline_fts_ready is True
        persisted = dict(db.cursor.execute(
            "SELECT clave, valor FROM data WHERE clave IN (?, ?)", _BASELINE_KEYS
        ).fetchall())
        assert persisted == {
            "search_baseline_rowid": str(memory_rowid),
            "search_baseline_sinapsis_rowid": str(edge_rowid),
        }

        results, _ = db.buscar_por_frase("manzana", limite=10)
        assert "manzana_despues" in [row[0] for row in results]
    finally:
        db.cerrar_sistema()
