#!/usr/bin/env python3
"""Comprueba igualdad B2/B3, además de la ausencia de regresión.

Dennys autorizó publicar B3 únicamente si las cuatro QA coinciden por
categoría, R@1 y FP 0/40. Una mejora tampoco se considera igualdad. El
comparador de no regresión y la verificación de fuentes siguen siendo
independientes y deben pasar por separado.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.comparar_qa_oficial_b3 import misma_fuente

DOCS = ROOT / "docs"
ESCENARIOS = ("snapshot_normal", "viva_normal", "snapshot_ruido", "viva_ruido")


def comprobar_escenario(a: dict, b: dict) -> list[str]:
    """Diferencias de métricas relevantes; no modifica ninguno de los datos."""
    problemas = []
    try:
        if not misma_fuente(a["db_src"], b["db_src"]):
            problemas.append("fuente diferente")
        if (a["casos_file"], a["casos_total"]) != (b["casos_file"], b["casos_total"]):
            problemas.append("corpus diferente")
        if a["categorias"] != b["categorias"]:
            problemas.append("categorías originales diferentes")
        for campo in ("categorias", "global_r5", "global_r1"):
            if a["qa_honesta"][campo] != b["qa_honesta"][campo]:
                problemas.append(f"QA honesta {campo} diferente")
        for campo in ("queries", "recall_at_5", "recall_at_1", "mrr"):
            if a["global"][campo] != b["global"][campo]:
                problemas.append(f"global {campo} diferente")
        for etiqueta, valor in (("B2", a), ("B3", b)):
            if (valor["global"]["negativos_fp"], valor["global"]["negativos_total"]) != (0, 40):
                problemas.append(f"{etiqueta}: FP no es 0/40")
        if a["e2b"]["censo_tematico"] != b["e2b"]["censo_tematico"]:
            problemas.append("censo temático diferente")
    except (KeyError, TypeError, ValueError) as exc:
        problemas.append(f"datos incompletos o inválidos: {exc}")
    return problemas


def evaluar(docs: Path = DOCS) -> dict:
    escenarios = {}
    pendientes = []
    for nombre in ESCENARIOS:
        ref = docs / f"e3b2_{nombre}_20261027.json"
        actual = docs / f"e3b3_{nombre}_20261028.json"
        if not ref.is_file() or not actual.is_file():
            pendientes.append(nombre)
            continue
        try:
            a, b = (json.loads(p.read_text(encoding="utf-8")) for p in (ref, actual))
            diferencias = comprobar_escenario(a, b)
            escenarios[nombre] = {"iguales": not diferencias, "diferencias": diferencias}
        except (OSError, json.JSONDecodeError) as exc:
            escenarios[nombre] = {"iguales": False, "diferencias": [f"lectura inválida: {exc}"]}
    completo = len(escenarios) == 4 and not pendientes
    return {
        "condicion": "iguales por categoría, R@1 y FP 0/40; también se verifica R@5, MRR y censo",
        "comparacion_completa": completo,
        "iguales": completo and all(e["iguales"] for e in escenarios.values()),
        "pendientes": pendientes,
        "escenarios": escenarios,
        "fuentes_y_no_regresion_se_verifican_independientemente": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--salida", type=Path, required=True)
    args = parser.parse_args()
    resultado = evaluar()
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for nombre, r in resultado["escenarios"].items():
        print(nombre, "IGUAL" if r["iguales"] else "; ".join(r["diferencias"]))
    print("Pendientes:", resultado["pendientes"])
    print("Igualdad de las cuatro:", resultado["iguales"])
    return 2 if not resultado["comparacion_completa"] else int(not resultado["iguales"])


if __name__ == "__main__":
    raise SystemExit(main())
