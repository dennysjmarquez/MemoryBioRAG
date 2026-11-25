"""Experimento 18, E1 — limpieza de las señales R, U y S (PROTOCOLO_V3.md §3). Criterios fijados antes.

Uso:  python e1_medir.py            → corre todo, escribe resultados/e1.json e imprime la tabla.
      (internos) python e1_medir.py construir <idioma> <variante> <ruta>
                 python e1_medir.py buscar_normal <ruta> <consultas.json> <salida.json>

Todo ocurre en /tmp. No toca el motor del repo ni ninguna base real.
Cada construcción y cada repaso corre en un proceso aparte, porque el motor lee el entorno al importarse.
"""
import contextlib
import io
import itertools
import json
import os
import random
import shutil
import sqlite3
import subprocess
import sys
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor

AQUI = os.path.dirname(os.path.abspath(__file__))
EXP16 = os.path.join(AQUI, "..", "experimento_16_protocolo_ns1_sintetico")
sys.path.insert(0, AQUI)
sys.path.insert(0, EXP16)

from mundos_espejo import etiqueta  # noqa: E402
import e1_mundo  # noqa: E402
import e1_repaso  # noqa: E402

PY = sys.executable
TMP = "/tmp/exp18_e1"
BASE_ENV = {"BIORAG_WORDNET_ENABLED": "0", "BIORAG_NO_LOG": "1", "PYTHONHASHSEED": "18"}
ENV_LIMPIO = dict(BASE_ENV, **e1_repaso.ENTORNO_LIMPIO)
N_ALTERADAS = 20


def _env(extra):
    e = dict(os.environ)
    e["HOME"] = os.path.join(TMP, "home")  # nada fuera de /tmp
    e.update(extra)
    return e


def _run(args, extra):
    p = subprocess.run([PY] + args, env=_env(extra), cwd=AQUI, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError("falló %s:\n%s" % (args, p.stderr[-3000:]))
    return p


def _cerrar(cerebro, ruta):
    with contextlib.redirect_stdout(io.StringIO()):
        cerebro.conn.commit()
        cerebro.cerrar_sistema()
    con = sqlite3.connect(ruta)
    con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    con.close()


def _copiar(origen, destino):
    for ext in ("", "-wal", "-shm"):
        if os.path.exists(destino + ext):
            os.remove(destino + ext)
    src = sqlite3.connect("file:%s?mode=ro" % origen, uri=True)
    dst = sqlite3.connect(destino)
    src.backup(dst)
    src.close()
    dst.close()


# ---------------------------------------------------------------- procesos hijos
def hijo_construir(lg, variante, ruta):
    """variante: D | DI (desde cero) · x3 | falsas | sueno (sobre una copia de D ya hecha en `ruta`)."""
    import construir as c16
    assert ruta.startswith("/tmp/")
    mundo = json.load(open(os.path.join(TMP, lg, "mundo.json")))
    if variante in ("D", "DI"):
        for ext in ("", "-wal", "-shm"):
            if os.path.exists(ruta + ext):
                os.remove(ruta + ext)
        cer = c16.abrir(ruta)
        for ev in mundo["D"]:
            with contextlib.redirect_stdout(io.StringIO()):
                c16.guardar(cer, ev)
        c16.dormir(cer)
        if variante == "DI":
            for ev in mundo["I"]:
                with contextlib.redirect_stdout(io.StringIO()):
                    c16.guardar(cer, ev)
        c16.dormir(cer)
        _cerrar(cer, ruta)
        return
    con = sqlite3.connect(ruta)
    r = random.Random(18)
    if variante == "x3":
        filas = con.execute("SELECT origen, destino FROM sinapsis ORDER BY origen, destino").fetchall()
        for o, d in r.sample(filas, min(N_ALTERADAS, len(filas))):
            con.execute("UPDATE sinapsis SET peso = peso * 3 WHERE origen=? AND destino=?", (o, d))
    elif variante == "falsas":
        nombres = [e["concepto"].lower() for e in mundo["D"]]
        pares = [(a, b) for a, b in itertools.combinations(range(24), 2) if etiqueta(a, b) == "neg"]
        for a, b in r.sample(pares, N_ALTERADAS):
            con.execute("INSERT OR REPLACE INTO sinapsis (origen, destino, peso, tipo, creado_en) "
                        "VALUES (?, ?, 1.0, 'co_ocurrencia', ?)", (nombres[a], nombres[b], time.time()))
    elif variante == "emergente":  # A4 / C1.2c
        nombres = [e["concepto"].lower() for e in mundo["D"]]
        con.execute("INSERT INTO dimensiones_semanticas (name, description, tipo_id, auto_generada, confianza, "
                    "generado_en) VALUES ('emergente_falsa_c12c', 'prueba C1.2c', 7, 1, 0.9, ?)", (time.time(),))
        did = con.execute("SELECT id FROM dimensiones_semanticas WHERE name='emergente_falsa_c12c'").fetchone()[0]
        for t in range(8):
            con.execute("INSERT OR IGNORE INTO largo_plazo_dimensiones (concepto, dimension_id) VALUES (?, ?)",
                        (nombres[t * 3 + 1], did))
        for n in nombres:
            otros = r.sample([x for x in nombres if x != n], 20)
            con.execute("UPDATE largo_plazo SET asociaciones = ? WHERE concepto = ?", (",".join(otros), n))
    con.commit()
    con.close()
    if variante in ("falsas", "sueno"):
        cer = c16.abrir(ruta)
        c16.dormir(cer)
        _cerrar(cer, ruta)


def hijo_buscar_normal(ruta, consultas_json, salida_json):
    import construir as c16
    sys.path.insert(0, os.path.abspath(os.path.join(AQUI, "..", "..", "..")))
    cer = c16.abrir(ruta)
    out = []
    for q in json.load(open(consultas_json)):
        with contextlib.redirect_stdout(io.StringIO()):
            res, _ = cer.buscar_por_frase(q, limite=5)
        out.append([[r[0], round(float(r[4] or 0), 6)] for r in (res or [])])
    json.dump(out, open(salida_json, "w"), ensure_ascii=False)


# ---------------------------------------------------------------- señales
def senales(rep, nombres):
    """R y U de los 276 pares a partir de los registros del repaso (PROTOCOLO_V3 §2)."""
    top5 = {}   # (x, s, tipo) -> (top5 sin x, x en top5)
    for g in rep["registros"]:
        top5[(g["x"], g["s"], g["tipo"])] = ([c for c in g["top"] if c != g["x"]][:5], g["x"] in g["top"][:5])
    por_x = {}
    for (x, s, t), v in top5.items():
        por_x.setdefault(x, []).append((s, v))
    R, U = {}, {}
    for a, b in itertools.combinations(range(len(nombres)), 2):
        A, B = nombres[a], nombres[b]
        sue = {s for s, (t5, _) in por_x.get(A, []) if B in t5} | {s for s, (t5, _) in por_x.get(B, []) if A in t5}
        R[(a, b)] = len(sue)

        def u(x, y):  # x rescata a y
            pis = por_x.get(y, [])
            return 0.0 if not pis else sum((not esta) and x in t5 for _, (t5, esta) in pis) / len(pis)
        U[(a, b)] = round(max(u(A, B), u(B, A)), 6)
    return R, U


def S_estructura(mundo):
    def nk(s):
        return unicodedata.normalize("NFKC", s).casefold().strip()
    ev = mundo["D"]
    out = {}
    for a, b in itertools.combinations(range(24), 2):
        da = {(k, v) for k, vs in ev[a]["dims"].items() for v in vs}
        db = {(k, v) for k, vs in ev[b]["dims"].items() for v in vs}
        sa = {nk(s) for s in ev[a]["sk"].split(",") if s.strip()}
        sb = {nk(s) for s in ev[b]["sk"].split(",") if s.strip()}
        out[(a, b)] = len(da & db) + len(sa & sb)
    return out


def auc(pos, neg):
    if not pos or not neg:
        return None
    gan = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return round(gan / (len(pos) * len(neg)), 3)


def identicos(x, y):
    return sum(x[k] == y[k] for k in x)


# ---------------------------------------------------------------- un idioma
def un_idioma(lg, mundo):
    d = os.path.join(TMP, lg)
    os.makedirs(d, exist_ok=True)
    json.dump(mundo, open(os.path.join(d, "mundo.json"), "w"), ensure_ascii=False)
    json.dump(mundo["D"], open(os.path.join(d, "eventos_D.json"), "w"), ensure_ascii=False)
    ruta = {k: os.path.join(d, k + ".db") for k in ("D", "D2", "DI", "x3", "falsas", "sueno", "emergente",
                                                     "antes", "despues")}
    for v, r in (("D", ruta["D"]), ("D", ruta["D2"]), ("DI", ruta["DI"])):
        _run(["e1_medir.py", "construir", lg, v, r], BASE_ENV)
    for v in ("x3", "falsas", "sueno", "emergente"):
        _copiar(ruta["D"], ruta[v])
        _run(["e1_medir.py", "construir", lg, v, ruta[v]], BASE_ENV)
    n_sin = {k: sqlite3.connect(ruta[k]).execute("SELECT COUNT(*) FROM sinapsis").fetchone()[0]
             for k in ("D", "DI", "x3", "falsas", "sueno")}

    # C1.4: foto de D antes de cualquier repaso
    _copiar(ruta["D"], ruta["antes"])
    reps = {}
    for nombre, base in (("D_1", "D"), ("D_2", "D"), ("D2", "D2"), ("DI", "DI"), ("x3", "x3"),
                         ("falsas", "falsas"), ("sueno", "sueno"), ("emergente", "emergente")):
        sal = os.path.join(d, "rep_%s.json" % nombre)
        _run(["e1_repaso.py", ruta[base], os.path.join(d, "eventos_D.json"), sal], ENV_LIMPIO)
        reps[nombre] = json.load(open(sal))
    for nombre, base in (("D_act", "D"), ("DI_act", "DI")):  # diagnóstico: profundidad="activos"
        sal = os.path.join(d, "rep_%s.json" % nombre)
        _run(["e1_repaso.py", ruta[base], os.path.join(d, "eventos_D.json"), sal, "activos"], ENV_LIMPIO)
        reps[nombre] = json.load(open(sal))
    _copiar(ruta["D"], ruta["despues"])
    consultas = [e1_repaso.pista_contenido(e["concepto"], e["contenido"], 1) for e in mundo["D"][:15:3]]
    json.dump(consultas, open(os.path.join(d, "consultas.json"), "w"), ensure_ascii=False)
    normales = {}
    for k in ("antes", "despues"):
        sal = os.path.join(d, "normal_%s.json" % k)
        _run(["e1_medir.py", "buscar_normal", ruta[k], os.path.join(d, "consultas.json"), sal], BASE_ENV)
        normales[k] = json.load(open(sal))

    nombres = [e["concepto"].lower() for e in mundo["D"]]
    sen = {k: senales(v, nombres) for k, v in reps.items()}
    S = S_estructura(mundo)
    lab = {p: etiqueta(*p) for p in S}

    def par_ru(k):
        R, U = sen[k]
        return {p: (R[p], U[p]) for p in R}

    RD, UD = sen["D_1"]
    pos = [p for p in lab if lab[p] == "pos"]
    neg = [p for p in lab if lab[p] == "neg"]
    pue = [p for p in lab if lab[p] == "puente"]
    # control contra hubs
    apar = {}
    for g in reps["D_1"]["registros"]:
        for c in [c for c in g["top"] if c != g["x"]][:5]:
            apar[c] = apar.get(c, 0) + 1
    hubs = [c for c, _ in sorted(apar.items(), key=lambda t: (-t[1], t[0]))[:3]]
    rescates = []
    for g in reps["D_1"]["registros"]:
        t5 = [c for c in g["top"] if c != g["x"]][:5]
        if g["x"] not in g["top"][:5]:
            rescates += t5
    tops_iguales = sum(a["top"] == b["top"] for a, b in zip(reps["D_1"]["registros"], reps["DI"]["registros"]))
    irr_en_DI = sum(any(c.startswith("irrelevante_") for c in g["top"][:5]) for g in reps["DI"]["registros"])
    n_pistas = len(reps["D_1"]["registros"])
    x_en_top5 = sum(g["x"] in g["top"][:5] for g in reps["D_1"]["registros"])

    return {
        "sinapsis_por_base": n_sin,
        "C1.1_identicos_D_vs_DI": identicos(par_ru("D_1"), par_ru("DI")),
        "C1.2_identicos_x3": identicos(par_ru("D_1"), par_ru("x3")),
        "C1.2b_identicos_falsas_vs_sueno": identicos(par_ru("falsas"), par_ru("sueno")),
        "C1.2c_identicos_emergente_y_asociaciones_falsas": identicos(par_ru("D_1"), par_ru("emergente")),
        "A4_copia_limpia_asociaciones_y_emergentes_al_terminar": max(
            r.get("asociaciones_vista_fin", 0) + r.get("emergentes_vista_fin", 0) for r in reps.values()),
        "C1.3_reproducible": reps["D_1"]["registros"] == reps["D_2"]["registros"],
        "C1.4_sha_igual": all(r["sha_original_antes"] == r["sha_original_despues"] for r in reps.values()),
        "C1.4_busquedas_normales_iguales": normales["antes"] == normales["despues"],
        "C1.5_sinapsis_en_copia_al_terminar": max(r["sinapsis_vista_fin"] for r in reps.values()),
        "C1.5_sinapsis_en_copia_al_abrir": max(r["sinapsis_vista_inicio"] for r in reps.values()),
        "diag_identicos_D_vs_D2_construida_otra_vez": identicos(par_ru("D_1"), par_ru("D2")),
        "diag_activos_identicos_D_vs_DI": identicos(par_ru("D_act"), par_ru("DI_act")),
        "diag_activos_X_se_encuentra_a_si_mismo": "%d/%d" % (
            sum(g["x"] in g["top"][:5] for g in reps["D_act"]["registros"]), n_pistas),
        "diag_dormidos_en_D": sqlite3.connect(ruta["D"]).execute(
            "SELECT COUNT(*) FROM largo_plazo WHERE estado='dormido'").fetchone()[0],
        "diag_dormidos_en_DI": sqlite3.connect(ruta["DI"]).execute(
            "SELECT COUNT(*) FROM largo_plazo WHERE estado='dormido'").fetchone()[0],
        "diag_top_identicos_D_vs_DI": "%d/%d" % (tops_iguales, n_pistas),
        "diag_pistas_DI_con_irrelevante_en_top5": irr_en_DI,
        "diag_X_se_encuentra_a_si_mismo": "%d/%d" % (x_en_top5, n_pistas),
        "C1.6": {
            "AUC_R": auc([RD[p] for p in pos], [RD[p] for p in neg]),
            "AUC_U": auc([UD[p] for p in pos], [UD[p] for p in neg]),
            "AUC_S": auc([S[p] for p in pos], [S[p] for p in neg]),
            "media_R_pos_neg_puente": [round(sum(RD[p] for p in g) / len(g), 3) for g in (pos, neg, pue)],
            "media_U_pos_neg_puente": [round(sum(UD[p] for p in g) / len(g), 3) for g in (pos, neg, pue)],
            "media_S_pos_neg_puente": [round(sum(S[p] for p in g) / len(g), 3) for g in (pos, neg, pue)],
            "frac_pos_con_U>0": round(sum(UD[p] > 0 for p in pos) / len(pos), 3),
            "frac_neg_con_U>0": round(sum(UD[p] > 0 for p in neg) / len(neg), 3),
            "frac_pos_con_R>0": round(sum(RD[p] > 0 for p in pos) / len(pos), 3),
            "frac_neg_con_R>0": round(sum(RD[p] > 0 for p in neg) / len(neg), 3),
            "hubs_top3": hubs,
            "frac_rescates_de_hubs": round(sum(c in hubs for c in rescates) / len(rescates), 3) if rescates else None,
            "n_rescates": len(rescates),
        },
    }


def criterios(por):
    n = 276
    return {
        "C1.1_invariancia_>=98%_cada_idioma": all(v["C1.1_identicos_D_vs_DI"] >= 0.98 * n for v in por.values()),
        "C1.2_x3_276/276": all(v["C1.2_identicos_x3"] == n for v in por.values()),
        "C1.2b_falsas_y_sueno_>=98%": all(v["C1.2b_identicos_falsas_vs_sueno"] >= 0.98 * n for v in por.values()),
        "C1.2c_emergente_y_asociaciones_276/276": all(
            v["C1.2c_identicos_emergente_y_asociaciones_falsas"] == n for v in por.values()),
        "C1.3_reproducible": all(v["C1.3_reproducible"] for v in por.values()),
        "C1.4_regresion": all(v["C1.4_sha_igual"] and v["C1.4_busquedas_normales_iguales"] for v in por.values()),
        "C1.5_0_sinapsis_en_copia": all(v["C1.5_sinapsis_en_copia_al_terminar"] == 0 for v in por.values()),
    }


def main():
    t0 = time.time()
    if os.path.exists(TMP):
        shutil.rmtree(TMP)
    os.makedirs(os.path.join(TMP, "home"))
    import construir as c16
    with contextlib.redirect_stdout(io.StringIO()):
        cat = c16.catalogo_real()
    mundos = e1_mundo.generar(cat)
    with ThreadPoolExecutor(max_workers=2) as ex:
        res = dict(zip(e1_mundo.IDIOMAS, ex.map(lambda lg: un_idioma(lg, mundos[lg]), e1_mundo.IDIOMAS)))
    crit = criterios(res)
    out = {"protocolo": "PROTOCOLO_V3.md §3 + enmienda A4", "por_idioma": res, "criterios": crit,
           "E1_pasa": all(crit.values()), "segundos": round(time.time() - t0, 1)}
    os.makedirs(os.path.join(AQUI, "resultados"), exist_ok=True)
    json.dump(out, open(os.path.join(AQUI, "resultados", "e1_a4.json"), "w"), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "construir":
        hijo_construir(*sys.argv[2:5])
    elif len(sys.argv) > 1 and sys.argv[1] == "buscar_normal":
        hijo_buscar_normal(*sys.argv[2:5])
    else:
        main()
