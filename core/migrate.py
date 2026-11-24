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
from core.schema_status import APPLIED_UPDATE_KEY, CURRENT_SCHEMA_VERSION, check_schema_version, valid_update_id
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
    check_schema_version(path)
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

    Errores se propagan. Si owns_backup es True y la migración falla, se restaura
    automáticamente la base de datos previa desde el respaldo verificado para
    evitar estados inconsistentes en migraciones sueltas.
    """
    path = Path(path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    check_schema_version(path)

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

        # Sellar user_version con BEGIN IMMEDIATE y isolation_level=None
        raw_conn = sqlite3.connect(str(path), isolation_level=None, timeout=30)
        try:
            raw_conn.execute("BEGIN IMMEDIATE")
            raw_conn.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION}")
            raw_conn.execute("COMMIT")
        finally:
            raw_conn.close()

        verification = verify_database(path)
    except Exception:
        if owns_backup and backup is not None:
            # Restaurar ANTES de marcar el backup como fallido para que su status='pending' sea válido
            from core.updater import restore_database_backup
            try:
                restore_database_backup(backup, path)
            except Exception as restore_exc:
                import sys
                sys.stderr.write(
                    f"CRITICAL: Migration failed and automatic restore failed: {restore_exc}\n"
                    f"Manual recovery snapshot available at: {backup}\n"
                )
            finish_backup(backup, success=False)
        elif owns_backup and backup is None:
            # BD nueva que no existía antes: limpiar cualquier archivo parcial creado
            path.unlink(missing_ok=True)
            Path(str(path) + "-wal").unlink(missing_ok=True)
            Path(str(path) + "-shm").unlink(missing_ok=True)
        raise
    if owns_backup:finish_backup(backup, success=True)
    retention = prune_successful(path) if owns_backup else None
    return dict(status='ok', database=str(path), backup=backup,
                schema_version=CURRENT_SCHEMA_VERSION,
                contextual_tables=list(COLUMNS), verification=verification, retention=retention)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', help='DB explícita; por defecto la ruta configurada del core')
    args = parser.parse_args()
    from core.paths import resolve_db_path
    print(json.dumps(migrate(args.db or resolve_db_path()), ensure_ascii=False))


if __name__ == '__main__':
    main()
