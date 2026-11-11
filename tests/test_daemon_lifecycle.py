"""Lifecycle con artifacts temporales; no lanza MCP ni el daemon de usuario."""

import multiprocessing
import os

import pytest

import core.daemon_lifecycle as lifecycle
from core.file_lock import FileLock, is_file_lock_held


def _child_hold_lock(path, acquired, release, outcome):
    lock = FileLock(path)
    locked = lock.acquire(blocking=False)
    outcome.put(locked)
    acquired.set()
    if locked:
        release.wait(5)
        lock.release()


@pytest.mark.skipif(os.name == "nt", reason="probe same-process no equivale al probe cross-process en Windows")
def test_file_lock_se_conserva_y_es_detectable(tmp_path):
    lock_path = tmp_path / "daemon.lock"
    lock = FileLock(lock_path)

    assert lock.acquire(blocking=False)
    try:
        assert is_file_lock_held(lock_path)
    finally:
        lock.release()
    assert lock_path.exists()
    assert not is_file_lock_held(lock_path)


def test_lock_de_proceso_distinto_es_detectable(tmp_path, monkeypatch):
    monkeypatch.setattr(lifecycle, "PROJECT_ROOT", str(tmp_path))
    db_path = tmp_path / "route-db.sqlite"
    lock_path = lifecycle.daemon_artifact_paths(db_path).lock_path
    context = multiprocessing.get_context("spawn")
    acquired = context.Event()
    release = context.Event()
    outcome = context.Queue()
    worker = context.Process(
        target=_child_hold_lock,
        args=(lock_path, acquired, release, outcome),
    )
    worker.start()
    try:
        assert acquired.wait(10)
        assert outcome.get(timeout=2) is True
        assert is_file_lock_held(lock_path)
        assert lifecycle.is_daemon_alive(db_path) is True
    finally:
        release.set()
        worker.join(10)
    assert not worker.is_alive()
    assert worker.exitcode == 0
    assert not is_file_lock_held(lock_path)
    assert lifecycle.is_daemon_alive(db_path) is False


def test_artifacts_del_daemon_varian_por_db_y_comparten_aliases(tmp_path, monkeypatch):
    monkeypatch.setattr(lifecycle, "PROJECT_ROOT", str(tmp_path))
    db_a = tmp_path / "data" / "a.db"
    db_b = tmp_path / "data" / "b.db"
    alias = tmp_path / "alias"
    try:
        alias.symlink_to(db_a.parent, target_is_directory=True)
    except (OSError, NotImplementedError):
        alias = None

    paths_a = lifecycle.daemon_artifact_paths(db_a)
    paths_b = lifecycle.daemon_artifact_paths(db_b)
    assert paths_a.pid_path != paths_b.pid_path
    assert paths_a.lock_path != paths_b.lock_path
    assert paths_a.spawn_lock_path != paths_b.spawn_lock_path
    assert paths_a.state_path != paths_b.state_path
    if alias is not None:
        assert lifecycle.daemon_artifact_paths(alias / "a.db") == paths_a
    assert not db_a.parent.exists()


def test_pid_reutilizado_sin_lock_del_daemon_no_es_alive(tmp_path, monkeypatch):
    monkeypatch.setattr(lifecycle, "PROJECT_ROOT", str(tmp_path))
    db_path = tmp_path / "memoria.db"
    paths = lifecycle.daemon_artifact_paths(db_path)
    os.makedirs(tmp_path, exist_ok=True)
    with open(paths.pid_path, "w", encoding="utf-8") as pid_file:
        pid_file.write(str(os.getpid()))
    monkeypatch.setattr(lifecycle, "_is_lock_held", lambda lock_path: False)

    assert lifecycle.is_daemon_alive(db_path) is False


def test_run_lock_route_specifico_confirma_daemon_aunque_pid_aun_no_exista(tmp_path, monkeypatch):
    monkeypatch.setattr(lifecycle, "PROJECT_ROOT", str(tmp_path))
    db_path = tmp_path / "memoria.db"
    paths = lifecycle.daemon_artifact_paths(db_path)
    monkeypatch.setattr(lifecycle, "_is_lock_held", lambda lock_path: lock_path == paths.lock_path)

    assert lifecycle.is_daemon_alive(db_path) is True


def test_legacy_daemon_ambiguo_impide_spawn_de_una_segunda_ruta(tmp_path, monkeypatch):
    monkeypatch.setattr(lifecycle, "PROJECT_ROOT", str(tmp_path))
    monkeypatch.setattr(lifecycle, "PID_PATH", str(tmp_path / ".hormiguita.pid"))
    monkeypatch.setattr(
        lifecycle, "LEGACY_RUN_LOCK_PATH", str(tmp_path / ".hormiguita.lock")
    )
    monkeypatch.setattr(
        lifecycle, "_is_lock_held",
        lambda path: path == lifecycle.LEGACY_RUN_LOCK_PATH,
    )
    monkeypatch.setattr(
        lifecycle, "spawn_daemon_detached",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("spawn no es seguro")),
    )

    assert lifecycle.ensure_daemon_alive(db_path=tmp_path / "otra.db") is False


def test_spawn_pasa_ruta_y_artifacts_canonicos_al_hijo(tmp_path, monkeypatch):
    monkeypatch.setattr(lifecycle, "PROJECT_ROOT", str(tmp_path))
    db_path = tmp_path / "data" / ".." / "memoria.db"
    expected_db = os.path.normcase(os.path.realpath(db_path))
    captured = {}

    class Process:
        pid = 456

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured["env"] = kwargs["env"]
        return Process()

    monkeypatch.setattr(lifecycle.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(lifecycle.time, "sleep", lambda _: None)
    monkeypatch.setattr(lifecycle, "is_daemon_alive", lambda path=None: path == expected_db)

    assert lifecycle.spawn_daemon_detached(db_path=db_path) is True
    env = captured["env"]
    assert env["BIORAG_PATH"] == expected_db
    assert env["BIORAG_DAEMON_PID_PATH"] == lifecycle.daemon_artifact_paths(db_path).pid_path
    assert env["BIORAG_DAEMON_LOCK_PATH"] == lifecycle.daemon_artifact_paths(db_path).lock_path
    assert env["BIORAG_DMN_ESTADO_PATH"] == lifecycle.daemon_artifact_paths(db_path).state_path
