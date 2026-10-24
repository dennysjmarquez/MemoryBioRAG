"""Análisis completo de la hoja marcada por Dennys (va más allá de medir_hoja.py).

Uso:  python analizar_hoja.py [ruta_a_la_db]      (sin ruta: snapshot del repo, SIEMPRE sobre una copia)

Necesita en esta carpeta: hoja_para_dennys.csv (marcada) y clave_no_mirar.json (sale de preparar_hoja.py).
Escribe ../resultados/examen_hoja_dennys.json. Ese archivo NO lleva textos de recuerdos: solo nombres
de concepto, grupo, fuerza, tipo de sinapsis de hoy y la respuesta de Dennys.

Qué mide:
  1. Por grupo, cuántos "sí" y "no" hay (los "no sé" no cuentan).
  2. Si la FUERZA de la neurona separa los "sí" de los "no" (AUC: 0.5 = azar, 1 = perfecto).
  3. En las sinapsis que ya existen (grupos A y B), neurona contra el PESO de hoy del motor.
  4. Margen de error con remuestreo (bootstrap, 5000 vueltas, semilla fija), porque son pocos pares.
"""
import csv
import json
import os
import shutil
import sqlite3
import sys
import tempfile

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
SNAPSHOT = os.path.abspath(os.path.join(AQUI, "..", "..", "..", "..", "snapshots", "qa_escape_qcr_20260811.db"))
TRAMOS = [(0.0, 0.4), (0.4, 0.5), (0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 1.01)]


def auc(s, y):
    s, y = np.asarray(s, float), np.asarray(y, int)
    p, n = s[y == 1], s[y == 0]
    if not len(p) or not len(n):
        return float("nan")
    return float(((p[:, None] > n[None, :]).sum() + 0.5 * (p[:, None] == n[None, :]).sum()) / len(p) / len(n))


def margen(fn, n, vueltas=5000, semilla=0):
    rng = np.random.default_rng(semilla)
    v = [fn(rng.integers(0, n, n)) for _ in range(vueltas)]
    v = np.array([x for x in v if not np.isnan(x)])
    return [round(float(x), 3) for x in np.percentile(v, [2.5, 97.5])], v


def main():
    clave = json.load(open(os.path.join(AQUI, "clave_no_mirar.json"), encoding="utf-8"))["pares"]
    resp = {}
    with open(os.path.join(AQUI, "hoja_para_dennys.csv"), encoding="utf-8-sig") as fh:
        for f in csv.reader(fh):
            if f and f[0] != "id":
                if f[1] != clave[f[0]]["a"] or f[3] != clave[f[0]]["b"]:
                    sys.exit(f"La hoja no corresponde a la clave (par {f[0]}). Regenera con preparar_hoja.py.")
                resp[f[0]] = f[5].strip().lower().replace("sí", "si").replace("no sé", "nose").replace("no se", "nose")

    tmp = tempfile.mkdtemp(prefix="hoja_")
    copia = os.path.join(tmp, "copia.db")
    shutil.copyfile(sys.argv[1] if len(sys.argv) > 1 else SNAPSHOT, copia)
    db = sqlite3.connect(f"file:{copia}?mode=ro", uri=True)
    peso = {}
    for o, d, p in db.execute("SELECT origen, destino, peso FROM sinapsis"):
        for k in ((o, d), (d, o)):
            peso[k] = max(peso.get(k, 0.0), p)
    db.close()
    shutil.rmtree(tmp, ignore_errors=True)

    lab = {i: int(r in ("si", "momento")) for i, r in resp.items() if r in ("si", "momento", "no")}
    ids = sorted(lab, key=int)
    fz = np.array([clave[i]["fuerza"] for i in ids])
    y = np.array([lab[i] for i in ids])
    out = {"contestadas": sum(1 for r in resp.values() if r), "decididas_si_o_no": len(ids),
           "conteo_respuestas": {r: list(resp.values()).count(r) for r in sorted(set(resp.values()))}}

    print(f"Contestadas {out['contestadas']} de {len(clave)} · con sí/no {len(ids)} (los 'no sé' no cuentan)\n")
    print("1) Por grupo")
    out["grupos"] = {}
    nombres = {"A": "la neurona CONSERVA", "B": "la neurona SOLTARÍA", "C": "Gemini las sacó, la neurona les da fuerza",
               "D": "la neurona PROPONE (no existen)"}
    for g, txt in nombres.items():
        gi = [i for i in ids if clave[i]["grupo"] == g]
        si = sum(lab[i] for i in gi)
        nose = sum(1 for i in clave if clave[i]["grupo"] == g and resp.get(i) == "nose")
        out["grupos"][g] = {"que_es": txt, "si": si, "no": len(gi) - si, "nose": nose,
                            "pct_si": round(100 * si / len(gi), 1) if gi else None}
        print(f"   {g} ({txt}): sí {si} · no {len(gi) - si} · no sé {nose} → {100 * si / len(gi):.0f} % sí")

    a_all = auc(fz, y)
    ci_all, _ = margen(lambda k: auc(fz[k], y[k]), len(ids))
    out["auc_fuerza_todos"] = {"valor": round(a_all, 3), "margen_95": ci_all}
    print(f"\n2) ¿La fuerza separa sí de no? AUC {a_all:.3f} (margen {ci_all[0]}–{ci_all[1]})")
    out["tramos_fuerza"] = []
    for lo, hi in TRAMOS:
        m = (fz >= lo) & (fz < hi)
        out["tramos_fuerza"].append({"desde": lo, "hasta": min(hi, 1.0), "n": int(m.sum()), "si": int(y[m].sum())})
        if m.sum():
            print(f"   fuerza {lo:.1f}–{min(hi, 1.0):.1f}: {int(y[m].sum())} sí de {int(m.sum())} ({100 * y[m].mean():.0f} %)")
    m = fz >= 0.6
    out["corte_0_6"] = {"arriba": [int(y[m].sum()), int(m.sum())], "abajo": [int(y[~m].sum()), int((~m).sum())]}
    print(f"   fuerza ≥ 0.6: {int(y[m].sum())}/{int(m.sum())} sí ({100 * y[m].mean():.0f} %) · "
          f"< 0.6: {int(y[~m].sum())}/{int((~m).sum())} ({100 * y[~m].mean():.0f} %)")

    ex = [k for k, i in enumerate(ids) if clave[i]["grupo"] in "AB"]
    fe, ye = fz[ex], y[ex]
    pe = np.array([peso.get((clave[ids[k]]["a"], clave[ids[k]]["b"]), 0.0) for k in ex])
    an, ah = auc(fe, ye), auc(pe, ye)
    ci_n, _ = margen(lambda k: auc(fe[k], ye[k]), len(ex))
    ci_h, _ = margen(lambda k: auc(pe[k], ye[k]), len(ex))
    ci_d, vd = margen(lambda k: auc(fe[k], ye[k]) - auc(pe[k], ye[k]), len(ex))
    out["existentes_neurona_vs_peso_hoy"] = {"n": len(ex), "neurona": round(an, 3), "neurona_margen_95": ci_n,
                                             "peso_hoy": round(ah, 3), "peso_hoy_margen_95": ci_h,
                                             "diferencia_margen_95": ci_d,
                                             "prob_neurona_mejor": round(float((vd > 0).mean()), 3)}
    print(f"\n3) Sinapsis que YA existen ({len(ex)} con sí/no): ¿quién ordena mejor lo bueno arriba?")
    print(f"   neurona AUC {an:.3f} (margen {ci_n[0]}–{ci_n[1]})")
    print(f"   peso de hoy AUC {ah:.3f} (margen {ci_h[0]}–{ci_h[1]})")
    print(f"   la neurona gana en {100 * (vd > 0).mean():.0f} % de los remuestreos "
          f"(diferencia {ci_d[0]} a {ci_d[1]}; si el margen cruza 0, con 58 pares aún no es prueba firme)")

    out["por_tipo_hoy"] = {}
    for i in ids:
        t = clave[i]["tipo_hoy"]
        d = out["por_tipo_hoy"].setdefault(t, {"n": 0, "si": 0})
        d["n"] += 1
        d["si"] += lab[i]
    out["pares"] = [{"id": int(i), "grupo": clave[i]["grupo"], "a": clave[i]["a"], "b": clave[i]["b"],
                     "fuerza": clave[i]["fuerza"], "tipo_hoy": clave[i]["tipo_hoy"],
                     "peso_hoy": round(peso.get((clave[i]["a"], clave[i]["b"]), 0.0), 3),
                     "respuesta_dennys": resp.get(i, "")} for i in sorted(clave, key=int)]
    dest = os.path.join(AQUI, "..", "resultados", "examen_hoja_dennys.json")
    json.dump(out, open(dest, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\nGuardado: resultados/examen_hoja_dennys.json (sin textos de recuerdos)")


if __name__ == "__main__":
    main()
