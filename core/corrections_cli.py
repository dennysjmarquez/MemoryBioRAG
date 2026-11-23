"""Correcciones estructuradas locales: mismo servicio y transacciones que MCP."""
import argparse
from core.cli_help import HelpParser
import json
import os
import sqlite3
import sys
from core.cli_notes import usage_note, command_examples


def main(argv=None):
    parser = HelpParser(
        prog='biorag correcciones',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description='Propose, review and approve fact replacements without deleting history.\n\n'
                    + usage_note('correcciones'),
        epilog='Workflow: registrar → revisar → confirmar with the reviewed digest.'
               '\nDates use UNIX seconds. BIORAG_CORRECTIONS=0 disables operations.\n'
               'JSON output; errors go to stderr. Message language is not interpreted.\n\n'
               + command_examples('correcciones'))
    subs = parser.add_subparsers(dest='operation')
    register = subs.add_parser('registrar', help='Create a proposal; does NOT approve it or edit memories',
                               description=usage_note('correcciones registrar'))
    review = subs.add_parser('revisar', help='Inspect full evidence and its digest',
                             description=usage_note('correcciones revisar'))
    confirm = subs.add_parser('confirmar', help='Explicitly approve the reviewed relationship',
                              description=usage_note('correcciones confirmar'))
    for sub, name in ((register, 'registrar'), (review, 'revisar'), (confirm, 'confirmar')):
        sub.formatter_class = argparse.RawDescriptionHelpFormatter
        sub.epilog = command_examples('correcciones ' + name)
    for sub in (register, review, confirm):
        sub.add_argument('--db', help='Existing database; defaults to BIORAG_PATH or the canonical path')
        sub.add_argument('--id', required=True, help='Stable proposal identifier')
    for flag, help_text in (
        ('mensaje', 'Original evidence message, in any language'),
        ('nodo-anterior', 'Existing concept containing the earlier fact'),
        ('nodo-sucesor', 'Existing concept containing its replacement'),
        ('entidad', 'Exact context entity identifier'),
        ('atributo', 'Exact context attribute identifier'),
        ('ambito', 'Exact context scope identifier'),
        ('valor-anterior', 'Explicit earlier value'),
        ('valor-nuevo', 'Explicit replacement value'),
    ):
        register.add_argument('--'+flag, required=True, metavar='VALUE', help=help_text)
    register.add_argument('--observado-en', type=float, required=True, metavar='SECONDS', help='Observation time in UNIX seconds')
    register.add_argument('--efectivo-desde', type=float, required=True, metavar='SECONDS', help='Effective start in UNIX seconds')
    register.add_argument('--anterior-desde', type=float, metavar='SECONDS', help='Earlier fact start; required if no prior approved context exists')
    confirm.add_argument('--digest', required=True, help='Digest returned by revisar; do not invent one')
    confirm.add_argument('--request-id', required=True, help='Confirmation request ID; reuse for an identical retry')
    args = parser.parse_args(argv)
    if args.operation is None:
        parser.print_help()
        return 0
    service = None
    try:
        # Antes de importar o abrir servicio: ni DB ni tablas si está deshabilitado.
        if os.environ.get('BIORAG_CORRECTIONS', '1') != '1':
            raise PermissionError('Correcciones deshabilitadas por BIORAG_CORRECTIONS')
        from core.paths import resolve_db_path
        from core.contextual.service import Corrections
        service = Corrections(resolve_db_path(args.db), source_client='local-cli')
        if args.operation == 'registrar':
            result = service.register_structured(
                args.id, args.mensaje, args.nodo_anterior, args.nodo_sucesor,
                args.observado_en, args.efectivo_desde,
                dict(entity=args.entidad, attribute=args.atributo, scope=args.ambito),
                args.valor_anterior, args.valor_nuevo, args.anterior_desde)
        elif args.operation == 'revisar':
            result = service.review(args.id)
        else:
            result = service.confirm(args.id, args.digest, args.request_id)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, sqlite3.Error, RuntimeError) as exc:
        print(json.dumps(dict(status='error', error=type(exc).__name__, message=str(exc)),
                         ensure_ascii=False), file=sys.stderr)
        return 1
    finally:
        if service is not None:
            service.close()


if __name__ == '__main__':
    raise SystemExit(main())
