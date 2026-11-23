"""Preparar/verificar esquema tras instalación: python -m core.migrate.

No actualiza paquetes ni descarga versiones. La misma inicialización del core
atiende instalaciones nuevas y bases existentes; respalda DBs antes de abrirlas.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3

from core.contextual.schema import COLUMNS
from core.database_backup import create_backup, finish_backup, prune_successful, verify_database, validate_update_backup
from core.schema_status import APPLIED_UPDATE_KEY, valid_update_id
from core.database_access import connect, connect_readonly


def _initialize(path):
    from core.memory_store import SQLiteMemoryBioRAG
    memory = SQLiteMemoryBioRAG(db_path=str(path))
    try:
        from core.contextual.schema import ensure_contextual_schema
        ensure_contextual_schema(memory.conn)
        memory.conn.commit()
    finally:
        memory.conn.close()


def migrate(path, *, existing_backup=None):
    from core.database_access import maintenance
    with maintenance(path):
        return _migrate(path, existing_backup=existing_backup)


def record_applied_update_id(path, update_id):
    """Record the installed Git target after every lifecycle step is verified.

    This is a single replaceable status value in the existing ``data`` table,
    not a per-update history. It is deliberately not written by ordinary DB
    initialization or standalone migration commands.
    """
    if not valid_update_id(update_id):
        raise ValueError('UPDATE_ID_INVALID')
    from core.database_access import maintenance
    path=Path(path).expanduser().resolve()
    with maintenance(path):
        with closing(connect(path)) as db:
            columns={row[1] for row in db.execute('PRAGMA table_info(data)')}
            if not {'clave','valor','descripcion'} <= columns:
                raise sqlite3.DatabaseError('UPDATE_MARKER_TABLE_UNAVAILABLE: data')
            db.execute(
                'INSERT INTO data(clave,valor,descripcion) VALUES(?,?,?) '
                'ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor,descripcion=excluded.descripcion',
                (APPLIED_UPDATE_KEY, update_id,
                 'Git commit whose database lifecycle completed and was verified.'),
            )
            db.commit()
    return {'key':APPLIED_UPDATE_KEY,'value':update_id}


def _migrate(path, *, existing_backup=None):
    """Respalda mediante SQLite backup (incluye WAL confirmado) y usa core real.

    Errores se propagan. El respaldo se conserva incluso si la migración falla.
    No reemplaza la DB viva automáticamente después de un fallo.
    """
    path = Path(path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    owns_backup = existing_backup is None
    backup = (create_backup(path, purpose='migration') if owns_backup
              else validate_update_backup(existing_backup, path))
    try:
        _initialize(path)
        with closing(connect_readonly(path)) as db:
            for table, columns in COLUMNS.items():
                actual = tuple(row[1] for row in db.execute('PRAGMA table_info('+table+')'))
                if actual != columns:
                    raise sqlite3.DatabaseError('MIGRATION_VERIFICATION_FAILED: '+table)
        verification = verify_database(path)
    except Exception:
        if owns_backup:finish_backup(backup, success=False)
        raise
    if owns_backup:finish_backup(backup, success=True)
    retention = prune_successful(path) if owns_backup else None
    return dict(status='ok', database=str(path), backup=backup,
                contextual_tables=list(COLUMNS), verification=verification, retention=retention)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', help='DB explícita; por defecto la ruta configurada del core')
    args = parser.parse_args()
    from core.paths import resolve_db_path
    print(json.dumps(migrate(args.db or resolve_db_path()), ensure_ascii=False))


if __name__ == '__main__':
    main()
