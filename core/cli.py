"""Entrada CLI ligera: ayuda y mantenimiento sin importar el motor ni abrir DB."""
import ast
from pathlib import Path
import sys

# Nombres públicos y aliases del despachador de memoria en biorag.py.
GROUPS = (
    ('Consultar memoria', (
        ('buscar', 'Buscar recuerdos; ver opciones con buscar --help'),
        ('listar', 'Listar conceptos con paginación'),
        ('corteza', 'Mostrar nodos de memoria permanente'),
        ('estado', 'Mostrar estadísticas de memoria'),
        ('familiaridad', 'Reconocer conceptos en un texto'),
        ('sustantivos', 'Consultar el núcleo temático de un nodo'),
    )),
    ('Escribir y organizar memoria', (
        ('guardar', 'Guardar un recuerdo con sustantivos clave'),
        ('correcciones', 'Registrar, revisar y confirmar sustituciones explícitas'),
        ('agregar_sustantivos', 'Asignar o actualizar sustantivos clave'),
        ('asociar', 'Vincular dos conceptos'),
        ('sueno', 'Consolidar memoria; modifica datos'),
    )),
    ('Comunicación e interfaces', (
        ('comunicar', 'Enviar un mensaje a otro agente'),
        ('leer_mensajes', 'Consultar mensajes entre agentes'),
        ('dashboard', 'Abrir la interfaz local, si está disponible'),
    )),
    ('Actualizar y recuperar el sistema', (
        ('update', 'Planificar actualización; --yes autoriza aplicarla'),
        ('recovery', 'Planificar recuperación; --stage crea copias separadas'),
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
    print('BioRAG — memoria local para agentes\n')
    print('Uso: biorag <comando> [opciones]')
    print('     python biorag.py <comando> [opciones]\n')
    for group, entries in GROUPS:
        print(group + ':')
        for name, description in entries:
            print(f'  {name:22} {description}')
        print()
    print('Ayuda: biorag help <comando>  |  biorag <comando> --help')
    print('Ejemplos:')
    print('  biorag update --dry-run')
    print('  biorag update --yes --db /ruta/externa/memory_biorag.db')
    print('  biorag recovery --receipt /ruta/recibo.json')
    print('\nSeguridad: detener MCP/daemon antes de aplicar update; usar el mismo Python.')
    print('Update requiere checkout Git limpio y DB externa; el plan puede consultar red.')
    print('Recovery --stage NO sobrescribe la DB actual ni revierte Git/pip.')
    print('Los seis modos de contexto_vigencia pertenecen al MCP recordar/buscar;')
    print('no son opciones del comando buscar de este CLI.')


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
            print('\n'.join(lines[index:end]).strip())
            from core.cli_notes import usage_note, command_examples
            print('\n' + usage_note(command))
            print('\n' + command_examples(command))
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
