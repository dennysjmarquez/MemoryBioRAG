"""Pruebas stdlib sobre DBs sintéticas: sin dependencias NLP ni DB viva."""
import ast
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from core.contextual.schema import COLUMNS, DDL, ensure_contextual_schema
from core.contextual.service import Corrections
from core.contextual.search import reorder


class SchemaLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name)/'test.db'

    def tearDown(self):
        self.tmp.cleanup()

    def connect(self, mode='DELETE'):
        db = sqlite3.connect(self.path, timeout=10)
        db.execute('PRAGMA journal_mode='+mode)
        return db

    def assert_schema(self, db):
        for name, columns in COLUMNS.items():
            self.assertEqual(tuple(r[1] for r in db.execute('PRAGMA table_info('+name+')')), columns)
        self.assertTrue(db.execute("SELECT 1 FROM sqlite_master WHERE name='ctx_claims_context'").fetchone())

    def test_new_and_reopen_both_journals_flags_off(self):
        for mode in ('WAL','DELETE'):
            with self.subTest(mode=mode), patch.dict(os.environ, {'BIORAG_CORRECTIONS':'0','BIORAG_TEMPORAL_PROTOTYPE':'0'}):
                with self.connect(mode) as db:
                    ensure_contextual_schema(db)
                    ensure_contextual_schema(db)
                    self.assert_schema(db)
                    self.assertEqual(db.execute('SELECT count(*) FROM ctx_claims').fetchone()[0],0)
                    self.assertEqual(db.execute('PRAGMA journal_mode').fetchone()[0].upper(),mode)
                db.close()
                with sqlite3.connect(self.path) as reopened:
                    self.assert_schema(reopened)
                reopened.close()

    def test_existing_partial_database_preserves_content(self):
        with self.connect() as db:
            db.execute('CREATE TABLE largo_plazo(concepto TEXT,contenido TEXT)')
            db.execute("INSERT INTO largo_plazo VALUES ('recuerdo','original')")
            db.execute(DDL[0])
            db.execute("INSERT INTO ctx_claims VALUES ('c','n','e','a','s','v','source',1,NULL,1)")
            ensure_contextual_schema(db)
            self.assert_schema(db)
            self.assertEqual(db.execute('SELECT contenido FROM largo_plazo').fetchone()[0],'original')
            self.assertEqual(db.execute('SELECT id FROM ctx_claims').fetchone()[0],'c')

    def test_outer_rollback_not_committed_by_migration(self):
        with self.connect() as db:
            db.execute('CREATE TABLE sentinel(value TEXT)')
            db.execute("INSERT INTO sentinel VALUES ('pending')")
            ensure_contextual_schema(db)
            self.assertTrue(db.in_transaction)
            db.rollback()
            self.assertEqual(db.execute('SELECT count(*) FROM sentinel').fetchone()[0],0)
            self.assertFalse(db.execute("SELECT 1 FROM sqlite_master WHERE name='ctx_claims'").fetchone())

    def test_incompatible_table_rejected_without_changes(self):
        with self.connect() as db:
            db.execute('CREATE TABLE ctx_claims(unexpected TEXT)')
            before=db.execute('SELECT name,sql FROM sqlite_master ORDER BY name').fetchall()
            with self.assertRaisesRegex(sqlite3.DatabaseError,'CONTEXTUAL_SCHEMA_INCOMPATIBLE'):
                ensure_contextual_schema(db)
            self.assertEqual(before,db.execute('SELECT name,sql FROM sqlite_master ORDER BY name').fetchall())

    def test_ddl_failure_rolls_back_all_contextual_objects(self):
        with self.connect() as db:
            def authorizer(action,name,*rest):
                if action==sqlite3.SQLITE_CREATE_TABLE and name=='ctx_approvals':
                    return sqlite3.SQLITE_DENY
                return sqlite3.SQLITE_OK
            db.set_authorizer(authorizer)
            with self.assertRaises(sqlite3.DatabaseError):ensure_contextual_schema(db)
            db.set_authorizer(None)
            self.assertFalse(db.execute("SELECT name FROM sqlite_master WHERE name LIKE 'ctx_%'").fetchall())

    def test_readonly_database_explicit_failure_without_mutation(self):
        with self.connect() as db:db.execute('CREATE TABLE largo_plazo(concepto TEXT)')
        db=sqlite3.connect(self.path.as_uri()+'?mode=ro',uri=True)
        try:
            with self.assertRaises(sqlite3.OperationalError):ensure_contextual_schema(db)
            self.assertFalse(db.execute("SELECT name FROM sqlite_master WHERE name LIKE 'ctx_%'").fetchall())
        finally:db.close()

    def test_concurrent_initializers(self):
        for mode in ('WAL','DELETE'):
            with self.subTest(mode=mode):
                self.connect(mode).close()
                def run(_):
                    db=sqlite3.connect(self.path,timeout=10)
                    try:ensure_contextual_schema(db)
                    finally:db.close()
                with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(run,range(3)))
                with sqlite3.connect(self.path) as db:self.assert_schema(db)
                db.close()

    def test_service_and_initializer_share_schema(self):
        with self.connect() as db:db.execute('CREATE TABLE largo_plazo(concepto TEXT,contenido TEXT)')
        service=Corrections(self.path)
        try:
            self.assert_schema(service.db)
            ensure_contextual_schema(service.db)
        finally:service.close()

    def test_search_does_not_migrate(self):
        with self.connect() as db:
            rows=[('n','text',0,None,.5)]
            result,info=reorder(db,rows,dict(entity='e',attribute='a',scope='s',at=1))
            self.assertEqual(result,rows)
            self.assertEqual(info['status'],'unknown')
            self.assertFalse(db.execute("SELECT name FROM sqlite_master WHERE name LIKE 'ctx_%'").fetchall())

    def test_both_core_initialization_paths_have_unconditional_hook(self):
        tree=ast.parse((Path(__file__).resolve().parents[1]/'core/memory/schema.py').read_text())
        for name in ('_crear_estructura_cerebral','_crear_tablas_nuevas_si_faltan'):
            fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
            self.assertTrue(any(isinstance(n,ast.Expr) and isinstance(n.value,ast.Call)
                                and isinstance(n.value.func,ast.Name) and n.value.func.id=='ensure_contextual_schema'
                                for n in fn.body),name)


if __name__=='__main__':unittest.main()
