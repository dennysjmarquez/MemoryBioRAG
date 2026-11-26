"""Paso 2 — examen de rescate en el laboratorio (PROTOCOLO_EXAMEN_RESCATE.md, puertas fijadas antes).

Uso:  python examen_rescate.py            → corre todo en /tmp, escribe resultados/examen.json
      (internos) python examen_rescate.py repaso  <base> <eventos.json> <salida.json>
                 python examen_rescate.py vecinos <base> <salida.json>

No toca el motor del repo ni ninguna base real. Cada proceso hijo lee el entorno al importar el motor,
por eso construcción, repaso ciego y consulta de vecinos corren aparte.
"""
import contextlib
import hashlib
import io
import json
import os
import random
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor

AQUI = os.path.dirname(os.path.abspath(__file__))
E1 = os.path.abspath(os.path.join(AQUI, "..", "..", "experimento_18_consolidacion_en_el_sueno"))
EXP16 = os.path.abspath(os.path.join(AQUI, "..", "..", "experimento_16_protocolo_ns1_sintetico"))
RAIZ = os.path.abspath(os.path.join(AQUI, "..", "..", "..", ".."))
for p in (RAIZ, EXP16, E1):
    sys.path.insert(0, p)

import e1_medir  # noqa: E402  (construcción del mundo, igual que E1)
import e1_mundo  # noqa: E402
import e1_repaso  # noqa: E402  (unidades Unicode, entorno limpio)
from mundos_espejo import etiqueta  # noqa: E402

PY = sys.executable
TMP = "/tmp/exp18_rescate"
SUENOS = (1, 2, 3, 4, 5)
NIVELES = (3, 2, 1)          # unidades por pista: 3 fácil … 1 difícil
ENV_LIMPIO = dict(e1_medir.BASE_ENV, **e1_repaso.ENTORNO_LIMPIO)


# ------------------------------------------------------------------ pistas
def _nk(s):
    return unicodedata.normalize("NFKC", s).casefold()


def pistas_dispersas(concepto, contenido):
    """Pistas de B: muestras dispersas de sus unidades Unicode, sin las del nombre, en 3 niveles × 5 sueños."""
    us, _ = e1_repaso.unidades(contenido)
    del_nombre = {u[2] for u in e1_repaso.unidades(concepto.replace("_", " "))[0]}
    textos = []
    for u in us:
        if u[2] not in del_nombre and u[2] not in textos:
            textos.append(u[2])
    out, vistas = [], set()
    for s in SUENOS:
        for nivel in NIVELES:
            if len(textos) < nivel:
                continue
            semilla = int(hashlib.sha256(("%s|%d|%d" % (concepto, s, nivel)).encode()).hexdigest(), 16)
            idx = sorted(random.Random(semilla).sample(range(len(textos)), nivel))
            p = " ".join(textos[i] for i in idx)
            if p not in vistas:
                vistas.add(p)
                out.append({"s": s, "nivel": nivel, "pista": p})
    return out


def en_guardia(b):
    return int(hashlib.sha256(b.encode()).hexdigest(), 16) % 5 == 0


# ------------------------------------------------------------------ hijos
def _sha(ruta):
    return e1_repaso.sha(ruta)


def _entorno_ok():
    for k, v in e1_repaso.ENTORNO_LIMPIO.items():
        assert os.environ.get(k) == v, "falta el entorno limpio: %s" % k


def _copia(original, prefijo):
    d = tempfile.mkdtemp(prefix=prefijo, dir="/tmp")
    ruta = os.path.join(d, "c.db")
    src = sqlite3.connect("file:%s?mode=ro" % original, uri=True)
    dst = sqlite3.connect(ruta)
    src.backup(dst)
    src.close()
    dst.close()
    return ruta


def hijo_repaso(base, eventos_json, salida):
    """Búsqueda ciega sobre la copia limpia A4 (igual que e1_repaso), con las pistas dispersas."""
    _entorno_ok()
    sha0 = _sha(base)
    vista = _copia(base, "rescate_vista_")
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
    for ev in json.load(open(eventos_json)):
        x = ev["concepto"].lower().replace(" ", "_")
        for p in pistas_dispersas(ev["concepto"], ev["contenido"]):
            with contextlib.redirect_stdout(io.StringIO()):
                res, _ = cer.buscar_por_frase(p["pista"], limite=6, profundidad="profundo", usar_inferencia=False,
                                              context_window=0, ignore_peso_sinaptico=True)
            regs.append(dict(p, x=x, top=[r[0] for r in (res or [])][:6]))
    q = lambda sql: cer.cursor.execute(sql).fetchone()[0]  # noqa: E731
    fin = {"sinapsis": q("SELECT COUNT(*) FROM sinapsis"),
           "asociaciones": q("SELECT COUNT(*) FROM largo_plazo WHERE asociaciones <> ''"),
           "emergentes": q("SELECT COUNT(*) FROM largo_plazo_dimensiones WHERE dimension_id IN "
                           "(SELECT id FROM dimensiones_semanticas WHERE auto_generada = 1)")}
    with contextlib.redirect_stdout(io.StringIO()):
        cer.cerrar_sistema()
    json.dump({"registros": regs, "vista_fin": fin, "sha_antes": sha0, "sha_despues": _sha(base)},
              open(salida, "w"), ensure_ascii=False)


def hijo_vecinos(base, salida):
    """El PISO: el orden a mano del canal 2, pedido al motor real sobre una copia del grafo completo."""
    _entorno_ok()
    sha0 = _sha(base)
    ruta = _copia(base, "rescate_vecinos_")
    from core.memory_store import SQLiteMemoryBioRAG
    with contextlib.redirect_stdout(io.StringIO()):
        cer = SQLiteMemoryBioRAG(db_path=ruta)
    n0 = cer.cursor.execute("SELECT COUNT(*) FROM sinapsis").fetchone()[0]
    nombres = [r[0] for r in cer.cursor.execute("SELECT concepto FROM largo_plazo ORDER BY concepto")]
    out = {}
    for n in nombres:
        completa = cer.obtener_asociaciones_enriquecidas([n], top_vecinos=10 ** 6).get(n, [])
        visibles = cer.obtener_asociaciones_enriquecidas([n]).get(n, [])
        out[n] = {"lista": [[a["concepto"], a["tipo_sinapsis"], a["fuerza_arista"]] for a in completa],
                  "visibles": [a["concepto"] for a in visibles]}
    aristas = [list(r) for r in cer.cursor.execute(
        "SELECT origen, destino, tipo, peso FROM sinapsis ORDER BY origen, destino")]
    n1 = cer.cursor.execute("SELECT COUNT(*) FROM sinapsis").fetchone()[0]
    estado = dict(cer.cursor.execute("SELECT concepto, estado FROM largo_plazo"))
    with contextlib.redirect_stdout(io.StringIO()):
        cer.cerrar_sistema()
    json.dump({"vecinos": out, "aristas": aristas, "estado": estado, "sinapsis_antes": n0, "sinapsis_despues": n1,
               "sha_antes": sha0, "sha_despues": _sha(base)}, open(salida, "w"), ensure_ascii=False)


# ------------------------------------------------------------------ análisis
def _run(args, env_extra):
    e = dict(os.environ)
    e["HOME"] = os.path.join(TMP, "home")
    e.update(env_extra)
    p = subprocess.run([PY] + args, env=e, cwd=AQUI, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError("falló %s:\n%s" % (args, p.stderr[-3000:]))


def _indices():
    return {e1_mundo.nombre(i): i for i in range(24)}


def _lab(a, b, idx):
    if a in idx and b in idx:
        return etiqueta(idx[a], idx[b])
    return "irr"


def casos(rep, vec):
    out = []
    for g in rep["registros"]:
        if g["x"] in g["top"][:5]:
            continue
        for A in [c for c in g["top"] if c != g["x"]][:5]:
            lista = [v[0] for v in vec["vecinos"].get(A, {}).get("lista", [])]
            if g["x"] in lista:
                out.append({"B": g["x"], "A": A, "s": g["s"], "nivel": g["nivel"], "pista": g["pista"],
                            "puesto": lista.index(g["x"]) + 1, "n": len(lista), "lista": lista,
                            "visible": g["x"] in vec["vecinos"][A]["visibles"]})
                break
    return out


def _mrr(puestos):
    return round(sum(1 / p for p in puestos) / len(puestos), 4) if puestos else None


def medir_examen(rep, vec):
    idx = _indices()
    cs = casos(rep, vec)
    rango = {"pos": 0, "puente": 1, "neg": 2, "irr": 2}
    anti = {"pos": 2, "puente": 1, "neg": 0, "irr": 0}

    def reordenar(c, clave):
        orden = sorted(range(len(c["lista"])), key=lambda i: (clave[_lab(c["A"], c["lista"][i], idx)], i))
        return [c["lista"][i] for i in orden].index(c["B"]) + 1

    pares = {}
    for o, d, tipo, peso in vec["aristas"]:
        if o != d:
            pares[frozenset((o, d))] = _lab(o, d, idx)
    frac_rel_grafo = (sum(v in ("pos", "puente") for v in pares.values()) / len(pares)) if pares else None
    frac_rel_casos = (sum(_lab(c["A"], c["B"], idx) in ("pos", "puente") for c in cs) / len(cs)) if cs else None
    por_A = {}
    for c in cs:
        por_A[c["A"]] = por_A.get(c["A"], 0) + 1
    top_A = sorted(por_A.values(), reverse=True)
    n = len(cs)
    pistas = rep["registros"]
    return {
        "pistas": len(pistas),
        "pistas_B_fuera_del_top5": sum(g["x"] not in g["top"][:5] for g in pistas),
        "casos": n,
        "B_distintos": len({c["B"] for c in cs}),
        "B_distintos_guardia": len({c["B"] for c in cs if en_guardia(c["B"])}),
        "casos_guardia": sum(en_guardia(c["B"]) for c in cs),
        "casos_por_nivel": {str(L): sum(c["nivel"] == L for c in cs) for L in NIVELES},
        "piso_R@1": round(sum(c["puesto"] == 1 for c in cs) / n, 4) if n else None,
        "piso_visible_en_canal2": round(sum(c["visible"] for c in cs) / n, 4) if n else None,
        "piso_MRR": _mrr([c["puesto"] for c in cs]),
        "azar_MRR_esperado": round(sum(sum(1 / k for k in range(1, c["n"] + 1)) / c["n"] for c in cs) / n, 4)
        if n else None,
        "oraculo_MRR": _mrr([reordenar(c, rango) for c in cs]),
        "anti_oraculo_MRR": _mrr([reordenar(c, anti) for c in cs]),
        "frac_relacion_real_en_casos": round(frac_rel_casos, 4) if frac_rel_casos is not None else None,
        "frac_relacion_real_en_aristas": round(frac_rel_grafo, 4) if frac_rel_grafo is not None else None,
        "aristas_no_dirigidas": len(pares),
        "etiquetas_casos": {k: sum(_lab(c["A"], c["B"], idx) == k for c in cs) for k in ("pos", "puente", "neg", "irr")},
        "share_A_max": round(top_A[0] / n, 4) if n else None,
        "share_top3_A": round(sum(top_A[:3]) / n, 4) if n else None,
        "n_vecinos_medio": round(sum(c["n"] for c in cs) / n, 2) if n else None,
        "lista_casos": [{k: c[k] for k in ("B", "A", "s", "nivel", "pista", "puesto", "n", "visible")} for c in cs],
    }


def un_idioma(lg, mundo):
    d = os.path.join(TMP, lg)
    os.makedirs(d, exist_ok=True)
    # e1_medir.hijo_construir lee el mundo de /tmp/exp18_e1/<lg>/mundo.json
    d_e1 = os.path.join(e1_medir.TMP, lg)
    os.makedirs(d_e1, exist_ok=True)
    os.makedirs(os.path.join(e1_medir.TMP, "home"), exist_ok=True)
    json.dump(mundo, open(os.path.join(d_e1, "mundo.json"), "w"), ensure_ascii=False)
    eventos = os.path.join(d, "eventos_D.json")
    json.dump(mundo["D"], open(eventos, "w"), ensure_ascii=False)
    r = {k: os.path.join(d, k + ".db") for k in ("D", "DI", "ruidoso", "DI_ruidoso")}
    for v in ("D", "DI"):
        e1_medir._run(["e1_medir.py", "construir", lg, v, r[v]], e1_medir.BASE_ENV)
    e1_medir._copiar(r["D"], r["ruidoso"])
    e1_medir._run(["e1_medir.py", "construir", lg, "falsas", r["ruidoso"]], e1_medir.BASE_ENV)
    e1_medir._copiar(r["DI"], r["DI_ruidoso"])
    e1_medir._run(["e1_medir.py", "construir", lg, "falsas", r["DI_ruidoso"]], e1_medir.BASE_ENV)

    reps, vecs = {}, {}
    for nombre, base in (("ruidoso_1", "ruidoso"), ("ruidoso_2", "ruidoso"), ("DI_ruidoso", "DI_ruidoso"), ("D", "D")):
        sal = os.path.join(d, "rep_%s.json" % nombre)
        _run(["examen_rescate.py", "repaso", r[base], eventos, sal], ENV_LIMPIO)
        reps[nombre] = json.load(open(sal))
    for base in ("ruidoso", "DI_ruidoso", "D"):
        sal = os.path.join(d, "vec_%s.json" % base)
        _run(["examen_rescate.py", "vecinos", r[base], sal], ENV_LIMPIO)
        vecs[base] = json.load(open(sal))

    ex = medir_examen(reps["ruidoso_1"], vecs["ruidoso"])
    ex_DI = medir_examen(reps["DI_ruidoso"], vecs["DI_ruidoso"])
    ex_D = medir_examen(reps["D"], vecs["D"])
    a, b = reps["ruidoso_1"]["registros"], reps["DI_ruidoso"]["registros"]
    assert [(g["x"], g["pista"]) for g in a] == [(g["x"], g["pista"]) for g in b]
    tops_iguales = sum(g["top"][:5] == h["top"][:5] for g, h in zip(a, b))
    # Diagnóstico (sin puerta): ¿el cambio D→DI viene de un irrelevante que CONTIENE la pieza (legítimo: no es
    # irrelevante para esa pista) o de un reorden entre los recuerdos D (no invariancia real)?
    irr = {e["concepto"].lower(): _nk(e["contenido"]) for e in mundo["I"]}
    diag_inv = {"distintas": 0, "entra_irrelevante_que_contiene_la_pieza": 0, "reorden_entre_D": 0}
    for g, h in zip(a, b):
        if g["top"][:5] == h["top"][:5]:
            continue
        diag_inv["distintas"] += 1
        entra = [c for c in h["top"][:5] if c in irr]
        if entra and all(any(u in irr[c] for u in g["pista"].split()) for c in entra):
            diag_inv["entra_irrelevante_que_contiene_la_pieza"] += 1
        solo_d = [c for c in h["top"] if c not in irr]
        m = min(len(solo_d), len(g["top"]), 5)
        if solo_d[:m] != g["top"][:m]:
            diag_inv["reorden_entre_D"] += 1
    k1 = {(c["B"], c["pista"]): (c["A"], c["puesto"]) for c in ex["lista_casos"]}
    k2 = {(c["B"], c["pista"]): (c["A"], c["puesto"]) for c in ex_DI["lista_casos"]}
    comunes = set(k1) & set(k2)
    limpio = {
        "repasos_identicos": reps["ruidoso_1"]["registros"] == reps["ruidoso_2"]["registros"],
        "sha_sin_cambio": all(x["sha_antes"] == x["sha_despues"] for x in list(reps.values()) + list(vecs.values())),
        "copia_ciega_al_terminar": {k: max(x["vista_fin"][k] for x in reps.values())
                                    for k in ("sinapsis", "asociaciones", "emergentes")},
        "vecinos_no_cambia_sinapsis": all(v["sinapsis_antes"] == v["sinapsis_despues"] for v in vecs.values()),
    }
    return {
        "sinapsis_filas": {k: len(v["aristas"]) for k, v in vecs.items()},
        "dormidos": {k: sum(e != "activo" for e in v["estado"].values()) for k, v in vecs.items()},
        "examen_ruidoso": ex,
        "diag_examen_D_limpio": {k: v for k, v in ex_D.items() if k != "lista_casos"},
        "diag_examen_DI_ruidoso": {k: v for k, v in ex_DI.items() if k != "lista_casos"},
        "P2_top5_ciego_identico_D_vs_DI": "%d/%d" % (tops_iguales, len(a)),
        "P2_frac": round(tops_iguales / len(a), 4),
        "diag_P2_descomposicion": diag_inv,
        "P2b_casos_comunes": len(comunes),
        "P2b_iguales": sum(k1[k] == k2[k] for k in comunes),
        "P2b_solo_en_D": len(set(k1) - set(k2)),
        "P2b_solo_en_DI": len(set(k2) - set(k1)),
        "P6": limpio,
    }


def puertas(por):
    def todas(f):
        return all(f(v) for v in por.values())

    def p2b(v):
        return v["P2b_casos_comunes"] > 0 and v["P2b_iguales"] >= 0.98 * v["P2b_casos_comunes"]

    def p5(v):
        e = v["examen_ruidoso"]
        return (e["casos"] > 0 and e["frac_relacion_real_en_casos"] > e["frac_relacion_real_en_aristas"]
                and e["oraculo_MRR"] > e["piso_MRR"] > e["anti_oraculo_MRR"])

    return {
        "P1_casos": todas(lambda v: v["examen_ruidoso"]["casos"] >= 30 and v["examen_ruidoso"]["B_distintos"] >= 8
                          and v["examen_ruidoso"]["B_distintos_guardia"] >= 2),
        "P2_invariancia_pregunta": todas(lambda v: v["P2_frac"] >= 0.98),
        "P2b_invariancia_respuesta": todas(p2b),
        "P3_hubs": todas(lambda v: v["examen_ruidoso"]["casos"] > 0 and v["examen_ruidoso"]["share_A_max"] <= 0.25
                         and v["examen_ruidoso"]["share_top3_A"] <= 0.50),
        "P4_margen": todas(lambda v: v["examen_ruidoso"]["casos"] > 0 and v["examen_ruidoso"]["piso_R@1"] <= 0.80),
        "P5_validez": todas(p5),
        "P6_limpieza": todas(lambda v: v["P6"]["repasos_identicos"] and v["P6"]["sha_sin_cambio"]
                             and not any(v["P6"]["copia_ciega_al_terminar"].values())
                             and v["P6"]["vecinos_no_cambia_sinapsis"]),
    }


def main():
    t0 = time.time()
    for carpeta in (TMP, e1_medir.TMP):
        if os.path.exists(carpeta):
            shutil.rmtree(carpeta)
    os.makedirs(os.path.join(TMP, "home"))
    import construir as c16
    with contextlib.redirect_stdout(io.StringIO()):
        cat = c16.catalogo_real()
    mundos = e1_mundo.generar(cat)
    with ThreadPoolExecutor(max_workers=2) as ex:
        res = dict(zip(e1_mundo.IDIOMAS, ex.map(lambda lg: un_idioma(lg, mundos[lg]), e1_mundo.IDIOMAS)))
    p = puertas(res)
    out = {"protocolo": "PROTOCOLO_EXAMEN_RESCATE.md", "puertas": p, "examen_sirve": all(p.values()),
           "por_idioma": res, "segundos": round(time.time() - t0, 1)}
    os.makedirs(os.path.join(AQUI, "resultados"), exist_ok=True)
    json.dump(out, open(os.path.join(AQUI, "resultados", "examen.json"), "w"), ensure_ascii=False, indent=1)
    resumen = {lg: {k: v["examen_ruidoso"][k] for k in ("casos", "B_distintos", "B_distintos_guardia", "piso_R@1",
                                                        "piso_MRR", "oraculo_MRR", "anti_oraculo_MRR")}
               for lg, v in res.items()}
    print(json.dumps({"puertas": p, "resumen": resumen}, ensure_ascii=False, indent=1))
    print("FIN", 0 if all(p.values()) else 1)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "repaso":
        hijo_repaso(*sys.argv[2:5])
    elif len(sys.argv) > 1 and sys.argv[1] == "vecinos":
        hijo_vecinos(*sys.argv[2:4])
    else:
        main()
