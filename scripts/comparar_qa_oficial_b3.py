#!/usr/bin/env python3
"""Compara las cuatro QA oficiales B3 contra B2, por categoría y fallos.

Un resultado parcial no es veredicto. El gate clásico rojo con ruido no es,
por sí solo, una regresión nueva: se compara con la misma referencia B2. La
suite pytest y las pruebas multilingües se verifican por separado.
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


def misma_fuente(a: str, b: str, raiz: Path = ROOT) -> bool:
    """Compara rutas absolutas y relativas ancladas a la raíz del proyecto.

    La identidad de la ruta no sustituye la comprobación independiente del SHA
    de la fuente. En B2 el snapshot se registró con ruta absoluta y en B3 con
    ruta relativa, aunque ambos leyeron exactamente el mismo archivo.
    """
    def resolver(valor: str) -> Path:
        path = Path(valor)
        return (path if path.is_absolute() else raiz / path).resolve()
    return resolver(a) == resolver(b)


def tabla_categoria(escenarios: dict) -> str:
    lines = ["# E3B3 — QA oficial por categoría", "", "Cada celda expresa **B2 → B3**. R@5 y R@1 son honestas.",
             "Snapshot y copia viva aparecen lado a lado.", ""]
    for modo, titulo in (("normal", "Sin ruido"), ("ruido", "Con ruido `zzqx`")):
        s, v = escenarios[f"snapshot_{modo}"], escenarios[f"viva_{modo}"]
        lines += [f"## {titulo}", "", "| Categoría | Snapshot R@5 | Snapshot R@1 | Viva R@5 | Viva R@1 |",
                  "|---|---:|---:|---:|---:|"]
        for cat in sorted(set(s["categorias_honestas"]) | set(v["categorias_honestas"])):
            celdas = []
            for escenario in (s, v):
                categoria = escenario["categorias_honestas"].get(cat)
                for campo in ("r5", "r1"):
                    if categoria is None:
                        celdas.append("—")
                    else:
                        d = categoria[campo]
                        celdas.append(f"{d['antes']}/{d['total']} → {d['despues']}/{d['total']}")
            lines.append("| " + cat + " | " + " | ".join(celdas) + " |")
        celdas = []
        for escenario in (s, v):
            for tipo, faltas in (("r5", "fallos"), ("r1", "no_top1")):
                a, b = escenario[f"{tipo}_antes"], escenario[f"{tipo}_b3"]
                celdas.append(f"{a['queries'] - a[faltas]}/{a['queries']} → {b['queries'] - b[faltas]}/{b['queries']}")
        lines += ["| **Global** | " + " | ".join(celdas) + " |", "",
                  "| Negativos (FP) | Snapshot B2 → B3 | Viva B2 → B3 |", "|---|---:|---:|"]
        sa, sb, va, vb = s["fp_antes"], s["fp_b3"], v["fp_antes"], v["fp_b3"]
        lines += [f"| negativo | {sa[0]}/{sa[1]} → {sb[0]}/{sb[1]} | {va[0]}/{va[1]} → {vb[0]}/{vb[1]} |", ""]
        for nombre, dato in (("Snapshot", s), ("Viva", v)):
            lines.append(f"- {nombre}: {len(dato['fallos_honestos_nuevos'])} fallos R@5 nuevos; "
                         f"{len(dato['fallos_honestos_recuperados'])} recuperados.")
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
            ref = DOCS / f"e3b2_{nombre}_20261027.json"
            ref_f = DOCS / f"e3b2_{nombre}_fallos_20261027.jsonl"
            actual = DOCS / f"e3b3_{nombre}_20261028.json"
            actual_f = DOCS / f"e3b3_{nombre}_fallos_20261028.jsonl"
            if not actual.exists() or not actual_f.exists():
                pendientes.append(nombre)
                continue
            a, b = leer(ref), leer(actual)
            resumen, errores = comparar(nombre, a, b, modo == "ruido")
            errores = [x.replace(" B1:", " B3:") for x in errores]
            if not misma_fuente(a["db_src"], b["db_src"]):
                errores.append(f"{nombre}: origen distinto")
            if a["e2b"]["censo_tematico"] != b["e2b"]["censo_tematico"]:
                errores.append(f"{nombre}: censo temático distinto")
            fallos_a, fallos_b = fallos_honestos(ref_f, a), fallos_honestos(actual_f, b)
            resumen["fallos_honestos_nuevos"] = sorted(fallos_b - fallos_a)
            resumen["fallos_honestos_recuperados"] = sorted(fallos_a - fallos_b)
            if resumen["fallos_honestos_nuevos"]:
                errores.append(f"{nombre}: fallos honestos nuevos {resumen['fallos_honestos_nuevos']}")
            for campo in ("r5", "r1", "fp"):
                resumen[f"{campo}_b3"] = resumen.pop(f"{campo}_b1")
            escenarios[nombre] = resumen
            problemas.extend(errores)
            print(f"{nombre:16} R@5 {resumen['r5_antes']['recall_at_5']:.2f}→{resumen['r5_b3']['recall_at_5']:.2f}  "
                  f"R@1 {resumen['r1_antes']['recall_at_1']:.2f}→{resumen['r1_b3']['recall_at_1']:.2f}  "
                  f"FP {resumen['fp_antes']}→{resumen['fp_b3']}")
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
