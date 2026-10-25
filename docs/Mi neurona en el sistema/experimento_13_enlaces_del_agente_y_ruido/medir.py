"""
Mediciones de solo lectura del experimento 13 (abre el snapshot en modo lectura).

    python medir.py SNAPSHOT FUERZAS_JSON

FUERZAS_JSON sale de preparar_copias.py. Escribe resultados/mediciones.json e
imprime un resumen en palabras simples.
"""
import collections
import json
import os
import sqlite3
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
EXAMEN = os.path.join(AQUI, "..", "experimento_11_neurona_asociativa", "resultados",
                      "examen_hoja_dennys.json")
PRIORIDAD = {"manual": 0, "sinonimo_explicito": 1, "co_semantica": 2, "latente_confirmada": 3,
             "co_ocurrencia": 4, "co_nombre": 5, "legacy_csv": 6, "manual_v7": 7, "test": 8}


def canal2(c):
    """Replica obtener_asociaciones_enriquecidas: lo que el agente ve junto a cada resultado."""
    activos = {k for (k,) in c.execute("SELECT concepto FROM largo_plazo WHERE estado = 'activo'")}
    aristas = collections.defaultdict(list)
    for o, d, p, t in c.execute("SELECT origen, destino, peso, tipo FROM sinapsis"):
        for r, v in ((o, d), (d, o)):
            if r in activos and v in activos and r != v:
                aristas[r].append((PRIORIDAD.get(t, 9), -p, v, t, p))
    top = {}
    for r in activos:
        vistos, out, n_sin = set(), [], 0
        for _, _, v, t, p in sorted(aristas[r]):
            if p < 0.5 or v in vistos:
                continue
            if t == "sinonimo_explicito":
                if n_sin >= 2:
                    continue
                n_sin += 1
            vistos.add(v)
            out.append((v, t))
            if len(out) == 5:
                break
        top[r] = out
    return activos, top


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    c = sqlite3.connect(f"file:{os.path.abspath(sys.argv[1])}?mode=ro", uri=True)
    fuerzas = {tuple(sorted((a, b))): (org, f) for a, b, org, t, f in json.load(open(sys.argv[2]))}
    examen = [p for p in json.load(open(EXAMEN))["pares"] if p["respuesta_dennys"] in ("si", "no")]
    r = {}

    # 1. Enlaces del agente
    q = lambda s: c.execute(s).fetchall()
    r["agente_por_peso"] = dict(q(
        "SELECT CASE WHEN peso >= 0.5 THEN '>=0.5' WHEN peso >= 0.2 THEN '0.2-0.5' ELSE '<0.2' END, "
        "COUNT(*) FROM sinapsis WHERE tipo = 'manual' GROUP BY 1"))
    r["agente_ya_usados"] = q("SELECT COUNT(*) FROM sinapsis WHERE tipo = 'manual' AND ultimo_uso IS NOT NULL")[0][0]
    r["agente_en_cuarentena"] = q(
        "SELECT tipo, COUNT(*), SUM(restaurado) FROM sinapsis_cuarentena "
        "WHERE tipo IN ('manual','manual_v7') GROUP BY tipo")
    creado = dict(q("SELECT concepto, creado_en FROM largo_plazo"))
    pares = {}
    for o, d, t in q("SELECT origen, destino, creado_en FROM sinapsis WHERE tipo = 'manual'"):
        pares[tuple(sorted((o, d)))] = t
    cuando = collections.Counter()
    for (a, b), t in pares.items():
        ds = [abs(t - creado[x]) for x in (a, b) if creado.get(x) and t]
        m = min(ds) if ds else None
        cuando["sin_fecha" if m is None else "al_guardar_<=10s" if m <= 10
               else "minutos_despues_<=10min" if m <= 600 else "mas_tarde"] += 1
    r["agente_cuando_se_crearon"] = dict(cuando)

    # 2. Hormiguita
    r["cuarentena_por_tipo"] = q(
        "SELECT tipo, COUNT(*), SUM(restaurado) FROM sinapsis_cuarentena GROUP BY tipo ORDER BY 2 DESC")

    # 3. Lo que ve el agente (canal 2)
    activos, top = canal2(c)
    comp = collections.Counter(t for out in top.values() for _, t in out)
    r["canal2_composicion"] = dict(comp.most_common())
    vis = collections.Counter()
    for p in examen:
        v = any(x == p["b"] for x, _ in top.get(p["a"], [])) or any(x == p["a"] for x, _ in top.get(p["b"], []))
        vis[f"{'visible' if v else 'no_visible'}_{p['respuesta_dennys']}"] += 1
    r["canal2_examen"] = dict(vis)

    # 4. Umbral de la neurona contra el examen de Dennys
    filas = []
    for p in examen:
        k = tuple(sorted((p["a"], p["b"])))
        if k in fuerzas:
            filas.append((fuerzas[k][0], fuerzas[k][1], p["respuesta_dennys"]))
    cuenta = lambda L, x: sum(1 for f in L if f[2] == x)
    hoy = [f for f in filas if f[0] == "vivo"]
    r["examen_hoy_con_hormiguita"] = {"quedan_si": cuenta(hoy, "si"), "quedan_no": cuenta(hoy, "no")}
    r["examen_por_umbral"] = {}
    for u in (-1, 0.4, 0.5, 0.6):
        quedan = [f for f in filas if f[1] >= u]
        r["examen_por_umbral"][str(u)] = {"quedan_si": cuenta(quedan, "si"), "quedan_no": cuenta(quedan, "no")}
    r["examen_pares_medibles"] = len(filas)

    os.makedirs(os.path.join(AQUI, "resultados"), exist_ok=True)
    json.dump(r, open(os.path.join(AQUI, "resultados", "mediciones.json"), "w"), indent=1, ensure_ascii=False)
    print(json.dumps(r, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
