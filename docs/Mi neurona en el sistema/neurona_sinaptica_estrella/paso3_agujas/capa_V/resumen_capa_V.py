"""Tablas de la capa V y evaluación de la regla de parada (PROTOCOLO_PASO3.md §10).

Uso: python resumen_capa_V.py [mecanico|ciego]  → resultados/tablas_{escritor}.md
"""
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(AQUI, "resultados")
IDIOMAS = ("es", "en", "zh", "ja")
LIMPIAS = ("S_tem", "S_tono", "S_sk", "X_min", "X_max", "X_concepto", "X_sk", "X_contenido",
           "B_flag", "B_weight", "B_angulos", "Cat")


def f(x, d=3):
    return "—" if x is None else ("%.*f" % (d, x)).replace(".", ",")


def decisivo(c):
    """Formato nuevo (27-11): {'E→V', 'V→E', 'cruzado'} → decide el cruzado. Formato del mecánico: plano (E→V)."""
    if c and "cruzado" in c:
        return c["cruzado"]
    return c or {}


def celda(c):
    c = decisivo(c)
    if not c.get("medible"):
        return c.get("motivo", "no medible")
    return "%s [%s; %s]%s" % (f(c["dif"]), f(c["IC95"][0]), f(c["IC95"][1]), " ✓" if c.get("cumple") else "")


def main(escritor):
    R = {}
    for i in IDIOMAS:
        p = os.path.join(RES, "v_%s_%s.json" % (escritor, i))
        if os.path.exists(p):
            R[i] = json.load(open(p))
    L = ["# Capa V — escritor `%s`\n" % escritor]
    L.append("| idioma | pares E | pares V | positivos V | nodos V evaluables | MRR piso | bridges rechazados | tipos en V |")
    L.append("|---|---|---|---|---|---|---|---|")
    for i, r in R.items():
        L.append("| %s | %d | %d | %d | %d | %s | %d | %s |" % (
            i, r["n_pares_E"], r["n_pares_V"], r["positivos_V"], r["nodos_V_evaluables"], f(r["MRR_piso"]),
            r["info_construccion"]["bridges_rechazados"], ", ".join("%s %d" % kv for kv in sorted(r["tipos_V"].items()))))
    L.append("\n## C3.5 — diferencia de MRR (piso + aguja − piso), IC95 por documento"
             " (formato nuevo: ajuste cruzado E↔V; formato del mecánico: E→V)\n")
    L.append("| aguja | " + " | ".join(R) + " | ¿cumple en todos? |")
    L.append("|---|" + "---|" * len(R) + "---|")
    cumple_todos = {}
    for n in LIMPIAS + ("R",):
        celdas, ok = [], True
        for i, r in R.items():
            c = decisivo(r["agujas"][n]["C3.5"])
            celdas.append(celda(c))
            ok = ok and bool(c.get("medible") and c.get("cumple"))
        cumple_todos[n] = ok and len(R) == 4
        L.append("| %s | %s | %s |" % (n, " | ".join(celdas), "**sí**" if cumple_todos[n] else "no"))
    for k in ("S+X", "12_limpias", "12_limpias+R"):
        celdas, ok = [], True
        for i, r in R.items():
            c = decisivo(r["combinaciones"][k])
            celdas.append(celda(c))
            ok = ok and bool(c.get("medible") and c.get("cumple"))
        L.append("| *%s* | %s | %s |" % (k, " | ".join(celdas), "**sí**" if ok and len(R) == 4 else "no"))
    L.append("\n## Secundarios de C3.5\n")
    for titulo, ka, kc in (("lista ampliada", "C3.5_ampliada", "combinaciones_ampliada"),
                           ("verdad con puente por entidad rara — CIRCULAR para X, S_sk y B; no admite",
                            "C3.5_con_puente", "combinaciones_con_puente")):
        if not any(ka in r["agujas"]["X_max"] for r in R.values()):
            continue
        L.append("\n**%s**\n" % titulo)
        L.append("| aguja | " + " | ".join(R) + " |")
        L.append("|---|" + "---|" * len(R))
        for n in LIMPIAS + ("R", "S+X", "12_limpias", "12_limpias+R"):
            celdas = [celda(r["agujas"][n].get(ka) if n in r["agujas"] else r.get(kc, {}).get(n)) for r in R.values()]
            L.append("| %s | %s |" % (n, " | ".join(celdas)))
    if any("potencia" in r for r in R.values()):
        L.append("\n**Potencia (nodos E + V del ajuste cruzado · documentos; mínimo 30 · 10)**\n")
        for i, r in R.items():
            L.append("- %s: %s" % (i, "; ".join("%s %d · %d" % (k, v["nodos"], v["documentos"])
                                                for k, v in r.get("potencia", {}).items())))
    L.append("\n## C3.3 — AUC con arista (mismo documento), IC95 · duros · al azar · C3.7 ρ con el grado\n")
    L.append("| aguja | " + " | ".join("%s AUC · duros · azar · ρ" % i for i in R) + " | máx−mín |")
    L.append("|---|" + "---|" * len(R) + "---|")
    for n in LIMPIAS + ("R",):
        celdas, aucs = [], []
        for i, r in R.items():
            a = r["agujas"][n]
            c, d = a["C3.3"], a["C3.3_duros"]
            if not c.get("medible"):
                celdas.append("no medible")
                continue
            aucs.append(c["AUC"])
            celdas.append("%s [%s]%s · %s · %s · %s" % (f(c["AUC"]), f(c["IC95"][0]), " ✓" if c["cumple"] else "",
                                                     f(d.get("AUC")), f(r["azar"]["AUC"].get(n)), f(a["C3.7_rho"], 2)))
        L.append("| %s | %s | %s |" % (n, " | ".join(celdas), f(max(aucs) - min(aucs)) if len(aucs) == len(R) else "—"))
    algun = [n for n in LIMPIAS if cumple_todos.get(n)]
    L.append("\n## Regla de parada\n")
    if len(R) < 4:
        L.append("Faltan idiomas: %s." % ", ".join(i for i in IDIOMAS if i not in R))
    elif algun:
        L.append("Cumplen C3.5 en los 4 idiomas: %s." % ", ".join(algun))
    else:
        L.append("**Ninguna de las 12 limpias cumple C3.5 en los 4 idiomas** con el escritor `%s`." % escritor)
        if escritor == "mecanico":
            L.append("El escritor mecánico es el control: por sí solo no dispara la regla de parada (§10); decide el ciego.")
        else:
            L.append("Se dispara la regla de parada: detenerse y reportar antes de inventar agujas o cambios.")
    out = os.path.join(RES, "tablas_%s.md" % escritor)
    open(out, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "mecanico")
