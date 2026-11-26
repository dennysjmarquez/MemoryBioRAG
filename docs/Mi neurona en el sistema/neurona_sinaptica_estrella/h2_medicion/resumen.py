"""Agrega resultados/config_*.json y controles_y_k8.json en tablas y marca K1–K9 (cumplido / no cumplido / no
medible) según §8 de la propuesta v2. Solo lee archivos de resultados; no construye ni mide nada.

Uso: python resumen.py  → escribe resultados/resumen.json y resultados/tablas.md
"""
import json
import os

AQUI = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(AQUI, "resultados")
BRAZOS = ("T", "-H2", "-4b", "-H2-4b")
SEMILLAS = (7, 11, 23)
RELOJES = ("comprimido", "diario")


def cargar():
    cfg = {}
    for f in sorted(os.listdir(RES)):
        if f.startswith("config_"):
            s, n, r = f[len("config_"):-5].split("_")
            cfg[(int(n[1:]), r, int(s[1:]))] = json.load(open(os.path.join(RES, f)))
    return cfg


def veredicto(ok_lista, vacuo=False):
    if ok_lista is None:
        return "no medible"
    return ("cumplido" + (" (vacuo)" if vacuo else "")) if all(ok_lista) else "no cumplido"


def evaluar(cfg, k8):
    tamanos = sorted({k[0] for k in cfg})
    out = {}
    for n in tamanos:
        for r in RELOJES:
            cs = [cfg.get((n, r, s)) for s in SEMILLAS]
            if any(c is None for c in cs):
                continue
            ev = {}
            for b in BRAZOS:
                e = {}
                e["K1"] = veredicto([c[b]["S1"]["cambios_estado_D"] == 0 and c[b]["S1"]["cambios_importancia_D"] == 0
                                     and c[b]["S1"]["top5_cambiados_atribuibles_H2_4b"] == 0 for c in cs])
                e["K3"] = veredicto([c[b]["K3"]["cambian_de_puesto"] == 0 and c[b]["K3"]["faltan"] == 0 for c in cs])
                k6_vacuo = all(sum(c[b]["K6"][w]["dormidos_por_H2"] + c[b]["K6"][w]["dormidos_por_peso_propio"]
                                   for w in c[b]["K6"]) == 0 for c in cs)
                e["K6"] = veredicto([all(c[b]["K6"][w]["dormidos_por_H2"] == 0 for w in c[b]["K6"]) for c in cs],
                                    vacuo=k6_vacuo)
                if b == "T":
                    e["K2"] = e["K4"] = e["K5"] = "referencia (= T)"
                else:
                    def m3(c, x):
                        return c[x]["M3"]["falsos_positivos_difusos"] + c[x]["M3"]["violaciones_C2_ajeno"] + \
                            c[x]["M3"]["otras_ajeno_con_texto"]
                    e["K2"] = veredicto([c[b]["M1"] >= c["T"]["M1"] and
                                         (c[b]["M2"]["orden_relativo_conservado"] or 0) >=
                                         (c["T"]["M2"]["orden_relativo_conservado"] or 0) and
                                         m3(c, b) <= m3(c, "T") and
                                         c[b]["S1"]["inserciones_I0_top5"] <= c["T"]["S1"]["inserciones_I0_top5"]
                                         for c in cs])
                    k4 = []
                    for c in cs:
                        x, t = c[b]["K4_DI1"], c["T"]["K4_DI1"]
                        k4.append(x["tema"] >= t["tema"] and x["puente"] >= t["puente"] and
                                  x["accidental"] + x["ajeno"] <= t["accidental"] + t["ajeno"] and
                                  x["precision_tema_puente"] >= t["precision_tema_puente"] and
                                  x["grado_medio"] <= 1.25 * t["grado_medio"])
                    e["K4"] = veredicto(k4)
                    e["K5"] = veredicto([c[b]["K5_DI1"]["frac_tema_puente"] >= c["T"]["K5_DI1"]["frac_tema_puente"]
                                         for c in cs])
                e["costo_vs_T"] = [round(c[b]["costo"]["t_sueno_DI1_s"] / c["T"]["costo"]["t_sueno_DI1_s"], 2)
                                   for c in cs]
                ev[b] = e
            out["%d|%s" % (n, r)] = ev
    # K7 (crecimiento: K1–K5 en los dos tamaños + costo ≤ 1,2 × T), K8, K9
    fin = {}
    for b in BRAZOS:
        f = {}
        for r in RELOJES:
            claves = ["%d|%s" % (n, r) for n in tamanos]
            if not all(k in out for k in claves) or len(tamanos) < 2:
                f["K7_" + r] = "no medible"
                continue
            ks = ("K1", "K3") if b == "T" else ("K1", "K2", "K3", "K4", "K5")
            ok = all(out[k][b][x].startswith("cumplido") for k in claves for x in ks) and \
                all(v <= 1.2 for k in claves for v in out[k][b]["costo_vs_T"])
            f["K7_" + r] = "cumplido" if ok else "no cumplido"
        if k8:
            filas = [v for k, v in k8.items() if k.split("|")[1] == b]
            f["K8"] = veredicto([v["sin_excepciones"] and v["recuerdos_dormidos_mas_de_una_vez"] == 0 and
                                 v["K1_cambios_estado_D"] == 0 and v["K1_cambios_importancia_D"] == 0 for v in filas])
        else:
            f["K8"] = "no medible"
        f["K9"] = "no medible en esta etapa (suite completa: autorización aparte)"
        fin[b] = f
    return out, fin


def tablas(cfg, k8, ev, fin):
    L = []
    w = L.append
    for key in sorted({"%d|%s" % (k[0], k[1]) for k in cfg}, key=lambda x: (int(x.split("|")[0]), x)):
        n, r = key.split("|")
        cs = {s: cfg.get((int(n), r, s)) for s in SEMILLAS}
        if any(v is None for v in cs.values()):
            continue
        w("\n### |D| = %s (mundo de %d), reloj %s — semillas 7 / 11 / 23\n" % (n, int(n) * 5 // 4, r))
        w("| brazo | Δestado D | Δimportancia D | top-5 cambiados (total) | atribuibles H2/4b (regla) | también con −H2−4b | estado D idéntico | recall origen D → D∪I0 | activos de D al final, D → D∪I0 |")
        w("|---|---|---|---|---|---|---|---|---|")
        for b in BRAZOS:
            g = lambda f: " / ".join(str(f(cs[s][b])) for s in SEMILLAS)  # noqa: E731
            w("| %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
                b, g(lambda x: x["S1"]["cambios_estado_D"]), g(lambda x: x["S1"]["cambios_importancia_D"]),
                g(lambda x: x["S1"]["top5_cambiados_total"]), g(lambda x: x["S1"]["top5_cambiados_atribuibles_H2_4b"]),
                g(lambda x: x["S1"]["top5_cambiados_tambien_sin_H2_4b"]),
                g(lambda x: "sí" if x["S1"].get("estado_D_identico") else "no"),
                g(lambda x: "%.2f→%.2f" % (x["recall_origen_top5"]["D"], x["recall_origen_top5"]["DI0"])),
                g(lambda x: "%d→%d" % (x["activos_D_final"]["D"], x["activos_D_final"]["DI0"]))))
        w("\n| brazo | M1 | M2 | M3 inserciones I′: puente / difusas / violaciones | K3 preguntas: cambian / faltan | K4 D∪I′: tema / puente / accidental+ajeno / precisión / grado | K5 visibles buenos (fracción) | dormidos H2 / peso propio (D∪I′) | costo vs T |")
        w("|---|---|---|---|---|---|---|---|---|")
        for b in BRAZOS:
            g = lambda f: " / ".join(str(f(cs[s][b])) for s in SEMILLAS)  # noqa: E731
            w("| %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
                b, g(lambda x: x["M1"]), g(lambda x: x["M2"]["orden_relativo_conservado"]),
                g(lambda x: "%d·%d·%d" % (x["M3"]["legitimas_puente"], x["M3"]["falsos_positivos_difusos"],
                                          x["M3"]["violaciones_C2_ajeno"] + x["M3"]["otras_ajeno_con_texto"])),
                g(lambda x: "%d:%d·%d" % (x["K3"]["preguntas"], x["K3"]["cambian_de_puesto"], x["K3"]["faltan"])),
                g(lambda x: "%d·%d·%d·%.3f·%.2f" % (x["K4_DI1"]["tema"], x["K4_DI1"]["puente"],
                                                   x["K4_DI1"]["accidental"] + x["K4_DI1"]["ajeno"],
                                                   x["K4_DI1"]["precision_tema_puente"], x["K4_DI1"]["grado_medio"])),
                g(lambda x: "%d (%.3f)" % (x["K5_DI1"].get("pares_visibles_tema_puente", 0),
                                           x["K5_DI1"]["frac_tema_puente"] or 0)),
                g(lambda x: "%d·%d" % (x["K6"]["DI1"]["dormidos_por_H2"], x["K6"]["DI1"]["dormidos_por_peso_propio"])),
                " / ".join(str(v) for v in ev[key][b]["costo_vs_T"])))
        w("\nRegistro por ciclo (semilla 7; las otras en el JSON). Ciclos totales: %d (los de I son los últimos %d)." % (
            cs[7]["T"]["registro"]["D"]["ciclos"],
            cs[7]["T"]["registro"]["D"]["ciclos"] - (int(n) // 50 + 1)))
        w("\n| brazo | ciclos con H2 (condición) D / D∪I0 | H2 durmió en n ciclos D / D∪I0 | ciclos con media > 0,70 D / D∪I0 | H2 solo con I | 4b solo con I / solo en D | mismos ciclos, otros de D dormidos | efecto acumulado D∪I0: importancia ≠ / estado ≠ |")
        w("|---|---|---|---|---|---|---|---|")
        for b in BRAZOS:
            g = lambda f: " / ".join(str(f(cs[s][b])) for s in SEMILLAS)  # noqa: E731
            R = lambda x: x["registro"]  # noqa: E731
            w("| %s | %s | %s | %s | %s | %s | %s | %s |" % (
                b, g(lambda x: "%d/%d" % (len(R(x)["D"]["h2_condicion_ciclos"]), len(R(x)["DI0"]["h2_condicion_ciclos"]))),
                g(lambda x: "%d/%d" % (len(R(x)["D"]["h2_durmio_ciclos"]), len(R(x)["DI0"]["h2_durmio_ciclos"]))),
                g(lambda x: "%d/%d" % (len(R(x)["D"]["cond_4b_ciclos"]), len(R(x)["DI0"]["cond_4b_ciclos"]))),
                g(lambda x: len(R(x)["cruces_DI0"]["h2_solo_con_I"])),
                g(lambda x: "%d/%d" % (len(R(x)["cruces_DI0"]["4b_solo_con_I"]), len(R(x)["cruces_DI0"]["4b_solo_en_D"]))),
                g(lambda x: len(R(x)["cruces_DI0"]["h2_mismos_ciclos_otros_dormidos_D"])),
                g(lambda x: "%d/%d" % (R(x)["efecto_acumulado_D"]["DI0"]["importancia_distinta"],
                                       R(x)["efecto_acumulado_D"]["DI0"]["estado_distinto"]))))
        w("\nVeredictos de este bloque:\n")
        w("| brazo | K1 | K2 | K3 | K4 | K5 | K6 |")
        w("|---|---|---|---|---|---|---|")
        for b in BRAZOS:
            e = ev[key][b]
            w("| %s | %s | %s | %s | %s | %s | %s |" % (b, e["K1"], e["K2"], e["K3"], e["K4"], e["K5"], e["K6"]))
    if k8:
        w("\n### K8: ciclo desde DB vacía (GUIA §8.8; 80 sesiones de 5, reloj diario, 320 D + 80 I0)\n")
        w("| semilla · brazo | ciclos | dormidos H2 / peso propio | dormidos > 1 vez | K1 al final: Δestado / Δimportancia D | activos al final |")
        w("|---|---|---|---|---|---|")
        for k, v in sorted(k8.items(), key=lambda kv: (BRAZOS.index(kv[0].split("|")[1]), kv[0])):
            w("| %s | %d | %d / %d | %d | %d / %d | %d |" % (k, v["ciclos"], v["dormidos_por_H2"],
                                                         v["dormidos_por_peso_propio"],
                                                         v["recuerdos_dormidos_mas_de_una_vez"],
                                                         v["K1_cambios_estado_D"], v["K1_cambios_importancia_D"],
                                                         v["activos_final_DI0"]))
    w("\n### K7, K8, K9\n")
    w("| brazo | K7 comprimido | K7 diario | K8 | K9 |")
    w("|---|---|---|---|---|")
    for b in BRAZOS:
        f = fin[b]
        w("| %s | %s | %s | %s | %s |" % (b, f["K7_comprimido"], f["K7_diario"], f["K8"], f["K9"]))
    return "\n".join(L) + "\n"


def main():
    cfg = cargar()
    p = os.path.join(RES, "controles_y_k8.json")
    extra = json.load(open(p)) if os.path.exists(p) else {}
    ev, fin = evaluar(cfg, extra.get("k8"))
    json.dump({"bloques": ev, "finales": fin, "controles": extra.get("controles")},
              open(os.path.join(RES, "resumen.json"), "w"), ensure_ascii=False, indent=1)
    open(os.path.join(RES, "tablas.md"), "w").write(tablas(cfg, extra.get("k8"), ev, fin))
    print(open(os.path.join(RES, "tablas.md")).read())


if __name__ == "__main__":
    main()
