"""Registro lateral de propuestas + simulación condicional, sin apply productivo."""
from dataclasses import asdict
import hashlib
import json
import sqlite3
from correction_language import extract, normalize
from ledger import Claim, Ledger, instant, text
from selector import Candidate, Query, select


class Observer:
    def __init__(self, connection):
        self.db = connection
        if self.db.execute("SELECT 1 FROM sqlite_master WHERE name IN ('largo_plazo','claims')").fetchone():
            raise ValueError('El registro de interacciones debe estar separado de la memoria/ledger')
        self.db.execute('''CREATE TABLE IF NOT EXISTS observations (
            event_id TEXT PRIMARY KEY, payload TEXT NOT NULL, result TEXT NOT NULL)''')
        self.db.commit()

    def observe(self, ledger, *, event_id, actor, role, message, observed_at, effective_at=None):
        for value in (event_id, actor, role):
            text(value)
        instant(observed_at)
        if effective_at is not None:
            instant(effective_at)
        if not isinstance(message, str) or len(message) > 4096:
            raise ValueError('Texto ausente o excede 4096 caracteres')
        payload = dict(actor=actor, role=role, message=message,
                       observed_at=observed_at, effective_at=effective_at)
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        prior = self.db.execute('SELECT payload,result FROM observations WHERE event_id=?', (event_id,)).fetchone()
        if prior:
            if prior[0] != encoded:
                raise ValueError('event_id reutilizado con contenido distinto')
            return json.loads(prior[1])
        extraction = extract(message)
        result = dict(event_id=event_id, status='abstain', reason='untrusted_role',
                      extraction=asdict(extraction), old_claim=None, confirmed=False,
                      production_action='none')
        if role == 'user':
            result.update(status=extraction.status, reason=extraction.reason)
            if extraction.status == 'proposal':
                result.update(status='needs_effective_time', reason='effective_time_not_inferred')
                if effective_at is not None:
                    f = extraction.fields
                    ctx = ledger.context(f['entity'], f['attribute'], f['scope'], effective_at)
                    candidates = tuple(Candidate(node, 0) for node in sorted({c.node for c in ctx.values()}))
                    d = select(ledger, Query(f['entity'], f['attribute'], f['scope'], effective_at), candidates)
                    matches = [ctx[k] for k in d.claims if normalize(ctx[k].value) == f['old']]
                    if d.status == 'conflict':
                        result.update(status='needs_review', reason='existing_conflict')
                    elif len(matches) != 1:
                        result.update(status='needs_review', reason='missing_or_ambiguous_predecessor')
                    else:
                        result.update(status='pending_confirmation', reason='predecessor_grounded', old_claim=matches[0].id)
        with self.db:
            self.db.execute('INSERT INTO observations VALUES (?,?,?)',
                            (event_id, encoded, json.dumps(result, ensure_ascii=False, sort_keys=True)))
        return json.loads(json.dumps(result))

    def simulate(self, ledger, event_id, *, new_node, query, candidates):
        text(new_node)
        row = self.db.execute('SELECT payload,result FROM observations WHERE event_id=?', (event_id,)).fetchone()
        if row is None:
            raise ValueError('Interacción inexistente')
        payload, proposal = map(json.loads, row)
        rows = tuple(candidates)
        original = asdict(select(ledger, query, rows))
        if proposal['status'] != 'pending_confirmation':
            return dict(mode='observation_only', status='not_simulated',
                        reason=proposal['reason'], actual=original, would_if_confirmed=None)
        # Copia consistente en RAM. Confirmación ficticia SOLO contrafactual.
        copy = sqlite3.connect(':memory:')
        try:
            ledger.db.backup(copy)
            simulation = Ledger(copy)
            f = proposal['extraction']['fields']
            cid = 'interaction:' + hashlib.sha256((event_id+row[0]).encode()).hexdigest()
            source = 'interaction:' + event_id
            simulation.add(Claim(cid, new_node, f['entity'], f['attribute'], f['scope'],
                                 f['new'], source, payload['effective_at'], confirmed=True))
            simulation.supersede(cid, proposal['old_claim'], source)
            hypothetical = asdict(select(simulation, query, rows))
        finally:
            copy.close()
        return dict(mode='observation_only', status='simulated_not_applied',
                    actual=original, would_if_confirmed=hypothetical,
                    confirmation_required=True, production_action='none')
