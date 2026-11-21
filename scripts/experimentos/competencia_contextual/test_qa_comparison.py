import json
from pathlib import Path
import tempfile
import unittest
from comparar_qa_selector import compare


class QaComparisonTests(unittest.TestCase):
    def test_exact_comparison_detects_changes_and_incomplete_traces(self):
        with tempfile.TemporaryDirectory(prefix='qa-comparison-') as root:
            root=Path(root); scripts=root/'code/scripts'; scripts.mkdir(parents=True)
            snapshots=root/'code/snapshots';snapshots.mkdir()
            (snapshots/'qa_escape_qcr_20260811.db').write_bytes(b'fixture')
            cases=scripts/'cases.jsonl';cases.write_text(json.dumps(dict(id='fixture'))+'\n')
            output=root/'results';output.mkdir()
            metric=dict(casos_total=1,global_ignored=None,categorias={})
            metric['global']=dict(recall_at_5=100,recall_at_1=100,mrr=1,negativos_fp=0,negativos_fp_rate=0,queries=1)
            import hashlib
            manifest={'snapshots/qa_escape_qcr_20260811.db':hashlib.sha256(b'fixture').hexdigest(),
                      'scripts/evaluar_qa.py':'fixture','scripts/casos_qa_baseline_v1.jsonl':'fixture'}
            (output/'input_manifest.json').write_text(json.dumps(manifest))
            trace=dict(query='fixture',before=[['node',1]],after=[['node',1]],status='passthrough_no_context')
            for mode in ('baseline','selector'):
                (output/(mode+'-metrics.json')).write_text(json.dumps(metric))
                (output/(mode+'-trace.jsonl')).write_text(json.dumps(trace)+'\n')
                (output/(mode+'-failed.jsonl')).write_text('')
                (output/(mode+'-exit.txt')).write_text('0')
            self.assertTrue(compare(output,cases)['exact_output_order_scores_per_case_equal'])
            trace['after']=[['other',1]]
            (output/'selector-trace.jsonl').write_text(json.dumps(trace)+'\n')
            self.assertEqual(compare(output,cases)['changed_case_ids'],['fixture'])
            (output/'selector-trace.jsonl').write_text('')
            with self.assertRaisesRegex(ValueError,'incompleta'):
                compare(output,cases)
