#!/usr/bin/env python3
"""Compara las cuatro QA oficiales B2 contra B1, también por categoría.

No anuncia veredicto mientras falte alguna corrida. Los errores del gate clásico
con ruido se contrastan con B1: no equivalen por sí solos a una regresión nueva.
La suite pytest y la QA multilingüe se verifican por separado.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.comparar_qa_oficial_b1 import comparar, fallos_honestos, leer

DOCS = ROOT / "docs"


def tabla_categoria(resultados: dict) -> str:
    lines = ["# E3B2 — QA oficial por categoría", "", "Cada celda expresa **B1 → B2**. R@5 y R@1 son honestas.",
             "Snapshot y copia viva aparecen lado a lado.", ""]
    for modo, titulo in (("normal", "Sin ruido"), ("ruido", "Con ruido `zzqx`")):
        s, v = resultados[f"snapshot_{modo}"], resultados[f"viva_{modo}"]
        lines += [f"## {titulo}", "", "| Categoría | Snapshot R@5 | Snapshot R@1 | Viva R@5 | Viva R@1 |",
                  "|---|---:|---:|---:|---:|"]
        for cat in sorted(set(s["categorias_honestas"]) | set(v["categorias_honestas"])):
            celdas = []
            for escenario in (s, v):
                for campo in ("r5", "r1"):
                    d = escenario["categorias_honestas"][cat][campo]
                    celdas.append(f"{d['antes']}/{d['total']} → {d['despues']}/{d['total']}")
            lines.append("| " + cat + " | " + " | ".join(celdas) + " |")
        cells = []
        for escenario in (s, v):
            for tipo, aciertos in (("r5", "fallos"), ("r1", "no_top1")):
                a, b = escenario[f"{tipo}_antes"], escenario[f"{tipo}_b2"]
                cells.append(f"{a['queries'] - a[aciertos]}/{a['queries']} → {b['queries'] - b[aciertos]}/{b['queries']}")
        lines += ["| **Global** | " + " | ".join(cells) + " |", "",
                  "| Negativos (FP) | Snapshot B1 → B2 | Viva B1 → B2 |", "|---|---:|---:|"]
        sfp, vfp = s["fp_antes"], v["fp_antes"]
        sbfp, vbfp = s["fp_b2"], v["fp_b2"]
        lines += [f"| negativo | {sfp[0]}/{sfp[1]} → {sbfp[0]}/{sbfp[1]} | {vfp[0]}/{vfp[1]} → {vbfp[0]}/{vbfp[1]} |", ""]
        for db, dato in (("Snapshot", s), ("Viva", v)):
            lines.append(f"- {db}: {len(dato['fallos_honestos_nuevos'])} fallos R@5 nuevos; {len(dato['fallos_honestos_recuperados'])} recuperados.")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--salida", type=Path, required=True)
    parser.add_argument("--tabla", type=Path)
    args = parser.parse_args()
    escenarios, pendientes, problemas = {}, [], []
    for db in ("snapshot", "viva"):
        for modo in ("normal", "ruido"):
            nombre = f"{db}_{modo}"
            ref, actual = (DOCS / f"e3b{n}_{nombre}_20261027.json" for n in (1, 2))
            ref_f, actual_f = (DOCS / f"e3b{n}_{nombre}_fallos_20261027.jsonl" for n in (1, 2))
            if not actual.exists() or not actual_f.exists():
                pendientes.append(nombre)
                continue
            a, b = leer(ref), leer(actual)
            resumen, errores = comparar(nombre, a, b, modo == "ruido")
            errores = [x.replace(" B1:", " B2:") for x in errores]
            if a["db_src"] != b["db_src"]:
                errores.append(f"{nombre}: origen distinto")
            if a["e2b"]["censo_tematico"] != b["e2b"]["censo_tematico"]:
                errores.append(f"{nombre}: censo temático distinto")
            fallos_a, fallos_b = fallos_honestos(ref_f, a), fallos_honestos(actual_f, b)
            resumen["fallos_honestos_nuevos"] = sorted(fallos_b - fallos_a)
            resumen["fallos_honestos_recuperados"] = sorted(fallos_a - fallos_b)
            if resumen["fallos_honestos_nuevos"]:
                errores.append(f"{nombre}: fallos honestos nuevos {resumen['fallos_honestos_nuevos']}")
            for campo in ("r5", "r1", "fp"):
                resumen[f"{campo}_b2"] = resumen.pop(f"{campo}_b1")
            escenarios[nombre] = resumen
            problemas.extend(errores)
            print(f"{nombre:16} R@5 {resumen['r5_antes']['recall_at_5']:.2f}→{resumen['r5_b2']['recall_at_5']:.2f}  "
                  f"R@1 {resumen['r1_antes']['recall_at_1']:.2f}→{resumen['r1_b2']['recall_at_1']:.2f}  "
                  f"FP {resumen['fp_antes']}→{resumen['fp_b2']}")
    completo = len(escenarios) == 4 and not pendientes
    salida = {"comparacion_completa": completo, "metricas_cumplen": completo and not problemas,
              "pendientes": pendientes, "problemas": problemas, "escenarios": escenarios,
              "pytest_y_multilingue_se_validan_aparte": True}
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(json.dumps(salida, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if completo and args.tabla:
        args.tabla.parent.mkdir(parents=True, exist_ok=True)
        args.tabla.write_text(tabla_categoria(escenarios), encoding="utf-8")
    print("Pendientes:", pendientes)
    for p in problemas:
        print("-", p)
    print("Comparación oficial:", "PENDIENTE" if not completo else ("NO CUMPLE" if problemas else "CUMPLE"))
    return 2 if not completo else int(bool(problemas))


if __name__ == "__main__":
    sys.exit(main())
