"""Paso 2c: examen de orden (entrenamiento) + examen de rescate (validación) en UD PUD, variantes T y C.

Protocolo (umbrales fijados antes): PROTOCOLO.md. No toca el motor ni el repositorio: todo en /tmp y en copias.
- T = motor tal cual. C = control de laboratorio: el sueño sin el bloque «4. Inhibición Lateral» (solo en el hijo).
Reutiliza del Paso 2b el mundo, las pistas, la búsqueda ciega, el piso y el examen de rescate.

Uso:  python examen_orden_rescate.py            (corrida completa, ~25 min con 2 CPU)
      H2C_LIMITE=200 python examen_orden_rescate.py   (prueba en seco: solo comprueba que corre)
"""
import gzip
import hashlib
import inspect
import json
import os
import random
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

AQUI = os.path.dirname(os.path.abspath(__file__))
P2B = os.path.abspath(os.path.join(AQUI, "..", "paso2b_examen_rescate_pud"))
sys.path.insert(0, P2B)
import examen_rescate_pud as b  # noqa: E402  (pone en sys.path la raíz, exp. 16, exp. 18 y paso 2)

v1 = b.v1
PY = sys.executable
TMP = "/tmp/paso2c"
VARIANTES = ("T", "C")
LIMITE = int(os.environ.get("H2C_LIMITE", "0") or 0)
SEMILLA_BOOT = 2026
N_BOOT = 2000

if LIMITE:
    _leer_original = b.leer

    def _leer_limitado(lg):
        frases, sha = _leer_original(lg)
        return frases[:LIMITE], sha

    b.leer = _leer_limitado


# ------------------------------------------------------------------ variante C (solo en el proceso hijo)
def activar_control_sin_inhibicion_lateral():
    import core.memory.consolidation as cons
    src = inspect.getsource(cons.ciclo_sueno_consolidacion)
    viejo = "if energia_total > limite_energia:"
    assert src.count(viejo) == 1, "el bloque de inhibición lateral cambió: revisar el control"
    src = src.replace(viejo, "if False:  # CONTROL 2c (laboratorio): sin inhibición lateral")
    ns = {}
    exec(compile(src, cons.__file__ + "#control_2c", "exec"), cons.__dict__, ns)
    cons.ciclo_sueno_consolidacion = ns["ciclo_sueno_consolidacion"]
    return cons


def hijo_construir(lg, variante_mundo, ruta, modo):
    if modo == "C":
        activar_control_sin_inhibicion_lateral()
    b.hijo_construir(lg, variante_mundo, ruta)


# ------------------------------------------------------------------ utilidades
def parte(doc):
    r = int(hashlib.sha256(("2c|" + doc).encode()).hexdigest(), 16) % 5
    return "guardia" if r == 0 else ("validacion" if r == 1 else "estudio")


def _run(args, env_extra):
    e = dict(os.environ)
    e["HOME"] = os.path.join(TMP, "home")
    e.update(env_extra)
    p = subprocess.run([PY, os.path.abspath(__file__)] + args, env=e, cwd=AQUI, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError("falló %s:\n%s" % (args, p.stderr[-3000:]))


def _mrr(puestos):
    return round(sum(1 / p for p in puestos) / len(puestos), 4) if puestos else None


def _reordenar(A, lista, B, mismo, primero_mismo):
    orden = sorted(range(len(lista)), key=lambda i: ((0 if mismo(A, lista[i]) else 1) if primero_mismo
                                                     else (1 if mismo(A, lista[i]) else 0), i))
    return [lista[i] for i in orden].index(B) + 1


def preguntas_orden(registros, vec, en_D):
    """Pares (A, B) únicos: A ≠ B en el top-5 ciego de una pista de B, con B en la lista del canal 2 de A (≥ 2)."""
    out = {}
    for g in registros:
        B = g["x"]
        for A in [c for c in g["top"][:5] if c != B]:
            lista = [v[0] for v in vec["vecinos"].get(A, {}).get("lista", [])]
            if B not in lista or len(lista) < 2:
                continue
            k = (A, B)
            if k not in out:
                lista_D = [x for x in lista if x in en_D]
                out[k] = {"A": A, "B": B, "puesto": lista.index(B) + 1,
                          "puesto_D": lista_D.index(B) + 1 if B in lista_D else None,
                          "n": len(lista), "lista": lista, "pistas": 0, "B_en_top5": False}
            out[k]["pistas"] += 1
            out[k]["B_en_top5"] = out[k]["B_en_top5"] or (B in g["top"][:5])
    return out


def medir_orden(Q, doc_de):
    def mismo(a, b_):
        return doc_de.get(a) is not None and doc_de.get(a) == doc_de.get(b_)

    qs = list(Q.values())
    n = len(qs)
    if not n:
        return {"preguntas": 0}
    por_parte = {p: [q for q in qs if parte(doc_de[q["B"]]) == p] for p in ("estudio", "validacion", "guardia")}
    por_A = {}
    for q in qs:
        por_A[q["A"]] = por_A.get(q["A"], 0) + 1
    top_A = sorted(por_A.values(), reverse=True)
    # O5a: B frente a un vecino cualquiera de la lista de A
    dif_por_A = {}
    for q in qs:
        base = sum(mismo(q["A"], x) for x in q["lista"]) / len(q["lista"])
        dif_por_A.setdefault(q["A"], []).append((1.0 if mismo(q["A"], q["B"]) else 0.0) - base)
    As = sorted(dif_por_A)
    total = [d for a in As for d in dif_por_A[a]]
    rng = random.Random(SEMILLA_BOOT)
    boots = []
    for _ in range(N_BOOT):
        m = [d for a in (rng.choice(As) for _ in As) for d in dif_por_A[a]]
        boots.append(sum(m) / len(m))
    boots.sort()
    return {
        "preguntas": n,
        "B_distintos": len({q["B"] for q in qs}), "A_distintos": len(por_A),
        "por_parte": {p: {"preguntas": len(v), "B": len({q["B"] for q in v}), "A": len({q["A"] for q in v})}
                      for p, v in por_parte.items()},
        "B_tambien_en_top5": round(sum(q["B_en_top5"] for q in qs) / n, 4),
        "pistas_por_pregunta": round(sum(q["pistas"] for q in qs) / n, 2),
        "share_A_max": round(top_A[0] / n, 4), "share_top3_A": round(sum(top_A[:3]) / n, 4),
        "piso_R@1": round(sum(q["puesto"] == 1 for q in qs) / n, 4),
        "piso_MRR": _mrr([q["puesto"] for q in qs]),
        "azar_MRR_esperado": round(sum(sum(1 / k for k in range(1, q["n"] + 1)) / q["n"] for q in qs) / n, 4),
        "oraculo_MRR": _mrr([_reordenar(q["A"], q["lista"], q["B"], mismo, True) for q in qs]),
        "anti_oraculo_MRR": _mrr([_reordenar(q["A"], q["lista"], q["B"], mismo, False) for q in qs]),
        "frac_mismo_doc_B": round(sum(mismo(q["A"], q["B"]) for q in qs) / n, 4),
        "frac_mismo_doc_vecino_cualquiera": round(sum(sum(mismo(q["A"], x) for x in q["lista"]) / len(q["lista"])
                                                      for q in qs) / n, 4),
        "O5a_diferencia": round(sum(total) / len(total), 4),
        "O5a_IC95": [round(boots[int(0.025 * N_BOOT)], 4), round(boots[int(0.975 * N_BOOT) - 1], 4)],
        "n_vecinos_medio": round(sum(q["n"] for q in qs) / n, 2),
    }


# ------------------------------------------------------------------ un idioma, una variante
def un_trabajo(args):
    modo, lg = args
    d = os.path.join(TMP, modo, lg)
    os.makedirs(d, exist_ok=True)
    frases, sha_corpus = b.leer(lg)
    D = [f for f in frases if not b.en_I(f["doc"])]
    I = [f for f in frases if b.en_I(f["doc"])]
    doc_de = {f["concepto"].lower(): f["doc"] for f in frases}
    en_D = {f["concepto"].lower() for f in D}
    r = {k: os.path.join(d, k + ".db") for k in ("D", "DI")}
    t0 = time.time()
    for v in ("D", "DI"):
        _run(["construir", lg, v, r[v], modo], b.BASE_ENV)
    t_construir = round(time.time() - t0, 1)

    df = {}
    for f in D:
        for u in b.conjunto_unidades(f["contenido"]):
            df[u] = df.get(u, 0) + 1
    unid_I = set()
    for f in I:
        unid_I |= b.conjunto_unidades(f["contenido"])
    todas, brutas = [], 0
    for f in D:
        ps, bb = b.pistas(f, df)
        todas += ps
        brutas += bb
    for p in todas:
        p["elegible_P2"] = not any(u in unid_I for u in p["unidades"])
    pj = os.path.join(d, "pistas.json")
    json.dump(todas, open(pj, "w"), ensure_ascii=False)
    primeros = {f["concepto"].lower() for f in D[:b.N_REPRO]}
    pj_repro = os.path.join(d, "pistas_repro.json")
    json.dump([p for p in todas if p["x"] in primeros], open(pj_repro, "w"), ensure_ascii=False)
    pj_DI = os.path.join(d, "pistas_DI.json")
    json.dump([p for p in todas if p["elegible_P2"]], open(pj_DI, "w"), ensure_ascii=False)

    reps, vecs = {}, {}
    t1 = time.time()
    for nombre, base, pjx in (("D", "D", pj), ("D_repro", "D", pj_repro), ("DI", "DI", pj_DI)):
        sal = os.path.join(d, "rep_%s.json" % nombre)
        _run(["repaso", r[base], pjx, sal], b.ENV_LIMPIO)
        reps[nombre] = json.load(open(sal))
    for base in ("D", "DI"):
        sal = os.path.join(d, "vec_%s.json" % base)
        _run(["vecinos", r[base], sal], b.ENV_LIMPIO)
        vecs[base] = json.load(open(sal))
    t_repaso = round(time.time() - t1, 1)

    # C2: búsqueda invariante en pistas elegibles
    por_clave_D = {(g["x"], g["pista"]): g for g in reps["D"]["registros"]}
    eleg_DI = reps["DI"]["registros"]
    eleg_D = [por_clave_D[(g["x"], g["pista"])] for g in eleg_DI]
    iguales = sum(por_clave_D[(g["x"], g["pista"])]["top"][:5] == g["top"][:5] for g in eleg_DI)
    cambios_tocan_estado = 0
    est_D, est_DI = vecs["D"]["estado"], vecs["DI"]["estado"]
    for g in eleg_DI:
        g0 = por_clave_D[(g["x"], g["pista"])]
        if g0["top"][:5] != g["top"][:5]:
            cambiados = set(g0["top"][:5]) ^ set(g["top"][:5])
            if any(est_D.get(c) != est_DI.get(c) for c in cambiados | {g["x"]}):
                cambios_tocan_estado += 1

    # Examen de orden
    Q = preguntas_orden(reps["D"]["registros"], vecs["D"], en_D)
    orden = medir_orden(Q, doc_de)
    Q_D_el = preguntas_orden(eleg_D, vecs["D"], en_D)
    Q_DI_el = preguntas_orden(eleg_DI, vecs["DI"], en_D)
    o2_igual = sum(1 for k, q in Q_D_el.items() if k in Q_DI_el and Q_DI_el[k]["puesto_D"] == q["puesto_D"])
    o2_solo_DI = len(set(Q_DI_el) - set(Q_D_el))

    # Examen de rescate (el del Paso 2b) + invariancia con puesto relativo a D
    resc = b.medir(reps["D"], vecs["D"], doc_de)
    resc["por_parte"] = {p: sum(parte(doc_de[c["B"]]) == p for c in resc["lista_casos"])
                         for p in ("estudio", "validacion", "guardia")}

    def casos_rel(rep, vec):
        out = {}
        for c in b.medir(rep, vec, doc_de)["lista_casos"]:
            lista = [v[0] for v in vec["vecinos"][c["A"]]["lista"]]
            lista_D = [x for x in lista if x in en_D]
            out[(c["B"], c["pista"])] = (c["A"], lista_D.index(c["B"]) + 1)
        return out

    c1 = casos_rel({"registros": eleg_D}, vecs["D"])
    c2 = casos_rel(reps["DI"], vecs["DI"])
    comunes = set(c1) & set(c2)

    repro_D = [g for g in reps["D"]["registros"] if g["x"] in primeros]
    res = {
        "corpus_sha256": sha_corpus, "recuerdos_D": len(D), "recuerdos_I": len(I),
        "pistas_tras_filtro": len(todas), "pistas_antes_del_filtro": brutas, "pistas_elegibles_C2": len(eleg_DI),
        "sinapsis_filas": {k: len(v["aristas"]) for k, v in vecs.items()},
        "tipos_sinapsis_D": b._contar([a[2] for a in vecs["D"]["aristas"]]),
        "dormidos": {k: sum(e != "activo" for e in v["estado"].values()) for k, v in vecs.items()},
        "D_que_cambian_de_estado_al_entrar_I": sum(1 for c in en_D if est_D.get(c) != est_DI.get(c)),
        "C2_top5_identico": "%d/%d" % (iguales, len(eleg_DI)),
        "C2_frac": round(iguales / len(eleg_DI), 4) if eleg_DI else None,
        "C2_fallos_que_tocan_un_cambio_de_estado": "%d/%d" % (cambios_tocan_estado, len(eleg_DI) - iguales),
        "orden": orden,
        "O2_preguntas_D_elegibles": len(Q_D_el), "O2_iguales": o2_igual,
        "O2_frac": round(o2_igual / len(Q_D_el), 4) if Q_D_el else None,
        "O2_solo_en_DI_frac": round(o2_solo_DI / len(Q_DI_el), 4) if Q_DI_el else None,
        "rescate": resc,
        "R2_casos_comunes": len(comunes), "R2_iguales": sum(c1[k] == c2[k] for k in comunes),
        "R2_solo_D": len(set(c1) - set(c2)), "R2_solo_DI": len(set(c2) - set(c1)),
        "C6": {
            "repaso_repetido_identico": repro_D == reps["D_repro"]["registros"],
            "sha_sin_cambio": all(x["sha_antes"] == x["sha_despues"] for x in list(reps.values()) + list(vecs.values())),
            "copia_ciega_al_terminar": {k: max(x["vista_fin"][k] for x in reps.values())
                                        for k in ("sinapsis", "asociaciones", "emergentes")},
            "vecinos_no_cambia_sinapsis": all(v["sinapsis_antes"] == v["sinapsis_despues"] for v in vecs.values()),
        },
        "segundos": {"construir": t_construir, "repasos_y_vecinos": t_repaso},
    }
    preg = [{k: q[k] for k in ("A", "B", "puesto", "puesto_D", "n", "pistas", "B_en_top5")}
            | {"parte": parte(doc_de[q["B"]]), "mismo_doc": doc_de[q["A"]] == doc_de[q["B"]]} for q in Q.values()]
    print(modo, lg, "listo", round(time.time() - t0, 1), "s", flush=True)
    return res, preg


def puertas(por):
    def todas(f):
        return all(f(v) for v in por.values())

    def o(v):
        return v["orden"]

    def rc(v):
        return v["rescate"]

    return {
        "C2_invariancia_busqueda": todas(lambda v: v["C2_frac"] is not None and v["C2_frac"] >= 0.98),
        "C6_limpieza": todas(lambda v: v["C6"]["repaso_repetido_identico"] and v["C6"]["sha_sin_cambio"]
                             and not any(v["C6"]["copia_ciega_al_terminar"].values())
                             and v["C6"]["vecinos_no_cambia_sinapsis"]),
        "O1_volumen": todas(lambda v: o(v)["preguntas"] > 0
                            and o(v)["por_parte"]["estudio"]["preguntas"] >= 300
                            and o(v)["por_parte"]["estudio"]["B"] >= 150
                            and o(v)["por_parte"]["estudio"]["A"] >= 100
                            and o(v)["por_parte"]["validacion"]["preguntas"] >= 75
                            and o(v)["por_parte"]["guardia"]["preguntas"] >= 75),
        "O2_invariancia_respuesta": todas(lambda v: v["O2_frac"] is not None and v["O2_frac"] >= 0.98
                                          and v["O2_solo_en_DI_frac"] is not None and v["O2_solo_en_DI_frac"] <= 0.02),
        "O3_hubs": todas(lambda v: o(v)["preguntas"] > 0 and o(v)["share_A_max"] <= 0.10
                         and o(v)["share_top3_A"] <= 0.25),
        "O4_margen": todas(lambda v: o(v)["preguntas"] > 0 and o(v)["piso_R@1"] <= 0.80),
        "O5_validez": todas(lambda v: o(v)["preguntas"] > 0 and o(v)["O5a_diferencia"] > 0 and o(v)["O5a_IC95"][0] > 0
                            and o(v)["oraculo_MRR"] > o(v)["piso_MRR"] > o(v)["anti_oraculo_MRR"]),
        "R1_volumen": todas(lambda v: rc(v)["casos"] >= 30 and rc(v)["B_distintos"] >= 20),
        "R2_invariancia_respuesta": todas(lambda v: v["R2_casos_comunes"] >= 1
                                          and v["R2_iguales"] >= 0.98 * v["R2_casos_comunes"]),
        "R3_hubs": todas(lambda v: rc(v)["casos"] > 0 and rc(v)["share_A_max"] <= 0.10
                         and rc(v)["share_top3_A"] <= 0.25),
        "R4_margen": todas(lambda v: rc(v)["casos"] > 0 and rc(v)["piso_R@1"] <= 0.80),
        "R5_validez": todas(lambda v: rc(v)["casos"] > 0
                            and rc(v)["frac_mismo_doc_en_casos"] > rc(v)["frac_mismo_doc_en_aristas"]
                            and rc(v)["oraculo_MRR"] > rc(v)["piso_MRR"] > rc(v)["anti_oraculo_MRR"]),
    }


def main():
    t0 = time.time()
    b.descargar()
    if os.path.exists(TMP):
        shutil.rmtree(TMP)
    os.makedirs(os.path.join(TMP, "home"))
    trabajos = [(m, lg) for m in VARIANTES for lg in b.IDIOMAS]
    with ThreadPoolExecutor(max_workers=2) as ex:
        salidas = dict(zip(trabajos, ex.map(un_trabajo, trabajos)))
    out = {"protocolo": "PROTOCOLO.md", "limite_prueba_en_seco": LIMITE or None,
           "commit": subprocess.run(["git", "-C", b.RAIZ, "rev-parse", "HEAD"], capture_output=True,
                                    text=True).stdout.strip(),
           "atribucion": "Universal Dependencies PUD (es, en, zh, ja), CC BY-SA 3.0", "variantes": {}}
    preguntas = {}
    for m in VARIANTES:
        por = {lg: salidas[(m, lg)][0] for lg in b.IDIOMAS}
        p = puertas(por)
        orden_ok = all(p[k] for k in ("C2_invariancia_busqueda", "C6_limpieza", "O1_volumen",
                                      "O2_invariancia_respuesta", "O3_hubs", "O4_margen", "O5_validez"))
        resc_ok = all(p[k] for k in ("C2_invariancia_busqueda", "C6_limpieza", "R1_volumen",
                                     "R2_invariancia_respuesta", "R3_hubs", "R4_margen", "R5_validez"))
        out["variantes"][m] = {"puertas": p, "orden_valido": orden_ok, "rescate_valido": resc_ok, "por_idioma": por}
        preguntas[m] = {lg: salidas[(m, lg)][1] for lg in b.IDIOMAS}
    out["segundos"] = round(time.time() - t0, 1)
    os.makedirs(os.path.join(AQUI, "resultados"), exist_ok=True)
    sufijo = "_prueba_en_seco" if LIMITE else ""
    json.dump(out, open(os.path.join(AQUI, "resultados", "examen_2c%s.json" % sufijo), "w"),
              ensure_ascii=False, indent=1)
    with gzip.open(os.path.join(AQUI, "resultados", "preguntas_orden%s.json.gz" % sufijo), "wt",
                   encoding="utf-8") as f:
        json.dump(preguntas, f, ensure_ascii=False)
    for m in VARIANTES:
        print(m, json.dumps(out["variantes"][m]["puertas"]), "orden_valido", out["variantes"][m]["orden_valido"],
              "rescate_valido", out["variantes"][m]["rescate_valido"], flush=True)
    print("FIN", out["segundos"])


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "construir":
        hijo_construir(*sys.argv[2:6])
    elif len(sys.argv) > 1 and sys.argv[1] == "repaso":
        b.hijo_repaso(*sys.argv[2:5])
    elif len(sys.argv) > 1 and sys.argv[1] == "vecinos":
        v1.hijo_vecinos(*sys.argv[2:4])
    else:
        main()
