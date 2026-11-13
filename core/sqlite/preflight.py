"""Comprobación del runtime de SQLite en la puerta de entrada.

Qué problema resuelve: el WAL-reset bug de SQLite corrompe la base si dos
procesos tocan el WAL sin coordinación. La política que lo evita existía, pero
solo se aplicaba **al intentar escribir**: el usuario se enteraba a mitad de su
trabajo, cuando le pedía al agente que recordara algo, con un error que habla de
versiones de SQLite y de journal_mode. Eso no es aceptable para alguien que solo
quiere usar el programa.

Por qué está aquí y no en otro sitio: es una comprobación del **entorno**, no del
archivo. No pertenece a `pair_guard` (que decide sobre el par de archivos) ni a
`opening` (que abre conexiones). Se ejecuta antes de construir el servidor.

Quién lo usa: `core/mcp_server/server.py:main()` al arrancar, y el daemon.

Medida con la que se aprueba: arrancar con un runtime vulnerable y una base en
WAL debe producir un aviso **antes** de atender ninguna herramienta, y no debe
impedir arrancar cuando la base no existe todavía o no está en WAL.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from core.sqlite_runtime import (  # fachada: regla de arquitectura del paquete
    _effective_sqlite_version,
    _journal_from_header,
    is_wal_reset_vulnerable,
    logger,
)


# Versiones con el WAL-reset bug corregido. Se listan explícitamente porque el
# número de versión por sí solo no basta: hay backports publicados (3.50.7 y
# 3.44.6) que no son "los más nuevos" y sí están arreglados.
VERSIONES_CORREGIDAS = ("3.51.3+", "3.50.7", "3.44.6 (con el backport)")

_CONSEJO_ACTUALIZAR = (
    "Actualiza el Python que ejecuta BioRAG: el SQLite viene compilado dentro "
    "de Python y no se puede actualizar con pip. Comprueba con "
    "`python -c \"import sqlite3; print(sqlite3.sqlite_version)\"` usando el "
    "MISMO intérprete que arranca el servidor."
)


@dataclass(frozen=True)
class RuntimeCheck:
    """Resultado de la comprobación de arranque.

    `bloqueante` es False por defecto: el aviso informa, no impide arrancar.
    Un sistema usable no deja al usuario sin servicio por un requisito que puede
    resolverse después. Solo se marca bloqueante cuando continuar escribiría en
    una base que podría corromperse.
    """

    version: tuple[int, int, int]
    vulnerable: bool
    base_en_wal: bool | None
    mensaje: str | None
    bloqueante: bool = False

    @property
    def ok(self) -> bool:
        return self.mensaje is None


def _version_legible(version: tuple[int, ...]) -> str:
    """Formatea la versión como `3.45.1`, que es lo que el usuario reconoce.

    Existe para que el mensaje no muestre una tupla de Python: quien lee el aviso
    tiene que poder comparar el número con lo que imprime `sqlite_version`.
    """
    return ".".join(map(str, version))


def comprobar_runtime(database: str | Path | None = None) -> RuntimeCheck:
    """Comprueba el runtime antes de arrancar y devuelve qué decir al usuario.

    No abre la base: el modo de journal se lee de la cabecera del archivo, en
    solo lectura, igual que hace la política de apertura. Si el archivo no
    existe, no hay nada que proteger: una base nueva se crea en el modo que el
    runtime permita.
    """
    version = tuple(_effective_sqlite_version())
    vulnerable = is_wal_reset_vulnerable(version)

    if not vulnerable:
        return RuntimeCheck(version, False, None, None)

    base_en_wal: bool | None = None
    if database is not None:
        ruta = Path(str(database)).expanduser()
        if ruta.exists():
            try:
                base_en_wal = _journal_from_header(str(ruta)) == "wal"
            except OSError:
                base_en_wal = None

    if base_en_wal is False:
        # Vulnerable pero la base no está en WAL: no hay riesgo del bug.
        return RuntimeCheck(version, True, False, None)

    if base_en_wal is None:
        detalle = (
            "No se pudo leer el modo de journal de la base (no existe todavía o "
            "no es accesible). Si ya existe y está en WAL, no se podrá escribir."
        )
    else:
        detalle = "La base existente está en journal_mode='wal'."

    mensaje = (
        f"BioRAG se está ejecutando con SQLite {_version_legible(version)}, que "
        f"tiene un fallo conocido que puede corromper la base cuando dos "
        f"procesos escriben a la vez. {detalle} La protección está activa: "
        f"podrás LEER, pero las operaciones que guardan memoria serán "
        f"rechazadas hasta que uses un runtime corregido "
        f"({', '.join(VERSIONES_CORREGIDAS)}). {_CONSEJO_ACTUALIZAR} "
        f"Más detalles: docs/sqlite_journal_migration_runbook.md"
    )
    return RuntimeCheck(version, True, base_en_wal, mensaje)


def anunciar_si_hay_problema(database: str | Path | None = None) -> RuntimeCheck:
    """Comprueba y, si hay algo que contar, lo registra y lo escribe en stderr.

    Se usa stderr y no stdout a propósito: el transporte MCP por stdio usa
    stdout para el protocolo, y escribir ahí rompería el handshake.
    """
    import sys

    resultado = comprobar_runtime(database)
    if resultado.mensaje:
        logger.warning("Runtime SQLite no corregido: %s", resultado.mensaje)
        try:
            sys.stderr.write(resultado.mensaje + "\n")
            sys.stderr.flush()
        except (OSError, ValueError):
            logger.debug("No se pudo escribir el aviso de runtime en stderr")
    return resultado
