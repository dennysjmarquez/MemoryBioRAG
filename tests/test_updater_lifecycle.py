"""Actualización en repositorios Git temporales; sin red ni DB viva."""
from contextlib import contextmanager, redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import sqlite3
import subprocess
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

    def tearDown(self):
        self.schema_patch.stop();self.patch.stop();self.tmp.cleanup()

    def git(self,*args):
        return subprocess.run(['git','-C',str(self.root),*args],check=True,capture_output=True,text=True).stdout.strip()

    def test_plan_does_not_change_code_or_data(self):
        report=updater.plan(self.root)
        self.assertTrue(report['changed']);self.assertEqual(self.git('rev-parse','HEAD'),self.before)
        self.assertFalse((self.db.parent/'backups').exists())

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
            (False, 'This checkout already matches its upstream revision.'),
            (True, 'After explicit authorization'),
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
                if not changed:
                    self.assertIn('No code update is available',payload['next'])

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
        self.assertIn('No code update is available',payload['next'])
        self.assertIn('database preparation is not confirmed',payload['next'])
        self.assertIn('--yes',payload['next'])

    def test_cli_local_changes_error_is_english_json(self):
        (self.root/'uncommitted.txt').write_text('keep me')
        output=io.StringIO()
        with patch.object(updater,'installed_root',return_value=self.root), redirect_stderr(output):
            self.assertEqual(updater.main(['--dry-run']),1)
        payload=json.loads(output.getvalue())
        self.assertEqual(payload['status'],'error')
        self.assertIn('Preserve or commit your local changes',payload['message'])
        self.assertNotIn('conserva',payload['message'])

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
        with sqlite3.connect(report['backup']) as backup:
            self.assertEqual(backup.execute('SELECT value FROM memories').fetchone()[0],'preserve')
        self.assertEqual(json.loads(Path(report['receipt']).read_text())['phase'],'complete')
        # Repetir incluso sin nuevos commits vuelve a verificar el lifecycle.
        report=updater.apply(self.root,database=self.db,runner=runner)
        self.assertEqual(report['status'],'ok');self.assertEqual(len(calls),4)

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
        stopped = {'stopped':[{'kind':'mcp','pid':456}], 'restart_required':True}
        with patch.object(updater, 'stop_known_database_processes', return_value=stopped):
            report = updater.apply(self.root, database=self.db, runner=runner)
        self.assertEqual(report['mcp_restart']['status'], 'pending_host_reconnect')
        self.assertEqual(report['mcp_restart']['health_check'],
                         'host_must_reconnect_and_verify_update_id')

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
            if args[1:3]==['-m','pip']:return None  # no instalar paquetes de prueba
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

    def test_failed_dependencies_produce_partial_receipt_not_success(self):
        def fail(*args,**kwargs):raise subprocess.CalledProcessError(1,'pip')
        with self.assertRaisesRegex(updater.UpdateError,'UPDATE_FAILED'):
            updater.apply(self.root,database=self.db,runner=fail)
        report=json.loads(next((self.db.parent/'update-receipts').glob('*.json')).read_text())
        self.assertEqual(report['status'],'recovery_required');self.assertEqual(report['phase'],'dependencies')
        self.assertTrue(Path(report['backup']).exists())
        from core.update_barrier import runtime_status
        self.assertEqual(runtime_status(self.db)['status'], 'update_incomplete')
        # No rollback destructivo del código ya actualizado.
        self.assertEqual(self.git('rev-parse','HEAD'),self.target)

    def test_zero_exit_without_valid_lifecycle_report_is_not_success(self):
        for output in ('', '{"status":"failed"}'):
            with self.subTest(output=output):
                def runner(*args,**kwargs):return SimpleNamespace(stdout=output)
                with self.assertRaisesRegex(updater.UpdateError,'LIFECYCLE_REPORT_'):
                    updater.apply(self.root,database=self.db,runner=runner)

    def test_failed_component_report_is_saved_in_receipt(self):
        detail={'status':'failed','failed_step':'files','completed':[{'step':'database-schema'}]}
        def runner(args,**kwargs):
            if args[1:3]==['-m','pip']:return None
            raise subprocess.CalledProcessError(1,args,output=json.dumps(detail))
        with self.assertRaises(updater.UpdateError):updater.apply(self.root,database=self.db,runner=runner)
        report=json.loads(next((self.db.parent/'update-receipts').glob('*.json')).read_text())
        self.assertEqual(report['lifecycle']['failed_step'],'files')
        self.assertEqual(report['phase'],'lifecycle')

    def test_failure_after_database_commit_preserves_later_memories(self):
        from core.recovery import stage
        def runner(args,**kwargs):
            if args[1:3]==['-m','pip']:return None
            with sqlite3.connect(self.db) as db:
                db.execute("INSERT INTO memories VALUES ('after-backup')")
            raise subprocess.CalledProcessError(1,args,output=json.dumps({'status':'failed','failed_step':'after-commit'}))
        with self.assertRaises(updater.UpdateError):updater.apply(self.root,database=self.db,runner=runner)
        receipt=next((self.db.parent/'update-receipts').glob('*.json'))
        report=json.loads(receipt.read_text())
        self.assertEqual(report['status'],'recovery_required')
        restored=stage(receipt)
        for path in (self.db,restored['current_snapshot']):
            with sqlite3.connect(path) as db:self.assertEqual(db.execute('SELECT count(*) FROM memories').fetchone()[0],2)
        with sqlite3.connect(restored['restored_snapshot']) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM memories').fetchone()[0],1)

    def test_backup_failure_never_advances_code(self):
        with patch.object(updater,'backup_database',side_effect=OSError('disk full')):
            with self.assertRaises(updater.UpdateError):updater.apply(self.root,database=self.db)
        self.assertEqual(self.git('rev-parse','HEAD'),self.before)
        receipt=json.loads(next((self.db.parent/'update-receipts').glob('*.json')).read_text())
        self.assertEqual(receipt['phase'],'backup')
        from core.update_barrier import runtime_status
        self.assertTrue(runtime_status(self.db)['allowed'])

    def test_lock_prevents_concurrent_updater(self):
        _,gitdir=updater.preflight(self.root)
        with updater.update_lock(gitdir):
            with self.assertRaisesRegex(updater.UpdateError,'UPDATE_LOCKED'):
                updater.apply(self.root,database=self.db)
        self.assertFalse((gitdir/'biorag-update.lock').exists())

    def test_downgrade_is_refused(self):
        self.git('update-ref','refs/heads/current',self.target)
        with patch.object(updater,'resolve_target',return_value=(self.before,'old')):
            with self.assertRaisesRegex(updater.UpdateError,'NON_FAST_FORWARD'):updater.plan(self.root)

    def test_target_without_contract_is_refused(self):
        with patch.object(updater,'git',wraps=updater.git) as command:
            real=updater.git
            def wrapper(root,*args):
                if args[:2]==('cat-file','-e'):raise subprocess.CalledProcessError(1,'cat-file')
                # evitar el mock recursivo
                return subprocess.run(['git','-C',str(root),*args],check=True,capture_output=True,text=True).stdout.strip()
            command.side_effect=wrapper
            with self.assertRaisesRegex(updater.UpdateError,'TARGET_LACKS_LIFECYCLE'):updater.plan(self.root)

    def test_non_git_install_has_actionable_refusal(self):
        other=self.home/'package';other.mkdir()
        with self.assertRaisesRegex(updater.UpdateError,'INSTALL_METHOD_UNSUPPORTED'):updater.plan(other)


if __name__=='__main__':unittest.main()


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
                    self.assertEqual(result['apply_command'][-1],'--yes')

    def test_stable_requires_approved_tag_and_uses_official_source(self):
        from core.mcp_server import update_checker
        with patch.object(update_checker.UpdateChecker,'check_once',return_value={'estado':'actualizacion_disponible','version_remota':'v36.2'}),patch.object(updater,'git',return_value='a'*40) as git:
            target,source=updater.resolve_target(Path('/synthetic'),'stable')
            self.assertEqual(source,'v36.2');self.assertEqual(target,'a'*40)
            self.assertIn('https://github.com/dennysjmarquez/MemoryBioRAG.git',git.call_args_list[0].args)
        with patch.object(update_checker.UpdateChecker,'check_once',return_value={'estado':'politica_invalida'}),patch.object(updater,'git') as git:
            with self.assertRaisesRegex(updater.UpdateError,'STABLE_NOT_APPROVED'):updater.resolve_target(Path('/synthetic'),'stable')
            git.assert_not_called()
