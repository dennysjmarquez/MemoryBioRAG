#!/usr/bin/env python3
"""Audita propuesta CJK del operador en una misma fuente sintética, sin editar motor.

Requiere que el commit del operador esté disponible localmente mediante fetch.
Cada brazo corre en otro proceso y en una copia Git aislada; cada consulta usa
una copia limpia de la misma DB temporal. No usa bases de usuario ni entrena.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
OPERATOR = '193f2226f5aef19f602d6cd8a2455c9b6dc55c89'
PATCHES = {
    'or': 'docs/e3_cjk_trigram_propuesta_NO_APLICAR_20261101.patch',
    'umbral2': 'docs/e3_cjk_trigram_umbral2_DIAGNOSTICO_NO_APLICAR_20261101.patch',
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def worker(args):
    sys.path.insert(0, str(ROOT))
    from scripts import evaluar_qa_multilingue_e3a as qa
    cases = qa.cargar_gold()
    if args.worker == 'crear':
        with patch('time.time', return_value=qa.RELOJ_FIJO):
            base = qa.crear_base(args.source, cases)
        args.result.write_text(json.dumps(base, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        return
    expected_sha = args.expected_sha
    if qa.sha256(args.source) != expected_sha:
        raise RuntimeError('La fuente del brazo no coincide con la original')
    results = []
    with tempfile.TemporaryDirectory(prefix='busquedas_', dir=args.temp) as folder:
        work = Path(folder)
        with patch('time.time', return_value=qa.RELOJ_FIJO):
            for i, case in enumerate(cases):
                os.environ['BIORAG_DMN_ESTADO_PATH'] = str(work / f'dmn_{i}.json')
                results.append(qa.buscar_caso(args.source, case, work))
    if qa.sha256(args.source) != expected_sha:
        raise RuntimeError('La fuente cambió durante la búsqueda')
    results.sort(key=lambda x: x['id'])
    result = {'source_sha256': expected_sha, 'gold_sha256': qa.sha256(qa.GOLD),
              'metricas': qa.metricas(results), 'casos': results}
    args.result.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--salida', type=Path)
    parser.add_argument('--worker', choices=('crear', 'buscar'))
    parser.add_argument('--source', type=Path)
    parser.add_argument('--result', type=Path)
    parser.add_argument('--temp', type=Path)
    parser.add_argument('--expected-sha')
    args = parser.parse_args()
    if args.worker:
        worker(args)
        return
    if not args.salida or args.salida.exists():
        parser.error('Seleccione un directorio de salida nuevo')
    # La copia Git, no el working tree, es la que se usa como referencia.
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    base_search = subprocess.check_output(['git', 'show', f'{head}:core/memory/search.py'], cwd=ROOT)
    operator_search = subprocess.check_output(['git', 'show', f'{OPERATOR}:core/memory/search.py'], cwd=ROOT)
    if base_search != operator_search:
        raise RuntimeError('El motor de HEAD y el motor del operador difieren; suspender comparación')
    gold = subprocess.check_output(['git', 'show', f'{head}:scripts/casos_qa_multilingue_e3a.jsonl'], cwd=ROOT)
    operator_gold = subprocess.check_output(['git', 'show', f'{OPERATOR}:scripts/casos_qa_multilingue_e3a.jsonl'], cwd=ROOT)
    if gold != operator_gold:
        raise RuntimeError('Gold de operador y auditor no coinciden')
    args.salida.mkdir(parents=True)
    out = args.salida.resolve()
    with tempfile.TemporaryDirectory(prefix='biorag-cjk-pareado-') as tmp:
        temp = Path(tmp)
        apps = {}
        for name in ('baseline', 'or', 'umbral2'):
            app = temp / name
            app.mkdir()
            archive = subprocess.check_output(['git', 'archive', head, 'core', 'middleware', 'config',
                'scripts/evaluar_qa_multilingue_e3a.py', 'scripts/casos_qa_multilingue_e3a.jsonl', 'biorag.py'], cwd=ROOT)
            tar_path = temp / f'{name}.tar'
            tar_path.write_bytes(archive)
            # git archive trusted repository commit; extraction destination is temp only.
            subprocess.run(['tar', '-xf', str(tar_path), '-C', str(app)], check=True)
            worker_file = app / 'scripts' / 'auditar_cjk_pareado_sintetico.py'
            worker_file.write_bytes(Path(__file__).read_bytes())
            if name in PATCHES:
                patch_data = subprocess.check_output(['git', 'show', f'{OPERATOR}:{PATCHES[name]}'], cwd=ROOT)
                patch_file = temp / f'{name}.patch'
                patch_file.write_bytes(patch_data)
                subprocess.run(['patch', '--batch', '--forward', '-p1', '-i', str(patch_file)], cwd=app, check=True)
            apps[name] = app
        source = temp / 'sintetica.db'
        env = {'PATH': os.environ.get('PATH', ''), 'HOME': str(temp), 'PYTHONHASHSEED': '0',
               'BIORAG_NEURONA': '0', 'BIORAG_NO_LOG': '1',
               'NLTK_DATA': str(ROOT / 'MemoryBioRAG_Data/nltk_data')}
        def call(app, action, result, expected=None):
            env_child = {**env, 'PYTHONPATH': str(app),
                         'BIORAG_DMN_ESTADO_PATH': str(temp / f'dmn_{app.name}_{action}.json')}
            cmd = [sys.executable, str(app / 'scripts/auditar_cjk_pareado_sintetico.py'),
                   '--worker', action, '--source', str(source), '--result', str(result), '--temp', str(temp)]
            if expected:
                cmd += ['--expected-sha', expected]
            subprocess.run(cmd, cwd=app, env=env_child, check=True)
        call(apps['baseline'], 'crear', out / 'base.json')
        source_sha = sha(source)
        base_meta = json.loads((out / 'base.json').read_text(encoding='utf-8'))
        if source_sha != base_meta['sha256_sqlite']:
            raise RuntimeError('La huella de la fuente no coincide tras crearla')
        for name, app in apps.items():
            call(app, 'buscar', out / f'{name}.json', source_sha)
        if sha(source) != source_sha:
            raise RuntimeError('La fuente sintética cambió')
        arms = {name: json.loads((out / f'{name}.json').read_text(encoding='utf-8')) for name in apps}
        baseline = {r['id']: r for r in arms['baseline']['casos']}
        summary = {'operator_commit': OPERATOR, 'audit_commit': head, 'source_sha256': source_sha,
                   'gold_sha256': arms['baseline']['gold_sha256'], 'motor_sha256': hashlib.sha256(base_search).hexdigest(),
                   'patches_sha256': {name: sha(temp / f'{name}.patch') for name in PATCHES},
                   'arms': {name: arm['metricas']['por_idioma'] for name, arm in arms.items()}, 'comparison': {}}
        for name in PATCHES:
            better, worse, lost_results, new_fp = [], [], [], []
            for case in arms[name]['casos']:
                prev = baseline[case['id']]
                if case['esperado'] is not None:
                    rank0, rank1 = prev['rango'] or 999, case['rango'] or 999
                    if rank1 < rank0: better.append(case['id'])
                    if rank1 > rank0: worse.append(case['id'])
                if case['falso_positivo'] and not prev['falso_positivo']:
                    new_fp.append(case['id'])
                missing = sorted({r['concepto'] for r in prev['resultados']} - {r['concepto'] for r in case['resultados']})
                if missing:
                    lost_results.append({'id': case['id'], 'count': len(missing)})
            summary['comparison'][name] = {'better_ranks': better, 'worse_ranks': worse,
                                            'new_fp': new_fp, 'old_top5_not_returned': lost_results}
        (out / 'resumen.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    for name, comparison in summary['comparison'].items():
        print(name, 'mejores', len(comparison['better_ranks']), 'peores', len(comparison['worse_ranks']),
              'fp_nuevos', comparison['new_fp'], 'casos_con_salidas_antes_presentes', len(comparison['old_top5_not_returned']))
    print('source_sha256', source_sha, 'resumen_sha256', sha(out / 'resumen.json'))


if __name__ == '__main__':
    main()
