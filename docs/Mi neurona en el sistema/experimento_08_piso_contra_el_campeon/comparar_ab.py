#!/usr/bin/env python3
"""Experimento 08 — compara la corrida A (antes) con la B (piso contra el campeón).

1. Determinismo: hasta el primer ciclo en que la regla actúa en B (veto_campeon), A y B
   tienen que ser idénticos ciclo a ciclo (mismo examen, mismas fases, mismas guardias).
   Si no lo son, la comparación no vale (habría ruido además del cambio).
2. Práctica: ascensos, retiros, vetos y guardia final.
3. QA oficial (motor directo) y camino MCP por categoría, A vs B y contra el piso.
"""
import json
import os
import re
import sys

R = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resultados")
PISO = {  # tabla oficial del usuario, fórmula a mano (R@1)
    "cruce_idioma": 62.50, "dormido": 100.0, "literal": 99.59, "por_tema": 63.08,
    "pregunta_natural": 93.85, "sinonimo": 56.36, "typo": 87.69, "variante_gramatical": 87.69,
}
CLAVES = ("estudio", "guardia", "fase", "margen", "guardia_mano", "guardia_campeon", "nuevas", "campeon")


def curva(et):
    with open(os.path.join(R, f"curva_{et}.jsonl"), encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def qa(et):
    out = {}
    for ln in open(os.path.join(R, f"qa_oficial_{et}.txt"), encoding="utf-8"):
        p = [x.strip() for x in ln.split("|")]
        if len(p) >= 5 and "%" in p[2]:
            out["GLOBAL" if p[0].startswith("GLOBAL") else p[0]] = (
                float(p[2].rstrip("%")), float(p[3].rstrip("%")), float(p[4]))
    return out


def mcp(et):
    d = json.load(open(os.path.join(R, f"mcp_{et}.json"), encoding="utf-8"))
    por = {}
    for c in d["casos"]:
        r = c["puesto"]
        t = por.setdefault(c["cat"], [0, 0, 0.0, 0])
        t[0] += r == 1
        t[1] += bool(r) and r <= 5
        t[2] += 1.0 / r if r and r <= 5 else 0.0
        t[3] += 1
    tot = [sum(v[i] for v in por.values()) for i in range(4)]
    por["GLOBAL"] = tot
    return {k: (100 * v[1] / v[3], 100 * v[0] / v[3], v[2] / v[3], v[0], v[3]) for k, v in por.items()}, d["casos"]


def main():
    A, B = curva("A"), curva("B")
    veto = [x["ciclo"] for x in B if x.get("veto_campeon")]
    primero = veto[0] if veto else len(B) + 1
    distintos = [a["ciclo"] for a, b in zip(A, B) if a["ciclo"] < primero
                 and any(a.get(k) != b.get(k) for k in CLAVES)]
    print("1. DETERMINISMO")
    print(f"   la regla actúa por primera vez en B en el ciclo {primero if veto else '— (nunca)'}")
    print(f"   ciclos anteriores con alguna diferencia A≠B: {len(distintos)}"
          + (f"  (primeros: {distintos[:5]})" if distintos else "  -> idénticos: la comparación es limpia"))

    print("\n2. PRÁCTICA (500 ciclos, presupuesto sin corte)")
    for et, c in (("A", A), ("B", B)):
        asc = [x["ciclo"] for x in c if x.get("fase") == "ascenso"]
        ret = [x["ciclo"] for x in c if x.get("retiro")]
        vet = [x["ciclo"] for x in c if x.get("veto_campeon")]
        u = c[-1]
        print(f"   {et}: ascensos {len(asc)} {asc} · retiros {len(ret)} · vetos {len(vet)} {vet[:12]}"
              f"{'…' if len(vet) > 12 else ''} · guardia mano {u.get('guardia_mano')} → campeón "
              f"{u.get('guardia_campeon')} · margen {u.get('margen')}")

    qa_a, qa_b = qa("A"), qa("B")
    print("\n3. QA OFICIAL (motor directo, 875) — R@5 / R@1 / MRR")
    print(f"   {'categoría':22s} {'piso R@1':>8s} | {'A':>22s} | {'B':>22s} | ΔR@1 B−A")
    for k in sorted(qa_a, key=lambda x: (x == "GLOBAL", x)):
        a, b = qa_a[k], qa_b.get(k, (0, 0, 0))
        print(f"   {k:22s} {PISO.get(k, float('nan')):8.2f} | {a[0]:6.2f} {a[1]:6.2f} {a[2]:.3f}"
              f"    | {b[0]:6.2f} {b[1]:6.2f} {b[2]:.3f}    | {b[1] - a[1]:+.2f}"
              + ("   <-- BAJO EL PISO" if k in PISO and b[1] < PISO[k] - 1e-9 else ""))

    (ma, ca), (mb, cb) = mcp("A"), mcp("B")
    print("\n4. CAMINO DEL AGENTE (recordar por MCP, 875) — R@5 / R@1 / MRR")
    for k in sorted(ma, key=lambda x: (x == "GLOBAL", x)):
        a, b = ma[k], mb[k]
        print(f"   {k:22s} | A {a[0]:6.2f} {a[1]:6.2f} {a[2]:.3f} ({a[3]}/{a[4]})"
              f" | B {b[0]:6.2f} {b[1]:6.2f} {b[2]:.3f} ({b[3]}/{b[4]}) | ΔR@1 {b[1] - a[1]:+.2f}")
    pa = {c["id"]: c["puesto"] for c in ca}
    gana = sum(1 for c in cb if c["puesto"] == 1 and pa.get(c["id"]) != 1)
    pierde = sum(1 for c in cb if c["puesto"] != 1 and pa.get(c["id"]) == 1)
    print(f"   #1 de B frente a A: +{gana} / −{pierde}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
