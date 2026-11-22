"""Contrato único post-install/post-update: python -m core.lifecycle.

Cada componente registra pasos idempotentes y verificables en STEPS. No descarga
código ni activa servicios por sorpresa. El primer fallo impide anunciar éxito.
"""
from __future__ import annotations
import argparse
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Callable

from core.migrate import migrate


@dataclass(frozen=True)
class Step:
    name: str
    run: Callable
    destructive: bool = False


@dataclass(frozen=True)
class PreparationContext:
    database: Path
    install_root: Path
    allow_service_start: bool = False
    pre_update_backup: str | None = None


def _database_schema(context):
    return migrate(context.database, existing_backup=context.pre_update_backup)


STEPS = (Step('database-schema', _database_schema),)


class PreparationError(RuntimeError):
    def __init__(self, step, completed, cause):
        self.step = step
        self.completed = list(completed)
        super().__init__('LIFECYCLE_VERIFICATION_FAILED: '+step+': '+str(cause))


def prepare(database, *, steps=None, pre_update_backup=None):
    steps = STEPS if steps is None else tuple(steps)
    names = [step.name for step in steps]
    if len(set(names)) != len(names):
        raise ValueError('DUPLICATE_LIFECYCLE_STEP')
    context = PreparationContext(Path(database).expanduser().resolve(), Path(__file__).resolve().parents[1], pre_update_backup=pre_update_backup)
    report = []
    for step in steps:
        try:
            if step.destructive:
                raise ValueError('DESTRUCTIVE_PREPARATION_UNSUPPORTED: requiere control exclusivo completo y recuperación validada')
            result = step.run(context)
            if not isinstance(result, dict) or result.get('status') != 'ok':
                raise ValueError('el componente no confirmó su preparación')
        except Exception as exc:
            raise PreparationError(step.name, report, exc) from exc
        report.append(dict(step=step.name, result=result))
    return dict(status='ok', steps=report, restart_required=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db')
    parser.add_argument('--pre-update-backup', help='Uso interno: respaldo pre-update validado de esta DB')
    args = parser.parse_args()
    from core.paths import resolve_db_path
    try:
        result = prepare(args.db or resolve_db_path(), pre_update_backup=args.pre_update_backup)
    except PreparationError as exc:
        print(json.dumps(dict(status='failed', failed_step=exc.step, completed=exc.completed, error=str(exc)), ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
