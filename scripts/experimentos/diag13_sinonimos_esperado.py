"""
Diagnóstico de Claude Web (2026-08-13) — Capa 4 sinónimos vs los 13 fallidos.

Pregunta: de los 13 casos sinonimo fallidos, ¿el nodo esperado ya tiene la palabra de la
query en su propio campo largo_plazo.sinonimos?

  - Si SÍ en varios casos → el mecanismo existe (Capa 4 l.4055-4070 inyecta al pool por
    LIKE substring, y l.3170 da piso max(0.70+0.10*ppmi, score) si sinonimos_ratio>=0.95)
    pero no se está disparando → BUG concreto y acotado a encontrar.
  - Si NO → el problema real es un HUECO DE DATOS: los 13 nodos no tienen el sinónimo
    que la gente usa para buscarlos. Solución: enriquecer manualmente el campo sinonimos
    de esos 13 nodos (sin tocar código de scoring).

Para cada caso compruebo:
  a) LIKE substring: ¿la palabra de la query aparece como substring en sinonimos?
     (replica exacta de la condición de Capa 4)
  b) score_simbolico_sinonimos(tokens_query, sinonimos) — la función real del motor
     (fallback_simbolico.py:388). >= 0.95 dispararía el piso 0.70.
  c) Match en contenido/concepto: ¿la palabra aparece en contenido o concepto?
  d) Comportamiento real: ¿el esperado entra al pool (limite=200) y en qué rango queda?
     ¿Qué sinonimos_ratio recibe realmente?

Disciplina: copia temp del snapshot, solo lectura, nada del core modificado.

Uso:
    python3 scripts/experimentos/diag13_sinonimos_esperado.py
"""
import json
import os
import sqlite3
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "core"))

from core.fallback_simbolico import score_simbolico_sinonimos, score_simbolico_concepto  # noqa: E402
from core.memory_store import SQLiteMemoryBioRAG  # noqa: E402

DB_SRC = os.path.join(BASE, "snapshots", "qa_escape_qcr_20260811.db")
TEMP_DB = os.path.join(BASE, "MemoryBioRAG_Data", "memory_biorag_diag13_temp.db")
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

    con = sqlite3.connect(f"file:{TEMP_DB}?mode=ro", uri=True)
    nodo_info = {}
    for r in con.execute("SELECT concepto, sinonimos, contenido, estado FROM largo_plazo").fetchall():
        nodo_info[r[0]] = {"sinonimos": r[1] or "", "contenido": r[2] or "", "estado": r[3]}
    con.close()

    db = SQLiteMemoryBioRAG(db_path=TEMP_DB)

    fallidos = [json.loads(l) for l in open(FALLIDOS) if l.strip()]
    sin = [f for f in fallidos if f.get("categoria") == "sinonimo"]

    print(f"casos sinonimo fallidos: {len(sin)}\n")
    print(f"{'id':<6}{'query':<16}{'esperado':<42}{'estado':<9}"
          f"{'sin_like':<9}{'sin_ratio':<10}{'conc_ratio':<11}{'pool_rank':<9}")
    print("-" * 118)

    cuentan_sin = 0
    cuentan_conc = 0
    con_en_pool = 0
    for f in sin:
        q = f["query"]
        esp = f.get("expected")
        info = nodo_info.get(esp)
        if info is None:
            print(f"{f['id']:<6}{q:<16}{esp:<42}{'NO_EXISTE':<9}")
            continue
        sinonimos = info["sinonimos"]
        contenido = info["contenido"]
        q_toks = set(q.lower().replace("_", " ").split())
        # a) LIKE substring — réplica Capa 4
        sin_like = all(w.lower() in sinonimos.lower() for w in q_toks) if sinonimos else False
        # b) score_simbolico_sinonimos — función real del motor
        sin_ratio = score_simbolico_sinonimos(q_toks, sinonimos)
        # c) concepto
        conc_ratio = score_simbolico_concepto(q_toks, esp)
        # d) comportamiento real del pool
        res, _ = db.buscar_por_frase(q, profundidad="activos", limite=200,
                                     ignore_peso_sinaptico=True)
        pool_order = [r[0] for r in res]
        rank = pool_order.index(esp) + 1 if esp in pool_order else None
        if esp in pool_order:
            con_en_pool += 1
        if sin_ratio >= 0.95:
            cuentan_sin += 1
        if conc_ratio >= 0.95:
            cuentan_conc += 1
        flag = "SIN_HUE" if sin_ratio < 0.95 else "BUG?"
        print(f"{f['id']:<6}{q:<16}{esp:<42}{info['estado']:<9}"
              f"{'S' if sin_like else 'N':<9}{sin_ratio:<10.3f}{conc_ratio:<11.3f}"
              f"{str(rank) if rank else '-':<9}  {flag}")
        if sinonimos:
            sn = sinonimos[:60]
        else:
            sn = "(vacio)"
        print(f"      sinonimos: {sn}")

    print(f"\nRESUMEN: sinonimos_ratio>=0.95: {cuentan_sin}/13 | concepto_ratio>=0.95: "
          f"{cuentan_conc}/13 | esperado en pool(200): {con_en_pool}/13")

    if os.path.exists(TEMP_DB):
        os.remove(TEMP_DB)


if __name__ == "__main__":
    main()
