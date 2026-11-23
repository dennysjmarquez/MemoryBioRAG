"""Ayuda y errores de uso no deben importar motor, abrir DB ni consultar red."""
import ast
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from core.cli import COMMANDS, GROUPS

ROOT = Path(__file__).resolve().parents[1]


class CLIHelpTests(unittest.TestCase):
    def run_cli(self, args, entry='script'):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / 'must-not-exist.db'
            # Guardia en proceso nuevo: detecta imports del motor y conexiones/red,
            # no solo ausencia del archivo final.
            program = '''import sys,runpy,socket,sqlite3,importlib.abc
class Guard(importlib.abc.MetaPathFinder):
 def find_spec(self, fullname, path=None, target=None):
  if fullname in ('core.memory_store','nltk','numpy'):
   raise AssertionError('Import de motor durante ayuda: '+fullname)
sys.meta_path.insert(0,Guard())
def forbidden(*a,**k):raise AssertionError('Ayuda abrió DB o red')
sqlite3.connect=forbidden
socket.create_connection=forbidden
'''
            if entry == 'script':
                program += 'sys.argv='+repr(['biorag.py', *args])+'\nrunpy.run_path("biorag.py",run_name="__main__")\n'
            else:
                program += 'sys.argv='+repr(['biorag', *args])+'\nfrom core.cli import main\nraise SystemExit(main())\n'
            env = dict(os.environ, HOME=folder, BIORAG_PATH=str(db),
                       BIORAG_UPDATE_CHECK='0', BIORAG_DAEMON_ENABLED='0')
            result = subprocess.run([sys.executable, '-c', program], cwd=ROOT,
                                    env=env, capture_output=True, text=True, timeout=15)
            self.assertFalse(db.exists())
            self.assertFalse(Path(str(db)+'.maintenance.lock').exists())
            return result

    def test_overview_both_entry_points_and_aliases(self):
        for entry in ('script', 'installed'):
            for args in ([], ['help'], ['--help'], ['-h']):
                with self.subTest(entry=entry, args=args):
                    result=self.run_cli(args,entry)
                    self.assertEqual(result.returncode,0,result.stderr)
                    for word in ('update','recovery','--dry-run','--stage','Read and search memory'):
                        self.assertIn(word,result.stdout)
                    self.assertIn('Quick start', result.stdout)
                    steps = ('biorag guardar service_note', 'biorag sueno', 'biorag buscar service_note')
                    positions = [result.stdout.index(step, result.stdout.index('Quick start')) for step in steps]
                    self.assertEqual(positions, sorted(positions))
                    self.assertIn('\nUpdates and recovery:\n', result.stdout)
                    self.assertIn('\n\nOptions:\n', result.stdout)

    def test_each_memory_command_and_alias_has_safe_help(self):
        for command in sorted(COMMANDS-{'update','recovery','correcciones'}):
            with self.subTest(command=command):
                result=self.run_cli([command,'--help'])
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertIn('biorag ',result.stdout)
                self.assertNotIn('Consulta el manual',result.stdout)

    def test_maintenance_help_uses_real_parsers(self):
        for command,option in (('update','--channel'),('recovery','--receipt'),('correcciones','registrar')):
            for entry in ('script','installed'):
                for args in ([command,'--help'],['help',command]):
                    result=self.run_cli(args,entry)
                    self.assertEqual(result.returncode,0,result.stderr)
                    self.assertIn(option,result.stdout)
                    if command == 'update':
                        self.assertIn('Updater messages are in English',result.stdout)
                        self.assertNotIn('Runtime messages retain their existing language',result.stdout)

    def test_each_command_explains_its_purpose_without_side_effects(self):
        from core.cli import ALIASES
        from core.cli_notes import NOTES, EXAMPLES
        self.assertEqual(set(NOTES), set(EXAMPLES))
        self.assertTrue(all(EXAMPLES.values()))
        canonical = COMMANDS-set(ALIASES)
        self.assertEqual(set(NOTES), canonical | {
            'correcciones registrar', 'correcciones revisar', 'correcciones confirmar'})
        requests = [[name, '--help'] for name in sorted(COMMANDS)]
        requests += [['correcciones', name, '--help']
                     for name in ('registrar', 'revisar', 'confirmar')]
        for entry in ('script', 'installed'):
            for args in requests:
                with self.subTest(entry=entry, args=args):
                    result = self.run_cli(args, entry)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn('What is it for?', ' '.join(result.stdout.split()))
                    headings = ('usage:', 'summary:', 'what is it for?', 'options:',
                                'examples:', 'expected output:', 'see also:')
                    positions = [result.stdout.lower().find(h) for h in headings]
                    self.assertTrue(all(p >= 0 for p in positions), result.stdout)
                    self.assertEqual(positions, sorted(positions))
                    from scripts.audit_cli_help import language_hits
                    import tomllib
                    markers = tomllib.loads((ROOT/'release_manifest.toml').read_text())['language']['spanish_markers']
                    self.assertEqual(language_hits(result.stdout, markers), [])
                    self.assertTrue(language_hits('No se pudo cargar archivo de configuración', markers))
                    self.assertIn('Examples:', result.stdout)
                    self.assertIn('biorag ', result.stdout)
                    if args[0] in ('buscar', 'guardar', 'sueno'):
                        options = result.stdout.split('Options:\n', 1)[1].split('\n\nExamples:', 1)[0]
                        self.assertTrue(all(not line or line.startswith('  ') for line in options.splitlines()))
                        self.assertIn('  - `corteza`', result.stdout)
                        self.assertIn('  - `sueno`', result.stdout)
                        self.assertIn('  - `sustantivos clave`', result.stdout)
                    if args[0] == 'buscar':
                        topic_line = next(line for line in options.splitlines() if 'Topic keywords' in line)
                        tokens_line = next(line for line in options.splitlines() if 'Search stemmed' in line)
                        self.assertEqual(topic_line.index('Topic keywords'), tokens_line.index('Search stemmed'))
                    if args[0] == 'guardar':
                        self.assertIn('Unicode letters', result.stdout)
                        required_line = next(line for line in options.splitlines() if 'Required: 1–5 keywords' in line)
                        alias_line = next(line for line in options.splitlines() if 'Alias of --sustantivos-clave' in line)
                        self.assertEqual(required_line.index('Required: 1–5 keywords'), alias_line.index('Alias of --sustantivos-clave'))
                    if args[0] == 'dashboard':
                        self.assertTrue(result.stdout.split('Examples:\n')[1].startswith('  biorag dashboard --help'))
                    if args[0] == 'comunicar':
                        self.assertIn('Options:\n  No additional options.', result.stdout)

    def test_corrections_help_distinguishes_editing_from_contextual_replacement(self):
        for entry in ('script', 'installed'):
            result = self.run_cli(['correcciones', '--help'], entry)
            self.assertEqual(result.returncode, 0, result.stderr)
            text = ' '.join(result.stdout.split())
            for phrase in ('How is this different from updating a node?', 'Updating a node changes its text',
                           'does not delete or rewrite', '8080', '8443',
                           'Both memories must already exist', 'MCP recordar/buscar',
                           'or guarantee'):
                self.assertIn(phrase, text)

    def test_unknown_command_fails_without_engine(self):
        for args in (['does-not-exist'],['help','does-not-exist'],['help','update','extra']):
            result=self.run_cli(args)
            self.assertEqual(result.returncode,2,result.stderr)
            self.assertIn('help',result.stderr)

    def test_catalog_matches_memory_dispatch(self):
        tree=ast.parse((ROOT/'biorag.py').read_text())
        main=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='main')
        commands=next(node.value for node in main.body if isinstance(node,ast.Assign)
                      and any(isinstance(target,ast.Name) and target.id=='comandos' for target in node.targets))
        self.assertEqual({key.value for key in commands.keys}, COMMANDS-{'update','recovery','correcciones'})
        listed=[name for _,entries in GROUPS for name,_ in entries]
        self.assertEqual(len(listed),len(set(listed)))


if __name__=='__main__':unittest.main()
