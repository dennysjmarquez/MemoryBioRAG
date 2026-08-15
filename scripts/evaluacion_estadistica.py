#!/usr/bin/env python3
"""evaluacion_estadistica.py — Incertidumbre y significancia para el benchmark de BioRAG.

Propuesto en docs/REVISION_MATEMATICA.md. El benchmark actual reporta puntos
porcentuales sin intervalos de confianza ni tests pareados, sobre categorías con
n = 8 a 487. Este script añade lo que falta:

  - Intervalo de Wilson por categoría (correcto con n pequeño y p cerca de 1).
  - Macro-promedio por categoría vs micro-promedio global (el GLOBAL actual está
    dominado por los 487 casos `literal`, que son el 55% del set).
  - Test de McNemar exacto pareado para comparar dos versiones sobre los mismos
    casos (más potente y correcto que comparar dos proporciones independientes).
  - Bootstrap de la diferencia de MRR.
  - Corrección de Benjamini-Hochberg (FDR) para la tabla de EXPERIMENTS.md,
    donde ~10 hipótesis se evaluaron sobre el mismo test set.

Uso:
    python3 scripts/evaluacion_estadistica.py --demo
    python3 scripts/evaluacion_estadistica.py --casos scripts/casos_qa.jsonl
    python3 scripts/evaluacion_estadistica.py --a run_a.jsonl --b run_b.jsonl

Formato esperado de --a / --b (una línea JSON por caso):
    {"id": "0001", "categoria": "literal", "acierto_5": 1, "acierto_1": 1, "rr": 1.0}
"""
from __future__ import annotations

import argparse
import json
import math
import random
from collections import Counter, defaultdict
from typing import Dict, List, Sequence, Tuple

# =============================================================================
# Intervalos de confianza
# =============================================================================


def wilson(k: int, n: int, z: float = 1.96) -> Tuple[float, float]:
    """Intervalo de Wilson al 95% para una proporción, en porcentaje.

    Preferible a Wald (p +- z*sqrt(p(1-p)/n)) porque no se sale de [0,1] ni
    colapsa a cero cuando p ~ 1, que es justo el régimen de este benchmark.
    """
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    den = 1.0 + z * z / n
    centro = (p + z * z / (2 * n)) / den
    margen = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (round(100 * max(0.0, centro - margen), 2),
            round(100 * min(1.0, centro + margen), 2))


# =============================================================================
# Tests pareados
# =============================================================================


def mcnemar_exacto(b: int, c: int) -> float:
    """Test de McNemar exacto (binomial bilateral) sobre pares discordantes.

    b = casos que A acierta y B falla; c = casos que B acierta y A falla.
    Los casos donde ambos coinciden no aportan información.
    """
    n = b + c
    if n == 0:
        return 1.0
    menor = min(b, c)
    cola = sum(math.comb(n, k) for k in range(0, menor + 1)) / (2 ** n)
    return min(1.0, 2 * cola)


def comparar_pareado(res_a: Dict[str, int], res_b: Dict[str, int]) -> dict:
    """Compara dos corridas caso a caso. res_* : {id_caso: 0/1}."""
    ids = sorted(set(res_a) & set(res_b))
    b = sum(1 for i in ids if res_a[i] == 1 and res_b[i] == 0)
    c = sum(1 for i in ids if res_a[i] == 0 and res_b[i] == 1)
    ka, kb = sum(res_a[i] for i in ids), sum(res_b[i] for i in ids)
    n = len(ids)
    return {
        "n_pares": n,
        "A": f"{100*ka/n:.2f}%" if n else "-",
        "B": f"{100*kb/n:.2f}%" if n else "-",
        "delta_pp": round(100 * (kb - ka) / n, 2) if n else 0.0,
        "discordantes_A_gana": b,
        "discordantes_B_gana": c,
        "p_mcnemar": round(mcnemar_exacto(b, c), 5),
        "significativo_005": mcnemar_exacto(b, c) < 0.05,
    }


def bootstrap_delta_mrr(rr_a: Sequence[float], rr_b: Sequence[float],
                        n_boot: int = 10000, seed: int = 20260804) -> dict:
    """IC bootstrap percentil de la diferencia pareada de MRR (B - A)."""
    if len(rr_a) != len(rr_b) or not rr_a:
        raise ValueError("rr_a y rr_b deben ser pareados y no vacíos")
    rng = random.Random(seed)
    n = len(rr_a)
    diffs = [rr_b[i] - rr_a[i] for i in range(n)]
    obs = sum(diffs) / n
    muestras = []
    for _ in range(n_boot):
        s = sum(diffs[rng.randrange(n)] for _ in range(n)) / n
        muestras.append(s)
    muestras.sort()
    lo = muestras[int(0.025 * n_boot)]
    hi = muestras[int(0.975 * n_boot) - 1]
    return {"delta_mrr": round(obs, 4),
            "ic95": (round(lo, 4), round(hi, 4)),
            "cruza_cero": lo <= 0 <= hi}


# =============================================================================
# Multiplicidad
# =============================================================================


def benjamini_hochberg(p_values: Sequence[float], q: float = 0.05) -> List[bool]:
    """Control de FDR. Devuelve una lista de bool (rechazar H0) en el orden dado.

    Con ~10 experimentos sobre el mismo test set (EXPERIMENTS.md), la
    probabilidad de al menos un falso positivo sin corrección es ~40%.
    """
    m = len(p_values)
    orden = sorted(range(m), key=lambda i: p_values[i])
    rechazos = [False] * m
    k_max = -1
    for rank, i in enumerate(orden, start=1):
        if p_values[i] <= q * rank / m:
            k_max = rank
    for rank, i in enumerate(orden, start=1):
        if rank <= k_max:
            rechazos[i] = True
    return rechazos


# =============================================================================
# Agregación de métricas
# =============================================================================


def resumen_por_categoria(registros: List[dict], campo: str = "acierto_5") -> dict:
    """Wilson por categoría + macro vs micro."""
    por_cat: Dict[str, List[int]] = defaultdict(list)
    for r in registros:
        por_cat[r["categoria"]].append(int(r.get(campo, 0)))

    filas = []
    for cat in sorted(por_cat):
        vals = por_cat[cat]
        k, n = sum(vals), len(vals)
        lo, hi = wilson(k, n)
        filas.append({"categoria": cat, "n": n, "pct": round(100 * k / n, 2),
                      "ic95": (lo, hi), "ancho_ic": round(hi - lo, 2)})

    total_k = sum(sum(v) for v in por_cat.values())
    total_n = sum(len(v) for v in por_cat.values())
    micro = 100 * total_k / total_n if total_n else 0.0
    macro = sum(f["pct"] for f in filas) / len(filas) if filas else 0.0
    return {"filas": filas, "micro": round(micro, 2), "macro": round(macro, 2),
            "n_total": total_n}


def imprimir_resumen(res: dict, titulo: str) -> None:
    print(f"\n{titulo}")
    print(f"{'categoria':<22} {'n':>5} {'%':>8} {'IC95 Wilson':>20} {'ancho':>7}")
    print("-" * 66)
    for f in res["filas"]:
        ic = f"[{f['ic95'][0]:.1f}, {f['ic95'][1]:.1f}]"
        aviso = "  <-- n muy chico" if f["n"] < 30 else ""
        print(f"{f['categoria']:<22} {f['n']:>5} {f['pct']:>7.2f}% {ic:>20} {f['ancho_ic']:>6.1f}{aviso}")
    print("-" * 66)
    print(f"{'MICRO (global)':<22} {res['n_total']:>5} {res['micro']:>7.2f}%")
    print(f"{'MACRO (por categoría)':<22} {'':>5} {res['macro']:>7.2f}%   <-- métrica honesta")


# =============================================================================
# Demo con los números publicados en el README
# =============================================================================


def demo() -> None:
    print("=" * 66)
    print("  ANÁLISIS ESTADÍSTICO DE LOS NÚMEROS PUBLICADOS EN EL README v28.0")
    print("=" * 66)

    # (categoria, n, R@5 reportado en producción)
    datos = [
        ("dormido", 65, 100.00), ("literal", 487, 100.00),
        ("pregunta_natural", 65, 100.00), ("variante_gramatical", 65, 98.46),
        ("typo", 65, 96.92), ("cruce_idioma", 8, 87.50),
        ("sinonimo", 61, 83.61), ("por_tema", 65, 86.15),
    ]
    registros = []
    for cat, n, pct in datos:
        k = round(n * pct / 100)
        registros.extend([{"categoria": cat, "acierto_5": 1}] * k)
        registros.extend([{"categoria": cat, "acierto_5": 0}] * (n - k))

    imprimir_resumen(resumen_por_categoria(registros), "R@5 con intervalos de confianza")

    print("\nLectura:")
    print("  - `literal` es el 55% del set (487/881) y da ~100%: infla el MICRO.")
    print("  - `cruce_idioma` con n=8 tiene un IC de 45 puntos de ancho: no es una métrica.")
    print("  - El salto real del proyecto se juega en `sinonimo` y `por_tema`, ambos con")
    print("    IC de ~18 puntos: hacen falta más casos para detectar mejoras de <10pp.")

    print("\n" + "=" * 66)
    print("  TESTS PAREADOS DE LAS MEJORAS REPORTADAS")
    print("=" * 66)
    comparaciones = [
        ("FP 25% -> 7.5% (40 negativos, 7 discordantes)", mcnemar_exacto(7, 0)),
        ("R@1 global +0.57pp (881 casos, ~5 discordantes)", mcnemar_exacto(5, 0)),
        ("sinonimo 2/14 -> 8/14 (pool 35, 6 discordantes)", mcnemar_exacto(6, 0)),
        ("por_tema 67.69% -> 81.54% (65 casos, 9 discordantes)", mcnemar_exacto(9, 0)),
    ]
    ps = [p for _, p in comparaciones]
    rechazos = benjamini_hochberg(ps, q=0.05)
    print(f"{'comparación':<52} {'p':>9} {'sig.':>6} {'BH':>5}")
    print("-" * 76)
    for (nombre, p), bh in zip(comparaciones, rechazos):
        print(f"{nombre:<52} {p:>9.4f} {'sí' if p < 0.05 else 'NO':>6} {'sí' if bh else 'NO':>5}")
    print("-" * 76)
    print("Nota: los p asumen el escenario MÁS favorable (todos los discordantes a favor).")
    print("      El +0.57pp de R@1 no alcanza significancia ni en el mejor caso.")

    print("\n" + "=" * 66)
    print("  POTENCIA: ¿cuántos casos hacen falta?")
    print("=" * 66)
    for delta in (0.02, 0.05, 0.10):
        # n aproximado para McNemar con tasa de discordancia ~2*delta, potencia 0.8
        pd = 2 * delta
        n = math.ceil(((1.96 * math.sqrt(pd) + 0.84 * math.sqrt(pd - delta ** 2)) ** 2) / (delta ** 2))
        print(f"  detectar +{delta*100:>4.0f}pp con potencia 80%  ->  ~{n:>5} casos pareados")
    print("  Con 65 casos por categoría sólo detectas mejoras de ~15pp o más.")


def cargar(path: str) -> List[dict]:
    with open(path, encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip()]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--demo", action="store_true", help="analiza los números del README")
    ap.add_argument("--casos", help="jsonl de casos QA (sólo reporta el balance del set)")
    ap.add_argument("--a", help="jsonl de resultados de la versión A")
    ap.add_argument("--b", help="jsonl de resultados de la versión B")
    args = ap.parse_args()

    if args.casos:
        casos = cargar(args.casos)
        c = Counter(x["categoria"] for x in casos)
        total = sum(c.values())
        print(f"\nBalance del set ({total} casos):")
        for cat, n in c.most_common():
            print(f"  {cat:<22} {n:>5}  ({100*n/total:>5.1f}%)")
        dominante = c.most_common(1)[0]
        print(f"\n  La categoría `{dominante[0]}` es el {100*dominante[1]/total:.0f}% del set.")
        print("  Reporta MACRO por categoría además del GLOBAL.")

    if args.a and args.b:
        ra, rb = cargar(args.a), cargar(args.b)
        for campo in ("acierto_5", "acierto_1"):
            da = {x["id"]: int(x.get(campo, 0)) for x in ra}
            db = {x["id"]: int(x.get(campo, 0)) for x in rb}
            print(f"\nMcNemar pareado sobre {campo}:")
            for k, v in comparar_pareado(da, db).items():
                print(f"  {k:<24} {v}")
        if all("rr" in x for x in ra) and all("rr" in x for x in rb):
            ids = sorted({x["id"] for x in ra} & {x["id"] for x in rb})
            ma = {x["id"]: float(x["rr"]) for x in ra}
            mb = {x["id"]: float(x["rr"]) for x in rb}
            print("\nBootstrap de delta MRR:")
            for k, v in bootstrap_delta_mrr([ma[i] for i in ids], [mb[i] for i in ids]).items():
                print(f"  {k:<24} {v}")
        imprimir_resumen(resumen_por_categoria(rb), "R@5 de la versión B")

    if not (args.demo or args.casos or (args.a and args.b)):
        demo()
    elif args.demo:
        demo()


if __name__ == "__main__":
    main()
