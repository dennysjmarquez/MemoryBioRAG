"""Apertura y política de journal para conexiones escritoras BioRAG.

La versión se consulta en el proceso que crea cada conexión: la versión del
SQLite del shell, otro Python o un daemon distinto no es intercambiable.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import sqlite3
import threading
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.paths import resolve_db_path

logger = logging.getLogger("BioRAG.SQLiteRuntime")

# Releases con corrección publicada por SQLite para el WAL-reset bug.
_FIRST_WAL_RELEASE = (3, 7, 0)
_DEFAULT_BUSY_TIMEOUT_MS = 30_000
_MAX_BUSY_TIMEOUT_MS = 300_000


class UnsafeSQLiteJournalModeError(sqlite3.OperationalError):
    """La conexión no puede abrirse para escribir en un journal seguro."""


class SQLiteDatabaseCorruptError(RuntimeError):
    """La base no se puede leer de forma segura tal como está en disco.

    Se distingue de un fallo de identidad: aquí el archivo principal puede
    estar sano y el problema ser un `-wal` que no le pertenece. Nunca implica
    que se haya modificado o reparado algo: el motor solo aparta el diario.
    """


class SQLiteDatabaseIdentityChangedError(sqlite3.OperationalError):
    """El path canónico apunta a un archivo SQLite distinto del que abrió el motor."""


def database_file_identity(database: str | os.PathLike[str]) -> tuple[int, int] | None:
    """Devuelve `(device, inode)` del archivo, sin inspeccionar su contenido.

    Los identificadores no aplican a bases `:memory:` ni a URI SQLite. Para un
    path de archivo inexistente propaga `OSError`: el caller decide si eso
    representa una generación desaparecida.
    """
    value = os.fsdecode(os.fspath(database))
    if _is_memory_database(value) or value.startswith("file:"):
        return None
    st = os.stat(value)
    return int(st.st_dev), int(st.st_ino)


def _effective_sqlite_version() -> tuple[int, int, int]:
    """Versión efectiva del motor enlazado al módulo sqlite3 de este proceso."""
    return tuple(sqlite3.sqlite_version_info[:3])


def is_wal_reset_vulnerable(version: tuple[int, ...] | None = None) -> bool:
    """Indica si la versión puede sufrir el WAL-reset bug documentado por SQLite.

    Se aplican los releases fijos publicados (3.51.3, 3.50.7 y 3.44.6), no
    inferencias basadas solo en el número de Python ni en una versión reportada
    por otro proceso.
    """
    version = tuple(version or _effective_sqlite_version())
    if version < _FIRST_WAL_RELEASE:
        return False  # este motor aún no tenía WAL
    if version >= (3, 51, 3):
        return False
    if (3, 50, 7) <= version < (3, 51, 0):
        return False
    if (3, 44, 6) <= version < (3, 45, 0):
        return False
    return True


def _is_memory_database(database: str | Path) -> bool:
    value = str(database)
    return value == ":memory:" or (
        value.startswith("file:") and "mode=memory" in value.lower()
    )


def _database_existed_before_open(database: str | Path) -> bool:
    value = str(database)
    if _is_memory_database(database):
        return False
    # URI SQLite no se interpreta como ruta de filesystem aquí. Tratarlo como
    # existente evita cambiar journal en una URI cuyo archivo no podemos resolver.
    if value.startswith("file:"):
        return True
    return Path(os.path.expanduser(value)).exists()


# Señales de que la base no se puede leer tal como está en disco. Un `-wal`
# heredado de otra generación se manifiesta de las tres formas: la lectura
# rechaza la imagen ("malformed"), el archivo no parece una base ("not a
# database"), o la lectura de páginas falla al no poder aplicar el diario ajeno
# ("disk I/O error"). Las tres son recuperables apartando el diario.
_UNREADABLE_MARKERS = ("malformed", "not a database", "disk i/o error", "disk i/o")


def _looks_unreadable(exc: BaseException) -> bool:
    message = str(exc).lower()
    return any(marker in message for marker in _UNREADABLE_MARKERS)


def _sqlite_header(path: str) -> bytes:
    try:
        with open(path, "rb") as handle:
            return handle.read(100)
    except OSError:
        return b""




_OWNER_SUFFIX = ".biorag-wal-owner"

# Margen por el que el archivo principal puede ser más nuevo que su `-wal` sin
# que eso signifique que el diario es de otra generación. Un checkpoint normal
# los deja casi simultáneos; 30 s cubre relojes y operaciones lentas.
_FOREIGN_WAL_MARGIN_NS = 30 * 1_000_000_000


def _owner_path(database) -> str | None:
    value = os.fsdecode(os.fspath(database))
    if _is_memory_database(value) or value.startswith("file:"):
        return None
    return os.path.expanduser(value) + _OWNER_SUFFIX


def _main_signature(database) -> list[int] | None:
    """Huella barata del archivo principal: tamaño y sellos de tiempo."""
    try:
        st = os.stat(os.fsdecode(os.fspath(database)))
    except OSError:
        return None
    return [
        int(st.st_size),
        int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1_000_000_000))),
        int(getattr(st, "st_ctime_ns", int(st.st_ctime * 1_000_000_000))),
    ]


def _wal_salt(path: str) -> str | None:
    """Los 8 bytes de "sal" de la cabecera del WAL.

    Es la señal que sí distingue procedencia: la sal la genera SQLite al crear
    el diario, se mantiene estable mientras ese diario vive (sobrevive a los
    checkpoints) y es distinta en un `-wal` de otra copia de la base. No es una
    heurística de tamaños ni de tiempos.
    """
    header = _sqlite_header(path)
    if len(header) < 24 or header[:3] != b"7\x7f\x06":
        return None
    return header[16:24].hex()


def _record_wal_salt(database) -> None:
    """Anota la sal del `-wal` vivo junto con la huella del archivo principal."""
    mark = _owner_path(database)
    if mark is None:
        return
    value = os.path.expanduser(os.fsdecode(os.fspath(database)))
    salt = _wal_salt(value + "-wal")
    if salt is None:
        return
    signature = _main_signature(database)
    if signature is None:
        return
    try:
        with open(mark, "w", encoding="ascii") as handle:
            json.dump({"main": signature, "wal_salt": salt}, handle)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError:
        logger.debug("No se pudo anotar la sal del WAL")


def _recorded_wal_salt(database) -> str | None:
    mark = _owner_path(database)
    if mark is None:
        return None
    try:
        with open(mark, "r", encoding="ascii") as handle:
            data = json.loads(handle.read() or "{}")
    except (OSError, ValueError):
        return None
    salt = data.get("wal_salt")
    return salt if isinstance(salt, str) and len(salt) == 16 else None


def _record_main_signature(database) -> None:
    """Anota la huella del archivo principal, solo cuando es seguro hacerlo.

    El único momento sin ambigüedad es cuando NO hay `-wal` con contenido: ahí
    el archivo y la base son lo mismo. Con un diario vivo no se sobrescribe,
    porque entonces se perdería la referencia contra la que comparar.
    """
    mark = _owner_path(database)
    if mark is None or _has_nonempty_wal(database):
        return
    signature = _main_signature(database)
    if signature is None:
        return
    import json as _json

    try:
        with open(mark, "w", encoding="ascii") as handle:
            handle.write(_json.dumps({"main": signature}))
            handle.flush()
            os.fsync(handle.fileno())
    except OSError:
        logger.debug("No se pudo anotar la huella del archivo principal")


def _main_changed_since_record(database) -> bool:
    mark = _owner_path(database)
    if mark is None:
        return False
    import json as _json

    try:
        with open(mark, "r", encoding="ascii") as handle:
            recorded = _json.loads(handle.read() or "{}").get("main")
    except (OSError, ValueError):
        return False
    if not isinstance(recorded, list):
        return False
    current = _main_signature(database)
    if current is None:
        return False
    try:
        return [int(v) for v in recorded] != current
    except (TypeError, ValueError):
        return False



def _wal_is_foreign_by_salt(database) -> bool | None:
    """Compara la sal del `-wal` con la anotada.

    Devuelve:
      True  -> el diario es de otra generación (sal distinta), o
      False -> es el mismo diario (sal idéntica), o
      None  -> no hay anotación previa y no se puede decidir.
    """
    value = os.fsdecode(os.fspath(database))
    if _is_memory_database(value) or value.startswith("file:"):
        return False
    if not _has_nonempty_wal(value):
        return False
    current = _wal_salt(os.path.expanduser(value) + "-wal")
    if current is None:
        return None
    recorded = _recorded_wal_salt(value)
    if recorded is None:
        return None
    return current != recorded


def _wal_is_suspect(database) -> bool:
    """¿Debe el motor negarse a abrir el par tal como está en disco?

    Política derivada de `docs/auditoria_pr13_ac31b4c.md`.

    La comprobación que la auditoría demostró insuficiente era de legibilidad
    (`quick_check` sobre una copia): un `-wal` ajeno puede ser válido y aun así
    sobrescribir filas buenas con las de otra versión. La señal que sí sirve es
    la **sal** de la cabecera del WAL: la genera SQLite al crear el diario,
    sobrevive a los checkpoints legítimos y difiere en el diario de otra copia.

    * Sal anotada y distinta de la actual -> el diario es de otra generación:
      se rechaza, sin mover, renombrar ni borrar nada.
    * Sal anotada e idéntica -> el diario es suyo: se abre con normalidad
      (preserva checkpoints legítimos y escritores coordinados).
    * Sin anotación previa -> no hay evidencia en ningún sentido. El motor
      adopta el par y anota la sal, en vez de bloquear una base que venía
      funcionando. Es un límite conocido y declarado: la primera apertura de
      una base antigua que tuviera un `-wal` ajeno no se puede distinguir.

    En ningún caso esta función modifica, renombra ni elimina un archivo.
    """
    value = os.fsdecode(os.fspath(database))
    if _is_memory_database(value) or value.startswith("file:"):
        return False
    if not _has_nonempty_wal(value):
        return False
    return _wal_is_foreign_by_salt(value) is True


def _has_record(database) -> bool:
    mark = _owner_path(database)
    if mark is None:
        return False
    try:
        with open(mark, "rb") as handle:
            return bool(handle.read().strip())
    except OSError:
        return False


def _sidecar_inventory(database) -> list[dict[str, Any]]:
    """Describe los sidecars presentes (tamaño, mtime, sha256). Solo lectura."""
    value = os.fsdecode(os.fspath(database))
    main = os.path.expanduser(value)
    inventory: list[dict[str, Any]] = []
    for suffix in ("-wal", "-shm"):
        path = main + suffix
        try:
            st = os.stat(path)
            with open(path, "rb") as handle:
                digest = hashlib.sha256(handle.read()).hexdigest()
        except OSError:
            continue
        inventory.append(
            {
                "route_id": _database_route_id(main),
                "suffix": suffix,
                "size": int(st.st_size),
                "mtime_ns": int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9))),
                "sha256": digest,
            }
        )
    return inventory


def _record_inventory(database, inventory: list[dict[str, Any]]) -> None:
    """Deja constancia escrita y verificable de lo que había, sin mover nada."""
    if not inventory:
        return
    marker, _ = _shared_epoch_paths(database) or (None, None)
    base = marker or (os.path.expanduser(os.fsdecode(os.fspath(database))) + ".huerfano")
    path = Path(base).with_suffix(Path(base).suffix + ".sidecars.json")
    payload = {
        "principal": _main_signature(database),
        "sidecars": inventory,
        "registrado": time.time(),
    }
    try:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError:
        logger.exception("No se pudo dejar constancia de los sidecars")
        return
    logger.warning(
        "Sidecars preservados sin moverlos; inventario en %s (sha256 %s)",
        path,
        ", ".join(f"{item['suffix']}={item['sha256'][:12]}" for item in inventory),
    )


class SQLiteSidecarConflictError(SQLiteDatabaseCorruptError):
    """Se rechazó abrir el par real porque no se puede probar su procedencia.

    No se movió, renombró ni borró ningún archivo: solo se dejó constancia de
    lo que había. La decisión de recuperar es del operador, no del motor.
    """




def _has_nonempty_wal(database) -> bool:
    value = os.fsdecode(os.fspath(database))
    if _is_memory_database(value) or value.startswith("file:"):
        return False
    try:
        return os.path.getsize(os.path.expanduser(value) + "-wal") > 0
    except OSError:
        return False


def _raw_execute(conn: sqlite3.Connection, sql: str, parameters: Any = ()):
    """Run an internal runtime statement without the user-facing cursor tracking.

    Runtime probes and journal-policy changes are not user commits, so they must
    not publish a commit epoch. Bypassing the tracked cursor also avoids keeping
    an untracked cursor alive in a traceback when a journal transition fails,
    which used to defer sqlite3_close and leave a WAL read lock behind.

    The class is looked up at call time on purpose: the tracked connection is
    defined further down this module, and a direct reference here would be an
    UnboundLocalError raised during ``configure_writer`` (inside the very
    ``except`` handler that builds the actionable journal error) instead of the
    real SQLite failure.
    """
    tracked = globals().get("_TrackedSQLiteConnection")
    if tracked is not None and isinstance(conn, tracked):
        return sqlite3.Connection.execute(conn, sql, parameters)
    return conn.execute(sql, parameters)


def _journal_mode(conn: sqlite3.Connection) -> str:
    row = _raw_execute(conn, "PRAGMA journal_mode").fetchone()
    if not row or not row[0]:
        raise sqlite3.OperationalError("SQLite no devolvió el journal mode efectivo")
    return str(row[0]).lower()


def _sqlite_source_id(conn: sqlite3.Connection) -> str:
    try:
        row = conn.execute("SELECT sqlite_source_id()").fetchone()
        return str(row[0]) if row else "desconocido"
    except sqlite3.Error:
        return "no disponible"


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
        os.makedirs(os.path.dirname(local_key) or ".", exist_ok=True)
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
    fd, temporary = tempfile.mkstemp(prefix=".biorag-epoch-", dir=directory)
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


def _statement_may_write(sql: Any) -> bool:
    """Conservative first-keyword classifier for SQLite write statements."""
    if not isinstance(sql, (str, bytes)):
        return False
    if isinstance(sql, bytes):
        sql = sql.decode("utf-8", errors="ignore")
    statement = re.sub(r"(?m)^\s*(?:--[^\n]*(?:\n|$)|/\*.*?\*/\s*)+", "", sql).lstrip()
    match = re.match(r"([A-Za-z]+)", statement)
    if not match:
        return False
    keyword = match.group(1).upper()
    if keyword in {"INSERT", "UPDATE", "DELETE", "REPLACE", "CREATE", "DROP", "ALTER", "REINDEX", "VACUUM", "ATTACH", "DETACH"}:
        return True
    if keyword == "WITH":
        return bool(re.search(r"\b(INSERT|UPDATE|DELETE|REPLACE)\b", statement, re.I))
    if keyword == "PRAGMA":
        pragma = statement.partition(" ")[2].strip()
        match = re.match(r"(?:[A-Za-z_][A-Za-z0-9_]*\.)?([A-Za-z_][A-Za-z0-9_]*)", pragma)
        if not match:
            return False
        pragma_name = match.group(1).lower()
        if pragma_name == "wal_checkpoint":
            return True
        if "=" not in pragma:
            return False
        # Only database-persistent header/schema pragmas can attest a file
        # transition. Connection-local settings such as busy_timeout must not
        # advance the epoch.
        return pragma_name in {
            "application_id", "auto_vacuum", "encoding", "journal_mode",
            "page_size", "schema_version", "secure_delete", "user_version",
        }
    return False


class _TrackedSQLiteCursor(sqlite3.Cursor):
    """Cursor that publishes DML, auto-committed DDL and scripts safely."""

    def execute(self, sql, parameters=()):
        keyword = _statement_keyword(sql)
        if keyword in {"COMMIT", "END"}:
            self.connection.commit()
            return self
        if keyword == "ROLLBACK":
            self.connection.rollback()
            return self
        may_write = _statement_may_write(sql)
        data_version = self.connection._data_version() if may_write else None
        result = super().execute(sql, parameters)
        if may_write:
            self.connection._biorag_pending_write = True
            if not self.connection.in_transaction:
                self.connection._biorag_pending_write = False
                self.connection._publish_autocommit(data_version)
        return result

    def executemany(self, sql, seq_of_parameters):
        may_write = _statement_may_write(sql)
        data_version = self.connection._data_version() if may_write else None
        result = super().executemany(sql, seq_of_parameters)
        if may_write:
            self.connection._biorag_pending_write = True
            if not self.connection.in_transaction:
                self.connection._biorag_pending_write = False
                self.connection._publish_autocommit(data_version)
        return result

    def executescript(self, sql_script):
        connection = self.connection
        if connection.in_transaction:
            connection.commit()
        may_write = _statement_may_write(sql_script)
        data_version = connection._data_version() if may_write else None
        result = super().executescript(sql_script)
        if may_write:
            connection._biorag_pending_write = True
            if not connection.in_transaction:
                connection._biorag_pending_write = False
                connection._publish_autocommit(data_version)
        return result


def _statement_keyword(sql: Any) -> str:
    if isinstance(sql, bytes):
        sql = sql.decode("utf-8", errors="ignore")
    if not isinstance(sql, str):
        return ""
    statement = re.sub(r"(?m)^\s*(?:--[^\n]*(?:\n|$)|/\*.*?\*/\s*)+", "", sql).lstrip()
    match = re.match(r"([A-Za-z]+)", statement)
    return match.group(1).upper() if match else ""


class _TrackedSQLiteConnection(sqlite3.Connection):
    """Attests current-process commits under SQLite's writer lock."""

    def __init__(self, database, *args, **kwargs):
        super().__init__(database, *args, **kwargs)
        self._biorag_database = database
        self._biorag_pending_write = False

    def _data_version(self) -> int:
        row = sqlite3.Connection.execute(self, "PRAGMA data_version").fetchone()
        return int(row[0]) if row else -1

    def _assert_no_foreign_commit(self, data_version_before) -> None:
        """Fail closed when another connection committed during our write.

        ``PRAGMA data_version`` is *not* advanced by the connection's own
        commits; it only moves when a different connection changes the file. So
        a non-zero delta right after our commit means a foreign commit was
        interleaved. Version 4 of the protocol never attests such a state: the
        file may already mix a coordinated commit with a legacy one.
        """
        if data_version_before is None:
            raise sqlite3.OperationalError("Falta la sonda previa del commit SQLite.")
        after = self._data_version()
        delta = (after - int(data_version_before)) & 0xFFFFFFFF
        if delta != 0:
            raise sqlite3.OperationalError(
                "Se detectó un commit externo no coordinado durante la operación; "
                "el commit quedó aplicado, pero no se publicó como generación segura."
            )

    def _publish_autocommit(self, data_version_before) -> None:
        """Attest an autocommitted statement (DDL, PRAGMA or script) atomically.

        The statement is already committed here, so the exclusive window only
        spans the publication: a concurrent reader sees either the previous
        epoch with the previous file, or the new epoch with the new file.
        """
        with _exclusive_commit_window(self._biorag_database) as publish:
            self._assert_no_foreign_commit(data_version_before)
            publish()

    def cursor(self, factory=None):
        if factory not in (None, _TrackedSQLiteCursor):
            raise TypeError("open_writer requiere cursores con seguimiento de commits")
        return sqlite3.Connection.cursor(self, _TrackedSQLiteCursor)

    def execute(self, sql, parameters=()):
        return self.cursor().execute(sql, parameters)

    def executemany(self, sql, seq_of_parameters):
        return self.cursor().executemany(sql, seq_of_parameters)

    def executescript(self, sql_script):
        return self.cursor().executescript(sql_script)

    def commit(self):
        if not self.in_transaction or not self._biorag_pending_write:
            return sqlite3.Connection.commit(self)
        data_version = self._data_version()
        with _exclusive_commit_window(self._biorag_database) as publish:
            result = sqlite3.Connection.commit(self)
            self._biorag_pending_write = False
            self._assert_no_foreign_commit(data_version)
            publish()
            # La sal del diario vivo es la prueba de pertenencia para la
            # próxima apertura: se anota dentro de la misma ventana exclusiva.
            _record_wal_salt(self._biorag_database)
        return result

    def rollback(self):
        result = sqlite3.Connection.rollback(self)
        self._biorag_pending_write = False
        return result

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        return False


def connection_diagnostics(
    conn: sqlite3.Connection,
    database: str | Path,
    *,
    role: str,
    consumer: str,
) -> dict[str, Any]:
    """Devuelve y registra runtime efectivo sin incluir ruta ni datos de la DB."""
    row = conn.execute("PRAGMA busy_timeout").fetchone()
    busy_timeout_ms = int(row[0]) if row else -1
    details = {
        "consumer": str(consumer),
        "role": str(role),
        "runtime": ".".join(map(str, _effective_sqlite_version())),
        "source_id": _sqlite_source_id(conn),
        "journal_mode": _journal_mode(conn),
        "busy_timeout_ms": busy_timeout_ms,
        "route_id": _database_route_id(database),
    }
    logger.debug(
        "SQLite connection: consumer=%s role=%s runtime=%s source_id=%s "
        "journal=%s busy_timeout_ms=%d route_id=%s",
        details["consumer"], details["role"], details["runtime"],
        details["source_id"], details["journal_mode"], busy_timeout_ms,
        details["route_id"],
    )
    return details


@dataclass(frozen=True)
class SQLiteWriterRuntime:
    version: tuple[int, int, int]
    source_id: str
    journal_mode: str
    wal_reset_vulnerable: bool
    transition_applied: bool


def configure_writer(
    conn: sqlite3.Connection,
    database: str | Path,
    *,
    busy_timeout_ms: int = _DEFAULT_BUSY_TIMEOUT_MS,
    database_existed: bool = True,
    allow_existing_journal_transition: bool = False,
) -> SQLiteWriterRuntime:
    """Configura una conexión escritora sin cambiar journal existente en silencio.

    Bases preexistentes conservan el journal actual. Un runtime vulnerable que
    encuentre WAL falla cerrado por defecto; la migración de una base existente
    requiere opt-in explícito y SQLite debe conceder el lock exclusivo requerido.
    Una base nueva puede iniciar en WAL si el runtime tiene la corrección.
    """
    if not isinstance(busy_timeout_ms, int) or not 0 <= busy_timeout_ms <= _MAX_BUSY_TIMEOUT_MS:
        raise ValueError(
            f"busy_timeout_ms debe ser un entero entre 0 y {_MAX_BUSY_TIMEOUT_MS}"
        )

    version = _effective_sqlite_version()
    vulnerable = is_wal_reset_vulnerable(version)
    source_id = _sqlite_source_id(conn)
    _raw_execute(conn, f"PRAGMA busy_timeout={busy_timeout_ms}")
    current = _journal_mode(conn)

    # Una base :memory: usa el journal interno `memory`, nunca WAL/DELETE.
    if _is_memory_database(database) or current == "memory":
        return SQLiteWriterRuntime(version, source_id, current, vulnerable, False)

    if vulnerable and current == "wal" and database_existed and not allow_existing_journal_transition:
        raise UnsafeSQLiteJournalModeError(
            "BioRAG rechazó la escritura sin modificar el journal: este proceso "
            f"usa SQLite {'.'.join(map(str, version))}, vulnerable al WAL-reset bug, "
            "y la base existente está en journal_mode='wal'. No se intentó cambiar "
            "ni borrar la base o sus sidecars. Cierre de forma ordenada los "
            "consumidores y autorice/ejecute una migración explícita del journal, "
            "o use en todos los escritores un runtime corregido (3.51.3+, 3.50.7 o "
            "3.44.6 con el arreglo aplicado)."
        )

    # Solo se elige un journal al crear un archivo nuevo, o ante una migración
    # explícitamente autorizada. En una base existente normal se respeta su modo.
    may_transition = not database_existed or allow_existing_journal_transition
    target = "delete" if vulnerable else "wal"
    transition_applied = False
    actual = current
    if may_transition and current != target:
        _raw_execute(conn, "PRAGMA busy_timeout=0")
        transition_error: sqlite3.Error | None = None
        try:
            row = _raw_execute(conn, f"PRAGMA journal_mode={target}").fetchone()
            actual = str(row[0]).lower() if row and row[0] else _journal_mode(conn)
            transition_applied = actual == target
        except sqlite3.OperationalError as exc:
            transition_error = exc
            actual = _journal_mode(conn)

        if vulnerable and actual != "delete":
            _raw_execute(conn, f"PRAGMA busy_timeout={busy_timeout_ms}")
            reason = f"; error SQLite: {transition_error}" if transition_error else ""
            raise UnsafeSQLiteJournalModeError(
                "BioRAG rechazó la escritura: no se pudo confirmar el cambio "
                f"exclusivo de journal a DELETE (modo efectivo: {actual!r}{reason}). "
                "Cierre los consumidores que mantienen la base abierta y reintente "
                "solo con autorización explícita. No se borraron ni repararon la "
                "base o sus sidecars."
            ) from transition_error

        if not vulnerable and actual not in {"wal", "delete", "truncate", "persist"}:
            _raw_execute(conn, f"PRAGMA busy_timeout={busy_timeout_ms}")
            raise sqlite3.OperationalError(
                f"No se pudo establecer un journal compatible; journal_mode={actual!r}"
            ) from transition_error

        if not transition_applied:
            logger.info(
                "SQLite %s: no se cambió journal %s→%s (modo efectivo %s); "
                "se conserva el modo existente",
                ".".join(map(str, version)), current, target, actual,
            )

    _raw_execute(conn, f"PRAGMA busy_timeout={busy_timeout_ms}")
    actual = _journal_mode(conn)
    if vulnerable and actual == "wal":
        raise UnsafeSQLiteJournalModeError(
            "BioRAG rechazó la escritura porque el runtime SQLite vulnerable "
            "no puede escribir sobre una base WAL existente sin migración autorizada."
        )

    return SQLiteWriterRuntime(version, source_id, actual, vulnerable, transition_applied)


def open_writer(
    database: str | Path,
    *,
    timeout: float = _DEFAULT_BUSY_TIMEOUT_MS / 1000,
    busy_timeout_ms: int = _DEFAULT_BUSY_TIMEOUT_MS,
    allow_existing_journal_transition: bool = False,
    consumer: str = "unspecified",
    **connect_kwargs: Any,
) -> sqlite3.Connection:
    """Abre una conexión BioRAG escritora con política version-aware.

    La transición de journal de una DB existente está desactivada por defecto y
    requiere `allow_existing_journal_transition=True` explícito por el operador.
    """
    database_existed = _database_existed_before_open(database)
    if "factory" in connect_kwargs:
        raise TypeError("open_writer administra la subclase de conexión")
    def _abrir():
        return sqlite3.connect(
            database, timeout=timeout, factory=_TrackedSQLiteConnection,
            **connect_kwargs,
        )

    def _configurar(connection):
        return configure_writer(
            connection,
            database,
            busy_timeout_ms=busy_timeout_ms,
            database_existed=database_existed,
            allow_existing_journal_transition=allow_existing_journal_transition,
        )

    # Política conservadora (auditoría docs/auditoria_pr13_ac31b4c.md).
    #
    # No se puede demostrar que un `-wal` pertenezca a este archivo principal:
    # un diario ajeno puede producir una base estructuralmente válida, pasar
    # `quick_check` y aun así sobrescribir filas buenas con las de otra rama.
    # Por eso, ante una combinación sospechosa, el motor NO mueve, renombra ni
    # borra nada: se niega a abrir el par real, deja constancia verificable de
    # los sidecars y devuelve la decisión al operador.
    if _wal_is_suspect(database):
        inventory = _sidecar_inventory(database)
        _record_inventory(database, inventory)
        raise SQLiteSidecarConflictError(
            "Se rechazó abrir la base: hay un -wal en disco que no se puede "
            "atribuir con certeza a este archivo principal (por ejemplo, tras "
            "cambiar de rama con la base versionada). Abrir en este estado "
            "podría aplicar datos de otra versión sobre los actuales. No se "
            "movió, renombró ni borró ningún archivo; se dejó constancia del "
            "sha256 de los sidecars junto a la base. Conserve una copia del "
            ".db, del -wal y del -shm, y decida la recuperación manualmente."
        )

    conn = _abrir()
    try:
        policy = _configurar(conn)
        # Anotar la huella del archivo principal (solo sin `-wal` con
        # contenido, el único momento sin ambigüedad) y la sal del diario vivo,
        # que es la prueba de pertenencia para las aperturas siguientes.
        _record_main_signature(database)
        _record_wal_salt(database)
    except BaseException:
        conn.close()
        raise

    logger.debug(
        "SQLite connection: consumer=%s role=writer runtime=%s source_id=%s "
        "journal=%s busy_timeout_ms=%d wal_reset_vulnerable=%s "
        "transition_applied=%s route_id=%s",
        consumer, ".".join(map(str, policy.version)), policy.source_id,
        policy.journal_mode, busy_timeout_ms, policy.wal_reset_vulnerable,
        policy.transition_applied, _database_route_id(database),
    )
    return conn


def open_reader(
    database: str | Path,
    *,
    timeout: float = _DEFAULT_BUSY_TIMEOUT_MS / 1000,
    consumer: str = "unspecified",
    **connect_kwargs: Any,
) -> sqlite3.Connection:
    """Abre una conexión read-only por path canónico y registra el runtime efectivo.

    Se rechazan SQLite URI y `:memory:` intencionalmente: esta interfaz recibe
    rutas de archivos para evitar combinaciones de URI/query no validadas.
    """
    if not isinstance(timeout, (int, float)) or not 0 <= timeout <= _MAX_BUSY_TIMEOUT_MS / 1000:
        raise ValueError(
            f"timeout debe estar entre 0 y {_MAX_BUSY_TIMEOUT_MS / 1000} segundos"
        )
    canonical = resolve_db_path(database)
    if canonical == ":memory:" or canonical.startswith("file:"):
        raise ValueError("open_reader requiere una ruta de archivo, no memory/SQLite URI")
    if "uri" in connect_kwargs:
        raise TypeError("open_reader administra el parámetro uri internamente")

    timeout_ms = int(round(timeout * 1000))
    uri = Path(canonical).as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=timeout, **connect_kwargs)
    try:
        conn.execute(f"PRAGMA busy_timeout={timeout_ms}")
        conn.execute("PRAGMA query_only=ON")
        connection_diagnostics(
            conn, canonical, role="read-only", consumer=consumer
        )
    except BaseException:
        conn.close()
        raise
    return conn
