"""Entrada CLI ligera: ayuda y mantenimiento sin importar el motor ni abrir DB."""
import ast
from pathlib import Path
from textwrap import dedent, indent
import sys

# Nombres públicos y aliases del despachador de memoria en biorag.py.
GROUPS = (
    ('Read and search memory', (
        ('buscar', 'Retrieve memories; see buscar --help'),
        ('listar', 'Browse concepts page by page'),
        ('corteza', 'Inspect permanent nodes'),
        ('estado', 'Show memory statistics'),
        ('familiaridad', 'Recognize concepts in text'),
        ('sustantivos', 'Inspect a node\'s topic keywords'),
    )),
    ('Write and organize memory', (
        ('guardar', 'Save a memory with topic keywords'),
        ('correcciones', 'Propose, review and approve fact replacements'),
        ('agregar_sustantivos', 'Assign or update topic keywords'),
        ('asociar', 'Associate two concepts'),
        ('sueno', 'Consolidate memory; changes data'),
    )),
    ('Communication and interfaces', (
        ('comunicar', 'Leave a shared message'),
        ('leer_mensajes', 'Read shared messages'),
        ('dashboard', 'Start the local interface, if installed'),
    )),
    ('Update and recover the system', (
        ('update', 'Plan an update; --yes authorizes applying it'),
        ('recovery', 'Plan recovery; --stage creates separate copies'),
    )),
)
ALIASES = {'sustantivo': 'sustantivos', 'agregar-sustantivos': 'agregar_sustantivos',
           'asignar_sustantivos': 'agregar_sustantivos', 'asignar-sustantivos': 'agregar_sustantivos'}
COMMANDS = {name for _, entries in GROUPS for name, _ in entries} | set(ALIASES)
HELP_FLAGS = ('--help', '-h')


def can_handle_early(argv):
    """No consumir argumentos de memoria salvo petición de ayuda explícita."""
    return (not argv or argv[0] in ('help', *HELP_FLAGS, 'update', 'recovery', 'correcciones')
            or argv[0] not in COMMANDS or any(flag in argv[1:] for flag in HELP_FLAGS))


def _overview():
    print('BioRAG — local memory for agents\n')
    print('usage: biorag <command> [options]')
    print('       python3 biorag.py <command> [options]\n')
    print('Summary:\nLocal memory tools for agents.\n')
    print('What is it for?\nStore, retrieve and maintain memory shared by your local agents.\n')
    for group, entries in GROUPS:
        print(group + ':')
        for name, description in entries:
            print(f'  {name:22} {description}')
        print()
    print('Help: biorag help <command>  |  biorag <command> --help')
    print('You can replace `biorag` with `python3 biorag.py` in the examples.\n')
    print('Key concepts:')
    print('  Working memory: guardar stores new memories here; run sueno before buscar.')
    print('  `corteza` (cortex: permanent memory): consolidated memories used by buscar/listar.')
    print('  `sueno` (sleep: consolidation): moves working memories into permanent storage.')
    print('  `sustantivos clave` (key nouns: the core topic of a memory).')
    print('  Dormant node: an inactive memory; buscar --deep can wake a retrieved node.\n')
    print('Before you start:\nDatabase: BIORAG_PATH selects your database; use a disposable copy for testing.')
    print('  Example: BIORAG_PATH=/path/copy.db biorag estado')
    print('  Commands may initialize or prepare schema when opening a database; help does not.\n')
    print('Updates and recovery:\nBefore applying update, stop the MCP server (agent-to-memory tools process)')
    print('and the daemon (background maintenance process). Use the same Python environment.')
    print('Update requires a clean Git checkout (no local changes) and an external database')
    print('(outside the checkout). Planning may access the network.')
    print('Recovery --stage never overwrites live memory or rolls back Git/pip.')
    print('The six `contexto_vigencia` modes belong to MCP `recordar`/`buscar`, not CLI `buscar`.')
    print('\nOptions:\n  -h, --help  Show help without opening a database.\n')
    print('Examples:')
    print('  Quick start (writes to your selected database; choose a disposable copy first):')
    print('  biorag guardar service_note \"The test service uses port 8443\" --sustantivos-clave \"service,port\"')
    print('  biorag sueno')
    print('  biorag buscar service_note')
    print('\n  More help:')
    print('  biorag guardar --help')
    print('  biorag buscar --help')
    print('  biorag update --dry-run')
    print('  biorag recovery --help')
    print('\nExpected output:\nCommand-specific text or JSON; runtime messages may remain Spanish.')
    print('\nSee also:\n  biorag guardar --help\n  biorag buscar --help\n  biorag sueno --help\n  biorag listar --help')


def _memory_help(command):
    """Reutilizar el detalle existente sin importar biorag y sus dependencias."""
    source = Path(__file__).resolve().parents[1] / 'biorag.py'
    documentation = ast.get_docstring(ast.parse(source.read_text(encoding='utf-8'))) or ''
    marker = '  python3 biorag.py ' + command
    lines = documentation.splitlines()
    for index, line in enumerate(lines):
        if line == marker or line.startswith(marker + ' '):
            end = index + 1
            while end < len(lines) and (not lines[end] or lines[end].startswith(' ')):
                if lines[end].startswith('  python3 biorag.py '):
                    break
                end += 1
            from core.cli_notes import help_intro, help_end
            detail = '\n'.join(lines[index:end]).strip().replace('python3 biorag.py', 'biorag')
            usage, _, body = detail.partition('\n')
            summary, _, options = body.partition('Options:')
            print('usage: ' + usage)
            print('\n' + help_intro(command, summary))
            print('\nOptions:\n' + indent(dedent(options).strip(), '  '))
            print('\n' + help_end(command))
            return 0
    # Nunca afirmar que un comando inexistente está implementado.
    print(f'Consulta el manual biorag.py para el comando {command}.')
    return 0


def dispatch_early(argv):
    """Devuelve exit code, o None para delegar un comando de memoria conocido."""
    argv = list(argv)
    if not argv:
        _overview()
        return 0
    command, args = argv[0], argv[1:]
    if command in ('help', *HELP_FLAGS):
        if not args:
            _overview()
            return 0
        if len(args) != 1 or args[0] not in COMMANDS:
            print('Uso: biorag help <comando>. Consulta biorag --help.', file=sys.stderr)
            return 2
        return dispatch_early([args[0], '--help'])
    if command == 'correcciones':
        from core.corrections_cli import main as corrections_main
        return corrections_main(args)
    if command == 'update':
        from core.updater import main as update_main
        return update_main(args)
    if command == 'recovery':
        from core.recovery import main as recovery_main
        return recovery_main(args)
    if command not in COMMANDS:
        print(f'Comando desconocido: {command}. Consulta biorag --help.', file=sys.stderr)
        return 2
    if any(flag in args for flag in HELP_FLAGS):
        return _memory_help(ALIASES.get(command, command))
    return None


def main():
    result = dispatch_early(sys.argv[1:])
    if result is not None:
        return result
    from biorag import main as memory_main
    return memory_main()
