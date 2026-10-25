"""
Prepara las copias del snapshot para el experimento 13 (NUNCA toca el original).

    python preparar_copias.py SNAPSHOT CARPETA_DESTINO

Crea en CARPETA_DESTINO:
  fuerzas.json         la fuerza que la neurona le da a cada par automático
                       (los vivos y los que la hormiguita mandó a cuarentena)
  sin_auto.db          sin NINGÚN enlace automático (solo los del agente y otros)
  h_apagada_todo.db    hormiguita apagada: todo lo que cortó vuelve
  neurona_040.db       la neurona decide al nacer con umbral 0.40
  neurona_050.db       ídem 0.50
  neurona_060.db       ídem 0.60

"Decide al nacer" se simula así: de todos los pares que las 5 reglas
propusieron (vivos + cuarentena), quedan solo los que la neurona juzga con
fuerza >= umbral. Los enlaces del agente y los demás tipos no se tocan.
Después se re-sincroniza el campo CSV `asociaciones`. El índice SDM no se
reconstruye (igual en todas las copias).
"""
import json
import os
import shutil
import sqlite3
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.abspath(os.path.join(AQUI, "..", "..", ".."))
sys.path.insert(0, RAIZ)

AUTO = ("sinonimo_explicito", "co_ocurrencia", "co_nombre", "co_semantica", "pmi_hebbiano")
IN_AUTO = "(" + ",".join(f"'{t}'" for t in AUTO) + ")"


def _resync(c):
    vec = {}
    for o, d in c.execute("SELECT origen, destino FROM sinapsis"):
        vec.setdefault(o, set()).add(d)
        vec.setdefault(d, set()).add(o)
    for (k,) in c.execute("SELECT concepto FROM largo_plazo").fetchall():
        c.execute("UPDATE largo_plazo SET asociaciones = ? WHERE concepto = ?",
                  (",".join(sorted(vec.get(k, ()))), k))


def calcular_fuerzas(snapshot, destino):
    from core import neurona_asociativa as na
    base = os.path.join(destino, "_base_fuerzas.db")
    shutil.copy(snapshot, base)
    c = sqlite3.connect(base)
    cur = c.cursor()
    nodos = {r[0] for r in cur.execute("SELECT concepto FROM largo_plazo")}
    pares = {}
    for o, d, t in cur.execute(f"SELECT origen, destino, tipo FROM sinapsis WHERE tipo IN {IN_AUTO}").fetchall():
        pares.setdefault(tuple(sorted((o, d))), ("vivo", t))
    for o, d, t in cur.execute(
            f"SELECT origen, destino, tipo FROM sinapsis_cuarentena WHERE tabla_origen = 'sinapsis' "
            f"AND restaurado = 0 AND tipo IN {IN_AUTO}").fetchall():
        k = tuple(sorted((o, d)))
        if k not in pares and o in nodos and d in nodos:
            pares[k] = ("cuarentena", t)
    na.estado(cur)
    c.commit()
    salida, juez = [], None
    for (a, b), (origen, t) in sorted(pares.items()):
        if juez is None or juez.concepto != a:
            juez = na.Juez(cur, a)
        salida.append([a, b, origen, t, round(float(juez.fuerza(b)), 4)])
    c.close()
    os.remove(base)
    return salida


def hacer_copia(snapshot, destino, nombre, fuerzas, umbral):
    ruta = os.path.join(destino, f"{nombre}.db")
    shutil.copy(snapshot, ruta)
    c = sqlite3.connect(ruta)
    quitar = [(a, b) for a, b, org, t, f in fuerzas if org == "vivo" and f < umbral]
    meter = {(a, b) for a, b, org, t, f in fuerzas if org == "cuarentena" and f >= umbral}
    for a, b in quitar:
        c.execute(f"DELETE FROM sinapsis WHERE tipo IN {IN_AUTO} AND "
                  "((origen = ? AND destino = ?) OR (origen = ? AND destino = ?))", (a, b, b, a))
    metidas = 0
    for o, d, t, p in c.execute(
            f"SELECT origen, destino, tipo, peso FROM sinapsis_cuarentena WHERE tabla_origen = 'sinapsis' "
            f"AND restaurado = 0 AND tipo IN {IN_AUTO}").fetchall():
        if tuple(sorted((o, d))) in meter:
            metidas += c.execute(
                "INSERT OR IGNORE INTO sinapsis (origen, destino, peso, tipo, creado_en) "
                "VALUES (?, ?, ?, ?, strftime('%s','now'))", (o, d, p, t)).rowcount
    _resync(c)
    c.commit()
    auto = c.execute(f"SELECT COUNT(*) FROM sinapsis WHERE tipo IN {IN_AUTO}").fetchone()[0]
    c.close()
    print(f"{nombre:16s} umbral {umbral:>5}: pares quitados {len(quitar):5d} | "
          f"vuelven de cuarentena {metidas:4d} | enlaces automáticos que quedan {auto}")


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    snapshot, destino = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
    if os.path.dirname(snapshot) == destino:
        sys.exit("El destino no puede ser la carpeta del snapshot.")
    os.makedirs(destino, exist_ok=True)
    fuerzas = calcular_fuerzas(snapshot, destino)
    json.dump(fuerzas, open(os.path.join(destino, "fuerzas.json"), "w"))
    print(f"pares juzgados por la neurona: {len(fuerzas)}")
    hacer_copia(snapshot, destino, "sin_auto", fuerzas, 99)
    hacer_copia(snapshot, destino, "h_apagada_todo", fuerzas, -1)
    for u in (0.40, 0.50, 0.60):
        hacer_copia(snapshot, destino, f"neurona_{int(u * 100):03d}", fuerzas, u)


if __name__ == "__main__":
    main()
