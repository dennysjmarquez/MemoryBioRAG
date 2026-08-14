"""
Aislamiento del efecto Fase C (jaccard re-ranking) sobre los 13 sinonimo fallidos.

diag13b: el piso sinonimos SÍ aplica (11/13 esperados score >= 0.70) pero quedan en
rango 6-83. diag13c: los esperados son origen 'literal' (no es el filtro de palabra
única). Y el pool final muestra orden NO descendente por score (0594: esperado 0.7664
> top5_min 0.7476 pero rango 8; top-5 con 0.748 luego 0.749).

Sospechoso: Fase C jaccard (memory_store.py:3260-3324) está ACTIVA porque
.env.local tiene BIORAG_RERANKING_JACCARD_ENABLED=1. Re-sortea head[:TOPK=20] por
score + 0.25*(jaccard/max_j) y RESTAURA solo el original_r0. Eso puede desplazar al
esperado fuera del top-5 aunque su score hibrido sea alto.

Script: corre los 13 con BIORAG_RERANKING_JACCARD_ENABLED=0 (Fase C OFF) y mide el
rango del esperado. Comparado con diag13b (Fase C ON, rangos 6-83), esto dice cuántos
casos se explican por Fase C.

Disciplina: copia temp, env seteado ANTES de importar core, nada modificado en repo.
"""
import json
import os
import sqlite3
import sys

os.environ["BIORAG_RERANKING_JACCARD_ENABLED"] = "0"
os.environ.pop("BIORAG_GABA_ACTIVO", None)

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "core"))

from core.memory_store import SQLiteMemoryBioRAG  # noqa: E402

DB_SRC = os.path.join(BASE, "snapshots", "qa_escape_qcr_20260811.db")
TEMP_DB = os.path.join(BASE, "MemoryBioRAG_Data", "memory_biorag_diag13d_temp.db")
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

    print(f"{'id':<6}{'query':<12}{'esperado':<42}{'rango_C_OFF':<12}{'score':<8}{'RESCATE'}")
    print("-" * 100)

    rescatados = 0
    for f in sin:
        q = f["query"]
        esp = f.get("expected")
        res, _ = db.buscar_por_frase(q, profundidad="activos", limite=5,
                                     ignore_peso_sinaptico=True)
        order = [r[0] for r in res]
        rank = order.index(esp) + 1 if esp in order else None
        s_esp = None
        if esp in order:
            s_esp = res[order.index(esp)][4]
        rescatado = (rank is not None and rank <= 5)
        if rescatado:
            rescatados += 1
        print(f"{f['id']:<6}{q:<12}{esp:<42}{str(rank):<12}{s_esp if s_esp else '-':<8}"
              f"{'SI' if rescatado else 'no'}")
        if rescatado:
            print(f"      top-5: " + ", ".join(f"{c[0]}({c[4]:.3f})" for c in res))

    print(f"\nRESCATADOS con Fase C OFF (rango<=5): {rescatados}/13")
    print("Comparar con diag13b (Fase C ON): los mismos casos en rango 6-83.")
    print("Si aqui entran al top-5 -> Fase C jaccard es quien los desplaza.")

    if os.path.exists(TEMP_DB):
        os.remove(TEMP_DB)


if __name__ == "__main__":
    main()
