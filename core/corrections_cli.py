"""Correcciones estructuradas locales: mismo servicio y transacciones que MCP."""
import argparse
import json
import os
import sqlite3
import sys
from core.cli_notes import usage_note


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog='biorag correcciones',
        description='Registrar propuestas, revisar evidencia y confirmar sin borrar historia. '
                    + usage_note('correcciones'),
        epilog='Flujo: registrar → revisar → confirmar con el digest revisado. '
               'Fechas en segundos UNIX. BIORAG_CORRECTIONS=0 deshabilita operaciones. '
               'Salida JSON; errores en stderr. No se interpreta el idioma del mensaje.')
    subs = parser.add_subparsers(dest='operation')
    register = subs.add_parser('registrar', help='Crear propuesta; NO aprueba ni sustituye recuerdos',
                               description=usage_note('correcciones registrar'))
    review = subs.add_parser('revisar', help='Mostrar evidencia completa y digest para revisión',
                             description=usage_note('correcciones revisar'))
    confirm = subs.add_parser('confirmar', help='Aprobar explícitamente la evidencia revisada',
                              description=usage_note('correcciones confirmar'))
    for sub in (register, review, confirm):
        sub.add_argument('--db', help='DB existente; por defecto BIORAG_PATH o ruta canónica')
        sub.add_argument('--id', required=True, help='Identificador estable de la propuesta')
    for flag, help_text in (
        ('mensaje', 'Evidencia original, en cualquier idioma'),
        ('nodo-anterior', 'Concepto existente que queda como antecedente'),
        ('nodo-sucesor', 'Concepto existente que lo sustituye'),
        ('entidad', 'Identificador exacto entity del contexto'),
        ('atributo', 'Identificador exacto attribute del contexto'),
        ('ambito', 'Identificador exacto scope del contexto'),
        ('valor-anterior', 'Valor anterior explícito'),
        ('valor-nuevo', 'Valor nuevo explícito'),
    ):
        register.add_argument('--'+flag, required=True, help=help_text)
    register.add_argument('--observado-en', type=float, required=True, help='Instante de observación UNIX')
    register.add_argument('--efectivo-desde', type=float, required=True, help='Inicio de vigencia UNIX')
    register.add_argument('--anterior-desde', type=float, help='Inicio del antecedente; necesario sin ledger previo')
    confirm.add_argument('--digest', required=True, help='Digest obtenido al revisar; no inventarlo')
    confirm.add_argument('--request-id', required=True, help='ID de confirmación; reutilizarlo para reintento idéntico')
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
