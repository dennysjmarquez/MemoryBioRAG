"""Immutable FTS5 reference indexes for corpus-growth-stable ranking.

FTS5 BM25 is useful for preserving the ranker's established field weighting,
but its statistics change when unrelated rows are appended. These indexes are
built once from the corpus cutoff recorded in ``data``. Searches use them for
reference memories and retrieve newer memories separately from the live FTS
indexes as an overlay.

Initialization happens during schema setup, never by scanning the corpus inside
an ordinary query. The reference indexes have no synchronization triggers.
"""
from __future__ import annotations

import sqlite3

REFERENCE_FTS = "biorag_largo_plazo_fts_ref"
REFERENCE_UNICODE_FTS = "biorag_largo_plazo_fts_unicode_ref"
_REQUIRED_COLUMNS = ("concepto", "contenido", "sinonimos", "sustantivos_clave")
_REQUIRED_UNICODE_COLUMNS = ("concepto", "contenido", "sinonimos")


def _exists(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (name,),
    ).fetchone() is not None


def _has_columns(conn: sqlite3.Connection, name: str, required: tuple[str, ...]) -> bool:
    try:
        cols = {str(row[1]) for row in conn.execute(f"PRAGMA table_info({name})")}
        return set(required).issubset(cols)
    except sqlite3.Error:
        return False


def _crear_si_falta(
    conn: sqlite3.Connection,
    name: str,
    *,
    tokenizer: str,
    required: tuple[str, ...],
    columns_sql: str,
    select_sql: str,
    baseline_rowid: int,
) -> None:
    if _exists(conn, name):
        if _has_columns(conn, name, required):
            return
        conn.execute(f"DROP TABLE {name}")
    conn.execute(
        f"CREATE VIRTUAL TABLE {name} USING fts5({columns_sql}, tokenize='{tokenizer}')"
    )
    conn.execute(
        f"INSERT INTO {name} (rowid, {', '.join(required)}) "
        f"SELECT rowid, {select_sql} FROM largo_plazo WHERE rowid <= ?",
        (int(baseline_rowid),),
    )


def asegurar_indice_referencia(
    conn: sqlite3.Connection, baseline_rowid: int | None
) -> bool:
    """Ensure immutable trigram and unicode61 indexes exist for the baseline."""
    if baseline_rowid is None:
        return False

    savepoint = "biorag_growth_fts"
    try:
        source_cols = {
            str(row[1]) for row in conn.execute("PRAGMA table_info(largo_plazo)")
        }
        if not {"concepto", "contenido"}.issubset(source_cols):
            return False
        synonyms = "COALESCE(sinonimos, '')" if "sinonimos" in source_cols else "''"
        nouns = (
            "COALESCE(sustantivos_clave, '')"
            if "sustantivos_clave" in source_cols else "''"
        )

        conn.execute(f"SAVEPOINT {savepoint}")
        _crear_si_falta(
            conn,
            REFERENCE_FTS,
            tokenizer="trigram",
            required=_REQUIRED_COLUMNS,
            columns_sql="concepto, contenido, sinonimos, sustantivos_clave",
            select_sql=(
                "COALESCE(concepto, ''), COALESCE(contenido, ''), "
                f"{synonyms}, {nouns}"
            ),
            baseline_rowid=baseline_rowid,
        )
        _crear_si_falta(
            conn,
            REFERENCE_UNICODE_FTS,
            tokenizer="unicode61",
            required=_REQUIRED_UNICODE_COLUMNS,
            columns_sql="concepto, contenido, sinonimos",
            select_sql=(
                "COALESCE(concepto, ''), COALESCE(contenido, ''), "
                f"{synonyms}"
            ),
            baseline_rowid=baseline_rowid,
        )
        conn.execute(f"RELEASE SAVEPOINT {savepoint}")
        return True
    except sqlite3.Error:
        try:
            conn.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
            conn.execute(f"RELEASE SAVEPOINT {savepoint}")
        except sqlite3.Error:
            pass
        return False


def referencia_disponible(conn: sqlite3.Connection) -> bool:
    """Return whether both immutable reference indexes are present and queryable."""
    try:
        return (
            _exists(conn, REFERENCE_FTS)
            and _has_columns(conn, REFERENCE_FTS, _REQUIRED_COLUMNS)
            and _exists(conn, REFERENCE_UNICODE_FTS)
            and _has_columns(conn, REFERENCE_UNICODE_FTS, _REQUIRED_UNICODE_COLUMNS)
        )
    except sqlite3.Error:
        return False
