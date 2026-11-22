"""Orquestación de instalación/migración sin paquetes externos ni DB viva."""
import ast
import importlib.util
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from core import migrate
from core.contextual.schema import ensure_contextual_schema


class InstallMigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'user'/'memory.db'

    def tearDown(self):self.tmp.cleanup()

    @staticmethod
    def synthetic_initializer(path):
        with sqlite3.connect(path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS largo_plazo(concepto TEXT,contenido TEXT)')
            ensure_contextual_schema(db)

    def test_new_db_and_repeated_upgrade(self):
        with patch.object(migrate,'_initialize',side_effect=self.synthetic_initializer):
            first=migrate.migrate(self.path)
            second=migrate.migrate(self.path)
        self.assertIsNone(first['backup'])
        self.assertEqual(second['status'],'ok')
        self.assertTrue(Path(second['backup']).is_file())

    def test_backup_includes_committed_wal_and_preserves_original(self):
        self.path.parent.mkdir()
        db=sqlite3.connect(self.path)
        try:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('CREATE TABLE largo_plazo(concepto TEXT,contenido TEXT)')
            db.execute("INSERT INTO largo_plazo VALUES ('n','original')");db.commit()
            with patch.object(migrate,'_initialize',side_effect=self.synthetic_initializer):
                result=migrate.migrate(self.path)
            with sqlite3.connect(result['backup']) as backup:
                self.assertEqual(backup.execute('SELECT contenido FROM largo_plazo').fetchone()[0],'original')
                self.assertFalse(backup.execute("SELECT 1 FROM sqlite_master WHERE name='ctx_claims'").fetchone())
            self.assertEqual(db.execute('SELECT contenido FROM largo_plazo').fetchone()[0],'original')
        finally:db.close()

    def test_failure_preserves_backup_and_is_not_reported_success(self):
        self.path.parent.mkdir()
        self.synthetic_initializer(self.path)
        with patch.object(migrate,'_initialize',side_effect=RuntimeError('injected')):
            with self.assertRaisesRegex(RuntimeError,'injected'):migrate.migrate(self.path)
        self.assertEqual(len(list((self.path.parent/'backups').glob('*.db'))),1)

    def test_verification_fails_if_initializer_did_not_create_tables(self):
        def incomplete(path):
            with sqlite3.connect(path) as db:db.execute('CREATE TABLE dummy(id INTEGER)')
        with patch.object(migrate,'_initialize',side_effect=incomplete):
            with self.assertRaisesRegex(sqlite3.DatabaseError,'MIGRATION_VERIFICATION_FAILED'):migrate.migrate(self.path)

    def test_installer_calls_migration_and_fails_closed(self):
        root=Path(__file__).resolve().parents[1]
        spec=importlib.util.spec_from_file_location('biorag_test_installer',root/'install.py')
        installer=importlib.util.module_from_spec(spec);spec.loader.exec_module(installer)
        with patch.object(installer,'_step'),patch.object(installer,'_ok'),patch.object(installer,'_fail'),patch.object(installer,'_info'):
            with patch.object(installer.subprocess,'run') as run:
                installer._initialize_database_schema()
                self.assertEqual(run.call_args.args[0][1:],['-m','core.lifecycle'])
                self.assertTrue(run.call_args.kwargs['check'])
            with patch.object(installer.subprocess,'run',side_effect=subprocess.CalledProcessError(1,'migration')):
                with self.assertRaises(SystemExit):installer._initialize_database_schema()
        tree=ast.parse((root/'install.py').read_text())
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='install')
        calls=[n.value.func.id for n in fn.body if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name)]
        self.assertLess(calls.index('_checkpoint2'),calls.index('_initialize_database_schema'))
        self.assertLess(calls.index('_initialize_database_schema'),calls.index('_verify_final'))


if __name__=='__main__':unittest.main()
