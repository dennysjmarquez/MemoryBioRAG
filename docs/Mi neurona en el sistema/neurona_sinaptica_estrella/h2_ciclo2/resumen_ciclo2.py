"""Agrega resultados/config_*.json, k8_*.json y controles.json del ciclo 2 en tablas y marca los criterios con los
ajustes del ciclo 2 (PROPUESTA_PROTOCOLO_CICLO2.md §1 y §4): atribución′, K2′ (conjunto fijo, sin filtrar), K5″,
K7′ (≤ 1,2 × T por sueño), M3′, residual en línea propia y «vacuo». Solo lee archivos; no construye ni mide nada.

Uso: python resumen_ciclo2.py [carpeta]  → escribe <carpeta>/resumen.json y <carpeta>/tablas.md
"""
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
RES = sys.argv[1] if len(sys.argv) > 1 else os.path.join(AQUI, "resultados")
BRAZOS = ("T", "-H2-4b", "H2loc", "4bp", "H2loc+4bp")
SEMILLAS = (7, 11, 23)
RELOJES = ("comprimido", "diario")
NEUS = ("real", "ctl")


def cargar():
    cfg = {}
    for f in sorted(os.listdir(RES)):
        if f.startswith("config_"):
            neu, s, n, r = f[len("config_"):-5].split("_")
            cfg[(neu, int(n[1:]), r, int(s[1:]))] = json.load(open(os.path.join(RES, f)))
    k8 = {}
    for neu in NEUS:
        p = os.path.join(RES, "k8_%s.json" % neu)
        if os.path.exists(p):
            k8[neu] = json.load(open(p))
    p = os.path.join(RES, "controles.json")
    return cfg, k8, (json.load(open(p)) if os.path.exists(p) else None)


def veredicto(ok, vacuo=False):
    if ok is None:
        return "no medible"
    return ("cumplido" + (" (vacuo)" if vacuo else "")) if all(ok) else "no cumplido"


def atrib(x):
    return x["S1"]["atribuibles_con_regla_estado_D"]


def residual(x):
    return x["S1"]["top5_cambiados_total"] - atrib(x)


def evaluar(cfg, k8):
    out, tam = {}, {}
    for neu in NEUS:
        tamanos = sorted({k[1] for k in cfg if k[0] == neu})
        tam[neu] = tamanos
        for n in tamanos:
            for r in RELOJES:
                cs = [cfg.get((neu, n, r, s)) for s in SEMILLAS]
                if any(c is None for c in cs):
                    continue
                ev = {}
                for b in BRAZOS:
                    e = {}
                    vac = all(c[b]["activos_D_final"]["D"] == 0 and c[b]["activos_D_final"]["DI0"] == 0 for c in cs)
                    e["K1"] = veredicto([c[b]["S1"]["cambios_estado_D"] == 0 and c[b]["S1"]["cambios_importancia_D"] == 0
                                         and atrib(c[b]) == 0 for c in cs], vacuo=vac)
                    e["K3"] = veredicto([c[b]["K3"]["cambian_de_puesto"] == 0 and c[b]["K3"]["faltan"] == 0 for c in cs],
                                        vacuo=vac or all(c[b]["K3"]["preguntas"] == 0 for c in cs))
                    k6_vac = all(sum(c[b]["K6"][w]["dormidos_por_H2"] + c[b]["K6"][w]["dormidos_por_peso_propio"]
                                     for w in c[b]["K6"]) == 0 for c in cs)
                    e["K6"] = veredicto([all(c[b]["K6"][w]["dormidos_por_H2"] == 0 for w in c[b]["K6"]) for c in cs],
                                        vacuo=k6_vac)
                    if b == "T":
                        e["K2p"] = e["K4"] = e["K5pp"] = "referencia (= T)"
                    else:
                        def m3(c, x):
                            # M3 + M3′: inserciones de I′ en el top-5 que no son legítimas (difusas, violaciones y,
                            # en las consultas con la entidad puente, las accidentales o ajenas)
                            v = c[x]["M3p"]["inserciones_I1_top5_por_verdad"]
                            return c[x]["M3"]["falsos_positivos_difusos"] + c[x]["M3"]["violaciones_C2_ajeno"] + \
                                c[x]["M3"]["otras_ajeno_con_texto"] + v["accidental"] + v["ajeno"]

                        def frac_orden(x, w):
                            d = x[w]["con_lista_en_ambos"]
                            return x[w]["orden_cambiado"] / d if d else None
                        k2, no_comp = [], 0
                        for c in cs:
                            x, t = c[b]["K2p"], c["T"]["K2p"]
                            ok = True
                            for w in ("DI0", "DI1"):
                                ok = ok and x[w]["cobertura_perdida"] <= t[w]["cobertura_perdida"] and \
                                    x["recall_origen_top5"][w] >= t["recall_origen_top5"][w]
                                fx, ft = frac_orden(x, w), frac_orden(t, w)
                                if ft is None:          # T sin listas en los dos mundos: el orden no es comparable
                                    no_comp += 1
                                elif fx is not None:
                                    ok = ok and fx <= ft
                            ok = ok and m3(c, b) <= m3(c, "T") and \
                                c[b]["S1"]["inserciones_I0_top5"] <= c["T"]["S1"]["inserciones_I0_top5"]
                            k2.append(ok)
                        e["K2p_orden_no_comparable"] = no_comp
                        e["K2p"] = veredicto(k2)
                        if no_comp and e["K2p"].startswith("cumplido"):
                            e["K2p"] += " (orden no comparable en %d de 6 mundos: T sin listas)" % no_comp
                        k4 = []
                        for c in cs:
                            x, t = c[b]["K4_DI1"], c["T"]["K4_DI1"]
                            k4.append(x["tema"] >= t["tema"] and x["puente"] >= t["puente"] and
                                      x["accidental"] + x["ajeno"] <= t["accidental"] + t["ajeno"] and
                                      x["precision_tema_puente"] >= t["precision_tema_puente"] and
                                      x["grado_medio"] <= 1.25 * t["grado_medio"])
                        e["K4"] = veredicto(k4)
                        e["K5pp"] = veredicto([(c[b]["K5_DI1"]["frac_tema_puente"] or 0) >=
                                               (c["T"]["K5_DI1"]["frac_tema_puente"] or 0) and
                                               c[b]["K5pp"]["DI1"] >= c["T"]["K5pp"]["DI1"] for c in cs])
                    e["costo_por_sueno_vs_T"] = [round(c[b]["K7p"]["s_por_sueno"] / c["T"]["K7p"]["s_por_sueno"], 2)
                                                 for c in cs]
                    ev[b] = e
                out["%s|%d|%s" % (neu, n, r)] = ev
    fin = {}
    for neu in NEUS:
        for b in BRAZOS:
            f = {}
            for r in RELOJES:
                claves = ["%s|%d|%s" % (neu, n, r) for n in tam[neu]]
                if len(tam[neu]) < 2 or not all(k in out for k in claves):
                    f["K7p_" + r] = "no medible"
                    continue
                ks = ("K1", "K3") if b == "T" else ("K1", "K2p", "K3", "K4", "K5pp")
                ok = all(out[k][b][x].startswith("cumplido") for k in claves for x in ks) and \
                    all(v <= 1.2 for k in claves for v in out[k][b]["costo_por_sueno_vs_T"])
                f["K7p_" + r] = "cumplido" if ok else "no cumplido"
            if neu in k8:
                filas = [v for k, v in k8[neu].items() if k.split("|")[1] == b]
                f["K8"] = veredicto([v["sin_excepciones"] and v["recuerdos_dormidos_mas_de_una_vez"] == 0 and
                                     v["K1_cambios_estado_D"] == 0 and v["K1_cambios_importancia_D"] == 0
                                     for v in filas])
            else:
                f["K8"] = "no medible"
            f["K9"] = "futuro (suite completa: autorización aparte)"
            fin["%s|%s" % (neu, b)] = f
    return out, fin


def tablas(cfg, k8, ctl, ev, fin):
    L = []
    w = L.append
    w("# Ciclo 2 H2/4b — tablas (laboratorio sintético; generado por resumen_ciclo2.py)\n")
    w("Controles: %s\n" % json.dumps(ctl, ensure_ascii=False))
    for neu in NEUS:
        w("\n## Configuración «%s» (%s; PPMI 0,15; corte tras D)\n" % (
            neu, "Neurona 1 activa" if neu == "real" else "BIORAG_NEURONA=0 en toda la corrida"))
        for key in sorted({"%s|%d|%s" % k[:3] for k in cfg if k[0] == neu},
                          key=lambda x: (int(x.split("|")[1]), x)):
            _, n, r = key.split("|")
            cs = {s: cfg.get((neu, int(n), r, s)) for s in SEMILLAS}
            if any(v is None for v in cs.values()):
                continue
            g = lambda b, f: " / ".join(str(f(cs[s][b])) for s in SEMILLAS)  # noqa: E731
            w("\n### %s · |D| = %s · reloj %s — semillas 7 / 11 / 23\n" % (neu, n, r))
            w("| brazo | Δestado D (D∪I0) | Δimportancia D | top-5 cambiados (total) | atribuibles′ H2/4b | **residual no atribuido** | estado D idéntico | activos de D al final D→D∪I0 |")
            w("|---|---|---|---|---|---|---|---|")
            for b in BRAZOS:
                w("| %s | %s | %s | %s | %s | %s | %s | %s |" % (
                    b, g(b, lambda x: x["S1"]["cambios_estado_D"]), g(b, lambda x: x["S1"]["cambios_importancia_D"]),
                    g(b, lambda x: x["S1"]["top5_cambiados_total"]), g(b, atrib), g(b, residual),
                    g(b, lambda x: "sí" if x["S1"]["estado_D_identico"] else "no"),
                    g(b, lambda x: "%d→%d" % (x["activos_D_final"]["D"], x["activos_D_final"]["DI0"]))))
            w("\n| brazo | K2′ D∪I0: cobertura perdida · orden cambiado/con lista | K2′ D∪I1: idem | recall origen D / D∪I0 / D∪I1 | M3 difusas+violaciones | M3′ puente/accid.+ajeno (consultas) | K3 cambian·faltan | K4 D∪I1 tema·puente·acc+aj·prec·grado | K5 buenos (frac.) | K6 dormidos vecindad/global · peso propio | s/sueño (×T) |")
            w("|---|---|---|---|---|---|---|---|---|---|---|")
            for b in BRAZOS:
                w("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
                    b,
                    g(b, lambda x: "%d · %d/%d" % (x["K2p"]["DI0"]["cobertura_perdida"], x["K2p"]["DI0"]["orden_cambiado"],
                                                   x["K2p"]["DI0"]["con_lista_en_ambos"])),
                    g(b, lambda x: "%d · %d/%d" % (x["K2p"]["DI1"]["cobertura_perdida"], x["K2p"]["DI1"]["orden_cambiado"],
                                                   x["K2p"]["DI1"]["con_lista_en_ambos"])),
                    g(b, lambda x: "%.3f·%.3f·%.3f" % tuple(x["recall_origen_top5"][k] for k in ("D", "DI0", "DI1"))),
                    g(b, lambda x: x["M3"]["falsos_positivos_difusos"] + x["M3"]["violaciones_C2_ajeno"] +
                      x["M3"]["otras_ajeno_con_texto"]),
                    g(b, lambda x: "%d/%d (%d)" % (x["M3p"]["inserciones_I1_top5_por_verdad"]["puente"],
                                                   x["M3p"]["inserciones_I1_top5_por_verdad"]["accidental"] +
                                                   x["M3p"]["inserciones_I1_top5_por_verdad"]["ajeno"],
                                                   x["M3p"]["consultas_puente"])),
                    g(b, lambda x: "%d·%d" % (x["K3"]["cambian_de_puesto"], x["K3"]["faltan"])),
                    g(b, lambda x: "%d·%d·%d·%.3f·%.2f" % (x["K4_DI1"]["tema"], x["K4_DI1"]["puente"],
                                                          x["K4_DI1"]["accidental"] + x["K4_DI1"]["ajeno"],
                                                          x["K4_DI1"]["precision_tema_puente"], x["K4_DI1"]["grado_medio"])),
                    g(b, lambda x: "%d (%.3f)" % (x["K5pp"]["DI1"], x["K5_DI1"]["frac_tema_puente"] or 0)),
                    g(b, lambda x: "%d · %d" % (x["K6"]["DI1"]["dormidos_por_H2"], x["K6"]["DI1"]["dormidos_por_peso_propio"])),
                    g(b, lambda x: "%.3f" % x["K7p"]["s_por_sueno"]) + " (" +
                    " / ".join(str(v) for v in ev[key][b]["costo_por_sueno_vs_T"]) + ")"))
            w("\nNeurona 1 por mundo (campeón D/D∪I0/D∪I1 · ascensos · reinicios) y aristas por tipo × verdad en D∪I1"
              " (suma de semillas; tema/puente/accidental/ajeno):\n")
            w("| brazo | Neurona 1 | aristas por tipo (tema·puente·accid.·ajeno) | H2-local dormidos D/D∪I0 · 4b-propio escalados D/D∪I0 |")
            w("|---|---|---|---|")
            for b in BRAZOS:
                def neur(x):
                    nn = x["neurona"]
                    if not nn["D"].get("tabla"):
                        return "sin tabla"
                    return "%s %s·%s" % ("".join("C" if nn[m]["campeon"] else "–" for m in ("D", "DI0", "DI1")),
                                         "/".join(str(nn[m]["ascensos"]) for m in ("D", "DI0", "DI1")),
                                         "/".join(str(nn[m]["reinicios"]) for m in ("D", "DI0", "DI1")))
                tv = {}
                for s in SEMILLAS:
                    for t, d in cs[s][b]["C_medida"]["tipo_x_verdad_DI1"].items():
                        acc = tv.setdefault(t, [0, 0, 0, 0])
                        for i, k in enumerate(("tema", "puente", "accidental", "ajeno")):
                            acc[i] += d[k]
                w("| %s | %s | %s | %s |" % (
                    b, g(b, neur), "; ".join("%s %s" % (t, "·".join(map(str, v))) for t, v in sorted(tv.items())),
                    g(b, lambda x: "%d/%d · %d/%d" % (x["actividad_variantes"]["D"]["h2loc_dormidos"],
                                                      x["actividad_variantes"]["DI0"]["h2loc_dormidos"],
                                                      x["actividad_variantes"]["D"]["4bp_escalados"],
                                                      x["actividad_variantes"]["DI0"]["4bp_escalados"]))))
            w("\nVeredictos de este bloque:\n")
            w("K2′: cobertura perdida y recall del origen no peores que T; orden cambiado como fracción de las consultas con"
              " lista en los dos mundos (si T no tiene ninguna, el orden no es comparable y se indica); M3+M3′ (inserciones"
              " de I′ no legítimas) e inserciones de I0 no mayores que en T.\n")
            w("| brazo | K1 | K2′ | K3 | K4 | K5″ | K6 |")
            w("|---|---|---|---|---|---|---|")
            for b in BRAZOS:
                e = ev[key][b]
                w("| %s | %s | %s | %s | %s | %s | %s |" % (b, e["K1"], e["K2p"], e["K3"], e["K4"], e["K5pp"], e["K6"]))
        if neu in k8:
            w("\n### %s · K8: desde DB vacía (sesiones de 5 mezcladas, reloj diario, 320 D + 80 I0)\n" % neu)
            w("| semilla · brazo | ciclos | dormidos H2/H2-local · peso propio | dormidos > 1 vez | Δestado / Δimportancia D | activos al final |")
            w("|---|---|---|---|---|---|")
            for k, v in sorted(k8[neu].items(), key=lambda kv: (BRAZOS.index(kv[0].split("|")[1]), kv[0])):
                w("| %s | %d | %d · %d | %d | %d / %d | %d |" % (k, v["ciclos"], v["dormidos_por_H2_o_H2loc"],
                                                              v["dormidos_por_peso_propio"],
                                                              v["recuerdos_dormidos_mas_de_una_vez"],
                                                              v["K1_cambios_estado_D"], v["K1_cambios_importancia_D"],
                                                              v["activos_final_DI0"]))
        w("\n### %s · K7′, K8, K9\n" % neu)
        w("| brazo | K7′ comprimido | K7′ diario | K8 | K9 |")
        w("|---|---|---|---|---|")
        for b in BRAZOS:
            f = fin["%s|%s" % (neu, b)]
            w("| %s | %s | %s | %s | %s |" % (b, f["K7p_comprimido"], f["K7p_diario"], f["K8"], f["K9"]))
    return "\n".join(L) + "\n"


def main():
    cfg, k8, ctl = cargar()
    ev, fin = evaluar(cfg, k8)
    json.dump({"bloques": ev, "finales": fin, "controles": ctl}, open(os.path.join(RES, "resumen.json"), "w"),
              ensure_ascii=False, indent=1)
    open(os.path.join(RES, "tablas.md"), "w").write(tablas(cfg, k8, ctl, ev, fin))
    print(open(os.path.join(RES, "tablas.md")).read())


if __name__ == "__main__":
    main()
