"""Las dos puertas del motor: `open_writer` y `open_reader`.

Qué problema resuelve: es el único punto por el que el motor abre conexiones.
Tenerlas juntas garantiza que ninguna ruta se salte las comprobaciones: la
pertenencia del par (`pair_guard`), la política de journal (`journal`) y la
anotación de estado tras abrir.

Por qué está aquí y no en otro sitio: es la fachada del paquete. Los
consumidores importan de aquí o de `core.sqlite_runtime`, nunca de los módulos
internos.

Quién lo usa: `core/memory_store.py`, `adn_conceptual`, `dmn_engine`,
`feedback_implicito`, `neocortex_teleologico`, `ppmi_hybrid_search` y el
dashboard.

Medida con la que se aprobó: los tres escenarios de la auditora y las 55
pruebas de la capa.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from core.paths import resolve_db_path
from core.sqlite import constants as _cfg
from core.sqlite import pair_guard as _pair_guard
from core.sqlite.constants import (
    SQLiteLfsPointerError,
    SQLiteSidecarConflictError,
    _DEFAULT_BUSY_TIMEOUT_MS,
    _MAX_BUSY_TIMEOUT_MS,
    _database_existed_before_open,
    lfs_pointer_info,
    logger,
)
from core.sqlite.epoch import _database_route_id
from core.sqlite.journal import configure_writer, connection_diagnostics
from core.sqlite.tracking import _TrackedSQLiteConnection
from core.sqlite.pair_guard import (
    _has_nonempty_wal,
    _olvidar_hash_principal,
    _pair_snapshot,
    _pair_snapshot_stable,
    _save_conflict_forensics,
)


def guard_enabled() -> bool:
    """Reenvío: el interruptor se lee donde se define."""
    return _cfg.guard_enabled()


def force_open_authorized() -> bool:
    """Reenvío: la autorización se lee donde se define."""
    return _cfg.force_open_authorized()


def _pair_can_be_opened(database) -> bool:
    """Reenvío: la decisión del par se toma donde se define.

    Se reenvía en vez de importar por valor para que la comprobación sea
    sustituible en pruebas sin duplicar la lógica.
    """
    return _pair_guard._pair_can_be_opened(database)


def record_pair_state(database) -> None:
    """Reenvío: la anotación del par se hace donde se define."""
    return _pair_guard.record_pair_state(database)

def _reject_lfs_pointer(database, *, purpose: str) -> None:
    """Falla con un mensaje accionable si el archivo es un puntero de git-lfs.

    Este proyecto versiona la base con git-lfs. Al clonar sin `git lfs pull` el
    archivo son 134 bytes de texto y SQLite responde `file is not a database`,
    que no distingue "falta bajarla" de "está corrupta". No son lo mismo: en el
    primer caso no hay nada que reparar.
    """
    info = lfs_pointer_info(database)
    if info is None:
        return
    raise SQLiteLfsPointerError(
        f"El archivo no es una base de datos sino un PUNTERO de git-lfs "
        f"(oid {info.get('oid', '?')}, tamaño real "
        f"{info.get('size', '?')} bytes). Esto pasa al clonar sin descargar "
        f"los objetos LFS. No hay nada que reparar: ejecuta "
        f"`git lfs install && git lfs pull` y vuelve a intentarlo. "
        f"(apertura para {purpose})"
    )


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
    _reject_lfs_pointer(database, purpose="escritura")
    _olvidar_hash_principal(database)
    database_existed = _database_existed_before_open(database)
    if "factory" in connect_kwargs:
        raise TypeError("open_writer administra la subclase de conexión")

    # Comprobación del par ANTES de abrir: abrir con un `-wal` de otra
    # generación presente puede hacer que SQLite lo aplique sobre el archivo
    # bueno. Se decide con los archivos, sin abrirlos con SQLite.
    # Fotografía del par tomada EN EL MISMO MOMENTO que la comprobación. Se
    # volverá a tomar tras abrir: si los archivos detrás de los nombres no son
    # los mismos, la comprobación se hizo sobre unos archivos y la apertura usó
    # otros (carrera TOCTOU). Ver `_pair_identity_stable`.
    # Se fotografía SIEMPRE que haya una decisión que verificar. `deep` depende
    # de lo que asumió `_pair_can_be_opened`: con diario decide por contenido;
    # sin diario solo asume "no había diario", y eso es lo que hay que revalidar.
    #
    # Saltarse la fotografía cuando no había `-wal` dejaba sin verificar justo el
    # caso en que aparece uno antes de abrir (revisión independiente sobre
    # `3912d68`): `_pair_can_be_opened` aceptaba por ausencia de diario, el
    # diario aparecía, y `open_reader` mostraba su dato.
    con_diario = _has_nonempty_wal(database) if guard_enabled() and database_existed else False
    antes = (
        _pair_snapshot(database, deep=con_diario)
        if guard_enabled() and database_existed
        else None
    )
    if guard_enabled() and database_existed and not _pair_can_be_opened(database):
        if force_open_authorized():
            forense = _save_conflict_forensics(database, motivo="apertura_forzada")
            logger.warning(
                "Apertura forzada con un -wal no verificado (%s); constancia en %s",
                consumer, forense,
            )
        else:
            forense = _save_conflict_forensics(database, motivo="par_no_verificado")
            raise SQLiteSidecarConflictError(
                "BioRAG no abrió la base porque hay un -wal que no se puede "
                "atribuir con certeza a este archivo principal (por ejemplo, "
                "tras cambiar de rama con la base versionada, tras una caída "
                "del proceso o si quedó un cliente antiguo abierto). Abrirla "
                "así podría aplicar datos de otra versión sobre los actuales. "
                "No se movió, renombró ni borró ningún archivo; hay una "
                f"constancia con los sha256 en {forense}. Para revisar y "
                "decidir: docs/sqlite_par_no_verificado.md. Para continuar "
                "bajo tu responsabilidad: BIORAG_SQLITE_FORCE_OPEN=1."
            )

    conn = sqlite3.connect(
        database, timeout=timeout, factory=_TrackedSQLiteConnection,
        **connect_kwargs,
    )
    try:
        if antes is not None and not force_open_authorized():
            if not _pair_snapshot_stable(antes, _pair_snapshot(database, deep=con_diario)):
                # Los archivos cambiaron entre la comprobación y la apertura.
                # Esta conexión pudo aplicar un diario que no es el verificado,
                # así que no se entrega. Se cierra sin checkpoint para no
                # consolidar en el principal nada de lo aplicado.
                try:
                    conn.execute("PRAGMA wal_autocheckpoint=0")
                    conn.execute("PRAGMA query_only=ON")
                except sqlite3.Error:
                    logger.debug("No se pudo desactivar el checkpoint previo al cierre")
                conn.close()
                forense = _save_conflict_forensics(database, motivo="par_cambio_en_apertura")
                raise SQLiteSidecarConflictError(
                    "BioRAG no abrió la base porque los archivos del par "
                    "cambiaron entre la comprobación y la apertura. Algo "
                    "sustituyó el archivo en esa ventana (un `git checkout`, un "
                    "renombrado o un proceso ajeno). La conexión se cerró sin "
                    "consolidar el diario en el principal. No se movió, renombró "
                    f"ni borró ningún archivo; constancia en {forense}. Para "
                    "revisar: docs/sqlite_par_no_verificado.md. Para continuar "
                    "bajo tu responsabilidad: BIORAG_SQLITE_FORCE_OPEN=1."
                )
        policy = configure_writer(
            conn,
            database,
            busy_timeout_ms=busy_timeout_ms,
            database_existed=database_existed,
            allow_existing_journal_transition=allow_existing_journal_transition,
        )
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
    # Con el diario vacío el par es coherente por construcción: se anota.
    if guard_enabled() and not _has_nonempty_wal(database):
        record_pair_state(database)
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

    # Misma comprobación de pertenencia que `open_writer`, ANTES de abrir.
    # Motivo (revisión independiente sobre 88ef43f): un lector también abre el
    # par, y SQLite aplica el `-wal` al abrirlo igual que en escritura. Sin esta
    # comprobación, `open_reader` aceptaba un par que `open_writer` rechazaba, y
    # las lecturas veían datos de otra versión de la base. Es el mismo riesgo,
    # por la puerta de al lado.
    database_existed = _database_existed_before_open(canonical)
    # Fotografía del par junto a la comprobación, para verificar después de
    # abrir que se abrió EXACTAMENTE lo que se verificó.
    _reject_lfs_pointer(canonical, purpose="lectura")
    _olvidar_hash_principal(canonical)
    con_diario = _has_nonempty_wal(canonical) if guard_enabled() and database_existed else False
    antes = (
        _pair_snapshot(canonical, deep=con_diario)
        if guard_enabled() and database_existed
        else None
    )
    if guard_enabled() and database_existed and not _pair_can_be_opened(canonical):
        if force_open_authorized():
            forense = _save_conflict_forensics(canonical, motivo="lectura_forzada")
            logger.warning(
                "Lectura forzada con un -wal no verificado (%s); constancia en %s",
                consumer, forense,
            )
        else:
            forense = _save_conflict_forensics(canonical, motivo="par_no_verificado")
            raise SQLiteSidecarConflictError(
                "BioRAG no abrió la base para lectura porque hay un -wal que no "
                "se puede atribuir con certeza a este archivo principal (por "
                "ejemplo, tras cambiar de rama con la base versionada, tras una "
                "caída del proceso o si quedó un cliente antiguo abierto). "
                "Abrirla así podría aplicar datos de otra versión sobre los "
                "actuales. No se movió, renombró ni borró ningún archivo; hay "
                f"una constancia con los sha256 en {forense}. Para revisar y "
                "decidir: docs/sqlite_par_no_verificado.md. Para continuar "
                "bajo tu responsabilidad: BIORAG_SQLITE_FORCE_OPEN=1."
            )

    timeout_ms = int(round(timeout * 1000))
    uri = Path(canonical).as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=timeout, **connect_kwargs)
    try:
        # Cierre de la ventana TOCTOU (revisión independiente sobre 2b3b11c).
        # La comprobación previa mira NOMBRES; entre comprobar y abrir alguien
        # puede poner otro archivo detrás del nombre. Aquí se comprueba que el
        # par sigue siendo el mismo que se verificó: mismo `(dev, ino)` —un
        # renombrado lo cambia, y es lo que hace `git checkout`— y mismo
        # contenido (una reescritura in situ conserva el inodo).
        #
        # En lectura no se ha leído nada todavía, así que cerrar es inocuo: la
        # conexión no ha aplicado nada ni consolidado nada.
        if antes is not None and not force_open_authorized():
            if not _pair_snapshot_stable(antes, _pair_snapshot(canonical, deep=con_diario)):
                conn.close()
                forense = _save_conflict_forensics(canonical, motivo="par_cambio_en_apertura")
                raise SQLiteSidecarConflictError(
                    "BioRAG no abrió la base para lectura porque los archivos "
                    "del par cambiaron entre la comprobación y la apertura. "
                    "Algo sustituyó el archivo en esa ventana (un `git "
                    "checkout`, un renombrado o un proceso ajeno). No se leyó "
                    "ningún dato de esa conexión y no se movió, renombró ni "
                    f"borró ningún archivo; constancia en {forense}. Para "
                    "revisar: docs/sqlite_par_no_verificado.md. Para continuar "
                    "bajo tu responsabilidad: BIORAG_SQLITE_FORCE_OPEN=1."
                )
        # PRAGMA no admite parametros (`?`), asi que el valor se interpola.
        # `timeout_ms` viene de `int(round(...))` sobre un float ya validado
        # contra `_MAX_BUSY_TIMEOUT_MS`: es un entero de este codigo, nunca un
        # dato de fuera. OWASP A03 (docs/SEGURIDAD_OWASP.md).
        conn.execute("PRAGMA busy_timeout=%d" % timeout_ms)
        conn.execute("PRAGMA query_only=ON")
        connection_diagnostics(
            conn, canonical, role="read-only", consumer=consumer
        )
    except BaseException:
        conn.close()
        raise
    return conn
