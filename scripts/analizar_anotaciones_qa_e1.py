#!/usr/bin/env python3
"""Resume acuerdo entre dos lotes ciegos; no decide aceptación ni aplica umbral."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path


def load_rows(path: Path) -> dict[str, dict]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    by_id = {row.get("candidate_id"): row for row in rows}
    if None in by_id or len(by_id) != len(rows):
        raise ValueError(f"IDs de candidato ausentes/duplicados: {path}")
    allowed_labels = {"respuesta_principal", "pista_util", "neutral", "ruido_tonto"}
    for row in rows:
        rating = row.get("rating_0_3")
        if not isinstance(rating, int) or rating not in range(4):
            raise ValueError(f"Rating faltante o inválido para {row['candidate_id']}")
        if row.get("etiqueta") not in allowed_labels or not row.get("justificacion"):
            raise ValueError(f"Etiqueta/justificación faltante o inválida para {row['candidate_id']}")
    return by_id


def weighted_kappa(a: list[int], b: list[int], quadratic: bool = False) -> float | None:
    if not a:
        return None
    labels = range(4)
    n = len(a)
    observed = Counter(zip(a, b))
    marg_a, marg_b = Counter(a), Counter(b)
    denom = 3.0
    def weight(i, j):
        d = abs(i-j) / denom
        return d*d if quadratic else d
    observed_disagreement = sum(observed[i, j] * weight(i, j) for i in labels for j in labels) / n
    expected_disagreement = sum(marg_a[i] * marg_b[j] * weight(i, j) for i in labels for j in labels) / (n*n)
    if expected_disagreement == 0:
        return 1.0 if observed_disagreement == 0 else None
    return 1.0 - observed_disagreement / expected_disagreement


def nominal_kappa(a: list[str], b: list[str]) -> float | None:
    if not a:
        return None
    n = len(a)
    observed = sum(x == y for x, y in zip(a, b)) / n
    labels = sorted(set(a) | set(b))
    ca, cb = Counter(a), Counter(b)
    expected = sum(ca[x] * cb[x] for x in labels) / (n*n)
    if expected == 1:
        return 1.0 if observed == 1 else None
    return (observed - expected) / (1 - expected)


def compare(first: Path, second: Path) -> dict:
    a, b = load_rows(first), load_rows(second)
    if set(a) != set(b):
        raise ValueError("Los dos revisores deben entregar exactamente los mismos candidate_id")
    ids = sorted(a)
    ratings_a = [a[i]["rating_0_3"] for i in ids]
    ratings_b = [b[i]["rating_0_3"] for i in ids]
    labels_a = [str(a[i]["etiqueta"]) for i in ids]
    labels_b = [str(b[i]["etiqueta"]) for i in ids]
    return {
        "n_candidatos_pareados": len(ids),
        "acuerdo_exacto_rating": sum(x == y for x, y in zip(ratings_a, ratings_b)) / len(ids) if ids else None,
        "kappa_ponderado_lineal": weighted_kappa(ratings_a, ratings_b),
        "kappa_ponderado_cuadratico": weighted_kappa(ratings_a, ratings_b, quadratic=True),
        "kappa_nominal_etiqueta": nominal_kappa(labels_a, labels_b),
        "diferencias_rating": [{"candidate_id": i, "revisor_1": a[i]["rating_0_3"],
                                "revisor_2": b[i]["rating_0_3"]}
                               for i in ids if a[i]["rating_0_3"] != b[i]["rating_0_3"]],
        "estado": "descriptivo; no se aplica umbral de aceptación",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("revisor_1", type=Path)
    parser.add_argument("revisor_2", type=Path)
    parser.add_argument("--salida", type=Path, required=True)
    args = parser.parse_args()
    result = compare(args.revisor_1, args.revisor_2)
    args.salida.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "diferencias_rating"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
