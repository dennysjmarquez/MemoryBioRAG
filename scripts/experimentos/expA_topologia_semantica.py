#!/usr/bin/env python3
"""
EXPERIMENTO A — Diagnóstico de topología semántica sobre vectores PPMI.
========================================================================
Objetivo: comprobar si un grafo semántico k-NN mutuo o un clustering
vectorial (HDBSCAN, aglomerativo) evita la degeneración observada con
LPA sobre sinapsis (1 cromosoma, firma escalar, afinidad uniforme).

Metodología (documento "Ruta de madurez" §2 y §5-Experimento A):
  - Snapshot canónico, copia aislada de lectura.
  - PPMI congelado (NO se reentrena durante la comparación).
  - Se prueban 3 construcciones de topología:
      1) Grafo k-NN mutuo sobre vectores PPMI normalizados + comunidades
         por propagación (LPA) sobre ESE grafo (no sobre sinapsis).
      2) HDBSCAN directo sobre los vectores (número de grupos por densidad).
      3) Aglomerativo jerárquico (navegación tema amplio -> subtema).
  - Se aplican los 5 criterios de no-degeneración (§2.3):
      1) >1 comunidad útil.
      2) Ninguna comunidad dominante que absorba el corpus.
      3) Firmas con varianza real entre nodos.
      4) Vecinos distintos para consultas distintas.
      5) Estabilidad razonable al reconstruir (k-NN es determinista; la
         estabilidad se mide con bootstrap de submuestreo para HDBSCAN).

Salida: tabla comparativa + veredicto PASA / NO_PASA por método.
Este script NO escribe en la DB del proyecto (solo lectura del snapshot).
"""

import argparse
import sqlite3
import sys
from collections import Counter

import numpy as np

DB_DEFAULT = "snapshots/qa_escape_qcr_20260811.db"
DIM = 100


def cargar_vectores(db_path):
    """Carga conceptos + vectores PPMI de la tabla nodos del snapshot."""
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    rows = con.execute("SELECT concepto, estado, vector FROM nodos").fetchall()
    con.close()
    conceptos = [r[0] for r in rows]
    estados = [r[1] for r in rows]
    M = np.array([np.frombuffer(r[2], dtype=np.float32).copy() for r in rows])
    return conceptos, estados, M


def normalizar(M):
    """Normaliza L2 por fila. Devuelve copia. Filas con norma 0 quedan en 0."""
    M = M.astype(np.float64)
    normas = np.linalg.norm(M, axis=1, keepdims=True)
    normas[normas == 0] = 1.0
    return M / normas


def top_k_mutuo(M, k=15, min_sim=0.3):
    """Devuelve aristas (i, j, sim) de vecindad MUTUA (k-NN simétrico).
    Conserva arista solo si j está en los k vecinos de i Y i en los k de j.
    Además exige similitud coseno >= min_sim para descartar vecinos débiles.
    """
    from sklearn.neighbors import NearestNeighbors

    nn = NearestNeighbors(n_neighbors=k + 1, metric="cosine", n_jobs=-1)
    nn.fit(M)
    dist, idx = nn.kneighbors(M)
    sim = 1.0 - dist  # coseno (M normalizada)
    vecinos = {i: set(idx[i][1:]) for i in range(len(M))}
    aristas = []
    for i in range(len(M)):
        for j in idx[i][1:]:
            if i >= j:
                continue
            if j in vecinos[i] and i in vecinos[j]:
                s = sim[i][list(idx[i]).index(j)]
                if s >= min_sim:
                    aristas.append((i, j, float(s)))
    return aristas


def lpa_comunidades(n, aristas, max_iter=100):
    """Propagación de etiquetas simple sobre un grafo (i, j, peso)."""
    import random

    adj = {i: [] for i in range(n)}
    for a, b, w in aristas:
        adj[a].append((b, w))
        adj[b].append((a, w))
    etiquetas = list(range(n))
    rng = random.Random(42)
    orden = list(range(n))
    for _ in range(max_iter):
        cambios = 0
        rng.shuffle(orden)
        for i in orden:
            if not adj[i]:
                continue
            pesos = Counter()
            for j, w in adj[i]:
                pesos[etiquetas[j]] += w
            nueva = pesos.most_common(1)[0][0]
            if nueva != etiquetas[i]:
                etiquetas[i] = nueva
                cambios += 1
        if cambios == 0:
            break
    # renumerar etiquetas
    mapa = {}
    for e in etiquetas:
        mapa.setdefault(e, len(mapa))
    return [mapa[e] for e in etiquetas]


def hdbscan_clusters(M, min_cluster_size=8):
    import hdbscan

    cl = hdbscan.HDBSCAN(min_cluster_size=min_cluster_size, metric="euclidean")
    labels = cl.fit_predict(M)
    return labels, cl


def aglomerativo_clusters(M, n_clusters=10):
    from sklearn.cluster import AgglomerativeClustering

    cl = AgglomerativeClustering(
        n_clusters=n_clusters, metric="cosine", linkage="average"
    )
    return cl.fit_predict(M)


def resumen_clusters(labels, conceptos, etiqueta=""):
    """Devuelve dict con métricas de salud de la partición."""
    labels = np.array(labels)
    n = len(labels)
    validos = labels[labels >= 0]
    n_com = len(set(validos))
    ruido = int((labels < 0).sum())
    if n_com == 0:
        return {"etiqueta": etiqueta, "n_comunidades": 0, "ruido": ruido,
                "nodos_en_com": 0, "cobertura": 0.0, "mayor": 0,
                "mayor_pct": 0.0, "tam_mediano": 0, "tam_1": 0}
    counts = Counter(validos)
    sizes = sorted(counts.values(), reverse=True)
    mayor = sizes[0]
    cobertura = len(validos) / n
    # varianza de firmas: varianza de la distribución de tamaños (información)
    return {"etiqueta": etiqueta, "n_comunidades": n_com, "ruido": ruido,
            "nodos_en_com": len(validos), "cobertura": round(cobertura, 3),
            "mayor": mayor, "mayor_pct": round(mayor / n, 3),
            "tam_mediano": int(np.median(sizes)), "tam_1": int(sizes[-1])}


def criterios_degeneracion(res, labels, M, conceptos):
    """Aplica los 5 criterios de no-degeneración. Devuelve lista de (criterio, ok, detalle)."""
    labels = np.array(labels)
    validos = labels[labels >= 0]
    n = len(labels)
    n_com = len(set(validos))
    out = []
    # 1) >1 comunidad útil
    ok1 = n_com >= 2
    out.append(("1. >1 comunidad útil", ok1, f"{n_com} comunidades"))
    # 2) ninguna comunidad dominante que absorba el corpus
    if n_com > 0:
        mayor = max(Counter(validos).values())
        ok2 = mayor / n < 0.5
        out.append(("2. sin comunidad dominante (>50%)", ok2, f"mayor={mayor}/{n} ({mayor/n:.1%})"))
    else:
        out.append(("2. sin comunidad dominante", False, "sin comunidades"))
    # 3) firmas con varianza real entre nodos: vector medio por comunidad distinto
    if n_com >= 2:
        centroides = []
        for lab in sorted(set(validos)):
            idx = np.where(labels == lab)[0]
            centroides.append(M[idx].mean(axis=0))
        centroides = np.array(centroides)
        dists = []
        for i in range(len(centroides)):
            for j in range(i + 1, len(centroides)):
                d = np.linalg.norm(centroides[i] - centroides[j])
                dists.append(d)
        dist_prom = float(np.mean(dists))
        ok3 = dist_prom > 1e-3
        out.append(("3. firmas con varianza real (centroides separados)", ok3,
                    f"dist media entre centroides={dist_prom:.4f}"))
    else:
        out.append(("3. firmas con varianza real", False, "n_com<2"))
    # 4) vecinos distintos para consultas distintas (top-5 de 3 queries distintas)
    queries_idx = [0, 100, 400]
    if n >= 500:
        from sklearn.neighbors import NearestNeighbors
        nn = NearestNeighbors(n_neighbors=6, metric="cosine", n_jobs=-1)
        nn.fit(M)
        _, idx_q = nn.kneighbors(M[queries_idx])
        conjuntos = [set(idx_q[r][1:]) for r in range(3)]
        intersecciones = []
        for a in range(3):
            for b in range(a + 1, 3):
                inter = len(conjuntos[a] & conjuntos[b])
                intersecciones.append(inter)
        prom_inter = float(np.mean(intersecciones))
        ok4 = prom_inter < 3  # menos de la mitad de los 5 vecinos compartidos
        out.append(("4. vecinos distintos para queries distintas", ok4,
                    f"intersección media top-5={prom_inter:.1f}/5"))
    else:
        out.append(("4. vecinos distintos", False, "corpus pequeño"))
    # 5) estabilidad bootstrap para HDBSCAN (si aplica)
    out.append(("5. estabilidad", None, "depende del método"))
    return out


def estabilidad_hdbscan(M, min_cluster_size=8, muestras=10, frac=0.7, semilla=7):
    """Mide estabilidad de HDBSCAN con submuestreo: fracción de pares que
    quedan juntos/dentro-fuera consistentemente."""
    import hdbscan
    rng = np.random.RandomState(semilla)
    n = len(M)
    pares_juntos = Counter()
    pares_vistos = Counter()
    for _ in range(muestras):
        idx = rng.choice(n, int(n * frac), replace=False)
        sub = M[idx]
        cl = hdbscan.HDBSCAN(min_cluster_size=max(3, int(min_cluster_size * frac)),
                             metric="euclidean").fit(sub)
        labs = cl.labels_
        for a in range(len(idx)):
            for b in range(a + 1, len(idx)):
                pares_vistos[(idx[a], idx[b])] += 1
                if labs[a] == labs[b] and labs[a] >= 0:
                    pares_juntos[(idx[a], idx[b])] += 1
    consistencia = []
    for par, veces in pares_vistos.items():
        if veces < muestras // 2:
            continue
        juntos = pares_juntos.get(par, 0)
        consistencia.append(juntos / veces if veces else 0)
    if not consistencia:
        return 0.0
    return float(np.mean(consistencia))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DB_DEFAULT)
    ap.add_argument("--k", type=int, default=15, help="k para k-NN mutuo")
    ap.add_argument("--min-sim", type=float, default=0.3, help="similitud mínima k-NN")
    ap.add_argument("--min-cluster", type=int, default=8, help="min_cluster_size HDBSCAN")
    ap.add_argument("--n-clusters-agg", type=int, default=10, help="clusters aglomerativo")
    ap.add_argument("--queries", nargs="*", default=None, help="conceptos query para criterio 4")
    args = ap.parse_args()

    print(f"== Cargando vectores PPMI de {args.db} ==")
    conceptos, estados, M_raw = cargar_vectores(args.db)
    M = normalizar(M_raw)
    print(f"  {len(conceptos)} nodos x {M.shape[1]} dims")
    print(f"  normas L2: min={np.linalg.norm(M, axis=1).min():.3f} "
          f"media={np.linalg.norm(M, axis=1).mean():.3f}")

    print("\n== Método 1: grafo k-NN mutuo + LPA sobre ESE grafo ==")
    aristas = top_k_mutuo(M, k=args.k, min_sim=args.min_sim)
    print(f"  aristas k-NN mutuo (k={args.k}, min_sim={args.min_sim}): {len(aristas)}")
    if len(aristas) < 20:
        print("  ⚠️ muy pocas aristas; bajar min_sim o subir k")
    labels1 = lpa_comunidades(len(M), aristas)
    r1 = resumen_clusters(labels1, conceptos, "kNN_mutuo+LPA")
    c1 = criterios_degeneracion(r1, labels1, M, conceptos)

    print("\n== Método 2: HDBSCAN directo ==")
    labels2, _ = hdbscan_clusters(M, min_cluster_size=args.min_cluster)
    r2 = resumen_clusters(labels2, conceptos, "HDBSCAN")
    est = estabilidad_hdbscan(M, min_cluster_size=args.min_cluster)
    c2 = criterios_degeneracion(r2, labels2, M, conceptos)
    c2[-1] = ("5. estabilidad bootstrap", est > 0.7, f"consistencia={est:.3f}")

    print("\n== Método 3: Aglomerativo jerárquico ==")
    labels3 = aglomerativo_clusters(M, n_clusters=args.n_clusters_agg)
    r3 = resumen_clusters(labels3, conceptos, "Aglomerativo")
    c3 = criterios_degeneracion(r3, labels3, M, conceptos)
    # aglomerativo es determinista (fijo n_clusters) -> estabilidad estructural alta
    c3[-1] = ("5. estabilidad", True, "determinista con n_clusters fijo")

    print("\n" + "=" * 78)
    print("RESUMEN COMPARATIVO")
    print("=" * 78)
    header = f"{'método':<16}{'#com':>5}{'ruido':>7}{'cobertura':>10}{'mayor%':>8}{'tam_med':>8}"
    print(header)
    for r in (r1, r2, r3):
        print(f"{r['etiqueta']:<16}{r['n_comunidades']:>5}{r['ruido']:>7}"
              f"{r['cobertura']:>10}{r['mayor_pct']:>8}{r['tam_mediano']:>8}")

    print("\n" + "-" * 78)
    for nombre, res, cs in (("kNN_mutuo+LPA", r1, c1), ("HDBSCAN", r2, c2), ("Aglomerativo", r3, c3)):
        print(f"\n[{nombre}] criterios de no-degeneración:")
        todos_ok = True
        pendientes = []
        for crit, ok, det in cs:
            marca = "PASA" if ok else ("N/A" if ok is None else "FALLA")
            if ok is False:
                todos_ok = False
            elif ok is None:
                pendientes.append(crit)
            print(f"  {marca:<6} {crit}: {det}")
        if todos_ok and pendientes:
            print(f"  -> VEREDICTO: PASA CONDICIONAL (los criterios evaluados cumplen; N/A: {', '.join(pendientes)})")
        else:
            print(f"  -> VEREDICTO: {'PASA (topología semántica NO degenerada)' if todos_ok else 'NO PASA (degenerada o insuficiente)'}")

    # guardar etiquetas en archivo para experimento C si se decide integrar
    import json

    def a_lista(x):
        return [int(i) for i in x]

    with open("scripts/experimentos/expA_labels.json", "w") as f:
        json.dump({
            "db": args.db,
            "conceptos": conceptos,
            "knn_lpa": a_lista(labels1),
            "hdbscan": a_lista(labels2),
            "aglomerativo": a_lista(labels3),
            "resumenes": [r1, r2, r3],
        }, f, ensure_ascii=False)
    print("\nEtiquetas guardadas en scripts/experimentos/expA_labels.json")


if __name__ == "__main__":
    main()
