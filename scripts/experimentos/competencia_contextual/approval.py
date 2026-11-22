"""Aprobación atómica de laboratorio; SQLite disk + ATTACH, rollback journals.
No exponer a DB viva. El host inyecta principal y grants; no el mensaje/tool.
"""
import hashlib
import json
from pathlib import Path
import sqlite3
from ledger import Ledger, text
from selector import Candidate, Query, select


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


class Approval:
    def __init__(self, root, principal, grants):
        root = Path(root).resolve()
        if not root.is_relative_to(Path('/tmp')) or not (root/'LAB_ONLY').is_file():
            raise ValueError('Requiere laboratorio marcado bajo /tmp')
        text(principal)
        self.principal, self.grants = principal, set(map(tuple, grants))
        paths = [root/'ledger.db', root/'graph.db']
        if any(p.is_symlink() for p in paths) or not paths[1].is_file():
            raise ValueError('Se requiere copia local del grafo sin symlinks')
        self.db = sqlite3.connect(str(paths[0]), timeout=10)
        self.ledger = Ledger(self.db)
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS proposals(id TEXT PRIMARY KEY,payload TEXT NOT NULL,result TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS approvals(request_id TEXT PRIMARY KEY,proposal_id TEXT UNIQUE NOT NULL,
                request TEXT NOT NULL,receipt TEXT NOT NULL);
        ''')
        self.db.execute('ATTACH DATABASE ? AS graph', (str(paths[1]),))
        for schema in ('main', 'graph'):
            if self.db.execute(f'PRAGMA {schema}.journal_mode=DELETE').fetchone()[0] != 'delete':
                raise ValueError('No soportar WAL en aprobación multiarchivo')
            self.db.execute(f'PRAGMA {schema}.synchronous=FULL')
        self.db.execute('''CREATE TABLE IF NOT EXISTS graph.sinapsis_sustitucion (
            successor_claim TEXT PRIMARY KEY, predecessor_claim TEXT NOT NULL,
            origen TEXT NOT NULL, destino TEXT NOT NULL, tipo TEXT NOT NULL CHECK(tipo='sustituye'),
            entity TEXT NOT NULL, attribute TEXT NOT NULL, scope TEXT NOT NULL,
            valid_from REAL NOT NULL, source TEXT NOT NULL)''')
        self.db.commit()

    def close(self):
        self.db.close()

    def register(self, observer, proposal_id):
        row = observer.db.execute('SELECT payload,result FROM observations WHERE event_id=?', (proposal_id,)).fetchone()
        if row is None:
            raise ValueError('Propuesta inexistente')
        result = json.loads(row[1])
        if result['status'] != 'pending_confirmation':
            raise ValueError('Propuesta no elegible')
        self._authorize(result['extraction']['fields'])
        old = self.db.execute('SELECT payload,result FROM proposals WHERE id=?', (proposal_id,)).fetchone()
        if old and tuple(old) != tuple(row):
            raise ValueError('ID de propuesta reutilizado')
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO proposals VALUES (?,?,?)', (proposal_id, *row))

    def _authorize(self, fields):
        if (fields['entity'], fields['attribute'], fields['scope']) not in self.grants:
            raise PermissionError('Contexto no delegado por anfitrión')

    def review(self, proposal_id, new_node):
        text(new_node)
        row = self.db.execute('SELECT payload,result FROM proposals WHERE id=?', (proposal_id,)).fetchone()
        if row is None:
            raise ValueError('Propuesta inexistente')
        payload, result = map(json.loads, row)
        f = result['extraction']['fields']
        self._authorize(f)
        at = payload['effective_at']
        claims = self.ledger.context(f['entity'], f['attribute'], f['scope'], at)
        edges = self.ledger.edges(f['entity'], f['attribute'], f['scope'], at)
        context = [list(r) for r in self.db.execute('''SELECT * FROM claims WHERE entity=? AND attribute=?
            AND scope=? AND valid_from<=? ORDER BY id''', (f['entity'],f['attribute'],f['scope'],at))]
        old = claims.get(result['old_claim'])
        graph_nodes = []
        for node in (old.node if old else '', new_node):
            graph_nodes.extend([list(r) for r in self.db.execute(
                'SELECT concepto,contenido FROM graph.largo_plazo WHERE concepto=?', (node,))])
        snapshot = dict(proposal_id=proposal_id, payload=payload, result=result, new_node=new_node,
                        context=context, edges=edges, graph_nodes=graph_nodes, policy='lab-explicit-context-v1')
        serialized = canonical(snapshot).encode()
        if len(serialized) > 1024 * 1024:
            raise ValueError('Evidencia excede presupuesto de revisión de 1 MiB')
        digest = hashlib.sha256(serialized).hexdigest()
        approved = self.db.execute('SELECT receipt FROM approvals WHERE proposal_id=?', (proposal_id,)).fetchone()
        return dict(digest=digest, proposal=snapshot, approver=self.principal,
                    approval=json.loads(approved[0]) if approved else None)

    def confirm(self, proposal_id, new_node, expected_digest, request_id, *, fault=None):
        for v in (proposal_id,new_node,expected_digest,request_id):
            text(v)
        request = canonical([proposal_id,new_node,expected_digest,self.principal])
        self.db.execute('BEGIN IMMEDIATE')
        try:
            # Authorize even replays; revoked grants cannot obtain fresh success.
            review = self.review(proposal_id, new_node)
            prior = self.db.execute('SELECT request,receipt FROM approvals WHERE request_id=?', (request_id,)).fetchone()
            if prior:
                if prior[0] != request:
                    raise ValueError('request_id reutilizado')
                self.db.rollback()
                return json.loads(prior[1])
            if self.db.execute('SELECT 1 FROM approvals WHERE proposal_id=?', (proposal_id,)).fetchone():
                raise ValueError('Propuesta ya aprobada')
            if review['digest'] != expected_digest:
                raise ValueError('stale_proposal')
            p = review['proposal']; f = p['result']['extraction']['fields']; at = p['payload']['effective_at']
            ctx = self.ledger.context(f['entity'],f['attribute'],f['scope'],at)
            decision = select(self.ledger, Query(f['entity'],f['attribute'],f['scope'],at),
                              tuple(Candidate(c.node,0) for c in {v.node:v for v in ctx.values()}.values()))
            old_id = p['result']['old_claim']
            matches = [ctx[k] for k in decision.claims if ctx[k].value.casefold() == f['old']]
            if decision.status != 'resolved' or len(matches)!=1 or matches[0].id != old_id:
                raise ValueError('Antecedente dejó de ser único vigente')
            old = matches[0]
            if new_node == old.node:
                raise ValueError('Requiere nodos distintos')
            for node in (old.node, new_node):
                if not self.db.execute('SELECT 1 FROM graph.largo_plazo WHERE concepto=?', (node,)).fetchone():
                    raise ValueError('Nodo inexistente en grafo')
            cid = 'approved:' + hashlib.sha256(proposal_id.encode()).hexdigest()
            source = 'approval:' + request_id
            self.db.execute('INSERT INTO claims VALUES (?,?,?,?,?,?,?,?,?,?)',
                (cid,new_node,f['entity'],f['attribute'],f['scope'],f['new'],source,at,None,1))
            self.db.execute('INSERT INTO revisions VALUES (?,?,?)', (cid,old_id,source))
            if fault:
                fault('after_ledger')
            self.db.execute('''INSERT INTO graph.sinapsis_sustitucion VALUES (?,?,?,?,'sustituye',?,?,?,?,?)''',
                (cid,old_id,new_node,old.node,f['entity'],f['attribute'],f['scope'],at,source))
            if fault:
                fault('after_graph')
            receipt = dict(status='approved_projected',proposal_id=proposal_id,request_id=request_id,
                           claim_id=cid,approver=self.principal,source=source,
                           graph_edge=[new_node,old.node,'sustituye'],scope=f['scope'])
            self.db.execute('INSERT INTO approvals VALUES (?,?,?,?)',
                            (request_id,proposal_id,request,canonical(receipt)))
            self.db.commit()
            return receipt
        except Exception:
            self.db.rollback()
            raise
