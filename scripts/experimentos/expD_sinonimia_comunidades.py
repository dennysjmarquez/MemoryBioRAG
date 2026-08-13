"""
Corazonada 2026-08-13: las comunidades PPMI son el puente de sinonimia.

Hipótesis falsable: para un caso sinonimo del benchmark ('query' -> concepto_esperado),
la query proyectada al espacio PPMI (vector_query) debe caer en la MISMA comunidad
que el concepto_esperado, aunque el texto de la query no matchee el contenido del nodo.

Si esto se cumple en una fracción muy superior al azar, las comunidades son un puente
de significado que las co-ocurrencias de palabras sueltas no pueden dar (lección
aciertos_word2vec_top5_coincidencia_lexica_no_semantica_20260808). Ese puente es la
palanca para cablear la memoria asociativa de otra forma: activar por comunidad, no
por palabra.

Medición: cruza los 61 casos sinonimo del benchmark contra las comunidades
knn_lpa (k=15) de expA_labels.json. Solo lectura; no modifica nada.

Uso:
    python3 scripts/experimentos/expD_sinonimia_comunidades.py
"""
import json
import sqlite3
import sys
from collections import Counter

import numpy as np

sys.path.insert(0, ".")
sys.path.insert(0, "core")
from core.ppmi_hybrid_search import IndicesBioRAG, _tokenizar  # noqa: E402


def cargar_vectores(db_path):
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    rows = con.execute("SELECT concepto, vector FROM nodos").fetchall()
    con.close()
    conceptos = [r[0] for r in rows]
    M = np.array([np.frombuffer(r[1], dtype=np.float32).copy() for r in rows])
    return conceptos, M


def main():
    db = "snapshots/qa_escape_qcr_20260811.db"
    labels = json.load(open("scripts/experimentos/expA_labels.json"))
    conceptos = labels["conceptos"]
    comunidades = labels["knn_lpa"]
    assert len(conceptos) == len(comunidades)

    # mapeo concepto -> comunidad
    com_por_concepto = dict(zip(conceptos, comunidades))
    idx_por_concepto = {c: i for i, c in enumerate(conceptos)}
    n_com = len(set(comunidades))
    print(f"nodos: {len(conceptos)}  comunidades: {n_com}")

    # centroides por comunidad (vectores PPMI, normalizados)
    _, M = cargar_vectores(db)
    normas = np.linalg.norm(M, axis=1, keepdims=True)
    normas[normas == 0] = 1.0
    M = M / normas
    centroides = {}
    acum = {}
    for i, c in enumerate(comunidades):
        if c not in acum:
            acum[c] = np.zeros(M.shape[1])
        acum[c] += M[i]
    for c, v in acum.items():
        n = np.linalg.norm(v)
        centroides[c] = v / n if n > 1e-10 else v
    centro_mat = np.array([centroides[c] for c in sorted(centroides)])
    comun_ordenadas = sorted(centroides)

    idx = IndicesBioRAG(db)

    casos = [json.loads(l) for l in open("scripts/casos_qa_baseline_v1.jsonl") if l.strip()]
    sin = [c for c in casos if c.get("categoria") == "sinonimo"]

    # --- baseline de azar: tamaño medio de comunidad ---
    tam = Counter(comunidades)
    prob_azar = sum(v * v for v in tam.values()) / (len(conceptos) ** 2)
    print(f"probabilidad de co-comunidad por azar (promedio): {prob_azar:.4f}")

    aciertos = 0
    esperado_no_indexado = 0
    ejemplos_ok, ejemplos_fail = [], []
    for caso in sin:
        q = caso["query"]
        esp = caso["concepto_esperado"]
        if esp not in com_por_concepto:
            esperado_no_indexado += 1
            continue
        com_esp = com_por_concepto[esp]

        # proyectar query al espacio PPMI
        vq = idx.vector_query(_tokenizar(q))
        if np.linalg.norm(vq) < 1e-10:
            continue
        vq = vq / np.linalg.norm(vq)
        # comunidad dominante de la query = max coseno contra centroides
        sims = centro_mat @ vq
        com_q = comun_ordenadas[int(np.argmax(sims))]

        ok = com_q == com_esp
        aciertos += ok
        (ejemplos_ok if ok else ejemplos_fail).append((caso["id"], q, esp, com_q, com_esp))

    total_medidos = len(sin) - esperado_no_indexado
    print(f"\ncasos sinonimo: {len(sin)} | esperado indexado: {total_medidos} "
          f"| no indexado: {esperado_no_indexado}")
    if total_medidos:
        print(f"co-comunidad query->esperado: {aciertos}/{total_medidos} "
              f"({aciertos / total_medidos:.1%})  vs azar {prob_azar:.1%}")
        print(f"ratio vs azar: {aciertos / total_medidos / prob_azar:.1f}x")

    print("\n--- aciertos (query cae en comunidad del esperado) ---")
    for e in ejemplos_ok:
        print(f"  {e[0]} | '{e[1]}' -> {e[2]}  (com {e[3]})")
    print(f"\n--- fallos ---")
    for e in ejemplos_fail:
        print(f"  {e[0]} | '{e[1]}' -> {e[2]}  (query com {e[3]} vs esperado com {e[4]})")

    # --- segunda vista: ¿el esperado está en la comunidad de la query, y además
    #     es de los vecinos PPMI más cercanos a la query? (más fuerte) ---
    print("\n--- vista fuerte: rango coseno query->esperado dentro de su comunidad ---")
    vq_cache = {}
    for caso in sin:
        q = caso["query"]
        esp = caso["concepto_esperado"]
        if esp not in idx_por_concepto:
            continue
        vq = vq_cache.get(q)
        if vq is None:
            vq = idx.vector_query(_tokenizar(q))
            if np.linalg.norm(vq) < 1e-10:
                continue
            vq = vq / np.linalg.norm(vq)
            vq_cache[q] = vq
        com_esp = com_por_concepto[esp]
        miem = [c for c, cc in com_por_concepto.items() if cc == com_esp and c in idx_por_concepto]
        if not miem:
            continue
        sims = np.array([_coseno(vq, M[idx_por_concepto[m]]) for m in miem])
        rango = int((sims >= _coseno(vq, M[idx_por_concepto[esp]])).sum())
        print(f"  {caso['id']} | '{q}' -> {esp}: rango {rango}/{len(miem)} en com {com_esp}")


def _coseno(a, b):
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    return float(np.dot(a, b) / (na * nb)) if na > 1e-10 and nb > 1e-10 else 0.0


if __name__ == "__main__":
    main()
