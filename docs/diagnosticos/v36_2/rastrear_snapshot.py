"""Diagnóstico, sin fixes: trabaja EXCLUSIVAMENTE en una copia del snapshot.
Uso (desde código aislado): python rastrear_snapshot.py SNAPSHOT WORKDIR [variante]
Variantes: baseline, sin_neurona, sin_identidad, sin_bono_exacto,
 dormido, dormido_profundo. Campeón REAL del snapshot; no entrena.
No publica contenido de recuerdos. Requiere dependencias del proyecto.
"""
import hashlib
import inspect
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys

src, dest = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
variant = sys.argv[3] if len(sys.argv) > 3 else 'baseline'
assert src.is_file() and not dest.exists(), 'WORKDIR debe ser nuevo'
dest.mkdir(parents=True)
assert src != dest / 'trabajo.db'
shutil.copyfile(src, dest / 'trabajo.db')
os.environ['BIORAG_PATH'] = str(dest / 'trabajo.db')
os.environ['BIORAG_NLTK_AUTO_DOWNLOAD'] = '0'
os.environ['BIORAG_UPDATE_CHECK'] = '0'
os.environ['BIORAG_DMN_SINTESIS_ACTIVA'] = '0'
from core.memory_store import SQLiteMemoryBioRAG
from core.memory import neurona
from core.mcp_server import search as mcp
import numpy as np

b = SQLiteMemoryBioRAG(str(dest / 'trabajo.db'))
b._persistente = True  # MCP usa una instancia persistente entre llamadas.
mcp._get_cerebro = lambda: b
tracked = ('ultima_version_biorag', 'version_actual_biorag', 'version_actual_biorag_v32_4_20261007')
if variant.startswith('dormido'):
    b.cursor.execute("UPDATE largo_plazo SET estado='dormido',peso_sinaptico=0.05 WHERE concepto=?", (tracked[0],))
    b.conn.commit()

def state():
    return b.cursor.execute('SELECT concepto,estado,peso_sinaptico,ultimo_acceso FROM largo_plazo WHERE concepto IN (?,?,?)', tracked).fetchall()
def rows(rs):
    return [{'concepto': r[0], 'peso': r[2], 'estado': r[3], 'score': r[4]} for r in rs]

est = neurona.estado(b)
report = dict(variant=variant, source_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),
              fingerprint=neurona.huella_motor(b), champion=est.campeon is not None,
              margin=est.margen, before=state(), scoring=[], neuronal=[])
original_scoring = b._calcular_score_hibrido

def scoring(**kw):
    caller = inspect.currentframe().f_back
    name = caller.f_locals.get('concepto')
    actual = dict(kw)
    if variant == 'sin_bono_exacto':
        actual['match_exacto'] = False
    score = original_scoring(**actual)
    if name in tracked:
        noexact = dict(kw, match_exacto=False)
        report['scoring'].append(dict(concepto=name, inputs=kw, score=score,
                                      score_without_exact=original_scoring(**noexact)))
    return score
b._calcular_score_hibrido = scoring
original_rerank = neurona.reordenar
if variant == 'sin_identidad':
    neurona._es_su_nombre = lambda *_: False
if variant == 'sin_neurona':
    os.environ['BIORAG_NEURONA'] = '0'

def rerank(self, frase, page, view):
    entry = dict(query=frase, before=rows(page), visible=None)
    if view is not None:
        corr = neurona._correccion(est.campeon, view['X'].astype(float))
        keys = view['base'].astype(float) + corr + neurona._prior(len(corr), neurona._margen_servir(est))
        entry['visible'] = [dict(concepto=n, base=float(bs), correction=float(c), key=float(k))
                            for n,bs,c,k in zip(view['nombres'],view['base'],corr,keys)]
        entry['identity'] = neurona._es_su_nombre(frase, page[0][0])
    out = original_rerank(self, frase, page, view)
    entry['after'] = rows(out)
    report['neuronal'].append(entry)
    return out
neurona.reordenar = rerank

calls = 2 if variant.startswith('dormido') else 1
report['calls'] = []
for i in range(calls):
    raw = mcp._recordar_impl(query='ultima version biorag',
             sustantivos_clave='ultima,version,biorag',
             parafrasis='cual es la ultima version de biorag,ultimo release publicado',
             limite=5, asociados=True, deep=(variant == 'dormido_profundo'))
    start = raw.rfind('\n\n{')
    response = json.loads(raw[start + 2:] if start >= 0 else raw)
    # Solo conservar campos diagnósticos, nunca contenidos personales.
    candidates = response.get('resultados', [])
    report['calls'].append(dict(status=response.get('status'),
        results=[{k:v for k,v in r.items() if k in ('concepto','peso_sinaptico','estado','score_hibrido')}
                 for r in candidates], state=state(), response_keys=list(response)))
report['after'] = state()
report['source_unchanged'] = hashlib.sha256(src.read_bytes()).hexdigest() == report['source_sha256']
(dest / 'trace.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str))
print(json.dumps({k:report[k] for k in ('variant','fingerprint','champion','margin','calls','source_unchanged')}, ensure_ascii=False))
b.conn.close()
