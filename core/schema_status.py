"""Read-only check of the active BioRAG SQLite schema and applied build ID.

This module never initializes or repairs the inspected database. The expected
core schema is derived from the normal in-memory initializer, so the checker
covers the same baseline tables, columns, indexes, triggers, and views used by
the application without maintaining a second handwritten inventory.
"""
from __future__ import annotations

from contextlib import closing
from functools import lru_cache
import os
from pathlib import Path
import re
import sqlite3
from typing import Any

from core.database_access import connect_readonly

APPLIED_UPDATE_KEY = "biorag_applied_update_id"


def _is_fts_shadow(name: str) -> bool:
    return any(
        name.startswith(base + "_") and name[len(base) + 1:] in {
            "config", "content", "data", "docsize", "idx"
        }
        for base in ("largo_plazo_fts", "largo_plazo_fts_unicode")
    )


@lru_cache(maxsize=1)
def expected_core_schema() -> dict[str, dict[str, Any]]:
    """Build the core contract in isolated memory using the real initializer."""
    # This throwaway schema build must not trigger downloads, vector-index work,
    # or background synthesis because none of those affect the schema contract.
    env_keys = ("BIORAG_NLTK_AUTO_DOWNLOAD", "BIORAG_DMN_SINTESIS_ACTIVA", "BIORAG_PPMI_WEIGHT")
    old_env = {key: os.environ.get(key) for key in env_keys}
    os.environ.update({
        "BIORAG_NLTK_AUTO_DOWNLOAD": "0",
        "BIORAG_DMN_SINTESIS_ACTIVA": "0",
        "BIORAG_PPMI_WEIGHT": "0",
    })
    try:
        from core.memory_store import SQLiteMemoryBioRAG
        from core.memory import constants

        old_dmn, old_ppmi = constants.DMN_SINTESIS_ACTIVA, constants.PPMI_VECTOR_WEIGHT
        constants.DMN_SINTESIS_ACTIVA = False
        constants.PPMI_VECTOR_WEIGHT = 0.0
        try:
            memory = SQLiteMemoryBioRAG(":memory:")
            try:
                from core.contextual.schema import ensure_contextual_schema
                ensure_contextual_schema(memory.conn)
                objects: dict[str, dict[str, Any]] = {}
                rows = memory.conn.execute(
                    "SELECT type, name FROM sqlite_master "
                    "WHERE name NOT LIKE 'sqlite_%' AND type IN ('table','view','index','trigger') "
                    "ORDER BY type, name"
                ).fetchall()
                for object_type, name in rows:
                    columns: tuple[str, ...] = ()
                    if object_type in ("table", "view"):
                        columns = tuple(
                            row[1] for row in memory.conn.execute(
                                "PRAGMA table_info(\"" + name.replace('"', '""') + "\")"
                            )
                        )
                    objects[name] = {"type": object_type, "columns": columns}
                return objects
            finally:
                memory.conn.close()
        finally:
            constants.DMN_SINTESIS_ACTIVA, constants.PPMI_VECTOR_WEIGHT = old_dmn, old_ppmi
    finally:
        for key, value in old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def inspect_database(
    database: str | Path,
    *,
    expected_update_id: str | None = None,
    expected_objects: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Inspect schema without creating, migrating, or writing to *database*.

    ``expected_objects`` is injectable for lightweight isolated tests; normal
    callers use the contract generated from BioRAG's real memory initializer.
    """
    raw_path = str(database)
    if raw_path == ":memory:":
        return {"status": "not_persistent", "database": raw_path,
                "message": "A persistent database is required for update status."}
    path = Path(database).expanduser().resolve()
    result: dict[str, Any] = {
        "database": str(path),
        "status": "unknown",
        "applied_update_id": None,
        "expected_update_id": expected_update_id,
        "missing_objects": [],
        "missing_columns": {},
        "schema_check": "not_run",
        "integrity_check": "not_run",
        "foreign_key_check": "not_run",
    }
    if not path.exists():
        result.update(status="not_initialized", schema_check="not_run",
                      integrity_check="not_run", foreign_key_check="not_run")
        return result
    if not path.is_file():
        result.update(status="unreadable", error="DATABASE_PATH_NOT_FILE")
        return result

    try:
        with closing(connect_readonly(path, timeout=10)) as db:
            objects = expected_objects if expected_objects is not None else expected_core_schema()
            actual_rows = db.execute(
                "SELECT type, name FROM sqlite_master "
                "WHERE name NOT LIKE 'sqlite_%' AND type IN ('table','view','index','trigger')"
            ).fetchall()
            actual = {name: object_type for object_type, name in actual_rows}
            missing = sorted(name for name in objects if name not in actual
                             or actual[name] != objects[name]["type"])
            missing_columns: dict[str, list[str]] = {}
            for name, contract in objects.items():
                if name in missing or contract["type"] not in ("table", "view"):
                    continue
                if _is_fts_shadow(name):
                    continue  # SQLite may vary virtual-table shadow columns by version.
                escaped = name.replace('"', '""')
                columns = {row[1] for row in db.execute(f'PRAGMA table_info("{escaped}")')}
                absent = sorted(set(contract["columns"]) - columns)
                if absent:
                    missing_columns[name] = absent

            marker = None
            if actual.get("data") == "table":
                data_columns = {row[1] for row in db.execute('PRAGMA table_info("data")')}
                if {'clave', 'valor'} <= data_columns:
                    row = db.execute(
                        "SELECT valor FROM data WHERE clave=?", (APPLIED_UPDATE_KEY,)
                    ).fetchone()
                    if row and isinstance(row[0], str):
                        marker = row[0]
            integrity = db.execute("PRAGMA quick_check").fetchall()
            result["integrity_check"] = "ok" if integrity == [("ok",)] else "failed"
            result["foreign_key_check"] = (
                "failed" if db.execute("PRAGMA foreign_key_check").fetchone() is not None else "ok"
            )
            result.update(
                applied_update_id=marker,
                missing_objects=missing,
                missing_columns=missing_columns,
                schema_check="ok" if not missing and not missing_columns else "failed",
            )
            if result["integrity_check"] != "ok" or result["foreign_key_check"] != "ok":
                result["status"] = "database_integrity_failed"
            elif missing or missing_columns:
                result["status"] = "schema_drift"
            elif marker is None:
                result["status"] = "update_id_not_recorded"
            elif expected_update_id is not None and marker != expected_update_id:
                result["status"] = "prepared_for_different_update"
            else:
                result["status"] = "ready"
    except Exception as exc:
        result.update(status="check_failed", error=f"{type(exc).__name__}: {exc}")
    return result


def valid_update_id(value: str) -> bool:
    """Current Git updater IDs are full SHA-1 or SHA-256 commit identifiers."""
    return isinstance(value, str) and re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", value) is not None
