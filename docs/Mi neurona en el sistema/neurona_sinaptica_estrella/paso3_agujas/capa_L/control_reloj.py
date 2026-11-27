"""Control de reloj para §5.2 (27-11): ¿las aristas D–D que faltan en D∪I a |D| = 2400 las quita el contenido de I
o el paso del tiempo (13 días y 13 sueños más)?

Mundo Dt = D + el mismo avance de reloj y los mismos sueños que D∪I, **sin escribir ningún documento de I**.
Si D→Dt pierde exactamente lo mismo que D→D∪I0 (mismas cuentas por tipo), la causa es el tiempo y no el contenido.
Uso: python control_reloj.py [n_D]  → resultados/control_reloj_n{n}.json (+ commit/push)
"""
import json
import os
import shutil
import sys
import time

import laboratorio_capa_L as L


def una(semilla, n_D):
    d = os.path.join(L.TMP, "reloj_s%d_n%d" % (semilla, n_D))
    os.makedirs(d, exist_ok=True)
    m = L.mundo_completo(semilla, n_D)
    en_D = sorted(r["concepto"].lower() for r in m["recuerdos"] if r["conj"] == "D")
    cj = os.path.join(d, "conceptos_D.json")
    json.dump(en_D, open(cj, "w"))
    med, info = {}, {}
    for w in ("D", "Dt"):
        ruta = os.path.join(d, w + ".db")
        if not os.path.exists(ruta + ".info.json"):
            L._run(["construir", semilla, n_D, w, ruta, ruta + ".info.json"])
        if not os.path.exists(ruta + ".med.json"):
            L._run(["medir", ruta, cj, ruta + ".med.json", "0"], L.ENV_MEDIR)
        med[w] = json.load(open(ruta + ".med.json"))
        info[w] = json.load(open(ruta + ".info.json"))
    hc = json.load(open(os.path.join(L.RAIZ, "db", "hebbian_clusters.json")))
    A = {w: L.Agujas(med[w], hc["idf"], hc["dim_names"]) for w in med}
    sD = set(en_D)
    por = {}
    claves = {k for w in A for k in A[w].tipos if set(k) <= sD}
    for k in claves:
        tD, tW = A["D"].tipos.get(k, set()), A["Dt"].tipos.get(k, set())
        for t in tD | tW:
            x = por.setdefault(t, {"en_D": 0, "en_W": 0, "en_ambos": 0})
            x["en_D"] += t in tD
            x["en_W"] += t in tW
            x["en_ambos"] += (t in tD and t in tW)
    for t, x in por.items():
        x["identicas_frac"] = round(x["en_ambos"] / (x["en_D"] + x["en_W"] - x["en_ambos"]), 6)
    fp = os.path.join(L.RES, "config_s%d_n%d.json" % (semilla, n_D))
    previo = json.load(open(fp)) if os.path.exists(fp) else {"tipo_invariancia": {"DI0": None, "DI1": None}}
    out = {"semilla": semilla, "n_D": n_D, "info": info, "D_vs_Dt": por,
           "D_vs_DI0_previo": previo["tipo_invariancia"]["DI0"],
           "D_vs_DI1_previo": previo["tipo_invariancia"]["DI1"]}
    shutil.rmtree(d, ignore_errors=True)
    return out


def main():
    n_D = int(sys.argv[1]) if len(sys.argv) > 1 else 2400
    t0 = time.time()
    res = []
    for s in L.SEMILLAS:
        res.append(una(s, n_D))
        print("reloj", s, n_D, round(time.time() - t0), flush=True)
    sal = os.path.join(L.RES, "control_reloj_n%d.json" % n_D)
    os.makedirs(L.RES, exist_ok=True)
    json.dump(res, open(sal, "w"), ensure_ascii=False, indent=1)
    L.subir([sal], "Paso 3 capa L: control de reloj n=%d (sintético)" % n_D)
    print("FIN", round(time.time() - t0), flush=True)


if __name__ == "__main__":
    main()
