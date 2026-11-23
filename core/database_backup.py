"""Backup SQLite y retención compartidos; no conoce Git, MCP ni migraciones.

Retiene 2 backups de operaciones exitosas por DB. Fallidos/pendientes se protegen.
Solo elimina archivos propios con metadatos válidos, nunca backups ajenos/legacy.
"""
from contextlib import closing
import json
import hashlib
import math
import os
from pathlib import Path
import sqlite3
import tempfile
import time

from core.database_access import connect_readonly

FORMAT = 'biorag.sqlite-backup.v1'
DEFAULT_KEEP = 2
BACKUP_TIMEOUT_SECONDS = 120


def verify_database(path):
    """Comprueba estructura SQLite y FKs; no demuestra equivalencia semántica."""
    path=Path(path).expanduser().resolve()
    with closing(connect_readonly(path, timeout=60)) as db:
        checks=db.execute('PRAGMA quick_check').fetchall()
        if checks != [('ok',)]:
            raise sqlite3.DatabaseError('DATABASE_QUICK_CHECK_FAILED')
        if db.execute('PRAGMA foreign_key_check').fetchone() is not None:
            raise sqlite3.DatabaseError('DATABASE_FOREIGN_KEY_CHECK_FAILED')
    return dict(quick_check='ok', foreign_key_check='ok')


def file_sha256(path):
    digest=hashlib.sha256()
    with open(path,'rb') as file:
        for chunk in iter(lambda:file.read(1024*1024),b''):
            digest.update(chunk)
    return digest.hexdigest()


def logical_fingerprint(path):
    """Huella del dump lógico del snapshot, no una evaluación de semántica."""
    digest=hashlib.sha256()
    with closing(connect_readonly(path)) as db:
        db.execute('BEGIN')
        for statement in db.iterdump():
            digest.update(statement.encode('utf-8'));digest.update(b'\n')
    return digest.hexdigest()


def rehearse_restore(backup):
    """Restaurar SOLO en temporal y comparar contenido lógico del snapshot."""
    backup=Path(backup).resolve()
    with tempfile.TemporaryDirectory(prefix='biorag-restore-test-') as directory:
        restored=Path(directory)/'restored.db'
        with closing(sqlite3.connect(backup.as_uri()+'?mode=ro',uri=True)) as source:
            with closing(sqlite3.connect(restored)) as target:source.backup(target)
        verify_database(restored)
        fingerprint=logical_fingerprint(backup)
        if logical_fingerprint(restored)!=fingerprint:
            raise sqlite3.DatabaseError('RESTORE_REHEARSAL_MISMATCH')
    return dict(restore_tested=True, logical_sha256=fingerprint)


def _metadata_path(backup):
    return Path(str(backup)+'.json')


def backup_evidence(backup):
    data=json.loads(_metadata_path(backup).read_text())
    if not isinstance(data,dict) or data.get('format')!=FORMAT:
        raise ValueError('BACKUP_METADATA_INVALID')
    return data


def _write_metadata(backup, data):
    path=_metadata_path(backup)
    with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,prefix='.backup-meta-',delete=False) as file:
        temporary=Path(file.name)
        try:
            json.dump(data,file,ensure_ascii=False,indent=2)
            file.flush()
            os.fsync(file.fileno())
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
    try:os.replace(temporary,path)
    finally:temporary.unlink(missing_ok=True)


def create_backup(database, *, purpose='migration'):
    source=Path(database).expanduser().resolve()
    if not source.exists() or not source.stat().st_size:return None
    if purpose not in ('migration','update','recovery'):
        raise ValueError('BACKUP_PURPOSE_INVALID')
    folder=source.parent/'backups'
    if folder.is_symlink():raise ValueError('BACKUP_DIRECTORY_SYMLINK_UNSUPPORTED')
    folder.mkdir(exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=folder,prefix=source.name+'.pre-'+purpose+'-',suffix='.db',delete=False) as file:
        backup=Path(file.name)
    metadata=dict(format=FORMAT,source=str(source),purpose=purpose,status='pending',created_at=time.time())
    _write_metadata(backup,metadata)
    try:
        deadline=time.monotonic()+BACKUP_TIMEOUT_SECONDS
        def progress(status, remaining, total):
            if time.monotonic()>deadline:
                raise TimeoutError('DATABASE_BACKUP_TIMEOUT')
        with closing(connect_readonly(source, timeout=60)) as db:
            with closing(sqlite3.connect(str(backup))) as destination:
                db.backup(destination,pages=256,progress=progress)
        metadata['verification']=verify_database(backup)
        metadata['backup_sha256']=file_sha256(backup)
        metadata.update(rehearse_restore(backup))
        _write_metadata(backup,metadata)
    except Exception:
        metadata['status']='failed'
        try:_write_metadata(backup,metadata)
        except OSError:pass  # No ocultar el error inicial si también falta espacio para metadata.
        raise
    return str(backup)


def validate_update_backup(backup, database):
    source=Path(database).expanduser().resolve()
    backup=Path(backup).expanduser()
    if backup.is_symlink() or _metadata_path(backup).is_symlink():
        raise ValueError('BACKUP_HANDOFF_INVALID')
    backup=backup.resolve()
    data=json.loads(_metadata_path(backup).read_text())
    if (not isinstance(data,dict) or backup.parent != source.parent/'backups' or data.get('format')!=FORMAT
            or data.get('source')!=str(source) or data.get('purpose')!='update'
            or data.get('status')!='pending'):
        raise ValueError('BACKUP_HANDOFF_INVALID')
    verify_database(backup)
    if data.get('backup_sha256') and file_sha256(backup)!=data['backup_sha256']:
        raise ValueError('BACKUP_CHECKSUM_MISMATCH')
    return str(backup)


def finish_backup(backup, *, success):
    if backup is None:return
    backup=Path(backup)
    metadata=json.loads(_metadata_path(backup).read_text())
    if not isinstance(metadata,dict) or metadata.get('format')!=FORMAT:raise ValueError('BACKUP_METADATA_INVALID')
    metadata.update(status='success' if success else 'failed',completed_at=time.time())
    _write_metadata(backup,metadata)


def prune_successful(database, *, keep=DEFAULT_KEEP):
    """Limpia solo éxitos antiguos, después del éxito total de su operación.

    Coste O(B log B) para B sidecars, independiente del número de recuerdos.
    Errores de borrado se informan y no invalidan una DB ya migrada.
    """
    if type(keep) is not int or keep<1:raise ValueError('BACKUP_KEEP_MUST_BE_POSITIVE')
    source=Path(database).expanduser().resolve();folder=source.parent/'backups'
    candidates=[];protected=0;warnings=[];deleted=[]
    if folder.is_symlink():
        return dict(deleted=[],protected=0,warnings=['BACKUP_DIRECTORY_SYMLINK_UNSUPPORTED'],keep=keep)
    if not folder.is_dir():return dict(deleted=deleted,protected=0,warnings=warnings,keep=keep)
    for path in folder.glob('*.db.json'):
        backup=path.with_name(path.name[:-5])
        if path.is_symlink() or backup.is_symlink():continue
        try:
            data=json.loads(path.read_text())
            if not isinstance(data,dict) or data.get('format')!=FORMAT or data.get('source')!=str(source):continue
            if not backup.name.startswith(source.name+'.pre-') or not backup.is_file():continue
            if data.get('status')!='success':
                protected+=1;continue
            completed=data.get('completed_at')
            if type(completed) not in (int,float) or not math.isfinite(completed):continue
            candidates.append((completed,backup.name,backup,path))
        except (OSError,ValueError,TypeError):
            continue  # Metadata desconocida jamás autoriza borrado.
    for _,_,backup,path in sorted(candidates,reverse=True)[keep:]:
        try:
            backup.unlink();path.unlink()
            deleted.append(str(backup))
        except OSError as exc:warnings.append(type(exc).__name__+': '+str(backup))
    return dict(deleted=deleted,protected=protected,warnings=warnings,keep=keep)
