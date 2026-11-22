"""Adaptador de solo lectura: no migra, filtra ni altera scores."""
import json
from dataclasses import asdict
from .ledger import Ledger
from .selector import Candidate, Query, select


def reorder(connection, rows, context):
    original = list(rows)
    try:
        values = json.loads(context) if isinstance(context,str) else context
        query = Query(**values)
        if not connection.execute("SELECT 1 FROM sqlite_master WHERE name='ctx_claims'").fetchone():
            return original, dict(status='unknown',winner=None,reason='no_approved_context')
        # Reader sin constructor: ninguna DDL/commit en la búsqueda.
        ledger = object.__new__(Ledger)
        ledger.db = connection
        decision = select(ledger,query,tuple(Candidate(r[0],r[4]) for r in original))
        by_node = {r[0]:r for r in original}
        ordered = [by_node[c.node] for c in decision.candidates]
        info = asdict(decision); info.pop('candidates')
        info['authority'] = 'approved_context_not_universal_truth'
        return ordered, info
    except Exception as exc:
        return original, dict(status='fallback_error',winner=None,error=type(exc).__name__)
