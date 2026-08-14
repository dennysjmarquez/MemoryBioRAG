"""
Experimento G2 — Gate Fino "Protección de Match Nominal" (2026-08-14).

Contexto: expG (expG_gated_synonym_rescue.py) midió que el gate score_top1<umbral
es inerte (los 12 fallidos tienen score 0.70-0.84, el gate nunca se abre). El
re-ranking global por idf_sin rescató 8/12 con 1 roto (neto +7) pero rompió el
caso 0811 ('biorag' -> protocolo_busqueda_biorag_automatica), que es correcto
en baseline (rank 4) y fue desplazado por nodos ricos en sinónimos.

El auditor (vía Dennys) propone la REGLA DE PROTECCIÓN DE MATCH EN CONCEPTO:
  - Si el Top-1 del baseline tiene match literal de token/stem de la query en su
    campo concepto  =>  el Top-1 está "protegido" (match nominal directo, no se
    toca con idf_sin). Se conserva el ranking baseline (0 regresiones).
  - Si NO tiene match literal en concepto  =>  se permite el re-ranking por
    idf_sin sobre el pool de candidatos (rescata sinonimia pura).

Preguntas empíricas que este script contesta (no asumidas):
  Q1. Regla del auditor exacta: cuántos rescata y cuántos rompe sobre los 61
      casos sinonimo (baseline limite=5, pool real last_todos, sort estable).
  Q2. Estabilidad: 0805 no debe aparecer como roto (su esperado es top1 baseline;
      'cv' no tokeniza => idf_sin=0.0 => sort estable conserva el orden).
  Q3. Variante refinada: proteger si >=3 de los 5 del top-5 baseline tienen match
      literal del token en su concepto (en vez de solo el Top-1), para no matar
      rescates cuyo top-1 casualmente comparte token (0594, 0625, 0828, 0840,
      0878 tienen match en top-1 y serían bloqueados por la regla del auditor).

Disciplina: copia aislada del snapshot a temp, solo lectura, NO toca producción.
Solo lectura de DB (conexión ro al índice), sin escrituras.

Uso:
    python3 scripts/experimentos/expG2_fine_gated_idf_sin.py
"""
import json
import os
import sqlite3
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "core"))

from core.memory_store import SQLiteMemoryBioRAG  # noqa: E402
from core.ppmi_hybrid_search import IndicesBioRAG, _tokenizar  # noqa: E402

DB_SRC = os.path.join(BASE, "snapshots", "qa_escape_qcr_20260811.db")
TEMP_DB = os.path.join(BASE, "MemoryBioRAG_Data", "memory_biorag_expe_temp_g2.db")
CASES = os.path.join(BASE, "scripts", "casos_qa_baseline_v1.jsonl")


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


def tokens(s):
    return set(_tokenizar(s))


def baseline(db, q):
    res, _ = db.buscar_por_frase(q, profundidad="activos", limite=5,
                                 ignore_peso_sinaptico=True)
    return [r[0] for r in res]


def pool_real(db, q):
    # last_todos se guarda tras cada búsqueda; es el universo de candidatos
    # que el pipeline consideró antes del ranking híbrido final.
    todos = getattr(db, "last_todos", []) or []
    if todos and isinstance(todos[0], tuple) and len(todos[0]) > 1:
        return {r[1] for r in todos}
    # fallback defensivo: pool amplio (último recurso, no es el mismo universo)
    res, _ = db.buscar_por_frase(q, profundidad="activos", limite=200,
                                 ignore_peso_sinaptico=True)
    return {r[0] for r in res}


def rerank_idf(idx, qt, pool_set, topn=5):
    ranked = sorted(((idx.idf_sin(qt, cn, pool_set), cn) for cn in pool_set),
                    key=lambda x: x[0], reverse=True)
    return [cn for _, cn in ranked[:topn]]


def match_top1_auditor(qt, top1):
    """Regla del auditor: Top-1 con match literal de token en su concepto."""
    if not qt:
        return False  # query no tokenizable ('cv'): sin señal, no proteger por match
    return bool(qt & tokens(top1))


def match_top5_minoritario(top5, qt, umbral=3):
    """Variante refinada: proteger si >= umbral de los top-5 tienen el token
    de la query en su concepto (match nominal colectivo fuerte)."""
    if not qt:
        return False
    n = sum(1 for cn in top5 if qt & tokens(cn))
    return n >= umbral


def main():
    copiar_a_temp()
    db = SQLiteMemoryBioRAG(db_path=TEMP_DB)
    idx = IndicesBioRAG(TEMP_DB)

    casos = [json.loads(l) for l in open(CASES) if l.strip()]
    sin = [c for c in casos if c.get("categoria") == "sinonimo"]
    print(f"casos sinonimo: {len(sin)}")

    resultados = []
    for caso in sin:
        q, esp = caso["query"], caso["concepto_esperado"]
        top5 = baseline(db, q)
        ok_base = esp in top5
        pool = pool_real(db, q)
        qt = set(_tokenizar(q))
        top5_idf = rerank_idf(idx, qt, pool)
        ok_idf = esp in top5_idf
        top1 = top5[0] if top5 else None
        m_t1 = match_top1_auditor(qt, top1) if top1 else False
        m_t5 = match_top5_minoritario(top5, qt)

        # GUARD OBLIGATORIO: query no tokenizable ('cv', 2 chars) => idf_sin sin
        # señal (0.0 para todo el pool) => re-rankear es ruido arbitrario sobre
        # un set() de Python. Proteger el baseline siempre en ese caso.
        guard_sin_tokens = (len(qt) == 0)

        # Ranking según la regla del auditor (Q1)
        if guard_sin_tokens or m_t1:
            top5_auditor = top5
        else:
            top5_auditor = top5_idf
        ok_auditor = esp in top5_auditor

        # Ranking según la variante refinada (Q3)
        if guard_sin_tokens or m_t5:
            top5_refinado = top5
        else:
            top5_refinado = top5_idf
        ok_refinado = esp in top5_refinado

        resultados.append({
            "id": caso["id"], "q": q, "esp": esp, "top5": top5,
            "ok_base": ok_base, "ok_idf": ok_idf, "ok_auditor": ok_auditor,
            "ok_refinado": ok_refinado, "m_t1": m_t1, "m_t5": m_t5,
            "qt_len": len(qt), "en_pool": esp in pool,
        })

    def reportar(clave):
        resc = [r for r in resultados if not r["ok_base"] and r[clave]]
        rotos = [r for r in resultados if r["ok_base"] and not r[clave]]
        return resc, rotos

    print("\n[Q1] REGLA DEL AUDITOR: proteger top-1 con match literal en concepto")
    resc, rotos = reportar("ok_auditor")
    print(f"  rescates={len(resc)} rotos={len(rotos)} neto={len(resc)-len(rotos)}")
    for r in resc:
        print(f"    RESC {r['id']} '{r['q']}' -> {r['esp'][:45]}")
    for r in rotos:
        print(f"    ROTO {r['id']} '{r['q']}' -> {r['esp'][:45]}")

    print("\n[Q3] VARIANTE REFINADA: proteger si >=3/5 top-5 con match en concepto")
    resc, rotos = reportar("ok_refinado")
    print(f"  rescates={len(resc)} rotos={len(rotos)} neto={len(resc)-len(rotos)}")
    for r in resc:
        print(f"    RESC {r['id']} '{r['q']}' -> {r['esp'][:45]}")
    for r in rotos:
        print(f"    ROTO {r['id']} '{r['q']}' -> {r['esp'][:45]}")

    print("\n[Q2] ESTABILIDAD: casos correctos que idf_sin desplaza del top-5")
    print("     (sin ninguna protección, cuántos se romperían)")
    for r in resultados:
        if r["ok_base"] and not r["ok_idf"]:
            print(f"    {r['id']} '{r['q']}' -> {r['esp'][:45]}  match_t1={r['m_t1']}")

    print("\n[REF] DETALLE de los 12 fallidos: qué hace cada regla")
    for r in resultados:
        if not r["ok_base"]:
            v = lambda ok: "SALVA" if ok else "pierde"  # noqa: E731
            print(f"    {r['id']} '{r['q']:<16}' idf={v(r['ok_idf']):<7} "
                  f"auditor={v(r['ok_auditor']):<7} refinado={v(r['ok_refinado']):<7} "
                  f"match_t1={r['m_t1']} match_t5={r['m_t5']}")

    # limpieza
    for f in [TEMP_DB, TEMP_DB + "-wal", TEMP_DB + "-shm"]:
        if os.path.exists(f):
            os.remove(f)


if __name__ == "__main__":
    main()
