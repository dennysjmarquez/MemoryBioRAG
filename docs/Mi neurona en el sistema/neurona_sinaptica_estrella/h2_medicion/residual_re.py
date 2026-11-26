"""R-E0 y R-E1: residual del buscador (PROPUESTA_PROTOCOLO_CICLO2.md §1b). SOLO laboratorio sintético.

No toca el motor, ni los tests, ni `laboratorio_h2.py`: reutiliza sus funciones tal cual. Las bases viven solo en
/tmp y se crean desde cero con `mundo_sintetico.py`.

Brazo −H2 −4b, reloj comprimido, mundos D y D∪I0, semillas 7/11/23, |D| = 800/2400 (mundos de 1000 y 3000).
  Factor A (cuándo se fija el corte de la cohorte de búsqueda congelada, `search_baseline_rowid`):
    A0 «medir»: como en la medición anterior; la base nace vacía, no se reabre y el corte se fija al abrir la
       copia para medir, con D∪I dentro.
    A1 «trasD»: el motor se cierra y se reabre una vez justo después de la fase D (en los DOS mundos), así que el
       corte se fija con solo D dentro, como en una base real que ya existía antes de I.
  Factor B (solo al medir; la construcción es idéntica): BIORAG_PPMI_WEIGHT = 0.15 (por defecto) o 0.
R-E0: lectura en modo solo lectura de cada base construida, antes de medir: corte guardado, filas del FTS de
  referencia, hash de `nodos.vector` de los conceptos de D y filas de `sinapsis_latentes`.

Uso:  python residual_re.py todo
"""
import contextlib
import hashlib
import io
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import laboratorio_h2 as lab  # noqa: E402
import mundo_sintetico as ms  # noqa: E402

TMP = "/tmp/h2_residual"
RES = os.path.join(AQUI, "resultados_residual")
BRAZO, RELOJ = "-H2-4b", "comprimido"
MUNDOS = ("D", "DI0")
CORTES = ("medir", "trasD")
PPMI = ("0.15", "0")
REF_FTS = ("biorag_largo_plazo_fts_ref", "biorag_largo_plazo_fts_unicode_ref")


# ------------------------------------------------------------------ hijo: construcción
def hijo_construir(semilla, n_D, mundo, corte, ruta, salida):
    if corte == "medir":                 # idéntico a la medición anterior
        return lab.hijo_construir(semilla, n_D, mundo, BRAZO, RELOJ, ruta, salida, "1", "0")
    n_D = int(n_D)
    assert ruta.startswith("/tmp/")
    reloj = lab.preparar_hijo(BRAZO, True, lab.T0)
    import construir as c16
    m = ms.generar(int(semilla), n_D)
    D = [r for r in m["recuerdos"] if r["conj"] == "D"]
    I = [r for r in m["recuerdos"] if r["conj"] == "I0"]
    for ext in ("", "-wal", "-shm"):
        if os.path.exists(ruta + ext):
            os.remove(ruta + ext)
    estado = {"cer": c16.abrir(ruta)}
    ciclos, t_sueno = [], 0.0
    delta = lab.RELOJES[RELOJ]

    def dormir(fase, nuevos):
        nonlocal t_sueno
        reloj.t += delta
        lab.REG.append(["ciclo", len(ciclos), fase, nuevos, lab._inmunes_activos(estado["cer"])])
        t = time.perf_counter()
        c16.dormir(estado["cer"])
        t_sueno += time.perf_counter() - t
        ciclos.append(fase)

    def guardar(r):
        with contextlib.redirect_stdout(io.StringIO()):
            c16.guardar(estado["cer"], {"concepto": r["concepto"], "contenido": r["contenido"], "syn": "",
                                        "cat": "General", "dims": {}, "sk": ""})

    corte_info = {}
    for fase, lote in (("D", D), ("I", I)):
        nuevos = 0
        for k, r in enumerate(lote, 1):
            reloj.t += 1
            if fase == "D" or mundo != "D":
                guardar(r)
                nuevos += 1
            if k % lab.CADA == 0:
                dormir(fase, nuevos)
                nuevos = 0
        dormir(fase, nuevos)
        if fase == "D":                  # A1: cerrar y reabrir → el corte se fija con solo D dentro
            with contextlib.redirect_stdout(io.StringIO()):
                estado["cer"].conn.commit()
                estado["cer"].cerrar_sistema()
            estado["cer"] = c16.abrir(ruta)
            corte_info = {"baseline_rowid": estado["cer"]._search_baseline_rowid,
                          "baseline_sinapsis_rowid": getattr(estado["cer"], "_search_baseline_sinapsis_rowid", None),
                          "fts_ref_listo": bool(getattr(estado["cer"], "_search_baseline_fts_ready", False))}
    with contextlib.redirect_stdout(io.StringIO()):
        estado["cer"].conn.commit()
        estado["cer"].cerrar_sistema()
    con = sqlite3.connect(ruta)
    con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    con.close()
    json.dump({"registro": lab.REG, "t_sueno": t_sueno, "reloj_final": reloj.t, "n_ciclos": len(ciclos),
               "sha_tablas": lab.sha_tablas(ruta), "corte_al_reabrir": corte_info}, open(salida, "w"),
              ensure_ascii=False)


# ------------------------------------------------------------------ R-E0: lectura estática (solo lectura)
def r_e0(ruta, conceptos_D):
    con = sqlite3.connect("file:%s?mode=ro" % ruta, uri=True)
    tablas = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    dato = lambda k: (con.execute("SELECT valor FROM data WHERE clave=?", (k,)).fetchone() or [None])[0]  # noqa
    out = {"search_baseline_rowid": dato("search_baseline_rowid") if "data" in tablas else None,
           "search_baseline_sinapsis_rowid": dato("search_baseline_sinapsis_rowid") if "data" in tablas else None,
           "max_rowid_largo_plazo": con.execute("SELECT MAX(rowid) FROM largo_plazo").fetchone()[0],
           "filas_largo_plazo": con.execute("SELECT COUNT(*) FROM largo_plazo").fetchone()[0],
           "fts_ref_filas": {t: (con.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0] if t in tablas else None)
                             for t in REF_FTS},
           "sinapsis_latentes_filas": con.execute("SELECT COUNT(*) FROM sinapsis_latentes").fetchone()[0],
           "sinapsis_filas": con.execute("SELECT COUNT(*) FROM sinapsis").fetchone()[0]}
    if "nodos" in tablas:
        h, n = hashlib.sha256(), 0
        for c, v in sorted(con.execute("SELECT concepto, vector FROM nodos")):
            if c.lower() in conceptos_D:
                h.update(c.encode() + b"|" + (v or b""))
                n += 1
        out["nodos_D"] = {"n": n, "sha": h.hexdigest()[:16],
                          "total": con.execute("SELECT COUNT(*) FROM nodos").fetchone()[0]}
    else:
        out["nodos_D"] = None
    if "tokens" in tablas:
        out["tokens_ppmi_filas"] = con.execute("SELECT COUNT(*) FROM tokens").fetchone()[0]
    con.close()
    return out


# ------------------------------------------------------------------ orquestación
def _run(args, extra=None):
    e = dict(os.environ)
    e["HOME"] = os.path.join(TMP, "home", hashlib.sha256(repr((args, extra)).encode()).hexdigest()[:16])
    e.update(lab.BASE_ENV)
    e.update(extra or {})
    shutil.rmtree(e["HOME"], ignore_errors=True)
    os.makedirs(e["HOME"])
    p = subprocess.run([lab.PY, os.path.abspath(__file__)] + [str(a) for a in args], env=e, cwd=AQUI,
                       capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError("falló %s:\n%s" % (args, p.stderr[-4000:]))


def una_celda(args):
    """Construye un mundo con un corte, lo lee (R-E0) y lo mide con los dos pesos PPMI."""
    semilla, n_D, mundo, corte, pj, conceptos_D = args
    d = os.path.join(TMP, "s%d_n%d" % (semilla, n_D), corte)
    os.makedirs(d, exist_ok=True)
    ruta = os.path.join(d, mundo + ".db")
    rc = os.path.join(d, mundo + "_reg.json")
    re0 = os.path.join(d, mundo + "_re0.json")
    meds = {w: os.path.join(d, "%s_med_ppmi%s.json" % (mundo, w)) for w in PPMI}
    if not (os.path.exists(rc) and os.path.exists(re0) and all(os.path.exists(x) for x in meds.values())):
        t = time.time()
        _run(["construir", semilla, n_D, mundo, corte, ruta, rc])
        json.dump(r_e0(ruta, conceptos_D), open(re0, "w"))
        reg = json.load(open(rc))
        for w in PPMI:
            _run(["medir", ruta, pj, meds[w], reg["reloj_final"]], {"BIORAG_PPMI_WEIGHT": w})
        os.remove(ruta)
        print("celda", semilla, n_D, mundo, corte, round(time.time() - t), flush=True)
    return (mundo, corte), {"reg": json.load(open(rc)), "re0": json.load(open(re0)),
                            "med": {w: json.load(open(meds[w])) for w in PPMI}}


def analizar(semilla, n_D, res, m):
    qs = lab.consultas(m)
    en_D = {r["concepto"].lower() for r in m["recuerdos"] if r["conj"] == "D"}
    esc = {q["id"]: q["esc"] for q in qs}
    out = {"consultas": len(qs), "celdas": {}}
    for corte in CORTES:
        rD, rI = res[("D", corte)], res[("DI0", corte)]
        for w in PPMI:
            mD, mI = rD["med"][w], rI["med"][w]
            eD, eI = mD["estado"], mI["estado"]
            cam_est = sum(1 for c in en_D if eD[c][0] != eI[c][0])
            cam_imp = sum(1 for c in en_D if eD[c][1] != eI[c][1])
            cam = sorted(q["id"] for q in qs if mD["top"][q["id"]][:lab.K] != mI["top"][q["id"]][:lab.K])
            solo_D = sorted(q["id"] for q in qs if [c for c in mD["top"][q["id"]][:lab.K] if c in en_D] !=
                            [c for c in mI["top"][q["id"]][:lab.K] if c in en_D])
            ins_I0 = sum(1 for q in qs for c in mI["top"][q["id"]][:lab.K] if c not in en_D)
            out["celdas"]["corte=%s|ppmi=%s" % (corte, w)] = {
                "estado_D_identico": cam_est == 0 and cam_imp == 0, "cambios_estado_D": cam_est,
                "cambios_importancia_D": cam_imp, "top5_cambiados": len(cam),
                "top5_cambiados_por_escritura": {e: sum(1 for i in cam if esc[i] == e) for e in ms.ESCRITURAS},
                "top5_cambiados_restringido_a_D": len(solo_D), "inserciones_I0_top5": ins_I0,
                "consultas_sin_resultado": {"D": sum(not mD["top"][q["id"]] for q in qs),
                                            "DI0": sum(not mI["top"][q["id"]] for q in qs)},
                "copia_restaurada": mD["copia_restaurada"] and mI["copia_restaurada"],
                "_top5_cambiados": cam}
        out["R-E0|" + corte] = {"D": rD["re0"], "DI0": rI["re0"], "corte_al_reabrir": {
            "D": rD["reg"].get("corte_al_reabrir"), "DI0": rI["reg"].get("corte_al_reabrir")},
            "nodos_D_identicos": (rD["re0"]["nodos_D"] or {}).get("sha") == (rI["re0"]["nodos_D"] or {}).get("sha"),
            "sha_largo_plazo_D_vs_DI0": [rD["reg"]["sha_tablas"]["largo_plazo"], rI["reg"]["sha_tablas"]["largo_plazo"]]}
    return out


def una_config(semilla, n_D):
    final = os.path.join(RES, "residual_s%d_n%d.json" % (semilla, n_D))
    if os.path.exists(final):
        return json.load(open(final))
    m = ms.generar(semilla, n_D)
    tag = os.path.join(TMP, "s%d_n%d" % (semilla, n_D))
    os.makedirs(tag, exist_ok=True)
    pj = os.path.join(tag, "consultas.json")
    json.dump(lab.consultas(m), open(pj, "w"), ensure_ascii=False)
    conceptos_D = {r["concepto"].lower() for r in m["recuerdos"] if r["conj"] == "D"}
    t0 = time.time()
    trabajos = [(semilla, n_D, w, c, pj, conceptos_D) for c in CORTES for w in MUNDOS]
    with ThreadPoolExecutor(2) as ex:
        res = dict(ex.map(una_celda, trabajos))
    an = analizar(semilla, n_D, res, m)
    an["_meta"] = {"semilla": semilla, "n_D": n_D, "brazo": BRAZO, "reloj": RELOJ, "segundos": round(time.time() - t0)}
    os.makedirs(RES, exist_ok=True)
    json.dump(an, open(final, "w"), ensure_ascii=False, indent=1)
    return an


def main():
    tam = (100,) if lab.SECO else (800, 2400)
    sem = (7,) if lab.SECO else lab.SEMILLAS
    t0 = time.time()
    for n in tam:
        for s in sem:
            an = una_config(s, n)
            print("config", s, n, round(time.time() - t0),
                  {k: v["top5_cambiados"] for k, v in an["celdas"].items()}, flush=True)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "construir":
        hijo_construir(*sys.argv[2:])
    elif cmd == "medir":
        lab.hijo_medir(*sys.argv[2:])
    elif cmd == "todo":
        if lab.SECO:
            RES = "/tmp/h2_residual/resultados_seco"
        main()
