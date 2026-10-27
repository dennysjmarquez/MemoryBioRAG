#!/usr/bin/env python3
"""Compara cuatro parejas E2e sobre métricas y fallos del arnés oficial.

La fórmula experimental solo se acepta si todas las parejas son comparables,
ninguna categoría empeora en R@5 honesta, R@1 honesta global no baja, ambos
lados mantienen FP 0/40 y el pytest aislado del candidato está verde.
El pytest se comprueba por separado; este programa solo evalúa las métricas.
"""
from decimal import Decimal
from pathlib import Path
import argparse
import json
import sys

ap = argparse.ArgumentParser()
ap.add_argument('--docs', type=Path, default=Path('docs'))
ap.add_argument('--veredicto', type=Path, default=None)
ap.add_argument('--escenario', action='append',
                choices=('snapshot:normal', 'snapshot:ruido', 'viva:normal', 'viva:ruido'),
                help='Comparar solo este escenario; repetible. Sin este argumento se comparan los cuatro.')
args = ap.parse_args()


def read(path):
    with path.open(encoding='utf-8') as f:
        return json.load(f)


def marks(d):
    fields = ('id', 'esperado', 'obsoleta', 'n_reclamantes', 'apartado_r5', 'apartado_r1')
    return sorted(tuple(x[k] for k in fields) for x in d['qa_honesta']['casos_apartados'])


def hit_count(total, percent):
    return int((Decimal(total) * Decimal(str(percent)) / Decimal(100)).to_integral_value())


def failures(path, metrics):
    cat = set(metrics['qa_honesta']['categorias'])
    excluded = {str(x['id']) for x in metrics['qa_honesta']['casos_apartados'] if x['apartado_r5']}
    rows = []
    with path.open(encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            x = json.loads(line)
            if x.get('categoria') in cat and str(x.get('id')) not in excluded:
                rows.append((str(x['id']), x['categoria']))
    if len(rows) != len(set(rows)):
        raise ValueError(f'{path}: IDs repetidos entre fallos honestos')
    if len(rows) != metrics['qa_honesta']['global_r5']['fallos']:
        raise ValueError(f'{path}: {len(rows)} fallos honestos, JSON indica {metrics["qa_honesta"]["global_r5"]["fallos"]}')
    return set(rows)


problems = []
summary = {}
for db in ('snapshot', 'viva'):
    for mode in ('normal', 'ruido'):
        if args.escenario and f'{db}:{mode}' not in args.escenario:
            continue
        scenario = f'{db} {mode}'
        stem0 = f'e2e_base_{db}_{mode}'
        stem1 = f'e2e_candidato_{db}_{mode}'
        old = read(args.docs / f'{stem0}_20261027.json')
        new = read(args.docs / f'{stem1}_20261027.json')
        print(f'\n=== {scenario} ===')
        if old['casos_total'] != 921 or new['casos_total'] != 921 or old['casos_file'] != new['casos_file']:
            problems.append(f'{scenario}: examen distinto o incompleto')
        oh, nh = old['qa_honesta'], new['qa_honesta']
        fixed = ('sinonimo_total', 'obsoletas', 'ambiguas', 'con_las_dos_marcas', 'apartados_r5', 'apartados_r1')
        if any(oh[k] != nh[k] for k in fixed) or marks(old) != marks(new):
            problems.append(f'{scenario}: clasificación honesta distinta; no comparable')
        expected_noise = 'zzqx' if mode == 'ruido' else None
        for name, run in (('antes', old), ('candidato', new)):
            if run['neurona']['activa']:
                problems.append(f'{scenario} {name}: neurona activa')
            if run['e2b']['ruido'] != expected_noise:
                problems.append(f'{scenario} {name}: ruido no corresponde')
            if (run['e2b']['censo_tematico'] is not None) != (mode == 'ruido'):
                problems.append(f'{scenario} {name}: censo no corresponde')
            g = run['global']
            if (g['negativos_fp'], g['negativos_total'], g['negativos_contaminados']) != (0, 40, 0):
                problems.append(f'{scenario} {name}: FP no es 0/40 con 40 controles válidos')
        print(f"FP antes/candidato: {old['global']['negativos_fp']}/{old['global']['negativos_total']} → {new['global']['negativos_fp']}/{new['global']['negativos_total']}; contaminados {old['global']['negativos_contaminados']} → {new['global']['negativos_contaminados']}")
        for kind in ('global_r5', 'global_r1'):
            if oh[kind]['queries'] != nh[kind]['queries']:
                problems.append(f'{scenario}: denominador honesto {kind} cambió')
        print('R@5 honesta global: %.2f%% → %.2f%%; fallos %s → %s; n=%s' % (
            oh['global_r5']['recall_at_5'], nh['global_r5']['recall_at_5'], oh['global_r5']['fallos'], nh['global_r5']['fallos'], oh['global_r5']['queries']))
        print('R@1 honesta global: %.2f%% → %.2f%%; no top-1 %s → %s; n=%s' % (
            oh['global_r1']['recall_at_1'], nh['global_r1']['recall_at_1'], oh['global_r1']['no_top1'], nh['global_r1']['no_top1'], oh['global_r1']['queries']))
        if nh['global_r1']['no_top1'] > oh['global_r1']['no_top1']:
            problems.append(f'{scenario}: baja R@1 honesta global')
        oc, nc = oh['categorias'], nh['categorias']
        if set(oc) != set(nc):
            problems.append(f'{scenario}: categorías distintas')
        print('Categoría                 R@5 honesta antes → candidato (aciertos / total)')
        cat_summary = {}
        for cat in sorted(set(oc) & set(nc)):
            b, c = oc[cat]['r5'], nc[cat]['r5']
            if b['total'] != c['total'] or b['apartados'] != c['apartados']:
                problems.append(f'{scenario}: denominador R@5 de {cat} cambió')
            hb, hc = hit_count(b['total'], b['recall_at_5']), hit_count(c['total'], c['recall_at_5'])
            if hc < hb:
                problems.append(f'{scenario}: baja R@5 honesta {cat} ({hb}→{hc}/{b["total"]})')
            print('%-24s %6.2f%% → %6.2f%% (%3d → %3d / %3d)%s' % (
                cat, b['recall_at_5'], c['recall_at_5'], hb, hc, b['total'], ' BAJA' if hc < hb else ''))
            cat_summary[cat] = {'total': b['total'], 'aciertos_antes': hb, 'aciertos_candidato': hc,
                                'r5_antes': b['recall_at_5'], 'r5_candidato': c['recall_at_5']}
        f0 = failures(args.docs / f'{stem0}_fallos_20261027.jsonl', old)
        f1 = failures(args.docs / f'{stem1}_fallos_20261027.jsonl', new)
        added = sorted(f1 - f0)
        recovered = sorted(f0 - f1)
        print(f'Fallos honestos nuevos ({len(added)}): {added}')
        print(f'Fallos honestos recuperados ({len(recovered)}): {recovered}')
        summary[scenario] = {
            'r5_antes': oh['global_r5'], 'r5_candidato': nh['global_r5'],
            'r1_antes': oh['global_r1'], 'r1_candidato': nh['global_r1'],
            'fp_antes': [old['global']['negativos_fp'], old['global']['negativos_total']],
            'fp_candidato': [new['global']['negativos_fp'], new['global']['negativos_total']],
            'categorias_r5': cat_summary, 'fallos_nuevos': added, 'fallos_recuperados': recovered,
        }
print('\n=== COMPARACIÓN DE MÉTRICAS (pytest se valida aparte) ===')
if len(summary) != 4:
    print(f'PARCIAL: {len(summary)}/4 parejas; NO constituye el veredicto final.')
print('NO CUMPLE' if problems else 'CUMPLE MÉTRICAS MEDIDAS')
for problem in problems:
    print('-', problem)
if args.veredicto:
    args.veredicto.write_text(json.dumps({'comparacion_completa': len(summary) == 4,
                                         'metricas_cumplen': not problems, 'motivos': problems,
                                         'escenarios': summary}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
sys.exit(1 if problems else 0)
