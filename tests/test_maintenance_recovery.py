"""Bloqueo cooperativo y recuperación en copias; nunca sobrescribe DB viva."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from core.database_access import connect, maintenance, MaintenanceError, TOKEN_ENV
from core.database_backup import create_backup, backup_evidence
from core.recovery import plan, stage


@unittest.skipUnless(os.name=='posix','Backend de mantenimiento POSIX; Windows no certificado')
class MaintenanceRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'memory.db'
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE memories(value TEXT)');db.execute("INSERT INTO memories VALUES ('original')")

    def tearDown(self):self.tmp.cleanup()

    def test_open_managed_client_blocks_maintenance(self):
        db=connect(self.path)
        try:
            with self.assertRaises(MaintenanceError):
                with maintenance(self.path):pass
        finally:db.close()
        with maintenance(self.path):pass

    def test_other_process_rejected_but_authorized_child_can_migrate(self):
        script="from core.database_access import connect; import sys; db=connect(sys.argv[1]); db.execute('CREATE TABLE IF NOT EXISTS child_test(id)'); db.close()"
        with maintenance(self.path) as token:
            env=dict(os.environ);env.pop(TOKEN_ENV,None)
            blocked=subprocess.run([sys.executable,'-c',script,str(self.path)],env=env,capture_output=True,text=True)
            self.assertNotEqual(blocked.returncode,0)
            allowed=subprocess.run([sys.executable,'-c',script,str(self.path)],env=dict(env,**{TOKEN_ENV:token}),capture_output=True,text=True)
            self.assertEqual(allowed.returncode,0,allowed.stderr)
        db=connect(self.path);db.close()

    def test_exception_releases_maintenance_and_preserves_db(self):
        with self.assertRaises(RuntimeError):
            with maintenance(self.path):raise RuntimeError('injected')
        db=connect(self.path)
        try:self.assertEqual(db.execute('SELECT value FROM memories').fetchone()[0],'original')
        finally:db.close()

    def test_forced_process_exit_releases_os_lock_without_restoring_data(self):
        script="from core.database_access import maintenance; import os,sys; ctx=maintenance(sys.argv[1]); ctx.__enter__(); os._exit(71)"
        result=subprocess.run([sys.executable,'-c',script,str(self.path)],capture_output=True,text=True)
        self.assertEqual(result.returncode,71)
        with maintenance(self.path):pass
        db=connect(self.path)
        try:self.assertEqual(db.execute('SELECT value FROM memories').fetchone()[0],'original')
        finally:db.close()

    def test_new_memories_after_backup_are_preserved_by_recovery(self):
        backup=create_backup(self.path,purpose='update')
        evidence=backup_evidence(backup);self.assertTrue(evidence['restore_tested'])
        # Escenario de aceptación: no fingir que un lock cooperativo impidió una escritura externa.
        with sqlite3.connect(self.path) as db:db.execute("INSERT INTO memories VALUES ('new-after-backup')")
        receipt=self.path.parent/'receipt.json';receipt.write_text(json.dumps({'backup':backup,'status':'recovery_required'}))
        proposed=plan(receipt)
        self.assertFalse(proposed['current_matches_backup'])
        self.assertFalse(proposed['automatic_restore_allowed'])
        restored=stage(receipt)
        self.assertTrue(restored['live_database_unchanged'])
        for path in (self.path,Path(restored['current_snapshot'])):
            with sqlite3.connect(path) as db:self.assertEqual(db.execute('SELECT count(*) FROM memories').fetchone()[0],2)
        with sqlite3.connect(restored['restored_snapshot']) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM memories').fetchone()[0],1)
        # La memoria actual sigue utilizable y acepta nuevos recuerdos.
        db=connect(self.path)
        try:
            db.execute("INSERT INTO memories VALUES ('usable')");db.commit()
            self.assertEqual(db.execute('SELECT count(*) FROM memories').fetchone()[0],3)
        finally:db.close()

    def test_tampered_backup_blocks_recovery(self):
        backup=create_backup(self.path,purpose='update')
        with sqlite3.connect(backup) as db:db.execute("INSERT INTO memories VALUES ('tampered')")
        receipt=self.path.parent/'receipt.json';receipt.write_text(json.dumps({'backup':backup}))
        with self.assertRaisesRegex(ValueError,'CHECKSUM_MISMATCH'):stage(receipt)
        with sqlite3.connect(self.path) as db:self.assertEqual(db.execute('SELECT count(*) FROM memories').fetchone()[0],1)


if __name__=='__main__':unittest.main()
