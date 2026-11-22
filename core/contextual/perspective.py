"""Contrato experimental de perspectiva explícita; no infiere intención del texto.

Se activa en MCP con BIORAG_TEMPORAL_PROTOTYPE=1. Opera sobre el pool
recuperado, nunca promete búsqueda exhaustiva ni inventa fechas de hechos.
"""
from dataclasses import asdict
from .ledger import Ledger, instant, text
from .selector import Candidate, Query, select

MODES = ('relevancia', 'recientes', 'antiguos', 'vigente', 'historico', 'ambos')
DESCRIPTION = (
    'PROTOTIPO: contexto_vigencia exige mode. Elige explícitamente: '
    'relevancia = pertinencia sin afirmar vigencia; recientes/antiguos = orden por '
    'fecha de registro creado_en, NO fecha del hecho; vigente = estado aplicable '
    'según evidencia aprobada; historico = antecedentes sustituidos según evidencia; '
    'ambos = vigentes y antecedentes distinguidos, conservando otros candidatos. '
    'Ejemplo general: {"mode":"relevancia"}. Para recientes/antiguos añade '
    '"time_basis":"registro". Para vigente/historico/ambos exige entity, attribute, '
    'scope exactos y at (segundos UNIX de la fecha consultada). Descubre el contexto '
    'aprobado, no lo inventes ni deduzcas vigencia del nombre o fecha de registro. '
    'Sin evidencia: VIGENCIA_NO_RESUELTA o HISTORIA_NO_RESUELTA. '
    'No uses relevancia como escape si el usuario pidió vigencia. '
    'Sin elección: CONTEXTO_VIGENCIA_REQUERIDO. No hay auto ni inferencia por palabras.'
)


class PerspectiveError(ValueError):
    pass


def validate(context):
    if not isinstance(context, dict) or 'mode' not in context:
        raise PerspectiveError('CONTEXTO_VIGENCIA_REQUERIDO: '+DESCRIPTION)
    if context['mode'] not in MODES:
        raise PerspectiveError('MODO_INVALIDO: elegir '+', '.join(MODES))
    mode = context['mode']
    allowed = {'mode'}
    if mode in ('recientes', 'antiguos'):
        allowed.add('time_basis')
        if context.get('time_basis') != 'registro':
            raise PerspectiveError('BASE_TEMPORAL_REQUERIDA: time_basis="registro"; fecha del hecho no implementada')
    if mode in ('vigente', 'historico', 'ambos'):
        allowed.update(('entity', 'attribute', 'scope', 'at'))
        try:
            for key in ('entity', 'attribute', 'scope'):
                text(context.get(key))
            instant(context.get('at'))
        except ValueError as exc:
            raise PerspectiveError('CONTEXTO_REQUERIDO: proporcionar entity, attribute, scope y at explícitos') from exc
    if set(context) - allowed:
        raise PerspectiveError('CAMPO_NO_ADMITIDO: '+', '.join(sorted(set(context)-allowed)))
    return dict(context)


def apply(connection, rows, context):
    """Mantiene scores y candidatos; estratifica historia, no fuerza certezas.

    vigente/historico no resueltos retornan candidatos exploratorios etiquetados;
    el consumidor NO debe afirmar que el top-1 satisface el modo solicitado.
    """
    context = validate(context)
    rows = list(rows);mode = context['mode']
    info = dict(mode=mode, status='resolved', coverage='retrieved_pool_only',
                winner=None, groups={}, scores_unchanged=True)
    if mode == 'relevancia':
        info['status'] = 'relevance_only'
        return rows, info
    if mode in ('recientes', 'antiguos'):
        # Consulta por lotes: acota variables SQL sin un SELECT por candidato.
        dates = {}
        nodes = [row[0] for row in rows]
        for start in range(0, len(nodes), 500):
            batch = nodes[start:start+500]
            placeholders = ','.join('?' for _ in batch)
            for node, value in connection.execute(
                    'SELECT concepto,creado_en FROM largo_plazo WHERE concepto IN ('+placeholders+')', batch):
                try:
                    instant(value)
                    if value <= 0:
                        raise ValueError('Fecha desconocida')
                except ValueError:
                    continue
                dates[node] = value
        known = [r for r in rows if r[0] in dates]
        known.sort(key=lambda r: dates[r[0]], reverse=mode == 'recientes')
        unknown = [r for r in rows if r[0] not in dates]
        info.update(time_basis='registro', dates=dates, unknown_dates=[r[0] for r in unknown],
                    status='partial' if unknown else 'resolved')
        return known + unknown, info
    try:
        if not connection.execute("SELECT 1 FROM sqlite_master WHERE name='ctx_claims'").fetchone():
            raise LookupError('no_approved_context')
        ledger = Ledger(connection, initialize=False)
        query = Query(**{key:context[key] for key in ('entity','attribute','scope','at')})
        decision = select(ledger, query, tuple(Candidate(r[0],r[4]) for r in rows))
        claims = ledger.context(query.entity,query.attribute,query.scope,query.at)
        historical = {claims[key].node for key in decision.superseded if key in claims}
        current = {claims[key].node for key in decision.claims if key in claims}
        info['decision'] = {k:v for k,v in asdict(decision).items() if k != 'candidates'}
        info['groups'] = {r[0]: ('conflict' if decision.status == 'conflict' and r[0] in current else
                                'vigente' if r[0] in current and decision.status == 'resolved' else
                                'historico' if r[0] in historical else 'sin_evidencia') for r in rows}
        if mode in ('vigente','ambos') and decision.status != 'resolved':
            info.update(status='VIGENCIA_NO_RESUELTA', reason=decision.status)
            return rows, info
        if mode == 'historico' and not any(r[0] in historical for r in rows):
            info.update(status='HISTORIA_NO_RESUELTA', reason='no_historical_candidate')
            return rows, info
        info['winner'] = decision.winner if mode != 'historico' else None
        if mode == 'vigente':
            preferred = {decision.winner}
            return [r for r in rows if r[0] in preferred]+[r for r in rows if r[0] not in preferred], info
        if mode == 'historico':
            return [r for r in rows if r[0] in historical]+[r for r in rows if r[0] not in historical], info
        return ([r for r in rows if r[0] in current]+[r for r in rows if r[0] in historical and r[0] not in current]+
                [r for r in rows if r[0] not in current | historical]), info
    except (LookupError, ValueError) as exc:
        info.update(status='HISTORIA_NO_RESUELTA' if mode == 'historico' else 'VIGENCIA_NO_RESUELTA', reason=str(exc))
        return rows, info
