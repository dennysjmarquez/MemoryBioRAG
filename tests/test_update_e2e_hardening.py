"""End-to-end hardening tests for consecutive updates, pip quiet mode, and active MCP."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from core import updater


def _git(cwd: Path, *args: str) -> str:
    res = subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return res.stdout.strip()


class UpdateConsecutiveE2ETests(unittest.TestCase):
    def test_two_consecutive_updates_leave_git_status_clean(self):
        """Two consecutive apply() runs with real pip build in checkout must both succeed and leave git status clean."""
        repo_root = Path(__file__).resolve().parents[1]

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            tmp_path = Path(tmp)
            origin = tmp_path / "origin.git"
            work = tmp_path / "work"
            seed = tmp_path / "seed"
            db = tmp_path / "outside.db"
            pip_prefix = tmp_path / "pip_prefix"

            # Clone current repo HEAD into a local bare origin + work checkout
            subprocess.run(["git", "clone", "--bare", str(repo_root), str(origin)], check=True, capture_output=True)
            subprocess.run(["git", "clone", str(origin), str(work)], check=True, capture_output=True)
            _git(work, "config", "user.email", "test@example.com")
            _git(work, "config", "user.name", "Test")

            # Seed helper clone to push two consecutive commits to origin
            subprocess.run(["git", "clone", str(origin), str(seed)], check=True, capture_output=True)
            _git(seed, "config", "user.email", "test@example.com")
            _git(seed, "config", "user.name", "Test")

            def push_upstream_commit(filename: str, content: str, msg: str):
                (seed / filename).write_text(content, encoding="utf-8")
                _git(seed, "add", filename)
                _git(seed, "commit", "-m", msg)
                _git(seed, "push", "origin", "HEAD")

            # Runner that executes real setuptools/pip build inside `work` (into isolated prefix)
            # while delegating lifecycle to the real python subprocess.
            def isolated_runner(cmd, **kwargs):
                if len(cmd) >= 4 and cmd[1:4] == ["-m", "pip", "install"]:
                    pip_cmd = [
                        sys.executable, "-m", "pip", "install",
                        "--no-deps",
                        "--prefix", str(pip_prefix), ".",
                    ]
                    return subprocess.run(pip_cmd, **kwargs)
                return subprocess.run(cmd, **kwargs)

            # First upstream commit + update
            push_upstream_commit("CHANGELOG_E2E_1.txt", "v1\n", "chore: e2e commit 1")
            res1 = updater.apply(work, channel="dev", database=db, runner=isolated_runner, wait=5.0)
            self.assertEqual(res1["status"], "ok", f"First update failed: {res1}")
            dirty1 = _git(work, "status", "--porcelain")
            self.assertEqual(dirty1, "", f"Checkout dirty after first update:\n{dirty1}")

            # Second upstream commit + update (must NOT fail with LOCAL_CHANGES)
            push_upstream_commit("CHANGELOG_E2E_2.txt", "v2\n", "chore: e2e commit 2")
            res2 = updater.apply(work, channel="dev", database=db, runner=isolated_runner, wait=5.0)
            self.assertEqual(res2["status"], "ok", f"Second update failed: {res2}")
            dirty2 = _git(work, "status", "--porcelain")
            self.assertEqual(dirty2, "", f"Checkout dirty after second update:\n{dirty2}")

    def test_pip_install_is_quiet_by_default_and_surfaces_error_or_verbose(self):
        """_run_pip_install captures output when verbose=False, streams when verbose=True, and prints stderr on failure."""
        import io
        from contextlib import redirect_stderr
        calls = []

        def fake_runner(cmd, **kwargs):
            calls.append((cmd, kwargs))
            return subprocess.CompletedProcess(cmd, 0, stdout="pip noise\n", stderr="")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            updater._run_pip_install(root, fake_runner, verbose=False)
            self.assertTrue(calls[-1][1].get("capture_output"))
            self.assertTrue(calls[-1][1].get("text"))

            updater._run_pip_install(root, fake_runner, verbose=True)
            self.assertNotIn("capture_output", calls[-1][1])

            def failing_runner(cmd, **kwargs):
                raise subprocess.CalledProcessError(1, cmd, output="", stderr="pip boom\n")

            err_buf = io.StringIO()
            with redirect_stderr(err_buf):
                with self.assertRaises(subprocess.CalledProcessError):
                    updater._run_pip_install(root, failing_runner, verbose=False)
            self.assertIn("pip boom", err_buf.getvalue())


if __name__ == "__main__":
    unittest.main()
