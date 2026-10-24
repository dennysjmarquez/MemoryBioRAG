"""Fábrica y examen de la neurona asociativa (experimento 11, versión 2).

  1. Arma 8 memorias de fábrica con verdad conocida (inglés, español,
     portugués, código, chat; largas, cortas, con y sin tiempo, con y sin
     etiquetas) y calcula las agujas de los pares que un motor propondría.
  2. Banco de calibración: qué tanto separa cada aguja "tiene que ver" de "no".
  3. Examen "nunca vista" (8 vueltas): en cada vuelta se calibra el piso Y se
     entrena la corrección con 7 memorias, y se examina en la 8ª. Nada de la
     memoria examinada se mira. Es el número limpio.
  4. Fábrica final: piso del archivo + corrección entrenada con las 8, congelada.
  5. Examen real: la memoria de Dennys (español técnico, nunca vista). Tres
     jueces: la persona (enlaces manuales), Gemini (la hormiguita: lo que sacó
     a cuarentena y lo que confirmó) y el peso que usa el motor hoy.
     Solo lectura sobre una COPIA del snapshot.

Uso:  python fabrica.py           (escribe resultados/*.json)
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
CACHE = f"/tmp/e11/cache_v{agujas.VERSION_AGUJAS}"
SEMILLAS = (0, 1, 2)
PESOS_POSIBLES = (-2, -1, 0, 1, 2, 3, 4)
RESTAN = ("hub", "una_sola")          # agujas que solo pueden restar (el banco dice AUC < .5 en todas)


def auc(s, y):
    return na._auc(s, y)


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
    os.makedirs(CACHE, exist_ok=True)
    d = {}
    for fn in corpus.FABRICA:
        ruta = os.path.join(CACHE, fn.__name__ + ".pkl")
        if os.path.exists(ruta):
            d[fn.__name__] = pickle.load(open(ruta, "rb"))
            continue
        t0 = time.time()
        mem = fn()
        m = agujas.Memoria(mem["textos"], orden=mem["orden"], etiquetas=mem["etiquetas"])
        pares = m.candidatos(rng=np.random.default_rng(0))
        y = [mem["verdad"](a, b) for a, b in pares]
        n_si_cand = sum(1 for v in y if v == 1)
        keep = [i for i, v in enumerate(y) if v is not None]
        pares = [pares[i] for i in keep]
        y = np.array([y[i] for i in keep])
        v = {"F": m.agujas(pares), "y": y, "pares": pares, "jac": jaccard_idf(m, pares),
             "idioma": mem["idioma"], "n_recuerdos": len(mem["textos"]),
             "tiene_tiempo": mem["orden"] is not None, "tiene_etiquetas": mem["etiquetas"] is not None,
             "fiab_episodio": round(m.fiab_episodio, 3), "fiab_etiquetas": round(m.fiab_etiquetas, 3),
             "palabras_mediana": int(np.median([len(t.split()) for t in mem["textos"]])),
             "positivos_totales": mem.get("positivos_totales"),
             "cobertura_candidatos": round(n_si_cand / mem["positivos_totales"], 3) if mem.get("positivos_totales") else None,
             "segundos": round(time.time() - t0, 1)}
        pickle.dump(v, open(ruta, "wb"))
        d[fn.__name__] = v
    for nm, v in d.items():
        print(f"  {nm:12s} {v['idioma']:6s} {v['n_recuerdos']:5d} recuerdos, {len(v['y']):6d} pares, "
              f"{int(v['y'].sum()):6d} sí, tiempo {v['fiab_episodio'] if v['tiene_tiempo'] else '-'}, "
              f"etiquetas {v['fiab_etiquetas'] if v['tiene_etiquetas'] else '-'}, "
              f"cobertura {v['cobertura_candidatos']}", flush=True)
    return d


# ---------- piso: calibración por banco (subida coordenada sobre pesos redondos) ----------

def _X(v):
    return na._columnas(v["F"], agujas.NOMBRES_TODAS)


def puntaje_piso(P, d, memorias):
    a = [auc(na.piso(_X(d[nm]), P), d[nm]["y"]) for nm in memorias]
    return float(np.mean(a)), a


def calibrar_piso(d, memorias, inicio=None):
    """Pesos enteros. Objetivo: AUC promedio de las memorias dadas. Signos fijos por
    biología/banco: las agujas que suman van de 0 a 4; `hub` y `una_sola` de -2 a 0."""
    P = dict(inicio or {"sesgo": na.PISO["sesgo"]})        # se arranca de cero: que decida el banco
    mejor, _ = puntaje_piso(P, d, memorias)
    cambio = True
    while cambio:
        cambio = False
        for a in na.AGUJAS:
            for w in PESOS_POSIBLES:
                if (a in RESTAN and w > 0) or (a not in RESTAN and w < 0):
                    continue
                if w == P.get(a, 0):
                    continue
                Q = dict(P)
                Q[a] = float(w)
                s, _ = puntaje_piso(Q, d, memorias)
                if s > mejor + 1e-4:
                    mejor, P, cambio = s, Q, True
    return P


def calibrar_sesgo(d, memorias, P):
    """El sesgo no cambia el ORDEN; solo decide cuándo una fuerza llega a 'conectar' (>= .80).
    Se elige el sesgo con más recall cuya precisión promedio en 'conectar' sea >= .80."""
    mejor, mejor_prec = None, (-1.0, None)
    for s in np.arange(-0.5, -6.01, -0.5):
        Q = dict(P)
        Q["sesgo"] = float(s)
        prec, rec = [], []
        for nm in memorias:
            y = d[nm]["y"]
            c = 1 / (1 + np.exp(-np.clip(na.piso(_X(d[nm]), Q), -30, 30))) >= na.UMBRAL_CONECTAR
            prec.append((c & (y == 1)).sum() / max(c.sum(), 1))
            rec.append((c & (y == 1)).sum() / max(y.sum(), 1))
        if np.mean(prec) >= 0.80 and (mejor is None or np.mean(rec) > mejor[1]):
            mejor = (float(s), float(np.mean(rec)))
        if np.mean(prec) > mejor_prec[0]:
            mejor_prec = (float(np.mean(prec)), float(s))
    Q = dict(P)
    Q["sesgo"] = mejor[0] if mejor else mejor_prec[1]
    return Q


class _ConPiso:
    """Usa otro piso dentro de un bloque `with` (para las vueltas 'nunca vista')."""

    def __init__(self, P):
        self.P = P

    def __enter__(self):
        self.viejo = dict(na.PISO)
        na.PISO.clear()
        na.PISO.update(self.P)

    def __exit__(self, *a):
        na.PISO.clear()
        na.PISO.update(self.viejo)


# ---------- corrección ----------

def pares_por_recuerdo(pares, y, filas_ok, maximo=None, semilla=0):
    """Índices (sí, no) de pares que comparten recuerdo, usando solo las filas permitidas."""
    por = {}
    for i in np.flatnonzero(filas_ok):
        a, b = pares[i]
        por.setdefault(a, []).append(i)
        por.setdefault(b, []).append(i)
    si, no = [], []
    for idx in por.values():
        ps = [i for i in idx if y[i] == 1]
        ng = [i for i in idx if y[i] == 0]
        for i in ps:
            si.extend([i] * len(ng))
            no.extend(ng)
    si, no = np.array(si, dtype=np.int64), np.array(no, dtype=np.int64)
    if maximo and len(si) > maximo:
        k = np.random.default_rng(semilla).choice(len(si), maximo, replace=False)
        si, no = si[k], no[k]
    return si, no


def filas(d, memorias):
    """Estudio y guardia por memoria. Estudio = pares (sí, no) que comparten recuerdo (la misma
    competencia que después decide). Guardia = 20 % de los recuerdos, nunca estudiados, medida
    con la misma vara (AUC por recuerdo)."""
    estudio, guardias = [], []
    for nm in memorias:
        v = d[nm]
        Z = _X(v)
        y = v["y"]
        es_g = np.array([guardia(f"{nm}:{a}", f"{nm}:{b}") for a, b in v["pares"]])
        si, no = pares_por_recuerdo(v["pares"], y, ~es_g)
        gs, gn = pares_por_recuerdo(v["pares"], y, es_g, maximo=200000)
        estudio.append((nm, Z, si, no))
        guardias.append((nm, Z, gs, gn))
    return estudio, guardias


def entrenar_con(d, memorias, semillas=SEMILLAS):
    E, G = filas(d, memorias)
    ps, infos = [], []
    for s in semillas:
        p, info = na.entrenar(E, G, semilla=s)
        ps.append(p)
        infos.append(info)
    return ps, infos


def examinar(v, p, P_piso=None):
    y = v["y"]
    X = _X(v)
    out = {"pares": int(len(y)), "si_tienen_que_ver_pct": round(float(y.mean()) * 100, 1)}
    out["motor_hoy_conecta_todo"] = pr(np.ones(len(y), bool), y)
    out["regla_jaccard_0.4"] = dict(auc=round(auc(v["jac"], y), 3), **pr(v["jac"] >= 0.4, y))
    zp = na.piso(X, P_piso)
    f_piso = 1 / (1 + np.exp(-np.clip(zp, -30, 30)))
    si, no = pares_por_recuerdo(v["pares"], y, np.ones(len(y), bool), maximo=400000)
    out["piso_a_mano"] = {"auc": round(auc(f_piso, y), 3), "auc_por_recuerdo": round(na.auc_por_recuerdo(zp, si, no), 3),
                          "conectar": pr(f_piso >= na.UMBRAL_CONECTAR, y),
                          "competencia_k5": pr(na.competencia(f_piso, v["pares"], 5), y),
                          "competencia_k10": pr(na.competencia(f_piso, v["pares"], 10), y),
                          "competencia_k20": pr(na.competencia(f_piso, v["pares"], 20), y)}
    if p is not None:
        ps = p if isinstance(p, list) else [p]
        fs = [1 / (1 + np.exp(-np.clip(zp + na.correccion(q, X), -30, 30))) for q in ps]
        aucs = [auc(f, y) for f in fs]
        f = fs[0]
        apr = [na.auc_por_recuerdo(zp + na.correccion(q, X), si, no) for q in ps]
        out["neurona"] = {"auc": round(float(np.mean(aucs)), 3), "auc_semillas": [round(a, 3) for a in aucs],
                          "auc_por_recuerdo": round(float(np.mean(apr)), 3),
                          "auc_por_recuerdo_semillas": [round(a, 3) for a in apr],
                          "conectar": pr(f >= na.UMBRAL_CONECTAR, y),
                          "competencia_k5": pr(na.competencia(f, v["pares"], 5), y),
                          "competencia_k10": pr(na.competencia(f, v["pares"], 10), y),
                          "competencia_k20": pr(na.competencia(f, v["pares"], 20), y)}
    return out


# ---------- examen real: Dennys ----------

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
    mem = corpus.dennys()
    conceptos, sin, cuar = mem["conceptos"], mem["sin"], mem["cuarentena"]
    out = {"recuerdos": len(mem["textos"])}
    variantes = {"completa (texto + tiempo + dims)": (mem["orden"], mem["etiquetas"]),
                 "solo texto (sin tiempo ni dims)": (None, None)}
    for nombre_var, (orden, etq) in variantes.items():
        m = agujas.Memoria(mem["textos"], orden=orden, etiquetas=etq)
        # --- conexiones de hoy ---
        pares = sorted(sin)
        F = m.agujas(pares)
        tipo = np.array([sin[k][0] for k in pares])
        peso = np.array([sin[k][1] for k in pares], dtype=float)
        y = (tipo == "manual").astype(int)
        f_piso = na.fuerza(F, agujas.NOMBRES_TODAS, p=None)
        f = na.fuerza(F, agujas.NOMBRES_TODAS, p=p)
        manual_set = {k for k in pares if sin[k][0] == "manual"}
        cand = set(m.candidatos(rng=np.random.default_rng(0)))
        r = {"fiab_episodio": round(m.fiab_episodio, 3), "fiab_etiquetas": round(m.fiab_etiquetas, 3),
             "manual_que_la_neurona_propondria_sola_pct": round(100 * len(manual_set & cand) / max(len(manual_set), 1), 1),
             "candidatos_propios": len(cand),
             "conexiones_existentes": len(pares), "manual": int(y.sum()),
             "auc_manual_vs_resto": {"peso_del_motor_hoy": round(auc(peso, y), 3),
                                     "piso_a_mano": round(auc(f_piso, y), 3),
                                     "neurona": round(auc(f, y), 3)}}
        # --- Gemini como segundo juez ---
        no_g = sorted(k for k, v in cuar.items() if v[2] == 0 and v[3] != "manual" and "prueba" not in v[0])
        si_h = [k for k in pares if sin[k][0] == "manual"]
        si_g = [k for k in pares if sin[k][0] == "latente_confirmada"]
        Fn = m.agujas(no_g)
        fn_, fpn = na.fuerza(Fn, agujas.NOMBRES_TODAS, p=p), na.fuerza(Fn, agujas.NOMBRES_TODAS, p=None)
        idx = {k: i for i, k in enumerate(pares)}
        fh = f[[idx[k] for k in si_h]]
        fg = f[[idx[k] for k in si_g]]
        fph = f_piso[[idx[k] for k in si_h]]
        r["jueces"] = {
            "n_humano_si": len(si_h), "n_gemini_si": len(si_g), "n_gemini_no": len(no_g),
            "auc_humano_si_vs_gemini_no": {"piso_a_mano": round(auc(np.r_[fph, fpn], np.r_[np.ones(len(fph)), np.zeros(len(fpn))]), 3),
                                           "neurona": round(auc(np.r_[fh, fn_], np.r_[np.ones(len(fh)), np.zeros(len(fn_))]), 3)},
            "auc_gemini_si_vs_gemini_no": {"neurona": round(auc(np.r_[fg, fn_], np.r_[np.ones(len(fg)), np.zeros(len(fn_))]), 3)},
            "fuerza_mediana": {"humano_si": round(float(np.median(fh)), 3), "gemini_si": round(float(np.median(fg)), 3),
                               "gemini_no": round(float(np.median(fn_)), 3)},
        }
        # --- competencia ---
        comp = {}
        ruido = np.random.default_rng(0).uniform(0, 1e-6, len(peso))
        por_tipo_n = {t: int((tipo == t).sum()) for t in set(tipo)}
        for k in (5, 10, 20):
            kn = na.competencia(f, pares, k)
            tn = _topk(f, pares, k)
            tw = _topk(peso + ruido, pares, k)
            comp[f"k{k}"] = {"se_conserva_pct": round(float(kn.mean()) * 100, 1),
                             "manual_conservadas_pct": round(float(kn[y == 1].mean()) * 100, 1),
                             "solo_competencia": {"manual_orden_neurona_pct": round(float(tn[y == 1].mean()) * 100, 1),
                                                  "manual_orden_peso_hoy_pct": round(float(tw[y == 1].mean()) * 100, 1)},
                             "por_tipo_pct": {t: round(float(kn[tipo == t].mean()) * 100, 1)
                                              for t in sorted(por_tipo_n, key=lambda t: -por_tipo_n[t]) if por_tipo_n[t] >= 50}}
        r["competencia"] = comp
        # --- caso Neuro-Visor ---
        caso = "leccion_discrepancia_busquedas_vocabulario_no_estocasticidad"
        if caso in conceptos:
            ic = conceptos.index(caso)
            k10 = na.competencia(f, pares, 10)
            filas_c = []
            for k, (a, b) in enumerate(pares):
                if ic in (a, b):
                    otro = conceptos[b if a == ic else a]
                    filas_c.append({"con": otro, "tipo": str(tipo[k]), "peso_motor": round(float(peso[k]), 2),
                                    "fuerza": round(float(f[k]), 3), "se_queda_k10": bool(k10[k]),
                                    "episodio": round(float(F[k, agujas.NOMBRES.index("episodio")]), 3),
                                    "etiquetas": round(float(F[k, agujas.NOMBRES.index("etiquetas")]), 3)})
            filas_c.sort(key=lambda q: -q["fuerza"])
            for i, q in enumerate(filas_c):
                q["puesto"] = i + 1
            r["caso_neuro_visor"] = {"recuerdo": caso, "conexiones": len(filas_c),
                                     "se_quedan_k10": sum(q["se_queda_k10"] for q in filas_c),
                                     "manual": [q for q in filas_c if q["tipo"] == "manual"],
                                     "top12": filas_c[:12]}
        out[nombre_var] = r
    return out


def main():
    os.makedirs(RES, exist_ok=True)
    t0 = time.time()
    print("1) Memorias de fábrica", flush=True)
    d = construir()
    nombres = list(d)
    print("2) Banco de calibración", flush=True)
    banco = {}
    for nm, v in d.items():
        banco[nm] = {"idioma": v["idioma"], "recuerdos": v["n_recuerdos"], "pares": int(len(v["y"])),
                     "si_pct": round(float(v["y"].mean()) * 100, 1), "palabras_mediana": v["palabras_mediana"],
                     "fiab_episodio": v["fiab_episodio"] if v["tiene_tiempo"] else None,
                     "fiab_etiquetas": v["fiab_etiquetas"] if v["tiene_etiquetas"] else None,
                     "cobertura_candidatos": v["cobertura_candidatos"],
                     "auc_por_aguja": {a: round(auc(v["F"][:, i], v["y"]), 3) for i, a in enumerate(agujas.NOMBRES)}}
    json.dump(banco, open(os.path.join(RES, "banco_calibracion.json"), "w"), indent=1, ensure_ascii=False)
    print("3) Examen 'nunca vista' (piso y corrección hechos SIN la memoria examinada)", flush=True)
    nunca = {}
    for fuera in nombres:
        dentro = [x for x in nombres if x != fuera]
        P = calibrar_sesgo(d, dentro, calibrar_piso(d, dentro))
        with _ConPiso(P):
            ps, infos = entrenar_con(d, dentro)
            ex = examinar(d[fuera], ps)
        ex_archivo = examinar(d[fuera], None)
        nunca[fuera] = {"piso_calibrado_sin_mirarla": {k: P.get(k, 0.0) for k in ["sesgo"] + na.AGUJAS},
                        **ex, "piso_del_archivo_auc": ex_archivo["piso_a_mano"]["auc"],
                        "entrenamiento": infos}
        print(f"  {fuera:12s} jaccard {ex['regla_jaccard_0.4']['auc']}  piso {ex['piso_a_mano']['auc']}/"
              f"{ex['piso_a_mano']['auc_por_recuerdo']}  neurona {ex['neurona']['auc']}/{ex['neurona']['auc_por_recuerdo']}"
              f"  (escalas {[i['escala'] for i in infos]})  "
              f"k10 {ex['neurona']['competencia_k10']}", flush=True)
    json.dump(nunca, open(os.path.join(RES, "examen_nunca_vista.json"), "w"), indent=1, ensure_ascii=False)
    print("4) Fábrica final (8 memorias), pesos congelados", flush=True)
    ps, infos = entrenar_con(d, nombres)
    na.guardar(ps[0], extra={"memorias": nombres, "entrenamiento": infos[0],
                             "pares": {k: int(len(v["y"])) for k, v in d.items()}})
    final = {nm: examinar(v, ps[0]) for nm, v in d.items()}
    json.dump(final, open(os.path.join(RES, "fabrica_final.json"), "w"), indent=1, ensure_ascii=False)
    print(f"  corrección: escala {infos[0]['escala']}, pasos {infos[0]['pasos']}, "
          f"guardia {infos[0]['guardia_por_memoria']}", flush=True)
    print("5) Examen real: memoria de Dennys (nunca vista)", flush=True)
    p = na.cargar()
    assert p is not None, "los pesos recién guardados no cargan"
    den = examen_dennys(p)
    json.dump(den, open(os.path.join(RES, "examen_dennys.json"), "w"), indent=1, ensure_ascii=False)
    for var, r in den.items():
        if not isinstance(r, dict):
            continue
        print(f"  [{var}] fiab tiempo {r['fiab_episodio']} dims {r['fiab_etiquetas']}; manuales que propondría sola "
              f"{r['manual_que_la_neurona_propondria_sola_pct']} % ({r['candidatos_propios']} candidatos)", flush=True)
        print(f"    AUC manual vs resto: {r['auc_manual_vs_resto']}", flush=True)
        print(f"    jueces: {r['jueces']}", flush=True)
        for k, v in r["competencia"].items():
            print(f"    {k}: se conserva {v['se_conserva_pct']} %, manual {v['manual_conservadas_pct']} % "
                  f"(solo competencia: neurona {v['solo_competencia']['manual_orden_neurona_pct']} % vs peso hoy "
                  f"{v['solo_competencia']['manual_orden_peso_hoy_pct']} %)", flush=True)
        if "caso_neuro_visor" in r:
            c = r["caso_neuro_visor"]
            print(f"    Neuro-Visor: se quedan {c['se_quedan_k10']}/{c['conexiones']}; manual: "
                  f"{[(q['puesto'], q['se_queda_k10']) for q in c['manual']]}", flush=True)
    print(f"listo en {round(time.time() - t0)} s", flush=True)


if __name__ == "__main__":
    main()
