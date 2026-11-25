"""Experimento 16 — métricas del piso (§4–§6) y entrenamiento/evaluación de la neurona (§7–§8).

Lee solo los extractos JSON de /tmp/exp16/extractos (mundos sintéticos). Escribe resultados/*.json.
Uso: PYTHONHASHSEED=1 python .../analizar.py /tmp/exp16
"""
import json
import os
import statistics
import sys
import time

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import mundo as M  # noqa: E402
import neurona as NS  # noqa: E402

PRIO = {"manual": 0, "sinonimo_explicito": 1, "co_semantica": 2, "latente_confirmada": 3, "co_ocurrencia": 4,
        "co_nombre": 5, "legacy_csv": 6, "manual_v7": 7, "test": 8}
MANUAL = {"manual"}


def cargar(base, nombre):
    with open(os.path.join(base, "extractos", nombre + ".json")) as fh:
        return json.load(fh)


def puntuacion_piso(ex):
    s = {}
    for o, d, p, t in ex["sinapsis"]:
        k = tuple(sorted((o, d)))
        s[k] = max(s.get(k, 0.0), float(p))
    return s


def candidatos(ex, peso_min=0.5):
    """Réplica del canal 2 del motor ANTES de truncar: mejor arista por (raíz, vecino)."""
    act = {c for c, r in ex["recs"].items() if r["estado"] == "activo"}
    filas = sorted(((PRIO.get(t, 9), -float(p), o, d, t, float(p)) for o, d, p, t in ex["sinapsis"]
                    if float(p) >= peso_min), key=lambda r: (r[0], r[1]))
    cand = {}
    for pr, _, o, d, t, p in filas:
        for raiz, vec in ((o, d), (d, o)):
            if raiz in ex["recs"] and vec in act and vec != raiz:
                lst = cand.setdefault(raiz, {})
                if vec not in lst:
                    lst[vec] = (t, round(p, 3))
    return cand


def lista_piso(cand_raiz):
    items = sorted(cand_raiz.items(), key=lambda kv: (PRIO.get(kv[1][0], 50), -kv[1][1]))
    return _truncar(items)


def lista_neurona(cand_raiz, puntaje):
    """Manuales primero; el resto por la neurona; tope 2 sinonimo_explicito; 5 lugares. No oculta:
    el conjunto de candidatos es el mismo que el del piso."""
    items = sorted(cand_raiz.items(), key=lambda kv: (0 if kv[1][0] in MANUAL else 1, -puntaje[kv[0]]))
    return _truncar(items)


def _truncar(items, top=5, max_syn=2):
    out, ns = [], 0
    for vec, (t, _) in items:
        if t == "sinonimo_explicito":
            if ns >= max_syn:
                continue
            ns += 1
        out.append(vec)
        if len(out) >= top:
            break
    return out


def auc(scores, labels):
    s, y = np.asarray(scores, float), np.asarray(labels, int)
    if y.min() == y.max():
        return float("nan")
    orden = s.argsort(kind="mergesort")
    rang = np.empty(len(s))
    ss = s[orden]
    i = 0
    while i < len(s):
        j = i
        while j + 1 < len(s) and ss[j + 1] == ss[i]:
            j += 1
        rang[orden[i:j + 1]] = (i + j) / 2 + 1
        i = j + 1
    npos = y.sum()
    nneg = len(y) - npos
    return float((rang[y == 1].sum() - npos * (npos + 1) / 2) / (npos * nneg))


def ece(p, y, bins=10):
    p, y = np.asarray(p, float), np.asarray(y, float)
    e = 0.0
    for b in range(bins):
        m = (p >= b / bins) & ((p < (b + 1) / bins) if b < bins - 1 else (p <= 1))
        if m.any():
            e += m.mean() * abs(p[m].mean() - y[m].mean())
    return float(e)


def precision_canal2(listas, raices, info):
    vals, vacias = [], 0
    for r in raices:
        l = listas.get(r, [])
        if not l:
            vacias += 1
            continue
        vals.append(sum(1 for v in l if M.relevancia(info, r, v) > 0) / len(l))
    return (float(np.mean(vals)) if vals else float("nan")), vacias


# ───────────────────────── piso ─────────────────────────
def metricas_piso(ex, solo_sellado=None):
    info = ex["info"]
    sp = puntuacion_piso(ex)
    pares = [k for k in sp if k[0] in info and k[1] in info]
    if solo_sellado is not None:
        pares = [k for k in pares if M.par_sellado(info, *k) == solo_sellado]
    lab = [1 if M.relevancia(info, *k) > 0 else 0 for k in pares]
    sc = [sp[k] for k in pares]
    # cobertura de rel=2
    porsub = {}
    for c, i in info.items():
        if i["grupo"] != "I" and i["tema"] is not None:
            porsub.setdefault((i["tema"], i["subtema"]), []).append(c)
    tot2 = cub2 = 0
    for miembros in porsub.values():
        for x in range(len(miembros)):
            for y in range(x + 1, len(miembros)):
                k = tuple(sorted((miembros[x], miembros[y])))
                if solo_sellado is not None and M.par_sellado(info, *k) != solo_sellado:
                    continue
                tot2 += 1
                cub2 += 1 if k in sp else 0
    raices = [c for c, i in info.items() if i["grupo"] == "D" and
              (solo_sellado is None or M.sellado(i["tema"]) == solo_sellado)]
    p5, vac = precision_canal2(ex["canal2_motor"], raices, info)
    grado = {}
    for a, b in sp:
        grado[a] = grado.get(a, 0) + 1
        grado[b] = grado.get(b, 0) + 1
    med = statistics.median(grado.values()) if grado else 0
    por_tipo = {}
    for o, d, p, t in ex["sinapsis"]:
        k = tuple(sorted((o, d)))
        if k[0] in info and k[1] in info:
            e = por_tipo.setdefault(t, [0, 0])
            e[0] += 1
            e[1] += 1 if M.relevancia(info, *k) > 0 else 0
    return {
        "pares_con_sinapsis": len(pares),
        "Q1_auc": round(auc(sc, lab), 4),
        "Q2_precision_nacimiento": round(float(np.mean(lab)), 4) if lab else None,
        "Q3_cobertura_rel2": round(cub2 / tot2, 4) if tot2 else None,
        "Q4_precision_at5": round(p5, 4), "Q4_sin_asociaciones": vac, "Q4_raices": len(raices),
        "Q5_grado_max": max(grado.values()) if grado else 0, "Q5_grado_mediana": med,
        "Q5_sobre_3x_mediana": sum(1 for g in grado.values() if g > 3 * med),
        "precision_por_tipo": {t: round(v[1] / v[0], 3) for t, v in sorted(por_tipo.items())},
        "aristas_por_tipo": {t: v[0] for t, v in sorted(por_tipo.items())},
    }


def invariancia(exD, exV, listas_D, listas_V):
    infoD = exD["info"]
    enD = {c for c, i in infoD.items()}
    sD, sV = puntuacion_piso(exD), puntuacion_piso(exV)
    claves = {k for k in set(sD) | set(sV) if k[0] in enD and k[1] in enD}
    difs = [abs(sD.get(k, 0.0) - sV.get(k, 0.0)) for k in claves]
    solo_uno = sum(1 for k in claves if (k in sD) != (k in sV))
    raices = sorted(c for c, i in infoD.items() if i["grupo"] == "D")
    lug = lug_I = cambia = 0
    for r in raices:
        lv = listas_V.get(r, [])
        lug += len(lv)
        lug_I += sum(1 for v in lv if v not in enD)
        cambia += 1 if lv != listas_D.get(r, []) else 0
    # diagnóstico (no es criterio): tipos de las aristas que aparecen/desaparecen y recuerdos que cambian de estado
    tipos = {}
    for exX, otra in ((exD, sV), (exV, sD)):
        for o, d, p, t in exX["sinapsis"]:
            k = tuple(sorted((o, d)))
            if k in claves and k not in otra:
                tipos[t] = tipos.get(t, 0) + 1
    estado_cambia = sum(1 for c in enD if c in exV["recs"] and
                        exD["recs"][c]["estado"] != exV["recs"][c]["estado"])
    return {
        "diag_aristas_en_una_sola_por_tipo": dict(sorted(tipos.items())),
        "diag_recuerdos_D_que_cambian_de_estado": estado_cambia,
        "I1_frac_pares_que_cambian": round(sum(1 for d in difs if d > 1e-9) / max(1, len(claves)), 4),
        "I2_max_delta": round(max(difs) if difs else 0.0, 4),
        "I3_pares_en_una_sola": solo_uno, "pares_evaluados": len(claves),
        "I4_frac_lugares_de_I": round(lug_I / max(1, lug), 4),
        "I5_frac_listas_que_cambian": round(cambia / max(1, len(raices)), 4),
    }


def determinismo(exA, exB):
    a = sorted(tuple(r) for r in exA["sinapsis"])
    b = sorted(tuple(r) for r in exB["sinapsis"])
    sa, sb = set(a), set(b)
    return {"R1_identicas": a == b, "aristas_A": len(a), "aristas_B": len(b),
            "solo_en_A": len(sa - sb), "solo_en_B": len(sb - sa)}


# ───────────────────────── neurona ─────────────────────────
def docs_de(ex):
    return {c: NS.documento(c, r) for c, r in ex["recs"].items()}


def tabla(pares, docs, ref):
    return np.array([NS.agujas(docs[a], docs[b], ref) for a, b in pares], float)


def main(base):
    out_dir = os.path.join(AQUI, "resultados")
    os.makedirs(out_dir, exist_ok=True)
    semillas = (1, 2, 3)
    ex = {(s, v): cargar(base, "s%d_%s" % (s, v)) for s in semillas
          for v in ("D", "D_rep", "D_Ipuro", "D_Ireal", "D_orden")}
    exG = cargar(base, "s11_G")
    res = {"piso": {}, "neurona": {}, "criterios": {}}

    # sanidad: la réplica del canal 2 reproduce al motor
    for s in semillas:
        c = candidatos(ex[(s, "D")])
        rep = {r: lista_piso(c[r]) for r in c}
        mot = ex[(s, "D")]["canal2_motor"]
        iguales = sum(1 for r in mot if rep.get(r, []) == mot[r])
        mismos_conj = sum(1 for r in mot if set(rep.get(r, [])) == set(mot[r]))
        # lo que importa: todo lo que muestra el motor está entre los candidatos que ve la neurona
        incluidas = sum(1 for r in mot if set(mot[r]) <= set(c.get(r, {})))
        # empates: vecinos con el mismo (tipo, fuerza) que el último lugar mostrado
        res.setdefault("sanidad_replica_canal2", {})[s] = {"listas": len(mot), "identicas": iguales,
                                                           "mismo_conjunto": mismos_conj,
                                                           "motor_dentro_de_candidatos": incluidas}

    # ── piso ──
    for s in semillas:
        D = ex[(s, "D")]
        r = {"todo": metricas_piso(D), "sellado": metricas_piso(D, True),
             "R1": determinismo(D, ex[(s, "D_rep")]), "Q6": ex[(s, "D_rep")].get("Q6")}
        for v in ("D_Ipuro", "D_Ireal", "D_orden"):
            r["inv_" + v] = invariancia(D, ex[(s, v)], D["canal2_motor"], ex[(s, v)]["canal2_motor"])
        r["segundos_construccion"] = {v: ex[(s, v)]["segundos_construccion"] for v in
                                      ("D", "D_rep", "D_Ipuro", "D_Ireal", "D_orden")}
        res["piso"][s] = r
    res["piso"]["G"] = {"todo": metricas_piso(exG), "sellado": metricas_piso(exG, True)}

    # ── neurona: entrenamiento SOLO con pares no sellados de los mundos D de las 3 semillas ──
    docs_ent, pares_fit, pares_cal = [], [], []
    for s in semillas:
        D = ex[(s, "D")]
        info = D["info"]
        dd = docs_de(D)
        for c, i in info.items():
            if i["tema"] is None or not M.sellado(i["tema"]):
                docs_ent.append(dd[c])
        for k in puntuacion_piso(D):
            if k[0] in info and k[1] in info and not M.par_sellado(info, *k):
                temas = {info[x]["tema"] for x in k} - {None}
                destino = pares_cal if any(t % 4 == 1 for t in temas) else pares_fit
                destino.append((s, k, 1 if M.relevancia(info, *k) > 0 else 0))
    ref = NS.Referencia(docs_ent)
    docs = {s: docs_de(ex[(s, "D")]) for s in semillas}

    def mat(lista):
        X = np.array([NS.agujas(docs[s][a], docs[s][b], ref) for s, (a, b), _ in lista], float)
        return X, np.array([y for *_, y in lista], float)

    Xf, yf = mat(pares_fit)
    Xc, yc = mat(pares_cal)
    red = NS.Neurona(ref, ocultas=16, semilla=0)
    t0 = time.time()
    perdida = red.entrenar(Xf, yf, Xc, yc)
    red.calibrar(Xc, yc)
    res["neurona"]["entrenamiento"] = {
        "pares_ajuste": len(yf), "positivos_ajuste": int(yf.sum()), "pares_calibracion": len(yc),
        "positivos_calibracion": int(yc.sum()), "docs_referencia": ref.n, "huella_referencia": ref.huella(),
        "epocas": red.epocas, "perdida_validacion": round(perdida, 4), "segundos": round(time.time() - t0, 1),
        "agujas": NS.NOMBRES}
    np.savez(os.path.join(out_dir, "neurona_ns1_pesos.npz"), W1=red.W1, b1=red.b1, w2=red.w2, b2=red.b2,
             mu=red.mu, sd=red.sd, iso_x=red.iso_x, iso_y=red.iso_y)

    def evaluar(exX, dd, etiqueta):
        info = exX["info"]
        sp = puntuacion_piso(exX)
        pares = [k for k in sp if k[0] in info and k[1] in info and M.par_sellado(info, *k)]
        X = tabla(pares, dd, ref)
        y = np.array([1 if M.relevancia(info, *k) > 0 else 0 for k in pares])
        cr = red.puntuar_crudo(X)
        p = red.prob(X)
        # canal 2 ordenado por la neurona, raíces de temas sellados
        cand = candidatos(exX)
        raices = [c for c, i in info.items() if i["grupo"] == "D" and M.sellado(i["tema"])]
        lp, ln = {}, {}
        for r in raices:
            if r not in cand:
                continue
            vec = list(cand[r])
            Xr = tabla([(r, v) for v in vec], dd, ref)
            pu = dict(zip(vec, red.puntuar_crudo(Xr)))
            lp[r] = lista_piso(cand[r])
            ln[r] = lista_neurona(cand[r], pu)
        p5_piso, vac_piso = precision_canal2(lp, raices, info)
        p5_neu, vac_neu = precision_canal2(ln, raices, info)
        p5_mot, vac_mot = precision_canal2(exX["canal2_motor"], raices, info)
        return {"pares_sellados": len(pares), "positivos": int(y.sum()),
                "AUC_piso": round(auc([sp[k] for k in pares], y), 4), "AUC_neurona": round(auc(cr, y), 4),
                "ECE_neurona": round(ece(p, y), 4), "Brier_neurona": round(float(((p - y) ** 2).mean()), 4),
                "P@5_piso_motor": round(p5_mot, 4), "P@5_piso_replica": round(p5_piso, 4),
                "P@5_neurona": round(p5_neu, 4),
                "sin_asociaciones_piso": vac_mot, "sin_asociaciones_neurona": vac_neu, "raices": len(raices)}

    for s in semillas:
        res["neurona"][s] = evaluar(ex[(s, "D")], docs[s], s)
    docsG = docs_de(exG)
    res["neurona"]["G"] = evaluar(exG, docsG, "G")

    # invariancia de la neurona (mismas variantes)
    for s in semillas:
        D = ex[(s, "D")]
        cD = candidatos(D)
        dd_all = {}
        for v in ("D", "D_Ipuro", "D_Ireal", "D_orden"):
            dd_all[v] = docs_de(ex[(s, v)])

        def listas_neu(v):
            c = candidatos(ex[(s, v)])
            out = {}
            for r in c:
                vec = list(c[r])
                pu = dict(zip(vec, red.puntuar_crudo(tabla([(r, x) for x in vec], dd_all[v], ref))))
                out[r] = lista_neurona(c[r], pu)
            return out

        lD = listas_neu("D")
        for v in ("D_Ipuro", "D_Ireal", "D_orden"):
            lV = listas_neu(v)
            base_inv = invariancia(D, ex[(s, v)], lD, lV)
            # I1 de la neurona: pares presentes en ambas variantes → ¿misma puntuación?
            sD, sV = puntuacion_piso(D), puntuacion_piso(ex[(s, v)])
            comunes = [k for k in sD if k in sV]
            a = red.puntuar_crudo(tabla(comunes, dd_all["D"], ref))
            b = red.puntuar_crudo(tabla(comunes, dd_all[v], ref))
            base_inv["I1_neurona_pares_comunes_que_cambian"] = int((np.abs(a - b) > 1e-9).sum())
            base_inv["I2_neurona_max_delta"] = float(np.abs(a - b).max()) if len(a) else 0.0
            res["neurona"].setdefault("inv", {}).setdefault(s, {})[v] = base_inv

    # costo por decisión (§8.7): N=400 frente a N=1600, con recuerdos generados por mundo.py
    import construir as C
    cat = C.catalogo_real()
    costo = {}
    for n in (400, 1600):
        mw = M.generar(5, cat, n=n)
        recs = {e["concepto"]: {"contenido": e["contenido"], "syn": e["syn"], "sk": e["sk"], "cat": e["cat"],
                                "dims": [x for v in e["dims"].values() for x in v]} for e in mw["eventos"]}
        dd = {c: NS.documento(c, r) for c, r in recs.items()}
        nombres = sorted(dd)
        rng = np.random.default_rng(1)
        pares = [(nombres[i], nombres[j]) for i, j in rng.integers(0, len(nombres), (3000, 2)) if i != j]
        t0 = time.perf_counter()
        red.puntuar_crudo(tabla(pares, dd, ref))
        costo[n] = (time.perf_counter() - t0) / len(pares) * 1e3
    res["neurona"]["costo_ms_por_par"] = {str(k): round(v, 4) for k, v in costo.items()}

    # ── criterios §8 (fijados antes de medir) ──
    cri = {}
    for s in semillas:
        e = res["neurona"][s]
        inv = res["neurona"]["inv"][s]
        cri[s] = {
            "1_auc": e["AUC_neurona"] >= e["AUC_piso"] + 0.05 and e["AUC_neurona"] >= 0.80,
            "2_p@5": e["P@5_neurona"] >= e["P@5_piso_motor"] + 0.10 and
                     e["sin_asociaciones_neurona"] <= e["sin_asociaciones_piso"],
            "3_cobertura": True,   # la neurona no cambia nacimientos: cobertura idéntica al piso
            "4_invariancia": all(inv[v]["I1_neurona_pares_comunes_que_cambian"] == 0 and
                                 inv[v]["I3_pares_en_una_sola"] == 0 and inv[v]["I4_frac_lugares_de_I"] == 0 and
                                 inv[v]["I5_frac_listas_que_cambian"] == 0 for v in inv),
            "4a_parte_de_la_neurona_I1": all(inv[v]["I1_neurona_pares_comunes_que_cambian"] == 0 for v in inv),
            "5_determinismo": res["piso"][s]["R1"]["R1_identicas"],
            "6_ece": e["ECE_neurona"] <= 0.05,
        }
    cri["7_costo"] = costo[1600] <= 1.5 * costo[400]
    g = res["neurona"]["G"]
    cri["8_generalizacion"] = g["AUC_neurona"] >= g["AUC_piso"] + 0.03
    res["criterios"] = cri
    with open(os.path.join(out_dir, "resultados.json"), "w") as fh:
        json.dump(res, fh, indent=1, ensure_ascii=False, default=str)
    print(json.dumps(res, indent=1, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main(sys.argv[1])
