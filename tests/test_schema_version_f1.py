"""Pruebas rigurosas para Fase F1: user_version, migración y restauración automática."""
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from core import migrate
from core.memory_store import SQLiteMemoryBioRAG
from core.schema_status import (
    CURRENT_SCHEMA_VERSION,
    SchemaVersionError,
    check_schema_version,
    inspect_database,
)


class SchemaVersionF1Tests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.db = self.root / "test_memory.db"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_legacy_database_user_version_zero_is_accepted(self):
        """user_version=0 es legado sin sello y debe operar con total normalidad."""
        conn = sqlite3.connect(str(self.db))
        conn.execute("PRAGMA user_version = 0")
        conn.close()

        # check_schema_version devuelve 0 sin lanzar excepción
        self.assertEqual(check_schema_version(self.db), 0)

        # SQLiteMemoryBioRAG abre la BD sin fallar
        mem = SQLiteMemoryBioRAG(str(self.db))
        self.assertIsNotNone(mem.conn)
        mem.conn.close()

    def test_database_newer_than_code_is_refused(self):
        """user_version > CURRENT_SCHEMA_VERSION debe ser rechazado con SCHEMA_NEWER_THAN_CODE."""
        conn = sqlite3.connect(str(self.db))
        conn.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION + 1}")
        conn.close()

        # En check_schema_version
        with self.assertRaisesRegex(SchemaVersionError, "SCHEMA_NEWER_THAN_CODE"):
            check_schema_version(self.db)

        # En apertura común SQLiteMemoryBioRAG
        with self.assertRaisesRegex(SchemaVersionError, "SCHEMA_NEWER_THAN_CODE"):
            SQLiteMemoryBioRAG(str(self.db))

        # En core.migrate
        with self.assertRaisesRegex(SchemaVersionError, "SCHEMA_NEWER_THAN_CODE"):
            migrate.migrate(self.db)

        # En inspect_database
        report = inspect_database(self.db)
        self.assertEqual(report["status"], "schema_newer_than_code")
        self.assertEqual(report["schema_version"], CURRENT_SCHEMA_VERSION + 1)

    def test_migrate_seals_user_version_on_success(self):
        """Una migración exitosa sella PRAGMA user_version con CURRENT_SCHEMA_VERSION."""
        report = migrate.migrate(self.db)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["schema_version"], CURRENT_SCHEMA_VERSION)

        conn = sqlite3.connect(str(self.db))
        ver = conn.execute("PRAGMA user_version").fetchone()[0]
        conn.close()
        self.assertEqual(ver, CURRENT_SCHEMA_VERSION)

    def test_migrate_failure_triggers_automatic_restore(self):
        """Fallo a mitad de migrate restaura automáticamente el estado anterior de la BD."""
        # 1. Crear una BD inicial con datos conocidos
        conn = sqlite3.connect(str(self.db))
        conn.execute("CREATE TABLE test_original_marker (id INT, valor TEXT)")
        conn.execute("INSERT INTO test_original_marker VALUES (42, 'preservar_esto')")
        conn.commit()
        conn.close()

        # 2. Inyectar fallo durante la inicialización de migrate
        with patch("core.migrate._initialize", side_effect=RuntimeError("INJECTED_MIGRATION_FAILURE")):
            with self.assertRaisesRegex(RuntimeError, "INJECTED_MIGRATION_FAILURE"):
                migrate.migrate(self.db)

        # 3. La base de datos viva DEBE haber sido restaurada automáticamente
        conn = sqlite3.connect(str(self.db))
        row = conn.execute("SELECT id, valor FROM test_original_marker").fetchone()
        conn.close()
        self.assertEqual(row, (42, 'preservar_esto'), "La base de datos viva no fue restaurada tras fallo en migrate")

    def test_external_lock_contention_fails_cleanly(self):
        """Si un proceso externo tiene una transacción abierta (BEGIN IMMEDIATE), migrate falla limpiamente."""
        migrate.migrate(self.db)

        # Abrir conexión externa con lock exclusivo
        ext_conn = sqlite3.connect(str(self.db), isolation_level=None, timeout=0.1)
        ext_conn.execute("BEGIN IMMEDIATE")
        try:
            # migrate en proceso con timeout bajo debe fallar por database is locked
            with patch.object(migrate, "_initialize", side_effect=sqlite3.OperationalError("database is locked")):
                with self.assertRaisesRegex(sqlite3.OperationalError, "database is locked"):
                    migrate.migrate(self.db)
        finally:
            ext_conn.execute("ROLLBACK")
            ext_conn.close()
