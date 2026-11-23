"""Read-only update-state checks against tiny synthetic SQLite databases."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.schema_status import APPLIED_UPDATE_KEY, inspect_database
from core.lifecycle import prepare


SHA_A = "a" * 40
SHA_B = "b" * 40
CONTRACT = {
    "data": {"type": "table", "columns": ("clave", "valor", "descripcion")},
    "required_table": {"type": "table", "columns": ("id", "payload")},
}


class SchemaStatusTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "memory.db"
        with sqlite3.connect(self.path) as db:
            db.execute("CREATE TABLE data(clave TEXT PRIMARY KEY, valor TEXT, descripcion TEXT)")
            db.execute("CREATE TABLE required_table(id INTEGER PRIMARY KEY, payload TEXT)")
            db.execute("INSERT INTO data VALUES(?,?,?)", (APPLIED_UPDATE_KEY, SHA_A, "verified"))

    def tearDown(self):
        self.tmp.cleanup()

    def inspect(self, expected=SHA_A, contract=CONTRACT):
        return inspect_database(self.path, expected_update_id=expected, expected_objects=contract)

    def test_matching_update_id_and_schema_is_ready(self):
        result = self.inspect()
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["integrity_check"], "ok")
        self.assertEqual(result["applied_update_id"], SHA_A)

    def test_update_id_mismatch_is_not_reported_as_current(self):
        result = self.inspect(expected=SHA_B)
        self.assertEqual(result["status"], "prepared_for_different_update")
        self.assertEqual(result["applied_update_id"], SHA_A)

    def test_missing_required_table_is_detected_even_when_marker_matches(self):
        with sqlite3.connect(self.path) as db:
            db.execute("DROP TABLE required_table")
        result = self.inspect()
        self.assertEqual(result["status"], "schema_drift")
        self.assertIn("required_table", result["missing_objects"])
        self.assertEqual(result["applied_update_id"], SHA_A)

    def test_missing_required_column_is_detected(self):
        with sqlite3.connect(self.path) as db:
            db.execute("ALTER TABLE required_table RENAME TO old_table")
            db.execute("CREATE TABLE required_table(id INTEGER PRIMARY KEY)")
        result = self.inspect()
        self.assertEqual(result["status"], "schema_drift")
        self.assertEqual(result["missing_columns"], {"required_table": ["payload"]})

    def test_missing_marker_is_not_assumed_to_be_applied(self):
        with sqlite3.connect(self.path) as db:
            db.execute("DELETE FROM data WHERE clave=?", (APPLIED_UPDATE_KEY,))
        self.assertEqual(self.inspect()["status"], "update_id_not_recorded")

    def test_missing_database_is_not_created_by_check(self):
        missing = Path(self.tmp.name) / "does-not-exist.db"
        result = inspect_database(missing, expected_update_id=SHA_A, expected_objects=CONTRACT)
        self.assertEqual(result["status"], "not_initialized")
        self.assertFalse(missing.exists())

    def test_lifecycle_replaces_one_marker_row_after_success(self):
        with patch("core.schema_status.inspect_database", return_value={
            "status": "ready", "schema_check": "ok", "integrity_check": "ok",
            "foreign_key_check": "ok"
        }):
            result = prepare(self.path, steps=(), update_id=SHA_B)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["update_marker"]["value"], SHA_B)
        with sqlite3.connect(self.path) as db:
            rows = db.execute("SELECT clave,valor FROM data WHERE clave=?", (APPLIED_UPDATE_KEY,)).fetchall()
        self.assertEqual(rows, [(APPLIED_UPDATE_KEY, SHA_B)])

    def test_lifecycle_rejects_non_commit_version_values(self):
        with self.assertRaisesRegex(ValueError, "UPDATE_ID_INVALID"):
            prepare(self.path, steps=(), update_id="36.2")
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("SELECT valor FROM data WHERE clave=?", (APPLIED_UPDATE_KEY,)).fetchone()[0], SHA_A)

    def test_failed_lifecycle_step_does_not_advance_marker(self):
        from core.lifecycle import Step, PreparationError
        with self.assertRaises(PreparationError):
            prepare(self.path, steps=(Step("fail", lambda _context: {"status": "failed"}),), update_id=SHA_B)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("SELECT valor FROM data WHERE clave=?", (APPLIED_UPDATE_KEY,)).fetchone()[0], SHA_A)

    def test_failed_preverification_does_not_advance_marker(self):
        with patch("core.schema_status.inspect_database", return_value={
            "status": "schema_drift", "schema_check": "failed", "integrity_check": "ok"
        }):
            with self.assertRaisesRegex(RuntimeError, "LIFECYCLE_VERIFICATION_FAILED"):
                prepare(self.path, steps=(), update_id=SHA_B)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("SELECT valor FROM data WHERE clave=?", (APPLIED_UPDATE_KEY,)).fetchone()[0], SHA_A)

    def test_default_lifecycle_applies_and_marks_synthetic_database(self):
        database = Path(self.tmp.name) / "lifecycle.db"
        report = prepare(database, update_id=SHA_A)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["database_status"]["status"], "ready")
        checked = inspect_database(database, expected_update_id=SHA_A)
        self.assertEqual(checked["status"], "ready")
        with sqlite3.connect(database) as db:
            rows = db.execute("SELECT clave,valor FROM data WHERE clave=?", (APPLIED_UPDATE_KEY,)).fetchall()
        self.assertEqual(rows, [(APPLIED_UPDATE_KEY, SHA_A)])

    def test_real_core_initializer_schema_is_the_readonly_contract(self):
        from core.memory_store import SQLiteMemoryBioRAG
        from core.migrate import record_applied_update_id
        real_db = Path(self.tmp.name) / "real-core.db"
        memory = SQLiteMemoryBioRAG(str(real_db))
        memory.conn.close()
        record_applied_update_id(real_db, SHA_A)
        self.assertEqual(inspect_database(real_db, expected_update_id=SHA_A)["status"], "ready")
        with sqlite3.connect(real_db) as db:
            db.execute("DROP TABLE concept_hubs")
        result = inspect_database(real_db, expected_update_id=SHA_A)
        self.assertEqual(result["status"], "schema_drift")
        self.assertIn("concept_hubs", result["missing_objects"])


if __name__ == "__main__":
    unittest.main()
