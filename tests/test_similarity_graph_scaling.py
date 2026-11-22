"""Bounded associative-search regression tests.

These tests use disposable SQLite databases. They verify that latent retrieval
keeps its candidate pool fixed and that appended memories/edges cannot perturb
the frozen baseline graph or FTS seed cohort.
"""
from __future__ import annotations

import sqlite3

from core.memory.growth_stable_fts import REFERENCE_FTS
from core.similitud_conceptual import (
    _cargar_grafo,
    _obtener_candidatos_similitud,
    _tokenizar_query,
)


def _crear_db_fts(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE largo_plazo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            concepto TEXT UNIQUE NOT NULL,
            contenido TEXT NOT NULL,
            peso_sinaptico REAL DEFAULT 1.0,
            estado TEXT DEFAULT 'activo',
            asociaciones TEXT DEFAULT '',
            sinonimos TEXT DEFAULT '',
            sustantivos_clave TEXT DEFAULT ''
        );
        CREATE VIRTUAL TABLE largo_plazo_fts USING fts5(
            concepto, contenido, sinonimos, sustantivos_clave, tokenize='trigram'
        );
        CREATE VIRTUAL TABLE biorag_largo_plazo_fts_ref USING fts5(
            concepto, contenido, sinonimos, sustantivos_clave, tokenize='trigram'
        );
        CREATE TABLE sinapsis (
            origen TEXT NOT NULL,
            destino TEXT NOT NULL,
            peso REAL DEFAULT 0.5,
            PRIMARY KEY (origen, destino)
        );
        CREATE INDEX idx_sin_origen ON sinapsis(origen);
        CREATE INDEX idx_sin_destino ON sinapsis(destino);
        """
    )


def _insertar_memoria(conn: sqlite3.Connection, concepto: str, contenido: str) -> int:
    cursor = conn.execute(
        "INSERT INTO largo_plazo (concepto, contenido) VALUES (?, ?)",
        (concepto, contenido),
    )
    rowid = int(cursor.lastrowid)
    values = (rowid, concepto, contenido, "", "")
    conn.execute(
        "INSERT INTO largo_plazo_fts "
        "(rowid, concepto, contenido, sinonimos, sustantivos_clave) "
        "VALUES (?, ?, ?, ?, ?)",
        values,
    )
    return rowid


def test_grafo_lazy_ignora_aristas_nuevas_y_limita_hubs():
    conn = sqlite3.connect(":memory:")
    try:
        _crear_db_fts(conn)
        cursor = conn.cursor()
        for index in range(40):
            cursor.execute(
                "INSERT INTO sinapsis (origen, destino, peso) VALUES ('hub', ?, 0.7)",
                (f"base_{index:03d}",),
            )
        edge_cutoff = int(cursor.execute("SELECT MAX(rowid) FROM sinapsis").fetchone()[0])
        cursor.executemany(
            "INSERT INTO sinapsis (origen, destino, peso) VALUES ('hub', ?, 0.99)",
            ((f"ruido_{index:05d}",) for index in range(20_000)),
        )

        grafo = _cargar_grafo(cursor, rowid_max=edge_cutoff)
        assert grafo
        assert grafo.get("hub") == {f"base_{index:03d}" for index in range(40)}
        assert grafo.grado("hub") == 40
        assert grafo.get("desconectado", set()) == set()

        for sql, args in (
            (
                "SELECT destino FROM sinapsis WHERE origen = ? AND rowid <= ? "
                "ORDER BY rowid LIMIT ?",
                ("hub", edge_cutoff, 512),
            ),
            (
                "SELECT origen FROM sinapsis WHERE destino = ? AND rowid <= ? "
                "ORDER BY rowid LIMIT ?",
                ("base_000", edge_cutoff, 512),
            ),
        ):
            plan = " ".join(row[3] for row in cursor.execute("EXPLAIN QUERY PLAN " + sql, args))
            assert "SEARCH sinapsis USING INDEX" in plan
            assert "SCAN sinapsis" not in plan
    finally:
        conn.close()


def test_pool_latente_acotado_y_aislado_del_crecimiento():
    conn = sqlite3.connect(":memory:")
    try:
        _crear_db_fts(conn)
        cursor = conn.cursor()
        conceptos = []
        for index in range(120):
            concepto = f"baseline_{index:03d}"
            contenido = "Nota sobre parametros biorag y memoria asociativa."
            rowid = _insertar_memoria(conn, concepto, contenido)
            conn.execute(
                f"INSERT INTO {REFERENCE_FTS} "
                "(rowid, concepto, contenido, sinonimos, sustantivos_clave) "
                "VALUES (?, ?, ?, '', '')",
                (rowid, concepto, contenido),
            )
            conceptos.append(concepto)

        # El primer seed FTS tiene una pequeña rama semántica recuperable.
        conn.executemany(
            "INSERT INTO sinapsis (origen, destino, peso) VALUES (?, ?, ?)",
            ((conceptos[0], conceptos[index], 0.8) for index in range(90, 105)),
        )
        baseline_rowid = int(cursor.execute("SELECT MAX(rowid) FROM largo_plazo").fetchone()[0])
        edge_cutoff = int(cursor.execute("SELECT MAX(rowid) FROM sinapsis").fetchone()[0])
        query_tokens = _tokenizar_query("parametros biorag")

        before, bridges_before = _obtener_candidatos_similitud(
            cursor,
            query_tokens,
            baseline_rowid=baseline_rowid,
            edge_rowid_max=edge_cutoff,
            limite=100,
            incluir_puentes=True,
        )
        before_identity = [(row[0], row[1]) for row in before]
        assert 0 < len(before) <= 100
        assert len(bridges_before) <= 50

        # Añade recuerdos distractores que copian los términos y muchas aristas
        # salientes desde una semilla vieja. El cohorte de referencia debe seguir
        # entregando exactamente el mismo pool, sin leer esas aristas nuevas.
        for index in range(2_000):
            concepto = f"distractor_{index:05d}"
            rowid = _insertar_memoria(
                conn, concepto,
                "Inventario irrelevante: parametros biorag y organizacion de almacenes.",
            )
            conn.execute(
                "INSERT INTO sinapsis (origen, destino, peso) VALUES (?, ?, 0.99)",
                (conceptos[0], concepto),
            )
            assert rowid > baseline_rowid

        after, bridges_after = _obtener_candidatos_similitud(
            cursor,
            query_tokens,
            baseline_rowid=baseline_rowid,
            edge_rowid_max=edge_cutoff,
            limite=100,
            incluir_puentes=True,
        )
        assert [(row[0], row[1]) for row in after] == before_identity
        assert bridges_after == bridges_before
        assert len(after) <= 100

        plan = cursor.execute(
            "EXPLAIN QUERY PLAN SELECT destino FROM sinapsis "
            "WHERE origen = ? AND rowid <= ? ORDER BY rowid LIMIT ?",
            (conceptos[0], edge_cutoff, 512),
        ).fetchall()
        assert any("SEARCH sinapsis USING INDEX" in row[3] for row in plan)
        assert all("SCAN sinapsis" not in row[3] for row in plan)
    finally:
        conn.close()
