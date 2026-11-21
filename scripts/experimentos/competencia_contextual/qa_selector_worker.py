"""Ejecutar SOLO desde copia aislada mediante el orquestador del laboratorio.
Instrumenta por proceso; no edita evaluar_qa ni core. Ledger vacío intencional:
esta corrida mide no interferencia, no eficacia con correcciones aprobadas.
"""
import json
import os
from pathlib import Path
import runpy
import sqlite3
import sys

root = Path(os.environ['CONTEXT_QA_CODE']).resolve()
if not root.is_relative_to(Path('/tmp')) or (root/'.env.local').exists():
    raise RuntimeError('Requiere copia de código en /tmp sin configuración privada')
source = Path(os.environ['BIORAG_PATH']).resolve()
if not source.is_relative_to(root/'snapshots') or not source.is_file():
    raise RuntimeError('Requiere snapshot existente dentro de la copia aislada')
for name in ('BIORAG_QA_METRICS', 'BIORAG_QA_FAILED_CASES', 'BIORAG_QA_TEMP_DB', 'CONTEXT_QA_TRACE'):
    if not Path(os.environ[name]).resolve().is_relative_to(Path('/tmp')):
        raise RuntimeError('Todas las salidas QA deben quedar en /tmp')
sys.path.insert(0, str(root))
from core.memory_store import SQLiteMemoryBioRAG
from ledger import Ledger
from search_adapter import wrap_search

mode = os.environ['CONTEXT_QA_MODE']
log = open(os.environ['CONTEXT_QA_TRACE'], 'w')
db = sqlite3.connect(':memory:')
ledger = Ledger(db)
original = SQLiteMemoryBioRAG.buscar_por_frase


def instrumented(self, *args, **kwargs):
    def emit(event):
        event['query'] = args[0] if args else kwargs.get('frase', '')
        log.write(json.dumps(event, ensure_ascii=False, default=str)+'\n')
        log.flush()
    call = lambda *a, **kw: original(self, *a, **kw)
    if mode == 'selector':
        return wrap_search(call, ledger, lambda a, kw: None, emit, shadow=False)(*args, **kwargs)
    results, total = call(*args, **kwargs)
    rows = [(r[0], r[4]) for r in results]
    emit(dict(status='baseline', before=rows, after=rows))
    return results, total


SQLiteMemoryBioRAG.buscar_por_frase = instrumented
sys.argv = [str(root/'scripts/evaluar_qa.py')]
try:
    runpy.run_path(sys.argv[0], run_name='__main__')
finally:
    log.close()
    db.close()
