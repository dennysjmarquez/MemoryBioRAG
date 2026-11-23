"""Pruebas aisladas de funciones reales; NO reproduce la DB del incidente.
Ejecutar: python verificar_limites.py (requiere numpy).
Se extraen funciones por AST para evitar inicializar el motor o abrir una DB.
"""
import ast
import hashlib
import json
import math
from pathlib import Path
from types import SimpleNamespace
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
p = ROOT / 'core/memory/neurona.py'
source = p.read_text()
names = {'vista', 'reordenar', '_norm_nombre', '_es_su_nombre', 'g', '_base'}
tree = ast.parse(source)
selected = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
assert len(selected) == len(names)
ns = dict(np=np, math=math, _EPS=1e-4, _L1=math.log(9999),
          _PEND=1/(1e-4*(1-1e-4)), F_FORMULA=range(17), F_SIG=range(29),
          _cfg=lambda: {'topk': 5, 'topk_max': 10},
          activa=lambda: True, silencio=lambda _: False,
          _en_pausa=lambda *_: False, estado=lambda _: SimpleNamespace(campeon={}, margen=0),
          _margen_servir=lambda _: 0, _prior=lambda k, m: np.zeros(k),
          _permutar_mapas=lambda *args: None, _bien=lambda *args: None)
def fail(*args):
    raise AssertionError(args)
ns['_fallo'] = fail
exec(compile(ast.Module(body=selected, type_ignores=[]), str(p), 'exec'), ns)

def view(rows, k):
    return ns['vista'](rows, {}, {}, {}, {}, True, True, k=k)

rows = [(f'nodo_{i}', '', .5, 'activo', .9-i*.02, '') for i in range(15)]
rows[6] = ('version_actual_biorag', '', .5, 'activo', .78, '')
v = view(rows, 5)
assert len(v['nombres']) == 5
# El campeón simulado prefiere el último candidato visible con fuerza enorme.
ns['_correccion'] = lambda p, x: np.arange(len(x))*100.
out = ns['reordenar'](None, 'ultima version biorag', rows, v)
assert out[6][0] == 'version_actual_biorag'
assert 'version_actual_biorag' not in [r[0] for r in out[:5]]
print('PASS: candidato #7 no entra al top-5 reordenado (pool=15, k=5)')

rows2 = [('ultima_version_biorag', '', .05, 'activo', .9, ''),
         ('version_actual_biorag', '', .8, 'activo', .8, '')]
v2 = view(rows2, 5)
ns['_correccion'] = lambda p, x: np.array([-100., 100.])
out2 = ns['reordenar'](None, 'ultima version biorag', rows2, v2)
assert out2[0][0] == 'ultima_version_biorag'
print('PASS: identidad conserva #1 incluso con correccion opuesta del campeon')
control = ns['reordenar'](None, 'version vigente biorag', rows2, v2)
assert control[0][0] == 'version_actual_biorag'
print('PASS: control sin identidad permite cambiar el ganador con misma correccion')
assert ns['_es_su_nombre']('ultima version biorag', 'ultima_version_biorag')
print(json.dumps({'source': str(p.relative_to(ROOT)),
                  'sha256': hashlib.sha256(source.encode()).hexdigest(),
                  'scope': 'funciones reales; campeon y dependencias simulados; sin DB'}, ensure_ascii=False))
