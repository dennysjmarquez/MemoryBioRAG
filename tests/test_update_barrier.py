import io
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

from core.update_barrier import activate, barrier_path, clear, runtime_status


class UpdateBarrierTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / 'memory.db'

    def tearDown(self):
        self.tmp.cleanup()

    def test_update_blocks_runtime_until_verified_clear(self):
        marker = activate(self.db, update_id='a' * 40, phase='lifecycle')
        self.assertEqual(marker, barrier_path(self.db))
        status = runtime_status(self.db)
        self.assertFalse(status['allowed'])
        self.assertEqual(status['status'], 'update_incomplete')
        self.assertEqual(status['update_id'], 'a' * 40)
        self.assertTrue(clear(self.db))
        self.assertEqual(runtime_status(self.db), {'allowed': True, 'status': 'ready'})

    def test_unknown_or_malformed_marker_is_never_deleted(self):
        marker = barrier_path(self.db)
        marker.write_text('{"format":"biorag.update-barrier.v1","phase":"lifecycle"}')
        with self.assertRaisesRegex(RuntimeError, 'UPDATE_BARRIER_INVALID'):
            clear(self.db)
        self.assertEqual(runtime_status(self.db)['status'], 'barrier_invalid')
        self.assertTrue(marker.exists())

    def test_mcp_refuses_start_while_update_barrier_is_set(self):
        activate(self.db, update_id='b' * 40, phase='dependencies')
        from core.mcp_server import server
        error = io.StringIO()
        with patch('core.paths.resolve_db_path', return_value=str(self.db)), \
             patch.object(server, '_build_server') as build, \
             redirect_stderr(error):
            result = server.main(['--sse'])
        self.assertEqual(result, 3)
        self.assertIn('startup blocked', error.getvalue())
        build.assert_not_called()


if __name__ == '__main__':
    unittest.main()
