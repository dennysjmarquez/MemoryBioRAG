"""Servicio único de lectura/escritura para MCP, CLI y dashboard.

POR QUÉ (Fase A): el dashboard escribía LIKE/INSERT crudo y se saltaba
buscar_por_frase, consolidación, dirty-set SDM y procedencia. Este módulo
no cambia la inteligencia: solo cablea las mismas primitivas del motor.

`sinapsis` es la fuente canónica del grafo. `largo_plazo.asociaciones` es
espejo histórico (core.sinapsis._sincronizar_asociaciones), no se muta
directamente desde este servicio.

Singleton: Kilo/VS Code dispara tools en paralelo. Reconstruir
SQLiteMemoryBioRAG en cada tool (~6–11s) causa MCP -32001 timeout.
Una instancia por db_path; cerrar_sistema() es no-op en ella.

F2 — Idle Lease Release:
  Tras BIORAG_IDLE_TIMEOUT_SECONDS (default 30) de inactividad, el
  singleton libera la conexión SQLite y el lease compartido sin destruir
  el objeto ni los índices en RAM.  Al llegar el primer request siguiente
  se re-abre la conexión en ~2 ms (medido 2026-11-24 en DB de 135 MB):
    managed_connect + PRAGMAs + 3 funciones SQL ≈ 2 ms
  Si user_version cambió durante la inactividad (update aplicado),
  el objeto se descarta y se devuelve "reloading" al cliente, evitando
  la recarga bloqueante de 11.6 s dentro del timeout MCP.
"""
from __future__ import annotations

import logging
import os
import re
import threading
import unicodedata
from contextlib import contextmanager
from typing import Optional

from core.identidad_unicode import normalizar_identidad
from core.paths import resolve_db_path

logger = logging.getLogger("BioRAG.MemoryService")

_lock = threading.RLock()
_cerebro = None
_path = None
_idle_timer: Optional[threading.Timer] = None
_in_flight_count = 0
_in_flight_lock = threading.Lock()

# Idle timeout: seconds of inactivity before releasing the SQLite connection.
# Set to 0 to disable idle release (e.g. for tests or CLI).
_IDLE_TIMEOUT = int(os.environ.get("BIORAG_IDLE_TIMEOUT_SECONDS", "30"))


# ---------------------------------------------------------------------------
# Internal helpers & request tracking
# ---------------------------------------------------------------------------

@contextmanager
def active_request():
    """Rastrea peticiones en curso para que el timer de reposo no cierre la conexión a mitad de ejecución."""
    global _in_flight_count
    with _in_flight_lock:
        _in_flight_count += 1
    try:
        yield
    finally:
        with _in_flight_lock:
            _in_flight_count -= 1
            is_zero = (_in_flight_count == 0)
        if is_zero:
            with _lock:
                _schedule_idle_release()


def _cancel_idle_timer() -> None:
    """Cancel any pending idle timer (must be called under _lock)."""
    global _idle_timer
    if _idle_timer is not None:
        _idle_timer.cancel()
        _idle_timer = None


def _schedule_idle_release() -> None:
    """Arm (or re-arm) the idle timer (must be called under _lock)."""
    global _idle_timer
    if _IDLE_TIMEOUT <= 0:
        return
    _cancel_idle_timer()
    _idle_timer = threading.Timer(_IDLE_TIMEOUT, _idle_release_callback)
    _idle_timer.daemon = True
    _idle_timer.start()


def _idle_release_callback() -> None:
    """Called by the idle timer thread: release the SQLite connection."""
    with _lock:
        global _idle_timer
        _idle_timer = None
        with _in_flight_lock:
            if _in_flight_count > 0:
                # Petición en vuelo: no cerrar, rearmar el timer y salir
                _schedule_idle_release()
                return
        if _cerebro is None or getattr(_cerebro, '_conn_released', False):
            return
        try:
            _cerebro.conn.close()   # ManagedConnection.close() releases the shared lease
        except Exception:
            pass
        _cerebro._conn_released = True
        logger.debug("BioRAG idle: SQLite connection and shared lease released.")


def _reopen_connection() -> bool:
    """Re-open SQLite connection after idle release.  Called under _lock.

    Returns True if the connection was restored and the caller can proceed.
    Returns False if user_version changed (schema update detected): the
    singleton has been discarded via reset_cerebro(); caller must signal
    the MCP client to retry.
    """
    global _cerebro, _path
    if _cerebro is None or not getattr(_cerebro, '_conn_released', False):
        return True  # nothing to do

    from core.database_access import connect as managed_connect

    try:
        new_conn = managed_connect(_path, timeout=60, check_same_thread=False)
    except Exception as exc:
        logger.warning("BioRAG idle re-open failed: %s", exc)
        return True  # keep serving with stale conn until next attempt

    # --- Check user_version for schema change during idle ---
    try:
        new_ver = new_conn.execute("PRAGMA user_version;").fetchone()[0]
    except Exception:
        new_ver = getattr(_cerebro, '_schema_version_at_open', 0)

    old_ver = getattr(_cerebro, '_schema_version_at_open', 0)
    if new_ver != old_ver:
        # Schema changed while idle (e.g. biorag update ran).
        # Discard singleton; next get_cerebro() will rebuild (~11.6 s).
        logger.info(
            "BioRAG schema updated during idle (user_version %s → %s): "
            "discarding singleton for clean reload.",
            old_ver, new_ver,
        )
        try:
            new_conn.close()
        except Exception:
            pass
        # reset_cerebro() needs _lock — we are already under it, use inline reset.
        try:
            _cerebro._persistente = False
            _cerebro.cerrar_sistema()
        except Exception:
            pass
        _cerebro = None
        _path = None
        return False  # signal: singleton gone, caller must rebuild

    # --- Restore connection on existing object (no RAM rebuild needed) ---
    # Apply PRAGMAs matching __init__.
    try:
        new_conn.execute("PRAGMA journal_mode=WAL")
        new_conn.execute("PRAGMA synchronous=NORMAL")
        new_conn.execute("PRAGMA busy_timeout=30000")
        new_conn.execute("PRAGMA cache_size=-64000")
        new_conn.execute("PRAGMA mmap_size=268435456")
        new_conn.execute("PRAGMA foreign_keys = ON")
    except Exception:
        pass

    # Re-register the three custom SQL functions defined in SQLiteMemoryBioRAG.__init__.
    def _palabra_completa(token, texto):
        if not token or not texto:
            return 0
        tn = token.lower().replace("_", " ").replace("-", " ")
        tx = texto.lower().replace("_", " ").replace("-", " ")
        return 1 if re.search(r"\b" + re.escape(tn) + r"\b", tx) else 0

    def _palabra_prefijo(token, texto):
        if not token or not texto:
            return 0
        tn = token.lower().replace("_", " ").replace("-", " ")
        tx = texto.lower().replace("_", " ").replace("-", " ")
        return 1 if re.search(r"\b" + re.escape(tn), tx) else 0

    def _palabra_inicio_ancho(token, texto):
        if not token or not texto:
            return 0
        tn = token.lower().replace("_", " ").replace("-", " ")
        tx = texto.lower().replace("_", " ").replace("-", " ")
        patron = re.compile(r"\b" + re.escape(tn))
        pos = tx.find(tn)
        while pos >= 0:
            if patron.match(tx, pos) or (
                pos > 0 and unicodedata.east_asian_width(tx[pos - 1]) in ("W", "F")
            ):
                return 1
            pos = tx.find(tn, pos + 1)
        return 0

    try:
        new_conn.create_function("PALABRA_COMPLETA", 2, _palabra_completa)
        new_conn.create_function("PALABRA_PREFIJO", 2, _palabra_prefijo)
        new_conn.create_function("PALABRA_INICIO_ANCHO", 2, _palabra_inicio_ancho)
    except Exception:
        pass

    _cerebro.conn = new_conn
    _cerebro.cursor = new_conn.cursor()
    _cerebro._conn_released = False
    logger.debug("BioRAG idle: SQLite connection restored (~2 ms).")
    return True


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def reset_cerebro():
    """Tests / cambio de BIORAG_PATH: suelta el singleton."""
    global _cerebro, _path, _in_flight_count
    with _lock:
        _cancel_idle_timer()
        with _in_flight_lock:
            _in_flight_count = 0
        if _cerebro is not None:
            try:
                _cerebro._persistente = False
                _cerebro.cerrar_sistema()
            except Exception:
                pass
        _cerebro = None
        _path = None


# Sentinel returned when the connection is being rebuilt after a schema update.
RELOADING_SENTINEL = object()


def get_cerebro(db_path: Optional[str] = None):
    """Instancia persistente de SQLiteMemoryBioRAG (thread-safe).

    Returns RELOADING_SENTINEL (not SQLiteMemoryBioRAG) when the schema
    changed during idle and a full rebuild is in progress.  MCP callers
    must check for this and return a "retry in a few seconds" response.
    """
    global _cerebro, _path
    from core.memory_store import SQLiteMemoryBioRAG

    path = resolve_db_path(db_path)
    with _lock:
        # Re-arm idle timer on every access.
        _schedule_idle_release()

        # Path changed: replace singleton.
        if _cerebro is not None and _path != path:
            _cancel_idle_timer()
            try:
                _cerebro._persistente = False
                _cerebro.cerrar_sistema()
            except Exception:
                pass
            _cerebro = None
            _path = None

        # Singleton exists: re-open connection if released by idle.
        if _cerebro is not None:
            ok = _reopen_connection()
            if not ok:
                # Schema changed during idle: singleton was discarded.
                # Return sentinel so MCP callers can respond "retry in a few
                # seconds" without blocking on a full 11.6 s rebuild here.
                return RELOADING_SENTINEL
            return _cerebro

        # Build singleton (cold start or post-schema-change rebuild).
        _cerebro = SQLiteMemoryBioRAG(path)
        _cerebro._persistente = True
        # Snapshot the schema version for idle re-open checks.
        try:
            _cerebro._schema_version_at_open = (
                _cerebro.conn.execute("PRAGMA user_version;").fetchone()[0]
            )
        except Exception:
            _cerebro._schema_version_at_open = 0
        _cerebro._conn_released = False
        _path = path
        return _cerebro


def buscar(cerebro, frase: str, **kwargs):
    """Recuperación híbrida común. Siempre pasa por buscar_por_frase()."""
    return cerebro.buscar_por_frase(frase, **kwargs)


def aprender(
    cerebro,
    concepto: str,
    contenido: str,
    sinonimos: str = "",
    categoria: str = "General",
    dimensiones=None,
    predicados=None,
    consolidar: bool = True,
):
    """Escritura canónica: corto plazo → (opcional) consolidar_concepto.

    POR QUÉ consolidar por defecto: una interfaz que «aprende» debe dejar el
    nodo recuperable por FTS/SDM/PPMI, no solo en RAM de trabajo.
    """
    from core.memory.ingest import _comprobar_clave_legacy

    clave_original = concepto.lower().strip()
    clave_normalizada = normalizar_identidad(concepto).lower().strip()
    # El ingreso ve la forma original; luego se consolida esa misma clave elegida.
    cerebro.percibir_corto_plazo(
        concepto, contenido, sinonimos or "", categoria, dimensiones, predicados
    )
    clave = _comprobar_clave_legacy(cerebro, clave_original, clave_normalizada)
    if consolidar:
        cerebro.consolidar_concepto(clave)
    return {"ok": True, "concepto": clave, "consolidado": consolidar}


def ensenar_lexico(cerebro, expression_surface: str, canonical_concept: str, **kwargs):
    """Enseñanza léxica atómica (Fase B)."""
    from core.lexical_learning import ensenar_expresion

    return ensenar_expresion(cerebro, expression_surface, canonical_concept, **kwargs)


def consolidar_ciclo(cerebro):
    """Sueño completo. Todas las interfaces deben llamar esto, no SQL suelto."""
    return cerebro.ciclo_sueno_consolidacion()


def resolver_analogia(cerebro, a: str, b: str, c: str, limite: int = 5):
    """F3: A:B :: C:? por álgebra PPMI local (Plan Maestro, INVENCIÓN 5)."""
    from core.ppmi_hybrid_search import resolver_analogia_simbolica

    return resolver_analogia_simbolica(cerebro, a, b, c, limite=limite)
