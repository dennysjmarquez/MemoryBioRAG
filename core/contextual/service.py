"""Correcciones aprobadas: unidad de trabajo en UNA DB, compatible con WAL.

El cliente MCP local tiene acceso a todos los contextos. El digest es
control de concurrencia, no autenticación. No altera recuerdos ni asociaciones.
"""
import hashlib
import json
from pathlib import Path
import sqlite3
from .language import extract, normalize
from .ledger import Ledger, instant, text
from .selector import Candidate, Query, select


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


class Corrections:
    def __init__(self, path):
        path = Path(path).expanduser().resolve()
        if not path.is_file():
            raise ValueError('DB existente requerida; no crear memoria por error')
        self.principal = 'local-mcp'  # Procedencia técnica, no identidad autenticada.
        self.db = sqlite3.connect(path.as_uri()+'?mode=rw', uri=True, timeout=10)
        if not self.db.execute("SELECT 1 FROM sqlite_master WHERE name='largo_plazo'").fetchone():
            self.db.close()
            raise ValueError('No es una DB BioRAG')
        self.ledger = Ledger(self.db)
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS ctx_proposals (
                id TEXT PRIMARY KEY, payload TEXT NOT NULL, created_by TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS ctx_approvals (
                request_id TEXT PRIMARY KEY, proposal_id TEXT UNIQUE NOT NULL REFERENCES ctx_proposals(id),
                request TEXT NOT NULL, receipt TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS ctx_synapses (
                successor_claim TEXT PRIMARY KEY REFERENCES ctx_claims(id),
                predecessor_claim TEXT NOT NULL REFERENCES ctx_claims(id),
                origen TEXT NOT NULL, destino TEXT NOT NULL,
                tipo TEXT NOT NULL CHECK(tipo='sustituye'), scope TEXT NOT NULL, source TEXT NOT NULL);
        ''')

    def close(self):
        self.db.close()

    def _node(self, name):
        row = self.db.execute('SELECT concepto,contenido FROM largo_plazo WHERE concepto=?', (name,)).fetchone()
        if row is None:
            raise ValueError('Nodo inexistente: '+name)
        return list(row)

    def register(self, proposal_id, message, old_node, new_node, observed_at, effective_at, previous_from=None):
        for v in (proposal_id,old_node,new_node):
            text(v)
        instant(observed_at); instant(effective_at)
        if previous_from is not None:
            instant(previous_from)
            if previous_from > effective_at:
                raise ValueError('Fecha del antecedente posterior a la corrección')
        extraction = extract(message)
        if extraction.status != 'proposal':
            return dict(status='abstain', reason=extraction.reason, production_action='none')
        f = extraction.fields
        if old_node == new_node:
            raise ValueError('Usar nodos distintos, sin reescribir el histórico')
        self._node(old_node); self._node(new_node)
        payload = dict(message=message, fields=f, spans=extraction.spans, old_node=old_node,
                       new_node=new_node, observed_at=observed_at, effective_at=effective_at,
                       previous_from=previous_from)
        raw = encoded(payload)
        with self.db:
            old = self.db.execute('SELECT payload FROM ctx_proposals WHERE id=?', (proposal_id,)).fetchone()
            if old and old[0] != raw:
                raise ValueError('ID de propuesta reutilizado')
            self.db.execute('INSERT OR IGNORE INTO ctx_proposals VALUES (?,?,?)', (proposal_id,raw,self.principal))
        approved=self.db.execute('SELECT receipt FROM ctx_approvals WHERE proposal_id=?',(proposal_id,)).fetchone()
        return dict(status='approved' if approved else 'pending_confirmation', id=proposal_id,
                    confirmed=bool(approved), receipt=json.loads(approved[0]) if approved else None)

    def review(self, proposal_id):
        row = self.db.execute('SELECT payload,created_by FROM ctx_proposals WHERE id=?', (proposal_id,)).fetchone()
        if row is None:
            raise ValueError('Propuesta inexistente')
        payload = json.loads(row[0]); f = payload['fields']
        at = payload['effective_at']
        claims = self.ledger.context(f['entity'],f['attribute'],f['scope'],at)
        edges = self.ledger.edges(f['entity'],f['attribute'],f['scope'],at)
        context = [vars(c) for _,c in sorted(claims.items())]
        evidence = dict(id=proposal_id,payload=payload,created_by=row[1],context=context,edges=edges,
                        nodes=[self._node(payload['old_node']),self._node(payload['new_node'])],
                        policy='trusted-local-single-valued-v2',bootstrap_predecessor=not bool(claims))
        raw=encoded(evidence).encode()
        if len(raw)>1024*1024:
            raise ValueError('Revisión excede presupuesto 1 MiB')
        approved=self.db.execute('SELECT receipt FROM ctx_approvals WHERE proposal_id=?',(proposal_id,)).fetchone()
        return dict(digest=hashlib.sha256(raw).hexdigest(),evidence=evidence,
                    approval=json.loads(approved[0]) if approved else None)

    def confirm(self, proposal_id, digest, request_id, *, fault=None):
        for v in (proposal_id,digest,request_id):
            text(v)
        request=encoded([proposal_id,digest,self.principal])
        self.db.execute('BEGIN IMMEDIATE')
        try:
            review=self.review(proposal_id)
            prior=self.db.execute('SELECT request,receipt FROM ctx_approvals WHERE request_id=?',(request_id,)).fetchone()
            if prior:
                if json.loads(prior[0])[:2] != [proposal_id, digest]:
                    raise ValueError('request_id reutilizado')
                self.db.rollback()
                return json.loads(prior[1])
            if review['approval']:
                raise ValueError('Propuesta ya aprobada')
            if review['digest']!=digest:
                raise ValueError('stale_proposal')
            e=review['evidence']; p=e['payload']; f=p['fields']; at=p['effective_at']
            source='approval:'+request_id
            cid='ctx:'+hashlib.sha256(proposal_id.encode()).hexdigest()
            if e['bootstrap_predecessor']:
                if p['previous_from'] is None:
                    raise ValueError('Antecedente sin ledger: revisar y proporcionar fecha previa explícita')
                old_id=cid+':previous'
                self.db.execute('INSERT INTO ctx_claims VALUES (?,?,?,?,?,?,?,?,?,?)',
                    (old_id,p['old_node'],f['entity'],f['attribute'],f['scope'],f['old'],source,
                     p['previous_from'],None,1))
            else:
                ctx=self.ledger.context(f['entity'],f['attribute'],f['scope'],at)
                nodes=sorted({c.node for c in ctx.values()})
                decision=select(self.ledger,Query(f['entity'],f['attribute'],f['scope'],at),
                                tuple(Candidate(n,0) for n in nodes))
                matches=[ctx[k] for k in decision.claims if normalize(ctx[k].value)==f['old']
                         and ctx[k].node==p['old_node']]
                if decision.status!='resolved' or len(matches)!=1:
                    raise ValueError('Antecedente no único/vigente; requiere revisión')
                old_id=matches[0].id
            self.db.execute('INSERT INTO ctx_claims VALUES (?,?,?,?,?,?,?,?,?,?)',
                (cid,p['new_node'],f['entity'],f['attribute'],f['scope'],f['new'],source,at,None,1))
            self.db.execute('INSERT INTO ctx_revisions VALUES (?,?,?)',(cid,old_id,source))
            if fault:
                fault('after_ledger')
            self.db.execute("INSERT INTO ctx_synapses VALUES (?,?,?,?,'sustituye',?,?)",
                            (cid,old_id,p['new_node'],p['old_node'],f['scope'],source))
            if fault:
                fault('after_graph')
            receipt=dict(status='approved',proposal_id=proposal_id,request_id=request_id,
                         principal=self.principal,claim_id=cid,source=source,
                         bootstrap_predecessor=e['bootstrap_predecessor'])
            self.db.execute('INSERT INTO ctx_approvals VALUES (?,?,?,?)',(request_id,proposal_id,request,encoded(receipt)))
            self.db.commit()
            return receipt
        except Exception:
            self.db.rollback()
            raise
