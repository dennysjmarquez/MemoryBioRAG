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
    L.append("\n## C3.5 — diferencia de MRR (piso + aguja − piso) en Validación, IC95 por documento\n")
    L.append("| aguja | " + " | ".join(R) + " | ¿cumple en todos? |")
    L.append("|---|" + "---|" * len(R) + "---|")
    cumple_todos = {}
    for n in LIMPIAS + ("R",):
        celdas, ok = [], True
        for i, r in R.items():
            c = r["agujas"][n]["C3.5"]
            if not c.get("medible"):
                celdas.append("no medible")
                ok = False
            else:
                celdas.append("%s [%s; %s]%s" % (f(c["dif"]), f(c["IC95"][0]), f(c["IC95"][1]),
                                                 " ✓" if c["cumple"] else ""))
                ok = ok and c["cumple"]
        cumple_todos[n] = ok and len(R) == 4
        L.append("| %s | %s | %s |" % (n, " | ".join(celdas), "**sí**" if cumple_todos[n] else "no"))
    for k in ("S+X", "12_limpias", "12_limpias+R"):
        celdas, ok = [], True
        for i, r in R.items():
            c = r["combinaciones"][k]
            if not c.get("medible"):
                celdas.append("no medible")
                ok = False
            else:
                celdas.append("%s [%s; %s]%s" % (f(c["dif"]), f(c["IC95"][0]), f(c["IC95"][1]),
                                                 " ✓" if c["cumple"] else ""))
                ok = ok and c["cumple"]
        L.append("| *%s* | %s | %s |" % (k, " | ".join(celdas), "**sí**" if ok and len(R) == 4 else "no"))
    L.append("\n## Secundario — C3.5 con lista ampliada (A en V, vecinos en E ∪ V)\n")
    L.append("| aguja | " + " | ".join("%s (%s nodos)" % (i, r.get("ampliada", {}).get("nodos_evaluables", "—"))
                                       for i, r in R.items()) + " |")
    L.append("|---|" + "---|" * len(R))
    for n in LIMPIAS + ("R", "S+X", "12_limpias", "12_limpias+R"):
        celdas = []
        for i, r in R.items():
            c = (r["agujas"][n].get("C3.5_ampliada") if n in r["agujas"]
                 else r.get("combinaciones_ampliada", {}).get(n)) or {}
            celdas.append("no medible" if not c.get("medible") else "%s [%s; %s]%s" % (
                f(c["dif"]), f(c["IC95"][0]), f(c["IC95"][1]), " ✓" if c["cumple"] else ""))
        L.append("| %s | %s |" % (n, " | ".join(celdas)))
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
