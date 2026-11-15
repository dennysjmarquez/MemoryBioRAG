#!/usr/bin/env python3
"""Compara las cuatro QA oficiales B1 con las referencias E2e.

python scripts/comparar_qa_oficial_b1.py --salida docs/e3b1_comparacion_oficial_20261027.json
Un resultado parcial no constituye veredicto: termina con código 2 si falta una
corrida. Verifica clasificación honesta, denominadores, R@5/R@1 por categoría,
MRR y FP. Pytest y las QA multilingües se comprueban aparte.
"""
from __future__ import annotations

import argparse
from decimal import Decimal
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def leer(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def marcas(d: dict) -> list[tuple]:
    fields = ("id", "esperado", "obsoleta", "n_reclamantes", "apartado_r5", "apartado_r1")
    return sorted(tuple(x[k] for k in fields) for x in d["qa_honesta"]["casos_apartados"])


def cantidad(total: int, porcentaje: float) -> int:
    return int((Decimal(total) * Decimal(str(porcentaje)) / Decimal(100)).to_integral_value())


def fallos_honestos(path: Path, metrics: dict) -> set[tuple[str, str]]:
    categorias = set(metrics["qa_honesta"]["categorias"])
    excluidos = {str(c["id"]) for c in metrics["qa_honesta"]["casos_apartados"] if c["apartado_r5"]}
    filas = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        caso = json.loads(line)
        if caso.get("categoria") in categorias and str(caso.get("id")) not in excluidos:
            filas.append((str(caso["id"]), caso["categoria"]))
    if len(filas) != len(set(filas)) or len(filas) != metrics["qa_honesta"]["global_r5"]["fallos"]:
        raise ValueError(f"{path}: fallos incompletos, duplicados o incompatibles con las métricas")
    return set(filas)


def comparar(nombre: str, antes: dict, despues: dict, ruido: bool) -> tuple[dict, list[str]]:
    problemas = []
    if antes["casos_total"] != 921 or despues["casos_total"] != 921 or antes["casos_file"] != despues["casos_file"]:
        problemas.append(f"{nombre}: examen distinto o incompleto")
    h_a, h_b = antes["qa_honesta"], despues["qa_honesta"]
    fijos = ("sinonimo_total", "obsoletas", "ambiguas", "con_las_dos_marcas", "apartados_r5", "apartados_r1")
    if any(h_a[k] != h_b[k] for k in fijos) or marcas(antes) != marcas(despues):
        problemas.append(f"{nombre}: clasificación honesta distinta")
    for lado, run in (("referencia", antes), ("B1", despues)):
        if run["neurona"]["activa"]:
            problemas.append(f"{nombre} {lado}: neurona activa")
        if run["e2b"]["ruido"] != ("zzqx" if ruido else None):
            problemas.append(f"{nombre} {lado}: ruido distinto")
        if (run["e2b"]["censo_tematico"] is not None) != ruido:
            problemas.append(f"{nombre} {lado}: censo distinto")
        g = run["global"]
        if (g["negativos_fp"], g["negativos_total"], g["negativos_contaminados"]) != (0, 40, 0):
            problemas.append(f"{nombre} {lado}: FP no es 0/40 sin contaminados")
    for key, pct, faltas in (("global_r5", "recall_at_5", "fallos"),
                             ("global_r1", "recall_at_1", "no_top1")):
        a, b = h_a[key], h_b[key]
        if a["queries"] != b["queries"]:
            problemas.append(f"{nombre}: denominador {key} distinto")
        if b[pct] < a[pct] or b[faltas] > a[faltas]:
            problemas.append(f"{nombre}: bajó {key}: {a[pct]} → {b[pct]}")
    if h_b["global_r1"]["mrr"] < h_a["global_r1"]["mrr"]:
        problemas.append(f"{nombre}: bajó MRR honesta")
    ca, cb = h_a["categorias"], h_b["categorias"]
    if set(ca) != set(cb):
        problemas.append(f"{nombre}: categorías honestas distintas")
    categorias = {}
    for cat in sorted(set(ca) & set(cb)):
        categorias[cat] = {}
        for tipo, pct in (("r5", "recall_at_5"), ("r1", "recall_at_1")):
            a, b = ca[cat][tipo], cb[cat][tipo]
            if a["total"] != b["total"] or a["apartados"] != b["apartados"]:
                problemas.append(f"{nombre}: denominador {cat} {tipo} distinto")
            ha, hb = cantidad(a["total"], a[pct]), cantidad(b["total"], b[pct])
            if hb < ha:
                problemas.append(f"{nombre}: bajó {cat} {tipo}: {ha}→{hb}/{a['total']}")
            categorias[cat][tipo] = {"total": a["total"], "antes": ha, "despues": hb,
                                     "porcentaje_antes": a[pct], "porcentaje_despues": b[pct]}
    # La tabla clásica también se compara para no ocultar una caída; la honesta
    # sigue siendo la referencia principal acordada por Dennys.
    if set(antes["categorias"]) != set(despues["categorias"]):
        problemas.append(f"{nombre}: categorías clásicas distintas")
    for cat in set(antes["categorias"]) & set(despues["categorias"]):
        a, b = antes["categorias"][cat], despues["categorias"][cat]
        if a["total"] != b["total"]:
            problemas.append(f"{nombre}: denominador clásico {cat} distinto")
        for campo in ("recall_at_5", "recall_at_1", "mrr"):
            if b[campo] < a[campo]:
                problemas.append(f"{nombre}: bajó clásico {cat} {campo}: {a[campo]} → {b[campo]}")
    if despues["global"]["mrr"] < antes["global"]["mrr"]:
        problemas.append(f"{nombre}: bajó MRR clásico global")
    return {
        "r5_antes": h_a["global_r5"], "r5_b1": h_b["global_r5"],
        "r1_antes": h_a["global_r1"], "r1_b1": h_b["global_r1"],
        "fp_antes": [antes["global"]["negativos_fp"], antes["global"]["negativos_total"]],
        "fp_b1": [despues["global"]["negativos_fp"], despues["global"]["negativos_total"]],
        "categorias_honestas": categorias,
    }, problemas


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--salida", type=Path, required=True)
    args = parser.parse_args()
    escenarios, pendientes, problemas = {}, [], []
    for db in ("snapshot", "viva"):
        for modo in ("normal", "ruido"):
            nombre = f"{db}_{modo}"
            ref = DOCS / f"e2e_base_{nombre}_20261027.json"
            actual = DOCS / f"e3b1_{nombre}_20261027.json"
            ref_fallos = DOCS / f"e2e_base_{nombre}_fallos_20261027.jsonl"
            actual_fallos = DOCS / f"e3b1_{nombre}_fallos_20261027.jsonl"
            if not actual.exists() or not actual_fallos.exists():
                pendientes.append(nombre)
                continue
            datos_ref, datos_actual = leer(ref), leer(actual)
            resumen, errores = comparar(nombre, datos_ref, datos_actual, modo == "ruido")
            fallos_antes = fallos_honestos(ref_fallos, datos_ref)
            fallos_despues = fallos_honestos(actual_fallos, datos_actual)
            resumen["fallos_honestos_nuevos"] = sorted(fallos_despues - fallos_antes)
            resumen["fallos_honestos_recuperados"] = sorted(fallos_antes - fallos_despues)
            if resumen["fallos_honestos_nuevos"]:
                errores.append(f"{nombre}: fallos honestos nuevos {resumen['fallos_honestos_nuevos']}")
            escenarios[nombre] = resumen
            problemas.extend(errores)
            a5, b5 = resumen["r5_antes"]["recall_at_5"], resumen["r5_b1"]["recall_at_5"]
            a1, b1 = resumen["r1_antes"]["recall_at_1"], resumen["r1_b1"]["recall_at_1"]
            print(f"{nombre:16} R@5 {a5:.2f}→{b5:.2f}  R@1 {a1:.2f}→{b1:.2f}  FP {resumen['fp_antes']}→{resumen['fp_b1']}")
    completo = len(escenarios) == 4 and not pendientes
    salida = {"comparacion_completa": completo, "metricas_cumplen": completo and not problemas,
              "pendientes": pendientes, "problemas": problemas, "escenarios": escenarios,
              "pytest_y_multilingue_se_validan_aparte": True}
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(json.dumps(salida, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Pendientes:", pendientes)
    for p in problemas:
        print("-", p)
    print("Comparación oficial:", "PENDIENTE" if not completo else ("NO CUMPLE" if problemas else "CUMPLE"))
    return 2 if not completo else int(bool(problemas))


if __name__ == "__main__":
    sys.exit(main())
