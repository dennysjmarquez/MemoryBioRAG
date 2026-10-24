"""Repesa con la neurona TODAS las sinapsis automáticas de una COPIA de la memoria.

Sirve para medir "¿qué pasaría si todas las sinapsis automáticas hubieran nacido con la
neurona?". El motor v35 solo pesa las sinapsis NUEVAS; esto simula el régimen completo para
poder medirlo con el QA oficial y con la calidad del grafo.

Uso:  python repesar_copia.py ORIGEN DESTINO
      ORIGEN  la DB a copiar (p. ej. snapshots/qa_escape_qcr_20260811.db). NUNCA se escribe.
      DESTINO la copia que se crea y se repesa (si existe, se sobrescribe).

Qué se repesa: solo los tipos que crea el motor por reglas (AUTOMATICAS). Las sinapsis
manuales, latentes confirmadas, del DMN, legacy y de prueba quedan EXACTAMENTE igual.
Regla: peso = 0.5 + 0.5·fuerza (la misma del motor). No se borra ni se crea ninguna sinapsis.
"""
import json
import os
import shutil
import sqlite3
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.abspath(os.path.join(AQUI, "..", "..", ".."))
sys.path.insert(0, RAIZ)

from core import neurona_asociativa as na  # noqa: E402

AUTOMATICAS = ("sinonimo_explicito", "co_ocurrencia", "co_nombre", "co_semantica", "pmi_hebbiano")


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    origen, destino = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
    if origen == destino:
        sys.exit("ORIGEN y DESTINO no pueden ser el mismo archivo: el original no se toca.")
    for sufijo in ("", "-wal", "-shm"):
        if os.path.exists(destino + sufijo):
            os.remove(destino + sufijo)
    shutil.copyfile(origen, destino)
    t0 = time.time()
    con = sqlite3.connect(destino)
    cur = con.cursor()
    na.construir(cur)
    filas = cur.execute(
        f"SELECT rowid, origen, destino, tipo, peso FROM sinapsis WHERE tipo IN ({','.join('?' * len(AUTOMATICAS))}) "
        "ORDER BY origen", AUTOMATICAS).fetchall()
    por_origen = {}
    for f in filas:
        por_origen.setdefault(f[1], []).append(f)
    cambios, sin_decidir = [], 0
    for o, lista in por_origen.items():
        juez = na.Juez(cur, o)
        for rowid, _, d, tipo, peso in lista:
            f = juez.fuerza(d)
            if f is None:
                sin_decidir += 1
                continue
            cambios.append((na.peso_desde_fuerza(f), rowid))
    cur.executemany("UPDATE sinapsis SET peso = ? WHERE rowid = ?", cambios)
    con.commit()
    resumen = {}
    for tipo, n, mn, md, mx in cur.execute(
            "SELECT tipo, COUNT(*), MIN(peso), AVG(peso), MAX(peso) FROM sinapsis GROUP BY tipo ORDER BY 2 DESC"):
        resumen[tipo] = {"n": n, "min": round(mn, 3), "media": round(md, 3), "max": round(mx, 3),
                         "repesada": tipo in AUTOMATICAS}
    total = cur.execute("SELECT COUNT(*) FROM sinapsis").fetchone()[0]
    con.close()
    out = {"origen": origen, "destino": destino, "sinapsis_total": total, "repesadas": len(cambios),
           "sin_decidir": sin_decidir, "segundos": round(time.time() - t0, 2), "por_tipo": resumen}
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
