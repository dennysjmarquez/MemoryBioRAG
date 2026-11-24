"""Safe Git updater; CLI: python -m core.updater [--dry-run].

Applies by default, stops only BioRAG's verified managed daemon, and creates a
verified database backup. Failures trigger automatic rollback where verifiable.
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
    managed_daemon_status,
    stop_managed_daemon,
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
    try:
        process_status=managed_daemon_status(root)
    except ProcessInspectionError:
        process_status={'status':'verification_failed',
                        'message':'BioRAG could not safely verify its own background service; no process will be stopped.'}
    return dict(status='planned',root=str(root),branch=branch,channel=channel,
                source=source,before=before,target=target,changed=changed,
                database=database_status,managed_daemon=process_status)


@contextmanager
def update_lock(gitdir):
    path = gitdir / 'biorag-update.lock'
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    file = os.fdopen(fd, 'r+')
    overlapped = None
    try:
        if os.name == 'posix':
            import fcntl
            try:
                fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except (BlockingIOError, OSError) as exc:
                raise UpdateError('UPDATE_LOCKED: An update is currently running in another process.') from exc
        elif os.name == 'nt':
            from core.database_access import _windows_lock
            try:
                overlapped = _windows_lock(file, exclusive=True)
            except (BlockingIOError, OSError) as exc:
                raise UpdateError('UPDATE_LOCKED: An update is currently running in another process.') from exc
        else:
            raise UpdateError('UPDATE_PLATFORM_UNSUPPORTED: no tested OS lock backend')

        file.seek(0)
        file.truncate(0)
        file.write(str(os.getpid()))
        file.flush()
        yield
    finally:
        try:
            if os.name == 'nt' and overlapped is not None:
                from core.database_access import _unlock
                _unlock(file, overlapped)
            elif os.name == 'posix':
                import fcntl
                try:
                    fcntl.flock(file, fcntl.LOCK_UN)
                except OSError:
                    pass
        finally:
            file.close()


@contextmanager
def exclusive_update(root, gitdir, database, channel, wait=30.0):
    """Plan, stop verified DB users, and hold the exclusive OS lease through apply."""
    with update_lock(gitdir):
        proposal = plan(root, channel, database=database)
        db_state = proposal.get('database', {}).get('status')
        if db_state in {'check_failed', 'unreadable', 'database_integrity_failed'}:
            raise UpdateError('DATABASE_PREFLIGHT_FAILED: no code or database changes were made; inspect the read-only database report before retrying.')
        from core.update_barrier import activate, runtime_status
        prior_barrier = runtime_status(database)
        if not prior_barrier['allowed']:
            raise UpdateError('UPDATE_BARRIER_ACTIVE: a previous update needs recovery; no process or data was changed.')
        stopped = stop_managed_daemon(root)
        progress = {'phase':'backup', 'preexisting_barrier':False}
        try:
            activate(database, update_id=proposal['target'], phase='backup')
        except Exception:
            try: restart_stopped_daemon(stopped, root)
            except Exception: pass
            raise
        from core.database_access import maintenance
        try:
            with maintenance(database, timeout=wait) as token:
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
                        progress['service_restart'] = restart_stopped_daemon(stopped, root)
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


def restart_stopped_daemon(process_stop, root=None):
    """Restart only the BioRAG daemon that this authorized update actually stopped."""
    stopped = process_stop.get('stopped', []) if isinstance(process_stop, dict) else []
    if not any(item.get('kind') == 'daemon' for item in stopped):
        return {'status':'not_needed'}
    from core.daemon_lifecycle import spawn_daemon_detached
    if not spawn_daemon_detached():
        raise UpdateError('DAEMON_RESTART_FAILED: BioRAG could not confirm its background service restarted.')
    try:
        status=managed_daemon_status(root or installed_root())
    except ProcessInspectionError as exc:
        raise UpdateError('DAEMON_RESTART_UNVERIFIED: BioRAG could not verify its restarted background service.') from exc
    if status.get('status')!='running':
        raise UpdateError('DAEMON_RESTART_UNVERIFIED: BioRAG could not verify its restarted background service.')
    return {'status':'ok','pid':status.get('pid'),'startup_verified':True}


def backup_database(database):
    from core.database_backup import create_backup
    return create_backup(database, purpose='update')


def dependency_inventory():
    """Installed package versions, used to avoid claiming a dependency rollback blindly."""
    from importlib.metadata import distributions
    inventory={}
    for distribution in distributions():
        name=distribution.metadata.get('Name')
        version=distribution.version
        if name:
            inventory[name.strip().lower().replace('_','-')]=version
    return dict(sorted(inventory.items()))


def restore_database_backup(backup, database):
    """Restore a verified snapshot atomically beside the live SQLite database."""
    from contextlib import closing
    import sqlite3
    from core.database_backup import logical_fingerprint, validate_update_backup, verify_database

    backup = Path(validate_update_backup(backup, database))
    target = Path(database).expanduser().resolve()
    with tempfile.NamedTemporaryFile(dir=target.parent, prefix=target.name+'.restore-',
                                     suffix='.db', delete=False) as file:
        temporary = Path(file.name)
    try:
        with closing(sqlite3.connect(backup.as_uri()+'?mode=ro', uri=True)) as source:
            with closing(sqlite3.connect(str(temporary))) as destination:
                source.backup(destination)
        verify_database(temporary)
        expected_fingerprint=logical_fingerprint(backup)
        if logical_fingerprint(temporary)!=expected_fingerprint:
            raise UpdateError('DATABASE_RESTORE_CONTENT_MISMATCH')
        os.replace(temporary, target)
        # Under the update lease and after managed services are stopped, these are
        # stale files from the replaced DB; never remove them before replacement.
        Path(str(target)+'-wal').unlink(missing_ok=True)
        Path(str(target)+'-shm').unlink(missing_ok=True)
        verify_database(target)
        if logical_fingerprint(target)!=expected_fingerprint:
            raise UpdateError('DATABASE_RESTORE_CONTENT_MISMATCH')
    finally:
        # Clean up WAL/SHM files left by verify_database opening the temporary copy.
        Path(str(temporary) + '-wal').unlink(missing_ok=True)
        Path(str(temporary) + '-shm').unlink(missing_ok=True)
        temporary.unlink(missing_ok=True)


def rollback_update(root, database, report, process_stop, runner):
    """Best-effort full rollback. Failure keeps the barrier and backup for recovery."""
    root = Path(root).resolve()
    before = report.get('before')
    current = git(root, 'rev-parse', 'HEAD')
    dependency_mismatch = None
    dependency_restore_error = None
    dependency_restore_attempted = current != before
    if current != before:
        # This is safe because preflight required a clean checkout and the updater
        # only performed a fast-forward. Never reset an unexpected user revision.
        if current != report.get('target'):
            raise UpdateError('ROLLBACK_HEAD_UNEXPECTED: refusing to reset an unexpected checkout state.')
        git(root, 'reset', '--hard', before)
        if git(root, 'rev-parse', 'HEAD') != before:
            raise UpdateError('CODE_ROLLBACK_NOT_VERIFIED')
        try:
            runner([sys.executable, '-m', 'pip', 'install', '.'], cwd=str(root),
                   check=True, timeout=900)
        except Exception as exc:
            dependency_restore_error=exc
    if dependency_restore_attempted or report.get('phase') in {'dependencies','lifecycle'}:
        try:
            actual_dependencies=dependency_inventory()
            if report.get('dependencies_before') != actual_dependencies:
                dependency_mismatch='DEPENDENCY_ROLLBACK_NOT_VERIFIED'
        except Exception:
            dependency_mismatch='DEPENDENCY_ROLLBACK_NOT_VERIFIED'
    if report.get('backup'):
        restore_database_backup(report['backup'], database)
    elif report.get('database_existed_before') is False:
        Path(database).unlink(missing_ok=True)
    if dependency_restore_error is not None:
        raise UpdateError('DEPENDENCY_RESTORE_FAILED') from dependency_restore_error
    if dependency_mismatch:
        raise UpdateError(dependency_mismatch)
    if not report.get('preexisting_barrier'):
        from core.update_barrier import clear
        clear(database)
        restarted = restart_stopped_daemon(process_stop, root)
    else:
        restarted = {'status':'not_restarted_preexisting_barrier'}
    return {'status':'ok', 'code_revision':before, 'database_restored':bool(report.get('backup')),
            'service_restart':restarted}


def apply(root, *, channel='dev', database, runner=subprocess.run, wait=30.0):
    root=Path(root).resolve();_,gitdir=preflight(root)
    database=Path(database).expanduser().resolve()
    if database==root or root in database.parents:
        raise UpdateError('DATABASE_IN_CHECKOUT: Use a database outside the Git checkout for a safe update.')
    from core.database_access import TOKEN_ENV
    with exclusive_update(root,gitdir,database,channel,wait=wait) as (maintenance_token, process_stop, proposal, progress):
        # Datos y recibos fuera del checkout; nunca se permite una DB versionada.
        database=Path(database).expanduser().resolve()
        if database==root or root in database.parents:
            raise UpdateError('DATABASE_IN_CHECKOUT: Use a database outside the Git checkout for a safe update.')
        receipt_dir=database.parent/'update-receipts';receipt_dir.mkdir(parents=True,exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=receipt_dir,prefix='update-',suffix='.json',delete=False) as file:
            receipt_path=Path(file.name)
        report=dict(proposal,status='running',phase='backup',backup=None,
                    database_existed_before=database.is_file(),
                    preexisting_barrier=progress.get('preexisting_barrier',False),
                    receipt=str(receipt_path),process_stop=process_stop,
                    mcp_restart={
                        'required':False,
                        'owner':'external_mcp_host',
                        'status':'host_restart_recommended',
                        'health_check':'reconnect_host_and_verify_update_id',
                    },
                    writers_blocked='managed_clients_only',managed_clients_excluded=True,
                    writer_control='cross_platform_shared_exclusive_database_lease_and_verified_managed_daemon_stop',
                    started_at=datetime.now(timezone.utc).isoformat(),restart_required=True)
        def save():
            tmp=receipt_path.with_suffix('.tmp');tmp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');os.replace(tmp,receipt_path)
        save()
        try:
            report['dependencies_before']=dependency_inventory()
            report['backup']=backup_database(database)
            if report['database_existed_before'] and not report['backup']:
                raise UpdateError('DATABASE_BACKUP_UNAVAILABLE: an existing database must have a verified backup before update.')
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
            from core.database_backup import verify_database
            report['database_verification']=verify_database(database)
            report['database_status']=lifecycle_report.get('database_status')
            if (not isinstance(report['database_status'],dict)
                    or report['database_status'].get('status')!='ready'
                    or report['database_status'].get('applied_update_id') != proposal['target']
                    or report['database_status'].get('expected_update_id') != proposal['target']):
                raise UpdateError('DATABASE_UPDATE_NOT_CONFIRMED: The new lifecycle process did not verify the schema and exact applied update ID.')
            from core.update_barrier import clear
            clear(database)
            report.update(status='ok',phase='complete',finished_at=datetime.now(timezone.utc).isoformat(),after=git(root,'rev-parse','HEAD'))
            if report['backup']:
                report['backup_cleanup']='pending'
            save()
            report['service_restart']=restart_stopped_daemon(process_stop, root)
            try:save()
            except OSError:pass  # El recibo de éxito previo ya confirma la verificación durable.
            if report['backup']:
                backup_path=Path(report['backup'])
                try:
                    backup_path.unlink(missing_ok=True)
                    Path(str(backup_path)+'.json').unlink(missing_ok=True)
                    report['backup_cleanup']='removed_after_verified_success'
                except OSError:
                    report['backup_cleanup']='warning_backup_retained'
                try:save()
                except OSError:pass  # El recibo de éxito ya es durable; la limpieza es solo housekeeping.
            return report
        except BaseException as exc:
            from core.database_backup import finish_backup
            if report['phase']=='lifecycle' and isinstance(exc,subprocess.CalledProcessError):
                try:
                    failed_report=json.loads((exc.stdout or '').strip().splitlines()[-1])
                    if isinstance(failed_report,dict):report['lifecycle']=failed_report
                except (IndexError,TypeError,ValueError):
                    pass  # Conserva fallo de proceso; jamás convierte ausencia de informe en éxito.
            try:
                report['rollback']=rollback_update(
                    root, database, report, process_stop, runner)
                try:finish_backup(report['backup'], success=False)
                except (OSError,ValueError):pass
                report.update(status='rolled_back',phase='rollback_complete',
                              finished_at=datetime.now(timezone.utc).isoformat(),
                              error=type(exc).__name__,detail=str(exc),
                              recovery='The update did not complete. The previous code, dependencies, and database were restored and verified; the protected backup and receipt were retained.')
                save()
                return report
            except Exception as rollback_exc:
                try:
                    from core.update_barrier import activate
                    activate(database, update_id=report.get('target', 'unknown'), phase='recovery')
                    barrier_state='active'
                except Exception:
                    barrier_state='unconfirmed'
                try:finish_backup(report['backup'], success=False)
                except (OSError,ValueError):pass
                report.update(status='recovery_required',safety_barrier=barrier_state,
                              finished_at=datetime.now(timezone.utc).isoformat(),
                              error=type(exc).__name__,detail=str(exc),rollback_error=type(rollback_exc).__name__,
                              rollback_detail=str(rollback_exc),
                              recovery='Automatic rollback could not be fully verified. The safety barrier remains active; keep the backup and receipt and contact support before restarting BioRAG.')
                save()
                raise UpdateError('UPDATE_RECOVERY_REQUIRED: phase '+report['phase']+'; receipt '+str(receipt_path)+'; '+str(rollback_exc)) from exc


def _public_result(result):
    """Keep machine diagnostics in the receipt, not in the nontechnical CLI output."""
    status=result.get('status')
    if status=='rolled_back':
        return {'status':status,
                'message':'The update could not be completed. The previous version and database were restored; a backup was kept.',
                'receipt':result.get('receipt'),'backup':result.get('backup')}
    if status=='recovery_required':
        return {'status':status,
                'message':'Automatic recovery could not be verified. Do not restart BioRAG; keep the receipt and contact support.',
                'receipt':result.get('receipt'),'backup':result.get('backup'),
                'safety_barrier':result.get('safety_barrier')}
    if status=='ok' and 'receipt' in result:
        return {'status':'ok','message':'The update was applied and verified. Reconnect the agent host to load the updated program.',
                'receipt':result.get('receipt'),'channel':result.get('channel'),
                'backup_cleanup':result.get('backup_cleanup','not_needed'),
                'host_restart_recommended':True}
    return result


def main(argv=None):
    from core.cli_notes import usage_note, command_examples
    parser=HelpParser(prog='biorag update',
        description='Apply a safe Git-based program update by default, or preview it with --dry-run.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=usage_note('update') + '\n\n' + command_examples('update'))
    parser.add_argument('--channel',choices=('dev','stable'),default='dev', help='dev: upstream of the installed branch; stable: policy-approved official tag; both require fast-forward')
    parser.add_argument('--dry-run',action='store_true',help='Preview the update without applying it')
    parser.add_argument('--yes',action='store_true',help='Deprecated compatibility option; updates now apply by default')
    parser.add_argument('--db',help='Database outside the checkout; defaults to BIORAG_PATH or the canonical path')
    parser.add_argument('--wait',type=float,default=30.0,help='Seconds to wait for active BioRAG clients to close (default: 30; older MCP servers without pending-gate support ignore the signal)')
    args=parser.parse_args(argv)
    if args.wait < 0:
        parser.error('--wait must be non-negative.')
    if args.dry_run and args.yes:
        parser.error('--dry-run and --yes cannot be combined.')
    try:
        from core.paths import resolve_db_path
        database=args.db or resolve_db_path()
        if args.dry_run:
            result=plan(installed_root(),args.channel,database=database)
            result['next']='Preview only: no changes were made. Run biorag update to apply safely.'
        else:
            result=apply(installed_root(),channel=args.channel,database=database,wait=args.wait)
        print(json.dumps(_public_result(result),ensure_ascii=False,indent=2))
        return 1 if result.get('status') in {'rolled_back','recovery_required'} else 0
    except (UpdateError,MaintenanceError,ProcessInspectionError,OSError,subprocess.SubprocessError) as exc:
        if isinstance(exc,ProcessInspectionError):
            message='BioRAG could not safely verify its own background service. Nothing was changed; try again later or contact support.'
        elif 'LOCAL_CHANGES:' in str(exc):
            message='The update was not started because this installation has local changes. Your files were left untouched; please commit or stash your changes before updating.'
        elif 'NON_FAST_FORWARD:' in str(exc):
            message='No update applied: the local installation is either already up to date or has diverged from the remote branch.'
        elif 'UPDATE_RECOVERY_REQUIRED:' in str(exc):
            message='Automatic recovery could not be verified. Do not restart BioRAG; keep the update receipt and contact support.'
            match=re.search(r'receipt (\S+)',str(exc))
            if match:message+=' Receipt: '+match.group(1)
        elif isinstance(exc,MaintenanceError):
            message='BioRAG is currently using the memory database. Wait for active work to finish, then try the update again.'
        else:
            message='BioRAG could not safely start the update. No update was applied; try again later or contact support.'
        print(json.dumps(dict(status='error',message=message),ensure_ascii=False),file=sys.stderr);return 1


if __name__=='__main__':
    raise SystemExit(main())
