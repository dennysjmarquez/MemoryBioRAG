"""Puerto experimental de búsqueda. Nunca modifica las tuplas ni elimina pistas."""
from selector import Candidate, select


def wrap_search(original, ledger, resolve_query, emit, *, shadow=True):
    def search(*args, **kwargs):
        results, total = original(*args, **kwargs)
        rows = tuple(results)
        status, decision, output = 'passthrough_no_context', None, rows
        try:
            query = resolve_query(args, kwargs)
            if query is not None:
                decision = select(ledger, query, tuple(Candidate(r[0], r[4]) for r in rows))
                status = decision.status
                by_node = {r[0]: r for r in rows}
                proposed = tuple(by_node[c.node] for c in decision.candidates)
                if not shadow:
                    output = proposed
        except Exception as exc:
            status = 'fallback_error:' + type(exc).__name__
            output = rows
        emit(dict(status=status, shadow=shadow,
                  before=[(r[0], r[4]) for r in rows],
                  after=[(r[0], r[4]) for r in output],
                  proposed_winner=decision.winner if decision else None))
        return (list(output) if isinstance(results, list) else tuple(output)), total
    return search
