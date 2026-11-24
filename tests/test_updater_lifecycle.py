"""Actualización en repositorios Git temporales; sin red ni DB viva."""
from contextlib import contextmanager, redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from core.lifecycle import Step, prepare
from core import updater


class LifecycleTests(unittest.TestCase):
    def test_order_and_repeat(self):
        log=[]
        def run(name):
            def fn(database):
                log.append((name,database));return {'status':'ok'}
            return fn
        steps=[Step('schema',run('schema')),Step('files',run('files'))]
        for _ in range(2):self.assertEqual(prepare('copy.db',steps=steps)['status'],'ok')
        self.assertEqual([name for name,_ in log],['schema','files','schema','files'])

    def test_failure_blocks_later_steps(self):
        log=[]
        def fail(_):return {'status':'failed'}
        with self.assertRaisesRegex(RuntimeError,'LIFECYCLE_VERIFICATION_FAILED'):
            prepare('copy.db',steps=[Step('first',fail),Step('never',lambda _:log.append(True))])
        self.assertFalse(log)

    def test_error_identifies_failed_component_and_completed_steps(self):
        from core.lifecycle import PreparationError
        def fail(_):raise OSError('injected')
        with self.assertRaises(PreparationError) as caught:
            prepare('copy.db',steps=[Step('schema',lambda _: {'status':'ok'}),Step('files',fail)])
        self.assertEqual(caught.exception.step,'files')
        self.assertEqual(caught.exception.completed[0]['step'],'schema')

    def test_duplicate_names_fail_before_side_effects(self):
        log=[]
        fn=lambda _:log.append(True)
        with self.assertRaises(ValueError):prepare('copy.db',steps=[Step('same',fn),Step('same',fn)])
        self.assertFalse(log)


class GitUpdaterTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.home=Path(self.tmp.name);self.root=self.home/'checkout';self.root.mkdir()
        self.db=self.home/'data'/'memory.db';self.db.parent.mkdir()
        self.git('init','--initial-branch=current')
        self.git('config','user.email','test@example.invalid');self.git('config','user.name','Synthetic Test')
        (self.root/'core').mkdir()
        for name in ('core/__init__.py','core/lifecycle.py','core/migrate.py','pyproject.toml'):(self.root/name).write_text('# synthetic\n')
        self.git('add','.');self.git('commit','-m','base')
        self.before=self.git('rev-parse','HEAD')
        self.git('commit','--allow-empty','-m','target');self.target=self.git('rev-parse','HEAD')
        self.git('update-ref','refs/heads/current',self.before)
        with sqlite3.connect(self.db) as db:
            db.execute('CREATE TABLE memories(value TEXT)');db.execute("INSERT INTO memories VALUES ('preserve')")
        self.patch=patch.object(updater,'resolve_target',return_value=(self.target,'origin/current'));self.patch.start()
        self.schema_patch=patch('core.schema_status.inspect_database',return_value={'status':'ready'})
        self.schema_patch.start()
        self.daemon_patch=patch.object(updater,'stop_managed_daemon',return_value={'status':'not_running','stopped':[]})
        self.daemon_patch.start()

    def tearDown(self):
        self.daemon_patch.stop();self.schema_patch.stop();self.patch.stop();self.tmp.cleanup()

    def git(self,*args):
        return subprocess.run(['git','-C',str(self.root),*args],check=True,capture_output=True,text=True).stdout.strip()

    def test_plan_does_not_change_code_or_data(self):
        report=updater.plan(self.root)
        self.assertTrue(report['changed']);self.assertEqual(self.git('rev-parse','HEAD'),self.before)
        self.assertFalse((self.db.parent/'backups').exists())

    def test_plan_hides_process_inspection_details_from_user(self):
        with patch.object(updater,'managed_daemon_status',side_effect=updater.ProcessInspectionError('AccessDenied / private traceback')):
            report=updater.plan(self.root)
        self.assertEqual(report['managed_daemon']['status'],'verification_failed')
        self.assertNotIn('AccessDenied',report['managed_daemon']['message'])

    def test_plan_reports_database_state_separately_from_git_update(self):
        with patch('core.schema_status.inspect_database',return_value={
            'status':'schema_drift','missing_objects':['required_table']
        }) as inspect:
            report=updater.plan(self.root,database=self.db)
        self.assertTrue(report['changed'])
        self.assertEqual(report['database']['status'],'schema_drift')
        self.assertEqual(report['database']['target_update_id'],self.target)
        self.assertTrue(report['database']['lifecycle_required'])
        inspect.assert_called_once_with(self.db,expected_update_id=self.before)
        self.assertEqual(self.git('rev-parse','HEAD'),self.before)
        self.assertFalse((self.db.parent/'backups').exists())

    def test_cli_plan_output_is_english_and_aware_of_no_update(self):
        for changed,expected in (
            (False, 'Preview only: no changes were made.'),
            (True, 'Preview only: no changes were made.'),
        ):
            with self.subTest(changed=changed):
                report=dict(status='planned',root=str(self.root),branch='current',channel='dev',
                            source='origin/current',before=self.before,
                            target=self.target if changed else self.before,changed=changed,
                            database={'status':'ready'})
                output=io.StringIO()
                with (
                    patch.object(updater,'installed_root',return_value=self.root),
                    patch.object(updater,'plan',return_value=report),
                    redirect_stdout(output),
                ):
                    self.assertEqual(updater.main(['--dry-run']),0)
                payload=json.loads(output.getvalue())
                self.assertIn(expected,payload['next'])
                self.assertNotIn('Detén',payload['next'])

    def test_cli_no_code_update_still_reports_unprepared_database(self):
        report=dict(status='planned',root=str(self.root),branch='current',channel='dev',
                    source='origin/current',before=self.before,target=self.before,changed=False,
                    database={'status':'schema_drift','missing_objects':['required_table']})
        output=io.StringIO()
        with (
            patch.object(updater,'installed_root',return_value=self.root),
            patch.object(updater,'plan',return_value=report),
            redirect_stdout(output),
        ):
            self.assertEqual(updater.main(['--dry-run','--db',str(self.db)]),0)
        payload=json.loads(output.getvalue())
        self.assertFalse(payload['changed'])
        self.assertEqual(payload['database']['status'],'schema_drift')
        self.assertIn('Preview only',payload['next'])

    def test_cli_applies_by_default_and_dry_run_is_opt_in_preview(self):
        output=io.StringIO()
        with (
            patch.object(updater,'installed_root',return_value=self.root),
            patch.object(updater,'apply',return_value={'status':'ok'}) as apply,
            redirect_stdout(output),
        ):
            self.assertEqual(updater.main([]),0)
        apply.assert_called_once()
        self.assertEqual(json.loads(output.getvalue())['status'],'ok')
        output=io.StringIO()
        with (
            patch.object(updater,'installed_root',return_value=self.root),
            patch.object(updater,'plan',return_value={'status':'planned'}) as plan,
            patch.object(updater,'apply') as apply,
            redirect_stdout(output),
        ):
            self.assertEqual(updater.main(['--dry-run']),0)
        plan.assert_called_once();apply.assert_not_called()
        self.assertIn('Preview only',json.loads(output.getvalue())['next'])

    def test_cli_local_changes_error_is_english_json(self):
        (self.root/'uncommitted.txt').write_text('keep me')
        output=io.StringIO()
        with patch.object(updater,'installed_root',return_value=self.root), redirect_stderr(output):
            self.assertEqual(updater.main(['--dry-run']),1)
        payload=json.loads(output.getvalue())
        self.assertEqual(payload['status'],'error')
        self.assertIn('local changes',payload['message'])
        self.assertIn('left untouched',payload['message'])

    def test_update_runs_new_processes_preserves_branch_and_backup(self):
        calls=[]
        def runner(args,**kwargs):
            calls.append((args,kwargs))
            return SimpleNamespace(stdout=json.dumps({'status':'ok','steps':[],
                                                      'update_id':self.target,
                                                      'database_status':{'status':'ready',
                                                                         'applied_update_id':self.target,
                                                                         'expected_update_id':self.target}}))
        report=updater.apply(self.root,database=self.db,runner=runner)
        self.assertEqual(report['status'],'ok');self.assertEqual(self.git('rev-parse','HEAD'),self.target)
        from core.update_barrier import runtime_status
        self.assertTrue(runtime_status(self.db)['allowed'])
        self.assertEqual(self.git('branch','--show-current'),'current')
        self.assertEqual(calls[0][0][1:],['-m','pip','install','.'])
        self.assertEqual(calls[1][0][1:3],['-m','core.lifecycle'])
        self.assertEqual(calls[1][0][calls[1][0].index('--update-id')+1],self.target)
        self.assertTrue(all(kwargs['check'] for _,kwargs in calls))
        self.assertFalse(Path(report['backup']).exists())
        self.assertEqual(report['backup_cleanup'],'removed_after_verified_success')
        with sqlite3.connect(self.db) as db:
            self.assertEqual(db.execute('SELECT value FROM memories').fetchone()[0],'preserve')
        self.assertEqual(json.loads(Path(report['receipt']).read_text())['phase'],'complete')
        report=updater.apply(self.root,database=self.db,runner=runner)
        self.assertEqual(report['status'],'ok');self.assertEqual(len(calls),4)

    def test_daemon_restart_waits_for_verified_pid_file_and_identity(self):
        stopped={'stopped':[{'kind':'daemon','pid':1234}]}
        with patch('core.daemon_lifecycle.spawn_daemon_detached',return_value=True) as spawn, \
             patch.object(updater,'managed_daemon_status',return_value={'status':'running','pid':5678}):
            result=updater.restart_stopped_daemon(stopped,self.root)
        spawn.assert_called_once_with()
        self.assertTrue(result['startup_verified'])
        with patch('core.daemon_lifecycle.spawn_daemon_detached',return_value=True), \
             patch.object(updater,'managed_daemon_status',return_value={'status':'not_running'}):
            with self.assertRaisesRegex(updater.UpdateError,'DAEMON_RESTART_UNVERIFIED'):
                updater.restart_stopped_daemon(stopped,self.root)

    def test_mcp_restart_is_explicitly_handed_to_host_for_health_check(self):
        def runner(args, **kwargs):
            if args[1:3] == ['-m', 'pip']:
                return None
            return SimpleNamespace(stdout=json.dumps({
                'status':'ok', 'steps':[], 'update_id':self.target,
                'database_status':{'status':'ready',
                                   'applied_update_id':self.target,
                                   'expected_update_id':self.target},
            }))
        report = updater.apply(self.root, database=self.db, runner=runner)
        self.assertEqual(report['mcp_restart']['status'], 'host_restart_recommended')
        self.assertFalse(report['process_stop']['stopped'])

    def test_lifecycle_executes_the_new_revision_in_a_real_child(self):
        self.git('update-ref','refs/heads/current',self.target)
        fixture = "from pathlib import Path\nimport sys\nuid=sys.argv[sys.argv.index('--update-id')+1]\nPath(sys.argv[sys.argv.index('--db')+1]).parent.joinpath('new-callback-ran').write_text('new revision')\nimport json\nprint(json.dumps({'status':'ok','steps':[],'update_id':uid,'database_status':{'status':'ready','applied_update_id':uid,'expected_update_id':uid}}))\n"
        (self.root/'core/lifecycle.py').write_text(fixture)
        self.git('add','core/lifecycle.py');self.git('commit','-m','new callback')
        new_target=self.git('rev-parse','HEAD')
        self.git('update-ref','refs/heads/current',self.before)
        self.git('read-tree',self.before)
        (self.root/'core/lifecycle.py').write_text('# synthetic\n')
        def runner(args,**kwargs):
            if args[1:3]==['-m','pip']:return None
            return subprocess.run(args,**kwargs)
        with patch.object(updater,'resolve_target',return_value=(new_target,'origin/current')):
            report=updater.apply(self.root,database=self.db,runner=runner)
        self.assertEqual(report['status'],'ok')
        self.assertEqual((self.db.parent/'new-callback-ran').read_text(),'new revision')

    def test_local_changes_refuse_without_stash_or_reset(self):
        (self.root/'local.txt').write_text('user data')
        with self.assertRaisesRegex(updater.UpdateError,'LOCAL_CHANGES') as caught:updater.plan(self.root)
        self.assertIn('Preserve or commit your local changes',str(caught.exception))
        self.assertNotIn('conserva',str(caught.exception))
        self.assertEqual((self.root/'local.txt').read_text(),'user data')
        self.assertEqual(self.git('rev-parse','HEAD'),self.before)

    def test_failed_dependencies_roll_back_code_database_and_keep_backup(self):
        pip_calls=0
        def fail_first_pip(args,**kwargs):
            nonlocal pip_calls
            if args[1:3]==['-m','pip']:
                pip_calls+=1
                if pip_calls==1:raise subprocess.CalledProcessError(1,'pip')
                return None
            raise AssertionError('Lifecycle must not run after dependency failure')
        report=updater.apply(self.root,database=self.db,runner=fail_first_pip)
        self.assertEqual(report['status'],'rolled_back');self.assertEqual(report['phase'],'rollback_complete')
        self.assertTrue(Path(report['backup']).exists())
        from core.update_barrier import runtime_status
        self.assertTrue(runtime_status(self.db)['allowed'])
        self.assertEqual(self.git('rev-parse','HEAD'),self.before)

    def test_dependency_inventory_mismatch_prevents_false_rollback_success(self):
        def fail_lifecycle(args,**kwargs):
            if args[1:3]==['-m','pip']:return None
            raise subprocess.CalledProcessError(1,args,output='failed')
        with patch.object(updater,'dependency_inventory',side_effect=[{'old-package':'1'}, {'new-package':'2'}]):
            with self.assertRaisesRegex(updater.UpdateError,'UPDATE_RECOVERY_REQUIRED'):
                updater.apply(self.root,database=self.db,runner=fail_lifecycle)
        report=json.loads(next((self.db.parent/'update-receipts').glob('*.json')).read_text())
        self.assertEqual(report['status'],'recovery_required')
        self.assertEqual(report['safety_barrier'],'active')
        self.assertTrue(Path(report['backup']).exists())
        from core.update_barrier import runtime_status
        self.assertEqual(runtime_status(self.db)['status'],'update_incomplete')

    def test_zero_exit_without_valid_lifecycle_report_is_not_success(self):
        for output in ('', '{"status":"failed"}'):
            with self.subTest(output=output):
                def runner(*args,**kwargs):return SimpleNamespace(stdout=output)
                report=updater.apply(self.root,database=self.db,runner=runner)
                self.assertEqual(report['status'],'rolled_back')
                self.assertTrue(Path(report['backup']).exists())

    def test_failed_component_report_is_saved_in_receipt(self):
        detail={'status':'failed','failed_step':'files','completed':[{'step':'database-schema'}]}
        def runner(args,**kwargs):
            if args[1:3]==['-m','pip']:return None
            raise subprocess.CalledProcessError(1,args,output=json.dumps(detail))
        result=updater.apply(self.root,database=self.db,runner=runner)
        report=json.loads(next((self.db.parent/'update-receipts').glob('*.json')).read_text())
        self.assertEqual(result['status'],'rolled_back')
        self.assertEqual(report['lifecycle']['failed_step'],'files')
        self.assertEqual(report['phase'],'rollback_complete')

    def test_failure_after_database_commit_restores_database_automatically(self):
        from core.recovery import stage
        def runner(args,**kwargs):
            if args[1:3]==['-m','pip']:return None
            with sqlite3.connect(self.db) as db:
                db.execute("INSERT INTO memories VALUES ('after-backup')")
            raise subprocess.CalledProcessError(1,args,output=json.dumps({'status':'failed','failed_step':'after-commit'}))
        result=updater.apply(self.root,database=self.db,runner=runner)
        receipt=next((self.db.parent/'update-receipts').glob('*.json'))
        report=json.loads(receipt.read_text())
        self.assertEqual(result['status'],'rolled_back')
        self.assertEqual(report['status'],'rolled_back')
        with sqlite3.connect(self.db) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM memories').fetchone()[0],1)
        restored=stage(receipt)
        with sqlite3.connect(restored['restored_snapshot']) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM memories').fetchone()[0],1)

    def test_existing_empty_database_cannot_skip_required_backup(self):
        self.db.write_bytes(b'')
        report=updater.apply(self.root,database=self.db,runner=lambda *a,**k:None)
        self.assertEqual(report['status'],'rolled_back')
        self.assertEqual(self.git('rev-parse','HEAD'),self.before)
        self.assertEqual(self.db.read_bytes(),b'')
        self.assertIsNone(report['backup'])

    def test_backup_failure_never_advances_code_and_clears_barrier(self):
        with patch.object(updater,'backup_database',side_effect=OSError('disk full')):
            report=updater.apply(self.root,database=self.db)
        self.assertEqual(report['status'],'rolled_back')
        self.assertEqual(self.git('rev-parse','HEAD'),self.before)
        receipt=json.loads(next((self.db.parent/'update-receipts').glob('*.json')).read_text())
        self.assertEqual(receipt['phase'],'rollback_complete')
        from core.update_barrier import runtime_status
        self.assertTrue(runtime_status(self.db)['allowed'])

    def test_existing_recovery_barrier_is_not_overwritten_or_services_stopped(self):
        from core.update_barrier import activate, barrier_path
        marker=activate(self.db,update_id='c'*40,phase='recovery')
        with patch.object(updater,'stop_managed_daemon') as stop:
            with self.assertRaisesRegex(updater.UpdateError,'UPDATE_BARRIER_ACTIVE'):
                updater.apply(self.root,database=self.db)
        stop.assert_not_called()
        self.assertEqual(json.loads(marker.read_text())['phase'],'recovery')
        self.assertEqual(self.git('rev-parse','HEAD'),self.before)

    def test_lock_prevents_concurrent_updater(self):
        _,gitdir=updater.preflight(self.root)
        with updater.update_lock(gitdir):
            with self.assertRaisesRegex(updater.UpdateError,'UPDATE_LOCKED'):
                updater.apply(self.root,database=self.db)
        self.assertTrue((gitdir/'biorag-update.lock').exists())

    def test_lock_mutual_exclusion_three_processes(self):
        """Prueba de tres procesos: A mantiene lock; B rechazado; B NO borra inodo; C rechazado."""
        _, gitdir = updater.preflight(self.root)
        code = f"""import os, time, sys
from pathlib import Path
from core import updater
gitdir = Path({repr(str(gitdir))})
with updater.update_lock(gitdir):
    sys.stdout.write("A_ACQUIRED\\n")
    sys.stdout.flush()
    time.sleep(30)
"""
        proc_a = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)
        try:
            line = proc_a.stdout.readline()
            self.assertEqual(line.strip(), "A_ACQUIRED")

            # Proceso B intenta adquirir y debe ser rechazado
            with self.assertRaisesRegex(updater.UpdateError, "UPDATE_LOCKED"):
                with updater.update_lock(gitdir):
                    pass

            # El archivo de lock debe seguir existiendo (inodo preservado)
            self.assertTrue((gitdir / 'biorag-update.lock').exists())

            # Proceso C intenta adquirir mientras A sigue vivo y DEBE ser rechazado también
            with self.assertRaisesRegex(updater.UpdateError, "UPDATE_LOCKED"):
                with updater.update_lock(gitdir):
                    pass

            # Ahora matamos abruptamente a A (SIGKILL)
            proc_a.kill()
            proc_a.wait()

            # Ahora un nuevo proceso debe adquirir el lock con éxito sin borrar el archivo
            with updater.update_lock(gitdir):
                self.assertTrue((gitdir / 'biorag-update.lock').exists())
        finally:
            if proc_a.poll() is None:
                proc_a.kill()
                proc_a.wait()

    def test_simultaneous_attempts_exactly_one_wins(self):
        """Dos intentos concurrentes: exactamente uno adquiere el lock y el otro es rechazado."""
        _, gitdir = updater.preflight(self.root)
        code = f"""import sys, time
from pathlib import Path
from core import updater
gitdir = Path({repr(str(gitdir))})
try:
    with updater.update_lock(gitdir):
        sys.stdout.write("WON\\n")
        sys.stdout.flush()
        time.sleep(1)
except updater.UpdateError:
    sys.stdout.write("LOCKED\\n")
    sys.stdout.flush()
"""
        p1 = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)
        p2 = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)
        out1, _ = p1.communicate(timeout=5)
        out2, _ = p2.communicate(timeout=5)
        results = sorted([out1.strip(), out2.strip()])
        self.assertEqual(results, ["LOCKED", "WON"])

    def test_lock_released_on_process_crash(self):
        _, gitdir = updater.preflight(self.root)
        code = f"""import os, time, sys
from pathlib import Path
from core import updater
gitdir = Path({repr(str(gitdir))})
with updater.update_lock(gitdir):
    sys.stdout.write("ACQUIRED\\n")
    sys.stdout.flush()
    time.sleep(30)
"""
        proc = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)
        try:
            line = proc.stdout.readline()
            self.assertEqual(line.strip(), "ACQUIRED")
            # Con el subproceso vivo, otro proceso debe fallar con UPDATE_LOCKED
            with self.assertRaisesRegex(updater.UpdateError, "UPDATE_LOCKED"):
                with updater.update_lock(gitdir):
                    pass
            # Simulamos caída abrupta / crash (SIGKILL o terminate en Windows)
            proc.kill()
            proc.wait()
            # El lock debe ser adquirido inmediatamente sin requerir borrar el archivo a mano
            with updater.update_lock(gitdir):
                pass
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()

    def test_downgrade_is_refused(self):
        self.git('update-ref','refs/heads/current',self.target)
        with patch.object(updater,'resolve_target',return_value=(self.before,'old')):
            with self.assertRaisesRegex(updater.UpdateError,'NON_FAST_FORWARD'):updater.plan(self.root)

    def test_target_without_contract_is_refused(self):
        with patch.object(updater,'git',wraps=updater.git) as command:
            def wrapper(root,*args):
                if args[:2]==('cat-file','-e'):raise subprocess.CalledProcessError(1,'cat-file')
                return subprocess.run(['git','-C',str(root),*args],check=True,capture_output=True,text=True).stdout.strip()
            command.side_effect=wrapper
            with self.assertRaisesRegex(updater.UpdateError,'TARGET_LACKS_LIFECYCLE'):updater.plan(self.root)

    def test_non_git_install_has_actionable_refusal(self):
        other=self.home/'package';other.mkdir()
        with self.assertRaisesRegex(updater.UpdateError,'INSTALL_METHOD_UNSUPPORTED'):updater.plan(other)


class UpdateSurfaceTests(unittest.TestCase):
    def test_installed_cli_routes_update_before_loading_memory(self):
        from core import cli
        with patch('sys.argv',['biorag','update','--channel','dev']),patch.object(updater,'main',return_value=0) as run:
            self.assertEqual(cli.main(),0)
            run.assert_called_once_with(['--channel','dev'])

    def test_mcp_only_plans_and_requires_local_transport(self):
        from core.mcp_server.maintenance import register
        class FakeMCP:
            def __init__(self):self.tools={}
            def tool(self):
                def decorate(fn):self.tools[fn.__name__]=fn;return fn
                return decorate
        for stdio in (False,True):
            mcp=FakeMCP();register(mcp,stdio=stdio)
            with patch.object(updater,'plan',return_value={'status':'planned'}) as plan:
                result=mcp.tools['planificar_actualizacion_sistema']('dev')
                if not stdio:
                    self.assertEqual(result['code'],'LOCAL_STDIO_REQUIRED');plan.assert_not_called()
                else:
                    self.assertTrue(result['requires_user_authorization'])
                    self.assertTrue(result['requires_separate_process'])
                    self.assertNotIn('--yes',result['apply_command'])

    def test_stable_requires_approved_tag_and_uses_official_source(self):
        from core.mcp_server import update_checker
        with patch.object(update_checker.UpdateChecker,'check_once',return_value={'estado':'actualizacion_disponible','version_remota':'v36.2'}),patch.object(updater,'git',return_value='a'*40) as git:
            target,source=updater.resolve_target(Path('/synthetic'),'stable')
            self.assertEqual(target,'a'*40);self.assertEqual(source,'v36.2')
            self.assertTrue(any('https://github.com/dennysjmarquez/MemoryBioRAG.git' in call.args[1:]
                                for call in git.call_args_list))


if __name__=='__main__':unittest.main()
