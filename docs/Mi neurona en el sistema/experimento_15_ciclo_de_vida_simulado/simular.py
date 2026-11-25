"""Experimento 15: simulación de laboratorio de dos reglas del ciclo de vida sináptico.

Ver PROTOCOLO.md (subido antes de medir). NO cambia el motor. Toda escritura ocurre en copias
temporales; la base de origen se abre en modo solo lectura y se comprueba su sha256.

Uso (desde la raíz del repo, con PYTHONHASHSEED=1):
    python .../simular.py preparar ORIGEN DIR      # crea DIR/S0.db, S1.db, S2.db (copias) y aplica S1 y S2
    python .../simular.py medir DB SALIDA.json      # métricas M1–M5 (solo totales)
    python .../simular.py sintetica DIR             # base sintética: comprueba los invariantes de las reglas
"""
import collections
import hashlib
import json
import math
import os
import random
import sqlite3
import sys
import time

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, RAIZ)
import core.neurona_asociativa as NA  # noqa: E402
from core.auto_clustering import detectar_comunidades  # noqa: E402
from core.memory.constants import TIPOS_SINAPSIS_AGENTE  # noqa: E402

MANUAL = set(TIPOS_SINAPSIS_AGENTE)
PRIO = {"manual": 0, "sinonimo_explicito": 1, "co_semantica": 2, "latente_confirmada": 3,
        "co_ocurrencia": 4, "co_nombre": 5, "legacy_csv": 6, "manual_v7": 7, "test": 8}
# Parámetros fijados en el protocolo
PRESUPUESTO_X_MEDIANA, PISO_PESO = 2.0, 0.10
FUERZA_MAX_PODA, TOP_PROTEGIDO, MIN_VECINOS = 0.40, 20, 5


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def copiar(origen, destino):
    src = sqlite3.connect(f"file:{os.path.abspath(origen)}?mode=ro", uri=True)
    dst = sqlite3.connect(destino)
    src.backup(dst)
    src.close()
    dst.close()


class _C:  # lo mínimo que detectar_comunidades espera del cerebro
    def __init__(self, cur):
        self.cursor = cur


def activos(cur):
    return dict(cur.execute("SELECT concepto, contenido FROM largo_plazo WHERE estado='activo'").fetchall())


def pares(cur, act):
    """{frozenset(a,b): {'filas': [(rowid, o, d, peso, tipo, ultimo_uso)], ...}} entre recuerdos activos."""
    P = collections.defaultdict(list)
    for rid, o, d, p, tp, u in cur.execute("SELECT rowid, origen, destino, peso, tipo, ultimo_uso FROM sinapsis"):
        if o != d and o in act and d in act:
            P[frozenset((o, d))].append((rid, o, d, float(p if p is not None else 0.5), tp, u))
    return P


def vecinos(P):
    V = collections.defaultdict(set)
    for k in P:
        a, b = tuple(k)
        V[a].add(b)
        V[b].add(a)
    return V


def fuerzas(cur, act, P):
    """Fuerza del par = máximo de las dos direcciones (conservador para podar)."""
    jueces, F = {}, {}
    for k in sorted(P, key=lambda s: tuple(sorted(s))):
        a, b = sorted(k)
        fs = []
        for x, y in ((a, b), (b, a)):
            if x not in jueces:
                jueces[x] = NA.Juez(cur, x, act[x])
            fs.append(jueces[x].fuerza(y, act[y]) or 0.0)
        F[k] = max(fs)
    return F


# ───────────────────────── escenarios ─────────────────────────
def aplicar_s1(con):
    cur = con.cursor()
    filas = cur.execute("SELECT rowid, origen, destino, peso, tipo FROM sinapsis").fetchall()
    A = collections.Counter()
    for _, o, d, p, tp in filas:
        if tp not in MANUAL:
            A[o] += float(p or 0)
            A[d] += float(p or 0)
    tot = sorted(v for v in A.values() if v > 0)
    if not tot:
        return {"cambiadas": 0}
    B = PRESUPUESTO_X_MEDIANA * tot[len(tot) // 2]
    f = {n: min(1.0, B / v) for n, v in A.items() if v > 0}
    cambiadas = al_piso = 0
    for rid, o, d, p, tp in filas:
        if tp in MANUAL:
            continue
        fac = math.sqrt(f.get(o, 1.0) * f.get(d, 1.0))
        if fac < 1.0:
            nuevo = float(p or 0) * fac
            if nuevo < PISO_PESO:
                nuevo = min(float(p or 0), PISO_PESO)
                al_piso += 1
            cur.execute("UPDATE sinapsis SET peso=? WHERE rowid=?", (nuevo, rid))
            cambiadas += 1
    con.commit()
    return {"presupuesto": round(B, 3), "nodos_escalados": sum(1 for v in f.values() if v < 1),
            "sinapsis_cambiadas": cambiadas, "llevadas_al_piso": al_piso}


def canal2_visibles(P, V):
    """Pares que hoy muestra el canal 2 (mismo criterio que synapses.obtener_asociaciones_enriquecidas)."""
    vis = set()
    for n in V:
        mejor = {}
        for v in V[n]:
            for _r, _o, _d, p, tp, _u in P[frozenset((n, v))]:
                k = (PRIO.get(tp, 9), -p, p, tp)
                if v not in mejor or k < mejor[v]:
                    mejor[v] = k
        xs = sorted((k[0], k[1], v, k) for v, k in mejor.items() if k[2] >= 0.50)
        cnt = sin = 0
        for _, _, v, k in xs:
            if k[3] == "sinonimo_explicito":
                if sin >= 2:
                    continue
                sin += 1
            vis.add(frozenset((n, v)))
            cnt += 1
            if cnt >= 5:
                break
    return vis


def aplicar_s2(con, proteger_visibles=False):
    """S2 (protocolo). S2b = S2 + nunca tocar un par visible en el canal 2 (agregado DESPUÉS de medir)."""
    cur = con.cursor()
    act = activos(cur)
    P = pares(cur, act)
    F = fuerzas(cur, act, P)
    V = vecinos(P)
    vis = canal2_visibles(P, V) if proteger_visibles else set()
    top = {}
    for n, vs in V.items():
        top[n] = set(sorted(vs, key=lambda v: (-F[frozenset((n, v))], v))[:TOP_PROTEGIDO])
    cand = []
    for k, filas in P.items():
        a, b = tuple(k)
        if any(tp in MANUAL for *_, tp, _u in filas):
            continue
        if any(u is not None for *_, u in filas):
            continue
        if F[k] >= FUERZA_MAX_PODA or b in top[a] or a in top[b]:
            continue
        if k in vis:
            continue
        cand.append((F[k], tuple(sorted(k)), k))
    cand.sort()
    cur.execute("CREATE TABLE IF NOT EXISTS exp15_cuarentena AS SELECT * FROM sinapsis WHERE 0")
    grado = {n: len(vs) for n, vs in V.items()}
    movidas = pares_movidos = 0
    for _, _, k in cand:
        a, b = tuple(k)
        if grado[a] - 1 < MIN_VECINOS or grado[b] - 1 < MIN_VECINOS:
            continue
        for rid, *_ in P[k]:
            cur.execute("INSERT INTO exp15_cuarentena SELECT * FROM sinapsis WHERE rowid=?", (rid,))
            cur.execute("DELETE FROM sinapsis WHERE rowid=?", (rid,))
            movidas += 1
        grado[a] -= 1
        grado[b] -= 1
        pares_movidos += 1
    con.commit()
    return {"candidatos": len(cand), "pares_a_cuarentena": pares_movidos, "filas_a_cuarentena": movidas}


# ───────────────────────── métricas ─────────────────────────
def medir(ruta):
    con = sqlite3.connect(ruta)
    cur = con.cursor()
    NA.construir(cur)
    con.commit()
    act = activos(cur)
    P = pares(cur, act)
    V = vecinos(P)
    filas_all = cur.execute("SELECT origen, destino, peso, tipo FROM sinapsis").fetchall()
    man = [(o, d, p) for o, d, p, tp in filas_all if tp in MANUAL]
    A = collections.Counter()
    n_auto = 0
    for o, d, p, tp in filas_all:
        if tp not in MANUAL and o in act and d in act:
            n_auto += 1
            A[o] += float(p or 0)
            A[d] += float(p or 0)
    sA = sorted(A.values()) or [0]
    grados = sorted(len(v) for v in V.values()) or [0]

    t = time.time()
    islas = detectar_comunidades(_C(cur))
    crudas = detectar_comunidades(_C(cur), min_densidad=0.0)
    t_lpa = time.time() - t

    # M3: examen tapado por peso
    m3_pos = m3_ok = 0
    for n in sorted(V):
        vs = V[n]
        if len(vs) <= 5:
            continue
        info = {}
        for v in vs:
            filas = P[frozenset((n, v))]
            info[v] = (max(f[3] for f in filas), any(f[4] in MANUAL for f in filas))
        mans = [v for v in vs if info[v][1]]
        if not mans:
            continue
        m3_pos += min(5, len(mans))
        orden = sorted(vs, key=lambda v: (-info[v][0], v))
        m3_ok += sum(1 for v in orden[:5] if info[v][1])

    # M4: canal 2 con el código actual
    lugares = huerf = 0
    fz = []
    jueces = {}
    for n in sorted(V):
        mejor = {}
        for v in V[n]:
            for _r, _o, _d, p, tp, _u in P[frozenset((n, v))]:
                k = (PRIO.get(tp, 9), -p, p, tp)
                if v not in mejor or k < mejor[v]:
                    mejor[v] = k
        xs = sorted((k[0], k[1], v, k) for v, k in mejor.items() if k[2] >= 0.50)
        out, sin = [], 0
        for _, _, v, k in xs:
            if k[3] == "sinonimo_explicito":
                if sin >= 2:
                    continue
                sin += 1
            out.append((v, k[3]))
            if len(out) >= 5:
                break
        lugares += len(out)
        huerf += not out
        for v, tp in out:
            if tp not in MANUAL:
                if n not in jueces:
                    jueces[n] = NA.Juez(cur, n, act[n])
                fz.append(jueces[n].fuerza(v, act[v]) or 0.0)
    fz.sort()
    sin_vecinos = sum(1 for n in act if len(V.get(n, ())) == 0)
    res = {
        "M1_grafo": {"sinapsis_automaticas": n_auto, "grado_max": grados[-1],
                     "nodos_mas_de_100_vecinos": sum(g > 100 for g in grados),
                     "suma_pesos_auto_por_nodo": {"p50": round(sA[len(sA) // 2], 2),
                                                  "p90": round(sA[int(.9 * (len(sA) - 1))], 2),
                                                  "max": round(sA[-1], 2)}},
        "M2_islas": {"con_filtro_del_motor": len(islas),
                     "crudas_5_o_mas": len(crudas),
                     "mayor_cruda": max((len(c["nodos"]) for c in crudas), default=0),
                     "segundos": round(t_lpa, 1)},
        "M3_examen_tapado_por_peso": {"manuales_posibles": m3_pos, "aciertos": m3_ok,
                                      "pct": round(100 * m3_ok / max(1, m3_pos), 1)},
        "M4_canal2": {"lugares": lugares, "recuerdos_sin_asociaciones": huerf,
                      "fuerza_mediana_auto": round(fz[len(fz) // 2], 3) if fz else None,
                      "auto_fuerza_ge_060": round(sum(f >= .6 for f in fz) / max(1, len(fz)), 3)},
        "M5_invariantes": {"recuerdos_activos": len(act),
                           "recuerdos_total": cur.execute("SELECT count(*) FROM largo_plazo").fetchone()[0],
                           "enlaces_manuales": len(man),
                           "suma_pesos_manuales": round(sum(float(p or 0) for *_, p in man), 4),
                           "recuerdos_con_menos_de_5_vecinos": sum(1 for n in act if len(V.get(n, ())) < 5),
                           "recuerdos_sin_vecinos": sin_vecinos},
    }
    con.close()
    return res


# ───────────────────────── base sintética ─────────────────────────
def sintetica(directorio):
    """Base creada desde cero por el motor (solo esquema) + datos inventados. Comprueba invariantes."""
    os.makedirs(directorio, exist_ok=True)
    from core.memory_store import SQLiteMemoryBioRAG  # noqa: E402
    ruta = os.path.join(directorio, "sintetica.db")
    for ext in ("", "-wal", "-shm"):
        if os.path.exists(ruta + ext):
            os.remove(ruta + ext)
    SQLiteMemoryBioRAG(db_path=ruta)
    vacia = ruta + ".vacia.db"
    copiar(ruta, vacia)
    rnd = random.Random(7)
    temas = [["perro", "gato", "mascota", "veterinario"], ["python", "codigo", "funcion", "error"],
             ["viaje", "playa", "hotel", "vuelo"], ["receta", "cocina", "horno", "harina"]]
    con = sqlite3.connect(ruta)
    cur = con.cursor()
    cols = {r[1] for r in cur.execute("PRAGMA table_info(largo_plazo)")}
    nombres = []
    for i in range(120):
        t = temas[i % 4]
        palabras = rnd.sample(t, 3) + [f"palabra{rnd.randint(0, 400)}" for _ in range(6)]
        c = f"recuerdo_{t[0]}_{i:03d}"
        nombres.append((c, i % 4))
        datos = {"concepto": c, "contenido": " ".join(palabras), "sinonimos": t[0],
                 "estado": "activo", "peso_sinaptico": 1.0 if i % 10 == 0 else 0.5,
                 "creado_en": 1.7e9 + i * 3600}
        datos = {k: v for k, v in datos.items() if k in cols}
        cur.execute(f"INSERT INTO largo_plazo ({','.join(datos)}) VALUES ({','.join('?' * len(datos))})",
                    list(datos.values()))
    tipos = ["sinonimo_explicito", "co_semantica", "co_ocurrencia", "pmi_hebbiano", "co_nombre"]
    vistos = set()
    for i, (a, ta) in enumerate(nombres):
        n_vec = 60 if i % 10 == 0 else 8   # unos pocos «hubs»
        for _ in range(n_vec):
            b, tb = rnd.choice(nombres)
            if b == a or (a, b) in vistos or (b, a) in vistos:
                continue
            vistos.add((a, b))
            tp = "manual" if (ta == tb and rnd.random() < .15) else rnd.choice(tipos)
            peso = 0.5 if tp == "manual" else rnd.choice([0.9, 1.0, 0.6, 0.4])
            cur.execute("INSERT INTO sinapsis (origen, destino, peso, tipo, creado_en) VALUES (?,?,?,?,?)",
                        (a, b, peso, tp, 1.7e9))
    con.commit()
    con.close()
    out = {}
    for nombre, base in (("vacia", vacia), ("con_datos", ruta)):
        for esc, fn in (("S1", aplicar_s1), ("S2", aplicar_s2)):
            dst = os.path.join(directorio, f"{nombre}_{esc}.db")
            copiar(base, dst)
            c = sqlite3.connect(dst)
            NA.construir(c.cursor())
            c.commit()
            antes = medir(base)["M5_invariantes"] if nombre == "con_datos" else None
            cambio = fn(c)
            c.close()
            despues = medir(dst)
            inv = despues["M5_invariantes"]
            chequeo = {}
            if antes:
                chequeo = {
                    "manuales_identicos": (inv["enlaces_manuales"], inv["suma_pesos_manuales"]) ==
                                          (antes["enlaces_manuales"], antes["suma_pesos_manuales"]),
                    "recuerdos_identicos": inv["recuerdos_total"] == antes["recuerdos_total"],
                    "menos_de_5_no_sube": inv["recuerdos_con_menos_de_5_vecinos"] <=
                                          antes["recuerdos_con_menos_de_5_vecinos"],
                }
            out[f"{nombre}_{esc}"] = {"cambio": cambio, "invariantes": chequeo}
    return out


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "preparar":
        origen, d = sys.argv[2], sys.argv[3]
        os.makedirs(d, exist_ok=True)
        h0 = sha(origen)
        info = {"sha_origen_antes": h0[:12]}
        for esc in ("S0", "S1", "S2"):
            dst = os.path.join(d, f"{esc}.db")
            copiar(origen, dst)
            con = sqlite3.connect(dst)
            NA.construir(con.cursor())   # mismas tablas auxiliares en los tres escenarios
            con.commit()
            if esc == "S1":
                info["S1"] = aplicar_s1(con)
            elif esc == "S2":
                info["S2"] = aplicar_s2(con)
            con.close()
        info["sha_origen_despues"] = sha(origen)[:12]
        print(json.dumps(info, ensure_ascii=False, indent=1))
    elif cmd == "s2b":   # escenario agregado después de medir S0–S2 (ver RESULTADOS.md)
        origen, d = sys.argv[2], sys.argv[3]
        h0 = sha(origen)
        dst = os.path.join(d, "S2b.db")
        copiar(origen, dst)
        con = sqlite3.connect(dst)
        NA.construir(con.cursor())
        con.commit()
        info = {"S2b": aplicar_s2(con, proteger_visibles=True)}
        con.close()
        info["origen_intacto"] = sha(origen) == h0
        print(json.dumps(info, ensure_ascii=False, indent=1))
    elif cmd == "medir":
        r = medir(sys.argv[2])
        with open(sys.argv[3], "w", encoding="utf-8") as fh:
            json.dump(r, fh, ensure_ascii=False, indent=1)
        print(json.dumps(r, ensure_ascii=False, indent=1))
    elif cmd == "sintetica":
        print(json.dumps(sintetica(sys.argv[2]), ensure_ascii=False, indent=1))
