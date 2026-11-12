import os
import sqlite3
import re
import logging
import copy
import functools
import threading
import time
from contextlib import contextmanager
from core.sqlite_runtime import (
    SQLiteDatabaseIdentityChangedError,
    _wal_content_signature,
    database_commit_state,
    database_read_window,
    database_file_identity,
    open_writer,
)
from collections import deque

logger = logging.getLogger("BioRAG.MemoryStore")

# Límite para esperar operaciones propias antes de cerrar; no limita SQLite
# checkpoint/close. La expiración preserva conexiones y permite reintentar.
_CIERRE_DRENAJE_SEGUNDOS = 30.0

# Auto-cargar .env.local al importar (antes de leer cualquier variable de entorno)
from config import _load_env_local

try:
    from core.calibracion import (zscore_por_query, fusion_rrf, FusionLogistica,
                                   CalibradorPlatt, calibracion_isotonica,
                                   UmbralConforme, mmr)
except ImportError:
    zscore_por_query = fusion_rrf = FusionLogistica = CalibradorPlatt = None
    calibracion_isotonica = UmbralConforme = mmr = None
_load_env_local()

# Pre-cargar WordNet al importar para evitar latencia de 3s en primera consulta semántica
try:
    from core.clasificador_wordnet import obtener_lexnames_query
    obtener_lexnames_query("test")  # Trigger NLTK/WordNet lazy load
except Exception:
    pass  # WordNet opcional, ignorar si falla

# =============================================================================
# Constantes, flags de configuración y re-exports hacia core.memory.constants
# =============================================================================

from core.memory import constants
from core.memory.constants import (
    CANDIDATOS_SIMILITUD, MAX_SALTOS_CADENA, LIMITE_DEFAULT, UMBRAL_JACCARD,
    RAFTAGA_ACTIVA, THRESHOLD_RAFTAGA, LIMITE_RAFTAGA, LIMITE_EVOCACION,
    JSD_WEIGHT, JSD_ADAPTATIVO, JSD_ADAPT_BASE, JSD_ADAPT_LARGO, JSD_ADAPT_CORTO, JSD_ADAPT_NT,
    DMN_SINTESIS_ACTIVA, DMN_SINTESIS_MAX, DMN_SINTESIS_PESO,
    EPISODIO_TEMPORAL_PESO, EPISODIO_TEMPORAL_ACTIVO, EPISODIO_VENTANA_HORAS, EPISODIO_LIMITE, EPISODIO_BUCKET_SEG,
    ANALOGIA_PESO, ANALOGIA_DETECTAR,
    CAMPO_POTENCIAL_PESO, CAMPO_SIGMA, CAMPO_K,
    EPISTEMICO_METADATA,
    MULTIHOP_EXPANSION, MULTIHOP_MAX_TOTAL, MULTIHOP_PRIOR,
    BAYESIAN_BM25, BAYESIAN_BM25_ALPHA,
    RERANKING_JACCARD_ACTIVO, RERANKING_JACCARD_ALPHA, RERANKING_JACCARD_GATE, RERANKING_JACCARD_TOPK, RERANKING_JACCARD_WINDOW,
    SDM_FALLBACK_ACTIVO, SDM_FALLBACK_K,
    QCR_IDF_ACTIVO, QCR_IDF_UMBRAL,
    QCR_TYPO_ACTIVA, DIM_RESONANCIA, DIM_RESONANCIA_K, DIM_ESCAPE, DIM_ESCAPE_T, QCR_TYPO_PISO, QCR_TYPO_DIST,
    NCD_PESO, NCD_ZLIB_LEVEL,
    GABA_ACTIVO,
    PPMI_VECTOR_WEIGHT,
    ADN_RANKING_ENABLED, ADN_PESO, ADN_MAX_EXPANSION, ADN_UMBRAL_ASOCIACION,
    _qcr_levenshtein, _qcr_todos_cercanos, normalizar_sustantivos_clave,
    normalizar_sustantivos_clave_exacto, normalizar_sustantivos_clave_exactos_coherentes,
)
from core.memory import comms
from core.memory import telemetry
from core.memory import synapses
from core.memory import episodes
from core.memory import quarantine
from core.memory import ingest
from core.memory import dmn
from core.memory import consolidation
from core.memory import scoring
from core.memory import umbral
from core.memory import context
from core.memory import catalog_methods
from core.memory import adn
from core.memory import rafaga
from core.memory import schema
from core.memory import search

# =============================================================================

def _sql_may_write(statement):
    sql = str(statement or "").lstrip()
    if re.match(r"PRAGMA\b", sql, re.IGNORECASE):
        return "=" in sql
    return bool(re.match(
        r"(?:INSERT|UPDATE|DELETE|REPLACE|CREATE|DROP|ALTER|VACUUM|REINDEX|ANALYZE|ATTACH|DETACH|WITH)\b",
        sql,
        re.IGNORECASE,
    ))


def _sql_palabra_completa(token, texto):
    if not token or not texto:
        return 0
    token_norm = token.lower().replace('_', ' ').replace('-', ' ')
    texto_norm = texto.lower().replace('_', ' ').replace('-', ' ')
    return 1 if re.search(r'\b' + re.escape(token_norm) + r'\b', texto_norm) else 0


def _sql_palabra_prefijo(token, texto):
    if not token or not texto:
        return 0
    token_norm = token.lower().replace('_', ' ').replace('-', ' ')
    texto_norm = texto.lower().replace('_', ' ').replace('-', ' ')
    return 1 if re.search(r'\b' + re.escape(token_norm), texto_norm) else 0


def _sql_palabra_inicio_ancho(token, texto):
    """Prefijo en límite habitual o después de un carácter W/F."""
    import unicodedata
    if not token or not texto:
        return 0
    token_norm = token.lower().replace('_', ' ').replace('-', ' ')
    texto_norm = texto.lower().replace('_', ' ').replace('-', ' ')
    patron = re.compile(r'\b' + re.escape(token_norm))
    pos = texto_norm.find(token_norm)
    while pos >= 0:
        if patron.match(texto_norm, pos) or (
            pos > 0 and unicodedata.east_asian_width(texto_norm[pos - 1]) in ('W', 'F')
        ):
            return 1
        pos = texto_norm.find(token_norm, pos + 1)
    return 0


class _GuardedSQLiteCursor:
    """Cursor DB-API que valida generación y participa en la barrera de cierre."""

    __slots__ = ("_owner", "_raw", "_connection")

    def __init__(self, owner, raw, connection):
        object.__setattr__(self, "_owner", owner)
        object.__setattr__(self, "_raw", raw)
        object.__setattr__(self, "_connection", connection)

    def __getattr__(self, name):
        if name == "connection":
            return self._connection
        with self._owner._dbapi_lease():
            value = getattr(self._raw, name)
            if not callable(value):
                self._owner._check_connection_access(self._connection._raw)
                return value

        def guarded(*args, **kwargs):
            with self._owner._dbapi_lease():
                self._owner._check_connection_access(self._connection._raw)
                result = value(*args, **kwargs)
                if (
                    name in {"execute", "executemany", "executescript"}
                    and args
                    and _sql_may_write(args[0])
                    and not self._connection._raw.in_transaction
                ):
                    self._owner._note_cooperative_commit(self._connection._raw)
                if result is self._raw:
                    return self
                if isinstance(result, sqlite3.Cursor):
                    return self._owner._guard_cursor(result, self._connection)
                return result

        return guarded

    def __setattr__(self, name, value):
        with self._owner._dbapi_lease():
            self._owner._check_connection_access(self._connection._raw)
            setattr(self._raw, name, value)

    def __iter__(self):
        with self._owner._dbapi_lease():
            self._owner._check_connection_access(self._connection._raw)
            return self

    def __next__(self):
        with self._owner._dbapi_lease():
            self._owner._check_connection_access(self._connection._raw)
            return next(self._raw)


class _GuardedSQLiteConnection:
    """Conexión DB-API que valida generación y participa en la barrera de cierre."""

    __slots__ = ("_owner", "_raw")

    def __init__(self, owner, raw):
        object.__setattr__(self, "_owner", owner)
        object.__setattr__(self, "_raw", raw)

    def __getattr__(self, name):
        if name in {"blobopen", "iterdump"}:
            raise NotImplementedError(
                f"{name} no está soportado por la barrera de cierre DB-API"
            )
        with self._owner._dbapi_lease():
            value = getattr(self._raw, name)
            if not callable(value):
                self._owner._check_connection_access(self._raw)
                return value

        def guarded(*args, **kwargs):
            with self._owner._dbapi_lease():
                self._owner._check_connection_access(self._raw)
                was_in_transaction = self._raw.in_transaction
                result = value(*args, **kwargs)
                if name == "commit" and was_in_transaction:
                    self._owner._remember_connection_snapshot(self._raw)
                elif name == "rollback":
                    self._owner._remember_connection_snapshot(self._raw)
                elif (
                    name in {"execute", "executemany", "executescript"}
                    and args
                    and _sql_may_write(args[0])
                    and not self._raw.in_transaction
                ):
                    self._owner._note_cooperative_commit(self._raw)
                if isinstance(result, sqlite3.Cursor):
                    return self._owner._guard_cursor(result, self)
                return result

        return guarded

    def __setattr__(self, name, value):
        with self._owner._dbapi_lease():
            self._owner._check_connection_access(self._raw)
            setattr(self._raw, name, value)

    def interrupt(self):
        """Interrumpe SQLite durante el drenaje sin competir con la consulta.

        Se registra como operación para impedir que el cierre libere la
        conexión mientras interrupt está en vuelo. La admisión usa el contador
        global; solo interrumpe esta conexión, no cancela callbacks Python.
        """
        owner = self._owner
        with owner._lifecycle_condition:
            if owner._closed or (owner._closing and owner._active_operations == 0):
                raise RuntimeError("La instancia SQLiteMemoryBioRAG ya se cerró o está cerrándose")
            owner._active_operations += 1
        try:
            return self._raw.interrupt()
        finally:
            with owner._lifecycle_condition:
                owner._active_operations -= 1
                owner._lifecycle_condition.notify_all()

    def __enter__(self):
        with self._owner._dbapi_lease():
            self._owner._check_connection_access(self._raw)
            self._raw.__enter__()
            return self

    def __exit__(self, exc_type, exc, tb):
        with self._owner._dbapi_lease():
            self._owner._check_connection_access(self._raw)
            result = self._raw.__exit__(exc_type, exc, tb)
            self._owner._remember_connection_snapshot(self._raw)
            return result


def _tracked_operation(method):
    @functools.wraps(method)
    def tracked(self, *args, **kwargs):
        self._begin_operation()
        try:
            return method(self, *args, **kwargs)
        finally:
            self._end_operation()
    return tracked


class _OperationTrackedMeta(type):
    """Envelopa una sola vez los métodos públicos, sin instrumentar cada atributo."""

    def __new__(mcls, name, bases, namespace):
        for method_name, value in tuple(namespace.items()):
            if method_name.startswith("_") or method_name == "cerrar_sistema":
                continue
            if callable(value):
                namespace[method_name] = _tracked_operation(value)
        return super().__new__(mcls, name, bases, namespace)


class SQLiteMemoryBioRAG(metaclass=_OperationTrackedMeta):
    """
    Motor de Almacenamiento Cognitivo BioRAG basado en SQLite (Fachada delgada).
    Implementa almacenamiento biomimético con persistencia de doble capa (Corto/Largo plazo),
    plasticidad sináptica (LTP/LTD), indexación por B-Tree ultrarrápida,
    búsqueda de familiaridad difusa por coincidencia de Jaccard y propagación de activación (Grafo).

    Excepción de límite de líneas por deuda técnica documentada: la fachada supera 500 porque los delegadores conservan la firma completa.
    """

    def __getattr__(self, name):
        # `last_*` es estado de respuesta del request, no global del singleton.
        if name.startswith("last_"):
            try:
                local = object.__getattribute__(self, "_request_local")
                try:
                    return getattr(local, name)
                except AttributeError:
                    defaults = object.__getattribute__(self, "_last_defaults")
                    if name in defaults:
                        value = copy.deepcopy(defaults[name])
                        setattr(local, name, value)
                        return value
            except AttributeError:
                pass
        raise AttributeError(f"{type(self).__name__!s} has no attribute {name!r}")

    def _guard_connection(self, raw):
        key = id(raw)
        with self._connection_registry_lock:
            pair = self._connection_guards.get(key)
            if pair is None or pair[0] is not raw:
                pair = (raw, _GuardedSQLiteConnection(self, raw))
                self._connection_guards[key] = pair
            return pair[1]

    def _guard_cursor(self, raw, connection):
        # No cache: retaining every temporary cursor would retain read locks.
        return _GuardedSQLiteCursor(self, raw, connection)

    @property
    def conn(self):
        with self._dbapi_lease():
            self._ensure_database_identity_for_db_access()
            conn = getattr(self._connection_local, "connection", None)
            if conn is None:
                conn = self._get_thread_state()[0]
            return self._guard_connection(conn)

    @conn.setter
    def conn(self, value):
        object.__getattribute__(self, "_connection_local").connection = value

    @property
    def cursor(self):
        with self._dbapi_lease():
            self._ensure_database_identity_for_db_access()
            cursor = getattr(self._connection_local, "cursor", None)
            if cursor is None:
                cursor = self._get_thread_state()[1]
            raw_conn = getattr(self._connection_local, "connection", None)
            if raw_conn is None:
                raw_conn = self._get_thread_state()[0]
            return self._guard_cursor(cursor, self._guard_connection(raw_conn))

    @cursor.setter
    def cursor(self, value):
        object.__getattribute__(self, "_connection_local").cursor = value

    def __setattr__(self, name, value):
        if name in {"conn", "cursor"}:
            try:
                local = object.__getattribute__(self, "_connection_local")
            except AttributeError:
                object.__setattr__(self, name, value)
                return
            try:
                object.__getattribute__(self, "_lifecycle_condition")
            except AttributeError:
                setattr(local, "connection" if name == "conn" else "cursor", value)
                return
            with self._dbapi_lease():
                if name == "conn" and value is not None:
                    with object.__getattribute__(self, "_connection_registry_lock"):
                        connections = object.__getattribute__(self, "_connections")
                        if value not in connections:
                            connections.append(value)
                setattr(local, "connection" if name == "conn" else "cursor", value)
            return
        if name.startswith("last_"):
            try:
                local = object.__getattribute__(self, "_request_local")
                defaults = object.__getattribute__(self, "_last_defaults")
            except AttributeError:
                object.__setattr__(self, name, value)
                return
            try:
                primary_thread_id = object.__getattribute__(self, "_primary_thread_id")
            except AttributeError:
                primary_thread_id = threading.get_ident()
            if threading.get_ident() == primary_thread_id:
                defaults.setdefault(name, copy.deepcopy(value))
            setattr(local, name, value)
            return
        object.__setattr__(self, name, value)

    def _begin_operation(self):
        state = self._operation_local
        depth = getattr(state, "depth", 0)
        if getattr(state, "dbapi_depth", 0):
            raise RuntimeError("No se puede iniciar una operación del motor desde una llamada DB-API activa")
        if depth == 0:
            with self._lifecycle_condition:
                if self._closing:
                    raise RuntimeError("La instancia SQLiteMemoryBioRAG se está cerrando")
                if self._closed:
                    raise RuntimeError("La instancia SQLiteMemoryBioRAG ya fue cerrada")
                if self._close_failed:
                    raise RuntimeError("El cierre anterior falló; solo se puede reintentar el cierre")
                self._active_operations += 1
            try:
                if self._is_memory_database:
                    self._memory_operation_lock.acquire()
            except BaseException:
                with self._lifecycle_condition:
                    self._active_operations -= 1
                    self._lifecycle_condition.notify_all()
                raise
            state.identity_checked = False
            state.identity_error = False
        state.depth = depth + 1

    def _end_operation(self):
        state = self._operation_local
        depth = getattr(state, "depth", 0)
        if depth <= 0:
            return
        if depth > 1:
            state.depth = depth - 1
            return
        identity_error = getattr(state, "identity_error", False)
        del state.depth
        if hasattr(state, "identity_checked"):
            del state.identity_checked
        if hasattr(state, "identity_error"):
            del state.identity_error
        if not identity_error:
            connection = getattr(self._connection_local, "connection", None)
            if connection is not None:
                try:
                    self._remember_connection_snapshot(connection)
                except SQLiteDatabaseIdentityChangedError as exc:
                    # El teardown del lease nunca debe dejar `_active_operations`
                    # ni el lock `:memory:` retenidos; el próximo acceso vuelve a
                    # validar y falla cerrado.
                    logger.warning("No se pudo actualizar snapshot de DB al cerrar operación: %s", exc)
        if self._is_memory_database:
            self._memory_operation_lock.release()
        with self._lifecycle_condition:
            self._active_operations -= 1
            self._lifecycle_condition.notify_all()

    @contextmanager
    def _dbapi_lease(self):
        """Drena llamadas DB-API directas sin duplicar un lease ya activo.

        El cierre bloquea nuevos leases antes de fotografiar conexiones. Los
        handles privados y procesos externos no participan en esta barrera.
        """
        if (getattr(self._operation_local, "depth", 0)
                or getattr(self._operation_local, "dbapi_depth", 0)):
            previous = getattr(self._operation_local, "dbapi_depth", 0)
            self._operation_local.dbapi_depth = previous + 1
            try:
                yield
            finally:
                if previous:
                    self._operation_local.dbapi_depth = previous
                else:
                    del self._operation_local.dbapi_depth
            return
        with self._lifecycle_condition:
            if self._closing:
                raise RuntimeError("La instancia SQLiteMemoryBioRAG se está cerrando")
            if self._closed:
                raise RuntimeError("La instancia SQLiteMemoryBioRAG ya fue cerrada")
            if self._close_failed:
                raise RuntimeError("El cierre anterior falló; solo se puede reintentar el cierre")
            self._active_operations += 1
        self._operation_local.dbapi_depth = 1
        try:
            yield
        finally:
            del self._operation_local.dbapi_depth
            with self._lifecycle_condition:
                self._active_operations -= 1
                self._lifecycle_condition.notify_all()

    @contextmanager
    def _operation_lease(self):
        """Delimita operaciones externas/delegadas para que el cierre espere."""
        self._begin_operation()
        try:
            yield
        finally:
            self._end_operation()

    def _ensure_database_identity_for_db_access(self, connection=None):
        if getattr(self, "_close_failed", False):
            raise RuntimeError("El cierre anterior falló; solo se puede reintentar el cierre")
        operation_state = self._operation_local
        if getattr(operation_state, "depth", 0):
            if getattr(operation_state, "identity_checked", False):
                return
            self._assert_database_identity(connection=connection)
            operation_state.identity_checked = True
            return
        self._assert_database_identity(connection=connection)

    def _sidecar_file_identity(self, suffix):
        try:
            st = os.stat(self.db_path + suffix)
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise SQLiteDatabaseIdentityChangedError(
                "No se pudo verificar la identidad de un sidecar SQLite; "
                "se rechazó el acceso por seguridad."
            ) from exc
        return int(st.st_dev), int(st.st_ino)

    def _capture_sidecar_identities(self):
        if self._journal_mode != "wal":
            return
        for suffix in ("-wal", "-shm"):
            identity = self._sidecar_file_identity(suffix)
            if identity is not None:
                self._sidecar_identities[suffix] = identity

    def _mark_identity_error(self):
        state = getattr(self, "_operation_local", None)
        if state is not None and getattr(state, "depth", 0):
            state.identity_error = True

    def _file_change_signature(self):
        st = os.stat(self.db_path)
        with open(self.db_path, "rb") as database_file:
            header = database_file.read(100)
        if len(header) != 100 or not header.startswith(b"SQLite format 3\x00"):
            raise SQLiteDatabaseIdentityChangedError(
                "El archivo en la ruta configurada ya no tiene un encabezado SQLite válido."
            )
        return (
            int(st.st_size),
            int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1_000_000_000))),
            int(getattr(st, "st_ctime_ns", int(st.st_ctime * 1_000_000_000))),
            int.from_bytes(header[24:28], "big"),
            int.from_bytes(header[40:44], "big"),
            header,
            _wal_content_signature(self.db_path),
        )

    def _consistent_snapshot_state(self):
        """Sample the stat probe and the full signature as one consistent pair.

        Both must describe the same instant. Computing the signature and only
        later stat-ing allowed a direct WAL edit to land in between: the probe
        then recorded the post-edit metadata while the stored signature came from
        the pre-edit content, so the next read matched and never alerted
        (auditoría 41a98a3). Here the probe is taken first and re-taken after the
        signature; if it moved, the whole sample is repeated a few times before
        failing closed.
        """
        last_error = None
        for _ in range(3):
            probe = self._cheap_file_probe()
            signature = self._file_change_signature()
            if self._cheap_file_probe() == probe:
                return probe, signature
            last_error = "la instantánea cambió mientras se calculaba"
        raise SQLiteDatabaseIdentityChangedError(
            "No se pudo obtener una instantánea consistente del archivo SQLite "
            f"({last_error}); se rechazó el acceso por seguridad."
        )

    def _remember_connection_snapshot(self, connection):
        if (
            not getattr(self, "_generation_guard_ready", False)
            or self._database_file_identity is None
            or getattr(connection, "in_transaction", False)
        ):
            return
        try:
            # Sample the file state and the published attestation under the same
            # coordination lock: a cooperative commit cannot be observed half
            # published, which used to reject perfectly valid generations.
            cached = self._connection_snapshots.get(id(connection))
            probe = self._cheap_file_probe()
            with database_read_window(self.db_path):
                row = connection.execute("PRAGMA data_version").fetchone()
                data_version = int(row[0]) if row else -1
                commit_epoch, committed_signature = database_commit_state(self.db_path)
                if (
                    cached is not None and cached[0] is connection
                    and cached[2] == data_version and cached[3] == commit_epoch
                    and probe is not None
                    and len(cached) > 5 and cached[5] == probe
                ):
                    # data_version and epoch unchanged and neither the main file
                    # nor the WAL moved in size, mtime or ctime.
                    return
                probe, signature = self._consistent_snapshot_state()
                if cached is not None and cached[0] is connection:
                    cached_epoch = cached[3]
                else:
                    cached_epoch = None
                if (
                    committed_signature is not None
                    and commit_epoch > (cached_epoch or 0)
                    and committed_signature != signature
                ):
                    # The writer attested one file state and this reader sees a
                    # different one at the same epoch: something changed the file
                    # outside the protocol while the snapshot was being taken.
                    # Storing the observed signature here would bless exactly
                    # that change, so fail closed instead (auditoría 41a98a3).
                    raise SQLiteDatabaseIdentityChangedError(
                        "La instantánea observada no coincide con la generación "
                        "atestiguada por el escritor; se rechazó el acceso por "
                        "seguridad."
                    )
        except SQLiteDatabaseIdentityChangedError:
            raise
        except (OSError, sqlite3.Error) as exc:
            raise SQLiteDatabaseIdentityChangedError(
                "No se pudo comprobar la generación SQLite del archivo; "
                "se rechazó el acceso por seguridad."
            ) from exc
        with self._connection_registry_lock:
            self._connection_snapshots[id(connection)] = (
                connection, signature, data_version,
                commit_epoch, committed_signature, probe,
            )

    def _note_cooperative_commit(self, connection):
        # The tracked SQLite cursor publishes autocommitted DDL before this
        # snapshot; do not publish a second, unlocked attestation here.
        self._remember_connection_snapshot(connection)

    def _cheap_file_probe(self):
        """Stat-only probe over the main file *and* the WAL sidecar.

        Skips reading file contents, so it is cheap, but it must cover both
        files: a direct change inside the WAL leaves every main-file field
        intact (auditoría 4747ca8), so a main-file-only probe reported "nothing
        changed" while the WAL had been altered.

        The comparison is a *necessary* condition used to skip the expensive
        digest. It never decides on its own: any mismatch runs the full
        signature, which is what actually accepts or rejects.
        """
        probe = []
        for path in (self.db_path, self.db_path + "-wal"):
            try:
                st = os.stat(path)
            except OSError:
                probe.append(None)
                continue
            probe.append(
                (
                    int(st.st_size),
                    int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1_000_000_000))),
                    int(getattr(st, "st_ctime_ns", int(st.st_ctime * 1_000_000_000))),
                )
            )
        return tuple(probe)

    def _check_in_place_change(self, connection):
        if (
            connection is None
            or not getattr(self, "_generation_guard_ready", False)
            or self._database_file_identity is None
            or getattr(connection, "in_transaction", False)
        ):
            return
        try:
            # Always build the full signature here. A fast path gated on
            # data_version/epoch/main-file-size was tried and reverted: it made
            # two real changes invisible (auditoría d5c3834).
            #   * an in-place edit with identical size and inode moves neither
            #     data_version nor the file size, only mtime/ctime/header;
            #   * a raw wal_checkpoint(PASSIVE) can move WAL pages into the main
            #     file without changing its size.
            # Only the complete signature (main file + full WAL digest) covers
            # both. Because that costs time, callers reach this check once per
            # operation, not once per statement.
            cached = self._connection_snapshots.get(id(connection))
            probe = self._cheap_file_probe()
            with database_read_window(self.db_path):
                row = connection.execute("PRAGMA data_version").fetchone()
                data_version = int(row[0]) if row else -1
                commit_epoch, committed_signature = database_commit_state(self.db_path)
                if (
                    cached is not None and cached[0] is connection
                    and cached[2] == data_version and cached[3] == commit_epoch
                    and probe is not None
                    and len(cached) > 5 and cached[5] == probe
                ):
                    # data_version and epoch unchanged and neither the main file
                    # nor the WAL moved in size, mtime or ctime.
                    return
                probe, signature = self._consistent_snapshot_state()
        except (OSError, sqlite3.Error) as exc:
            self._mark_identity_error()
            raise SQLiteDatabaseIdentityChangedError(
                "No se pudo comprobar la generación SQLite del archivo; "
                "se rechazó el acceso por seguridad."
            ) from exc

        with self._connection_registry_lock:
            snapshot = self._connection_snapshots.get(id(connection))
            if snapshot is None or snapshot[0] is not connection:
                self._connection_snapshots[id(connection)] = (
                    connection, signature, data_version,
                    commit_epoch, committed_signature, probe,
                )
                return
            (
                _same_connection, old_signature, old_data_version,
                old_epoch, _old_committed_signature, *_rest,
            ) = snapshot
            current_epoch = commit_epoch
            changed = signature != old_signature or data_version != old_data_version
            # The sidecar signature is recorded while the cooperative writer
            # holds SQLite's write reservation. It must exactly match the file
            # observed now; this prevents a later legacy write or in-place copy
            # from piggybacking on an unrelated epoch increment.
            attested_commit = (
                current_epoch > old_epoch
                and committed_signature == signature
            )
            if changed and not attested_commit:
                self._mark_identity_error()
                raise SQLiteDatabaseIdentityChangedError(
                    "La generación del archivo cambió sin una transición de commit "
                    "SQLite verificable; se rechazó el acceso para evitar leer o "
                    "escribir sobre una sustitución in-place."
                )
            self._connection_snapshots[id(connection)] = (
                connection, signature, data_version,
                current_epoch, committed_signature, probe,
            )

    def _assert_database_identity(self, connection=None):
        expected = getattr(self, "_database_file_identity", None)
        if expected is not None:
            try:
                current = database_file_identity(self.db_path)
            except OSError:
                current = None
            if current != expected:
                self._mark_identity_error()
                raise SQLiteDatabaseIdentityChangedError(
                    "La identidad del archivo SQLite cambió desde que se abrió esta "
                    "instancia; se rechazó la operación para evitar escribir en una "
                    "generación antigua. Cierre ordenadamente el motor y vuelva a "
                    "abrirlo desde la ruta configurada. No se modificó ni reparó ningún archivo."
                )

        if getattr(self, "_journal_mode", None) == "wal":
            sidecars = getattr(self, "_sidecar_identities", None)
            if sidecars is not None:
                for suffix in ("-wal", "-shm"):
                    current = self._sidecar_file_identity(suffix)
                    expected_sidecar = sidecars.get(suffix)
                    if expected_sidecar is None:
                        # WAL/SHM pueden aparecer al primer acceso que realmente los usa.
                        # Desde ese momento se fija su identidad hasta el cierre del motor.
                        if current is not None:
                            sidecars[suffix] = current
                    elif current != expected_sidecar:
                        self._mark_identity_error()
                        raise SQLiteDatabaseIdentityChangedError(
                            "La identidad de un sidecar WAL/SHM cambió desde que fue "
                            "observado; se rechazó el acceso. No se borró ni reparó ningún archivo."
                        )
        if connection is None:
            connection = getattr(self._connection_local, "connection", None)
        self._check_in_place_change(connection)

    def _check_connection_access(self, connection):
        if getattr(self, "_close_failed", False):
            raise RuntimeError("El cierre anterior falló; solo se puede reintentar el cierre")
        if getattr(self._operation_local, "depth", 0):
            self._ensure_database_identity_for_db_access(connection=connection)
        else:
            self._assert_database_identity(connection=connection)

    def _open_connection(self):
        conn = open_writer(
            self.db_path,
            timeout=60,
            busy_timeout_ms=30_000,
            consumer="memory_store",
            check_same_thread=False,
        )
        try:
            conn.execute("PRAGMA synchronous=NORMAL")
            is_primary_thread = threading.get_ident() == self._primary_thread_id
            # Mantener el presupuesto histórico del hilo principal; limitar las
            # conexiones auxiliares para que el caché máximo no se multiplique
            # por cada worker MCP.
            conn.execute(f"PRAGMA cache_size={-64000 if is_primary_thread else -8000}")
            conn.execute(f"PRAGMA mmap_size={268435456 if is_primary_thread else 33554432}")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.create_function("PALABRA_COMPLETA", 2, _sql_palabra_completa)
            conn.create_function("PALABRA_PREFIJO", 2, _sql_palabra_prefijo)
            conn.create_function("PALABRA_INICIO_ANCHO", 2, _sql_palabra_inicio_ancho)
            return conn
        except BaseException:
            conn.close()
            raise

    def _get_thread_state(self):
        local = self._connection_local
        conn = getattr(local, "connection", None)
        cursor = getattr(local, "cursor", None)
        if conn is not None and cursor is not None:
            if self._closed:
                raise RuntimeError("La instancia SQLiteMemoryBioRAG ya fue cerrada")
            return conn, cursor

        with self._connection_registry_lock:
            if self._closed:
                raise RuntimeError("La instancia SQLiteMemoryBioRAG ya fue cerrada")
            expected_identity = getattr(self, "_database_file_identity", None)
            if expected_identity is not None:
                validation_connection = getattr(local, "connection", None)
                if validation_connection is None and self._connections:
                    validation_connection = self._connections[0]
                self._assert_database_identity(connection=validation_connection)
            if self._is_memory_database:
                conn = self._memory_connection
                if conn is None:
                    conn = self._open_connection()
                    self._memory_connection = conn
                    self._connections.append(conn)
            else:
                conn = self._open_connection()
                try:
                    if expected_identity is not None:
                        self._assert_database_identity()
                except BaseException:
                    conn.close()
                    raise
                self._connections.append(conn)
            cursor = conn.cursor()
            local.connection = conn
            local.cursor = cursor
            return conn, cursor

    def __init__(self, db_path=None):
        from core.paths import resolve_db_path
        self.db_path = resolve_db_path(db_path)
        if self.db_path != ":memory:":
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        # Conexión/cursor por hilo para la DB persistente. En :memory: se conserva
        # una conexión compartida, protegida por el lock de operación.
        self._is_memory_database = self.db_path == ":memory:"
        self._primary_thread_id = threading.get_ident()
        self._connection_local = threading.local()
        self._request_local = threading.local()
        self._operation_local = threading.local()
        self._method_wrapper_cache = {}
        self._connection_registry_lock = threading.RLock()
        self._connection_guards = {}
        self._connection_snapshots = {}
        self._generation_guard_ready = False
        self._lifecycle_condition = threading.Condition(threading.RLock())
        self._memory_operation_lock = threading.RLock()
        self._connections = []
        self._memory_connection = None
        self._active_operations = 0
        self._closing = False
        self._closing_owner = None
        self._closed = False
        self._close_failed = False
        self._close_checkpoint_complete = False
        self._close_pending = None
        self._last_defaults = {}
        self._persistente = False

        # Toda conexión escritora pasa por la política version-aware y registra
        # las funciones SQL propias; también se aplica a conexiones de otros hilos.
        self._get_thread_state()
        try:
            self._database_file_identity = database_file_identity(self.db_path)
        except OSError:
            self.cerrar_sistema()
            raise
        row = self.conn.execute("PRAGMA journal_mode").fetchone()
        self._journal_mode = str(row[0]).lower() if row and row[0] else "unknown"
        self._sidecar_identities = {}
        self._capture_sidecar_identities()
        self._cat_cache = {}
        self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='largo_plazo'")
        if not self.cursor.fetchone():
            self._crear_estructura_cerebral()
        self._crear_tablas_nuevas_si_faltan()
        # Trazaabilidad: datos de la última búsqueda para mcp_server.py
        self.last_todos = []
        self.last_origen_scores = {}
        # Signal #14 (v29): metadatos del contrato de degradación asociativa.
        # Con flag OFF queda con valores vacíos por defecto; con flag ON, el
        # último enriquecimiento ADN deja aquí su estado epistémico (Política A).
        self.last_estado_epistemico = {
            "estado": "no_evaluado",
            "confianza_epistemica": 0.0,
            "indice_adn_listo": False,
            "tipo_relacion_por_concepto": {},
            "genes_compartidos_por_concepto": {},
            "candidatos_adn_consultados": 0,
        }
        self.last_parent_map = {}  # parent pointers from last spreading activation
        # Buffer circular de memoria de trabajo (v19.0 Context Window)
        self._context_window = deque(maxlen=10)
        self.dmn = None
        self._dmn_sintesis_hecha = False
        if constants.DMN_SINTESIS_ACTIVA:
            try:
                from core.dmn_engine import sintetizar_sinapsis_dmn
                sintetizar_sinapsis_dmn(self, max_n=constants.DMN_SINTESIS_MAX)
                self._dmn_sintesis_hecha = True
            except Exception:
                pass
        # v22.1: Cache for thematic scores (precomputed once)
        self._thematic_scores_cache = None
        self._thematic_profiles_cache = None
        self._thematic_idf_cache = None
        # Signal #13 (v26.0): Índice de vectores PPMI+SVD (lazy-loaded, ~320KB en RAM)
        # Solo se carga si BIORAG_PPMI_WEIGHT > 0 para cero overhead cuando está OFF
        self._ppmi_index = None
        if constants.PPMI_VECTOR_WEIGHT > 0.0:
            try:
                from core.ppmi_hybrid_search import IndicesBioRAG
                self._ppmi_index = IndicesBioRAG(str(self.db_path))
            except Exception:
                pass  # Silencioso: si la tabla no existe aún, se crea en el próximo sueño

        # v26.1: Neocórtex de Sangre y ADN Conceptual (solo si PPMI está activo:
        # el ADN se construye sobre vectores PPMI/SVD, sin ellos no tiene señales)
        self.neocortex = None
        self.adn_engine = None
        if self._ppmi_index is not None:
            try:
                from core.neocortex_teleologico import NeocortexTeleologico
                from core.adn_conceptual import ADNConceptualEngine
                self.neocortex = NeocortexTeleologico(str(self.db_path))
                self.adn_engine = ADNConceptualEngine(db_path=str(self.db_path), indices=self._ppmi_index)
                # El índice ADN v29 se carga desde artefactos persistidos; nunca se recalcula aquí.
                self._adn_pendiente_recalculo = False
            except Exception as e:
                logger.warning(f"No se pudo inicializar el Neocórtex de Sangre: {e}")

        # v28.1: Componentes de calibración y decisión estadística (FP controlado)
        self._platt_calibrador = None
        self._umbral_conforme = None
        self._fusion_logistica = None
        self._calibracion_entrenada = False
        self._calibracion_meta = None

        # v28.1: Cargar calibración persistida si existe (rápida, sin búsquedas).
        # Esto le da al path caliente el umbral/Platt ya calibrados contra el
        # corpus del momento en que se persistieron. Si el corpus creció o se
        # redujo después, `calibrar_y_persistir()` lo detecta por n_nodos y
        # recalcula la garantía.
        try:
            if getattr(self, 'cursor', None) is not None:
                self._cargar_calibracion_persistida()
        except Exception as _e_cal:
            logger.debug(f"Calibración persistida no cargada: {_e_cal}")
        # Captura WAL/SHM y firma de archivo tras el bootstrap, cuando SQLite ya pudo crearlos.
        self._capture_sidecar_identities()
        self._generation_guard_ready = True
        for connection in tuple(self._connections):
            self._remember_connection_snapshot(connection)

    def notificar_actividad_usuario(self):
        return dmn.notificar_actividad_usuario(self)

    def iniciar_dmn(self, idle_seconds=300):
        return dmn.iniciar_dmn(self, idle_seconds=idle_seconds)

    def detener_dmn(self):
        return dmn.detener_dmn(self)

    def registrar_acceso_contexto(self, concepto: str):
        return dmn.registrar_acceso_contexto(self, concepto=concepto)

    def obtener_bonus_contexto(self, concepto: str) -> float:
        return dmn.obtener_bonus_contexto(self, concepto=concepto)


    def _resolver_categoria_id(self, nombre):
        return catalog_methods._resolver_categoria_id(self, nombre)

    def listar_categorias(self):
        return catalog_methods.listar_categorias(self)

    def _resolver_dimension_ids(self, tipo_nombre, valores_str):
        return catalog_methods._resolver_dimension_ids(self, tipo_nombre, valores_str)

    def _obtener_arbol_dimensiones(self):
        return catalog_methods._obtener_arbol_dimensiones(self)

    def sync_status(self):
        return catalog_methods.sync_status(self)

    def sync_marcado(self, categoria_ids):
        return catalog_methods.sync_marcado(self, categoria_ids)

    def sync_limpiar(self):
        return catalog_methods.sync_limpiar(self)


    def _cargar_firmas_adn(self):
        return adn._cargar_firmas_adn(self)

    def _persistir_firma_adn(self, concepto: str, firma: dict):
        return adn._persistir_firma_adn(self, concepto=concepto, firma=firma)


    def _crear_estructura_cerebral(self):
        return schema._crear_estructura_cerebral(self)

    def _crear_tabla_data(self):
        return schema._crear_tabla_data(self)

    # =========================================================================
    # TECNOLOGÍA COGNITIVA: Ley de Potencia de Práctica de ACT-R (Anderson & Lebiere, 1998)
    # Modelo formal de activación de nivel base (Base-Level Activation) y retención biológica:
    # B_i = ln( \sum_{k=1}^n t_k^{-d} ), con d = 0.5.
    # Modula la tasa de olvido pasivo (LTD) en el ciclo de consolidación de sueño.
    # =========================================================================

    def _registrar_acceso_nodo(self, concepto: str, ts: float = None):
        return dmn._registrar_acceso_nodo(self, concepto=concepto, ts=ts)


    def _calcular_base_level_actr(self, concepto: str, ahora: float = None):
        return consolidation._calcular_base_level_actr(self, concepto=concepto, ahora=ahora)


    def _crear_tablas_nuevas_si_faltan(self):
        return schema._crear_tablas_nuevas_si_faltan(self)

    def _asegurar_catalogo_dimensiones(self):
        return schema._asegurar_catalogo_dimensiones(self)

    def _idf_tokens_qcr(self, tokens):
        return scoring._idf_tokens_qcr(self, tokens=tokens)

    def _calcular_jaccard(self, str1, str2):
        return scoring._calcular_jaccard(self, str1=str1, str2=str2)


    def _buscar_en_contenido(self, query, solo_activos=True):
        return search._buscar_en_contenido(self, query=query, solo_activos=solo_activos)

    def _buscar_todos_en_contenido(self, query, solo_activos=True):
        return search._buscar_todos_en_contenido(self, query=query, solo_activos=solo_activos)

    def buscar_recuerdo_microsegundos(self, concepto):
        return search.buscar_recuerdo_microsegundos(self, concepto=concepto)

    def buscar_todos_recuerdos(self, concepto):
        return search.buscar_todos_recuerdos(self, concepto=concepto)

    def buscar_por_predicados(self, sujeto=None, accion=None, objeto=None, contexto=None, limite=10):
        return search.buscar_por_predicados(self, sujeto=sujeto, accion=accion, objeto=objeto, contexto=contexto, limite=limite)

    def _fallback_busqueda_predicados(self, frase, limite=10):
        return search._fallback_busqueda_predicados(self, frase=frase, limite=limite)

    def buscar_por_tokens(self, tokens, modo="relaxed", profundidad="activos", limite=3, pagina=1):
        return search.buscar_por_tokens(self, tokens=tokens, modo=modo, profundidad=profundidad, limite=limite, pagina=pagina)

    def buscar_recuerdo_profundo(self, concepto):
        return search.buscar_recuerdo_profundo(self, concepto=concepto)

    def percibir_corto_plazo(self, concepto, contenido, sinonimos="", categoria="General", dimensiones=None, predicados=None, valencia_somatica=0.0, sustantivos_clave="", sustantivos_clave_exactos=None):
        return ingest.percibir_corto_plazo(
            self,
            concepto=concepto,
            contenido=contenido,
            sinonimos=sinonimos,
            categoria=categoria,
            dimensiones=dimensiones,
            predicados=predicados,
            valencia_somatica=valencia_somatica,
            sustantivos_clave=sustantivos_clave,
            sustantivos_clave_exactos=sustantivos_clave_exactos,
        )

    def consolidar_concepto(self, concepto):
        return ingest.consolidar_concepto(self, concepto=concepto)


    def _auto_generar_co_ocurrencia(self, recuerdos_sesion):
        return consolidation._auto_generar_co_ocurrencia(self, recuerdos_sesion=recuerdos_sesion)

    def _clasificar_nodo_wordnet(self, concepto, contenido, sinonimos=""):
        return consolidation._clasificar_nodo_wordnet(self, concepto=concepto, contenido=contenido, sinonimos=sinonimos)

    def _crear_tabla_historial_si_falta(self):
        return telemetry._crear_tabla_historial_si_falta(self)

    def ciclo_sueno_consolidacion(self):
        return consolidation.ciclo_sueno_consolidacion(self)


    def aplicar_refuerzo_dopaminergico(self, concepto: str, exito: bool, motivo: str = None) -> bool:
        return synapses.aplicar_refuerzo_dopaminergico(self, concepto, exito, motivo)

    def _reconstruir_camino(self, destino):
        return synapses._reconstruir_camino(self, destino)

    def establecer_asociacion(self, concepto_a, concepto_b):
        return synapses.establecer_asociacion(self, concepto_a, concepto_b)

    # ─── CANAL DE COMUNICACION INTER-AGENTE ──────────────────────────────

    def _crear_tabla_comunicaciones(self):
        return comms._crear_tabla_comunicaciones(self)

    def enviar_comunicado(self, origen, destino, contenido):
        return comms.enviar_comunicado(self, origen, destino, contenido)

    def leer_comunicados(self, destino=None, solo_no_leidos=False, ultimos=10, agente=None):
        return comms.leer_comunicados(self, destino=destino, solo_no_leidos=solo_no_leidos, ultimos=ultimos, agente=agente)

    def marcar_como_leido(self, ids, agente=None):
        return comms.marcar_como_leido(self, ids, agente=agente)

    # ─── FULL-TEXT SEARCH (FTS5) ─────────────────────────────────

    def _crear_tabla_fts(self):
        return schema._crear_tabla_fts(self)

    def _poblar_fts(self):
        return schema._poblar_fts(self)

    def _poblar_fts_unicode(self):
        return schema._poblar_fts_unicode(self)

    def _crear_tabla_metricas(self):
        return dmn._crear_tabla_metricas(self)


    def _agregar_prefix_wildcards(self, query):
        return scoring._agregar_prefix_wildcards(self, query=query)

    def _pesar_tokens_query(self, frase):
        return scoring._pesar_tokens_query(self, frase=frase)


    def _evocacion_por_cadena(self, semillas, max_saltos=None, limite=None):
        return synapses._evocacion_por_cadena(self, semillas, max_saltos=max_saltos, limite=limite)

    @staticmethod
    def _ncd_sim(a, b, level=None):
        return scoring._ncd_sim(a=a, b=b, level=level)

    def _ncd_sims_pool(self, query, filas):
        return scoring._ncd_sims_pool(self, query=query, filas=filas)

    @staticmethod
    def _jsd_weight_adaptativo(query, n_tokens=None):
        return scoring._jsd_weight_adaptativo(query=query, n_tokens=n_tokens)

    def _ts_nodo(self, concepto):
        return episodes._ts_nodo(self, concepto)

    def _expandir_episodio_temporal(self, nodo_ancla, ventana_horas=None, limite_episodio=None):
        return episodes._expandir_episodio_temporal(self, nodo_ancla, ventana_horas=ventana_horas, limite_episodio=limite_episodio)

    def _afinidad_temporal_pool(self, conceptos):
        return episodes._afinidad_temporal_pool(self, conceptos)

    def _analogia_scores_pool(self, v_target, pool):
        return scoring._analogia_scores_pool(self, v_target=v_target, pool=pool)


    def _generar_variaciones(self, query, historial_fallos=None):
        return search._generar_variaciones(self, query=query, historial_fallos=historial_fallos)

    @staticmethod
    def _calcular_jsd(query_text: str, node_text: str) -> float:
        return scoring._calcular_jsd(query_text=query_text, node_text=node_text)

    @staticmethod
    def _calcular_bm25_bayesiano(raw_scores: dict, alpha: float = 1.0) -> dict:
        return scoring._calcular_bm25_bayesiano(raw_scores=raw_scores, alpha=alpha)

    def _calcular_score_hibrido(self, bm25_norm=0.0, dim_score=0.0,
                                peso_sinaptico=0.0, concepto_ratio=0.0,
                                sinonimos_ratio=0.0, score_latente=0.0,
                                score_cadena=0.0, temporal=0.0,
                                asoc_count=0, match_exacto=False,
                                grupo_score=0.0, tematico_score=0.0,
                                jsd_score: float = 0.0,
                                jsd_weight: float = 0.0,
                                pred_score: float = 0.0,
                                ppmi_score: float = 0.0,
                                hub_match: float = 0.0,
                                ncd_score: float = 0.0,
                                episodio_score: float = 0.0,
                                analogia_score: float = 0.0,
                                campo_score: float = 0.0):
        return scoring._calcular_score_hibrido(
            self,
            bm25_norm=bm25_norm,
            dim_score=dim_score,
            peso_sinaptico=peso_sinaptico,
            concepto_ratio=concepto_ratio,
            sinonimos_ratio=sinonimos_ratio,
            score_latente=score_latente,
            score_cadena=score_cadena,
            temporal=temporal,
            asoc_count=asoc_count,
            match_exacto=match_exacto,
            grupo_score=grupo_score,
            tematico_score=tematico_score,
            jsd_score=jsd_score,
            jsd_weight=jsd_weight,
            pred_score=pred_score,
            ppmi_score=ppmi_score,
            hub_match=hub_match,
            ncd_score=ncd_score,
            episodio_score=episodio_score,
            analogia_score=analogia_score,
            campo_score=campo_score,
        )


    # =============================================================================
    # v28.1: Calibración de probabilidad y decisión con garantía (FP controlado)
    # =============================================================================

    def _preparar_datos_calibracion(self, n_calibracion: int = 500) -> tuple:
        return umbral._preparar_datos_calibracion(self, n_calibracion=n_calibracion)

    def entrenar_calibracion(self, n_calibracion: int = 500, metodo: str = "platt") -> bool:
        return umbral.entrenar_calibracion(self, n_calibracion=n_calibracion, metodo=metodo)

    def calibrar_umbral_conforme(self, alpha: float = None, n_negativos: int = 100) -> float:
        return umbral.calibrar_umbral_conforme(self, alpha=alpha, n_negativos=n_negativos)

    def _score_con_calibracion(self, score_bruto: float) -> float:
        return umbral._score_con_calibracion(self, score_bruto=score_bruto)

    UMBRAL_COLD_START = 0.65

    def _debe_responder(self, score: float) -> bool:
        return umbral._debe_responder(self, score=score)

    def buscar_con_calibracion(self, query: str, limite: int = 10,
                               usar_calibracion: bool = True) -> list:
        return umbral.buscar_con_calibracion(self, query=query, limite=limite, usar_calibracion=usar_calibracion)

    # =============================================================================
    # v28.1: Calibración dinámica persistente — garantía FP independiente del corpus
    # =============================================================================

    def _contar_nodos_corpus(self) -> int:
        return umbral._contar_nodos_corpus(self)

    def _cargar_calibracion_persistida(self) -> bool:
        return umbral._cargar_calibracion_persistida(self)

    def _persistir_calibracion(self, n_positivos: int, metodo: str = "conforme") -> None:
        return umbral._persistir_calibracion(self, n_positivos=n_positivos, metodo=metodo)

    def calibrar_y_persistir(self, alpha: float = None, n_negativos: int = 40,
                             n_positivos_max: int = 300,
                             recalcular_si_drift: bool = True,
                             force: bool = False) -> dict:
        return umbral.calibrar_y_persistir(
            self,
            alpha=alpha,
            n_negativos=n_negativos,
            n_positivos_max=n_positivos_max,
            recalcular_si_drift=recalcular_si_drift,
            force=force,
        )

    def nivel_certeza(self, score: float) -> str:
        return umbral.nivel_certeza(self, score=score)

    def confianza_calibrada(self, score: float) -> float:
        return umbral.confianza_calibrada(self, score=score)

    def expandir_contexto_vecinos(self, pagina_resultados, depth, profundidad="activos", preview_chars=None):
        return synapses.expandir_contexto_vecinos(self, pagina_resultados, depth, profundidad=profundidad, preview_chars=preview_chars)

    def _expandir_contexto_bfs(self, pagina_resultados, depth, profundidad="activos", preview_chars=None):
        return synapses._expandir_contexto_bfs(self, pagina_resultados, depth, profundidad=profundidad, preview_chars=preview_chars)

    def _rerank_jaccard_protect_r0(self, resultados, frase_limpia, preview_chars=1500):
        return scoring._rerank_jaccard_protect_r0(self, resultados=resultados, frase_limpia=frase_limpia, preview_chars=preview_chars)


    def obtener_asociaciones_enriquecidas(self, conceptos_top, top_vecinos=5, peso_min=0.50):
        return synapses.obtener_asociaciones_enriquecidas(self, conceptos_top, top_vecinos=top_vecinos, peso_min=peso_min)

    # OPT-NUEVA-5: constates de evaluacion epistemica (Ce). Umbrales = HIPOTESIS
    # inicial documentada (sin set calibrado); ranking intacto por construccion.
    EPISTEMICO_TOP_K = 5
    EPISTEMICO_UMBRAL_CONOCIDO = 0.55
    EPISTEMICO_UMBRAL_INCERTIDUMBRE = 0.30
    EPISTEMICO_VACIOS_CAP = 200

    def _epistemico_coherencia_dimensional(self, top_conceptos):
        return context._epistemico_coherencia_dimensional(self, top_conceptos)

    def _epistemico_evaluar(self, pagina_resultados):
        return context._epistemico_evaluar(self, pagina_resultados)

    def _epistemico_publicar(self, frase, pagina_resultados, total):
        return context._epistemico_publicar(self, frase, pagina_resultados, total)

    def _epistemico_publicar_sin_consulta(self):
        return context._epistemico_publicar_sin_consulta(self)

    def _epistemico_encolar_vacio(self, frase, ce):
        return context._epistemico_encolar_vacio(self, frase, ce)


    def _multihop_vecinos(self, semillas, excluir, limite):
        return synapses._multihop_vecinos(self, semillas, excluir, limite)

    def buscar_por_frase(self, frase, profundidad="activos", pagina=1, limite=None, categoria=None, preview_chars=1500, historial_fallos=None, context_window=0, dimensiones_dict=None, dimensiones_ids=None, parafrasis_list=None, desde_ts=None, hasta_ts=None, modo_estricto=False, usar_inferencia=True, buscar_por_rol=None, ignore_peso_sinaptico=False, ordenar_por="relevancia", permitir_expansion_empate=False, expandir_episodio=False, analogia=False, sustantivos_clave_boost=None, convergencia_limite=None):
        return search.buscar_por_frase(
            self,
            frase=frase,
            profundidad=profundidad,
            pagina=pagina,
            limite=limite,
            categoria=categoria,
            preview_chars=preview_chars,
            historial_fallos=historial_fallos,
            context_window=context_window,
            dimensiones_dict=dimensiones_dict,
            dimensiones_ids=dimensiones_ids,
            parafrasis_list=parafrasis_list,
            desde_ts=desde_ts,
            hasta_ts=hasta_ts,
            modo_estricto=modo_estricto,
            usar_inferencia=usar_inferencia,
            buscar_por_rol=buscar_por_rol,
            ignore_peso_sinaptico=ignore_peso_sinaptico,
            ordenar_por=ordenar_por,
            permitir_expansion_empate=permitir_expansion_empate,
            expandir_episodio=expandir_episodio,
            analogia=analogia,
            sustantivos_clave_boost=sustantivos_clave_boost,
            convergencia_limite=convergencia_limite,
        )

    def obtener_provenance_ultimo_resultado(self) -> dict:
        return telemetry.obtener_provenance_ultimo_resultado(self)

    def _enriquecer_con_adn(self, query, resultados_base, limite=None):
        return adn._enriquecer_con_adn(self, query=query, resultados_base=resultados_base, limite=limite)


    def actualizar_log_busqueda(self, params_json: str):
        return telemetry.actualizar_log_busqueda(self, params_json)

    def validar_rafaga(self, rafaga_palabras):
        return rafaga.validar_rafaga(self, rafaga_palabras=rafaga_palabras)

    def buscar_por_rafaga(self, query, rafaga_palabras, pagina=1, limite=None, dimensiones_ids=None):
        return rafaga.buscar_por_rafaga(
            self,
            query=query,
            rafaga_palabras=rafaga_palabras,
            pagina=pagina,
            limite=limite,
            dimensiones_ids=dimensiones_ids,
        )


    # ─── AUTO-MANTENIMIENTO Y EVICCION ──────────────────────────

    def _benchmark_rendimiento(self):
        return telemetry._benchmark_rendimiento(self)

    def _candidatos_eviccion(self, limite=5):
        return quarantine._candidatos_eviccion(self, limite=limite)

    def _ejecutar_eviccion(self, max_borrar=10):
        return quarantine._ejecutar_eviccion(self, max_borrar=max_borrar)

    def _ultimo_benchmark(self):
        return telemetry._ultimo_benchmark(self)

    def purgar_cuarentena_vencida(self) -> int:
        return quarantine.purgar_cuarentena_vencida(self)

    def mover_a_cuarentena(self, concepto: str, dias_expiracion: int = 30) -> bool:
        return quarantine.mover_a_cuarentena(self, concepto=concepto, dias_expiracion=dias_expiracion)

    def rescatar_de_cuarentena(self, concepto: str) -> bool:
        return quarantine.rescatar_de_cuarentena(self, concepto=concepto)

    def buscar_en_cuarentena(self, frase: str, limite: int = 3):
        return quarantine.buscar_en_cuarentena(self, frase=frase, limite=limite)

    def _consolidar_antes_de_cerrar(self, connections):
        """Deja el diario vacío para que el `.db` sea autosuficiente al cerrar.

        Motivo: si el motor termina con un `-wal` con datos y ese archivo se
        copia, se versiona o se sincroniza aparte del `.db`, el diario puede
        acabar junto a otra versión del archivo principal. Al reabrir, SQLite
        aplica ese diario ajeno y la base termina con datos que no le
        corresponden. Consolidar al cerrar hace que ese estado no llegue a
        existir.

        Es best-effort y nunca impide cerrar: si falla (base en solo lectura,
        otro proceso trabajando, plataforma sin soporte) se registra y se sigue.
        """
        if getattr(self, "_is_memory_database", False):
            return
        for conn in connections:
            try:
                if getattr(conn, "in_transaction", False):
                    continue
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchall()
            except sqlite3.Error as exc:
                logger.debug("No se pudo consolidar el WAL al cerrar: %s", exc)

    def cerrar_sistema(self):
        """Espera operaciones activas y cierra todas las conexiones de la instancia."""
        if getattr(self, "_persistente", False):
            return
        if (getattr(self._operation_local, "depth", 0)
                or getattr(self._operation_local, "dbapi_depth", 0)):
            raise RuntimeError("cerrar_sistema no puede ejecutarse desde una operación activa")

        with self._lifecycle_condition:
            while self._closing:
                if self._closing_owner == threading.get_ident():
                    raise RuntimeError("cerrar_sistema no puede reentrar en su propio cierre")
                self._lifecycle_condition.wait()
            if self._closed:
                return
            self._closing = True
            self._closing_owner = threading.get_ident()
            try:
                limite = time.monotonic() + _CIERRE_DRENAJE_SEGUNDOS
                while self._active_operations:
                    restante = limite - time.monotonic()
                    if restante <= 0:
                        raise TimeoutError("No terminó el drenaje de operaciones; no se cerraron conexiones")
                    self._lifecycle_condition.wait(restante)
                with self._connection_registry_lock:
                    if self._close_pending is None:
                        self._close_pending = list(self._connections)
            except BaseException:
                self._close_failed = True
                self._closing = False
                self._closing_owner = None
                self._lifecycle_condition.notify_all()
                raise

        try:
            # Si un cierre parcial falló, sus conexiones ya cerradas no deben
            # volver a usarse para el checkpoint durante el reintento.
            if not self._close_checkpoint_complete:
                self._consolidar_antes_de_cerrar(tuple(self._close_pending))
                self._close_checkpoint_complete = True
            while self._close_pending:
                conn = self._close_pending[0]
                conn.close()
                self._close_pending.pop(0)
            with self._lifecycle_condition:
                self._closed = True
                self._close_failed = False
        except BaseException:
            # Bloquear operaciones también después de liberar _closing: una
            # conexión puede haberse cerrado antes de que otra fallara.
            with self._lifecycle_condition:
                self._close_failed = True
            raise
        finally:
            with self._lifecycle_condition:
                self._closing = False
                self._closing_owner = None
                self._lifecycle_condition.notify_all()
