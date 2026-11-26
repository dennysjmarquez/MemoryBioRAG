"""R-E2: qué señal del score cambia entre D y D∪I0 (RESULTADOS_RESIDUAL.md §5). SOLO laboratorio sintético.

Instrumentación SOLO en el proceso hijo, sobre una copia de una base sintética de /tmp: envoltorios que registran
y devuelven el resultado original sin tocarlo. No modifica el motor, los tests ni `laboratorio_h2.py`.
  - `cer._calcular_score_hibrido` (atributo de la instancia): kwargs de cada candidato y score.
  - `core.ppmi_hybrid_search.score_candidato`: norma de vq, s_ppmi, s_idf, s_hop y total.
  - `cer._enriquecer_con_adn`: orden de los conceptos antes y después.
Control: el top-k instrumentado tiene que coincidir con el de la medición sin instrumentar (R-E1).

Uso:  python residual_re2.py medir2 BASE CONSULTAS SALIDA RELOJ_FINAL       (hijo)
      python residual_re2.py todo  D.db DI0.db REG_D.json SEMILLA N_D       (orquesta y analiza)
"""
import contextlib
import hashlib
import io
import json
import os
import shutil
import sqlite3
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import laboratorio_h2 as lab  # noqa: E402
import mundo_sintetico as ms  # noqa: E402

TMP = "/tmp/h2_re2"


def hijo_medir2(ruta, consultas_json, salida, reloj_final):
    lab.preparar_hijo("T", False, float(reloj_final))
    os.makedirs(TMP, exist_ok=True)
    d = os.path.join(TMP, "vista_" + hashlib.sha256(ruta.encode()).hexdigest()[:8] + ".db")
    shutil.copyfile(ruta, d)
    from core.memory_store import SQLiteMemoryBioRAG
    import core.ppmi_hybrid_search as phs
    with contextlib.redirect_stdout(io.StringIO()):
        cer = SQLiteMemoryBioRAG(db_path=d)
    cer.conn.commit()
    pristina = sqlite3.connect(":memory:")
    cer.conn.backup(pristina)
    actual = {"q": None}
    reg_score, reg_ppmi, reg_adn = {}, {}, {}

    orig_score = cer._calcular_score_hibrido

    def score_env(**kw):
        s = orig_score(**kw)
        c = actual.get("concepto")
        reg_score.setdefault(actual["q"], []).append({"c": c, "kw": {k: (round(v, 9) if isinstance(v, float) else v)
                                                                    for k, v in kw.items()}, "s": round(s, 9)})
        return s

    orig_cand = phs.score_candidato

    def cand_env(idx, vq, q_toks_unique, es_corta, c_name, pool_set):
        tot, det = orig_cand(idx, vq, q_toks_unique, es_corta, c_name, pool_set)
        import numpy as np
        reg_ppmi.setdefault(actual["q"], {})[c_name] = {
            "vq_norma": round(float(np.linalg.norm(vq)), 9), "es_corta": es_corta, "total": round(tot, 9),
            "s_ppmi": round(det["s_ppmi"], 9), "s_idf": round(det["s_idf"], 9), "s_hop": round(det["s_hop"], 9),
            "n_pool": len(pool_set)}
        actual["concepto"] = c_name
        return tot, det

    orig_adn = cer._enriquecer_con_adn

    def adn_env(query, resultados_base, limite=None):
        antes = [r[0] for r in (resultados_base or [])]
        out = orig_adn(query, resultados_base, limite)
        despues = [r[0] for r in (out[0] or [])] if isinstance(out, tuple) else None
        reg_adn[actual["q"]] = {"antes": antes, "despues": despues, "cambia": antes != despues}
        return out

    import core.memory.evidence_convergence as ev
    import core.memory.neurona as neu
    reg_etapas = {}
    fila = lambda p: [(r[0], round(float(r[4]), 9)) for r in (p or [])]  # noqa: E731

    orig_conv = ev.rerank_con_evidencia_multicampo

    def conv_env(pagina, *a, **k):
        out = orig_conv(pagina, *a, **k)
        reg_etapas.setdefault(actual["q"], {})["conv"] = {"antes": fila(pagina), "despues": fila(out[0])}
        return out

    orig_neu = neu.reordenar

    def neu_env(self_, frase, pagina, v):
        out = orig_neu(self_, frase, pagina, v)
        reg_etapas.setdefault(actual["q"], {})["neurona"] = {"antes": fila(pagina), "despues": fila(out)}
        return out

    ev.rerank_con_evidencia_multicampo = conv_env
    neu.reordenar = neu_env
    cer._calcular_score_hibrido = score_env
    cer._enriquecer_con_adn = adn_env
    phs.score_candidato = cand_env

    qs = json.load(open(consultas_json))
    top = {}
    for q in qs:
        actual["q"] = q["id"]
        actual["concepto"] = None
        with contextlib.redirect_stdout(io.StringIO()):
            res, _ = cer.buscar_por_frase(q["q"], profundidad="activos", limite=10, context_window=0)
        top[q["id"]] = [r[0] for r in (res or [])][:10]
        cer.conn.commit()
        pristina.backup(cer.conn)
    try:
        est = neu.estado(cer)
        camp = est.campeon
        info_neu = {"campeon": camp is not None,
                    "campeon_sha": hashlib.sha256(repr(camp).encode()).hexdigest()[:16] if camp is not None else None}
    except Exception as e:
        info_neu = {"error": repr(e)}
    info = {"neurona": info_neu, "n_docs_ppmi": getattr(cer._ppmi_index, "n_docs", None),
            "neocortex": cer.neocortex is not None, "adn_engine": cer.adn_engine is not None,
            "adn_indice_listo": bool(cer.adn_engine is not None and getattr(cer.adn_engine, "indice_listo", False))}
    with contextlib.redirect_stdout(io.StringIO()):
        cer.cerrar_sistema()
    os.remove(d)
    json.dump({"top": top, "etapas": reg_etapas, "score": reg_score, "ppmi": reg_ppmi, "adn": reg_adn, "info": info}, open(salida, "w"),
              ensure_ascii=False)


def _run(args):
    e = dict(os.environ)
    e["HOME"] = os.path.join(TMP, "home", hashlib.sha256(repr(args).encode()).hexdigest()[:16])
    e.update(lab.BASE_ENV)
    shutil.rmtree(e["HOME"], ignore_errors=True)
    os.makedirs(e["HOME"])
    p = subprocess.run([lab.PY, os.path.abspath(__file__)] + [str(a) for a in args], env=e, cwd=AQUI,
                       capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError("falló %s:\n%s" % (args, p.stderr[-4000:]))


def todo(rD, rI, reg_json, semilla, n_D):
    semilla, n_D = int(semilla), int(n_D)
    os.makedirs(TMP, exist_ok=True)
    m = ms.generar(semilla, n_D)
    qs = lab.consultas(m)
    pj = os.path.join(TMP, "consultas.json")
    json.dump(qs, open(pj, "w"), ensure_ascii=False)
    reloj = json.load(open(reg_json))["reloj_final"]
    sal = {w: os.path.join(TMP, w + "_re2.json") for w in ("D", "DI0")}
    for w, r in (("D", rD), ("DI0", rI)):
        _run(["medir2", r, pj, sal[w], reloj])
    A, B = (json.load(open(sal[w])) for w in ("D", "DI0"))
    previo = json.load(open(os.path.join(AQUI, "resultados_residual", "residual_s%d_n%d.json" % (semilla, n_D))))
    cam_prev = set(previo["celdas"]["corte=medir|ppmi=0.15"]["_top5_cambiados"])
    cam = sorted(q["id"] for q in qs if A["top"][q["id"]][:lab.K] != B["top"][q["id"]][:lab.K])
    en_D = {r["concepto"].lower() for r in m["recuerdos"] if r["conj"] == "D"}
    out = {"control_reproduce_R-E1": set(cam) == cam_prev, "cambiadas": len(cam), "info": {"D": A["info"], "DI0": B["info"]}}
    claves_dif, por_clave_q, ppmi_dif, ppmi_comp, adn_cambia, ejemplos = {}, {}, 0, {}, 0, []
    for qid in cam:
        sa = {x["c"]: x for x in A["score"].get(qid, [])}
        sb = {x["c"]: x for x in B["score"].get(qid, [])}
        difs_q = set()
        for c in set(sa) & set(sb):
            if c is None or c.lower() not in en_D:
                continue
            for k in sa[c]["kw"]:
                if sa[c]["kw"][k] != sb[c]["kw"].get(k):
                    difs_q.add(k)
                    claves_dif[k] = claves_dif.get(k, 0) + 1
        for k in difs_q:
            por_clave_q[k] = por_clave_q.get(k, 0) + 1
        pa, pb = A["ppmi"].get(qid, {}), B["ppmi"].get(qid, {})
        dif_q = False
        for c in set(pa) & set(pb):
            for k in ("s_ppmi", "s_idf", "s_hop", "total", "vq_norma", "n_pool"):
                if pa[c][k] != pb[c][k]:
                    ppmi_comp[k] = ppmi_comp.get(k, 0) + 1
                    dif_q = True
        ppmi_dif += dif_q
        adn_cambia += bool(A["adn"].get(qid, {}).get("cambia") or B["adn"].get(qid, {}).get("cambia"))
        if len(ejemplos) < 3:
            c0 = next((c for c in sorted(set(pa) & set(pb)) if pa[c] != pb[c]), None)
            ejemplos.append({"consulta": qid, "claves_kw_distintas": sorted(difs_q),
                             "vq_norma": (pa.get(c0, {}).get("vq_norma"), pb.get(c0, {}).get("vq_norma")) if c0 else None,
                             "ppmi_D": pa.get(c0), "ppmi_DI0": pb.get(c0), "candidatos_pool_D": len(sa),
                             "candidatos_pool_DI0": len(sb)})
    out["kwargs_distintos_en_candidatos_D_por_clave"] = claves_dif
    out["consultas_cambiadas_con_esa_clave_distinta"] = por_clave_q
    out["consultas_cambiadas_con_score_candidato_distinto"] = ppmi_dif
    out["score_candidato_componentes_distintos"] = ppmi_comp
    out["consultas_cambiadas_donde_adn_reordena"] = adn_cambia
    out["vq_cero_en_cambiadas"] = sum(1 for qid in cam if any(v["vq_norma"] == 0 for v in A["ppmi"].get(qid, {}).values()))
    # control negativo: consultas NO cambiadas con score_candidato distinto
    no_cam = [q["id"] for q in qs if q["id"] not in set(cam)]
    out["consultas_no_cambiadas_con_score_candidato_distinto"] = sum(
        1 for qid in no_cam if any(A["ppmi"].get(qid, {}).get(c) != B["ppmi"].get(qid, {}).get(c)
                                   for c in set(A["ppmi"].get(qid, {})) & set(B["ppmi"].get(qid, {}))))
    out["ejemplos"] = ejemplos
    # etapa en la que D y D∪I0 se separan por primera vez (orden de los conceptos)
    etapa = {}
    for qid in cam:
        ea, eb = A["etapas"].get(qid, {}), B["etapas"].get(qid, {})
        nom = lambda x: [c for c, _ in x]  # noqa: E731
        if "conv" in ea and "conv" in eb and nom(ea["conv"]["antes"])[:lab.K] != nom(eb["conv"]["antes"])[:lab.K]:
            e = "antes_de_convergencia (ranking hibrido)"
        elif "conv" in ea and "conv" in eb and nom(ea["conv"]["despues"])[:lab.K] != nom(eb["conv"]["despues"])[:lab.K]:
            e = "convergencia_multicampo"
        elif "neurona" in ea and "neurona" in eb and nom(ea["neurona"]["despues"])[:lab.K] != nom(eb["neurona"]["despues"])[:lab.K]:
            e = "neurona_1"
        else:
            e = "despues_de_neurona / sin registro"
        etapa[e] = etapa.get(e, 0) + 1
    out["etapa_de_separacion"] = etapa
    out["neurona_reordena_en_D_DI0"] = [sum(1 for qid, e in X["etapas"].items() if "neurona" in e and
                                            e["neurona"]["antes"] != e["neurona"]["despues"]) for X in (A, B)]
    dst = os.path.join(AQUI, "resultados_residual", "re2_s%d_n%d.json" % (semilla, n_D))
    json.dump(out, open(dst, "w"), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1)[:6000])


if __name__ == "__main__":
    if sys.argv[1] == "medir2":
        hijo_medir2(*sys.argv[2:])
    elif sys.argv[1] == "todo":
        todo(*sys.argv[2:])
