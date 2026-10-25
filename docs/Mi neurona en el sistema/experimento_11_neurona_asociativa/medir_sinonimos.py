"""¿Cómo arreglar `vincular_por_sinonimos`? Comparación de reglas en la COPIA de la memoria de Dennys.

Para cada recuerdo activo se toman sus sinónimos (columna `sinonimos`) y se simula qué sinapsis
crearía cada regla. Para cada regla se mide:
  - cuántos pares crea y cuántas sinapsis le tocan al recuerdo con más
  - la fuerza mediana que les da la neurona (qué tan "de verdad" parecen)
  - cuántos de los 381 enlaces humanos (manuales) vuelve a encontrar (no queremos perderlos)

Reglas:
  hoy                 core/sinapsis.py: el término como PEDAZO DE TEXTO (LIKE '%t%') en el nombre o
                      en los sinónimos de cualquier otro recuerdo, sin tope
  palabra completa    el término tiene que ser una palabra (o frase) completa del nombre, o uno de
                      los sinónimos del otro
  + raro              además, se ignora un término que aparece en más de 10 recuerdos (es un tema,
                      no un sinónimo)
  + tope 10           además, como mucho 10 sinapsis por guardado (primero los términos más raros)
  hoy + neurona       la regla de hoy, y la neurona decide: cada recuerdo se queda con sus K socios
                      más fuertes (K = 5, 10, 20)

No toca ninguna DB: lee /tmp/e11/dennys.db (copia) en modo solo lectura.
Uso:  python medir_sinonimos.py   → resultados/sinonimos.json
"""
import collections
import json
import os
import re
import sqlite3

import numpy as np

import agujas
import corpus
import neurona_asociativa as na

AQUI = os.path.dirname(os.path.abspath(__file__))
DB = "/tmp/e11/dennys.db"
RARO = 10
TOPE = 10


def terminos(s):
    return [t.strip().lower() for t in (s or "").split(",") if t.strip()]


def main():
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    filas = c.execute("SELECT concepto, COALESCE(sinonimos,'') FROM largo_plazo WHERE estado='activo'").fetchall()
    con = [f[0] for f in filas]
    syn = {f[0]: f[1] for f in filas}
    low = {x: x.lower() for x in con}
    synset = {y: set(terminos(syn[y])) for y in con}
    existentes = c.execute("SELECT COUNT(*) FROM sinapsis WHERE tipo='sinonimo_explicito'").fetchone()[0]
    por_origen = [n for (_, n) in c.execute(
        "SELECT origen, COUNT(*) FROM sinapsis WHERE tipo='sinonimo_explicito' GROUP BY origen")]

    hits_hoy, hits_pal = {}, {}

    def norm(t):
        return re.sub(r"[\s\-]+", "_", t)

    def palabra(t, y):
        tn = norm(t)
        if tn == low[y] or t in synset[y] or tn in {norm(s) for s in synset[y]}:
            return True
        nombre, partes = low[y].split("_"), tn.split("_")
        n = len(partes)
        return any(nombre[i:i + n] == partes for i in range(len(nombre) - n + 1))

    for x in con:
        for t in terminos(syn[x]):
            if t not in hits_hoy:
                hits_hoy[t] = {y for y in con if t in low[y] or t in syn[y].lower()}
                hits_pal[t] = {y for y in con if palabra(t, y)}

    mem = corpus.dennys(DB)
    pos = {x: i for i, x in enumerate(mem["conceptos"])}
    sin = mem["sin"]
    manual = {k for k, v in sin.items() if v[0] == "manual"}

    def construir(hits, raro=None, tope=None):
        out = set()
        for x in con:
            if x not in pos:
                continue
            cands = []
            for t in dict.fromkeys(terminos(syn[x])):
                h = [y for y in hits[t] if y != x and y in pos]
                if raro and len(h) > raro:
                    continue
                cands += [(len(h), y) for y in h]
            cands.sort(key=lambda q: q[0])
            elegidos = list(dict.fromkeys(y for _, y in cands))
            if tope:
                elegidos = elegidos[:tope]
            for y in elegidos:
                a, b = pos[x], pos[y]
                out.add((min(a, b), max(a, b)))
        return out

    reglas = {"hoy": construir(hits_hoy), "palabra completa": construir(hits_pal),
              f"palabra completa + raro (<= {RARO})": construir(hits_pal, raro=RARO),
              f"palabra completa + raro + tope {TOPE}": construir(hits_pal, raro=RARO, tope=TOPE)}
    m = agujas.Memoria(mem["textos"], orden=mem["orden"], etiquetas=mem["etiquetas"])
    todos = sorted(set().union(*reglas.values()))
    F = dict(zip(todos, na.fuerza(m.agujas(todos), agujas.NOMBRES_TODAS, p=na.cargar())))
    hoy = sorted(reglas["hoy"])
    fh = np.array([F[k] for k in hoy])
    for k in (5, 10, 20):
        keep = na.competencia(fh, hoy, k)
        reglas[f"hoy + neurona (top {k})"] = {hoy[i] for i in np.where(keep)[0]}

    out = {"sinapsis_sinonimo_explicito_en_la_db": existentes,
           "recuerdos_con_ese_tipo": len(por_origen), "max_por_recuerdo_en_la_db": max(por_origen),
           "terminos_mas_comunes": [(t, len(v)) for t, v in sorted(hits_pal.items(), key=lambda kv: -len(kv[1]))[:10]],
           "enlaces_humanos": len(manual), "reglas": {}}
    print(f"{'regla':42s} {'pares':>7s} {'máx/recuerdo':>13s} {'fuerza med.':>11s} {'humanos':>9s}")
    for nm, s in reglas.items():
        fs = np.array([F[k] for k in s])
        cnt = collections.Counter([a for a, b in s] + [b for a, b in s])
        r = {"pares": len(s), "max_por_recuerdo": max(cnt.values()), "fuerza_mediana": round(float(np.median(fs)), 3),
             "humanos_encontrados": len(s & manual)}
        out["reglas"][nm] = r
        print(f"{nm:42s} {r['pares']:7d} {r['max_por_recuerdo']:13d} {r['fuerza_mediana']:11.3f} "
              f"{r['humanos_encontrados']:5d}/{len(manual)}")
    json.dump(out, open(os.path.join(AQUI, "resultados", "sinonimos.json"), "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
