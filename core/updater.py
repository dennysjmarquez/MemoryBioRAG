"""Actualizador Git conservador. CLI: python -m core.updater [--yes].

Actualiza solo el checkout donde está instalado este módulo, sin cambiar de rama.
No restaura código/DB automáticamente ni convierte una instalación ajena en Git.
"""
from __future__ import annotations
import argparse
from core.cli_help import HelpParser
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
from core.process_inspection import (
    ProcessInspectionError,
    inspect_database_processes,
    stop_known_database_processes,
)


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
        raise UpdateError('INSTALL_METHOD_UNSUPPORTED: This is not a Git checkout. Update it with the installer or package manager that installed it, then run python -m core.lifecycle.') from exc
    if root != top:
        raise UpdateError('INSTALL_ROOT_MISMATCH: The installation root is not the Git repository root; refusing to update its parent repository.')
    if git(root,'status','--porcelain','--untracked-files=normal'):
        raise UpdateError('LOCAL_CHANGES: Preserve or commit your local changes before updating. No automatic stash or reset will be performed.')
    try:
        branch = git(root,'symbolic-ref','--quiet','--short','HEAD')
    except subprocess.CalledProcessError as exc:
        raise UpdateError('DETACHED_HEAD: Check out a branch with an upstream before updating.') from exc
    if not branch:
        raise UpdateError('DETACHED_HEAD: Configure an explicit update branch.')
    if git(root,'ls-files','--stage').find('160000 ') >= 0:
        raise UpdateError('SUBMODULES_UNSUPPORTED: Submodules are not supported by this updater; use the project update procedure.')
    gitdir = Path(git(root,'rev-parse','--absolute-git-dir'))
    for marker in ('MERGE_HEAD','CHERRY_PICK_HEAD','REVERT_HEAD','rebase-merge','rebase-apply','BISECT_LOG'):
        if (gitdir/marker).exists():
            raise UpdateError('GIT_OPERATION_IN_PROGRESS: A Git operation is in progress ('+marker+'). Finish it before updating.')
    return branch,gitdir


def resolve_target(root, channel):
    if channel == 'dev':
        try:
            upstream = git(root,'rev-parse','--abbrev-ref','--symbolic-full-name','@{upstream}')
        except subprocess.CalledProcessError as exc:
            raise UpdateError('UPSTREAM_REQUIRED: Configure an upstream for the current branch.') from exc
        remote,sep,ref = upstream.partition('/')
        if not sep or not remote or remote.startswith('-') or not ref or ref.startswith('-'):
            raise UpdateError('UPSTREAM_REQUIRED: Configure an upstream for the current branch.')
        git(root,'fetch','--no-tags',remote,ref)
        target = git(root,'rev-parse','FETCH_HEAD^{commit}')
        return target,upstream
    if channel != 'stable':
        raise UpdateError('CHANNEL_INVALID: Choose dev or stable.')
    from core.mcp_server.update_checker import UpdateChecker
    checker=UpdateChecker(enabled=True)
    result=checker.check_once()
    tag=result.get('version_remota')
    if result.get('estado') not in ('actualizacion_disponible','actualizado','version_local_mas_reciente') or not tag or not re.fullmatch(r'v?\d+\.\d+(?:\.\d+)?',tag):
        raise UpdateError('STABLE_NOT_APPROVED: The release policy and tag could not be validated.')
    # Fuente oficial fija, no el origin arbitrario del checkout.
    git(root,'fetch','--no-tags','https://github.com/dennysjmarquez/MemoryBioRAG.git','refs/tags/'+tag)
    return git(root,'rev-parse','FETCH_HEAD^{commit}'),tag


def plan(root, channel='dev', *, database=None):
    root=Path(root).resolve();branch,_=preflight(root)
    before=git(root,'rev-parse','HEAD')
    target,source=resolve_target(root,channel)
    try:git(root,'merge-base','--is-ancestor',before,target)
    except subprocess.CalledProcessError as exc:
        raise UpdateError('NON_FAST_FORWARD: The target is behind or has diverged; the current branch will not be modified.') from exc
    for required in ('pyproject.toml','core/lifecycle.py','core/migrate.py'):
        try:git(root,'cat-file','-e',target+':'+required)
        except subprocess.CalledProcessError as exc:
            raise UpdateError('TARGET_LACKS_LIFECYCLE: The update target is missing required file '+required) from exc
    if database is None:
        database_status=dict(status='not_checked',message='No database path was supplied to the planner.')
    else:
        from core.schema_status import inspect_database
        database_status=inspect_database(database,expected_update_id=before)
    changed=before!=target
    database_status['target_update_id']=target
    database_status['lifecycle_required']=changed or database_status.get('status')!='ready'
    process_status=inspect_database_processes(database) if database is not None else {
        'status':'not_checked','holders':[],'scan_errors':[]}
    return dict(status='planned',root=str(root),branch=branch,channel=channel,
                source=source,before=before,target=target,changed=changed,
                database=database_status,database_processes=process_status)


@contextmanager
def update_lock(gitdir):
    path=gitdir/'biorag-update.lock'
    try:fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except FileExistsError as exc:
        raise UpdateError('UPDATE_LOCKED: An update may be running or the lock may be stale; verify before removing it.') from exc
    try:
        with os.fdopen(fd,'w') as file:file.write(str(os.getpid()))
        yield
    finally:path.unlink(missing_ok=True)


@contextmanager
def exclusive_update(root, gitdir, database, channel):
    """Plan, stop verified DB users, and hold the exclusive OS lease through apply."""
    with update_lock(gitdir):
        proposal = plan(root, channel, database=database)
        db_state = proposal.get('database', {}).get('status')
        if db_state in {'check_failed', 'unreadable', 'database_integrity_failed'}:
            raise UpdateError('DATABASE_PREFLIGHT_FAILED: no code or database changes were made; inspect the read-only database report before retrying.')
        stopped = stop_known_database_processes(database)
        from core.update_barrier import activate, runtime_status
        prior_barrier = runtime_status(database)
        progress = {'phase':'backup', 'preexisting_barrier':not prior_barrier['allowed']}
        try:
            activate(database, update_id=proposal['target'], phase='backup')
        except Exception:
            try: restart_stopped_daemon(stopped)
            except Exception: pass
            raise
        from core.database_access import maintenance
        try:
            with maintenance(database) as token:
                yield token, stopped, proposal, progress
        except BaseException:
            # Before code moves, the old service remains compatible and can be restored.
            # Once HEAD advances, keep the daemon stopped until the new DB lifecycle is verified.
            if progress['phase'] in {'backup', 'code'}:
                try:
                    unchanged = git(root, 'rev-parse', 'HEAD') == proposal['before']
                except (OSError, subprocess.SubprocessError):
                    unchanged = False
                if unchanged:
                    try:
                        progress['service_restart'] = restart_stopped_daemon(stopped)
                    except Exception as restart_exc:
                        progress['service_restart'] = {
                            'status':'failed', 'detail':str(restart_exc)}
                    if not progress['preexisting_barrier']:
                        try:
                            from core.update_barrier import clear
                            clear(database)
                        except Exception as barrier_exc:
                            progress['barrier_clear_error'] = str(barrier_exc)
            raise


def restart_stopped_daemon(process_stop):
    """Restart only the BioRAG daemon that this authorized update actually stopped."""
    stopped = process_stop.get('stopped', []) if isinstance(process_stop, dict) else []
    if not any(item.get('kind') == 'daemon' for item in stopped):
        return {'status':'not_needed'}
    from core.daemon_lifecycle import spawn_daemon_detached
    if not spawn_daemon_detached():
        raise UpdateError('DAEMON_RESTART_FAILED: code and database are prepared, but the previously active daemon did not confirm startup.')
    return {'status':'ok'}


def backup_database(database):
    from core.database_backup import create_backup
    return create_backup(database, purpose='update')


def apply(root, *, channel='dev', database, runner=subprocess.run):
    root=Path(root).resolve();_,gitdir=preflight(root)
    database=Path(database).expanduser().resolve()
    if database==root or root in database.parents:
        raise UpdateError('DATABASE_IN_CHECKOUT: Use a database outside the Git checkout for a safe update.')
    from core.database_access import TOKEN_ENV
    with exclusive_update(root,gitdir,database,channel) as (maintenance_token, process_stop, proposal, progress):
        # Datos y recibos fuera del checkout; nunca se permite una DB versionada.
        database=Path(database).expanduser().resolve()
        if database==root or root in database.parents:
            raise UpdateError('DATABASE_IN_CHECKOUT: Use a database outside the Git checkout for a safe update.')
        receipt_dir=database.parent/'update-receipts';receipt_dir.mkdir(parents=True,exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=receipt_dir,prefix='update-',suffix='.json',delete=False) as file:
            receipt_path=Path(file.name)
        mcp_was_stopped = any(
            isinstance(item, dict) and item.get('kind') == 'mcp'
            for item in process_stop.get('stopped', [])
        ) if isinstance(process_stop, dict) else False
        report=dict(proposal,status='running',phase='backup',backup=None,
                    receipt=str(receipt_path),process_stop=process_stop,
                    mcp_restart={
                        'required':mcp_was_stopped,
                        'owner':'external_mcp_host',
                        'status':'pending_host_reconnect' if mcp_was_stopped else 'not_required',
                        'health_check':'host_must_reconnect_and_verify_update_id' if mcp_was_stopped else 'not_applicable',
                    },
                    writers_blocked=True,managed_clients_excluded=True,
                    writer_control='cross_platform_database_lease_plus_verified_process_inventory',
                    started_at=datetime.now(timezone.utc).isoformat(),restart_required=True)
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
            report['phase']='code';progress['phase']='code'
            from core.update_barrier import activate
            activate(database, update_id=proposal['target'], phase='code')
            save()
            # Revalidar tras backup y antes de escribir código.
            preflight(root)
            if git(root,'rev-parse','HEAD')!=proposal['before']:
                raise UpdateError('HEAD_CHANGED: HEAD changed after planning; create a new plan.')
            git(root,'merge','--ff-only',proposal['target'])
            report['phase']='dependencies';progress['phase']='dependencies'
            activate(database, update_id=proposal['target'], phase='dependencies')
            save()
            runner([sys.executable,'-m','pip','install','.'],cwd=str(root),check=True,timeout=900)
            report['phase']='lifecycle';progress['phase']='lifecycle'
            activate(database, update_id=proposal['target'], phase='lifecycle')
            save()
            # Proceso NUEVO: importa callbacks del código recién instalado.
            lifecycle_command=[sys.executable,'-m','core.lifecycle','--db',str(database),
                               '--update-id',proposal['target']]
            if report['backup']:
                lifecycle_command += ['--pre-update-backup',report['backup']]
            prepared=runner(lifecycle_command,
                            cwd=str(root),check=True,timeout=300,capture_output=True,text=True,
                            env=dict(os.environ,**({TOKEN_ENV:maintenance_token} if maintenance_token else {})))
            try:
                lifecycle_report=json.loads(prepared.stdout.strip().splitlines()[-1])
            except (AttributeError,IndexError,TypeError,ValueError) as exc:
                raise UpdateError('LIFECYCLE_REPORT_INVALID: The lifecycle process returned no verifiable report.') from exc
            if (not isinstance(lifecycle_report,dict)
                    or lifecycle_report.get('status')!='ok'
                    or lifecycle_report.get('update_id') != proposal['target']):
                raise UpdateError('LIFECYCLE_REPORT_FAILED: The new lifecycle process did not confirm this exact update ID.')
            report['lifecycle']=lifecycle_report
            from core.database_backup import verify_database, finish_backup, prune_successful
            report['database_verification']=verify_database(database)
            report['database_status']=lifecycle_report.get('database_status')
            if (not isinstance(report['database_status'],dict)
                    or report['database_status'].get('status')!='ready'
                    or report['database_status'].get('applied_update_id') != proposal['target']
                    or report['database_status'].get('expected_update_id') != proposal['target']):
                raise UpdateError('DATABASE_UPDATE_NOT_CONFIRMED: The new lifecycle process did not verify the schema and exact applied update ID.')
            from core.update_barrier import clear
            clear(database)
            report['service_restart']=restart_stopped_daemon(process_stop)
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
                          recovery='No automatic rollback of code, dependencies, or the database was performed. Keep the backup and receipt; fix the failed phase and retry the update. Do not start MCP until verification is complete.')
            save();raise UpdateError('UPDATE_FAILED: phase '+report['phase']+'; receipt '+str(receipt_path)+'; '+str(exc)) from exc


def main(argv=None):
    from core.cli_notes import usage_note, command_examples
    parser=HelpParser(prog='biorag update',
        description='Plan or apply a conservative Git-based program update without switching branches.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=usage_note('update') + '\n\n' + command_examples('update'))
    parser.add_argument('--channel',choices=('dev','stable'),default='dev', help='dev: upstream of the installed branch; stable: policy-approved official tag; both require fast-forward')
    parser.add_argument('--dry-run',action='store_true',help='Plan without applying; includes a read-only database schema and applied-update check')
    parser.add_argument('--yes',action='store_true',help='Authorize applying the update; otherwise only plan')
    parser.add_argument('--db',help='Database outside the checkout; defaults to BIORAG_PATH or the canonical path')
    args=parser.parse_args(argv)
    if args.dry_run and args.yes:
        parser.error('--dry-run and --yes cannot be combined.')
    try:
        from core.paths import resolve_db_path
        database=args.db or resolve_db_path()
        if not args.yes:
            result=plan(installed_root(),args.channel,database=database)
            database_status=result.get('database',{}).get('status')
            if database_status in ('check_failed','unreadable','database_integrity_failed'):
                result['next']='The database check failed. Inspect the reported database path and error and resolve it before authorizing an update; no code or database changes were made.'
            elif result.get('changed'):
                result['next']='After explicit authorization, rerun with --yes. The CLI inventories users of this database, stops only recognized BioRAG MCP/daemon/CLI/worker processes, and refuses unknown or uninspectable holders before backing up, updating, preparing, and verifying. Restart the MCP host if it does not respawn its server.'
            elif database_status=='ready':
                result['next']='This checkout already matches its upstream revision. No code update is available, and the database lifecycle is verified for this checkout; no source files or database were changed.'
            else:
                result['next']='No code update is available, but database preparation is not confirmed. After explicit authorization, rerun with --yes; the CLI will inventory database users, stop only recognized BioRAG MCP/daemon/CLI/worker processes, then back up, prepare, and verify. Unknown or uninspectable holders block the operation.'
        else:
            result=apply(installed_root(),channel=args.channel,database=database)
        print(json.dumps(result,ensure_ascii=False,indent=2));return 0
    except (UpdateError,MaintenanceError,ProcessInspectionError,OSError,subprocess.SubprocessError) as exc:
        print(json.dumps(dict(status='error',message=str(exc)),ensure_ascii=False),file=sys.stderr);return 1


if __name__=='__main__':
    raise SystemExit(main())
