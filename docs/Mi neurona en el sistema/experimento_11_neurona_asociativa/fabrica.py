"""Fábrica y examen de la neurona asociativa (experimento 11).

  1. Arma tres memorias de fábrica con verdad conocida (noticias, diccionario,
     relatos) y calcula las agujas de los pares que un motor mecánico propondría.
  2. Banco de calibración: qué tanto separa cada aguja "tiene que ver" de "no".
  3. Examen "nunca vista": entrena con 2 memorias y examina en la 3ª (x3).
  4. Fábrica final: entrena con las 3, congela los pesos (pesos_fabrica.json).
  5. Examen real: la memoria de Dennys (español, nunca vista, otro idioma,
     otro dominio). Solo lectura sobre una COPIA del snapshot.

Uso:  python fabrica.py           (escribe resultados/*.json; ~2-3 min)
"""
import hashlib
import json
import os
import pickle
import sys
import time

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import agujas  # noqa: E402
import corpus  # noqa: E402
import neurona_asociativa as na  # noqa: E402

RES = os.path.join(AQUI, "resultados")
CACHE = "/tmp/e11/fabrica_cache.pkl"
SEMILLAS = (0, 1, 2)


def auc(s, y):
    s = np.asarray(s, dtype=np.float64)
    y = np.asarray(y)
    o = np.argsort(s, kind="mergesort")
    r = np.empty(len(s))
    ss = s[o]
    i = 0
    while i < len(s):
        j = i
        while j + 1 < len(s) and ss[j + 1] == ss[i]:
            j += 1
        r[o[i:j + 1]] = (i + j + 2) / 2.0
        i = j + 1
    p = y == 1
    n1, n0 = p.sum(), (~p).sum()
    return float((r[p].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def pr(conecta, y):
    tp = int((conecta & (y == 1)).sum())
    return {"precision": round(tp / max(int(conecta.sum()), 1), 3),
            "recall": round(tp / max(int((y == 1).sum()), 1), 3),
            "conecta_pct": round(float(conecta.mean()) * 100, 1)}


def jaccard_idf(m, pares):
    out = np.zeros(len(pares))
    for k, (a, b) in enumerate(pares):
        sa, sb = m.sets[a], m.sets[b]
        com = sa & sb
        ic = sum(m.idf[j] for j in com)
        ia = sum(m.idf[j] for j in sa)
        ib = sum(m.idf[j] for j in sb)
        out[k] = ic / max(ia + ib - ic, 1e-9)
    return out


def guardia(a, b):
    """20 % de los recuerdos (por hash) son GUARDIA: nunca se estudian."""
    return any(int(hashlib.sha256(str(x).encode()).hexdigest(), 16) % 5 == 0 for x in (a, b))


def construir():
    if os.path.exists(CACHE):
        return pickle.load(open(CACHE, "rb"))
    d = {}
    for fn in (corpus.noticias, corpus.diccionario, corpus.relatos):
        t0 = time.time()
        nombre, textos, verdad = fn()
        m = agujas.Memoria(textos)
        pares = m.candidatos(rng=np.random.default_rng(0))
        y = [verdad(a, b) for a, b in pares]
        keep = [i for i, v in enumerate(y) if v is not None]
        pares = [pares[i] for i in keep]
        y = np.array([y[i] for i in keep])
        d[nombre] = {"F": m.agujas(pares), "y": y, "pares": pares, "jac": jaccard_idf(m, pares),
                     "n_recuerdos": len(textos), "segundos": round(time.time() - t0, 1)}
        print(f"  {nombre}: {len(textos)} recuerdos, {len(pares)} pares, {int(y.sum())} sí", flush=True)
    pickle.dump(d, open(CACHE, "wb"))
    return d


def filas(d, nombres_mem):
    """X, y, w (cada memoria pesa 1; dentro, sí y no pesan 1/2 cada uno), separadas en estudio/guardia."""
    E, G = [[], [], []], [[], [], []]
    for nm in nombres_mem:
        v = d[nm]
        X = na._columnas(v["F"], agujas.NOMBRES)
        y = v["y"].astype(float)
        es_g = np.array([guardia(f"{nm}:{a}", f"{nm}:{b}") for a, b in v["pares"]])
        for dest, mask in ((E, ~es_g), (G, es_g)):
            yy = y[mask]
            n1, n0 = max(yy.sum(), 1), max((1 - yy).sum(), 1)
            ww = np.where(yy == 1, 0.5 / n1, 0.5 / n0)
            dest[0].append(X[mask]); dest[1].append(yy); dest[2].append(ww)
    return [np.concatenate(a) for a in E], [np.concatenate(a) for a in G]


def examinar(v, p):
    y = v["y"]
    out = {"pares": int(len(y)), "si_tienen_que_ver_pct": round(float(y.mean()) * 100, 1)}
    f_piso = na.fuerza(v["F"], agujas.NOMBRES, p=None)
    out["motor_hoy_conecta_todo"] = pr(np.ones(len(y), bool), y)
    out["regla_jaccard_0.4"] = dict(auc=round(auc(v["jac"], y), 3), **pr(v["jac"] >= 0.4, y))
    out["piso_a_mano"] = {"auc": round(auc(f_piso, y), 3),
                          "debil_o_mas": pr(f_piso >= na.UMBRAL_DEBIL, y),
                          "conectar": pr(f_piso >= na.UMBRAL_CONECTAR, y),
                          "competencia_k5": pr(na.competencia(f_piso, v["pares"], 5), y),
                          "competencia_k10": pr(na.competencia(f_piso, v["pares"], 10), y)}
    if p is not None:
        ps = p if isinstance(p, list) else [p]
        fs = [na.fuerza(v["F"], agujas.NOMBRES, p=q) for q in ps]
        aucs = [auc(f, y) for f in fs]
        f = fs[0]
        out["neurona"] = {"auc": round(float(np.mean(aucs)), 3), "auc_semillas": [round(a, 3) for a in aucs],
                          "debil_o_mas": pr(f >= na.UMBRAL_DEBIL, y),
                          "conectar": pr(f >= na.UMBRAL_CONECTAR, y),
                          "competencia_k5": pr(na.competencia(f, v["pares"], 5), y),
                          "competencia_k10": pr(na.competencia(f, v["pares"], 10), y)}
    return out


def entrenar_con(d, memorias):
    E, G = filas(d, memorias)
    ps, infos = [], []
    for s in SEMILLAS:
        p, info = na.entrenar(*E, *G, semilla=s)
        ps.append(p)
        infos.append(info)
    return ps, infos


def _topk(f, pares, k):
    keep = np.zeros(len(f), bool)
    por = {}
    for i, (a, b) in enumerate(pares):
        por.setdefault(a, []).append(i)
        por.setdefault(b, []).append(i)
    for idx in por.values():
        idx = np.asarray(idx)
        keep[idx[np.argsort(-f[idx], kind="mergesort")[:k]]] = True
    return keep


def examen_dennys(p):
    nombre, textos, verdad, conceptos, sin = corpus.dennys()
    m = agujas.Memoria(textos)
    pares = sorted(sin)
    F = m.agujas(pares)
    tipo = np.array([sin[k][0] for k in pares])
    peso = np.array([sin[k][1] for k in pares], dtype=float)
    y = (tipo == "manual").astype(int)
    f_piso = na.fuerza(F, agujas.NOMBRES, p=None)
    f = na.fuerza(F, agujas.NOMBRES, p=p)
    out = {"recuerdos": len(textos), "conexiones_existentes": len(pares), "manual": int(y.sum()),
           "auc_manual_vs_resto": {"peso_del_motor_hoy": round(auc(peso, y), 3),
                                   "piso_a_mano": round(auc(f_piso, y), 3),
                                   "neurona": round(auc(f, y), 3)}}
    por_tipo = {}
    for t in sorted(set(tipo), key=lambda t: -(tipo == t).sum()):
        mk = tipo == t
        por_tipo[t] = {"n": int(mk.sum()), "peso_motor_medio": round(float(peso[mk].mean()), 2),
                       "fuerza_media": round(float(f[mk].mean()), 3),
                       "conectar_pct": round(float((f[mk] >= na.UMBRAL_CONECTAR).mean()) * 100, 1),
                       "debil_pct": round(float(((f[mk] >= na.UMBRAL_DEBIL) & (f[mk] < na.UMBRAL_CONECTAR)).mean()) * 100, 1),
                       "no_pct": round(float((f[mk] < na.UMBRAL_DEBIL).mean()) * 100, 1)}
    out["por_tipo"] = por_tipo
    # competencia: cada recuerdo conserva sus K socios más fuertes. ¿Cuántos enlaces
    # HUMANOS (manual) sobreviven si el orden lo da la neurona vs el peso de hoy?
    comp = {}
    ruido = np.random.default_rng(0).uniform(0, 1e-6, len(peso))   # desempata el peso de hoy al azar
    for k in (5, 10, 20):
        kn = na.competencia(f, pares, k)          # regla completa de la neurona
        tn = _topk(f, pares, k)                    # solo competencia, orden de la neurona
        tw = _topk(peso + ruido, pares, k)         # solo competencia, orden del peso de hoy
        comp[f"k{k}"] = {"se_conserva_pct": round(float(kn.mean()) * 100, 1),
                         "manual_conservadas_neurona_pct": round(float(kn[y == 1].mean()) * 100, 1),
                         "solo_competencia": {"se_conserva_pct": round(float(tn.mean()) * 100, 1),
                                              "manual_orden_neurona_pct": round(float(tn[y == 1].mean()) * 100, 1),
                                              "manual_orden_peso_hoy_pct": round(float(tw[y == 1].mean()) * 100, 1)},
                         "por_tipo_pct": {t: round(float(kn[tipo == t].mean()) * 100, 1)
                                          for t in por_tipo if por_tipo[t]["n"] >= 50}}
    out["competencia"] = comp
    k10 = na.competencia(f, pares, 10)
    # el recuerdo de la captura del Neuro-Visor
    caso = "leccion_discrepancia_busquedas_vocabulario_no_estocasticidad"
    if caso in conceptos:
        ic = conceptos.index(caso)
        idx = [k for k, (a, b) in enumerate(pares) if ic in (a, b)]
        filas_c = []
        for k in idx:
            a, b = pares[k]
            otro = conceptos[b if a == ic else a]
            filas_c.append({"con": otro, "tipo": str(tipo[k]), "peso_motor": round(float(peso[k]), 2),
                            "fuerza": round(float(f[k]), 3), "decision": str(na.decision(np.array([f[k]]))[0]),
                            "se_queda_con_competencia_k10": bool(k10[k])})
        filas_c.sort(key=lambda r: -r["fuerza"])
        dec = [r["decision"] for r in filas_c]
        out["caso_neuro_visor"] = {"recuerdo": caso, "conexiones": len(filas_c),
                                   "conectar": dec.count("conectar"), "debil": dec.count("debil"), "no": dec.count("no"),
                                   "manual_conservadas": sum(1 for r in filas_c if r["tipo"] == "manual" and r["decision"] != "no"),
                                   "manual_total": sum(1 for r in filas_c if r["tipo"] == "manual"),
                                   "se_quedan_k10": sum(1 for r in filas_c if r["se_queda_con_competencia_k10"]),
                                   "manual_se_quedan_k10": sum(1 for r in filas_c if r["tipo"] == "manual" and r["se_queda_con_competencia_k10"]),
                                   "todas": filas_c}
    return out


def main():
    os.makedirs(RES, exist_ok=True)
    t0 = time.time()
    print("1) Memorias de fábrica", flush=True)
    d = construir()
    print("2) Banco de calibración", flush=True)
    banco = {}
    for nm, v in d.items():
        banco[nm] = {a: {"auc": round(auc(v["F"][:, i], v["y"]), 3),
                         "media_si": round(float(v["F"][v["y"] == 1, i].mean()), 3),
                         "media_no": round(float(v["F"][v["y"] == 0, i].mean()), 3)}
                     for i, a in enumerate(agujas.NOMBRES)}
    json.dump(banco, open(os.path.join(RES, "banco_calibracion.json"), "w"), indent=1, ensure_ascii=False)
    print("3) Examen 'nunca vista' (entrena con 2, examina en la 3ª)", flush=True)
    nunca = {}
    for fuera in d:
        dentro = [x for x in d if x != fuera]
        ps, infos = entrenar_con(d, dentro)
        nunca[fuera] = {"entrenada_con": dentro, **examinar(d[fuera], ps), "entrenamiento": infos}
        print(f"  {fuera}: piso {nunca[fuera]['piso_a_mano']['auc']} -> neurona {nunca[fuera]['neurona']['auc']}"
              f"  | competencia k10: {nunca[fuera]['neurona']['competencia_k10']}", flush=True)
    json.dump(nunca, open(os.path.join(RES, "examen_nunca_vista.json"), "w"), indent=1, ensure_ascii=False)
    print("4) Fábrica final (las 3 memorias), pesos congelados", flush=True)
    ps, infos = entrenar_con(d, list(d))
    na.guardar(ps[0], extra={"memorias": list(d), "entrenamiento": infos[0],
                             "pares": {k: int(len(v["y"])) for k, v in d.items()}})
    final = {nm: examinar(v, ps[0]) for nm, v in d.items()}
    json.dump(final, open(os.path.join(RES, "fabrica_final.json"), "w"), indent=1, ensure_ascii=False)
    print("5) Examen real: memoria de Dennys (nunca vista)", flush=True)
    den = examen_dennys(na.cargar())
    json.dump(den, open(os.path.join(RES, "examen_dennys.json"), "w"), indent=1, ensure_ascii=False)
    print(f"  AUC manual vs resto: {den['auc_manual_vs_resto']}", flush=True)
    for k, v in den["competencia"].items():
        print(f"  competencia {k}: se conserva {v['se_conserva_pct']} %, manual {v['manual_conservadas_neurona_pct']} % | "
              f"solo competencia: orden neurona {v['solo_competencia']['manual_orden_neurona_pct']} % vs peso hoy "
              f"{v['solo_competencia']['manual_orden_peso_hoy_pct']} %", flush=True)
    print(f"listo en {round(time.time() - t0)} s", flush=True)


if __name__ == "__main__":
    main()
