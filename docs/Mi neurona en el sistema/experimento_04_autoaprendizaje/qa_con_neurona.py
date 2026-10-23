"""Paso 4 del experimento 04: la neurona dentro del MOTOR REAL, de punta a punta.

Corre el `scripts/evaluar_qa.py` OFICIAL (sin modificarlo) pero, en memoria,
envuelve `_calcular_score_hibrido` para sumar la corrección aprendida a cada
candidato. Todo lo demás del motor (fallbacks, QCR, hub, GABA, convergencia,
abstención, negativos) corre igual que siempre. Así se ve si lo que ganó la
neurona en el ranking "crudo" sobrevive al post-proceso y si los umbrales
absolutos (GABA .80, abstención .6212, léxico .88…) siguen sanos.

Escala: score_nuevo = g⁻¹(g(s) + corrección), con g de `escala.py` (logit para
s < 1 y recta empinada por encima: los matches exactos siguen dominando como hoy).
Pesos viejos sin escala "g": sigmoid(logit(s)+c) para s < 1 y s + desempate mínimo
para s >= 1.

Uso (desde la raíz del repo):
    BIORAG_PATH=snapshots/qa_escape_qcr_20260811.db PYTHONHASHSEED=1 \
        python ".../qa_con_neurona.py" [--pesos resultados/pesos/A_R2_semilla7.npz] --etiqueta X

Sin --pesos corre los pesos base (la referencia, en el mismo arnés).
El snapshot no se toca: evaluar_qa trabaja sobre su copia temporal de siempre.
Las métricas se escriben en resultados/qa_motor_<etiqueta>.json (no en scripts/).
"""
import argparse
import math
import os
import sys
from pathlib import Path

import numpy as np

AQUI = Path(__file__).resolve().parent
REPO = AQUI.parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(AQUI.parent / "experimento_01_pesos_aprendidos"))

ap = argparse.ArgumentParser()
ap.add_argument("--pesos", default=None)
ap.add_argument("--etiqueta", required=True)
ap.add_argument("--modo", choices=["top5", "orden", "escala"], default="top5",
                help="top5 = la neurona solo reordena la lista FINAL que entrega el motor (R@5 idéntico por construcción); "
                     "orden = reordena todo el pool antes del post-proceso, scores de hoy reasignados; "
                     "escala = la corrección se suma al score (cambia la escala: lo que falló en la 1.ª prueba)")
args, resto = ap.parse_known_args()
sys.argv = [sys.argv[0]] + resto

os.environ["BIORAG_QA_METRICS"] = str(AQUI / "resultados" / f"qa_motor_{args.etiqueta}.json")
os.environ["BIORAG_QA_FAILED_CASES"] = str(AQUI / "resultados" / f"qa_motor_{args.etiqueta}_fallidos.jsonl")
os.environ.setdefault("BIORAG_QA_GATE", "1")

from core.memory import scoring  # noqa: E402
from core.memory_store import SQLiteMemoryBioRAG  # noqa: E402
import entrenar_neurona as en  # noqa: E402  (feats() idéntico al del entrenamiento)
import escala  # noqa: E402

P = None
if args.pesos:
    z = np.load(args.pesos)
    assert list(z["F_SIG"]) == list(en.F_SIG), "las agujas no coinciden con las del entrenamiento"
    P = {k: z[k] for k in z.files if k not in ("tipo", "F_SIG", "escala")}
    TIPO = str(z["tipo"])
    ESCALA = str(z["escala"]) if "escala" in z.files else "logit"
    print(f"[neurona] {TIPO} desde {args.pesos}", flush=True)
else:
    print("[neurona] sin pesos: referencia con los pesos base", flush=True)

DEFAULTS = dict(bm25_norm=0.0, dim_score=0.0, concepto_ratio=0.0, sinonimos_ratio=0.0,
                score_latente=0.0, score_cadena=0.0, grupo_score=0.0, tematico_score=0.0,
                asoc_count=0, pred_score=0.0, ppmi_score=0.0, hub_match=0.0, ncd_score=0.0,
                episodio_score=0.0, campo_score=0.0, jsd_score=0.0, match_exacto=False)


def correccion(kw):
    k = dict(DEFAULTS)
    k.update(kw)
    x = np.array(en.feats(k), dtype=float)
    if TIPO == "R1":
        return float(x @ P["w"])
    return float(np.tanh(P["W"] @ x + P["b"]) @ P["v"])


def _con_neurona(self, **kw):
    s = scoring._calcular_score_hibrido(self, **kw)
    if P is None:
        return s
    c = correccion(kw)
    if args.modo in ("orden", "top5"):
        # solo anota la corrección de ESTE nodo; el score que ve el motor no cambia
        concepto = sys._getframe(1).f_locals.get("concepto")
        if concepto is not None:
            CORR[concepto] = c
        return s
    if ESCALA == "g":
        return escala.g_inv(escala.g(s) + c)
    if s >= 1 - 1e-4:
        return s + 1e-3 * math.tanh(c)
    z = en.logit(s) + c
    return 1.0 / (1.0 + math.exp(-z))


SQLiteMemoryBioRAG._calcular_score_hibrido = _con_neurona

CORR = {}
ULTIMO = {}  # lista final ANTES de reordenar + correcciones (para simular reglas sin re-correr)
ENGANCHES = {"llamadas": 0, "reordenadas": 0, "top1_cambiado": 0, "sin_correccion": 0}


def _reordenar(lista):
    """El enganche: la neurona ordena el pool y los scores de hoy se reasignan
    en ese orden (mismo multiconjunto de números -> ningún umbral absoluto cambia)."""
    ENGANCHES["llamadas"] += 1
    if not CORR or len(lista) < 2:
        return lista
    claves = [escala.g(r[4]) + CORR.get(r[0], 0.0) for r in lista]
    orden = sorted(range(len(lista)), key=lambda i: (-claves[i], i))
    if orden == list(range(len(lista))):
        return lista
    ENGANCHES["reordenadas"] += 1
    ENGANCHES["top1_cambiado"] += int(orden[0] != 0)
    scores = [r[4] for r in lista]  # ya vienen ordenados desc (sort de la línea anterior)
    return [lista[i][:4] + (scores[j],) + lista[i][5:] for j, i in enumerate(orden)]


def _reordenar_final(res):
    """Modo top5: reordena SOLO la lista final (mismos nodos, mismos scores reasignados)."""
    ENGANCHES["llamadas"] += 1
    ULTIMO.clear()
    if not CORR or len(res) < 2:
        return res
    cs = [CORR.get(r[0]) for r in res]
    ULTIMO.update(pre=[[r[0], float(r[4])] for r in res], c=cs)
    conocidas = [c for c in cs if c is not None]
    relleno = float(np.mean(conocidas)) if conocidas else 0.0
    ENGANCHES["sin_correccion"] += sum(c is None for c in cs)
    claves = [escala.g(min(max(r[4], 1e-4), 50.0)) + (c if c is not None else relleno) for r, c in zip(res, cs)]
    orden = sorted(range(len(res)), key=lambda i: (-claves[i], i))
    if orden == list(range(len(res))):
        return res
    ENGANCHES["reordenadas"] += 1
    ENGANCHES["top1_cambiado"] += int(orden[0] != 0)
    scores = sorted((r[4] for r in res), reverse=True)
    return [tuple(res[i][:4]) + (scores[j],) + tuple(res[i][5:]) for j, i in enumerate(orden)]


if P is not None and args.modo == "top5":
    from core.memory import search as _search
    _original = _search.buscar_por_frase
    _prof = [0]

    def _buscar_con_neurona(*a, **k):
        if _prof[0] == 0:
            CORR.clear()
        _prof[0] += 1
        try:
            res, total = _original(*a, **k)
        finally:
            _prof[0] -= 1
        if _prof[0] == 0:
            res = _reordenar_final(list(res))
        return res, total

    _search.buscar_por_frase = _buscar_con_neurona
    print("[neurona] modo top5: solo se reordena la lista final del motor", flush=True)

if P is not None and args.modo == "orden":
    import ast
    import textwrap
    from core.memory import search as _search
    src = Path(_search.__file__).read_text(encoding="utf-8")
    ancla = ("    resultados_con_hibrido.sort(key=lambda r: r[4], reverse=True)\n\n"
             "    # Promoción de candidatos generados por episodio léxico explícito.")
    assert src.count(ancla) == 1, "no encuentro el punto de enganche (search.py cambió)"
    src = src.replace(ancla, ancla.replace(
        "reverse=True)\n", "reverse=True)\n    resultados_con_hibrido = _NEURONA_REORDENAR(resultados_con_hibrido)\n", 1))
    arbol = ast.parse(src)
    fn = next(n for n in arbol.body if isinstance(n, ast.FunctionDef) and n.name == "buscar_por_frase")
    codigo = textwrap.dedent(ast.get_source_segment(src, fn))
    _search._NEURONA_REORDENAR = _reordenar
    exec(compile("\n" * (fn.lineno - 1) + codigo, _search.__file__, "exec"), _search.__dict__)
    _original = _search.buscar_por_frase

    def _buscar_con_neurona(*a, **k):
        CORR.clear()
        return _original(*a, **k)

    _search.buscar_por_frase = _buscar_con_neurona
    print("[neurona] modo orden: enganche insertado en memoria tras el sort de search.py "
          "(el archivo no se modifica)", flush=True)

# Registro por consulta (para contar ganancias y pérdidas caso a caso, también en la base)
import json as _json  # noqa: E402
from core.memory import search as _search_reg  # noqa: E402
_REG = open(AQUI / "resultados" / f"qa_motor_{args.etiqueta}_top.jsonl", "w", encoding="utf-8")
_antes_reg = _search_reg.buscar_por_frase
_prof_reg = [0]


def _buscar_registrando(self, frase, *a, **k):
    _prof_reg[0] += 1
    try:
        res, total = _antes_reg(self, frase, *a, **k)
    finally:
        _prof_reg[0] -= 1
    if _prof_reg[0] == 0 and k.get("limite") == 5:
        _REG.write(_json.dumps({"q": frase, "top": [r[0] for r in res], **ULTIMO}, ensure_ascii=False) + "\n")
        ULTIMO.clear()
    return res, total


_search_reg.buscar_por_frase = _buscar_registrando

import evaluar_qa  # noqa: E402

metrics, gate_ok, reasons = evaluar_qa.run_evaluation()
print(f"\n[GATE] {'OK' if gate_ok else 'FALLADO'} — {'; '.join(reasons) if reasons else 'dentro de umbrales'}")
if P is not None and args.modo in ("orden", "top5"):
    print(f"[neurona] enganche: {ENGANCHES}")
