"""Época de commit compartida entre procesos.

Qué problema resuelve: varios procesos (motor, daemon, MCP, dashboard) escriben
la misma base. Cada uno necesita saber si otro publicó un commit desde su última
lectura, sin abrir SQLite para averiguarlo.

Por qué está aquí y no en otro sitio: mantiene un sello auxiliar en disco
(`<base>.biorag-commit-epoch`) protegido por un lock entre procesos. Es
autocontenido: no depende de la política de apertura.

Quién lo usa: `tracking` (ventana de commit) y `opening` (identidad de ruta).

Medida con la que se aprobó: `tests/test_sqlite_runtime.py` y las pruebas de
generación, que verifican que un commit de otro proceso se detecta.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from core.paths import resolve_db_path
from core.sqlite.config import (
    _is_memory_database,
    logger,
)

def _database_route_id(database: str | Path) -> str:
    """Huella estable de la ruta efectiva; evita revelar rutas en logs normales."""
    try:
        value = resolve_db_path(database)
    except (TypeError, ValueError, OSError):
        value = os.fsdecode(os.fspath(database))
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()[:12]

_COMMIT_EPOCH_LOCK = threading.RLock()
_COMMIT_EPOCHS: dict[str, int] = {}

def _shared_epoch_paths(database: str | Path) -> tuple[str, str] | None:
    """Return per-database marker and lock paths (None for non-file databases)."""
    value = os.fsdecode(os.fspath(database))
    if _is_memory_database(value) or value.startswith("file:"):
        return None
    try:
        canonical = resolve_db_path(database)
    except (TypeError, ValueError, OSError):
        canonical = os.path.abspath(os.path.expanduser(value))
    marker = canonical + ".biorag-commit-epoch"
    return marker, marker + ".lock"

_EPOCH_LOCK_HELD = threading.local()

def _epoch_lock_held(lock_path: str) -> bool:
    """Consumers and the runtime re-enter the same lock; flock would deadlock."""
    held = getattr(_EPOCH_LOCK_HELD, "paths", None)
    return bool(held) and os.path.abspath(lock_path) in held

@contextmanager
def _shared_epoch_guard(lock_path: str, *, exclusive: bool):
    """Cross-process lock for the tiny commit epoch sidecar protocol."""
    local_key = os.path.abspath(lock_path)
    if _epoch_lock_held(local_key):
        # Already owned by this thread (database_read_window + commit_state, or
        # an exclusive publication that re-reads its own state). Re-locking the
        # same file through a second descriptor would block forever, and on
        # Windows a second msvcrt.locking on our own byte raises OSError.
        yield
        return
    with _COMMIT_EPOCH_LOCK:
        try:
            os.makedirs(os.path.dirname(local_key) or ".", exist_ok=True)
        except OSError:
            # El sello de época es auxiliar; sin permiso de escritura se sigue
            # sin él en lugar de impedir toda la operación.
            yield
            return
        held = getattr(_EPOCH_LOCK_HELD, "paths", None)
        if held is None:
            held = set()
            _EPOCH_LOCK_HELD.paths = held
        with open(local_key, "a+b") as lock_file:
            if os.name == "nt":
                import msvcrt
                lock_file.seek(0)
                if not os.path.getsize(local_key):
                    lock_file.write(b"0")
                    lock_file.flush()
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
                held.add(local_key)
                try:
                    yield
                finally:
                    held.discard(local_key)
                    lock_file.seek(0)
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(
                    lock_file.fileno(),
                    fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH,
                )
                held.add(local_key)
                try:
                    yield
                finally:
                    held.discard(local_key)
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

def _database_file_signature(database: str | Path) -> tuple[Any, ...] | None:
    """Firma barata del archivo principal: cabecera, tamaño y cambio del WAL. Sirve para detectar que otro proceso escribió sin leer la base entera."""
    value = os.fsdecode(os.fspath(database))
    if _is_memory_database(value) or value.startswith("file:"):
        return None
    canonical = resolve_db_path(database)
    st = os.stat(canonical)
    with open(canonical, "rb") as database_file:
        header = database_file.read(100)
    if len(header) != 100 or not header.startswith(b"SQLite format 3\x00"):
        # A brand-new WAL database can have all committed pages in -wal until
        # the first checkpoint. Its generation guard is not ready yet; publish
        # the epoch without a main-file attestation and let later commits attach
        # a full signature. A live guard still fails closed on an invalid header.
        return None
    # The -wal *contents* belong in the signature: in WAL mode a commit barely
    # touches the main file, so leaving the WAL out let a coordinated commit
    # followed by a raw one match the attested signature and be accepted. The
    # digest is normalized so a passive/truncate checkpoint is not a false
    # change, and file stat data is still excluded because mtime/ctime move on
    # any write, checkpoints included.
    return (
        int(st.st_size),
        int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1_000_000_000))),
        int(getattr(st, "st_ctime_ns", int(st.st_ctime * 1_000_000_000))),
        int.from_bytes(header[24:28], "big"),
        int.from_bytes(header[40:44], "big"),
        header,
        _wal_content_signature(canonical),
    )

def _wal_content_signature(canonical: str) -> tuple[int, str] | None:
    """Full content digest of the WAL, stable across checkpoints.

    Sampling the head and tail is not enough: after a checkpoint SQLite keeps the
    WAL at a fixed size and later commits reuse frames *inside* the already valid
    area, so size plus edge samples can stay byte-identical while a new commit is
    present (docs/auditoria_pr13_reuso_wal_68e4151.md). Only the whole content
    distinguishes that case.

    An absent or empty WAL is normalized to ``None`` so a checkpoint performed by
    a cooperative writer reads as the same state it published, and a torn read
    (a raw writer appending without the coordination lock) produces an unexpected
    digest, which fails closed rather than open.

    This is an integrity signal, not a cryptographic commitment: whoever can
    write the WAL can also rewrite the marker. It detects uncoordinated commits
    and in-place replacement, which is the contract of this guard.
    """
    wal_path = canonical + "-wal"
    try:
        st = os.stat(wal_path)
    except FileNotFoundError:
        return None
    size = int(st.st_size)
    if size == 0:
        return None
    digest = hashlib.sha256()
    try:
        with open(wal_path, "rb") as wal:
            for chunk in iter(lambda: wal.read(1 << 20), b""):
                digest.update(chunk)
    except FileNotFoundError:
        # A checkpoint truncated it between stat and read: same as empty.
        return None
    return size, digest.hexdigest()

def _read_shared_state(marker_path: str) -> tuple[int, tuple[Any, ...] | None]:
    """Lee el sello de época del disco: número de época y firma del archivo. Devuelve (0, None) si no hay sello."""
    try:
        with open(marker_path, "r", encoding="ascii") as marker:
            raw = marker.read().strip()
    except FileNotFoundError:
        return 0, None
    try:
        state = json.loads(raw)
        epoch = int(state["epoch"])
        signature_json = state.get("signature")
        signature = None
        if signature_json is not None:
            signature = tuple(signature_json)
            if len(signature) != 7 or not isinstance(signature[5], str):
                raise ValueError("firma atestiguada inválida")
            wal_digest = signature[6]
            if wal_digest is not None:
                wal_digest = (int(wal_digest[0]), str(wal_digest[1]))
            signature = (
                signature[:5] + (bytes.fromhex(signature[5]),) + (wal_digest,)
            )
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise sqlite3.OperationalError(
            "El marcador compartido de commits SQLite está dañado; "
            "se rechazó el acceso por seguridad."
        ) from exc
    if epoch < 0:
        raise sqlite3.OperationalError(
            "El marcador compartido de commits SQLite es inválido; "
            "se rechazó el acceso por seguridad."
        )
    return epoch, signature

def database_commit_state(database: str | Path) -> tuple[int, tuple[Any, ...] | None]:
    """Atomically read the shared commit epoch and the file state it attests."""
    paths = _shared_epoch_paths(database)
    if paths is None:
        key = _database_route_id(database)
        with _COMMIT_EPOCH_LOCK:
            return _COMMIT_EPOCHS.get(key, 0), None
    marker_path, lock_path = paths
    with _shared_epoch_guard(lock_path, exclusive=False):
        return _read_shared_state(marker_path)

def database_commit_epoch(database: str | Path) -> int:
    """Return the current process-shared commit sequence."""
    return database_commit_state(database)[0]

def _bump_memory_epoch(database: str | Path) -> int:
    """Incrementa la época solo en memoria, para bases en memoria que no tienen sello en disco."""
    key = _database_route_id(database)
    with _COMMIT_EPOCH_LOCK:
        epoch = _COMMIT_EPOCHS.get(key, 0) + 1
        _COMMIT_EPOCHS[key] = epoch
        return epoch

def _publish_state_locked(marker_path: str, database: str | Path) -> int:
    """Write the next epoch and the file state it attests. Caller holds the lock."""
    epoch = _read_shared_state(marker_path)[0] + 1
    signature = _database_file_signature(database)
    signature_json = None if signature is None else list(signature)
    if signature_json is not None:
        signature_json[5] = signature[5].hex()  # raw header bytes are not JSON
        if signature_json[6] is not None:
            signature_json[6] = list(signature_json[6])
    state = json.dumps(
        {"epoch": epoch, "signature": signature_json},
        separators=(",", ":"),
    )
    directory = os.path.dirname(marker_path) or "."
    try:
        fd, temporary = tempfile.mkstemp(prefix=".biorag-epoch-", dir=directory)
    except OSError:
        # Sin permiso de escritura junto a la base: el sello es auxiliar. Se
        # continúa sin él en lugar de impedir la escritura.
        logger.warning(
            "No se pudo publicar el sello de época (directorio sin escritura); "
            "se continúa sin él"
        )
        return epoch
    try:
        with os.fdopen(fd, "w", encoding="ascii") as marker:
            marker.write(state + "\n")
            marker.flush()
            os.fsync(marker.fileno())
        os.replace(temporary, marker_path)
        # Persist the directory entry where supported. Some platforms reject
        # opening directories; the epoch remains fsync'd at file level.
        try:
            dir_fd = os.open(directory, os.O_RDONLY)
        except OSError:
            dir_fd = None
        if dir_fd is not None:
            try:
                os.fsync(dir_fd)
            except OSError:
                pass
            finally:
                os.close(dir_fd)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise
    return epoch

def note_database_commit(database: str | Path) -> int:
    """Durably publish a completed commit and the exact file state it attests."""
    paths = _shared_epoch_paths(database)
    if paths is None:
        return _bump_memory_epoch(database)
    marker_path, lock_path = paths
    with _shared_epoch_guard(lock_path, exclusive=True):
        return _publish_state_locked(marker_path, database)

@contextmanager
def _exclusive_commit_window(database: str | Path):
    """Make "SQLite commit + epoch publication" one step for every reader.

    Without this window a reader can observe a committed file whose epoch and
    signature were not published yet, and would reject or accept the wrong
    generation. Yields the publication callable, because re-entering the flock
    from the same process would deadlock.
    """
    paths = _shared_epoch_paths(database)
    if paths is None:
        with _COMMIT_EPOCH_LOCK:
            yield lambda: _bump_memory_epoch(database)
        return
    marker_path, lock_path = paths
    with _shared_epoch_guard(lock_path, exclusive=True):
        yield lambda: _publish_state_locked(marker_path, database)

@contextmanager
def database_read_window(database: str | Path):
    """Hold the shared coordination lock while a consumer inspects the database.

    Consumers read the epoch, the attested signature and the observed file state
    inside this window so a concurrent cooperative commit cannot be mistaken for
    an unattested change (or vice versa).
    """
    paths = _shared_epoch_paths(database)
    if paths is None:
        with _COMMIT_EPOCH_LOCK:
            yield
        return
    _marker_path, lock_path = paths
    with _shared_epoch_guard(lock_path, exclusive=False):
        yield
