"""Subprocess supervisor tests: synthetic SQLite :memory: only."""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.authorizer_supervisor import (
    database_class,
    persist_event_exclusive,
    safe_call_frames,
    supervise_subprocess,
)


def _synthetic_child(event_fd: int, worker_event_path: str, mode: str) -> None:
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE synthetic_rows(value INTEGER)")
    sent = False

    def auth(action, arg1, arg2, database, source):
        nonlocal sent
        if action == sqlite3.SQLITE_INSERT and not sent:
            sent = True
            event = {
                "phase": "synthetic_search",
                "action": "SQLITE_INSERT",
                "database": database_class(database),
                "frames": safe_call_frames(),
            }
            if mode == "communication_failure":
                # Model IPC loss only after the worker has durably recorded the
                # first event, so the parent can test its recovery path.
                persist_event_exclusive(event, worker_event_path)
                os.close(event_fd)
            from scripts.authorizer_supervisor import notify_first_event
            notify_first_event(event_fd, event, worker_event_path)
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    con.set_authorizer(auth)
    try:
        con.execute("INSERT INTO synthetic_rows VALUES (1)")
    except sqlite3.DatabaseError:
        pass  # emulate code that catches a denied SQLite action
    time.sleep(30)  # parent must stop this worker before it can be accepted


def _run_batch(root: Path, modes: list[str]):
    started = []
    outcomes = []
    for mode in modes:
        started.append(mode)
        event_r, event_w = os.pipe()
        worker_path = root / (f"missing-worker/{mode}.json" if mode == "event_save_failure"
                              else f"worker-{mode}.json")
        primary_path = root / (f"missing-supervisor/{mode}.json" if mode == "event_save_failure"
                               else f"supervisor-{mode}.json")
        fallback_path = root / f"fallback-{mode}.json"
        argv = [sys.executable, __file__, "--synthetic-worker", str(event_w),
                str(worker_path), mode]
        proc = subprocess.Popen(
            argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, pass_fds=(event_w,), close_fds=True,
        )
        os.close(event_w)
        try:
            outcome = supervise_subprocess(
                proc, event_r, worker_path, primary_path, fallback_path,
                timeout=5.0, grace=0.5,
            )
        finally:
            os.close(event_r)
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=0.5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=0.5)
        outcomes.append(outcome)
        if outcome["status"] != "worker_exit" or outcome["returncode"] != 0:
            break
    return started, outcomes


class SubprocessSupervisorSyntheticTests(unittest.TestCase):
    def test_normal_guard_event_stops_worker_before_next(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            os.chmod(root, 0o700)
            started, outcomes = _run_batch(root, ["normal", "must_not_start"])
            result = outcomes[0]
            self.assertEqual(started, ["normal"])
            self.assertEqual(result["status"], "guard_event")
            self.assertTrue(result["worker_stopped"])
            self.assertEqual(result["event_saved_to"], "primary")
            event = json.loads((root / "supervisor-normal.json").read_text())
            self.assertEqual(event["action"], "SQLITE_INSERT")
            self.assertTrue(event["frames"])
            self.assertFalse(set(event) & {"sql", "arg1", "arg2", "query", "values", "locals"})
            print({"probe": "subprocess guard event", "workers_started": 1,
                   "next_worker_started": False, "event_saved": True,
                   "worker_stopped": True, "instant_interruption_claimed": False})

    def test_ipc_failure_recovers_worker_event_and_stops_before_next(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            os.chmod(root, 0o700)
            started, outcomes = _run_batch(root, ["communication_failure", "must_not_start"])
            result = outcomes[0]
            self.assertEqual(started, ["communication_failure"])
            self.assertEqual(result["status"], "worker_channel_failure")
            self.assertTrue(result["worker_stopped"])
            self.assertTrue((root / "worker-communication_failure.json").exists())
            self.assertTrue((root / "supervisor-communication_failure.json").exists())
            print({"probe": "subprocess IPC failure", "workers_started": 1,
                   "next_worker_started": False, "worker_event_recovered": True,
                   "worker_stopped": True, "instant_interruption_claimed": False})

    def test_event_save_failure_uses_fallback_and_stops_before_next(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            os.chmod(root, 0o700)
            started, outcomes = _run_batch(root, ["event_save_failure", "must_not_start"])
            result = outcomes[0]
            self.assertEqual(started, ["event_save_failure"])
            self.assertEqual(result["status"], "guard_event")
            self.assertEqual(result["event_saved_to"], "fallback")
            self.assertTrue(result["worker_stopped"])
            self.assertTrue((root / "fallback-event_save_failure.json").exists())
            print({"probe": "subprocess event-save failure", "workers_started": 1,
                   "next_worker_started": False, "fallback_event_saved": True,
                   "worker_stopped": True, "instant_interruption_claimed": False})


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "--synthetic-worker":
        _synthetic_child(int(sys.argv[2]), sys.argv[3], sys.argv[4])
        raise SystemExit(0)
    unittest.main(verbosity=2)
