#!/usr/bin/env python3
"""Experimento: ¿la Neurona de Puentes aporta algo sobre el umbral de cobertura?

No entrena para lucirse: entrena para responder una pregunta incómoda.
Si un umbral bien puesto iguala a la neurona, la neurona sobra y hay que decirlo.

Protocolo
    - Banco: snapshots/qa_escape_qcr_20260811.db (6 hubs, 30 bridges) + 921 casos.
    - Compuerta ancha (0.20): deja pasar todo lo que el hub ve como débil, que
      es donde el problema duele (medido: 154 disparos, 8 aciertos = 5,2 %).
    - Etiqueta por ARCO (consulta, puente): y=1 si el canónico de ese hub está
      en el oro de la consulta, y=0 si no.
    - Guardia: 20 % de los NODOS del oro por hash (regla de la neurona de
      ranking). No se entrena con ellos jamás.
    - Se compara EN GUARDIA: compuerta sola vs neurona sobre la misma compuerta.
"""
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from core.concept_hub import _indice_bridges, _tokenizar_stems  # noqa: E402
from core.memory import neurona_puentes as npu  # noqa: E402

DB = RAIZ / "snapshots" / "qa_escape_qcr_20260811.db"
CASOS = RAIZ / "scripts" / "casos_qa_baseline_v1.jsonl"
COMPUERTA = 0.20


def es_guardia(nodo):
    return int(hashlib.sha256(nodo.encode("utf-8")).hexdigest()[:8], 16) % 5 == 0


def cargar_casos():
    salida = []
    with open(CASOS, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            try:
                c = json.loads(linea)
            except json.JSONDecodeError:
                continue
            esperado = (c.get("esperado") or c.get("gold")
                        or c.get("concepto_esperado") or [])
            if isinstance(esperado, str):
                esperado = [esperado]
            q = c.get("query") or c.get("consulta") or ""
            if q and esperado:
                salida.append((q, set(esperado)))
    return salida


def arcos(idx, casos):
    """Construye (rasgos, etiqueta, nodo) por cada arco que pasa la compuerta."""
    X, y, nodos = [], [], []
    for q, oro in casos:
        qs = _tokenizar_stems(q)
        if not qs:
            continue
        pesos = {s: idx.idf.get(s, idx.idf_max) for s in qs}
        total = sum(pesos.values()) or 1e-9
        fuera = sum(1 for s in qs if s not in idx.idf) / len(qs)

        # 1ª pasada: cobertura de cada puente y confianza por hub
        candidatos, por_hub = [], {}
        for hub_id, stems, weight, angle, texto in idx.filas:
            com = stems & qs
            if not com:
                continue
            cob = sum(pesos[s] for s in com) / total
            if cob < COMPUERTA:
                continue
            idfs = [pesos[s] for s in com]
            candidatos.append(dict(
                hub=hub_id, stems=stems, weight=weight, angle=angle, cob=cob,
                nm=len(com), npu_len=len(stems),
                idf_medio=(sum(idfs) / len(idfs)) / idx.idf_max,
                idf_total=cob))
            por_hub[hub_id] = max(por_hub.get(hub_id, 0.0), cob)

        if not candidatos:
            continue
        confs = sorted(por_hub.values(), reverse=True)

        # 2ª pasada: rasgos con el margen ya conocido
        for c in candidatos:
            canon = (idx.nodos.get(c["hub"]) or [None])[0]
            if not canon:
                continue
            segundo = next((v for v in confs if v < c["cob"] - 1e-12), 0.0) \
                if len(confs) > 1 else 0.0
            margen = min(1.0, max(0.0, c["cob"] - segundo) / 0.5)
            X.append(npu.rasgos_puente(
                cobertura=c["cob"], idf_medio=c["idf_medio"], idf_total=c["idf_total"],
                n_query=len(qs), n_puente=c["npu_len"], n_matched=c["nm"],
                fuera_vocab=fuera, angulo=c["angle"], margen=margen, peso=c["weight"]))
            y.append(1.0 if canon in oro else 0.0)
            nodos.append(canon)
    return np.asarray(X, float), np.asarray(y, float), nodos


def auc(s, y):
    """AUC por rangos. Numpy puro, como el resto del motor."""
    s, y = np.asarray(s, float), np.asarray(y, float)
    pos, neg = s[y > .5], s[y <= .5]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    todo = np.r_[pos, neg]
    orden = np.argsort(todo, kind="mergesort")
    rangos = np.empty(len(todo), float)
    rangos[orden] = np.arange(1, len(todo) + 1)
    return float((rangos[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def main():
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    idx = _indice_bridges(conn)
    if idx is None:
        print("Sin hubs en la base. Nada que medir.")
        return
    casos = cargar_casos()
    print(f"Casos con oro: {len(casos)}   hubs: {len(idx.nodos)}   puentes: {len(idx.filas)}")

    X, y, nodos = arcos(idx, casos)
    if len(y) == 0:
        print("Ningún arco supera la compuerta. Nada que medir.")
        return
    print(f"Arcos (consulta, puente): {len(y)}   positivos: {int(y.sum())} ({100*y.mean():.1f} %)")

    guard = np.array([es_guardia(n) for n in nodos])
    Xtr, ytr, Xgu, ygu = X[~guard], y[~guard], X[guard], y[guard]
    print(f"Entrenamiento: {len(ytr)} arcos ({int(ytr.sum())} pos)   "
          f"Guardia: {len(ygu)} arcos ({int(ygu.sum())} pos)")

    def linea(nombre, keep):
        tp = int(((keep == 1) & (ygu == 1)).sum())
        fp = int(((keep == 1) & (ygu == 0)).sum())
        pos = int(ygu.sum())
        prec = tp / (tp + fp) if (tp + fp) else float("nan")
        rec = tp / pos if pos else float("nan")
        print(f"  {nombre:<34} dispara {tp+fp:>4}  acierta {tp:>3}  "
              f"precisión {prec*100:>5.1f} %  recall {rec*100:>5.1f} %")

    print("\nGUARDIA — compuerta sola (lo que hay hoy sin neurona):")
    for t in (0.20, 0.30, 0.40, 0.50, 0.55):
        linea(f"cobertura >= {t:.2f}", (Xgu[:, 0] >= t).astype(int))

    if ytr.sum() == 0 or ytr.sum() == len(ytr):
        print("\nUna sola clase en entrenamiento: no se puede entrenar.")
        return

    print("\nAUC en guardia (0.5 = no sabe nada):")
    for nombre, s in (("cobertura IDF", Xgu[:, 0]),
                      ("nº raíces compartidas", Xgu[:, 3]),
                      ("idf medio", Xgu[:, 1]),
                      ("fuera de vocabulario", -Xgu[:, 7]),
                      ("margen entre hubs", Xgu[:, 13]),
                      ("ángulo sinonimo", Xgu[:, 8])):
        print(f"  {nombre:<24} {auc(s, ygu):.3f}")

    p, inf = npu.entrenar(Xtr, ytr, pasos=300, lr=0.5)
    m = np.array([npu.multiplicador_params(p, x) for x in Xgu])
    print(f"\nNeurona entrenada con {inf['n']} arcos, pérdida final {inf['perdida']:.4f}")
    print(f"AUC de la neurona en guardia: {auc(m, ygu):.3f}")
    print("\nGUARDIA — neurona sobre la misma compuerta 0.20:")
    for corte in (0.60, 0.70, 0.80, 0.90, 0.95):
        linea(f"mantiene si mult >= {corte:.2f}", (m >= corte).astype(int))


if __name__ == "__main__":
    main()
