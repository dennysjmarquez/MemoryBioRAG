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
    can2 = canal2_por_raiz(ruta, sorted(recs))
    con.close()
    # dimensiones creadas por el MOTOR (p. ej. «tema_*» del auto-clustering): dependen de todo el corpus,
    # así que la neurona no puede usarlas (PROTOCOLO.md §7: comunidad = aguja prohibida)
    auto = sorted(r[0] for r in sqlite3.connect(ruta).execute(
        "SELECT name FROM dimensiones_semanticas WHERE auto_generada = 1"))
    return {"recs": recs, "sinapsis": sin, "canal2_motor": can2, "info": info, "dims_auto": auto}


class _SoloLectura:
    """Lo único que usa synapses.obtener_asociaciones_enriquecidas es self.cursor."""

    def __init__(self, ruta):
        self.conn = sqlite3.connect("file:%s?mode=ro" % ruta, uri=True)
        self.cursor = self.conn.cursor()


def canal2_por_raiz(ruta, raices):
    """Canal 2 del MOTOR, llamado con UNA raíz por vez, como cuando un recuerdo sale en una búsqueda.
    (Llamarlo con todas las raíces juntas cambia el resultado: si origen y destino están ambos en la
    lista, el motor solo cuenta la arista desde el origen.) Conexión de solo lectura."""
    from core.memory import synapses
    s = _SoloLectura(ruta)
    out = {}
    for r in raices:
        res = synapses.obtener_asociaciones_enriquecidas(s, [r], top_vecinos=5)
        out[r] = [a["concepto"] for a in res.get(r, [])]
    s.conn.close()
    return out


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


def _nombre(semilla, var, version):
    return ("" if version == "v1" else version + "_") + "s%d_%s" % (semilla, var)


def main(base, version="v1"):
    """Cada construcción corre en un PROCESO NUEVO: así ningún caché de módulo pasa de un mundo a otro."""
    import subprocess
    os.makedirs(os.path.join(base, "extractos"), exist_ok=True)
    for semilla, var, _ in trabajos():
        salida = os.path.join(base, "extractos", _nombre(semilla, var, version) + ".json")
        if os.path.exists(salida):
            continue
        subprocess.run([sys.executable, os.path.abspath(__file__), "uno", base, str(semilla), var, version],
                       check=True)
    print("FIN", flush=True)


def uno(base, semilla, var, version="v1"):
    kw = {v: k for s, v, k in trabajos() if s == semilla}[var]
    salida = os.path.join(base, "extractos", _nombre(semilla, var, version) + ".json")
    generar = M.generar if version == "v1" else M.generar_v2
    cat = C.catalogo_real()
    if True:  # noqa: SIM108 (bloque conservado para legibilidad)
        mundo = generar(semilla, cat, **kw)
        ruta = os.path.join(base, "dbs", _nombre(semilla, var, version) + ".db")
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        cerebro, dt = C.construir(mundo, ruta)
        ex = extraer(cerebro, ruta, mundo["info"])
        ex["params"] = mundo["params"]
        ex["segundos_construccion"] = round(dt, 1)
        ex["canal2_por_raiz"] = True
        if var == "D_rep":
            ex["Q6"] = renacimiento(cerebro, mundo)
        with open(salida, "w") as fh:
            json.dump(ex, fh)
        print(time.strftime("%H:%M:%S"), version, semilla, var, "eventos", len(mundo["eventos"]), "sinapsis",
              len(ex["sinapsis"]), "seg", round(dt, 1), ex.get("Q6", ""), flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "uno":
        uno(sys.argv[2], int(sys.argv[3]), sys.argv[4], *(sys.argv[5:6] or ["v1"]))
    else:
        main(sys.argv[1], *(sys.argv[2:3] or ["v1"]))
