"""Decide si un `.db` y su `-wal` pueden abrirse juntos.

Qué problema resuelve: SQLite aplica el `-wal` al abrir, sin comprobar que
pertenezca al archivo principal. Si el diario viene de otra versión de la base
(otra rama de git, una copia vieja), se aplica igual y la base queda con datos
ajenos, con `integrity_check` diciendo `ok`. Este módulo decide, ANTES de abrir
SQLite y leyendo solo cabeceras, si hay prueba de que el diario es de esa base.

Por qué está aquí y no en otro sitio: es la única pieza que toca los archivos
auxiliares, y lo hace en solo lectura. Aislarla permite apagarla entera
(`BIORAG_SQLITE_GUARD=0`) sin tocar el resto del motor.

Quién lo usa: `opening` antes de cada `sqlite3.connect`; `tracking` para
reanotar el estado tras cada commit propio.

Garantía: nunca mueve, renombra ni borra nada. Si no puede probar pertenencia,
rechaza y deja constancia en `<base>.biorag-pair-state.conflicto.json`.

Medida con la que se aprobó: los tres escenarios de la auditora reproducidos
(caída, cambio de rama, consolidación imposible) más 30 pruebas en
`tests/test_sqlite_generation.py`.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from core.sqlite.constants import _is_memory_database, guard_enabled, logger

_PAIR_STATE_SUFFIX = ".biorag-pair-state"

def _has_nonempty_wal(database) -> bool:
    """True si existe un `-wal` con contenido. Si está vacío o no existe, no hay diario que aplicar y la comprobación no hace falta."""
    value = os.fsdecode(os.fspath(database))
    if _is_memory_database(value) or value.startswith("file:"):
        return False
    try:
        return os.path.getsize(os.path.expanduser(value) + "-wal") > 0
    except OSError:
        return False

def _pair_state_path(database) -> str | None:
    """Ruta del archivo donde se anota el estado del par. No es un sidecar de SQLite: es nuestro, y se llama `<base>.biorag-pair-state`."""
    value = os.fsdecode(os.fspath(database))
    if _is_memory_database(value) or value.startswith("file:"):
        return None
    return os.path.expanduser(value) + _PAIR_STATE_SUFFIX

def _file_forensics(path: str) -> dict[str, Any] | None:
    """Tamaño, fechas y sha256 de un archivo. Solo lectura."""
    try:
        st = os.stat(path)
        with open(path, "rb") as handle:
            digest = hashlib.sha256()
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
    except OSError:
        return None
    return {
        "size": int(st.st_size),
        "mtime_ns": int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9))),
        "sha256": digest.hexdigest(),
    }

def _file_identity(path: str) -> dict[str, Any] | None:
    """Identidad del archivo en el sistema: `(st_dev, st_ino)` + tamaño y fecha.

    Qué problema resuelve: entre comprobar el par y abrirlo hay una ventana
    (TOCTOU) en la que el archivo puede cambiar. Ninguna comprobación previa
    puede cerrar esa ventana, porque comprobar y abrir son dos operaciones
    distintas sobre un **nombre**.

    Por qué el inodo: `os.replace()` sobre un nombre produce un inodo **nuevo**.
    Comparar `(st_dev, st_ino)` antes y después de abrir detecta la sustitución
    por renombrado, que es exactamente lo que hace un `git checkout` al cambiar
    la base versionada. Git no participa en los bloqueos del motor, así que
    esta comprobación **no se apoya en ningún bloqueo**: se apoya en la
    identidad del archivo, que el sistema mantiene.

    Por qué no basta: una escritura **in situ** conserva el inodo y cambia el
    contenido. Ese caso lo cubre el sha256, que se compara en la misma
    fotografía.
    """
    try:
        st = os.stat(path)
    except OSError:
        return None
    return {
        "dev": int(st.st_dev),
        "ino": int(st.st_ino),
        "size": int(st.st_size),
        "mtime_ns": int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9))),
    }


def _pair_snapshot(database) -> dict[str, Any]:
    """Fotografía verificable del par: identidad + contenido de principal y diario.

    Es la referencia contra la que se comprueba que el par **no cambió** entre
    la verificación y la apertura. Los campos `dev`/`ino` detectan sustitución
    por renombrado; los `sha256` detectan reescritura in situ.
    """
    value = os.path.expanduser(os.fsdecode(os.fspath(database)))
    wal = value + "-wal"
    principal = _file_identity(value)
    if principal is not None:
        forense = _file_forensics(value)
        if forense is not None:
            principal = {**principal, "sha256": forense["sha256"]}
    diario = _file_identity(wal)
    if diario is not None:
        try:
            tamano = diario["size"]
        except (KeyError, TypeError):
            tamano = 0
        if tamano > 0:
            diario = {**diario, "content": _wal_content_digest(wal)}
        else:
            diario = None
    return {"main": principal, "wal": diario}


def _pair_identity_stable(before: dict[str, Any], after: dict[str, Any]) -> bool:
    """¿Los mismos archivos siguen detrás de los mismos nombres?

    Solo mira `dev`/`ino`: es lo que cambia un renombrado y lo que no cambia
    una escritura legítima del motor sobre el archivo ya abierto.
    """
    principal_a, principal_b = before.get("main"), after.get("main")
    if principal_a is None or principal_b is None:
        return False
    if (principal_a["dev"], principal_a["ino"]) != (principal_b["dev"], principal_b["ino"]):
        return False
    diario_a, diario_b = before.get("wal"), after.get("wal")
    if (diario_a is None) != (diario_b is None):
        # El diario apareció o desapareció dentro de la ventana.
        return False
    if diario_a is not None:
        if (diario_a["dev"], diario_a["ino"]) != (diario_b["dev"], diario_b["ino"]):
            return False
    return True


def _pair_snapshot_stable(before: dict[str, Any], after: dict[str, Any]) -> bool:
    """¿El par está exactamente como se verificó? Identidad **y** contenido.

    Es la comprobación fuerte: además del inodo exige el mismo sha256 del
    principal y el mismo contenido del diario, así que también detecta la
    reescritura in situ dentro de la ventana.
    """
    if not _pair_identity_stable(before, after):
        return False
    principal_a, principal_b = before["main"], after["main"]
    if principal_a.get("sha256") != principal_b.get("sha256"):
        return False
    diario_a, diario_b = before.get("wal"), after.get("wal")
    if diario_a is None:
        return diario_b is None
    if diario_b is None:
        return False
    return diario_a.get("content") == diario_b.get("content")


def _wal_content_digest(path: str) -> str | None:
    """sha256 del CONTENIDO del diario (todo menos la cabecera de 32 bytes).

    Por qué no basta la sal (revisión independiente sobre `d98a946`): la sal
    está en la cabecera y **una copia la conserva**. Copiar el `-wal`, modificar
    los datos y dejar el principal intacto producía la misma sal, así que la
    comprobación lo aceptaba y las lecturas veían el dato de la copia.

    La cabecera se puede copiar; los frames con datos de otra base no coinciden.
    Si el diario no existe o está vacío se devuelve None.
    """
    try:
        with open(path, "rb") as handle:
            head = handle.read(32)
            if len(head) < 32 or head[:3] != b"7\x7f\x06":
                return None
            digest = hashlib.sha256()
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


def _wal_header_salt(path: str) -> str | None:
    """Sal (8 bytes) de la cabecera del WAL. Identifica AL DIARIO, no su dueño.

    Se anota solo como dato forense: por sí sola no prueba pertenencia
    (`docs/auditoria_pr13_039a819.md`)."""
    try:
        with open(path, "rb") as handle:
            head = handle.read(24)
    except OSError:
        return None
    if len(head) < 24 or head[:3] != b"7\x7f\x06":
        return None
    return head[16:24].hex()

def record_pair_state(database: str | Path) -> None:
    """Anota el estado del par (principal + diario) cuando es verificable.

    Se escribe en los dos momentos en que el par es coherente por construcción:
    tras cerrar ordenadamente (el diario queda consolidado y vacío) y tras un
    commit propio del motor. Nunca se escribe con un diario ajeno presente.
    """
    if not guard_enabled():
        return
    state_path = _pair_state_path(database)
    if state_path is None:
        return
    value = os.path.expanduser(os.fsdecode(os.fspath(database)))
    # Evitar hashear el archivo completo si tamaño y fecha no cambiaron.
    recorded = _recorded_pair_state(database)
    if recorded is not None:
        try:
            st = os.stat(value)
            if (
                int(st.st_size) == int(recorded["main"]["size"])
                and int(st.st_mtime_ns) == int(recorded["main"]["mtime_ns"])
                and _wal_header_salt(value + "-wal") == recorded.get("wal_salt")
                and _wal_content_digest(value + "-wal") == recorded.get("wal_content")
            ):
                return
        except (OSError, KeyError, TypeError, ValueError):
            pass
    main = _file_forensics(value)
    if main is None:
        return
    payload = {
        "main": main,
        "wal_salt": _wal_header_salt(value + "-wal"),
        "wal_content": _wal_content_digest(value + "-wal"),
        "guard": True,
        "recorded_at": time.time(),
    }
    try:
        with open(state_path, "w", encoding="ascii") as handle:
            json.dump(payload, handle)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError:
        logger.debug("No se pudo anotar el estado del par SQLite")

def _recorded_pair_state(database) -> dict[str, Any] | None:
    """Estado del par anotado en el último commit propio, o None si nunca se anotó."""
    state_path = _pair_state_path(database)
    if state_path is None:
        return None
    try:
        with open(state_path, "r", encoding="ascii") as handle:
            data = json.loads(handle.read() or "{}")
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and "main" in data else None

def _journal_from_header(value: str) -> str | None:
    """Modo de journal según la cabecera del archivo, sin abrir SQLite."""
    try:
        with open(value, "rb") as handle:
            head = handle.read(100)
    except OSError:
        return None
    if len(head) < 100 or not head.startswith(b"SQLite format 3\x00"):
        return None
    return "wal" if head[18] == 2 or head[19] == 2 else "rollback"

def _pair_can_be_opened(database) -> bool:
    """Decide si el par se puede abrir, SIN abrir el par real.

    Orden de comprobaciones (todas de solo lectura sobre los archivos):

    1. Sin `-wal` o con el diario vacío -> se puede abrir. No hay nada que
       pueda aplicarse; es el estado que deja un cierre ordenado.
    2. El modo de journal se lee de la cabecera (byte 18/19). Si no es WAL pero
       hay un `-wal` en disco, ese archivo no corresponde a este principal.
    3. Con anotación y principal idéntico (sha256) -> se puede abrir. Un diario
       nuevo entonces viene de una escritura externa legítima.
    4. Con anotación y principal distinto, o sin anotación -> hay riesgo de
       aplicar un diario de otra generación. No se puede probar pertenencia:
       se rechaza y se conserva todo.

    El caso 4 es el precio de la política cerrada: también rechaza algún
    mantenimiento legítimo que cambie el principal. Es deliberado: preferimos
    pedir una confirmación a aplicar datos de otra versión.
    """
    value = os.path.expanduser(os.fsdecode(os.fspath(database)))
    wal = value + "-wal"
    try:
        wal_size = os.path.getsize(wal)
    except OSError:
        return True
    if wal_size == 0:
        return True

    journal = _journal_from_header(value)
    if journal is None:
        # Cabecera inválida o archivo ausente: no se puede afirmar nada.
        return False
    if journal != "wal":
        return False

    recorded = _recorded_pair_state(value)
    if recorded is None:
        return False
    try:
        expected = recorded["main"]["sha256"]
    except (KeyError, TypeError):
        return False
    current = _file_forensics(value)
    if current is None:
        return False
    if current["sha256"] != expected:
        # El principal cambió con un diario vivo: no se puede distinguir un
        # checkpoint legítimo de una sustitución. Se pide confirmación.
        return False

    # El principal NO cambió respecto a lo anotado. Eso solo descarta la
    # sustitución del archivo principal; NO descarta que el `-wal` sea de otra
    # base (hallazgo de la revisión independiente sobre 88ef43f). La sal de la
    # cabecera identifica AL DIARIO, y está anotada junto al principal: si la
    # sal de ahora no es la anotada, este diario no es el que había cuando se
    # verificó el par, así que no se puede probar que le pertenezca.
    #
    # Este es el caso de una caída del proceso: el diario es el mismo que había
    # en el último commit propio (misma sal), así que se acepta y SQLite
    # recupera. Un diario de otra base trae otra sal y se rechaza.
    recorded_salt = recorded.get("wal_salt")
    if not recorded_salt:
        # Se anotó el par sin diario vivo: cualquier diario que aparezca ahora
        # es nuevo y no está atestiguado.
        return False
    if _wal_header_salt(wal) != recorded_salt:
        return False

    # La sal se conserva al COPIAR el diario, así que sola no basta (revisión
    # independiente sobre d98a946: un WAL copiado y modificado mantenía la sal).
    # El sha256 del contenido sí cambia cuando los frames llevan datos de otra
    # base, y es estable para el mismo diario tras una caída.
    recorded_content = recorded.get("wal_content")
    if not recorded_content:
        return False
    if _wal_content_digest(wal) != recorded_content:
        return False
    return True

def _save_conflict_forensics(database, **extra) -> str | None:
    """Deja constancia verificable de lo que había. No mueve ni borra nada."""
    state_path = _pair_state_path(database)
    if state_path is None:
        return None
    value = os.path.expanduser(os.fsdecode(os.fspath(database)))
    payload = {
        "motivo": extra.get("motivo"),
        "principal": _file_forensics(value),
        "wal": _file_forensics(value + "-wal"),
        "shm": _file_forensics(value + "-shm"),
        "wal_salt": _wal_header_salt(value + "-wal"),
        "anotado": _recorded_pair_state(value),
        "detectado_en": time.time(),
    }
    target = state_path + ".conflicto.json"
    try:
        with open(target, "w", encoding="ascii") as handle:
            json.dump(payload, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError:
        logger.exception("No se pudo dejar constancia del conflicto de sidecars")
        return None
    return target
