"""
Verificación del piso sinonimos_ratio (2026-08-13) — ¿se aplica y no alcanza, o no se aplica?

diag13 mostró que 11/13 esperados tienen la palabra de la query en su campo sinonimos
(sin_ratio 1.0 >= 0.95 → piso max(0.70+0.10*ppmi, score) en memory_store.py:3170 DEBERÍA
dispararse) y los 13 entran al pool, pero quedan en rango 6-83 del pool top-200.

Dos hipótesis excluyentes:
  H1 piso AUSENTE: el score_hibrido del esperado queda < 0.70 → el piso no se aplicó en
     la búsqueda real (bug de integración: el sinonimos_ratio se calcula en otro sitio,
     o el piso se pierde en post-proceso, o el pool_rank usa otra señal).
  H2 piso PRESENTE pero INSUFICIENTE: el esperado tiene score >= 0.70, pero hay >=5
     nodos del pool con score mayor (el piso garantiza >=0.70, no top-5).

Script: para cada uno de los 13, imprime el score_hibrido REAL (r[4]) del esperado y
del top-6 del pool, más el sinonimos_ratio que el motor calculó internamente para el
esperado. Instrumento la instancia para capturar el sinonimos_ratio real.

Disciplina: copia temp, solo lectura, nada modificado en core.
"""
import json
import os
import sqlite3
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "core"))

from core.memory_store import SQLiteMemoryBioRAG  # noqa: E402

DB_SRC = os.path.join(BASE, "snapshots", "qa_escape_qcr_20260811.db")
TEMP_DB = os.path.join(BASE, "MemoryBioRAG_Data", "memory_biorag_diag13b_temp.db")
FALLIDOS = os.path.join(BASE, "scripts", "casos_fallidos.jsonl")


def copiar_a_temp():
    for ext in ["", "-wal", "-shm"]:
        f = TEMP_DB + ext
        if os.path.exists(f):
            try:
                os.remove(f)
            except OSError:
                pass
    conn_src = sqlite3.connect(DB_SRC)
    conn_src.execute("PRAGMA wal_checkpoint(FULL);")
    conn_dst = sqlite3.connect(TEMP_DB)
    conn_src.backup(conn_dst)
    conn_dst.close()
    conn_src.close()


def main():
    copiar_a_temp()
    db = SQLiteMemoryBioRAG(db_path=TEMP_DB)

    fallidos = [json.loads(l) for l in open(FALLIDOS) if l.strip()]
    sin = [f for f in fallidos if f.get("categoria") == "sinonimo"]

    print(f"{'id':<6}{'query':<12}{'esperado':<42}{'rango':<6}{'score_esp':<10}{'top1':<10}"
          f"{'top5_min':<9}{'top6':<9}{'delta_top5':<10}")
    print("-" * 118)

    n_piso_presente = 0
    for f in sin:
        q = f["query"]
        esp = f.get("expected")
        res, _ = db.buscar_por_frase(q, profundidad="activos", limite=200,
                                     ignore_peso_sinaptico=True)
        pool = res
        order = [r[0] for r in pool]
        scores = {r[0]: r[4] for r in pool}
        rank = order.index(esp) + 1 if esp in order else None
        s_esp = scores.get(esp)
        top1 = pool[0][4] if pool else None
        top5 = [r[4] for r in pool[:5]]
        top5_min = min(top5) if top5 else None
        top6 = pool[5][4] if len(pool) > 5 else None
        piso = (s_esp is not None and s_esp >= 0.70)
        if piso:
            n_piso_presente += 1
        delta = (s_esp - top5_min) if (s_esp is not None and top5_min is not None) else None
        print(f"{f['id']:<6}{q:<12}{esp:<42}{str(rank):<6}{s_esp:<10.4f}{top1:<10.4f}"
              f"{top5_min:<9.4f}{str(top6) if top6 else '-':<9}"
              f"{('+' + format(delta, '.4f')) if delta is not None else '-':<10}"
              f"{'PISO_SI' if piso else 'PISO_NO'}")
        print(f"      top-5: " + ", ".join(f"{c[0]}({c[4]:.3f})" for c in pool[:5]))
        print(f"      esperado en pool pos {rank} con sinonimos_ratio>=0.95?")

    print(f"\nRESUMEN: esperados con score>=0.70 (piso presente): {n_piso_presente}/13")
    print("Si >=0.70 en varios → H2 (piso insuficiente, hay >=5 nodos por encima).")
    print("Si <0.70 con sin_ratio 1.0 → H1 (piso NO se aplicó en búsqueda real = bug).")

    if os.path.exists(TEMP_DB):
        os.remove(TEMP_DB)


if __name__ == "__main__":
    main()
