import concurrent.futures
import sqlite3
import tempfile
from pathlib import Path
import unittest
from approval import Approval
from ledger import Claim
from observation import Observer


class ApprovalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='biorag-approval-')
        self.root = Path(self.temp.name)
        (self.root/'LAB_ONLY').touch()
        db = sqlite3.connect(str(self.root/'graph.db'))
        db.executescript('''CREATE TABLE largo_plazo(concepto TEXT PRIMARY KEY,contenido TEXT);
            INSERT INTO largo_plazo VALUES ('old','keep old'),('new','keep new');
            CREATE TABLE sinapsis(origen TEXT,destino TEXT,tipo TEXT,PRIMARY KEY(origen,destino));
            INSERT INTO sinapsis VALUES ('new','old','manual');''')
        db.close()
        self.grants = [('service','port','prod')]
        self.s = Approval(self.root,'owner',self.grants)
        self.s.ledger.add(Claim('old','old','service','port','prod','8080','fixture',1,confirmed=True))
        self.log = sqlite3.connect(':memory:')
        observer = Observer(self.log)
        observer.observe(self.s.ledger,event_id='p',actor='owner',role='user',
            message='Corrijo: el port de service en prod es 8443, no 8080.',observed_at=3,effective_at=2)
        self.s.register(observer,'p')
        self.digest = self.s.review('p','new')['digest']

    def tearDown(self):
        self.s.close()
        self.log.close()
        self.temp.cleanup()

    def confirm(self, **kw):
        return self.s.confirm('p',kw.get('node','new'),kw.get('digest',self.digest),kw.get('request','r'),fault=kw.get('fault'))

    def test_atomic_approval_preserves_nodes_and_manual_edge(self):
        before=self.s.db.execute('SELECT * FROM graph.largo_plazo').fetchall()
        result=self.confirm()
        self.assertEqual(result['status'],'approved_projected')
        self.assertEqual(self.s.review('p','new')['approval'],result)
        self.assertEqual(self.s.db.execute('SELECT * FROM graph.largo_plazo').fetchall(),before)
        self.assertEqual(self.s.db.execute('SELECT tipo FROM graph.sinapsis').fetchall(),[('manual',)])
        self.assertEqual(self.s.db.execute('SELECT tipo FROM graph.sinapsis_sustitucion').fetchall(),[('sustituye',)])
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM revisions').fetchone()[0],1)

    def test_rollback_after_ledger_and_after_graph(self):
        for phase in ('after_ledger','after_graph'):
            def fault(point):
                if point == phase:
                    raise RuntimeError('injected failure')
            with self.assertRaises(RuntimeError):
                self.confirm(fault=fault)
            for table in ('revisions','approvals','graph.sinapsis_sustitucion'):
                self.assertEqual(self.s.db.execute('SELECT count(*) FROM '+table).fetchone()[0],0)
            self.assertEqual(self.s.db.execute('SELECT count(*) FROM claims').fetchone()[0],1)

    def test_replay_and_mismatched_request(self):
        receipt=self.confirm()
        self.assertEqual(self.confirm(),receipt)
        with self.assertRaises(ValueError):
            self.confirm(digest='different')
        with self.assertRaises(ValueError):
            self.confirm(request='another')

    def test_stale_context_requires_review(self):
        self.s.ledger.add(Claim('conflict','new','service','port','prod','9000','fixture',1,confirmed=True))
        with self.assertRaisesRegex(ValueError,'stale_proposal'):
            self.confirm()

    def test_unauthorized_even_on_replay(self):
        self.confirm()
        self.s.grants=set()
        with self.assertRaises(PermissionError):
            self.confirm()

    def test_missing_successor_rollback(self):
        digest=self.s.review('p','absent')['digest']
        with self.assertRaisesRegex(ValueError,'Nodo inexistente'):
            self.confirm(node='absent',digest=digest)
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM claims').fetchone()[0],1)

    def test_reject_same_node_and_bad_digest(self):
        with self.assertRaisesRegex(ValueError,'stale_proposal'):
            self.confirm(digest='bad')
        digest=self.s.review('p','old')['digest']
        with self.assertRaisesRegex(ValueError,'nodos distintos'):
            self.confirm(node='old',digest=digest)

    def test_growth_exact_10000_irrelevant(self):
        self.s.db.executemany('INSERT INTO claims VALUES (?,?,?,?,?,?,?,?,?,?)',
            [(f'noise{i}',f'node{i}',f'entity{i}','other','other','X','fixture',0,None,0) for i in range(10000)])
        self.s.db.commit()
        self.assertEqual(self.s.review('p','new')['digest'],self.digest)
        self.confirm()

    def test_concurrent_same_request_exactly_once(self):
        def run(_):
            service=Approval(self.root,'owner',self.grants)
            try:
                return service.confirm('p','new',self.digest,'r')
            finally:
                service.close()
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            receipts=list(executor.map(run,range(2)))
        self.assertEqual(receipts[0],receipts[1])
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM approvals').fetchone()[0],1)

    def test_changed_node_content_requires_new_review(self):
        self.s.db.execute("UPDATE graph.largo_plazo SET contenido='changed' WHERE concepto='new'")
        self.s.db.commit()
        with self.assertRaisesRegex(ValueError,'stale_proposal'):
            self.confirm()

    def test_process_death_before_commit_recovers_both_files(self):
        import subprocess
        import sys
        script = '''import os,sys
from approval import Approval
s=Approval(sys.argv[1],'owner',[('service','port','prod')])
s.confirm('p','new',sys.argv[2],'crash',fault=lambda phase: os._exit(73) if phase=='after_graph' else None)
'''
        env = dict(__import__('os').environ, PYTHONPATH=str(Path(__file__).parent.resolve()))
        result = subprocess.run([sys.executable,'-c',script,str(self.root),self.digest],env=env)
        self.assertEqual(result.returncode,73)
        self.s.close()
        self.s=Approval(self.root,'owner',self.grants)
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM claims').fetchone()[0],1)
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM graph.sinapsis_sustitucion').fetchone()[0],0)
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM approvals').fetchone()[0],0)
        self.confirm()

    def test_lost_ack_after_commit_replays_persisted_receipt(self):
        import subprocess
        import sys
        script = '''import os,sys
from approval import Approval
s=Approval(sys.argv[1],'owner',[('service','port','prod')])
s.confirm('p','new',sys.argv[2],'r')
os._exit(74)
'''
        env = dict(__import__('os').environ, PYTHONPATH=str(Path(__file__).parent.resolve()))
        result = subprocess.run([sys.executable,'-c',script,str(self.root),self.digest],env=env)
        self.assertEqual(result.returncode,74)
        self.assertEqual(self.confirm()['status'],'approved_projected')
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM approvals').fetchone()[0],1)
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM graph.sinapsis_sustitucion').fetchone()[0],1)

    def test_concurrent_different_requests_only_one_approval(self):
        def run(request):
            service=Approval(self.root,'owner',self.grants)
            try:
                return service.confirm('p','new',self.digest,request)['status']
            except ValueError:
                return 'rejected'
            finally:
                service.close()
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            results=list(executor.map(run,('a','b')))
        self.assertEqual(sorted(results),['approved_projected','rejected'])
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM approvals').fetchone()[0],1)

    def test_approval_does_not_replace_another_scope(self):
        from selector import Candidate, Query, select
        self.s.ledger.add(Claim('test-old','old','service','port','test','8080','fixture',1,confirmed=True))
        # Unrelated context must not stale the original review or inherit its revision.
        self.assertEqual(self.s.review('p','new')['digest'],self.digest)
        self.confirm()
        rows=(Candidate('new',1),Candidate('old',.5))
        decision=select(self.s.ledger,Query('service','port','test',3),rows)
        self.assertEqual(decision.winner,'old')
        self.assertEqual(self.s.db.execute('SELECT scope FROM graph.sinapsis_sustitucion').fetchall(),[('prod',)])

    def test_second_correction_can_return_to_previous_value_without_claim_cycle(self):
        from selector import Candidate, Query, select
        self.confirm()
        observer=Observer(self.log)
        proposal=observer.observe(self.s.ledger,event_id='p2',actor='owner',role='user',
            message='Actualizo: el port de service en prod pasa de 8443 a 8080.',observed_at=4,effective_at=3)
        self.assertEqual(proposal['status'],'pending_confirmation')
        self.s.register(observer,'p2')
        digest=self.s.review('p2','old')['digest']
        self.s.confirm('p2','old',digest,'r2')
        decision=select(self.s.ledger,Query('service','port','prod',4),
                        (Candidate('new',1),Candidate('old',.5)))
        self.assertEqual(decision.winner,'old')
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM revisions').fetchone()[0],2)
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM graph.sinapsis_sustitucion').fetchone()[0],2)

    def test_review_budget_is_visible_not_truncation(self):
        self.s.db.execute("UPDATE graph.largo_plazo SET contenido=? WHERE concepto='new'",('X'*(1024*1024),))
        self.s.db.commit()
        with self.assertRaisesRegex(ValueError,'presupuesto'):
            self.s.review('p','new')

    def test_confinement(self):
        with tempfile.TemporaryDirectory(prefix='unmarked-') as root:
            with self.assertRaises(ValueError):
                Approval(root,'owner',self.grants)
