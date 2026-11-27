"""Ciclo 2 de H2/4b (h2_propuesta/PROPUESTA_PROTOCOLO_CICLO2.md, rev. 2 + ajuste de control de R-E2).
SOLO laboratorio sintético. Aprobado el 26-11.

- No toca el motor, los tests ni `h2_medicion/laboratorio_h2.py`: reutiliza sus funciones. Las variantes de H2 y
  4b existen solo en el proceso hijo, sobre una copia del código fuente del sueño compilada en memoria (con
  comprobación de marcadores únicos).
- Brazos: T (H2 y 4b de hoy), −H2−4b, H2loc (H2-local + 4b de hoy), 4bp (H2 de hoy + 4b-propio) y H2loc+4bp.
    H2-local: por cada recuerdo activo r con al menos un vecino activo (|N(r)∪{r}| ≥ 2), si la energía de
      N(r)∪{r} supera 0,8·|N(r)∪{r}|, se duerme el más débil NO inmune de esa vecindad (desempate: acceso más
      antiguo y luego nombre). Todas las decisiones se toman sobre la foto anterior al bloque y se aplican juntas;
      mismo efecto que H2 de hoy sobre el dormido (estado 'dormido', peso ×0,9 con piso 0,05).
    4b-propio: cada recuerdo activo no inmune con importancia > 0,70 se multiplica por 0,98 (redondeo a 2
      decimales); decide solo su propio valor, sin media global.
- Configuraciones de la Neurona 1: «real» (activa) y «ctl» (BIORAG_NEURONA=0 durante TODA la corrida).
  PPMI 0,15 en las dos.
- El corte de la cohorte de búsqueda congelada se fija tras D: el motor se cierra y reabre una vez justo después
  de la fase D, en los tres mundos (D, D∪I0, D∪I1). K8 (desde DB vacía, sesiones mezcladas) no se reabre: mide
  estado, no top-k.
- Por mundo se registra el estado de la Neurona 1 (campeón, ascensos, reinicios, huella), leído en modo solo
  lectura de la base construida.
- Bases solo en /tmp. Sin DB viva, snapshots, datos privados, UD PUD ni QA oficial.
- Cada configuración terminada se guarda en `resultados/` y se sube (commit + push a la rama de la sesión), para
  no perderla si el entorno se reinicia; al relanzar, lo terminado se salta.

Uso:  python laboratorio_ciclo2.py todo              (corrida completa)
      H2M_SECO=1 python laboratorio_ciclo2.py todo   (prueba en seco)
"""
import contextlib
import hashlib
import io
import json
import os
import random
import shutil
import sqlite3
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

AQUI = os.path.dirname(os.path.abspath(__file__))
MED = os.path.abspath(os.path.join(AQUI, "..", "h2_medicion"))
sys.path.insert(0, MED)
import laboratorio_h2 as lab  # noqa: E402
import mundo_sintetico as ms  # noqa: E402

SECO = lab.SECO
TMP = "/tmp/h2_ciclo2"
RES = os.path.join(TMP, "resultados_seco") if SECO else os.path.join(AQUI, "resultados")
BRAZOS = ("T", "-H2-4b", "H2loc", "4bp", "H2loc+4bp")
NEURONA = {"ctl": {"BIORAG_NEURONA": "0"}, "real": {}}
MUNDOS = lab.MUNDOS
RAMA = "arena/da3df5df-memorybiorag"
N_PUENTE_Q = 10 if SECO else 120

INMUNE_SQL = ("NOT ((prioridad IS NULL OR prioridad NOT IN (0, 1)) AND COALESCE(valencia_somatica, 0.0) < 0.80 "
              "AND (categoria IS NULL OR categoria NOT IN (SELECT id FROM categories WHERE name IN "
              "('Principle', 'Protocol'))))")

H2_LOCAL = '''
    # ── H2-local (laboratorio ciclo 2): inhibición lateral por vecindad, sobre la foto previa ──
    self.cursor.execute("SELECT concepto, peso_sinaptico, ultimo_acceso, CASE WHEN %s THEN 1 ELSE 0 END "
                        "FROM largo_plazo WHERE estado = 'activo'")
    _lab_act = {r[0]: (float(r[1] or 0.0), float(r[2] or 0.0), bool(r[3])) for r in self.cursor.fetchall()}
    _lab_vec = {c: set() for c in _lab_act}
    self.cursor.execute("SELECT origen, destino FROM sinapsis")
    for _lab_o, _lab_d in self.cursor.fetchall():
        if _lab_o in _lab_act and _lab_d in _lab_act and _lab_o != _lab_d:
            _lab_vec[_lab_o].add(_lab_d)
            _lab_vec[_lab_d].add(_lab_o)
    _lab_dormir = set()
    _lab_vecindades_en_exceso = 0
    for _lab_r in sorted(_lab_act):
        _lab_N = _lab_vec[_lab_r] | {_lab_r}
        if len(_lab_N) < 2:
            continue
        if sum(_lab_act[c][0] for c in _lab_N) > 0.8 * len(_lab_N):
            _lab_vecindades_en_exceso += 1
            _lab_cand = [c for c in _lab_N if not _lab_act[c][2]]
            if _lab_cand:
                _lab_dormir.add(min(_lab_cand, key=lambda c: (_lab_act[c][0], _lab_act[c][1], c)))
    nodos_a_dormir = [(c, _lab_act[c][0]) for c in sorted(_lab_dormir)]
    if nodos_a_dormir:
        for i in range(0, len(nodos_a_dormir), 900):
            lote = [n[0] for n in nodos_a_dormir[i:i+900]]
            placeholders = ",".join("?" for _ in lote)
            self.cursor.execute(f"UPDATE largo_plazo SET estado = 'dormido', peso_sinaptico = MAX(0.05, ROUND(peso_sinaptico * 0.9, 2)) WHERE concepto IN ({placeholders})", lote)
    nodos_inhibicion_lateral = [n[0] for n in nodos_a_dormir]
    _LAB_REG('h2loc', len(_lab_act), _lab_vecindades_en_exceso, len(nodos_a_dormir))
''' % ("(prioridad IN (0, 1)) OR COALESCE(valencia_somatica, 0.0) >= 0.80 OR (categoria IN (SELECT id FROM "
       "categories WHERE name IN ('Principle', 'Protocol')))")


# ------------------------------------------------------------------ sinónimos sintéticos (§4)
def sinonimos(m):
    """Sinónimos sintéticos en el 35 % de los recuerdos, para que nazcan `co_semantica` y `sinonimo_explicito`
    (hoy `syn = ""` en el laboratorio). Sin listas de ningún idioma: el sinónimo es una de las 2 primeras palabras
    inventadas del vocabulario del propio tema (legítimo; 2 opciones para que coincidan entre recuerdos) y, en 1 de cada 10, de otro tema de D con la misma escritura (ruido, para
    que haya sinónimos accidentales). Determinista por semilla y por recuerdo: el mismo recuerdo lleva el mismo
    sinónimo en D, D∪I0 y D∪I1."""
    temas_D = {}
    for tid, t in sorted(m["temas"].items()):
        if t["conj"] == "D":
            temas_D.setdefault(t["esc"], []).append(tid)
    out = {}
    for r in m["recuerdos"]:
        rng = random.Random("syn|%d|%s" % (m["semilla"], r["concepto"]))
        if rng.random() >= 0.35:
            continue
        tid = r["tema"]
        if rng.random() < 0.10:
            otros = [t for t in temas_D.get(r["esc"], []) if t != tid]
            if otros:
                tid = rng.choice(otros)
        out[r["concepto"]] = rng.choice(m["temas"][tid]["voc"][:2])
    return out


# ------------------------------------------------------------------ hijo: variantes del sueño
def preparar_hijo2(brazo, t_inicial):
    reloj = lab.Reloj(t_inicial)
    time.time = reloj                       # antes de importar el motor
    import core.memory.consolidation as cons
    import inspect
    src = inspect.getsource(cons.ciclo_sueno_consolidacion)

    def reemplazar(viejo, nuevo):
        nonlocal src
        assert src.count(viejo) == 1, "marcador no único en el sueño: %r" % viejo
        src = src.replace(viejo, nuevo)

    reemplazar("    energia_total = self.cursor.fetchone()[0] or 0.0\n",
               "    energia_total = self.cursor.fetchone()[0] or 0.0\n"
               "    _LAB_REG('h2', n_activos, energia_total, limite_energia)\n")
    if brazo in ("-H2-4b", "H2loc", "H2loc+4bp"):
        reemplazar("if energia_total > limite_energia:", "if False:  # H2 global apagado (laboratorio)")
    if brazo in ("H2loc", "H2loc+4bp"):
        reemplazar("    # 4b. Escalado Sináptico Homeostático", H2_LOCAL + "    # 4b. Escalado Sináptico Homeostático")
    reemplazar("    # 4b. Escalado Sináptico Homeostático",
               "    _LAB_REG('h2_fin', sorted(n[0] for n in nodos_a_dormir), sorted(nodos_dormidos_ltd))\n"
               "    # 4b. Escalado Sináptico Homeostático")
    reemplazar("    peso_medio_activo = self.cursor.fetchone()[0] or 0.0\n",
               "    peso_medio_activo = self.cursor.fetchone()[0] or 0.0\n"
               "    _LAB_REG('4b', peso_medio_activo)\n")
    if brazo == "-H2-4b":
        reemplazar("if peso_medio_activo > 0.70:", "if False:  # 4b apagado (laboratorio)")
    if brazo in ("4bp", "H2loc+4bp"):
        reemplazar("""    if peso_medio_activo > 0.70:
        self.cursor.execute(\"\"\"
            UPDATE largo_plazo
            SET peso_sinaptico = ROUND(peso_sinaptico * 0.98, 2)
            WHERE estado = 'activo'
""", """    if True:  # 4b-propio (laboratorio): decide el valor propio de cada recuerdo
        self.cursor.execute(\"\"\"
            UPDATE largo_plazo
            SET peso_sinaptico = ROUND(peso_sinaptico * 0.98, 2)
            WHERE estado = 'activo' AND peso_sinaptico > 0.70
""")
        reemplazar("    _LAB_REG('4b', peso_medio_activo)\n",
                   "    _LAB_REG('4b', peso_medio_activo)\n"
                   "    self.cursor.execute(\"SELECT COUNT(*) FROM largo_plazo WHERE estado = 'activo' AND "
                   "peso_sinaptico > 0.70 AND COALESCE(valencia_somatica, 0.0) < 0.80 AND (categoria IS NULL OR "
                   "categoria NOT IN (SELECT id FROM categories WHERE name IN ('Principle', 'Protocol')))\")\n"
                   "    _LAB_REG('4bp', self.cursor.fetchone()[0])\n")
    cons._LAB_REG = lambda *a: lab.REG.append(list(a))
    ns = {}
    exec(compile(src, cons.__file__ + "#lab_ciclo2", "exec"), cons.__dict__, ns)
    cons.ciclo_sueno_consolidacion = ns["ciclo_sueno_consolidacion"]
    return reloj


def estado_neurona(ruta):
    con = sqlite3.connect("file:%s?mode=ro" % ruta, uri=True)
    try:
        f = {c: v for c, v, _ in con.execute("SELECT clave, valor, actualizado FROM neurona_estado")}
    except sqlite3.Error:
        con.close()
        return {"tabla": False}
    con.close()
    d = json.loads(f["pesos"]) if "pesos" in f else {}
    st = d.get("stats", {})
    return {"tabla": True, "campeon": bool(d.get("campeon")), "huella": d.get("huella"),
            "ascensos": st.get("ascensos"), "reinicios": st.get("reinicios"), "retiros": st.get("retiros"),
            "ciclos": st.get("ciclos"), "preguntas": st.get("preguntas"), "tranquila": st.get("tranquila")}


def _contar_inmunes(ruta):
    con = sqlite3.connect("file:%s?mode=ro" % ruta, uri=True)
    n = con.execute("SELECT COUNT(*) FROM largo_plazo WHERE " + INMUNE_SQL).fetchone()[0]
    con.close()
    return n


def hijo_construir2(semilla, n_D, mundo, brazo, reloj_nombre, ruta, salida, k8="0"):
    n_D, k8 = int(n_D), k8 == "1"
    assert ruta.startswith("/tmp/")
    reloj = preparar_hijo2(brazo, lab.T0)
    import construir as c16
    m = ms.generar(int(semilla), n_D)
    D = [r for r in m["recuerdos"] if r["conj"] == "D"]
    I = [r for r in m["recuerdos"] if r["conj"] == ("I1" if mundo == "DI1" else "I0")]
    for ext in ("", "-wal", "-shm"):
        if os.path.exists(ruta + ext):
            os.remove(ruta + ext)
    SYN = sinonimos(m)
    st = {"cer": c16.abrir(ruta)}
    ciclos, t_sueno = [], 0.0
    delta = lab.RELOJES[reloj_nombre]

    excepciones = {}
    vivas = {}

    def trazar(frame, evento, arg):
        """K8 medido: toda excepción lanzada dentro del sueño en código del motor, aunque el motor la capture."""
        if evento == "exception":
            f = frame.f_code.co_filename
            if "/core/" in f or "#lab_ciclo2" in f:
                # Se guarda el objeto (no solo su id) mientras dura el sueño: un id de un objeto ya liberado
                # puede reutilizarse y ocultaría una excepción nueva (observación del auditor, 27-11).
                if id(arg[1]) not in vivas or vivas[id(arg[1])] is not arg[1]:
                    vivas[id(arg[1])] = arg[1]
                    clave = "%s @ %s:%d" % (arg[0].__name__, f.split("/core/")[-1], frame.f_lineno)
                    excepciones[clave] = excepciones.get(clave, 0) + 1
        return trazar

    def dormir(fase, nuevos):
        nonlocal t_sueno
        reloj.t += delta
        lab.REG.append(["ciclo", len(ciclos), fase, nuevos, lab._inmunes_activos(st["cer"])])
        lab.REG.append(["aristas_antes", len(ciclos), dict(st["cer"].cursor.execute(
            "SELECT tipo, COUNT(*) FROM sinapsis GROUP BY tipo").fetchall())])
        t = time.perf_counter()
        if k8:
            sys.settrace(trazar)
            try:
                c16.dormir(st["cer"])
            finally:
                sys.settrace(None)
                vivas.clear()
        else:
            c16.dormir(st["cer"])
        t_sueno += time.perf_counter() - t
        ciclos.append(fase)

    def guardar(r):
        with contextlib.redirect_stdout(io.StringIO()):
            c16.guardar(st["cer"], {"concepto": r["concepto"], "contenido": r["contenido"], "syn": "",
                                    "cat": "General", "dims": {}, "sk": ""} | {"syn": SYN.get(r["concepto"], "")})

    corte = {}
    if k8:
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
                if k % lab.CADA == 0:
                    dormir(fase, nuevos)
                    nuevos = 0
            dormir(fase, nuevos)
            if fase == "D":      # corte de la cohorte de búsqueda tras D (como una base real que ya existía)
                with contextlib.redirect_stdout(io.StringIO()):
                    st["cer"].conn.commit()
                    st["cer"].cerrar_sistema()
                st["cer"] = c16.abrir(ruta)
                corte = {"baseline_rowid": st["cer"]._search_baseline_rowid,
                         "fts_ref_listo": bool(getattr(st["cer"], "_search_baseline_fts_ready", False))}
    with contextlib.redirect_stdout(io.StringIO()):
        st["cer"].conn.commit()
        st["cer"].cerrar_sistema()
    con = sqlite3.connect(ruta)
    con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    con.close()
    json.dump({"registro": lab.REG, "t_sueno": t_sueno, "reloj_final": reloj.t, "n_ciclos": len(ciclos),
               "sha_tablas": lab.sha_tablas(ruta), "corte": corte, "neurona": estado_neurona(ruta),
               "excepciones_en_sueno": excepciones if k8 else None,
               "inmunes_en_la_base": _contar_inmunes(ruta)},
              open(salida, "w"), ensure_ascii=False)


# ------------------------------------------------------------------ orquestación
def _run(args, extra):
    e = dict(os.environ)
    e["HOME"] = os.path.join(TMP, "home", hashlib.sha256(repr((args, extra)).encode()).hexdigest()[:16])
    e.update(lab.BASE_ENV)
    e.update(extra)
    shutil.rmtree(e["HOME"], ignore_errors=True)
    os.makedirs(e["HOME"])
    p = subprocess.run([lab.PY, os.path.abspath(__file__)] + [str(a) for a in args], env=e, cwd=AQUI,
                       capture_output=True, text=True)
    shutil.rmtree(e["HOME"], ignore_errors=True)
    if p.returncode != 0:
        raise RuntimeError("falló %s:\n%s" % (args, p.stderr[-4000:]))


def consultas_puente(m):
    """M3′: consultas con la entidad puente (I1↔D) + una palabra del tema del recuerdo de D que la contiene."""
    rng = random.Random("puente|%d" % m["semilla"])
    conj_tema = {tid: t["conj"] for tid, t in m["temas"].items()}
    ents_ID = {}
    for p in m["puentes"]:
        cs = sorted(conj_tema[t] for t in p["temas"])
        if cs == ["D", "I1"]:
            tD = [t for t in p["temas"] if conj_tema[t] == "D"][0]
            ents_ID.setdefault(tD, []).append(p["entidad"])
    cand = []
    for r in m["recuerdos"]:
        if r["conj"] != "D" or not r["palabras_tema"]:
            continue
        for e in ents_ID.get(r["tema"], []):
            if e in r["entidades"]:
                cand.append((r, e))
    rng.shuffle(cand)
    out = []
    for r, e in cand[:N_PUENTE_Q]:
        w = rng.choice(r["palabras_tema"])
        ws = [e, w]
        rng.shuffle(ws)
        q = "".join(ws) if r["esc"] in ms.SIN_ESPACIOS else " ".join(ws)
        out.append({"id": "puente|%s|%s" % (r["concepto"], e), "x": r["concepto"].lower(), "q": q, "esc": r["esc"],
                    "entidad": e})
    return out


def un_mundo(args):
    neu, semilla, n_D, reloj_nombre, brazo, mundo = args
    tag = "%s_s%d_n%d_%s" % (neu, semilla, n_D, reloj_nombre)
    d = os.path.join(TMP, tag, brazo.replace("-", "m").replace("+", "_"))
    os.makedirs(d, exist_ok=True)
    pj = os.path.join(TMP, tag, "consultas.json")
    ruta = os.path.join(d, mundo + ".db")
    rc, rm = os.path.join(d, mundo + "_reg.json"), os.path.join(d, mundo + "_med.json")
    if not (os.path.exists(rc) and os.path.exists(rm)):
        _run(["construir", semilla, n_D, mundo, brazo, reloj_nombre, ruta, rc], NEURONA[neu])
        reg = json.load(open(rc))
        _run(["medir", ruta, pj, rm, reg["reloj_final"]], NEURONA[neu])
        os.remove(ruta)
    return (brazo, mundo), {"reg": json.load(open(rc)), "med": json.load(open(rm))}


def subir(rutas, mensaje):
    if SECO:
        return
    raiz = lab.RAIZ
    try:
        subprocess.run(["git", "-C", raiz, "add"] + rutas, check=True, capture_output=True)
        subprocess.run(["git", "-C", raiz, "commit", "-q", "-m", mensaje], check=True, capture_output=True)
        subprocess.run(["git", "-C", raiz, "push", "-q", "origin", RAMA], check=True, capture_output=True,
                       timeout=120)
        print("subido:", mensaje, flush=True)
    except Exception as e:  # el resultado queda en disco; se sube en el siguiente intento
        print("no se pudo subir (%s): %r" % (mensaje, e), flush=True)


def analizar_extra(semilla, n_D, res, m, base):
    """Ajustes del ciclo 2 sobre el análisis v2: atribución′, K2′, K5″, K7′, M3′, estado de la Neurona 1."""
    idx = {r["concepto"].lower(): r for r in m["recuerdos"]}
    U = {c: lab.unidades(r["contenido"]) for c, r in idx.items()}
    midx = {"puentes": {}}
    for p in m["puentes"]:
        midx["puentes"].setdefault(tuple(p["temas"]), []).append(p["entidad"])
    texto = lambda a, b: lab.coinciden(U[a["concepto"].lower()], U[b["concepto"].lower()])  # noqa: E731
    verdad = lambda a, b: ms.verdad_par(midx, idx[a], idx[b], texto)  # noqa: E731
    en_D = {c for c, r in idx.items() if r["conj"] == "D"}
    qs = lab.consultas(m)
    qp = consultas_puente(m)
    K = lab.K
    for brazo in BRAZOS:
        R = {w: res[(brazo, w)] for w in MUNDOS}
        a = base[brazo]
        tD = R["D"]["med"]["top"]
        sD = lambda t, q: [c for c in t[q][:K] if c in en_D]  # noqa: E731
        # atribución′
        s1 = a["S1"]
        s1["atribuibles_con_regla_estado_D"] = 0 if s1["estado_D_identico"] else s1["top5_cambiados_atribuibles_H2_4b"]
        # K2′ (conjunto fijo, sin filtrar)
        k2 = {}
        for w in ("DI0", "DI1"):
            tW = R[w]["med"]["top"]
            perdida = sum(1 for q in qs if sD(tD, q["id"]) and not sD(tW, q["id"]))
            ambas = [q for q in qs if sD(tD, q["id"]) and sD(tW, q["id"])]
            orden = sum(1 for q in ambas if sD(tD, q["id"]) != sD(tW, q["id"]))
            k2[w] = {"consultas": len(qs), "cobertura_perdida": perdida, "con_lista_en_ambos": len(ambas),
                     "orden_cambiado": orden, "vacias_D": sum(1 for q in qs if not sD(tD, q["id"])),
                     "vacias_" + w: sum(1 for q in qs if not sD(tW, q["id"]))}
        k2["recall_origen_top5"] = a["recall_origen_top5"]
        a["K2p"] = k2
        # K5″ número de pares buenos visibles (además de la fracción)
        a["K5pp"] = {w: a["K5_" + w]["pares_visibles_tema_puente"] for w in ("D", "DI1")}
        # K7′ costo por sueño y por recuerdo activo (D∪I1)
        cyc = lab.ciclos(R["DI1"]["reg"]["registro"])
        act = sum((x.get("n_activos") or 0) for x in cyc)
        t = R["DI1"]["reg"]["t_sueno"]
        a["K7p"] = {"t_sueno_s": round(t, 2), "ciclos": len(cyc), "s_por_sueno": round(t / max(1, len(cyc)), 4),
                    "s_por_recuerdo_activo_y_sueno": round(t / act, 6) if act else None,
                    "activos_medios": round(act / max(1, len(cyc)), 1)}
        # H2-local y 4b-propio: actividad por mundo
        act_loc = {}
        for w in MUNDOS:
            reg = R[w]["reg"]["registro"]
            act_loc[w] = {"h2loc_dormidos": sum(ev[3] for ev in reg if ev[0] == "h2loc"),
                          "h2loc_ciclos_con_exceso": sum(1 for ev in reg if ev[0] == "h2loc" and ev[2] > 0),
                          "4bp_escalados": sum(ev[1] for ev in reg if ev[0] == "4bp")}
        a["actividad_variantes"] = act_loc
        # M3′ consultas con la entidad puente (en D∪I1)
        tI1, tD_p = R["DI1"]["med"]["top"], R["D"]["med"]["top"]
        ins = {"puente": 0, "tema": 0, "accidental": 0, "ajeno": 0}
        q_con_puente = 0
        for q in qp:
            top = tI1.get(q["id"], [])[:K]
            hubo = False
            for c in top:
                if c in idx and idx[c]["conj"] == "I1":
                    v = verdad(q["x"], c)
                    ins[v] += 1
                    hubo = hubo or v == "puente"
            q_con_puente += hubo
        a["M3p"] = {"consultas_puente": len(qp), "inserciones_I1_top5_por_verdad": ins,
                    "consultas_con_algun_puente_legitimo": q_con_puente,
                    "recall_origen_D": round(sum(q["x"] in tD_p.get(q["id"], [])[:K] for q in qp) / len(qp), 4) if qp else None,
                    "recall_origen_DI1": round(sum(q["x"] in tI1.get(q["id"], [])[:K] for q in qp) / len(qp), 4) if qp else None}
        # C-medida: aristas por tipo × verdad al final (D∪I1) y por tipo antes de cada sueño
        tv = {}
        vistos = set()
        for o, de, tipo, peso in R["DI1"]["med"]["aristas"]:
            par = tuple(sorted((o, de)))
            if o not in idx or de not in idx or par in vistos:
                continue
            vistos.add(par)
            v = verdad(o, de)
            tv.setdefault(tipo, {"tema": 0, "puente": 0, "accidental": 0, "ajeno": 0})[v] += 1
        a["C_medida"] = {"tipo_x_verdad_DI1": tv,
                         "por_tipo_antes_de_cada_sueno_DI1": [ev[2] for ev in R["DI1"]["reg"]["registro"]
                                                             if ev[0] == "aristas_antes"]}
        # Neurona 1 por mundo
        a["neurona"] = {w: R[w]["reg"].get("neurona") for w in MUNDOS}
        a["corte"] = {w: R[w]["reg"].get("corte") for w in MUNDOS}
    return base


def una_config(neu, semilla, n_D, reloj_nombre):
    tag = "%s_s%d_n%d_%s" % (neu, semilla, n_D, reloj_nombre)
    final = os.path.join(RES, "config_%s.json" % tag)
    if os.path.exists(final):
        return json.load(open(final))
    m = ms.generar(semilla, n_D)
    os.makedirs(os.path.join(TMP, tag), exist_ok=True)
    json.dump(lab.consultas(m) + consultas_puente(m), open(os.path.join(TMP, tag, "consultas.json"), "w"),
              ensure_ascii=False)
    t0 = time.time()
    trabajos = [(neu, semilla, n_D, reloj_nombre, b, w) for b in BRAZOS for w in MUNDOS]
    with ThreadPoolExecutor(2) as ex:
        res = dict(ex.map(un_mundo, trabajos))
    lab.BRAZOS = BRAZOS
    por_brazo = {b: {w: res[(b, w)] for w in MUNDOS} for b in BRAZOS}
    base = lab.analizar_config(semilla, n_D, reloj_nombre, por_brazo, m)
    an = analizar_extra(semilla, n_D, res, m, base)
    an["_meta"] = {"neurona": neu, "semilla": semilla, "n_D": n_D, "reloj": reloj_nombre,
                   "n_I0": len([r for r in m["recuerdos"] if r["conj"] == "I0"]),
                   "n_I1": len([r for r in m["recuerdos"] if r["conj"] == "I1"]),
                   "consultas_puente": len(consultas_puente(m)), "segundos": round(time.time() - t0, 1)}
    os.makedirs(RES, exist_ok=True)
    json.dump(an, open(final, "w"), ensure_ascii=False)
    shutil.rmtree(os.path.join(TMP, tag), ignore_errors=True)
    subir([final], "H2/4b ciclo 2: config %s (sintético)" % tag)
    return an


def k8(neu):
    final = os.path.join(RES, "k8_%s.json" % neu)
    if os.path.exists(final):
        return json.load(open(final))
    n = 40 if SECO else 320
    jobs = [(s, b) for s in lab.SEMILLAS[:1 if SECO else 3] for b in BRAZOS]

    def uno(job):
        s, brazo = job
        d = os.path.join(TMP, "k8_" + neu, "s%d_%s" % (s, brazo.replace("-", "m").replace("+", "_")))
        os.makedirs(d, exist_ok=True)
        r = {}
        for mundo in ("D", "DI0"):
            ruta = os.path.join(d, mundo + ".db")
            sal = ruta + ".json"
            _run(["construir", s, n, mundo, brazo, "diario", ruta, sal, "1"], NEURONA[neu])
            con = sqlite3.connect("file:%s?mode=ro" % ruta, uri=True)
            r[mundo] = {"estado": dict(con.execute("SELECT concepto, estado FROM largo_plazo").fetchall()),
                        "peso": dict(con.execute("SELECT concepto, peso_sinaptico FROM largo_plazo").fetchall()),
                        "reg": json.load(open(sal))}
            con.close()
            os.remove(ruta)
        cyc = lab.ciclos(r["DI0"]["reg"]["registro"])
        dorm = {}
        for x in cyc:
            for c in x.get("h2_dormidos", []) + x.get("ltd_dormidos", []):
                dorm[c] = dorm.get(c, 0) + 1
        enD = list(r["D"]["estado"])
        return "s%d|%s" % (s, brazo), {
            "ciclos": len(cyc),
            # K8 medido (corrección de la auditoría de 64e055f): antes este campo valía True sin medirse.
            # No capturadas: el hijo terminó con código 0 (si no, _run habría fallado). Capturadas: trazadas en el sueño.
            "excepciones_no_capturadas": 0,
            "excepciones_capturadas_en_sueno": {w: r[w]["reg"]["excepciones_en_sueno"] for w in ("D", "DI0")},
            "sin_excepciones": all(not r[w]["reg"]["excepciones_en_sueno"] for w in ("D", "DI0")),
            "recuerdos_dormidos_mas_de_una_vez": sum(1 for v in dorm.values() if v > 1),
            "dormidos_por_H2_o_H2loc": sum(len(x.get("h2_dormidos", [])) for x in cyc),
            "dormidos_por_peso_propio": sum(len(x.get("ltd_dormidos", [])) for x in cyc),
            "K1_cambios_estado_D": sum(1 for c in enD if r["D"]["estado"][c] != r["DI0"]["estado"][c]),
            "K1_cambios_importancia_D": sum(1 for c in enD if r["D"]["peso"][c] != r["DI0"]["peso"][c]),
            "suma_abs_delta_importancia_D": round(sum(abs(r["D"]["peso"][c] - r["DI0"]["peso"][c]) for c in enD), 4),
            "activos_final_DI0": sum(1 for v in r["DI0"]["estado"].values() if v == "activo"),
            "neurona": {w: r[w]["reg"].get("neurona") for w in ("D", "DI0")}}
    with ThreadPoolExecutor(2) as ex:
        out = dict(ex.map(uno, jobs))
    os.makedirs(RES, exist_ok=True)
    json.dump(out, open(final, "w"), ensure_ascii=False, indent=1)
    subir([final], "H2/4b ciclo 2: K8 %s (sintético)" % neu)
    return out


def controles():
    """El registro no cambia la base (con y sin el registro extra de las variantes) y el orden de las consultas
    no cambia el top-k. Semilla 7, |D| mínimo, comprimido, D∪I1, configuración «ctl»."""
    final = os.path.join(RES, "controles.json")
    if os.path.exists(final):
        return json.load(open(final))
    s, n = 7, lab.TAMANOS[0]
    d = os.path.join(TMP, "control")
    os.makedirs(d, exist_ok=True)
    m = ms.generar(s, n)
    pj = os.path.join(d, "consultas.json")
    json.dump(lab.consultas(m) + consultas_puente(m), open(pj, "w"), ensure_ascii=False)
    out = {}
    for brazo in ("H2loc+4bp",):
        ruta = os.path.join(d, "a.db")
        _run(["construir", s, n, "DI1", brazo, "comprimido", ruta, ruta + ".json"], NEURONA["ctl"])
        sha_a = json.load(open(ruta + ".json"))["sha_tablas"]
        reloj = json.load(open(ruta + ".json"))["reloj_final"]
        for orden in ("directo", "inverso"):
            _run(["medir", ruta, pj, ruta + "." + orden, reloj, orden], NEURONA["ctl"])
        ta, tb = (json.load(open(ruta + "." + o))["top"] for o in ("directo", "inverso"))
        ruta2 = os.path.join(d, "b.db")
        _run(["construir", s, n, "DI1", brazo, "comprimido", ruta2, ruta2 + ".json"], NEURONA["ctl"])
        out[brazo] = {"construccion_determinista": sha_a == json.load(open(ruta2 + ".json"))["sha_tablas"],
                      "orden_consultas_indiferente": ta == tb}
    os.makedirs(RES, exist_ok=True)
    json.dump(out, open(final, "w"), ensure_ascii=False, indent=1)
    shutil.rmtree(d, ignore_errors=True)
    subir([final], "H2/4b ciclo 2: controles (sintético)")
    return out


def main():
    os.makedirs(RES, exist_ok=True)
    t0 = time.time()
    print("controles", controles(), flush=True)
    sem = lab.SEMILLAS[:1] if SECO else lab.SEMILLAS
    for neu in ("ctl", "real"):
        for rj in lab.RELOJES:
            for n in lab.TAMANOS:
                for s in sem:
                    an = una_config(neu, s, n, rj)
                    print("config", neu, s, n, rj, round(time.time() - t0),
                          {b: an[b]["S1"]["top5_cambiados_total"] for b in BRAZOS}, flush=True)
        print("k8", neu, json.dumps(k8(neu))[:300], round(time.time() - t0), flush=True)
    print("FIN", round(time.time() - t0), flush=True)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "construir":
        hijo_construir2(*sys.argv[2:])
    elif cmd == "medir":
        lab.hijo_medir(*sys.argv[2:])
    elif cmd == "todo":
        main()
