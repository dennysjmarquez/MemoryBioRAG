#!/usr/bin/env python3
"""Sonda FTS crudo CJK en base E3 sintética; NO cambia ni simula el motor.

La alternativa OR de trigramas es una pregunta al índice, no una propuesta de
segmentador ni una evaluación de agente. Incluye los cuatro negativos locales.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import evaluar_qa_multilingue_e3a as qa


def clean_query(query: str) -> str:
    # En estos casos sin espacios se comprueba explícitamente que este
    # preprocesamiento coincide con los fts_match de la traza del motor.
    return re.sub(r'[^\w\s_-]', ' ', query.lower()).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--traza', type=Path, required=True)
    parser.add_argument('--salida', type=Path, required=True)
    args = parser.parse_args()
    if os.environ.get('PYTHONHASHSEED') != '0' or os.environ.get('BIORAG_NEURONA') != '0' or os.environ.get('BIORAG_PATH'):
        parser.error('Se requieren PYTHONHASHSEED=0, BIORAG_NEURONA=0 y BIORAG_PATH ausente')
    if args.salida.exists():
        parser.error('La salida ya existe')
    traced = json.loads(args.traza.read_text(encoding='utf-8'))
    if traced['gold_sha256'] != qa.sha256(qa.GOLD):
        raise RuntimeError('El gold no coincide con la traza')
    trace_by_id = {r['id']: r for r in traced['casos']}
    casos = [c for c in qa.cargar_gold() if c['idioma'] in {'zh', 'ja'} and
             (c['id'].split('-')[1] in {f'{i:02}' for i in range(6, 19)} or c['tipo'] == 'negativo')]
    if len(casos) != 30 or len(trace_by_id) != 26:
        raise RuntimeError('Selección o traza incompleta')
    from core.memory_store import SQLiteMemoryBioRAG
    records = []
    with tempfile.TemporaryDirectory(prefix='biorag-cjk-fts-') as tmp:
        root = Path(tmp)
        db = root / 'sintetica.db'
        os.environ['BIORAG_DMN_ESTADO_PATH'] = str(root / 'dmn.json')
        with patch('time.time', return_value=qa.RELOJ_FIJO):
            base = qa.crear_base(db, qa.cargar_gold())
            brain = SQLiteMemoryBioRAG(str(db))
            try:
                def lookup(expr):
                    # Sin ranking ni limite: inspecta todos los candidatos del índice.
                    return {r[0] for r in brain.conn.execute(
                        'SELECT l.concepto FROM largo_plazo_fts f '
                        'JOIN largo_plazo l ON l.rowid=f.rowid '
                        "WHERE largo_plazo_fts MATCH ? AND l.estado='activo'", (expr,))}
                for case in casos:
                    cleaned = clean_query(case['query'])
                    if len(cleaned.split()) != 1 or len(cleaned) < 3:
                        raise RuntimeError(f"Caso no previsto: {case['id']}")
                    if case['id'] in trace_by_id and cleaned != trace_by_id[case['id']]['fts']['frase_fts']:
                        raise RuntimeError(f"La expresión FTS real difiere: {case['id']}")
                    # Secuencias de longitud 3 de la consulta, sin mirar gold ni
                    # contenido esperado y sin eliminar términos. Sin límite top-K.
                    chunks = sorted(set(cleaned[i:i+3] for i in range(len(cleaned)-2)))
                    if any('"' in c for c in chunks):
                        raise RuntimeError('Comillas inesperadas')
                    expr = ' OR '.join('"' + c + '"' for c in chunks)
                    literal = lookup(cleaned)
                    or_hits = lookup(expr)
                    gold = case['concepto']
                    expected_literal = gold in literal if gold else None
                    if gold and expected_literal != trace_by_id[case['id']]['fts']['esperado_presente']:
                        raise RuntimeError(f"FTS crudo difiere de la traza: {case['id']}")
                    records.append({'id': case['id'], 'tipo': case['tipo'], 'fts_original_count': len(literal),
                                    'fts_original_esperado': expected_literal, 'trigramas_count': len(chunks),
                                    'fts_or_count': len(or_hits), 'fts_or_esperado': gold in or_hits if gold else None})
            finally:
                brain.cerrar_sistema()
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    result = {'gold_sha256': qa.sha256(qa.GOLD), 'traza_sha256': qa.sha256(args.traza),
              'base': base, 'casos': records}
    with args.salida.open('x', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write('\n')
    for lang in ('zh', 'ja'):
        failures = [r for r in records if r['id'].startswith(lang) and r['id'].split('-')[1] in {f'{i:02}' for i in range(11,19)}]
        negatives = [r for r in records if r['id'].startswith(lang) and r['tipo'] == 'negativo']
        print(lang, 'fallos', len(failures), 'fts_original', sum(r['fts_original_esperado'] for r in failures),
              'fts_or', sum(r['fts_or_esperado'] for r in failures),
              'negativos_or_con_candidatos', sum(r['fts_or_count'] > 0 for r in negatives), '/', len(negatives))
    print('evidencia_sha256', qa.sha256(args.salida))


if __name__ == '__main__':
    main()
