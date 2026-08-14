"""
Confirmación del mecanismo exacto de pérdida (2026-08-13) — diag13c

diag13b mostró: el piso sinonimos SÍ se aplica (11/13 esperados >= 0.70) pero quedan
en rango 6-83. El caso 0594 (esperado 0.7664 > top5_min 0.7476 pero rango 8) sugiere
un REORDENAMIENTO posterior al sort: el filtro de palabra única (memory_store.py:4595)
mueve resultados con origen en _ORIGENES_NO_LITERALES {typo,expansion,latente,cadena,
simbolico,dimensional_fallback,semantica,unicode} al FINAL, después de los literales,
sin importar su score.

Y la Capa 4 sinónimos asigna origen ("semantica", ...) (memory_store.py:4085) → un nodo
rescatado por sinonimos es NO literal → termina detrás de todos los literales.

Script: para cada caso sinonimo, corre buscar_por_frase CON limite=5 (camino exacto de
evaluar_qa.py:93) y lee self.last_origen_scores para clasificar el origen REAL del
esperado y de los 5 que quedan arriba. Esto decide si el culpable es el filtro de
palabra única (esperado NO literal) u otro mecanismo.
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
TEMP_DB = os.path.join(BASE, "MemoryBioRAG_Data", "memory_biorag_diag13c_temp.db")
FALLIDOS = os.path.join(BASE, "scripts", "casos_fallidos.jsonl")

_ORIGENES_NO_LITERALES = {"typo", "expansion", "latente", "cadena", "simbolico",
                          "dimensional_fallback", "semantica", "unicode"}


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

    print(f"{'id':<6}{'query':<12}{'esperado':<42}{'origen':<20}{'rango':<6}{'esp_literal':<12}{'causa'}")
    print("-" * 120)

    n_no_literal = 0
    n_literal = 0
    for f in sin:
        q = f["query"]
        esp = f.get("expected")
        res, _ = db.buscar_por_frase(q, profundidad="activos", limite=5,
                                     ignore_peso_sinaptico=True)
        origenes = db.last_origen_scores or {}
        pool_order = [r[0] for r in res]
        rank = pool_order.index(esp) + 1 if esp in pool_order else None

        o_esp = origenes.get(esp, "SIN_DATO")
        esp_no_lit = (o_esp[0] in _ORIGENES_NO_LITERALES) if isinstance(o_esp, tuple) else None

        # Cuántos literales quedan arriba y cuántos no-literales
        supers = []
        for c in pool_order:
            o = origenes.get(c, ("?", 0.0))
            if isinstance(o, tuple) and o[0] not in _ORIGENES_NO_LITERALES:
                supers.append(f"{c}(lit:{o[0]})")
        causa = ""
        if rank == 5:
            causa = "RANGO_5_CUESTIONABLE"
        if isinstance(o_esp, tuple) and o_esp[0] in _ORIGENES_NO_LITERALES:
            causa = "FILTRO_PALABRA_UNICA"
            n_no_literal += 1
        elif isinstance(o_esp, tuple):
            n_literal += 1

        print(f"{f['id']:<6}{q:<12}{esp:<42}{str(o_esp):<20}{str(rank):<6}"
              f"{str(esp_no_lit):<12}{causa}")
        if supers:
            print(f"      literales que quedaron arriba: {', '.join(supers)}")

    print(f"\nRESUMEN: esperados NO literales (filtro palabra única los puso al final): {n_no_literal}"
          f" | esperados literales: {n_literal}")
    print("Si n_no_literal es alto → el culpable es que Capa 4 sinónimos usa origen 'semantica'")
    print("  (memory_store.py:4085) y el filtro de palabra única (l.4595) lo relega tras los literales.")

    if os.path.exists(TEMP_DB):
        os.remove(TEMP_DB)


if __name__ == "__main__":
    main()
