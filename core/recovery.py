"""Recuperación asistida sin sobrescribir memoria: python -m core.recovery.

Planifica y restaura el backup en OTRO archivo. Nunca restaura encima de la DB
actual ni revierte Git/pip. Conserva una copia del estado actual, incluidos datos
posteriores al backup. Compatibilidad código-datos requiere verificación aparte.
"""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile

from core.database_access import maintenance
from core.database_backup import (file_sha256, logical_fingerprint, verify_database,
                                  create_backup, backup_evidence)


def plan(receipt):
    receipt=Path(receipt).expanduser().resolve()
    report=json.loads(receipt.read_text())
    backup=report.get('backup')
    if not backup:raise ValueError('RECOVERY_BACKUP_UNAVAILABLE')
    backup=Path(backup).resolve()
    metadata=backup_evidence(backup)
    database=Path(metadata['source']).resolve()
    if backup.parent!=database.parent/'backups':raise ValueError('RECOVERY_BACKUP_LOCATION_INVALID')
    if file_sha256(backup)!=metadata.get('backup_sha256'):
        raise ValueError('RECOVERY_BACKUP_CHECKSUM_MISMATCH')
    verify_database(backup)
    same = logical_fingerprint(database)==logical_fingerprint(backup) if database.exists() else False
    return dict(status='recovery_required',receipt=str(receipt),database=str(database),backup=str(backup),
                restore_tested=metadata.get('restore_tested',False),current_matches_backup=same,
                automatic_restore_allowed=False,
                reason='Estado distinto o incierto: puede incluir escrituras posteriores' if not same else 'No se infiere compatibilidad de código/dependencias de una DB idéntica',
                next='Usar --stage para restaurar en copia separada, preservando DB actual. Verificar versión compatible antes de elegir una DB.')


def stage(receipt):
    proposal=plan(receipt)
    database=Path(proposal['database'])
    with maintenance(database):
        proposal=plan(receipt)
        current_backup=create_backup(database,purpose='recovery')
        folder=database.parent/'recovery';folder.mkdir(exist_ok=True)
        directory=Path(tempfile.mkdtemp(prefix='staged-',dir=folder))
        restored=directory/'restored.db'
        with closing(sqlite3.connect(Path(proposal['backup']).as_uri()+'?mode=ro',uri=True)) as source:
            with closing(sqlite3.connect(restored)) as destination:source.backup(destination)
        verify_database(restored)
        if logical_fingerprint(restored)!=logical_fingerprint(proposal['backup']):
            raise sqlite3.DatabaseError('RECOVERY_RESTORE_MISMATCH')
        result=dict(proposal,status='staged',current_snapshot=current_backup,
                    restored_snapshot=str(restored),live_database_unchanged=True,
                    code_dependencies_reverted=False,
                    next='Ambas versiones conservadas. No cambiar BIORAG_PATH ni reiniciar hasta validar código, dependencias y datos elegidos. No se fusionan recuerdos automáticamente.')
        (directory/'recovery.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt',required=True)
    parser.add_argument('--stage',action='store_true',help='Autorizar copias de recuperación, nunca reemplazo de DB viva')
    args=parser.parse_args(argv)
    try:
        print(json.dumps(stage(args.receipt) if args.stage else plan(args.receipt),ensure_ascii=False,indent=2))
        return 0
    except (OSError,ValueError,sqlite3.Error,RuntimeError) as exc:
        print(json.dumps(dict(status='error',message=str(exc)),ensure_ascii=False))
        return 1


if __name__=='__main__':raise SystemExit(main())
