"""Correcciones independientes del idioma, sin romper propuestas previas."""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from core.contextual.service import Corrections
from core.contextual.perspective import apply


class StructuredCorrectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'memory.db'
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE largo_plazo(concepto TEXT PRIMARY KEY,contenido TEXT)')
            db.executemany('INSERT INTO largo_plazo VALUES (?,?)',[('old','source A'),('new','source B')])
        self.service=Corrections(self.path)

    def tearDown(self):self.service.close();self.tmp.cleanup()

    def register(self,**kwargs):
        values=dict(proposal_id='p',message='訂正: 新しい設定です。',old_node='old',new_node='new',
                    observed_at=3,effective_at=2,context={'entity':'service-ID','attribute':'port-ID','scope':'prod-ID'},
                    old_value='A',new_value='B',previous_from=1)
        values.update(kwargs);return self.service.register_structured(**values)

    def test_mcp_path_does_not_call_language_parser(self):
        for i,message in enumerate(('設定を変更しました','إعداد جديد','The setting changed','Corrijo lo anterior','🧠')):
            with patch('core.contextual.language.extract',side_effect=AssertionError('parser no permitido')):
                result=self.register(proposal_id='p'+str(i),message=message)
            self.assertFalse(result['confirmed'])
            evidence=self.service.review('p'+str(i))['evidence']
            self.assertEqual(evidence['payload']['message'],message)
            self.assertIsNone(evidence['payload']['spans'])
        self.assertEqual(self.service.db.execute('SELECT count(*) FROM ctx_claims').fetchone()[0],0)

    def test_explicit_values_case_identity_and_atomic_confirmation(self):
        self.register();review=self.service.review('p')
        receipt=self.service.confirm('p',review['digest'],'r')
        self.assertEqual(receipt,self.service.confirm('p',review['digest'],'r'))
        rows=[('old','',0,None,.9),('new','',0,None,.3)]
        context=dict(mode='vigente',entity='service-ID',attribute='port-ID',scope='prod-ID',at=3)
        self.assertEqual(apply(self.service.db,rows,context)[1]['winner'],'new')
        self.assertEqual(self.service.db.execute("SELECT value FROM ctx_claims WHERE node='new'").fetchone()[0],'B')

    def test_rejects_missing_context_and_identical_values_without_proposal(self):
        for kwargs in ({'context':{}},{'context':{'entity':'e','attribute':'a','scope':''}}, {'old_value':'B'}):
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):self.register(**kwargs)
        self.assertEqual(self.service.db.execute('SELECT count(*) FROM ctx_proposals').fetchone()[0],0)

    def test_persisted_legacy_proposal_is_still_reviewable(self):
        self.service.register('legacy','Corrijo: el puerto de servicio en prod es 8443, no 8080.','old','new',3,2,1)
        self.service.close();self.service=Corrections(self.path)
        review=self.service.review('legacy')
        self.assertEqual(self.service.confirm('legacy',review['digest'],'legacy-r')['status'],'approved')

    def test_changed_payload_does_not_reuse_proposal_id(self):
        self.register()
        with self.assertRaisesRegex(ValueError,'reutilizado'):self.register(new_value='C')

    def test_confirmation_rollback_still_atomic(self):
        self.register();digest=self.service.review('p')['digest']
        def fault(point):
            if point=='after_graph':raise RuntimeError('injected')
        with self.assertRaises(RuntimeError):self.service.confirm('p',digest,'r',fault=fault)
        for table in ('ctx_claims','ctx_revisions','ctx_synapses','ctx_approvals'):
            self.assertEqual(self.service.db.execute('SELECT count(*) FROM '+table).fetchone()[0],0)


if __name__=='__main__':unittest.main()
