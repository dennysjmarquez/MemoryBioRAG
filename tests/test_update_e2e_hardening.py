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

    def test_update_with_active_mcp_server_drains_and_succeeds(self):
        """Real updater.apply() against an active stdio MCP server with continuous traffic drains via pending gate and succeeds."""
        import asyncio
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        repo_root = Path(__file__).resolve().parents[1]

        async def _run():
            with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
                tmp_path = Path(tmp)
                origin = tmp_path / "origin.git"
                work = tmp_path / "work"
                seed = tmp_path / "seed"
                db = tmp_path / "outside.db"
                pip_prefix = tmp_path / "pip_prefix"

                subprocess.run(["git", "clone", "--bare", str(repo_root), str(origin)], check=True, capture_output=True)
                subprocess.run(["git", "clone", str(origin), str(work)], check=True, capture_output=True)
                _git(work, "config", "user.email", "test@example.com")
                _git(work, "config", "user.name", "Test")

                subprocess.run(["git", "clone", str(origin), str(seed)], check=True, capture_output=True)
                _git(seed, "config", "user.email", "test@example.com")
                _git(seed, "config", "user.name", "Test")
                (seed / "CHANGELOG_ACTIVE_MCP.txt").write_text("active mcp\n", encoding="utf-8")
                _git(seed, "add", "CHANGELOG_ACTIVE_MCP.txt")
                _git(seed, "commit", "-m", "chore: active mcp update")
                _git(seed, "push", "origin", "HEAD")

                def isolated_runner(cmd, **kwargs):
                    if len(cmd) >= 4 and cmd[1:4] == ["-m", "pip", "install"]:
                        pip_cmd = [
                            sys.executable, "-m", "pip", "install",
                            "--no-deps", "--prefix", str(pip_prefix), ".",
                        ]
                        return subprocess.run(pip_cmd, **kwargs)
                    return subprocess.run(cmd, **kwargs)

                env = os.environ.copy()
                env["BIORAG_PATH"] = str(db)
                env["BIORAG_IDLE_TIMEOUT_SECONDS"] = "30"
                env["BIORAG_UPDATE_CHECK"] = "0"

                params = StdioServerParameters(
                    command=sys.executable,
                    args=[str(repo_root / "mcp_server.py")],
                    cwd=str(repo_root),
                    env=env,
                )

                async with stdio_client(params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        init_res = await session.call_tool("estado", {})
                        self.assertFalse(init_res.isError, f"Initial estado failed: {init_res.content}")

                        stop_traffic = asyncio.Event()
                        busy_seen = 0
                        unexpected_errors = []

                        async def traffic_loop():
                            nonlocal busy_seen
                            while not stop_traffic.is_set():
                                res = await session.call_tool("estado", {})
                                if res.isError:
                                    text = res.content[0].text if res.content else ""
                                    if "Output validation error" in text:
                                        unexpected_errors.append(text)
                                    elif "retry" in text.lower():
                                        busy_seen += 1
                                    else:
                                        unexpected_errors.append(text)
                                await asyncio.sleep(0.15)

                        traffic_task = asyncio.create_task(traffic_loop())
                        try:
                            await asyncio.sleep(0.3)
                            res = await asyncio.to_thread(
                                updater.apply,
                                work,
                                channel="dev",
                                database=db,
                                runner=isolated_runner,
                                wait=15.0,
                            )
                        finally:
                            stop_traffic.set()
                            await traffic_task

                        self.assertEqual(res["status"], "ok", f"Update failed: {res}")
                        self.assertEqual(unexpected_errors, [], f"Unexpected MCP errors: {unexpected_errors}")
                        self.assertGreater(busy_seen, 0, "Expected at least one readable retry response during update")

                        # First call after schema version bump triggers background reload; poll briefly until ready
                        post_res = None
                        for _ in range(30):
                            post_res = await session.call_tool("estado", {})
                            if not post_res.isError:
                                break
                            text = post_res.content[0].text if post_res.content else ""
                            self.assertIn("reloading", text.lower(), f"Unexpected post-update error: {text}")
                            await asyncio.sleep(0.5)
                        self.assertFalse(post_res.isError, f"Post-update estado failed: {post_res.content}")

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()
