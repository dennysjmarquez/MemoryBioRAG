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
                    for word in ('update','recovery','--dry-run','--stage','Consultar memoria'):
                        self.assertIn(word,result.stdout)

    def test_each_memory_command_and_alias_has_safe_help(self):
        for command in sorted(COMMANDS-{'update','recovery','correcciones'}):
            with self.subTest(command=command):
                result=self.run_cli([command,'--help'])
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertIn('biorag.py',result.stdout)
                self.assertNotIn('Consulta el manual',result.stdout)

    def test_maintenance_help_uses_real_parsers(self):
        for command,option in (('update','--channel'),('recovery','--receipt'),('correcciones','registrar')):
            for entry in ('script','installed'):
                for args in ([command,'--help'],['help',command]):
                    result=self.run_cli(args,entry)
                    self.assertEqual(result.returncode,0,result.stderr)
                    self.assertIn(option,result.stdout)

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
                    self.assertIn('¿Para qué me sirve?', ' '.join(result.stdout.split()))
                    self.assertIn('Ejemplos:', result.stdout)
                    self.assertIn('biorag ', result.stdout)

    def test_corrections_help_distinguishes_editing_from_contextual_replacement(self):
        for entry in ('script', 'installed'):
            result = self.run_cli(['correcciones', '--help'], entry)
            self.assertEqual(result.returncode, 0, result.stderr)
            text = ' '.join(result.stdout.split())
            for phrase in ('Diferencia con actualizar un nodo:', 'Actualizar cambia el contenido',
                           'no borra ni reescribe', '8080', '8443',
                           'Ambos recuerdos deben existir', 'búsquedas MCP',
                           'ni garantiza'):
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
