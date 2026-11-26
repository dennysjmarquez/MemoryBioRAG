"""Medición del protocolo H2/4b v2 (h2_propuesta/PROPUESTA_PROTOCOLO_H2.md §5–§8). SOLO laboratorio sintético.

- No toca el motor ni los tests: los brazos −H2 / −4b y el registro por ciclo existen solo en el proceso hijo,
  sobre una copia del código fuente del sueño compilada en memoria (con comprobación de marcadores únicos).
- Bases solo en /tmp, creadas desde cero con el mundo de `mundo_sintetico.py`. Nada de DB viva, snapshots,
  datos privados, UD PUD ni QA oficial.
- Reloj simulado y determinista en el hijo (time.time): +1 s por recuerdo, +Δ antes de cada sueño
  (comprimido: Δ = 60 s; diario: Δ = 86 400 s). El mundo D recorre el MISMO calendario de sueños que D∪I, con
  los turnos de I vacíos, para que la única diferencia sea el contenido de I.

Uso:  python laboratorio_h2.py todo            (corrida completa)
      H2M_SECO=1 python laboratorio_h2.py todo (prueba en seco, mundos diminutos)
"""
import contextlib
import hashlib
import io
import json
import math
import os
import shutil
import sqlite3
import subprocess
import sys
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor

AQUI = os.path.dirname(os.path.abspath(__file__))
RES = "/tmp/h2_medicion/resultados_seco" if os.environ.get("H2M_SECO") else os.path.join(AQUI, "resultados")
RAIZ = os.path.abspath(os.path.join(AQUI, "..", "..", "..", ".."))
EXP16 = os.path.abspath(os.path.join(AQUI, "..", "..", "experimento_16_protocolo_ns1_sintetico"))
E1 = os.path.abspath(os.path.join(AQUI, "..", "..", "experimento_18_consolidacion_en_el_sueno"))
for p in (RAIZ, EXP16, E1, AQUI):
    sys.path.insert(0, p)

import mundo_sintetico as ms  # noqa: E402

PY = sys.executable
TMP = "/tmp/h2_medicion"
SECO = bool(os.environ.get("H2M_SECO"))
SEMILLAS = (7, 11, 23)
TAMANOS = (100,) if SECO else (800, 2400)          # |D|; |I0| = |I1| = |D|/4  → mundos de 1000 y 3000
RELOJES = {"comprimido": 60.0, "diario": 86400.0}
BRAZOS = ("T", "-H2", "-4b", "-H2-4b")
MUNDOS = ("D", "DI0", "DI1")
CADA = 50
T0 = 1_600_000_000.0
K = 5
N_CONSULTA_REC = 20 if SECO else 240
BASE_ENV = {"BIORAG_WORDNET_ENABLED": "0", "BIORAG_NO_LOG": "1", "PYTHONHASHSEED": "18"}
TABLAS_CLAVE = ("largo_plazo", "sinapsis", "sinapsis_latentes", "largo_plazo_dimensiones")


# ------------------------------------------------------------------ texto (sin idioma, sin el motor)
def _sin_espacios(ch):
    return unicodedata.name(ch, "").startswith(("CJK UNIFIED IDEOGRAPH", "CJK COMPATIBILITY IDEOGRAPH",
                                                "HIRAGANA", "KATAKANA", "HANGUL"))


def unidades(texto):
    t = unicodedata.normalize("NFKC", texto).casefold()
    t = "".join(ch if unicodedata.category(ch)[0] in "LN" else " " for ch in t)
    out = set()
    for trozo in t.split():
        corr, tipo = "", None
        partes = []
        for ch in trozo:
            k = _sin_espacios(ch)
            if tipo is None or k == tipo:
                corr += ch
            else:
                partes.append((corr, tipo))
                corr = ch
            tipo = k
        if corr:
            partes.append((corr, tipo))
        for txt, cjk in partes:
            if cjk and len(txt) >= 2:
                out |= {txt[i:i + 2] for i in range(len(txt) - 1)}
            else:
                out.add(txt)
    return out


def _es_hira(ch):
    return unicodedata.name(ch, "").startswith("HIRAGANA")


def clase_texto(uq, ui):
    """C0 / C1 / C2 de un recuerdo (unidades ui) frente a una consulta (unidades uq) — §5.1."""
    if uq & ui:
        return "C0"
    cq = {ch for u in uq for ch in u if _sin_espacios(ch) and not _es_hira(ch)}
    if cq and cq & {ch for u in ui for ch in u}:
        return "C1"
    for u in uq:
        if len(u) >= 4 and not any(_sin_espacios(c) for c in u):
            m = max(4, math.ceil(0.7 * len(u)))
            if any(len(w) >= m and w[:m] == u[:m] for w in ui):
                return "C1"
    return "C2"


def coinciden(ua, ub):
    return clase_texto(ua, ub) != "C2" or clase_texto(ub, ua) != "C2"


# ------------------------------------------------------------------ hijo: reloj, brazos, registro
class Reloj:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t


REG = []


def preparar_hijo(brazo, instrumentar, t_inicial):
    reloj = Reloj(t_inicial)
    time.time = reloj                       # antes de importar el motor
    import core.memory.consolidation as cons
    import inspect
    src = inspect.getsource(cons.ciclo_sueno_consolidacion)

    def reemplazar(viejo, nuevo):
        nonlocal src
        assert src.count(viejo) == 1, "marcador no único en el sueño: %r" % viejo
        src = src.replace(viejo, nuevo)

    if instrumentar:
        reemplazar("    energia_total = self.cursor.fetchone()[0] or 0.0\n",
                   "    energia_total = self.cursor.fetchone()[0] or 0.0\n"
                   "    _LAB_REG('h2', n_activos, energia_total, limite_energia)\n")
        reemplazar("    # 4b. Escalado Sináptico Homeostático",
                   "    _LAB_REG('h2_fin', sorted(n[0] for n in nodos_a_dormir), sorted(nodos_dormidos_ltd))\n"
                   "    # 4b. Escalado Sináptico Homeostático")
        reemplazar("    peso_medio_activo = self.cursor.fetchone()[0] or 0.0\n",
                   "    peso_medio_activo = self.cursor.fetchone()[0] or 0.0\n"
                   "    _LAB_REG('4b', peso_medio_activo)\n")
    if brazo in ("-H2", "-H2-4b"):
        reemplazar("if energia_total > limite_energia:", "if False:  # BRAZO −H2 (laboratorio)")
    if brazo in ("-4b", "-H2-4b"):
        reemplazar("if peso_medio_activo > 0.70:", "if False:  # BRAZO −4b (laboratorio)")
    cons._LAB_REG = lambda *a: REG.append(list(a))
    if instrumentar or brazo != "T":
        ns = {}
        exec(compile(src, cons.__file__ + "#lab_h2", "exec"), cons.__dict__, ns)
        cons.ciclo_sueno_consolidacion = ns["ciclo_sueno_consolidacion"]
    return reloj


def _inmunes_activos(cer):
    return cer.cursor.execute(
        "SELECT COUNT(*) FROM largo_plazo WHERE estado='activo' AND NOT ((prioridad IS NULL OR prioridad NOT IN (0,1)) "
        "AND COALESCE(valencia_somatica,0.0) < 0.80 AND (categoria IS NULL OR categoria NOT IN "
        "(SELECT id FROM categories WHERE name IN ('Principle','Protocol'))))").fetchone()[0]


def hijo_construir(semilla, n_D, mundo, brazo, reloj_nombre, ruta, salida, instrumentar="1", k8="0"):
    n_D, instrumentar, k8 = int(n_D), instrumentar == "1", k8 == "1"
    assert ruta.startswith("/tmp/")
    reloj = preparar_hijo(brazo, instrumentar, T0)
    import construir as c16
    m = ms.generar(int(semilla), n_D)
    D = [r for r in m["recuerdos"] if r["conj"] == "D"]
    I = [r for r in m["recuerdos"] if r["conj"] == ("I1" if mundo == "DI1" else "I0")]
    for ext in ("", "-wal", "-shm"):
        if os.path.exists(ruta + ext):
            os.remove(ruta + ext)
    cer = c16.abrir(ruta)
    ciclos, t_sueno = [], 0.0
    delta = RELOJES[reloj_nombre]

    def dormir(fase, nuevos):
        nonlocal t_sueno
        reloj.t += delta
        REG.append(["ciclo", len(ciclos), fase, nuevos, _inmunes_activos(cer)])
        t = time.perf_counter()
        c16.dormir(cer)
        t_sueno += time.perf_counter() - t
        ciclos.append(fase)

    def guardar(r):
        with contextlib.redirect_stdout(io.StringIO()):
            c16.guardar(cer, {"concepto": r["concepto"], "contenido": r["contenido"], "syn": "", "cat": "General",
                              "dims": {}, "sk": ""})

    if k8:   # GUIA §8.8: sesiones de 5 recuerdos, sueño tras cada sesión; cada 5.ª sesión es de I
        sesiones, iD, iI = [], 0, 0
        while iD < len(D) or iI < len(I):
            if len(sesiones) % 5 == 4 and iI < len(I):
                sesiones.append(("I", I[iI:iI + 5]))
                iI += 5
            else:
                sesiones.append(("D", D[iD:iD + 5]))
                iD += 5
        for fase, lote in sesiones:
            for r in lote:
                reloj.t += 1
                if fase == "D" or mundo != "D":
                    guardar(r)
            dormir(fase, len(lote) if (fase == "D" or mundo != "D") else 0)
    else:
        for fase, lote in (("D", D), ("I", I)):
            nuevos = 0
            for k, r in enumerate(lote, 1):
                reloj.t += 1
                if fase == "D" or mundo != "D":
                    guardar(r)
                    nuevos += 1
                if k % CADA == 0:
                    dormir(fase, nuevos)
                    nuevos = 0
            dormir(fase, nuevos)
    with contextlib.redirect_stdout(io.StringIO()):
        cer.conn.commit()
        cer.cerrar_sistema()
    con = sqlite3.connect(ruta)
    con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    con.close()
    json.dump({"registro": REG, "t_sueno": t_sueno, "reloj_final": reloj.t, "n_ciclos": len(ciclos),
               "sha_tablas": sha_tablas(ruta)}, open(salida, "w"), ensure_ascii=False)


def sha_tablas(ruta):
    con = sqlite3.connect("file:%s?mode=ro" % ruta, uri=True)
    out = sha_con(con)
    con.close()
    return out


def sha_con(con):
    out = {}
    for t in TABLAS_CLAVE:
        h = hashlib.sha256()
        for row in sorted(con.execute("SELECT * FROM %s" % t).fetchall(), key=repr):
            h.update(repr(row).encode())
        out[t] = h.hexdigest()[:16]
    return out


def hijo_medir(ruta, consultas_json, salida, reloj_final, orden="directo"):
    """Top-k del camino normal del agente (profundidad 'activos', con peso) y canal 2, sobre una copia.
    Cada consulta parte del mismo estado: tras cada búsqueda se restaura la copia (las búsquedas escriben)."""
    preparar_hijo("T", False, float(reloj_final))
    d = os.path.join(os.path.dirname(ruta), "vista_" + os.path.basename(ruta))
    shutil.copyfile(ruta, d)
    from core.memory_store import SQLiteMemoryBioRAG
    with contextlib.redirect_stdout(io.StringIO()):
        cer = SQLiteMemoryBioRAG(db_path=d)
    cer.conn.commit()
    pristina = sqlite3.connect(":memory:")
    cer.conn.backup(pristina)
    qs = json.load(open(consultas_json))
    if orden == "inverso":
        qs = qs[::-1]
    top = {}
    for q in qs:
        with contextlib.redirect_stdout(io.StringIO()):
            res, _ = cer.buscar_por_frase(q["q"], profundidad="activos", limite=10, context_window=0)
        top[q["id"]] = [r[0] for r in (res or [])][:10]
        cer.conn.commit()
        pristina.backup(cer.conn)
    restaurada = sha_con(cer.conn) == sha_con(pristina)     # cada consulta partió del mismo estado
    estado = {c: [e, p] for c, e, p in cer.cursor.execute("SELECT concepto, estado, peso_sinaptico FROM largo_plazo")}
    vec = {}
    for n in sorted(estado):
        completa = cer.obtener_asociaciones_enriquecidas([n], top_vecinos=10 ** 6).get(n, [])
        visibles = cer.obtener_asociaciones_enriquecidas([n]).get(n, [])
        vec[n] = {"lista": [a["concepto"] for a in completa], "visibles": [a["concepto"] for a in visibles]}
    aristas = [list(r) for r in cer.cursor.execute("SELECT origen, destino, tipo, peso FROM sinapsis")]
    with contextlib.redirect_stdout(io.StringIO()):
        cer.cerrar_sistema()
    os.remove(d)
    json.dump({"top": top, "estado": estado, "vecinos": vec, "aristas": aristas, "copia_restaurada": restaurada},
              open(salida, "w"), ensure_ascii=False)


# ------------------------------------------------------------------ padre
def _run(args):
    e = dict(os.environ)
    # HOME propio y nuevo por proceso hijo: ningún estado en disco (p. ej. el de la hormiguita) se comparte
    e["HOME"] = os.path.join(TMP, "home", hashlib.sha256(repr(args).encode()).hexdigest()[:16])
    e.update(BASE_ENV)
    shutil.rmtree(e["HOME"], ignore_errors=True)
    os.makedirs(e["HOME"])
    p = subprocess.run([PY, os.path.abspath(__file__)] + [str(a) for a in args], env=e, cwd=AQUI,
                       capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError("falló %s:\n%s" % (args, p.stderr[-4000:]))


def consultas(m):
    """2 y 3 palabras del tema de recuerdos de D (muestra fija por escritura). Sin palabras función."""
    import random
    rng = random.Random("consultas|%d" % m["semilla"])
    D = [r for r in m["recuerdos"] if r["conj"] == "D" and len(r["palabras_tema"]) >= 3]
    out = []
    for e in ms.ESCRITURAS:
        cand = [r for r in D if r["esc"] == e]
        rng.shuffle(cand)
        for r in cand[:N_CONSULTA_REC // 4]:
            for n in (2, 3):
                ws = rng.sample(r["palabras_tema"], n)
                q = ("".join(ws) if e in ms.SIN_ESPACIOS else " ".join(ws))
                out.append({"id": "%s|%d" % (r["concepto"], n), "x": r["concepto"].lower(), "q": q, "esc": e})
    return out


def un_brazo(args):
    semilla, n_D, reloj_nombre, brazo = args
    d = os.path.join(TMP, "s%d_n%d_%s" % (semilla, n_D, reloj_nombre), brazo.replace("-", "m"))
    os.makedirs(d, exist_ok=True)
    pj = os.path.join(TMP, "s%d_n%d_%s" % (semilla, n_D, reloj_nombre), "consultas.json")
    out = {}
    for mundo in MUNDOS:
        ruta = os.path.join(d, mundo + ".db")
        rc, rm = os.path.join(d, mundo + "_reg.json"), os.path.join(d, mundo + "_med.json")
        if not (os.path.exists(rc) and os.path.exists(rm)):
            _run(["construir", semilla, n_D, mundo, brazo, reloj_nombre, ruta, rc])
            reg = json.load(open(rc))
            _run(["medir", ruta, pj, rm, reg["reloj_final"]])
            os.remove(ruta)
        out[mundo] = {"reg": json.load(open(rc)), "med": json.load(open(rm))}
    return brazo, out


# ------------------------------------------------------------------ análisis
def ciclos(reg):
    """Registro por ciclo: n_activos, energía, límite, H2 (se habría disparado / durmió a quién), media, 4b."""
    out, cur = [], None
    for ev in reg:
        if ev[0] == "ciclo":
            cur = {"i": ev[1], "fase": ev[2], "nuevos": ev[3], "inmunes_activos": ev[4]}
            out.append(cur)
        elif ev[0] == "h2":
            cur.update(n_activos=ev[1], energia=round(ev[2], 4), limite=ev[3], h2_condicion=ev[2] > ev[3])
        elif ev[0] == "h2_fin":
            cur.update(h2_dormidos=ev[1], ltd_dormidos=ev[2])
        elif ev[0] == "4b":
            cur.update(media_4b=round(ev[1], 4), cond_4b=ev[1] > 0.70)
    return out


def analizar_config(semilla, n_D, reloj_nombre, res, m):
    idx = {r["concepto"].lower(): r for r in m["recuerdos"]}
    U = {c: unidades(r["contenido"]) for c, r in idx.items()}
    midx = {"puentes": {}}
    for p in m["puentes"]:
        midx["puentes"].setdefault(tuple(p["temas"]), []).append(p["entidad"])
    texto = lambda a, b: coinciden(U[a["concepto"].lower()], U[b["concepto"].lower()])  # noqa: E731
    verdad = lambda a, b: ms.verdad_par(midx, idx[a], idx[b], texto)  # noqa: E731
    en_D = {c for c, r in idx.items() if r["conj"] == "D"}
    qs = consultas(m)
    uq = {q["id"]: unidades(q["q"]) for q in qs}
    out = {}
    for brazo in BRAZOS:
        R = res[brazo]
        tD, tI0, tI1 = (R[w]["med"]["top"] for w in MUNDOS)
        eD, eI0, eI1 = (R[w]["med"]["estado"] for w in MUNDOS)
        a = {"brazo": brazo}
        # --- K1 / S1 con I0 (verdaderamente irrelevante)
        clases_I0 = {}
        for q in qs:
            for c in tI0[q["id"]][:K]:
                if c not in en_D:
                    clases_I0[clase_texto(uq[q["id"]], U[c]) + "|" + verdad(q["x"], c)] = \
                        clases_I0.get(clase_texto(uq[q["id"]], U[c]) + "|" + verdad(q["x"], c), 0) + 1
        c2_ok = all(clase_texto(uq[q["id"]], U[c]) == "C2" for q in qs for c in idx
                    if idx[c]["conj"] == "I0")
        cam_estado = sorted(c for c in en_D if eD[c][0] != eI0[c][0])
        cam_peso = [c for c in en_D if eD[c][1] != eI0[c][1]]
        cam_top = sorted(q["id"] for q in qs if tD[q["id"]][:K] != tI0[q["id"]][:K])
        a["S1"] = {"cambios_estado_D": len(cam_estado), "cambios_importancia_D": len(cam_peso),
                   "suma_abs_delta_importancia_D": round(sum(abs(eD[c][1] - eI0[c][1]) for c in cam_peso), 4),
                   "consultas": len(qs), "top5_cambiados_total": len(cam_top), "_top5_cambiados": cam_top,
                   "inserciones_I0_top5": sum(clases_I0.values()), "inserciones_I0_por_clase": clases_I0,
                   "I0_todo_C2_comprobado": c2_ok}
        a["M1"] = round(1 - len(cam_top) / len(qs), 4)
        # recall del recuerdo de origen en el camino normal del agente, y consultas sin resultados
        a["recall_origen_top5"] = {w: round(sum(q["x"] in t[q["id"]][:K] for q in qs) / len(qs), 4)
                                   for w, t in (("D", tD), ("DI0", tI0), ("DI1", tI1))}
        a["recall_origen_top5_por_escritura"] = {
            w: {e: round(sum(q["x"] in t[q["id"]][:K] for q in qs if q["esc"] == e) /
                         max(1, sum(1 for q in qs if q["esc"] == e)), 4) for e in ms.ESCRITURAS}
            for w, t in (("D", tD), ("DI0", tI0))}
        a["top5_cambiados_por_escritura"] = {e: sum(1 for i in cam_top if i in {q["id"] for q in qs if q["esc"] == e})
                                             for e in ms.ESCRITURAS}
        a["consultas_sin_resultado"] = {w: sum(not t[q["id"]] for q in qs) for w, t in
                                        (("D", tD), ("DI0", tI0), ("DI1", tI1))}
        a["activos_D_final"] = {w: sum(1 for c in en_D if e[c][0] == "activo") for w, e in
                                (("D", eD), ("DI0", eI0), ("DI1", eI1))}
        a["S1"]["estado_D_identico"] = not cam_estado and not cam_peso
        # --- K3: examen de orden con I0
        vD, vI0 = R["D"]["med"]["vecinos"], R["DI0"]["med"]["vecinos"]
        preg, cambia, falta = 0, 0, 0
        for A in sorted(en_D):
            lista = [x for x in vD.get(A, {}).get("lista", []) if x in en_D]
            if len(lista) < 2:
                continue
            l2 = [x for x in vI0.get(A, {}).get("lista", []) if x in en_D]
            for B in lista:
                preg += 1
                if B not in l2:
                    falta += 1
                elif l2.index(B) != lista.index(B):
                    cambia += 1
        a["K3"] = {"preguntas": preg, "cambian_de_puesto": cambia, "faltan": falta}
        # --- M2 / M3 con I1
        m2_n, m2_ok, ins = 0, 0, {}
        for q in qs:
            top1 = tI1[q["id"]][:K]
            i1_c0 = any(idx[c]["conj"] == "I1" and clase_texto(uq[q["id"]], U[c]) == "C0" for c in idx
                        if idx[c]["conj"] == "I1" and idx[c]["esc"] == q["esc"])
            for c in top1:
                if c not in en_D:
                    k_ = clase_texto(uq[q["id"]], U[c]) + "|" + verdad(q["x"], c)
                    ins[k_] = ins.get(k_, 0) + 1
            if not i1_c0:
                m2_n += 1
                sub = [c for c in top1 if c in en_D]
                m2_ok += sub == [c for c in tD[q["id"]] if c in en_D][:len(sub)]
        a["M2"] = {"consultas_sin_I1_C0": m2_n, "orden_relativo_conservado": round(m2_ok / m2_n, 4) if m2_n else None}
        leg = sum(v for k_, v in ins.items() if k_.endswith("|puente"))
        dif = sum(v for k_, v in ins.items() if k_.endswith("|accidental"))
        vio = sum(v for k_, v in ins.items() if k_ == "C2|ajeno")
        a["M3"] = {"inserciones_I1_top5": sum(ins.values()), "por_clase": ins, "legitimas_puente": leg,
                   "falsos_positivos_difusos": dif, "violaciones_C2_ajeno": vio,
                   "otras_ajeno_con_texto": sum(ins.values()) - leg - dif - vio}
        # --- K4 aristas por verdad, K5 canal 2 visible (en D y en D∪I1)
        for w in ("D", "DI1"):
            pares = {}
            for o, de, tipo, peso in R[w]["med"]["aristas"]:
                if o in idx and de in idx and o != de:
                    pares.setdefault(tuple(sorted((o, de))), tipo)
            cnt = {"tema": 0, "puente": 0, "accidental": 0, "ajeno": 0}
            pmi = {"tema": 0, "puente": 0, "accidental": 0, "ajeno": 0}
            for (x, y), tipo in pares.items():
                v = verdad(x, y)
                cnt[v] += 1
                pmi[v] += tipo == "pmi_hebbiano"
            n_nodos = sum(1 for c in R[w]["med"]["estado"] if c in idx)
            tot = sum(cnt.values())
            vis = [(A, B) for A, v in R[w]["med"]["vecinos"].items() if A in idx for B in v["visibles"] if B in idx]
            vis_ok = sum(verdad(A, B) in ("tema", "puente") for A, B in vis)
            a["K4_" + w] = {"pares": tot, **cnt, "pmi_hebbiano_por_verdad": pmi,
                            "precision_tema_puente": round((cnt["tema"] + cnt["puente"]) / tot, 4) if tot else None,
                            "grado_medio": round(2 * tot / n_nodos, 3) if n_nodos else None}
            a["K5_" + w] = {"pares_visibles": len(vis), "pares_visibles_tema_puente": vis_ok,
                            "frac_tema_puente": round(vis_ok / len(vis), 4) if vis else None}
        # --- K6, registro por ciclo, costo
        cyc = {w: ciclos(R[w]["reg"]["registro"]) for w in MUNDOS}
        a["registro"] = {}
        for w in MUNDOS:
            c = cyc[w]
            a["registro"][w] = {
                "ciclos": len(c),
                "h2_condicion_ciclos": [x["i"] for x in c if x.get("h2_condicion")],
                "h2_durmio_ciclos": [x["i"] for x in c if x.get("h2_dormidos")],
                "h2_dormidos_total": sum(len(x.get("h2_dormidos", [])) for x in c),
                "ltd_dormidos_total": sum(len(x.get("ltd_dormidos", [])) for x in c),
                "cond_4b_ciclos": [x["i"] for x in c if x.get("cond_4b")],
                "media_4b_por_ciclo": [x.get("media_4b") for x in c],
                "n_activos_por_ciclo": [x.get("n_activos") for x in c],
                "inmunes_activos_max": max((x["inmunes_activos"] for x in c), default=0),
                "t_sueno_s": round(R[w]["reg"]["t_sueno"], 2),
                "copia_restaurada": R[w]["med"]["copia_restaurada"]}
        for w in ("DI0", "DI1"):
            cD, cW = cyc["D"], cyc[w]
            assert len(cD) == len(cW)
            a["registro"]["cruces_" + w] = {
                "h2_solo_en_D": [x["i"] for x, y in zip(cD, cW) if x.get("h2_condicion") and not y.get("h2_condicion")],
                "h2_solo_con_I": [x["i"] for x, y in zip(cD, cW) if y.get("h2_condicion") and not x.get("h2_condicion")],
                "h2_mismos_ciclos_otros_dormidos_D": [x["i"] for x, y in zip(cD, cW) if
                                                      x.get("h2_dormidos") is not None and
                                                      sorted(set(x["h2_dormidos"]) & en_D) !=
                                                      sorted(set(y.get("h2_dormidos", [])) & en_D)],
                "4b_solo_en_D": [x["i"] for x, y in zip(cD, cW) if x.get("cond_4b") and not y.get("cond_4b")],
                "4b_solo_con_I": [x["i"] for x, y in zip(cD, cW) if y.get("cond_4b") and not x.get("cond_4b")]}
        eW = eI1
        a["registro"]["efecto_acumulado_D"] = {
            "DI0": {"importancia_distinta": len(cam_peso), "estado_distinto": len(cam_estado)},
            "DI1": {"importancia_distinta": sum(1 for c in en_D if eD[c][1] != eW[c][1]),
                    "estado_distinto": sum(1 for c in en_D if eD[c][0] != eW[c][0]),
                    "suma_abs_delta": round(sum(abs(eD[c][1] - eW[c][1]) for c in en_D), 4)}}
        a["K6"] = {w: {"dormidos_por_H2": a["registro"][w]["h2_dormidos_total"],
                       "dormidos_por_peso_propio": a["registro"][w]["ltd_dormidos_total"]} for w in MUNDOS}
        nuevos = len([r for r in m["recuerdos"] if r["conj"] in ("D", "I1")])
        a["costo"] = {"t_sueno_DI1_s": a["registro"]["DI1"]["t_sueno_s"],
                      "s_por_recuerdo_nuevo": round(a["registro"]["DI1"]["t_sueno_s"] / nuevos, 5)}
        out[brazo] = a
    # atribución: cambios del top-5 que NO aparecen con −H2 −4b
    base = set(out["-H2-4b"]["S1"]["_top5_cambiados"])
    for brazo in BRAZOS:
        s = out[brazo]["S1"]
        s["top5_cambiados_atribuibles_H2_4b"] = len(set(s["_top5_cambiados"]) - base)
        s["top5_cambiados_tambien_sin_H2_4b"] = len(set(s["_top5_cambiados"]) & base)
    return out


def reanalizar(semilla, n_D, reloj_nombre):
    """Rehace el análisis desde los registros y mediciones ya guardados en /tmp (sin reconstruir nada)."""
    tag = "s%d_n%d_%s" % (semilla, n_D, reloj_nombre)
    final = os.path.join(RES, "config_%s.json" % tag)
    viejo = json.load(open(final))
    m = ms.generar(semilla, n_D)
    res = {}
    for b in BRAZOS:
        d = os.path.join(TMP, tag, b.replace("-", "m"))
        res[b] = {w: {"reg": json.load(open(os.path.join(d, w + "_reg.json"))),
                      "med": json.load(open(os.path.join(d, w + "_med.json")))} for w in MUNDOS}
    an = analizar_config(semilla, n_D, reloj_nombre, res, m)
    an["_meta"] = viejo["_meta"]
    json.dump(an, open(final, "w"), ensure_ascii=False)
    return an


def una_config(semilla, n_D, reloj_nombre):
    tag = "s%d_n%d_%s" % (semilla, n_D, reloj_nombre)
    final = os.path.join(RES, "config_%s.json" % tag)
    if os.path.exists(final):
        return json.load(open(final))
    m = ms.generar(semilla, n_D)
    os.makedirs(os.path.join(TMP, tag), exist_ok=True)
    json.dump(consultas(m), open(os.path.join(TMP, tag, "consultas.json"), "w"), ensure_ascii=False)
    t0 = time.time()
    with ThreadPoolExecutor(2) as ex:
        res = dict(ex.map(un_brazo, [(semilla, n_D, reloj_nombre, b) for b in BRAZOS]))
    an = analizar_config(semilla, n_D, reloj_nombre, res, m)
    an["_meta"] = {"semilla": semilla, "n_D": n_D, "n_I0": len([r for r in m["recuerdos"] if r["conj"] == "I0"]),
                   "n_I1": len([r for r in m["recuerdos"] if r["conj"] == "I1"]), "reloj": reloj_nombre,
                   "temas_D": len([t for t in m["temas"].values() if t["conj"] == "D"]),
                   "puentes": len(m["puentes"]), "segundos": round(time.time() - t0, 1)}
    os.makedirs(os.path.dirname(final), exist_ok=True)
    json.dump(an, open(final, "w"), ensure_ascii=False)
    return an


def controles():
    """(a) el registro no cambia la base; (b) el orden de las consultas no cambia el top-k (restauración)."""
    out = {}
    s, n, rj = 7, TAMANOS[0], "comprimido"
    d = os.path.join(TMP, "control")
    os.makedirs(d, exist_ok=True)
    m = ms.generar(s, n)
    pj = os.path.join(d, "consultas.json")
    json.dump(consultas(m), open(pj, "w"), ensure_ascii=False)

    def uno(brazo):
        r = {}
        for inst in ("1", "0"):
            ruta = os.path.join(d, "%s_%s.db" % (brazo.replace("-", "m"), inst))
            sal = ruta + ".json"
            _run(["construir", s, n, "DI1", brazo, rj, ruta, sal, inst])
            r[inst] = json.load(open(sal))
            if inst == "1" and brazo == "T":
                for orden in ("directo", "inverso"):
                    _run(["medir", ruta, pj, ruta + "." + orden, r[inst]["reloj_final"], orden])
                a, b = (json.load(open(ruta + "." + o))["top"] for o in ("directo", "inverso"))
                r["orden_indiferente"] = a == b
            os.remove(ruta)
        return brazo, {"registro_no_cambia_la_base": r["1"]["sha_tablas"] == r["0"]["sha_tablas"],
                       "sha": r["1"]["sha_tablas"], **({"orden_consultas_indiferente": r["orden_indiferente"]}
                                                       if "orden_indiferente" in r else {})}
    with ThreadPoolExecutor(2) as ex:
        out = dict(ex.map(uno, BRAZOS))
    return out


def k8():
    """GUIA §8.8: desde DB vacía, sesiones de 5, 80 sesiones (320 D + 80 I0). Sin excepciones, sin oscilación,
    y K1 al final (D frente a D∪I0)."""
    n = 40 if SECO else 320
    out = {}
    jobs = [(s, b) for s in SEMILLAS for b in BRAZOS]

    def uno(job):
        s, brazo = job
        d = os.path.join(TMP, "k8", "s%d_%s" % (s, brazo.replace("-", "m")))
        os.makedirs(d, exist_ok=True)
        r = {}
        for mundo in ("D", "DI0"):
            ruta = os.path.join(d, mundo + ".db")
            sal = ruta + ".json"
            _run(["construir", s, n, mundo, brazo, "diario", ruta, sal, "1", "1"])
            con = sqlite3.connect(ruta)
            r[mundo] = {"estado": dict(con.execute("SELECT concepto, estado FROM largo_plazo").fetchall()),
                        "peso": dict(con.execute("SELECT concepto, peso_sinaptico FROM largo_plazo").fetchall()),
                        "reg": json.load(open(sal))}
            con.close()
            os.remove(ruta)
        cyc = ciclos(r["DI0"]["reg"]["registro"])
        dorm = {}
        for x in cyc:
            for c in x.get("h2_dormidos", []) + x.get("ltd_dormidos", []):
                dorm[c] = dorm.get(c, 0) + 1
        enD = [c for c in r["D"]["estado"]]
        return "s%d|%s" % (s, brazo), {
            "ciclos": len(cyc), "sin_excepciones": True,
            "recuerdos_dormidos_mas_de_una_vez": sum(1 for v in dorm.values() if v > 1),
            "dormidos_por_H2": sum(len(x.get("h2_dormidos", [])) for x in cyc),
            "dormidos_por_peso_propio": sum(len(x.get("ltd_dormidos", [])) for x in cyc),
            "K1_cambios_estado_D": sum(1 for c in enD if r["D"]["estado"][c] != r["DI0"]["estado"][c]),
            "K1_cambios_importancia_D": sum(1 for c in enD if r["D"]["peso"][c] != r["DI0"]["peso"][c]),
            "activos_final_DI0": sum(1 for v in r["DI0"]["estado"].values() if v == "activo")}
    with ThreadPoolExecutor(2) as ex:
        out = dict(ex.map(uno, jobs))
    return out


def main():
    os.makedirs(RES, exist_ok=True)
    t0 = time.time()
    resumen = {"controles": controles()}
    print("controles", json.dumps(resumen["controles"])[:400], flush=True)
    resumen["k8"] = k8()
    print("k8 listo", round(time.time() - t0), flush=True)
    for n in TAMANOS:
        for rj in RELOJES:
            for s in SEMILLAS:
                una_config(s, n, rj)
                print("config", s, n, rj, round(time.time() - t0), flush=True)
    resumen["segundos"] = round(time.time() - t0, 1)
    json.dump(resumen, open(os.path.join(RES, "controles_y_k8.json"), "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "construir":
        hijo_construir(*sys.argv[2:])
    elif cmd == "medir":
        hijo_medir(*sys.argv[2:])
    elif cmd == "todo":
        main()
    elif cmd == "reanalizar":
        for f in sorted(os.listdir(RES)):
            if f.startswith("config_"):
                s_, n_, r_ = f[len("config_"):-5].split("_")
                reanalizar(int(s_[1:]), int(n_[1:]), r_)
                print("reanalizado", f, flush=True)
    elif cmd == "config":
        print(json.dumps(una_config(int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]))[:2000])
