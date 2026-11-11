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

from core.sqlite.config import _is_memory_database, guard_enabled, logger

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
    if current["sha256"] == expected:
        return True
    # El principal cambió con un diario vivo: no se puede distinguir un
    # checkpoint legítimo de una sustitución. Se pide confirmación.
    return False

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
