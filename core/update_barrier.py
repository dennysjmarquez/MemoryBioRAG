"""Durable fail-closed gate preventing MCP from serving an unverified update."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import tempfile
from datetime import datetime, timezone


class UpdateBarrierError(RuntimeError):
    pass


_FORMAT = 'biorag.update-barrier.v1'
_PHASES = {'starting', 'backup', 'code', 'dependencies', 'lifecycle'}


def _valid_payload(data):
    return (isinstance(data, dict)
            and data.get('format') == _FORMAT
            and isinstance(data.get('update_id'), str)
            and re.fullmatch(r'[0-9a-fA-F]{40,64}', data['update_id']) is not None
            and data.get('phase') in _PHASES
            and isinstance(data.get('pid'), int)
            and isinstance(data.get('started_at'), str))


def barrier_path(database: str | os.PathLike[str]) -> Path:
    path = Path(database).expanduser().resolve()
    return path.with_name(path.name + '.biorag-update-incomplete.json')


def activate(database: str | os.PathLike[str], *, update_id: str, phase: str = 'starting') -> Path:
    """Atomically create/update the maintenance barrier; a preexisting barrier is preserved on error."""
    if not isinstance(update_id, str) or re.fullmatch(r'[0-9a-fA-F]{40,64}', update_id) is None:
        raise UpdateBarrierError('UPDATE_BARRIER_UPDATE_ID_INVALID')
    if phase not in _PHASES:
        raise UpdateBarrierError('UPDATE_BARRIER_PHASE_INVALID')
    target = barrier_path(database)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink():
        raise UpdateBarrierError('UPDATE_BARRIER_SYMLINK_REFUSED')
    payload = {
        'format': _FORMAT,
        'pid': os.getpid(),
        'update_id': update_id,
        'phase': phase,
        'started_at': datetime.now(timezone.utc).isoformat(),
    }
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=target.parent,
                                     prefix='.biorag-update-', delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(payload, stream, ensure_ascii=False, sort_keys=True)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def clear(database: str | os.PathLike[str]) -> bool:
    """Remove only BioRAG's exact, non-symlink barrier after verified preparation."""
    target = barrier_path(database)
    if target.is_symlink():
        raise UpdateBarrierError('UPDATE_BARRIER_SYMLINK_REFUSED')
    if not target.exists():
        return False
    try:
        data = json.loads(target.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise UpdateBarrierError('UPDATE_BARRIER_INVALID: refusing to remove unreadable barrier') from exc
    if not _valid_payload(data):
        raise UpdateBarrierError('UPDATE_BARRIER_INVALID: refusing to remove malformed barrier')
    target.unlink()
    return True


def runtime_status(database: str | os.PathLike[str]) -> dict:
    """Return whether MCP/runtime must refuse service until a verified CLI recovery."""
    target = barrier_path(database)
    if target.is_symlink():
        return {'allowed': False, 'status': 'barrier_symlink', 'path': str(target)}
    if not target.exists():
        return {'allowed': True, 'status': 'ready'}
    try:
        data = json.loads(target.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {'allowed': False, 'status': 'barrier_unreadable', 'path': str(target)}
    if not _valid_payload(data):
        return {'allowed': False, 'status': 'barrier_invalid', 'path': str(target)}
    return {'allowed': False, 'status': 'update_incomplete', 'path': str(target),
            'update_id': data.get('update_id'), 'phase': data.get('phase'), 'pid': data.get('pid')}
