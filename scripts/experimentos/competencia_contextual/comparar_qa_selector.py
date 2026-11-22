"""Comparación emparejada de trazas/metrics QA; no exporta recuerdos ni queries.
Requiere resultados completos de ambos workers. No modifica gates ni métricas.
"""
import argparse
import hashlib
import json
from pathlib import Path


def compare(folder, cases_path):
    def read(name):
        return json.loads((folder/name).read_text())
    baseline, variant = read('baseline-metrics.json'), read('selector-metrics.json')
    cases=[json.loads(line) for line in cases_path.read_text().splitlines() if line.strip()]
    traces={mode:[json.loads(line) for line in (folder/(mode+'-trace.jsonl')).read_text().splitlines()]
            for mode in ('baseline','selector')}
    if baseline['casos_total']!=len(cases) or variant['casos_total']!=len(cases):
        raise ValueError('Conteo de casos diferente')
    if any(len(t)!=len(cases) for t in traces.values()):
        raise ValueError('Traza incompleta; no afirmar comparación por caso')
    changed=[]
    errors=[]
    for i,(a,b) in enumerate(zip(traces['baseline'],traces['selector'])):
        if a['query']!=b['query']:
            raise ValueError('Consultas no alineadas')
        if a['before']!=a['after'] or b['before']!=b['after'] or a['after']!=b['after']:
            changed.append(cases[i]['id'])
        if b['status']!='passthrough_no_context':
            errors.append(dict(id=cases[i]['id'],status=b['status']))
    keys=('recall_at_5','recall_at_1','mrr','negativos_fp','negativos_fp_rate','queries')
    table={k:dict(baseline=baseline['global'][k],adapter=variant['global'][k],
                  delta=round(variant['global'][k]-baseline['global'][k],8)) for k in keys}
    manifest=read('input_manifest.json')
    return dict(scope='921 official cases; adapter with empty ledger and absent contextual resolver',
                efficacy_with_approved_corrections_measured=False,
                hebbian_asset_manifested=('db/hebbian_clusters.json' in manifest),
                hebbian_asset_sha256=manifest.get('db/hebbian_clusters.json'),
                configuration=manifest.get('configuration', {}),
                cases_total=len(cases),scored_queries=baseline['global']['queries'],
                global_metrics=table,
                official_snapshot_champion_present=bool(baseline.get('neurona',{}).get('base_medida',{}).get('campeon')),
                neuron_applied={mode: bool(m.get('neurona',{}).get('actuo'))
                                for mode,m in (('baseline',baseline),('adapter',variant))},
                categories_equal=baseline['categorias']==variant['categorias'],
                all_global_fields_equal=baseline['global']==variant['global'],
                exact_output_order_scores_per_case_equal=not changed,
                changed_case_ids=changed,unexpected_adapter_states=errors,
                gate_exit_codes={mode:int((folder/(mode+'-exit.txt')).read_text()) for mode in traces},
                qa_input_snapshot_unchanged=(hashlib.sha256(
                    (cases_path.parent.parent/'snapshots/qa_escape_qcr_20260811.db').read_bytes()).hexdigest()
                    == manifest['snapshots/qa_escape_qcr_20260811.db']),
                official_snapshot_sha256=manifest['snapshots/qa_escape_qcr_20260811.db'],
                evaluator_sha256=manifest['scripts/evaluar_qa.py'],
                cases_sha256=manifest['scripts/casos_qa_baseline_v1.jsonl'],
                hashes={name:hashlib.sha256((folder/name).read_bytes()).hexdigest()
                        for name in ('baseline-trace.jsonl','selector-trace.jsonl')},
                baseline_failure_records=len((folder/'baseline-failed.jsonl').read_text().splitlines()),
                variant_failure_records=len((folder/'selector-failed.jsonl').read_text().splitlines()))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--results',type=Path,required=True)
    p.add_argument('--cases',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    report=compare(a.results,a.cases)
    a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if (not report['exact_output_order_scores_per_case_equal']
            or not report['categories_equal'] or not report['all_global_fields_equal']
            or not report['qa_input_snapshot_unchanged'] or report['unexpected_adapter_states']
            or any(report['gate_exit_codes'].values())):
        raise SystemExit(1)
