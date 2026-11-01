#!/usr/bin/env python3
"""Exploración MCP real, fixture E3 sintética; no mide una campaña ni un agente ciego.

Un caso por copia limpia; las consultas dentro de un caso comparten la copia.
Semillas por etiquetas de la pregunta, sin decidir consultas según el gold.
Los eventos completos se guardan en JSONL privado, no en la salida estándar.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import evaluar_qa_multilingue_e3a as qa
from scripts.evaluar_qa_intuicion_asociaciones_e1 import parse_tool_result

# Selección fija: ocho preguntas antes fallidas y cuatro controles negativos.
IDS = tuple(f'{lang}-{n}' for lang in ('zh', 'ja') for n in ('12', '15', '17', '18', 'n01', 'n02'))
LABELS = ROOT / 'scripts/casos_qa_multilingue_sustantivos_e3a.jsonl'


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidencia', type=Path, required=True)
    parser.add_argument('--resumen', type=Path, required=True)
    args = parser.parse_args()
    if os.environ.get('PYTHONHASHSEED') != '0' or os.environ.get('BIORAG_NEURONA') != '0' or os.environ.get('BIORAG_PATH'):
        parser.error('Iniciar con PYTHONHASHSEED=0, BIORAG_NEURONA=0 y BIORAG_PATH ausente')
    if args.evidencia.exists() or args.resumen.exists():
        parser.error('No se sobrescriben evidencias previas')
    labels = {r['id']: r['sustantivos_busqueda'] for r in map(json.loads, LABELS.read_text(encoding='utf-8').splitlines())}
    cases = {c['id']: c for c in qa.cargar_gold()}
    # Verificar que las semillas proceden de la pregunta, sin mirar la respuesta.
    plans = {}
    for case_id in IDS:
        terms = labels[case_id].split(',')
        if len(terms) < 2 or any(not t or t not in cases[case_id]['query'] for t in terms):
            raise RuntimeError(f'Semillas no válidas: {case_id}')
        plans[case_id] = terms

    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    args.evidencia.parent.mkdir(parents=True, exist_ok=True)
    args.resumen.parent.mkdir(parents=True, exist_ok=True)
    summaries = []
    with args.evidencia.open('x', encoding='utf-8') as evidence, tempfile.TemporaryDirectory(prefix='biorag-mcp-cjk-') as tmp:
        temp = Path(tmp)
        source = temp / 'fuente_sintetica.db'
        os.environ['BIORAG_DMN_ESTADO_PATH'] = str(temp / 'fuente_dmn.json')
        with patch('time.time', return_value=qa.RELOJ_FIJO):
            base = qa.crear_base(source, qa.cargar_gold())
        evidence.write(json.dumps({'event': 'base', 'base': base, 'gold_sha256': qa.sha256(qa.GOLD),
                                   'labels_sha256': qa.sha256(LABELS), 'plan': plans}, ensure_ascii=False) + '\n')
        evidence.flush()
        for case_id in IDS:
            db = temp / f'{case_id}.db'
            shutil.copyfile(source, db)
            env = {k: v for k, v in os.environ.items() if not k.startswith('BIORAG_')}
            env.update({'BIORAG_PATH': str(db), 'BIORAG_QA_TEMP_ROOT': str(temp),
                        'BIORAG_DMN_ESTADO_PATH': str(temp / f'{case_id}_dmn.json'),
                        'BIORAG_NEURONA': '0', 'BIORAG_NO_LOG': '1',
                        'BIORAG_AUTOGUARDADO_HEURISTICO': '0', 'BIORAG_MCP_AUTO_PARAFRASIS': '0',
                        'BIORAG_MCP_AUTO_DIMS': '0', 'BIORAG_QA_RELOJ_FIJO': str(qa.RELOJ_FIJO),
                        'PYTHONHASHSEED': '0'})
            params = StdioServerParameters(command=sys.executable,
                args=[str(ROOT / 'scripts/qa_stdio_server_intuicion.py')], env=env, cwd=str(ROOT))
            events = []
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as client:
                    await client.initialize()
                    async def search(query, reason):
                        arguments = {'query': query, 'sustantivos_clave': labels[case_id],
                                     'limite': 120, 'completo': True, 'asociados': True,
                                     'asociaciones_max': 0, 'context_window': 1, 'deep': False}
                        result = await client.call_tool('recordar', arguments=arguments)
                        raw, obj = parse_tool_result(result)
                        entry = {'id': case_id, 'motivo': reason, 'argumentos': arguments,
                                 'is_error': bool(result.isError), 'respuesta': obj, 'raw': raw}
                        evidence.write(json.dumps(entry, ensure_ascii=False) + '\n')
                        evidence.flush()
                        events.append(entry)
                        return obj
                    terms = plans[case_id]
                    # Descomposición explícita: acción/contexto expresados por
                    # sustantivos de la pregunta, no se envía la pregunta larga.
                    await search(' '.join(terms), 'semillas conjuntas de la pregunta')
                    for term in terms:
                        await search(term, 'aislar una semilla de la pregunta')
                    # Seguir una vez cada pista asociativa expuesta por las
                    # búsquedas de semillas, sin elegir usando el esperado.
                    links = set()
                    for item in list(events):
                        for row in item['respuesta'].get('resultados', []):
                            associations = row.get('asociaciones', {})
                            if isinstance(associations, dict):
                                if associations.get('truncada'):
                                    raise RuntimeError('Asociaciones truncadas pese a pedir lista completa')
                                links.update(v for v in associations.get('items', []) if isinstance(v, str) and v)
                    for link in sorted(links):
                        await search(link, 'seguir asociación expuesta por una semilla')
            # Gold se usa solo después de terminar la trayectoria; no decide búsquedas.
            expected = cases[case_id]['concepto']
            valid = [e for e in events if not e['is_error'] and e['respuesta'].get('status') != 'error']
            errors = len(events) - len(valid)
            seen = {row.get('concepto') for e in valid for row in e['respuesta'].get('resultados', [])}
            pages_incomplete = any((e['respuesta'].get('paginas_totales') or 0) > 1 for e in valid)
            summaries.append({'id': case_id, 'tipo': cases[case_id]['tipo'], 'consultas': len(events), 'errores': errors,
                              'resultados_en_alguna_consulta': bool(seen) if valid else None,
                              'esperado_visto': (expected in seen) if expected and valid else None,
                              'asociaciones_seguidas': len(links), 'paginas_incompletas': pages_incomplete})
        if qa.sha256(source) != base['sha256_sqlite']:
            raise RuntimeError('La fuente sintética se modificó')
    result = {'base': base, 'gold_sha256': qa.sha256(qa.GOLD), 'labels_sha256': qa.sha256(LABELS),
              'evidencia_sha256': qa.sha256(args.evidencia), 'casos': summaries}
    with args.resumen.open('x', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write('\n')
    print('casos', len(summaries), 'llamadas', sum(x['consultas'] for x in summaries),
          'errores', sum(x['errores'] for x in summaries),
          'positivos_con_esperado', sum(x['esperado_visto'] is True for x in summaries),
          'negativos_con_resultados', sum(x['tipo'] == 'negativo' and x['resultados_en_alguna_consulta'] is True for x in summaries),
          'asociaciones_seguidas', sum(x['asociaciones_seguidas'] for x in summaries),
          'casos_paginas_incompletas', sum(x['paginas_incompletas'] for x in summaries))
    print('evidencia_sha256', qa.sha256(args.evidencia), 'resumen_sha256', qa.sha256(args.resumen))


if __name__ == '__main__':
    asyncio.run(main())
