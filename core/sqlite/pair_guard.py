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

# Hash del principal recién calculado en ESTA misma operación, por ruta.
# Se reutiliza únicamente si tamaño y fecha siguen siendo los mismos: no es una
# caché entre operaciones (eso ya demostró ser inseguro), sino evitar repetir
# el mismo trabajo dentro de la misma comprobación. Lleva la firma dentro, así
# que un archivo que cambió no puede servirse de aquí.
_ULTIMO_HASH_PRINCIPAL: dict[str, tuple[str, int, int]] = {}


def _olvidar_hash_principal(database) -> None:
    """Descarta el hash reutilizable de una ruta.

    Se llama al empezar cada apertura: el ámbito de reutilización es **una
    operación**, no la vida del proceso. Si se dejara, un hash viejo podría
    sobrevivir a un cambio de archivo con el mismo tamaño y fecha (posible en
    sistemas de archivos de resolución gruesa), y eso es exactamente el tipo de
    suposición que ya nos costó un hallazgo. Preferible recalcular.
    """
    try:
        clave = os.path.abspath(os.path.expanduser(os.fsdecode(os.fspath(database))))
    except (TypeError, ValueError):
        return
    _ULTIMO_HASH_PRINCIPAL.pop(clave, None)


def _forense_principal(value: str) -> dict[str, Any] | None:
    """`_file_forensics` del principal, sin repetir el hash ya hecho en esta operación.

    Coste medido antes de esto: una sola apertura hasheaba el principal cuatro
    veces (~450 ms por vez con 302 MB, 5,6 s con 1 GB). Las cuatro miran el
    mismo archivo en el mismo instante, así que tres de ellas eran trabajo puro
    perdido.

    No confundir con un caché de resultados: la firma `(size, mtime_ns)` va
    dentro y se comprueba en cada consulta, así que si el archivo cambió se
    recalcula. Y no interviene en ninguna decisión: la comprobación de apertura
    sigue calculando el hash del principal siempre que hace falta decidir.
    """
    clave = os.path.abspath(value)
    try:
        st = os.stat(value)
    except OSError:
        _ULTIMO_HASH_PRINCIPAL.pop(clave, None)
        return None
    firma = (int(st.st_size), int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9))))
    previo = _ULTIMO_HASH_PRINCIPAL.get(clave)
    if previo is not None and (previo[1], previo[2]) == firma:
        return {"size": firma[0], "mtime_ns": firma[1], "sha256": previo[0]}
    forense = _file_forensics(value)
    if forense is not None:
        _ULTIMO_HASH_PRINCIPAL[clave] = (forense["sha256"], firma[0], firma[1])
    return forense


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


def _pair_snapshot(database, *, deep: bool) -> dict[str, Any]:
    """Fotografía verificable del par: identidad + contenido de principal y diario.

    Es la referencia contra la que se comprueba que el par **no cambió** entre
    la verificación y la apertura. Los campos `dev`/`ino` detectan sustitución
    por renombrado; los `sha256` detectan reescritura in situ.

    `deep` decide si se hashea el contenido. La regla no es de coste, es de
    correspondencia: **la verificación posterior debe comprobar exactamente lo
    que asumió la anterior.**

    - Si al comprobar **había** diario, la decisión se apoyó en el contenido
      (sha256 del principal y del diario), así que la posterior debe rehashear.
    - Si **no** había diario, la decisión solo asumió "no hay diario y el
      principal es este archivo". Basta identidad + tamaño + fecha para
      detectar que en la ventana apareció uno o se sustituyó el principal.
      Hashear ahí no añadiría garantía y sí coste en **todas** las aperturas.

    El error que corrigió esto (revisión independiente sobre `3912d68`): saltarse
    la fotografía cuando no había `-wal` dejaba sin verificar justo el caso en
    que un diario ajeno aparece antes de abrir.
    """
    value = os.path.expanduser(os.fsdecode(os.fspath(database)))
    wal = value + "-wal"
    principal = _file_identity(value)
    if principal is not None and deep:
        forense = _forense_principal(value)
        if forense is not None:
            principal = {**principal, "sha256": forense["sha256"]}
    diario = _file_identity(wal)
    if diario is not None:
        try:
            tamano = diario["size"]
        except (KeyError, TypeError):
            tamano = 0
        if tamano > 0:
            if deep:
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
    # En modo superficial no hay sha256; la identidad, el tamaño y la fecha ya
    # se compararon en `_pair_identity_stable`... salvo tamaño y fecha, que se
    # comprueban aquí porque una reescritura in situ conserva el inodo.
    for campo in ("size", "mtime_ns"):
        if principal_a.get(campo) != principal_b.get(campo):
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
    # Una sola lectura de cada archivo por anotación. Antes el diario se hasheaba
    # dos veces (una en el atajo de arriba, otra aquí): trabajo repetido sobre el
    # mismo archivo en el mismo instante.
    contenido = _wal_content_digest(value + "-wal")
    sal = _wal_header_salt(value + "-wal")

    # El principal se reutiliza SOLO si tamaño y fecha coinciden con lo ya
    # anotado: entonces su sha256 no puede haber cambiado. Motivo (coste
    # medido): un commit en WAL **no modifica el principal**, así que
    # rehashearlo en cada commit costaba ~1,2 s por GB sin aportar nada.
    #
    # Dirección del fallo si la inferencia se equivoca: se anotaría el sha
    # viejo, la apertura siguiente no coincidiría y **rechazaría**. Falla
    # cerrado, nunca acepta un par ajeno. La decisión de abrir sigue
    # recalculando el hash del principal siempre, en `_pair_can_be_opened`.
    main = None
    if recorded is not None:
        try:
            st = os.stat(value)
            fila = recorded["main"]
            if (
                int(st.st_size) == int(fila["size"])
                and int(st.st_mtime_ns) == int(fila["mtime_ns"])
            ):
                main = dict(fila)
        except (OSError, KeyError, TypeError, ValueError):
            main = None
    if main is None:
        main = _forense_principal(value)
        if main is None:
            return
    payload = {
        "main": main,
        "wal_salt": sal,
        "wal_content": contenido,
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
    _ULTIMO_HASH_PRINCIPAL[os.path.abspath(value)] = (current["sha256"], current["size"], current["mtime_ns"])
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
        # Constancia, no decisión: se reutiliza el hash ya calculado en esta
        # misma operación si el archivo no cambió. Rehashear aquí el principal
        # costaba otros ~450 ms por GB en un camino que ya está fallando.
        "principal": _forense_principal(value),
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
