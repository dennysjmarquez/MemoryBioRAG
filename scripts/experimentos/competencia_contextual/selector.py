"""Competencia contextual determinista: decide con evidencia, nunca con nombres.

No es una neurona ni una medida de verdad universal. No aprende al leer.
Los scores base se conservan, no se reinterpretan como probabilidad de vigencia.
"""
from dataclasses import dataclass
from ledger import instant, text


@dataclass(frozen=True)
class Candidate:
    node: str
    base_score: float


@dataclass(frozen=True)
class Query:
    entity: str
    attribute: str
    scope: str
    at: float
    intent: str = 'current'


@dataclass(frozen=True)
class Decision:
    status: str
    winner: str | None
    candidates: tuple
    claims: tuple = ()
    superseded: tuple = ()
    missing_nodes: tuple = ()


def select(ledger, query, candidates):
    """Promoción estable de un candidato respaldado, sin eliminar ningún vecino.

    Sin evidencia completa para elegir: señal explícita y orden original intacto.
    El llamador debe respetar winner/status, no interpretar top-1 como certeza.
    """
    rows = tuple(candidates)
    if len({c.node for c in rows}) != len(rows):
        raise ValueError('Candidatos duplicados')
    for c in rows:
        text(c.node)
        instant(c.base_score)
    instant(query.at)
    for v in (query.entity, query.attribute, query.scope):
        text(v)
    if query.intent not in ('current', 'historical', 'identifier', 'generic'):
        raise ValueError('Intención desconocida')
    if query.intent != 'current':
        return Decision('passthrough', None, rows)
    claims = ledger.context(query.entity, query.attribute, query.scope, query.at)
    if not claims:
        return Decision('unknown', None, rows)
    confirmed = {k: c for k, c in claims.items() if c.confirmed}
    edges = ledger.edges(query.entity, query.attribute, query.scope, query.at)
    # Una sustitución efectiva no deja de existir cuando expira el sucesor:
    # en ese caso no se resucita automáticamente al predecesor.
    replaced = {old for new, old, source in edges if new in confirmed and old in confirmed}
    surviving = {k: c for k, c in confirmed.items() if k not in replaced
                 and (c.valid_until is None or query.at < c.valid_until)}
    ids, suppressed = tuple(sorted(surviving)), tuple(sorted(replaced))
    if not surviving:
        return Decision('unknown', None, rows, ids, suppressed)
    if len({c.value for c in surviving.values()}) > 1:
        return Decision('conflict', None, rows, ids, suppressed)
    eligible = {c.node for c in surviving.values()}
    # Afirmaciones no confirmadas quedan como pistas, nunca autoridad.
    selected = next((c for c in rows if c.node in eligible), None)
    if selected is None:
        return Decision('retrieval_gap', None, rows, ids, suppressed, tuple(sorted(eligible)))
    ordered = (selected,) + tuple(c for c in rows if c.node != selected.node)
    return Decision('resolved', selected.node, ordered, ids, suppressed)
