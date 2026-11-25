"""Experimento 14: el canal 2 hoy, con un filtro y con la neurona asociativa que solo ORDENA.

No cambia el motor. Trabaja SIEMPRE sobre una copia temporal de la DB que se le pasa, abierta en
modo solo lectura y copiada con `sqlite3.backup`; la copia se borra al terminar. La DB original no
se escribe. El JSON de salida solo tiene totales: ningún nombre ni contenido de recuerdos.

Uso (desde la raíz del repo):
    PYTHONHASHSEED=1 python "docs/Mi neurona en el sistema/experimento_14_neurona_ordena_canal2/medir.py" \
        RUTA_DB  SALIDA.json

Qué compara (los tres usan los mismos filtros del canal 2 de hoy: peso >= .50, vecino activo,
5 lugares por recuerdo, como máximo 2 `sinonimo_explicito`):
  - hoy:        escalera fija por tipo y después peso (`core/memory/synapses.py`,
                `obtener_asociaciones_enriquecidas`);
  - filtro_050: oculta las automáticas con fuerza < .50 (propuesta externa); lo demás igual;
  - ordena:     `manual`/`manual_v7` primero; el resto, por la fuerza de la neurona cerrada
                (`core/neurona_asociativa.py`, `asoc-1`, escala 0). No oculta nada.

Examen tapado: se le quita la etiqueta `manual` a todas las sinapsis de un recuerdo y se cuenta
cuántos enlaces hechos a mano por el agente quedan entre los 5 primeros. Se informa por separado
para el 20 % de guardia (sha256(nombre)[:8] % 5 == 0), igual que la primera neurona.
"""
import collections
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import time

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, RAIZ)
import core.neurona_asociativa as NA  # noqa: E402

PRIO = {"manual": 0, "sinonimo_explicito": 1, "co_semantica": 2, "latente_confirmada": 3,
        "co_ocurrencia": 4, "co_nombre": 5, "legacy_csv": 6, "manual_v7": 7, "test": 8}
MANUAL = {"manual", "manual_v7"}
JUZGA = {"co_ocurrencia", "co_nombre", "co_semantica", "pmi_hebbiano", "sinonimo_explicito",
         "latente_confirmada"}
LUGARES, MAX_SIN, PESO_MIN = 5, 2, 0.50


def es_guardia(c):
    return int(hashlib.sha256(c.encode("utf-8")).hexdigest()[:8], 16) % 5 == 0


def cinco(xs):
    """xs ya ordenada: [(vecino, tipo)]. Aplica tope de sinónimos y de lugares."""
    out, sin = [], 0
    for v, tp in xs:
        if tp == "sinonimo_explicito":
            if sin >= MAX_SIN:
                continue
            sin += 1
        out.append((v, tp))
        if len(out) >= LUGARES:
            break
    return out


def main(ruta, salida):
    tmp = tempfile.mkdtemp(prefix="exp14_")
    try:
        src = sqlite3.connect(f"file:{os.path.abspath(ruta)}?mode=ro", uri=True)
        con = sqlite3.connect(os.path.join(tmp, "copia.db"))
        src.backup(con)
        src.close()
        cur = con.cursor()
        t0 = time.time()
        NA.construir(cur)
        con.commit()
        t_construir = time.time() - t0

        activos = dict(cur.execute(
            "SELECT concepto, contenido FROM largo_plazo WHERE estado='activo'").fetchall())
        vec = collections.defaultdict(dict)  # raiz -> vecino -> (prio, -peso, peso, tipo)
        for o, d, p, tp in cur.execute("SELECT origen, destino, peso, tipo FROM sinapsis"):
            if o == d or o not in activos or d not in activos:
                continue
            p = float(p or 0.5)
            for r, v in ((o, d), (d, o)):
                k = (PRIO.get(tp, 9), -p, p, tp)
                if v not in vec[r] or k < vec[r][v]:
                    vec[r][v] = k

        t0 = time.time()
        F = {}
        for r in sorted(vec):
            J = NA.Juez(cur, r, activos[r])
            for v in sorted(vec[r]):
                F[(r, v)] = J.fuerza(v, activos[v]) or 0.0
        t_juzgar = time.time() - t0

        def hoy(r, it):
            xs = sorted((k[0], k[1], v, k[3]) for v, k in it.items() if k[2] >= PESO_MIN)
            return cinco([(v, tp) for _, _, v, tp in xs])

        def filtro(r, it):
            keep = {v: k for v, k in it.items() if k[3] not in JUZGA or F[(r, v)] >= 0.5}
            return hoy(r, keep)

        def ordena(r, it):
            xs = sorted((0 if k[3] in MANUAL else 1, -F[(r, v)], k[1], v, k[3])
                        for v, k in it.items() if k[2] >= PESO_MIN)
            return cinco([(v, tp) for *_, v, tp in xs])

        canal = {}
        for nombre, fn in (("hoy", hoy), ("filtro_050", filtro), ("ordena", ordena)):
            tipos, fz = collections.Counter(), []
            lugares = huerfanos = cambian = 0
            for r in sorted(vec):
                out = fn(r, vec[r])
                lugares += len(out)
                huerfanos += not out
                if nombre != "hoy":
                    cambian += {v for v, _ in out} != {v for v, _ in hoy(r, vec[r])}
                for v, tp in out:
                    tipos[tp] += 1
                    if tp not in MANUAL:
                        fz.append(F[(r, v)])
            fz.sort()
            canal[nombre] = {
                "lugares": lugares,
                "recuerdos_sin_asociaciones": huerfanos,
                "recuerdos_con_otra_lista_que_hoy": cambian,
                "automaticas_mostradas": len(fz),
                "fuerza_mediana_automaticas": round(fz[len(fz) // 2], 3) if fz else None,
                "automaticas_con_fuerza_ge_060": round(sum(f >= 0.6 for f in fz) / max(1, len(fz)), 3),
                "por_tipo": dict(tipos.most_common()),
            }

        examen = {}
        for grupo, g in (("estudio", False), ("guardia", True)):
            tot = collections.Counter()
            n_rec = n_man = 0
            for r in sorted(vec):
                it = vec[r]
                if es_guardia(r) != g:
                    continue
                man = {v for v, k in it.items() if k[3] in MANUAL}
                if not man or len(it) <= LUGARES:
                    continue
                n_rec += 1
                n_man += min(len(man), LUGARES)
                J = NA.Juez(cur, r, activos[r])
                fu = {v: (J.fuerza(v, activos[v]) or 0.0) if v in man else F[(r, v)] for v in it}
                ordenes = {
                    "peso_de_hoy": sorted(it, key=lambda v: (-it[v][2], v)),
                    "escalera_por_tipo": sorted(it, key=lambda v: (
                        4 if v in man else PRIO.get(it[v][3], 9), -it[v][2], v)),
                    "neurona": sorted(it, key=lambda v: (-fu[v], v)),
                }
                for k, o in ordenes.items():
                    tot[k] += sum(1 for v in o[:LUGARES] if v in man)
            examen[grupo] = {"recuerdos": n_rec, "manuales_posibles_en_top5": n_man,
                             **{k: {"aciertos": tot[k], "pct": round(100 * tot[k] / max(1, n_man), 1)}
                                for k in ("peso_de_hoy", "escalera_por_tipo", "neurona")}}

        grados = sorted(len(it) for it in vec.values())
        res = {
            "db": os.path.basename(ruta),
            "neurona": NA.VERSION,
            "recuerdos_activos": len(activos),
            "recuerdos_con_vecinos": len(vec),
            "pares_juzgados": len(F),
            "vecinos_por_recuerdo": {"mediana": grados[len(grados) // 2], "p90": grados[int(.9 * len(grados))],
                                     "max": grados[-1]},
            "segundos": {"construir_estado": round(t_construir, 2), "juzgar_todo": round(t_juzgar, 1),
                         "ms_por_par": round(1000 * t_juzgar / max(1, len(F)), 3)},
            "canal2": canal,
            "examen_tapado": examen,
        }
        with open(salida, "w", encoding="utf-8") as fh:
            json.dump(res, fh, ensure_ascii=False, indent=1)
        print(json.dumps(res, ensure_ascii=False, indent=1))
        con.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
