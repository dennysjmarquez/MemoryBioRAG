#!/usr/bin/env python3
"""Controles mecánicos de las dos pasadas E1; no adjudica ni ejecuta BioRAG.

Los archivos son entradas explícitas. Solo se devuelve un resumen agregado y
hashes: nunca se escribe el texto de las respuestas o el paquete en el informe.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

CASE = re.compile(r"case-[0-9a-f]{16}")
ITEM = re.compile(r"item-[0-9a-f]{16}")
LABELS = {
    "rd": "RD", "pi": "PI", "n": "N", "ip": "IP", "ei": "EI",
    "respuesta directa a la pregunta": "RD", "pista indirecta útil": "PI",
    "neutral": "N", "irrelevante o perjudicial": "IP", "evidencia insuficiente": "EI",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_package(path: Path) -> dict[tuple[str, str], str]:
    pairs: dict[tuple[str, str], str] = {}
    case_codes: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        case = json.loads(line)
        code = case["case_code"]
        if not isinstance(code, str) or not CASE.fullmatch(code) or code in case_codes:
            raise ValueError("invalid or duplicate case code in package")
        case_codes.add(code)
        if not isinstance(case["items"], list) or not case["items"]:
            raise ValueError("case without items")
        for item in case["items"]:
            key = (code, item["item_code"])
            if not isinstance(key[1], str) or not ITEM.fullmatch(key[1]) or key in pairs:
                raise ValueError("invalid or duplicate item code in package")
            if not isinstance(item["text"], str):
                raise ValueError("non-string item text")
            pairs[key] = item["text"]
    if not pairs:
        raise ValueError("empty package")
    return pairs


def parse_review(path: Path, pairs: dict[tuple[str, str], str]) -> dict[tuple[str, str], dict]:
    result: dict[tuple[str, str], dict] = {}
    seen_cases: set[str] = set()
    text = path.read_text(encoding="utf-8")
    for section in re.split(r"(?=case-[0-9a-f]{16})", text)[1:]:
        case = CASE.match(section).group()
        if case in seen_cases:
            raise ValueError("duplicate review case")
        seen_cases.add(case)
        for block in re.split(r"(?=item-[0-9a-f]{16})", section)[1:]:
            item = ITEM.match(block).group()
            key = case, item
            if key not in pairs or key in result:
                raise ValueError("extra or duplicate review pair")
            block = block.replace("**", "")
            cat = re.search(r"Categoría(?: provisional)?:\s*([^\n]+)", block)
            evidence = re.search(r"Evidencia(?: textual)?:\s*([^\n]+)", block)
            if not cat or not evidence:
                raise ValueError("missing category or evidence")
            label = LABELS.get(cat.group(1).strip().rstrip(".").lower())
            if label is None:
                raise ValueError("unrecognized review category")
            citations = [a or b for a, b in re.findall(r'«([^»]+)»|"([^"]+)"', evidence.group(1))]
            result[key] = {
                "label": label,
                "quote_status": "missing_quote" if not citations else (
                    "exact" if all(citation in pairs[key] for citation in citations) else "not_exact"
                ),
            }
    if set(result) != set(pairs):
        raise ValueError("review does not cover every package pair exactly once")
    return result


def summarize(package: Path, first: Path, second: Path) -> dict:
    pairs = load_package(package)
    reviews = [parse_review(first, pairs), parse_review(second, pairs)]
    cases = {key[0] for key in pairs}
    agreements = sum(reviews[0][key]["label"] == reviews[1][key]["label"] for key in pairs)
    no_direct = []
    for review in reviews:
        no_direct.append(sum(not any(review[key]["label"] == "RD" for key in pairs if key[0] == case)
                             for case in cases))
    return {
        "input_sha256": {"package": sha256(package), "first_review": sha256(first), "second_review": sha256(second)},
        "cases": len(cases), "presentations": len(pairs),
        "same_categories": agreements, "different_categories": len(pairs) - agreements,
        "cases_without_direct_label": no_direct,
        "quote_status": [dict(sorted(Counter(x["quote_status"] for x in review.values()).items())) for review in reviews],
        "limitations": "Descriptive checks only: no semantic correctness, independence, gold approval or E1 execution.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("first_review", type=Path)
    parser.add_argument("second_review", type=Path)
    args = parser.parse_args()
    print(json.dumps(summarize(args.package, args.first_review, args.second_review), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
