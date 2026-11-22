"""CLI real sobre fixture sintética: comparte evidencia/recibos con MCP/Python."""
import json
import os
from pathlib import Path
import sqlite3
import shlex
import subprocess
import sys
import tempfile
import unittest
from core.contextual.service import Corrections

ROOT = Path(__file__).resolve().parents[1]


class CorrectionsCLITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name)/'memory.db'
        with sqlite3.connect(self.db) as db:
            db.execute('CREATE TABLE largo_plazo(concepto TEXT PRIMARY KEY,contenido TEXT)')
            db.executemany('INSERT INTO largo_plazo VALUES (?,?)', [('old','old content'),('new','new content')])

    def tearDown(self):
        self.temp.cleanup()

    def call(self, *args, flag='1', installed=False):
        env = dict(os.environ, HOME=self.temp.name, BIORAG_PATH=str(self.db),
                   BIORAG_CORRECTIONS=flag, BIORAG_DAEMON_ENABLED='0', BIORAG_UPDATE_CHECK='0')
        command = ([sys.executable, '-c', 'from core.cli import main; raise SystemExit(main())']
                   if installed else [sys.executable, str(ROOT/'biorag.py')])
        return subprocess.run(command+['correcciones', *args], cwd=ROOT, env=env,
                              capture_output=True, text=True, timeout=15)

    def register(self, **options):
        args=['registrar','--id','p','--mensaje','設定を変更しました',
              '--nodo-anterior','old','--nodo-sucesor','new','--entidad','service',
              '--atributo','port','--ambito','prod','--valor-anterior','8080',
              '--valor-nuevo','8443','--observado-en','3','--efectivo-desde','2',
              '--anterior-desde','1']
        return self.call(*args, **options)

    def test_roundtrip_interoperability_idempotence_and_preservation(self):
        result=self.register(installed=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertFalse(json.loads(result.stdout)['confirmed'])
        reviewed=self.call('revisar','--id','p','--db',str(self.db))
        self.assertEqual(reviewed.returncode,0,reviewed.stderr)
        evidence=json.loads(reviewed.stdout)
        self.assertIsNone(evidence['evidence']['payload']['spans'])
        service=Corrections(self.db)
        try:self.assertEqual(service.review('p'),evidence)
        finally:service.close()
        args=('confirmar','--id','p','--digest',evidence['digest'],'--request-id','r')
        result=self.call(*args);repeat=self.call(*args)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout),json.loads(repeat.stdout))
        with sqlite3.connect(self.db) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM ctx_approvals').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT * FROM largo_plazo ORDER BY concepto').fetchall(),
                             [('new','new content'),('old','old content')])

    def test_disabled_and_missing_db_do_not_initialize(self):
        result=self.register(flag='0')
        self.assertEqual(result.returncode,1)
        self.assertEqual(json.loads(result.stderr)['error'],'PermissionError')
        with sqlite3.connect(self.db) as db:
            self.assertIsNone(db.execute("SELECT name FROM sqlite_master WHERE name='ctx_claims'").fetchone())
        missing=Path(self.temp.name)/'missing.db'
        result=self.call('revisar','--id','p','--db',str(missing))
        self.assertEqual(result.returncode,1)
        self.assertFalse(missing.exists())

    def test_validation_and_stale_digest_never_approve(self):
        self.assertEqual(self.register().returncode,0)
        result=self.call('confirmar','--id','p','--digest','incorrect','--request-id','r')
        self.assertEqual(result.returncode,1)
        self.assertIn('stale_proposal',json.loads(result.stderr)['message'])
        with sqlite3.connect(self.db) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM ctx_approvals').fetchone()[0],0)
        result=self.call('registrar','--id','incomplete')
        self.assertEqual(result.returncode,2)

    def test_published_examples_work_with_explicit_fixture_substitutions(self):
        from core.cli_notes import EXAMPLES
        digest = None
        for operation in ('registrar', 'revisar', 'confirmar'):
            command = EXAMPLES['correcciones '+operation][0].replace('\\\n', '')
            tokens = shlex.split(command)[2:]
            replacements = {'/path/test-copy.db': str(self.db),
                            'servicio_puerto_anterior': 'old', 'servicio_puerto_actual': 'new',
                            'REVIEW_DIGEST': digest}
            tokens = [replacements.get(token, token) for token in tokens]
            result = self.call(*tokens)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            if operation == 'revisar':
                digest = payload['digest']
            if operation == 'confirmar':
                self.assertEqual(payload['status'], 'approved')

    def test_help_without_db_and_all_subcommands(self):
        self.db.unlink()
        for args in ((),('--help',),('registrar','--help'),('revisar','--help'),('confirmar','--help')):
            result=self.call(*args)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('usage:',result.stdout)
        self.assertFalse(self.db.exists())


if __name__=='__main__':unittest.main()
