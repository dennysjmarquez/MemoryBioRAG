"""Retención de backups propios sobre bases sintéticas y sin red."""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from core import database_backup as backups
from core import migrate


class BackupPolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.db=Path(self.tmp.name)/'memory.db'
        with sqlite3.connect(self.db) as db:
            db.execute('CREATE TABLE memories(value TEXT)')
            db.execute("INSERT INTO memories VALUES ('original')")

    def tearDown(self):self.tmp.cleanup()

    def test_success_retention_keeps_two_latest_and_protects_pending_failed(self):
        successful=[]
        for _ in range(4):
            path=backups.create_backup(self.db)
            backups.finish_backup(path,success=True);successful.append(path)
        pending=backups.create_backup(self.db)
        failed=backups.create_backup(self.db);backups.finish_backup(failed,success=False)
        report=backups.prune_successful(self.db)
        self.assertEqual(len(report['deleted']),2)
        self.assertEqual(report['protected'],2)
        self.assertTrue(all(Path(p).exists() for p in successful[-2:]+[pending,failed]))
        self.assertTrue(all(not Path(p).exists() for p in successful[:2]))

    def test_unknown_legacy_and_other_database_backups_are_untouched(self):
        folder=self.db.parent/'backups';folder.mkdir()
        legacy=folder/'legacy.db';legacy.write_bytes(b'keep')
        bad=folder/'memory.db.pre-migration-unknown.db';bad.write_bytes(b'keep')
        Path(str(bad)+'.json').write_text('[]')
        other=self.db.parent/'other.db'
        with sqlite3.connect(other) as db:db.execute('CREATE TABLE t(id)')
        other_backup=backups.create_backup(other);backups.finish_backup(other_backup,success=True)
        backups.prune_successful(self.db)
        self.assertTrue(all(p.exists() for p in (legacy,bad,Path(other_backup))))

    def test_backup_contains_wal_and_passes_integrity(self):
        db=sqlite3.connect(self.db)
        try:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute("INSERT INTO memories VALUES ('wal-committed')");db.commit()
            backup=backups.create_backup(self.db,purpose='update')
            self.assertEqual(backups.verify_database(backup)['quick_check'],'ok')
            with sqlite3.connect(backup) as copied:
                self.assertEqual(copied.execute('SELECT count(*) FROM memories').fetchone()[0],2)
        finally:db.close()

    def test_corruption_is_rejected(self):
        self.db.write_bytes(b'not sqlite')
        with self.assertRaises(sqlite3.DatabaseError):backups.verify_database(self.db)

    def test_foreign_key_violation_is_rejected(self):
        with sqlite3.connect(self.db) as db:
            db.executescript('CREATE TABLE parent(id INTEGER PRIMARY KEY); CREATE TABLE child(id REFERENCES parent(id)); INSERT INTO child VALUES(42);')
        with self.assertRaisesRegex(sqlite3.DatabaseError,'FOREIGN_KEY_CHECK_FAILED'):backups.verify_database(self.db)

    def test_no_zero_retention(self):
        with self.assertRaises(ValueError):backups.prune_successful(self.db,keep=0)

    def test_update_handoff_prevents_duplicate_migration_backup(self):
        from core.contextual.schema import ensure_contextual_schema
        backup=backups.create_backup(self.db,purpose='update')
        def initialize(path):
            with sqlite3.connect(path) as db:ensure_contextual_schema(db)
        with patch.object(migrate,'_initialize',side_effect=initialize):
            result=migrate.migrate(self.db,existing_backup=backup)
        self.assertEqual(result['backup'],backup)
        self.assertEqual(len(list((self.db.parent/'backups').glob('*.db'))),1)
        metadata=json.loads(Path(backup+'.json').read_text())
        self.assertEqual(metadata['status'],'pending')  # solo update completo lo finaliza
        self.assertIsNone(result['retention'])

    def test_handoff_cannot_use_backup_of_another_source(self):
        backup=backups.create_backup(self.db,purpose='update')
        with self.assertRaisesRegex(ValueError,'BACKUP_HANDOFF_INVALID'):
            backups.validate_update_backup(backup,self.db.parent/'other.db')

    def test_failure_keeps_backup_protected(self):
        with patch.object(migrate,'_initialize',side_effect=RuntimeError('injected')):
            with self.assertRaises(RuntimeError):migrate.migrate(self.db)
        metadata=json.loads(next((self.db.parent/'backups').glob('*.json')).read_text())
        self.assertEqual(metadata['status'],'failed')
        self.assertEqual(backups.prune_successful(self.db)['protected'],1)

    def test_cleanup_error_is_reported_without_deleting_retained_copies(self):
        for _ in range(3):
            path=backups.create_backup(self.db);backups.finish_backup(path,success=True)
        with patch.object(Path,'unlink',side_effect=PermissionError('locked')):
            report=backups.prune_successful(self.db)
        self.assertTrue(report['warnings'])
        self.assertEqual(len(list((self.db.parent/'backups').glob('*.db'))),3)


if __name__=='__main__':unittest.main()
