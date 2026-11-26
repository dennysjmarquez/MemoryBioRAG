"""Paso 2b — examen de rescate v2 sobre UD PUD (PROTOCOLO_V2.md, puertas fijadas antes de medir).

Uso:  python examen_rescate_pud.py        → corre todo en /tmp, escribe resultados/examen_pud.json
      (internos) construir <idioma> <D|DI> <ruta> · repaso <base> <pistas.json> <salida.json>
                 vecinos <base> <salida.json>

No toca el motor del repo ni ninguna base real. El corpus se descarga de GitHub a /tmp/pud (no se sube al repo).
"""
import contextlib
import glob
import hashlib
import io
import json
import os
import random
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import time
import unicodedata
import urllib.request
from concurrent.futures import ThreadPoolExecutor

AQUI = os.path.dirname(os.path.abspath(__file__))
V1 = os.path.abspath(os.path.join(AQUI, "..", "paso2_examen_rescate"))
E1 = os.path.abspath(os.path.join(AQUI, "..", "..", "experimento_18_consolidacion_en_el_sueno"))
EXP16 = os.path.abspath(os.path.join(AQUI, "..", "..", "experimento_16_protocolo_ns1_sintetico"))
RAIZ = os.path.abspath(os.path.join(AQUI, "..", "..", "..", ".."))
for p in (RAIZ, EXP16, E1, V1):
    sys.path.insert(0, p)

import e1_repaso  # noqa: E402  unidades Unicode y entorno limpio
import examen_rescate as v1  # noqa: E402  copia limpia, piso (vecinos), guardia

PY = sys.executable
TMP = "/tmp/exp18_rescate_pud"
PUD = "/tmp/pud"
IDIOMAS = {"es": "Spanish", "en": "English", "zh": "Chinese", "ja": "Japanese"}
SUENOS = (1, 2, 3)
NIVELES = (3, 2, 1)
DF_MAX = 10           # filtro de pistas sin contenido: cada unidad en ≤ 10 recuerdos del mundo
N_REPRO = 150         # P6: segundo repaso sobre los primeros 150 B
CADA = 50
BASE_ENV = {"BIORAG_WORDNET_ENABLED": "0", "BIORAG_NO_LOG": "1", "PYTHONHASHSEED": "18"}
ENV_LIMPIO = dict(BASE_ENV, **e1_repaso.ENTORNO_LIMPIO)


# ------------------------------------------------------------------ corpus
def descargar():
    os.makedirs(PUD, exist_ok=True)
    for nombre in IDIOMAS.values():
        carpeta = os.path.join(PUD, "UD_%s-PUD-master" % nombre)
        if glob.glob(os.path.join(carpeta, "*.conllu")):
            continue
        url = "https://codeload.github.com/UniversalDependencies/UD_%s-PUD/tar.gz/refs/heads/master" % nombre
        tgz = os.path.join(PUD, nombre + ".tgz")
        urllib.request.urlretrieve(url, tgz)
        with tarfile.open(tgz) as t:
            t.extractall(PUD)


def leer(lg):
    f = glob.glob(os.path.join(PUD, "UD_%s-PUD-master" % IDIOMAS[lg], "*.conllu"))[0]
    doc, sid, out = None, None, []
    for line in open(f, encoding="utf-8"):
        if line.startswith("# newdoc id"):
            doc = line.split("=", 1)[1].strip()
        elif line.startswith("# sent_id"):
            sid = line.split("=", 1)[1].strip()
        elif line.startswith("# text ="):
            out.append({"concepto": sid, "doc": doc, "contenido": line.split("=", 1)[1].strip()})
    return out, v1._sha(f)


def en_I(doc):
    return int(hashlib.sha256(doc.encode()).hexdigest(), 16) % 5 == 0


def conjunto_unidades(texto):
    return {u[2] for u in e1_repaso.unidades(texto)[0]}


# ------------------------------------------------------------------ pistas (filtro sin listas)
def pistas(ev, df):
    textos = []
    for u in e1_repaso.unidades(ev["contenido"])[0]:
        if u[2] not in textos:
            textos.append(u[2])
    out, vistas, brutas = [], set(), 0
    for s in SUENOS:
        for nivel in NIVELES:
            if len(textos) < nivel:
                continue
            semilla = int(hashlib.sha256(("%s|%d|%d" % (ev["concepto"], s, nivel)).encode()).hexdigest(), 16)
            idx = sorted(random.Random(semilla).sample(range(len(textos)), nivel))
            unid = [textos[i] for i in idx]
            p = " ".join(unid)
            if p in vistas:
                continue
            vistas.add(p)
            brutas += 1
            if all(df.get(u, 0) <= DF_MAX for u in unid):
                out.append({"x": ev["concepto"].lower(), "s": s, "nivel": nivel, "pista": p, "unidades": unid})
    return out, brutas


# ------------------------------------------------------------------ hijos
def hijo_construir(lg, variante, ruta):
    import construir as c16
    assert ruta.startswith("/tmp/")
    frases, _ = leer(lg)
    D = [f for f in frases if not en_I(f["doc"])]
    I = [f for f in frases if en_I(f["doc"])]
    for ext in ("", "-wal", "-shm"):
        if os.path.exists(ruta + ext):
            os.remove(ruta + ext)
    cer = c16.abrir(ruta)
    lotes = [D] + ([I] if variante == "DI" else [])
    for lote in lotes:
        for k, f in enumerate(lote, 1):
            with contextlib.redirect_stdout(io.StringIO()):
                c16.guardar(cer, {"concepto": f["concepto"], "contenido": f["contenido"], "syn": "",
                                  "cat": "General", "dims": {}, "sk": ""})
            if k % CADA == 0:
                c16.dormir(cer)
        c16.dormir(cer)
    with contextlib.redirect_stdout(io.StringIO()):
        cer.conn.commit()
        cer.cerrar_sistema()
    con = sqlite3.connect(ruta)
    con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    con.close()


def hijo_repaso(base, pistas_json, salida):
    v1._entorno_ok()
    sha0 = v1._sha(base)
    vista = v1._copia(base, "rescate_pud_vista_")
    con = sqlite3.connect(vista)
    con.execute("DELETE FROM sinapsis")
    con.execute("DELETE FROM sinapsis_latentes")
    con.execute("UPDATE largo_plazo SET asociaciones = ''")
    con.execute("DELETE FROM largo_plazo_dimensiones WHERE dimension_id IN "
                "(SELECT id FROM dimensiones_semanticas WHERE auto_generada = 1)")
    con.commit()
    con.close()
    from core.memory_store import SQLiteMemoryBioRAG
    with contextlib.redirect_stdout(io.StringIO()):
        cer = SQLiteMemoryBioRAG(db_path=vista)
    regs = []
    for p in json.load(open(pistas_json)):
        with contextlib.redirect_stdout(io.StringIO()):
            res, _ = cer.buscar_por_frase(p["pista"], limite=6, profundidad="profundo", usar_inferencia=False,
                                          context_window=0, ignore_peso_sinaptico=True)
        regs.append(dict(p, top=[r[0] for r in (res or [])][:6]))
    q = lambda sql: cer.cursor.execute(sql).fetchone()[0]  # noqa: E731
    fin = {"sinapsis": q("SELECT COUNT(*) FROM sinapsis"),
           "asociaciones": q("SELECT COUNT(*) FROM largo_plazo WHERE asociaciones <> ''"),
           "emergentes": q("SELECT COUNT(*) FROM largo_plazo_dimensiones WHERE dimension_id IN "
                           "(SELECT id FROM dimensiones_semanticas WHERE auto_generada = 1)")}
    with contextlib.redirect_stdout(io.StringIO()):
        cer.cerrar_sistema()
    json.dump({"registros": regs, "vista_fin": fin, "sha_antes": sha0, "sha_despues": v1._sha(base)},
              open(salida, "w"), ensure_ascii=False)


# ------------------------------------------------------------------ análisis
def _run(args, env_extra):
    e = dict(os.environ)
    e["HOME"] = os.path.join(TMP, "home")
    e.update(env_extra)
    p = subprocess.run([PY] + args, env=e, cwd=AQUI, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError("falló %s:\n%s" % (args, p.stderr[-3000:]))


def medir(rep, vec, doc_de):
    def mismo(a, b):
        return doc_de.get(a) is not None and doc_de.get(a) == doc_de.get(b)

    cs = []
    for g in rep["registros"]:
        if g["x"] in g["top"][:5]:
            continue
        for A in [c for c in g["top"] if c != g["x"]][:5]:
            lista = [v[0] for v in vec["vecinos"].get(A, {}).get("lista", [])]
            if g["x"] in lista:
                cs.append({"B": g["x"], "A": A, "s": g["s"], "nivel": g["nivel"], "pista": g["pista"],
                           "puesto": lista.index(g["x"]) + 1, "n": len(lista), "lista": lista,
                           "visible": g["x"] in vec["vecinos"][A]["visibles"]})
                break

    def reordenar(c, primero_mismo):
        orden = sorted(range(len(c["lista"])),
                       key=lambda i: ((0 if mismo(c["A"], c["lista"][i]) else 1) if primero_mismo
                                      else (1 if mismo(c["A"], c["lista"][i]) else 0), i))
        return [c["lista"][i] for i in orden].index(c["B"]) + 1

    pares = {frozenset((o, d)) for o, d, _, _ in vec["aristas"] if o != d}
    n, por_A = len(cs), {}
    for c in cs:
        por_A[c["A"]] = por_A.get(c["A"], 0) + 1
    top_A = sorted(por_A.values(), reverse=True)
    regs = rep["registros"]
    return {
        "pistas_buscadas": len(regs),
        "pistas_B_fuera_del_top5": sum(g["x"] not in g["top"][:5] for g in regs),
        "casos": n,
        "B_distintos": len({c["B"] for c in cs}),
        "B_distintos_guardia": len({c["B"] for c in cs if v1.en_guardia(c["B"])}),
        "casos_guardia": sum(v1.en_guardia(c["B"]) for c in cs),
        "casos_por_nivel": {str(L): sum(c["nivel"] == L for c in cs) for L in NIVELES},
        "piso_R@1": round(sum(c["puesto"] == 1 for c in cs) / n, 4) if n else None,
        "piso_visible_en_canal2": round(sum(c["visible"] for c in cs) / n, 4) if n else None,
        "piso_MRR": v1._mrr([c["puesto"] for c in cs]),
        "azar_MRR_esperado": round(sum(sum(1 / k for k in range(1, c["n"] + 1)) / c["n"] for c in cs) / n, 4)
        if n else None,
        "oraculo_MRR": v1._mrr([reordenar(c, True) for c in cs]),
        "anti_oraculo_MRR": v1._mrr([reordenar(c, False) for c in cs]),
        "frac_mismo_doc_en_casos": round(sum(mismo(c["A"], c["B"]) for c in cs) / n, 4) if n else None,
        "frac_mismo_doc_en_aristas": round(sum(mismo(*tuple(p)) for p in pares) / len(pares), 4) if pares else None,
        "aristas_no_dirigidas": len(pares),
        "share_A_max": round(top_A[0] / n, 4) if n else None,
        "share_top3_A": round(sum(top_A[:3]) / n, 4) if n else None,
        "n_vecinos_medio": round(sum(c["n"] for c in cs) / n, 2) if n else None,
        "lista_casos": [{k: c[k] for k in ("B", "A", "s", "nivel", "pista", "puesto", "n", "visible")} for c in cs],
    }


def un_idioma(lg):
    d = os.path.join(TMP, lg)
    os.makedirs(d, exist_ok=True)
    frases, sha_corpus = leer(lg)
    D = [f for f in frases if not en_I(f["doc"])]
    I = [f for f in frases if en_I(f["doc"])]
    doc_de = {f["concepto"].lower(): f["doc"] for f in frases}
    r = {k: os.path.join(d, k + ".db") for k in ("D", "DI")}
    t0 = time.time()
    for v in ("D", "DI"):
        _run(["examen_rescate_pud.py", "construir", lg, v, r[v]], BASE_ENV)
    t_construir = round(time.time() - t0, 1)

    # filtro: presencia de cada unidad en el mundo D; las unidades que aparecen en algún I marcan la pista
    # como no elegible para P2 (la NORMA MÁXIMA solo habla de I que no contienen la consulta)
    df = {}
    for f in D:
        for u in conjunto_unidades(f["contenido"]):
            df[u] = df.get(u, 0) + 1
    unid_I = set()
    for f in I:
        unid_I |= conjunto_unidades(f["contenido"])
    todas, brutas = [], 0
    for f in D:
        ps, b = pistas(f, df)
        todas += ps
        brutas += b
    for p in todas:
        p["elegible_P2"] = not any(u in unid_I for u in p["unidades"])
    pj = os.path.join(d, "pistas.json")
    json.dump(todas, open(pj, "w"), ensure_ascii=False)
    primeros = {f["concepto"].lower() for f in D[:N_REPRO]}
    pj_repro = os.path.join(d, "pistas_repro.json")
    json.dump([p for p in todas if p["x"] in primeros], open(pj_repro, "w"), ensure_ascii=False)
    pj_DI = os.path.join(d, "pistas_DI.json")
    json.dump([p for p in todas if p["elegible_P2"]], open(pj_DI, "w"), ensure_ascii=False)

    reps, vecs = {}, {}
    t1 = time.time()
    for nombre, base, pjx in (("D", "D", pj), ("D_repro", "D", pj_repro), ("DI", "DI", pj_DI)):
        sal = os.path.join(d, "rep_%s.json" % nombre)
        _run(["examen_rescate_pud.py", "repaso", r[base], pjx, sal], ENV_LIMPIO)
        reps[nombre] = json.load(open(sal))
    for base in ("D", "DI"):
        sal = os.path.join(d, "vec_%s.json" % base)
        _run(["examen_rescate_pud.py", "vecinos", r[base], sal], ENV_LIMPIO)
        vecs[base] = json.load(open(sal))
    t_repaso = round(time.time() - t1, 1)

    ex = medir(reps["D"], vecs["D"], doc_de)
    # P2: misma pista elegible en D y en DI
    por_clave_D = {(g["x"], g["pista"]): g for g in reps["D"]["registros"]}
    elegibles = [g for g in reps["DI"]["registros"]]
    iguales = sum(por_clave_D[(g["x"], g["pista"])]["top"][:5] == g["top"][:5] for g in elegibles)
    # P2b: casos sobre pistas elegibles, D frente a DI
    rep_D_eleg = {"registros": [por_clave_D[(g["x"], g["pista"])] for g in elegibles]}
    c1 = {(c["B"], c["pista"]): (c["A"], c["puesto"]) for c in medir(rep_D_eleg, vecs["D"], doc_de)["lista_casos"]}
    c2 = {(c["B"], c["pista"]): (c["A"], c["puesto"]) for c in medir(reps["DI"], vecs["DI"], doc_de)["lista_casos"]}
    comunes = set(c1) & set(c2)
    repro_D = [g for g in reps["D"]["registros"] if g["x"] in primeros]
    tam_doc = {}
    for f in D:
        tam_doc[f["doc"]] = tam_doc.get(f["doc"], 0) + 1
    return {
        "corpus_sha256": sha_corpus,
        "recuerdos_D": len(D), "recuerdos_I": len(I),
        "B_sin_compañero_de_documento": sum(tam_doc[f["doc"]] == 1 for f in D),
        "pistas_antes_del_filtro": brutas, "pistas_tras_filtro": len(todas),
        "pistas_elegibles_P2": len(elegibles),
        "sinapsis_filas": {k: len(v["aristas"]) for k, v in vecs.items()},
        "tipos_sinapsis_D": _contar([a[2] for a in vecs["D"]["aristas"]]),
        "dormidos": {k: sum(e != "activo" for e in v["estado"].values()) for k, v in vecs.items()},
        "examen_D": ex,
        "P2_top5_identico": "%d/%d" % (iguales, len(elegibles)),
        "P2_frac": round(iguales / len(elegibles), 4) if elegibles else None,
        "P2b_casos_comunes": len(comunes), "P2b_iguales": sum(c1[k] == c2[k] for k in comunes),
        "P2b_solo_en_D": len(set(c1) - set(c2)), "P2b_solo_en_DI": len(set(c2) - set(c1)),
        "P6": {
            "repaso_repetido_identico": repro_D == reps["D_repro"]["registros"],
            "sha_sin_cambio": all(x["sha_antes"] == x["sha_despues"] for x in list(reps.values()) + list(vecs.values())),
            "copia_ciega_al_terminar": {k: max(x["vista_fin"][k] for x in reps.values())
                                        for k in ("sinapsis", "asociaciones", "emergentes")},
            "vecinos_no_cambia_sinapsis": all(v["sinapsis_antes"] == v["sinapsis_despues"] for v in vecs.values()),
        },
        "segundos": {"construir": t_construir, "repasos_y_vecinos": t_repaso},
    }


def _contar(xs):
    out = {}
    for x in xs:
        out[x] = out.get(x, 0) + 1
    return out


def puertas(por):
    def todas(f):
        return all(f(v) for v in por.values())

    def e(v):
        return v["examen_D"]

    return {
        "P1_casos": todas(lambda v: e(v)["casos"] >= 100 and e(v)["B_distintos"] >= 40
                          and e(v)["B_distintos_guardia"] >= 8),
        "P2_invariancia_pregunta": todas(lambda v: v["P2_frac"] is not None and v["P2_frac"] >= 0.98),
        "P2b_invariancia_respuesta": todas(lambda v: v["P2b_casos_comunes"] > 0
                                           and v["P2b_iguales"] >= 0.98 * v["P2b_casos_comunes"]),
        "P3_hubs": todas(lambda v: e(v)["casos"] > 0 and e(v)["share_A_max"] <= 0.10 and e(v)["share_top3_A"] <= 0.25),
        "P4_margen": todas(lambda v: e(v)["casos"] > 0 and e(v)["piso_R@1"] <= 0.80),
        "P5_validez": todas(lambda v: e(v)["casos"] > 0
                            and e(v)["frac_mismo_doc_en_casos"] > e(v)["frac_mismo_doc_en_aristas"]
                            and e(v)["oraculo_MRR"] > e(v)["piso_MRR"] > e(v)["anti_oraculo_MRR"]),
        "P6_limpieza": todas(lambda v: v["P6"]["repaso_repetido_identico"] and v["P6"]["sha_sin_cambio"]
                             and not any(v["P6"]["copia_ciega_al_terminar"].values())
                             and v["P6"]["vecinos_no_cambia_sinapsis"]),
    }


def main():
    t0 = time.time()
    descargar()
    if os.path.exists(TMP):
        shutil.rmtree(TMP)
    os.makedirs(os.path.join(TMP, "home"))
    with ThreadPoolExecutor(max_workers=2) as ex:
        res = dict(zip(IDIOMAS, ex.map(un_idioma, IDIOMAS)))
    p = puertas(res)
    out = {"protocolo": "PROTOCOLO_V2.md", "puertas": p, "examen_sirve": all(p.values()),
           "atribucion": "Universal Dependencies PUD (es, en, zh, ja), CC BY-SA 3.0",
           "por_idioma": res, "segundos": round(time.time() - t0, 1)}
    os.makedirs(os.path.join(AQUI, "resultados"), exist_ok=True)
    json.dump(out, open(os.path.join(AQUI, "resultados", "examen_pud.json"), "w"), ensure_ascii=False, indent=1)
    resumen = {lg: {k: v["examen_D"][k] for k in ("casos", "B_distintos", "B_distintos_guardia", "piso_R@1",
                                                  "piso_MRR", "oraculo_MRR", "anti_oraculo_MRR",
                                                  "frac_mismo_doc_en_casos", "frac_mismo_doc_en_aristas")}
               for lg, v in res.items()}
    print(json.dumps({"puertas": p, "resumen": resumen}, ensure_ascii=False, indent=1))
    print("FIN", 0 if all(p.values()) else 1)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "construir":
        hijo_construir(*sys.argv[2:5])
    elif len(sys.argv) > 1 and sys.argv[1] == "repaso":
        hijo_repaso(*sys.argv[2:5])
    elif len(sys.argv) > 1 and sys.argv[1] == "vecinos":
        v1.hijo_vecinos(*sys.argv[2:4])
    else:
        main()
