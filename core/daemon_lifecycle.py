"""Lifecycle del daemon de mantenimiento, asociado a la DB y a su lock vivo.

El PID se usa como dato auxiliar, no como prueba suficiente de vida: un PID
reutilizado solo se acepta si también está bloqueado el archivo advisory de
esa ruta de DB. No se terminan procesos ni se borran lock files automáticamente.
"""
from __future__ import annotations

import hashlib
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass

from core.file_lock import FileLock, is_file_lock_held
from core.paths import DEFAULT_DB, project_root, resolve_db_path

logger = logging.getLogger(__name__)

PROJECT_ROOT = project_root()
DAEMON_SCRIPT = os.path.join(PROJECT_ROOT, "graph_maintenance_daemon.py")
# Compatibilidad de importación para consumidores antiguos; las funciones usan
# daemon_artifact_paths(db_path), no estos paths globales para DB no-default.
PID_PATH = os.path.join(PROJECT_ROOT, ".hormiguita.pid")
LEGACY_RUN_LOCK_PATH = os.path.join(PROJECT_ROOT, ".hormiguita.lock")
LEGACY_STATE_PATH = os.path.join(PROJECT_ROOT, "estado_hormiga.json")


@dataclass(frozen=True)
class DaemonArtifactPaths:
    db_path: str
    pid_path: str
    lock_path: str
    spawn_lock_path: str
    state_path: str


def daemon_artifact_paths(db_path: str | os.PathLike[str] | None = None) -> DaemonArtifactPaths:
    """Rutas estables por DB canónica; conserva rutas legacy para DB default."""
    canonical_db = resolve_db_path(db_path)
    default_db = resolve_db_path(DEFAULT_DB)
    if canonical_db == default_db:
        return DaemonArtifactPaths(
            db_path=canonical_db,
            pid_path=PID_PATH,
            lock_path=LEGACY_RUN_LOCK_PATH,
            spawn_lock_path=os.path.join(PROJECT_ROOT, ".hormiguita.spawn.lock"),
            state_path=LEGACY_STATE_PATH,
        )

    key = hashlib.sha256(os.fsencode(canonical_db)).hexdigest()[:24]
    prefix = os.path.join(PROJECT_ROOT, f".hormiguita-{key}")
    return DaemonArtifactPaths(
        db_path=canonical_db,
        pid_path=prefix + ".pid",
        lock_path=prefix + ".lock",
        spawn_lock_path=prefix + ".spawn.lock",
        state_path=prefix + ".estado.json",
    )


def _leer_pid(db_path: str | os.PathLike[str] | None = None) -> int | None:
    try:
        with open(daemon_artifact_paths(db_path).pid_path, "r", encoding="utf-8") as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError, OSError):
        return None


def _escribir_pid(pid: int, db_path: str | os.PathLike[str] | None = None) -> None:
    path = daemon_artifact_paths(db_path).pid_path
    with open(path, "w", encoding="utf-8") as f:
        f.write(str(pid))


def _borrar_pid(db_path: str | os.PathLike[str] | None = None) -> None:
    try:
        os.remove(daemon_artifact_paths(db_path).pid_path)
    except FileNotFoundError:
        pass


def _is_lock_held(path: str) -> bool:
    return is_file_lock_held(path)


def is_daemon_alive(db_path: str | os.PathLike[str] | None = None) -> bool:
    """El run-lock por DB es la prueba de vida; el PID solo sirve para diagnóstico.

    Un PID reutilizado sin el lock correspondiente nunca se confunde con el
    daemon. Un lock tomado con PID aún ausente representa un arranque en curso.
    """
    paths = daemon_artifact_paths(db_path)
    return _is_lock_held(paths.lock_path)


def _legacy_daemon_might_be_running() -> bool:
    """Fail closed ante un daemon/spawn legacy cuya DB no quedó registrada."""
    return _is_lock_held(LEGACY_RUN_LOCK_PATH)


def spawn_daemon_detached(
    intervalo_horas: float | None = None,
    max_nodos: int | None = None,
    db_path: str | os.PathLike[str] | None = None,
) -> bool:
    """Lanza un daemon detachado con ruta y artifacts ya canonizados."""
    paths = daemon_artifact_paths(db_path)
    cmd = [sys.executable, DAEMON_SCRIPT]
    if intervalo_horas is not None:
        cmd.extend(["--intervalo", str(intervalo_horas)])
    if max_nodos is not None:
        cmd.extend(["--max-nodos", str(max_nodos)])

    env = os.environ.copy()
    env["BIORAG_PATH"] = paths.db_path
    env["BIORAG_DAEMON_SPAWNED_FROM_MCP"] = "1"
    env["BIORAG_DAEMON_PID_PATH"] = paths.pid_path
    env["BIORAG_DAEMON_LOCK_PATH"] = paths.lock_path
    env["BIORAG_DMN_ESTADO_PATH"] = paths.state_path

    try:
        if sys.platform == "win32":
            flags = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
            flags |= getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            proc = subprocess.Popen(
                cmd, creationflags=flags, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                env=env, cwd=PROJECT_ROOT,
            )
        else:
            proc = subprocess.Popen(
                cmd, start_new_session=True, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                env=env, cwd=PROJECT_ROOT,
            )

        logger.info("Daemon spawned (PID %d) para DB canónica", proc.pid)
        for _ in range(10):
            time.sleep(0.5)
            if is_daemon_alive(paths.db_path):
                return True
        logger.warning("Daemon spawned pero no confirmó el run-lock en 5s")
        return False
    except Exception as exc:
        logger.error("Failed to spawn daemon: %s", exc)
        return False


def ensure_daemon_alive(
    intervalo_horas: float | None = None,
    max_nodos: int | None = None,
    db_path: str | os.PathLike[str] | None = None,
) -> bool:
    """Asegura un daemon por DB usando un lock de spawn distinto al lock vivo."""
    paths = daemon_artifact_paths(db_path)
    if is_daemon_alive(paths.db_path):
        logger.info("Daemon ya vivo (PID %s)", _leer_pid(paths.db_path))
        return True

    default_db = resolve_db_path(DEFAULT_DB)
    if paths.db_path != default_db and _legacy_daemon_might_be_running():
        logger.error(
            "Hay un daemon legacy activo sin identidad de DB verificable; "
            "no se iniciará otro hasta que el operador lo revise y lo cierre ordenadamente."
        )
        return False

    spawn_lock = FileLock(paths.spawn_lock_path)
    try:
        acquired = spawn_lock.acquire(blocking=False)
    except OSError as exc:
        logger.warning("No se pudo adquirir el lock de spawn: %s", exc)
        return is_daemon_alive(paths.db_path)
    if not acquired:
        logger.info("Otra instancia gestiona el spawn del daemon para esta DB")
        time.sleep(1.0)
        return is_daemon_alive(paths.db_path)

    try:
        if is_daemon_alive(paths.db_path):
            return True
        return spawn_daemon_detached(
            intervalo_horas=intervalo_horas,
            max_nodos=max_nodos,
            db_path=paths.db_path,
        )
    finally:
        spawn_lock.release()
