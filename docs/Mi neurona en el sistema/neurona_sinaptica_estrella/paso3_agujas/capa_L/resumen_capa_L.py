"""Resumen de la capa L del Paso 3: aplica los criterios fijados antes (PROTOCOLO_PASO3.md §5) a resultados/config_*.json.

C3.1 invariancia (D∪I0 y D∪I1; locales y K/L1-local 100 %, buscador ≥ 98 %; T1/T2 por tipo, §5.2 ≥ 98 %)
C3.2 bucle (Dfa: sinapsis automáticas + emergentes + CSV falsos; Dfm: `manual` falsas)
C3.4 costo por par constante entre |D| = 800 y 2400 (± 20 %)
C3.7 Spearman(aguja, grado de A) ≤ 0,3 en cada escritura
C3.8 vacua (constante en una escritura) → «no medible»
Las AUC se informan con la marca «filtración léxica por construcción» y no cuentan para admitir.
Uso: python resumen_capa_L.py [carpeta_resultados]
"""
import glob
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
RES = sys.argv[1] if len(sys.argv) > 1 else os.path.join(AQUI, "resultados")
LOCALES = ("S_tem", "S_tono", "S_sk", "S_idf", "X_min", "X_max", "X_concepto", "X_sk", "X_contenido",
           "B_flag", "B_weight", "B_angulos", "Cat")
BUSCADOR = ("G_ciego", "R")
GRAFO = ("K", "L1_local", "T2")
TODAS = LOCALES + BUSCADOR + GRAFO
UMBRAL = {**{a: 1.0 for a in LOCALES + ("K", "L1_local")}, **{a: 0.98 for a in BUSCADOR}}
GRUPO = {**{a: "locales" for a in LOCALES}, **{a: "buscador" for a in BUSCADOR}, **{a: "grafo" for a in GRAFO}}
ESCRITURAS = ("lat_a", "lat_b", "han", "jpn")
# qué debe NO cambiar en cada inyección del bucle (C3.2)
BUCLE_DEBE_IGUAL = {"Dfa": LOCALES + BUSCADOR + ("L1_local",), "Dfm": LOCALES}


def cargar():
    cs = {}
    for f in sorted(glob.glob(os.path.join(RES, "config_s*_n*.json"))):
        a = json.load(open(f))
        cs[(a["semilla"], a["n_D"])] = a
    return cs


def main():
    cs = cargar()
    if not cs:
        sys.exit("sin resultados en %s" % RES)
    tam = sorted({n for _s, n in cs})
    sem = sorted({s for s, _n in cs})
    res = {"configs": ["s%d_n%d" % k for k in sorted(cs)], "agujas": {}}
    L = ["# Paso 3, capa L — tablas (generadas por `resumen_capa_L.py`)", "",
         "Configuraciones: " + ", ".join(res["configs"]), ""]
    # control de la medición
    L += ["## Controles de la medición", "", "| config | pares D–D con arista | copia limpia (sinapsis/asoc./emerg. al final) "
          "| original intacta | recuerdos en corto plazo | bridges rechazados (D) | aristas manual (D) | inmunes (D) "
          "| D activos/dormidos | s por búsqueda (D) |", "|---|---|---|---|---|---|---|---|---|---|"]
    for k in sorted(cs):
        a = cs[k]
        cl = a["copia_limpia"]
        L.append("| s%d_n%d | %d | %s | %s | %s | %d | %d | %d | %d/%d | %.4f |" % (
            k[0], k[1], a["n_pares_D"],
            " · ".join("%s %d/%d/%d" % (w, v["sinapsis_fin"], v["asociaciones_fin"], v["emergentes_fin"])
                       for w, v in cl.items() if v),
            all(a["original_intacta"].values()), sum(a["n_corto_plazo"].values()),
            a["info"]["D"]["bridges_rechazados"], a["info"]["D"]["vinculos"], a["recuerdos_inmunes"]["D"],
            a["estado_D_en_D"]["activo"], a["estado_D_en_D"]["dormido"], a["busqueda_s_por_consulta"]["D"]))
    L.append("")
    L += ["## Top-K ciego idéntico (recuerdos de D)", "", "| config | D∪I0 | D∪I1 | Dfa (bucle) | no-D en tops D∪I0 / D∪I1 |",
          "|---|---|---|---|---|"]
    for k in sorted(cs):
        t = cs[k]["topk_ciego_identico"]
        L.append("| s%d_n%d | %d/%d | %d/%d | %d/%d | %d / %d |" % (
            k[0], k[1], t["DI0"]["top_identico"], t["DI0"]["n"], t["DI1"]["top_identico"], t["DI1"]["n"],
            t["Dfa"]["top_identico"], t["Dfa"]["n"], t["DI0"]["apariciones_no_D_en_tops"],
            t["DI1"]["apariciones_no_D_en_tops"]))
    L.append("")
    # costo por par por grupo y por tamaño (media de semillas)
    costo = {}
    for g in ("locales", "buscador", "grafo"):
        costo[g] = {n: sum(cs[(s, n)]["costo_s_por_par"][g] for s in sem if (s, n) in cs) /
                    max(1, sum(1 for s in sem if (s, n) in cs)) for n in tam}
    busq = {n: sum(cs[(s, n)]["busqueda_s_por_consulta"]["D"] for s in sem if (s, n) in cs) /
            max(1, sum(1 for s in sem if (s, n) in cs)) for n in tam}
    res["costo"] = {"por_par": costo, "busqueda_por_consulta": busq}
    # por aguja
    filas = []
    for a in TODAS:
        r = {"C3.1": {}, "C3.2": {}, "C3.7": {}, "C3.8": {}, "auc": {}}
        ok1 = True
        for k in sorted(cs):
            for w in ("DI0", "DI1"):
                x = cs[k]["invariancia_y_bucle"][w][a]
                r["C3.1"]["s%d_n%d_%s" % (k[0], k[1], w)] = x["frac"]
                if a in UMBRAL and x["frac"] is not None and x["frac"] < UMBRAL[a]:
                    ok1 = False
        ok2 = True
        aplica2 = False
        for k in sorted(cs):
            for w, debe in BUCLE_DEBE_IGUAL.items():
                x = cs[k]["invariancia_y_bucle"][w][a]
                r["C3.2"]["s%d_n%d_%s" % (k[0], k[1], w)] = x["frac"]
                if a in debe:
                    aplica2 = True
                    if x["frac"] is not None and x["frac"] < 1.0:
                        ok2 = False
        cambia_con_grafo = any((cs[k]["invariancia_y_bucle"]["Dfa"][a]["frac"] or 1.0) < 1.0 or
                               (cs[k]["invariancia_y_bucle"]["Dfm"][a]["frac"] or 1.0) < 1.0 for k in cs)
        ok7, ok8 = True, True
        rhos = []
        for esc in ESCRITURAS:
            for k in sorted(cs):
                rho = cs[k]["spearman_grado"][esc].get(a)
                vac = cs[k]["vacua"][esc].get(a)
                au = cs[k]["auc_filtracion_lexica"][esc].get(a, {}).get("auc")
                r["C3.7"]["s%d_n%d_%s" % (k[0], k[1], esc)] = rho
                r["C3.8"]["s%d_n%d_%s" % (k[0], k[1], esc)] = vac
                r["auc"]["s%d_n%d_%s" % (k[0], k[1], esc)] = au
                if rho is not None:
                    rhos.append(rho)
                    if rho > 0.3:
                        ok7 = False
                if vac:
                    ok8 = False
        g = GRUPO[a]
        c0, c1 = costo[g][tam[0]], costo[g][tam[-1]]
        ratio = c1 / c0 if c0 else None
        ok4 = ratio is not None and ratio <= 1.2
        if g == "buscador":
            rb = busq[tam[-1]] / busq[tam[0]] if busq[tam[0]] else None
            r["busqueda_ratio"] = rb
            ok4 = ok4 and rb is not None and rb <= 1.2
        r["costo_ratio_por_par"] = ratio
        r["veredicto"] = {"C3.1": ok1 if a in UMBRAL else "por tipo (§5.2)", "C3.2": ok2 if aplica2 else
                          ("lee el grafo → C3.5" if cambia_con_grafo else "no cambia"), "C3.4": ok4,
                          "C3.7": ok7, "C3.8": ok8}
        limpia = all(v is True for kk, v in r["veredicto"].items() if kk != "C3.2" or aplica2)
        if a in GRAFO:
            limpia = limpia and not cambia_con_grafo
        r["capa_L"] = "limpia" if limpia else "no limpia"
        if a == "T2":   # el tipo se decide por tipo (§5.2), no con un umbral único
            r["capa_L"] = "por tipo (§5.2)" if ok4 and ok7 and ok8 else "no limpia"
        aucs = [v for v in r["auc"].values() if v is not None]
        r["auc_media_marcada"] = round(sum(aucs) / len(aucs), 3) if aucs else None
        r["rho_max"] = max(rhos) if rhos else None
        dentro = [v for k in cs for esc in ESCRITURAS
                  for v in (cs[k].get("spearman_grado_por_clase", {}).get(esc, {}).get(a) or {}).values()
                  if v is not None]
        r["rho_max_dentro_de_clase"] = max(dentro) if dentro else None
        res["agujas"][a] = r
        filas.append((a, r))
    L += ["## Veredicto por aguja (capa L)", "",
          "AUC = media sobre escrituras y configuraciones, **con filtración léxica por construcción: no cuenta para "
          "admitir**.", "",
          "| aguja | C3.1 invariancia (mín. D∪I0 / D∪I1) | C3.2 bucle (mín. Dfa / Dfm) | C3.4 costo (×, 2400 vs 800) "
          "| C3.7 ρ máx. con el grado | ρ máx. dentro de clase (diagnóstico) | C3.8 no vacua | capa L | AUC (marcada) |",
          "|---|---|---|---|---|---|---|---|---|"]
    for a, r in filas:
        m1 = [min(v for kk, v in r["C3.1"].items() if kk.endswith(w) and v is not None) if any(
            kk.endswith(w) and v is not None for kk, v in r["C3.1"].items()) else None for w in ("DI0", "DI1")]
        m2 = [min((v for kk, v in r["C3.2"].items() if kk.endswith(w) and v is not None), default=None)
              for w in ("Dfa", "Dfm")]
        fmt = lambda x: "—" if x is None else ("%.4f" % x)  # noqa: E731
        v = r["veredicto"]
        L.append("| %s | %s / %s %s | %s / %s %s | %s %s | %s %s | %s | %s | **%s** | %s |" % (
            a, fmt(m1[0]), fmt(m1[1]), "✓" if v["C3.1"] is True else ("✗" if v["C3.1"] is False else v["C3.1"]),
            fmt(m2[0]), fmt(m2[1]), "✓" if v["C3.2"] is True else ("✗" if v["C3.2"] is False else v["C3.2"]),
            fmt(r["costo_ratio_por_par"]) + (" (búsq. %s)" % fmt(r.get("busqueda_ratio")) if "busqueda_ratio" in r
                                             else ""), "✓" if v["C3.4"] else "✗",
            fmt(r["rho_max"]), "✓" if v["C3.7"] else "✗", fmt(r["rho_max_dentro_de_clase"]),
            "✓" if v["C3.8"] else "✗ (vacua en alguna escritura)",
            r["capa_L"], fmt(r["auc_media_marcada"])))
    L.append("")
    # §5.2 tipo
    tipos = sorted({t for k in cs for w in ("DI0", "DI1") for t in cs[k]["tipo_invariancia"][w]})
    res["tipo"] = {}
    L += ["## §5.2 Invariancia por tipo de arista (pares D–D: existencia del tipo idéntica en D y en D∪I)", "",
          "| tipo | prioridad | mín. D∪I0 | mín. D∪I1 | aristas en D (suma) | ≥ 98 % |", "|---|---|---|---|---|---|"]
    pr = {"manual": 0, "sinonimo_explicito": 1, "co_semantica": 2, "latente_confirmada": 3, "co_ocurrencia": 4,
          "co_nombre": 5, "pmi_hebbiano": 9}
    for t in tipos:
        mins = []
        for w in ("DI0", "DI1"):
            vs = [cs[k]["tipo_invariancia"][w][t]["identicas_frac"] for k in cs if t in cs[k]["tipo_invariancia"][w]]
            mins.append(min(vs) if vs else None)
        nD = sum(cs[k]["tipo_invariancia"]["DI0"].get(t, {}).get("en_D", 0) for k in cs)
        ok = all(m is not None and m >= 0.98 for m in mins)
        res["tipo"][t] = {"min_DI0": mins[0], "min_DI1": mins[1], "n_D": nD, "ok": ok}
        L.append("| %s | %s | %s | %s | %d | %s |" % (t, pr.get(t, "50 (sin prioridad)"),
                                                    "—" if mins[0] is None else "%.4f" % mins[0],
                                                    "—" if mins[1] is None else "%.4f" % mins[1], nD,
                                                    "✓" if ok else "✗"))
    L.append("")
    # tipos por escritura y verdad (suma)
    L += ["## Tipos por escritura y verdad (mundo D, suma de configuraciones)", "",
          "| escritura | tipo | tema | puente | accidental | ajeno |", "|---|---|---|---|---|---|"]
    agg = {}
    for k in cs:
        for esc, d in cs[k]["tipos_por_escritura_y_verdad"].items():
            for t, vv in d.items():
                for ver, n in vv.items():
                    agg.setdefault((esc, t), {}).setdefault(ver, 0)
                    agg[(esc, t)][ver] += n
    for (esc, t), vv in sorted(agg.items()):
        L.append("| %s | %s | %d | %d | %d | %d |" % (esc, t, vv.get("tema", 0), vv.get("puente", 0),
                                                     vv.get("accidental", 0), vv.get("ajeno", 0)))
    res["tipos_por_escritura"] = {"%s|%s" % k: v for k, v in agg.items()}
    L.append("")
    L += ["## Costo", "", "| grupo | " + " | ".join("s/par |D|=%d" % n for n in tam) + " |",
          "|---|" + "---|" * len(tam)]
    for g in ("locales", "buscador", "grafo"):
        L.append("| %s | %s |" % (g, " | ".join("%.2e" % costo[g][n] for n in tam)))
    L.append("| búsqueda ciega (s/consulta) | %s |" % " | ".join("%.4f" % busq[n] for n in tam))
    L.append("")
    # control de reloj (control_reloj.py): ¿lo que cambia en §5.2 lo cambia el contenido de I o el tiempo?
    for fr in sorted(f for f in os.listdir(RES) if f.startswith("control_reloj_n")):
        cr = json.load(open(os.path.join(RES, fr)))
        L += ["## Control de reloj (%s): D frente a Dt (mismos días y sueños que D∪I, sin documentos)" % fr, "",
              "Cada celda: en D / en el otro mundo / en ambos. «=» quiere decir que Dt coincide exactamente con D∪I0 y "
              "con D∪I1.", "", "| semilla | tipo | D→Dt | D→D∪I0 | D→D∪I1 | ¿Dt = D∪I? |", "|---|---|---|---|---|---|"]
        iguales = True
        for r in cr:
            for t in sorted(r["D_vs_Dt"]):
                f3 = lambda x: "%s/%s/%s" % (x.get("en_D"), x.get("en_W"), x.get("en_ambos")) if x else "—"  # noqa: E731
                a_, b_, c_ = r["D_vs_Dt"][t], (r["D_vs_DI0_previo"] or {}).get(t), (r["D_vs_DI1_previo"] or {}).get(t)
                eq = f3(a_) == f3(b_) == f3(c_)
                iguales &= eq
                L.append("| %s | %s | %s | %s | %s | %s |" % (r["semilla"], t, f3(a_), f3(b_), f3(c_), "=" if eq else "≠"))
        L += ["", "**Dt = D∪I en todas las celdas: %s.** Si es sí, la parte del cambio atribuible al contenido de I es "
              "cero y lo explica el paso del tiempo (sueños)." % ("sí" if iguales else "no"), ""]
        res["control_reloj_" + fr] = iguales
    open(os.path.join(RES, "tablas.md"), "w").write("\n".join(L))
    json.dump(res, open(os.path.join(RES, "resumen.json"), "w"), ensure_ascii=False, indent=1)
    print("\n".join(L))


if __name__ == "__main__":
    main()
