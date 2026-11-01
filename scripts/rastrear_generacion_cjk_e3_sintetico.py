#!/usr/bin/env python3
"""Diagnóstico local E3 en base sintética: sin MCP, sin entrenar ni editar motor.

Una ejecución por proceso, con PYTHONHASHSEED=0 y BIORAG_NEURONA=0. El
observador no cambia el estado del motor y se coteja con una búsqueda sin
observador desde otra copia limpia. La salida no debe existir previamente.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import evaluar_qa_multilingue_e3a as qa


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--salida', type=Path, required=True)
    args = p.parse_args()
    if os.environ.get('PYTHONHASHSEED') != '0' or os.environ.get('BIORAG_NEURONA') != '0':
        p.error('Se requieren PYTHONHASHSEED=0 BIORAG_NEURONA=0 antes de iniciar Python')
    if os.environ.get('BIORAG_PATH'):
        p.error('BIORAG_PATH debe estar ausente')
    if args.salida.exists():
        p.error('La salida ya existe; no se sobrescribe')
    from core.memory import search
    from core.memory_store import SQLiteMemoryBioRAG

    # Anclas de instrucciones ejecutables en el motor medido. Abortar si
    # faltan o no son únicas, para no etiquetar otra fase como equivalente.
    lines = Path(search.__file__).read_text(encoding='utf-8').splitlines()
    anchors = {
        'fts': '    fts5_conceptos = [r[1] for r in todos if r[1]]',
        'despues_rescates': '    if resultados_concepto:',
        'final_generacion': '    raw_vals = [abs(v) for v in bm25_raw.values()]',
        'ranking_bruto': '    resultados_con_hibrido.sort(key=lambda r: r[4], reverse=True)',
        'antes_filtro': "    query_words = re.findall(r'\\w{3,}', query.lower())",
    }
    steps = {}
    for label, text in anchors.items():
        matches = [i + 1 for i, line in enumerate(lines) if line == text]
        if label == 'antes_filtro':
            matches = [i for i in matches if i > steps['ranking_bruto']]
        if len(matches) != 1:
            raise RuntimeError(f'Ancla ambigua o ausente: {label}, {matches}')
        steps[label] = matches[0]
    if list(steps.values()) != sorted(steps.values()):
        raise RuntimeError('Anclas fuera de orden')
    by_line = {number: label for label, number in steps.items()}
    casos = [c for c in qa.cargar_gold() if c['idioma'] in {'zh', 'ja'} and
             c['id'].split('-')[1] in {f'{i:02}' for i in range(6, 19)}]
    assert len(casos) == 26
    records = []
    with tempfile.TemporaryDirectory(prefix='biorag-cjk-audit-') as tmp:
        root = Path(tmp)
        original = root / 'fuente.db'
        with patch('time.time', return_value=qa.RELOJ_FIJO):
            base = qa.crear_base(original, qa.cargar_gold())
            for index, case in enumerate(casos):
                def run(observar):
                    copy = root / f'{index}_{int(observar)}.db'
                    shutil.copyfile(original, copy)
                    os.environ['BIORAG_DMN_ESTADO_PATH'] = str(root / f'dmn_{index}_{int(observar)}.json')
                    brain = SQLiteMemoryBioRAG(str(copy))
                    events = {}
                    def trace(frame, event, arg):
                        if event == 'line' and frame.f_code is search.buscar_por_frase.__code__:
                            if frame.f_lineno in by_line:
                                local = frame.f_locals
                                label = by_line[frame.f_lineno]
                                scoring = label in {'ranking_bruto', 'antes_filtro'}
                                pool = local['resultados_con_hibrido'] if scoring else local['todos']
                                names = [row[0 if scoring else 1] for row in pool]
                                origins = local['origen_scores']
                                events[label] = {
                                    'pool': len(names),
                                    'esperado_presente': case['concepto'] in names,
                                    'origen_esperado': origins.get(case['concepto'], (None,))[0],
                                    'tokens_fts': len(local['palabras']),
                                    'frase_fts': local['fts_match'],
                                    'expansion_necesaria': local['_necesita_expansion'],
                                }
                        return trace
                    try:
                        if observar:
                            sys.settrace(trace)
                        rows, total = brain.buscar_por_frase(case['query'], profundidad='activos', limite=5,
                                                            ignore_peso_sinaptico=True)
                    finally:
                        sys.settrace(None)
                        brain.cerrar_sistema()
                    return [(r[0], float(r[4])) for r in rows], total, events

                plain, total_plain, _ = run(False)
                traced, total_trace, events = run(True)
                if (plain, total_plain) != (traced, total_trace):
                    raise RuntimeError(f"El observador alteró la salida: {case['id']}")
                if set(events) != set(steps):
                    raise RuntimeError(f"Faltó un punto de observación: {case['id']}")
                names = [name for name, score in plain]
                records.append({'id': case['id'], 'esperado_en_top5': case['concepto'] in names,
                                'total_motor': total_plain, **events})
        if qa.sha256(original) != base['sha256_sqlite']:
            raise RuntimeError('La base sintética fuente cambió durante las búsquedas')
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    result = {'gold_sha256': qa.sha256(qa.GOLD), 'base': base,
              'observador_lineas': steps, 'comparaciones_sin_observador': len(records),
              'casos': records}
    with args.salida.open('x', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write('\n')
    for lang in ('zh', 'ja'):
        subset = [r for r in records if r['id'].startswith(lang)]
        print(lang, 'casos', len(subset), 'top5', sum(r['esperado_en_top5'] for r in subset))
        for label in steps:
            print(' ', label, 'esperado_presente', sum(r[label]['esperado_presente'] for r in subset),
                  'pool_vacio', sum(r[label]['pool'] == 0 for r in subset))
    print('comparaciones_sin_observador', len(records), 'diferencias', 0)
    print('evidencia_sha256', qa.sha256(args.salida))


if __name__ == '__main__':
    main()
