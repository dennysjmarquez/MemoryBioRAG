"""Experimento 16 — construye todas las variantes con el motor real y extrae lo necesario a JSON.

Uso (desde la raíz del repo):
    PYTHONHASHSEED=1 HOME=/tmp/exp16/home python .../extraer.py /tmp/exp16
Todo se escribe bajo /tmp/exp16 (bases y extractos). Ninguna base real se abre.
"""
import json
import os
import random
import sqlite3
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import construir as C  # noqa: E402
import mundo as M  # noqa: E402

VARIANTES = {
    "D": dict(),
    "D_rep": dict(),
    "D_Ipuro": dict(n_irrelevantes=400, irrelevantes_reales=False),
    "D_Ireal": dict(n_irrelevantes=400, irrelevantes_reales=True),
    "D_orden": dict(permutar_sesiones=True),
}
GENERALIZACION = dict(n=400, temas=35, subtemas=5, frac_generica=0.25)


def extraer(cerebro, ruta, info):
    con = sqlite3.connect(ruta)
    dimnom = dict(con.execute("SELECT id, name FROM dimensiones_semanticas"))
    catnom = dict(con.execute("SELECT id, name FROM categories"))
    recs = {}
    for c, cont, syn, sk, cat, est in con.execute(
            "SELECT concepto, contenido, sinonimos, COALESCE(sustantivos_clave_exactos, sustantivos_clave), "
            "categoria, estado FROM largo_plazo"):
        recs[c] = {"contenido": cont or "", "syn": syn or "", "sk": sk or "", "cat": catnom.get(cat, str(cat)),
                   "estado": est, "dims": []}
    for c, d in con.execute("SELECT concepto, dimension_id FROM largo_plazo_dimensiones"):
        if c in recs:
            recs[c]["dims"].append(dimnom.get(d, str(d)))
    sin = [list(r) for r in con.execute("SELECT origen, destino, peso, tipo FROM sinapsis ORDER BY rowid")]
    # canal 2 para TODAS las raíces (el motor solo filtra el estado del VECINO, no el de la raíz)
    todas = sorted(recs)
    can2 = cerebro.obtener_asociaciones_enriquecidas(todas, top_vecinos=5)
    can2 = {k: [a["concepto"] for a in v] for k, v in can2.items()}
    con.close()
    return {"recs": recs, "sinapsis": sin, "canal2_motor": can2, "info": info}


def renacimiento(cerebro, mundo, n=30, semilla=99):
    """Q6: desvincula 30 sinapsis con rel=0, vuelve a guardar el recuerdo de origen y duerme."""
    from core.sinapsis import desvincular
    info = mundo["info"]
    cur = cerebro.cursor
    filas = cur.execute("SELECT origen, destino FROM sinapsis ORDER BY origen, destino").fetchall()
    cands = sorted({tuple(sorted(f)) for f in filas if f[0] in info and f[1] in info
                    and M.relevancia(info, f[0], f[1]) == 0 and info[f[0]]["grupo"] == "D"})
    rnd = random.Random(semilla)
    elegidos = rnd.sample(cands, min(n, len(cands)))
    ev = {e["concepto"]: e for e in mundo["eventos"]}
    for a, b in elegidos:
        desvincular(cerebro, a, b)
    for a, b in elegidos:
        C.guardar(cerebro, ev[a])
    C.dormir(cerebro)
    vuelven = 0
    for a, b in elegidos:
        k = cur.execute("SELECT COUNT(*) FROM sinapsis WHERE (origen=? AND destino=?) OR (origen=? AND destino=?)",
                        (a, b, b, a)).fetchone()[0]
        vuelven += 1 if k else 0
    return {"desvinculados": len(elegidos), "renacieron": vuelven}


def trabajos():
    return [(s, v, kw) for s in (1, 2, 3) for v, kw in VARIANTES.items()] + [(11, "G", GENERALIZACION)]


def main(base):
    """Cada construcción corre en un PROCESO NUEVO: así ningún caché de módulo pasa de un mundo a otro."""
    import subprocess
    os.makedirs(os.path.join(base, "extractos"), exist_ok=True)
    for semilla, var, _ in trabajos():
        salida = os.path.join(base, "extractos", "s%d_%s.json" % (semilla, var))
        if os.path.exists(salida):
            continue
        subprocess.run([sys.executable, os.path.abspath(__file__), "uno", base, str(semilla), var], check=True)
    print("FIN", flush=True)


def uno(base, semilla, var):
    kw = {v: k for s, v, k in trabajos() if s == semilla}[var]
    salida = os.path.join(base, "extractos", "s%d_%s.json" % (semilla, var))
    cat = C.catalogo_real()
    if True:  # noqa: SIM108 (bloque conservado para legibilidad)
        mundo = M.generar(semilla, cat, **kw)
        ruta = os.path.join(base, "dbs", "s%d_%s.db" % (semilla, var))
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        cerebro, dt = C.construir(mundo, ruta)
        ex = extraer(cerebro, ruta, mundo["info"])
        ex["params"] = mundo["params"]
        ex["segundos_construccion"] = round(dt, 1)
        if var == "D_rep":
            ex["Q6"] = renacimiento(cerebro, mundo)
        with open(salida, "w") as fh:
            json.dump(ex, fh)
        print(time.strftime("%H:%M:%S"), semilla, var, "eventos", len(mundo["eventos"]), "sinapsis",
              len(ex["sinapsis"]), "seg", round(dt, 1), ex.get("Q6", ""), flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "uno":
        uno(sys.argv[2], int(sys.argv[3]), sys.argv[4])
    else:
        main(sys.argv[1])
