"""Actualizador Git conservador. CLI: python -m core.updater [--yes].

Actualiza solo el checkout donde está instalado este módulo, sin cambiar de rama.
No restaura código/DB automáticamente ni convierte una instalación ajena en Git.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from core.database_access import MaintenanceError


class UpdateError(RuntimeError):
    pass


def git(root, *args):
    return subprocess.run(['git','-C',str(root),*args],check=True,
                          capture_output=True,text=True,timeout=120).stdout.strip()


def installed_root():
    return Path(__file__).resolve().parents[1]


def preflight(root):
    root = Path(root).resolve()
    try:
        top = Path(git(root,'rev-parse','--show-toplevel')).resolve()
    except (OSError,subprocess.SubprocessError) as exc:
        raise UpdateError('INSTALL_METHOD_UNSUPPORTED: no es un checkout Git. Actualiza con el gestor que lo instaló y ejecuta python -m core.lifecycle.') from exc
    if root != top:
        raise UpdateError('INSTALL_ROOT_MISMATCH: no actualizar el repositorio padre de un paquete instalado')
    if git(root,'status','--porcelain','--untracked-files=normal'):
        raise UpdateError('LOCAL_CHANGES: conserva/commit tus cambios antes de actualizar; no se hace stash ni reset automático')
    try:
        branch = git(root,'symbolic-ref','--quiet','--short','HEAD')
    except subprocess.CalledProcessError as exc:
        raise UpdateError('DETACHED_HEAD: usa una rama con upstream antes de actualizar') from exc
    if not branch:
        raise UpdateError('DETACHED_HEAD: configura una rama de actualización explícita')
    if git(root,'ls-files','--stage').find('160000 ') >= 0:
        raise UpdateError('SUBMODULES_UNSUPPORTED: actualizar con el procedimiento del proyecto')
    gitdir = Path(git(root,'rev-parse','--absolute-git-dir'))
    for marker in ('MERGE_HEAD','CHERRY_PICK_HEAD','REVERT_HEAD','rebase-merge','rebase-apply','BISECT_LOG'):
        if (gitdir/marker).exists():
            raise UpdateError('GIT_OPERATION_IN_PROGRESS: '+marker)
    return branch,gitdir


def resolve_target(root, channel):
    if channel == 'dev':
        try:
            upstream = git(root,'rev-parse','--abbrev-ref','--symbolic-full-name','@{upstream}')
        except subprocess.CalledProcessError as exc:
            raise UpdateError('UPSTREAM_REQUIRED: configura el upstream de la rama actual') from exc
        remote,sep,ref = upstream.partition('/')
        if not sep or not remote or remote.startswith('-') or not ref or ref.startswith('-'):
            raise UpdateError('UPSTREAM_REQUIRED: configura el upstream de la rama actual')
        git(root,'fetch','--no-tags',remote,ref)
        target = git(root,'rev-parse','FETCH_HEAD^{commit}')
        return target,upstream
    if channel != 'stable':
        raise UpdateError('CHANNEL_INVALID: elegir dev o stable')
    from core.mcp_server.update_checker import UpdateChecker
    checker=UpdateChecker(enabled=True)
    result=checker.check_once()
    tag=result.get('version_remota')
    if result.get('estado') not in ('actualizacion_disponible','actualizado','version_local_mas_reciente') or not tag or not re.fullmatch(r'v?\d+\.\d+(?:\.\d+)?',tag):
        raise UpdateError('STABLE_NOT_APPROVED: no se pudo validar política y tag')
    # Fuente oficial fija, no el origin arbitrario del checkout.
    git(root,'fetch','--no-tags','https://github.com/dennysjmarquez/MemoryBioRAG.git','refs/tags/'+tag)
    return git(root,'rev-parse','FETCH_HEAD^{commit}'),tag


def plan(root, channel='dev'):
    root=Path(root).resolve();branch,_=preflight(root)
    before=git(root,'rev-parse','HEAD')
    target,source=resolve_target(root,channel)
    try:git(root,'merge-base','--is-ancestor',before,target)
    except subprocess.CalledProcessError as exc:
        raise UpdateError('NON_FAST_FORWARD: destino divergente o anterior; no se modifica tu rama') from exc
    for required in ('pyproject.toml','core/lifecycle.py','core/migrate.py'):
        try:git(root,'cat-file','-e',target+':'+required)
        except subprocess.CalledProcessError as exc:
            raise UpdateError('TARGET_LACKS_LIFECYCLE: '+required) from exc
    return dict(status='planned',root=str(root),branch=branch,channel=channel,
                source=source,before=before,target=target,changed=before!=target)


@contextmanager
def update_lock(gitdir):
    path=gitdir/'biorag-update.lock'
    try:fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except FileExistsError as exc:
        raise UpdateError('UPDATE_LOCKED: hay una actualización activa o lock huérfano; comprobar antes de eliminarlo') from exc
    try:
        with os.fdopen(fd,'w') as file:file.write(str(os.getpid()))
        yield
    finally:path.unlink(missing_ok=True)


def backup_database(database):
    from core.database_backup import create_backup
    return create_backup(database, purpose='update')


def apply(root, *, channel='dev', database, runner=subprocess.run):
    root=Path(root).resolve();_,gitdir=preflight(root)
    database=Path(database).expanduser().resolve()
    if database==root or root in database.parents:
        raise UpdateError('DATABASE_IN_CHECKOUT: usa una DB externa para actualizar con seguridad')
    from core.database_access import maintenance, TOKEN_ENV
    with update_lock(gitdir), maintenance(database) as maintenance_token:
        proposal=plan(root,channel)
        # Datos y recibos fuera del checkout; nunca se permite una DB versionada.
        database=Path(database).expanduser().resolve()
        if database==root or root in database.parents:
            raise UpdateError('DATABASE_IN_CHECKOUT: usa una DB externa para actualizar con seguridad')
        receipt_dir=database.parent/'update-receipts';receipt_dir.mkdir(parents=True,exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=receipt_dir,prefix='update-',suffix='.json',delete=False) as file:
            receipt_path=Path(file.name)
        report=dict(proposal,status='running',phase='backup',backup=None,
                    receipt=str(receipt_path),writers_blocked=False,managed_clients_excluded=True,writer_control='cooperative_managed_connections_only',started_at=datetime.now(timezone.utc).isoformat(),restart_required=True)
        def save():
            tmp=receipt_path.with_suffix('.tmp');tmp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');os.replace(tmp,receipt_path)
        save()
        try:
            report['backup']=backup_database(database)
            if report['backup']:
                from core.database_backup import backup_evidence
                evidence=backup_evidence(report['backup'])
                report['backup_sha256']=evidence.get('backup_sha256')
                report['restore_tested']=evidence.get('restore_tested',False)
            else:
                report['backup_sha256']=None;report['restore_tested']=False
            save()
            report['phase']='code';save()
            # Revalidar tras backup y antes de escribir código.
            preflight(root)
            if git(root,'rev-parse','HEAD')!=proposal['before']:
                raise UpdateError('HEAD_CHANGED: repetir la planificación')
            git(root,'merge','--ff-only',proposal['target'])
            report['phase']='dependencies';save()
            runner([sys.executable,'-m','pip','install','.'],cwd=str(root),check=True,timeout=900)
            report['phase']='lifecycle';save()
            # Proceso NUEVO: importa callbacks del código recién instalado.
            lifecycle_command=[sys.executable,'-m','core.lifecycle','--db',str(database)]
            if report['backup']:
                lifecycle_command += ['--pre-update-backup',report['backup']]
            prepared=runner(lifecycle_command,
                            cwd=str(root),check=True,timeout=300,capture_output=True,text=True,
                            env=dict(os.environ,**({TOKEN_ENV:maintenance_token} if maintenance_token else {})))
            try:
                lifecycle_report=json.loads(prepared.stdout.strip().splitlines()[-1])
            except (AttributeError,IndexError,TypeError,ValueError) as exc:
                raise UpdateError('LIFECYCLE_REPORT_INVALID: proceso sin resultado verificable') from exc
            if not isinstance(lifecycle_report,dict) or lifecycle_report.get('status')!='ok':
                raise UpdateError('LIFECYCLE_REPORT_FAILED: no se confirmó preparación')
            report['lifecycle']=lifecycle_report
            from core.database_backup import verify_database, finish_backup, prune_successful
            report['database_verification']=verify_database(database)
            finish_backup(report['backup'], success=True)
            report['retention']=prune_successful(database)
            report.update(status='ok',phase='complete',finished_at=datetime.now(timezone.utc).isoformat(),after=git(root,'rev-parse','HEAD'))
            save();return report
        except Exception as exc:
            from core.database_backup import finish_backup
            try:finish_backup(report['backup'], success=False)
            except (OSError,ValueError):pass  # Backup pendiente sigue protegido si metadata no se pudo actualizar.
            if report['phase']=='lifecycle' and isinstance(exc,subprocess.CalledProcessError):
                try:
                    failed_report=json.loads((exc.stdout or '').strip().splitlines()[-1])
                    if isinstance(failed_report,dict):report['lifecycle']=failed_report
                except (IndexError,TypeError,ValueError):
                    pass  # Conserva fallo de proceso; jamás convierte ausencia de informe en éxito.
            report.update(status='recovery_required',finished_at=datetime.now(timezone.utc).isoformat(),error=type(exc).__name__,detail=str(exc),
                          recovery='No rollback automático de código/dependencias/DB. Conserva backup y recibo; corrige la fase fallida y repite update. No arranques MCP hasta verificar.')
            save();raise UpdateError('UPDATE_FAILED: fase '+report['phase']+'; recibo '+str(receipt_path)+'; '+str(exc)) from exc


def main(argv=None):
    from core.cli_notes import usage_note
    parser=argparse.ArgumentParser(description=__doc__, epilog=usage_note('update'))
    parser.add_argument('--channel',choices=('dev','stable'),default='dev')
    parser.add_argument('--dry-run',action='store_true',help='Planificación sin aplicar; equivalente al modo por defecto')
    parser.add_argument('--yes',action='store_true',help='autorizar actualización; sin esta opción solo planifica')
    parser.add_argument('--db',help='DB externa; por defecto resolución de rutas del core')
    args=parser.parse_args(argv)
    if args.dry_run and args.yes:
        parser.error('--dry-run y --yes son incompatibles')
    try:
        if not args.yes:
            result=plan(installed_root(),args.channel)
            result['next']='Detén clientes MCP/servicios de esta instalación y repite con --yes. No se publica ningún release.'
        else:
            from core.paths import resolve_db_path
            result=apply(installed_root(),channel=args.channel,database=args.db or resolve_db_path())
        print(json.dumps(result,ensure_ascii=False,indent=2));return 0
    except (UpdateError,MaintenanceError,OSError,subprocess.SubprocessError) as exc:
        print(json.dumps(dict(status='error',message=str(exc)),ensure_ascii=False),file=sys.stderr);return 1


if __name__=='__main__':
    raise SystemExit(main())
