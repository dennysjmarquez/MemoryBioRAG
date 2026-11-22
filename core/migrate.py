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


def _initialize(path):
    from core.memory_store import SQLiteMemoryBioRAG
    memory = SQLiteMemoryBioRAG(db_path=str(path))
    try:
        memory.conn.commit()
    finally:
        memory.conn.close()


def migrate(path, *, existing_backup=None):
    from core.database_access import maintenance
    with maintenance(path):
        return _migrate(path, existing_backup=existing_backup)


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
        with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as db:
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
