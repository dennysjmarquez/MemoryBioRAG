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

    # La traza se amarra a dos instrucciones concretas; si el código cambia,
    # se rechaza el experimento en vez de atribuir resultados a otra fase.
    lines = Path(search.__file__).read_text(encoding='utf-8').splitlines()
    before = [i + 1 for i, s in enumerate(lines) if "query_words = re.findall(r'\\w{3,}', query.lower())" in s][-1]
    after = next(i + 1 for i, s in enumerate(lines) if 'v30.1: GUARDIA DE ORDEN MONOTÓNICO' in s)
    # En Python 3.11 la traza de la condición multilínea comienza en el
    # primer operando, no en el `if (` sin bytecode propio.
    after = next(i + 1 for i in range(after, len(lines))
                 if 'ordenar_por == "relevancia"' in lines[i] and not lines[i].lstrip().startswith('#'))
    assert before < after
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
                            if frame.f_lineno in (before, after):
                                local = frame.f_locals
                                pool = local['resultados_con_hibrido']
                                names = [row[0] for row in pool]
                                origins = local['origen_scores']
                                events['antes' if frame.f_lineno == before else 'despues'] = {
                                    'pool': len(names),
                                    'esperado_presente': case['concepto'] in names,
                                    'origen_esperado': origins.get(case['concepto'], (None,))[0],
                                    'cantidad_tokens_filtro': len(re.findall(r'\w{3,}', local['query'].lower())),
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
                if set(events) != {'antes', 'despues'}:
                    raise RuntimeError(f"Faltó un punto de observación: {case['id']}")
                names = [name for name, score in plain]
                records.append({'id': case['id'], 'esperado_en_top5': case['concepto'] in names,
                                'total_motor': total_plain, **events})
        if qa.sha256(original) != base['sha256_sqlite']:
            raise RuntimeError('La base sintética fuente cambió durante las búsquedas')
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    result = {'gold_sha256': qa.sha256(qa.GOLD), 'base': base,
              'observador_lineas': [before, after], 'comparaciones_sin_observador': len(records),
              'casos': records}
    with args.salida.open('x', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write('\n')
    for lang in ('zh', 'ja'):
        subset = [r for r in records if r['id'].startswith(lang)]
        print(lang, 'casos', len(subset), 'top5', sum(r['esperado_en_top5'] for r in subset),
              'antes', sum(r['antes']['esperado_presente'] for r in subset),
              'despues', sum(r['despues']['esperado_presente'] for r in subset),
              'eliminados_filtro', sum(r['antes']['esperado_presente'] and not r['despues']['esperado_presente'] for r in subset))
    print('comparaciones_sin_observador', len(records), 'diferencias', 0)
    print('evidencia_sha256', qa.sha256(args.salida))


if __name__ == '__main__':
    main()
