"""Paso 3, capa V (valor): ¿las 12 agujas limpias de la capa L ordenan mejor el canal 2 que el orden a mano?

Protocolo: ../PROTOCOLO_PASO3.md §4 (capa V), §5 (C3.3, C3.5, C3.7, C3.8), §9 y §10 (decisiones del 27-11).
Motor sin tocar; todo en /tmp/capa_V; sin DB viva. Corpus: corpus_v.py (licencias en resultados/manifiesto_corpus.json).

Agujas medidas (capa L, RESULTADOS_CAPA_L.md): las 12 limpias S_tem, S_tono, S_sk, X_min, X_max, X_concepto, X_sk,
X_contenido, B_flag, B_weight, B_angulos, Cat; R aparte, como referencia (no se admite por esta vía).
S_idf y G_ciego siguen fuera (C3.7 no se relaja).

Escritores de las declaraciones (dimensiones, sustantivos clave, 5 bridges, categoría, syn):
- `mecanico`: regla local por recuerdo, sin listas: las unidades más repetidas dentro del propio texto, entre las de
  largo ≥ la mediana del texto (empate: más larga, luego primera aparición). No inventa dimensiones ni categoría (no tiene con qué): S_tem, S_tono y Cat quedan
  constantes → «no medible» (C3.8). Es el CONTROL: separa la coincidencia de superficie del conocimiento del agente.
- `ciego`: declaraciones escritas por una sesión aislada distinta (decisión 27-11), un recuerdo cada vez, barajado,
  sin documento ni verdad. Se exporta el paquete con `exportar` y se importa su salida en
  /tmp/capa_V/ciego_{idioma}.jsonl. Sin ese archivo, este escritor no corre.

Construcción: camino de `aprender` del motor real (como la capa L), orden barajado con semilla fija (para que la
co-ocurrencia de sesión no delate el documento), sueño T cada 50 recuerdos, reloj diario, reloj simulado también en
SQLite. Medición con BIORAG_NEURONA=0, PPMI 0 y síntesis DMN 0 (§6); R sobre la copia limpia.

Verdad: positivo = mismo documento. Negativo duro = documento distinto con Jaccard de unidades ≥ mediana de los
positivos del idioma. Partición por documento: E (Estudio, 60 %), V (Validación, 20 %), G (Guardia, 20 %, sellada:
se ingiere, pero ningún análisis la lee). Listas del canal 2 de A: vecinos activos con peso ≥ 0,5 de la MISMA
partición que A (sin pares a ambos lados), mejor arista por par (prioridad de tipo, peso).

Reglas fijadas antes de medir (§10 del protocolo):
- piso = orden a mano del motor: prioridad de tipo ASC, peso DESC (synapses.py L509–585) → p = −100·prioridad + peso.
- piso + aguja = regresión logística [z(p), z(aguja)] ajustada solo con los pares de E (L2 = 1e-3, Newton).
- C3.5: MRR del primer vecino verdadero, en los nodos de V con ≥ 1 positivo y ≥ 1 negativo en su lista; empates al azar
  (esperanza sobre 64 barajados, semilla fija); diferencia pareada por nodo; IC95 por bootstrap de documentos (2000,
  semilla 2711) > 0 → cumple.
- C3.3: AUC (positivo frente a negativo) en los pares con arista de V; IC95 bootstrap por documento;
  ≥ 0,60 con IC inferior > 0,50 en cada idioma; máx − mín entre idiomas ≤ 0,10. Secundario: pares al azar de V.
- C3.7: Spearman(aguja, grado de A) ≤ 0,3 en los pares de V. C3.8: constante en un idioma → «no medible».
- Regla de parada (decisión 27-11): si ninguna de las 12 limpias (en especial S + X) cumple C3.5 en cada idioma, se
  detiene y se reporta antes de inventar agujas o cambios.

Uso:
  python laboratorio_capa_V.py todo [mecanico|ciego]      (CAPA_V_SECO=1: prueba en seco con 150 recuerdos)
  python laboratorio_capa_V.py exportar                   → /tmp/capa_V/paquete_ciego/ (para la sesión aislada)
"""
import contextlib
import hashlib
import io
import json
import math
import os
import random
import shutil
import sqlite3
import subprocess
import sys
import time
import unicodedata
from collections import Counter

AQUI = os.path.dirname(os.path.abspath(__file__))
CAPA_L = os.path.abspath(os.path.join(AQUI, "..", "capa_L"))
if CAPA_L not in sys.path:
    sys.path.insert(0, CAPA_L)
os.environ.setdefault("CAPA_L_RELOJ_SQLITE", "1")   # reloj simulado también en SQLite (27-11)
import laboratorio_capa_L as L  # noqa: E402

lab = L.lab
PY = sys.executable
SECO = bool(os.environ.get("CAPA_V_SECO"))
TMP = "/tmp/capa_V"
RES = os.path.join(TMP, "resultados_seco") if SECO else os.path.join(AQUI, "resultados")
IDIOMAS = ("es", "en", "zh", "ja")
N_SECO = 150
SEMILLA = 2711
CADA = 50
DIA = 86400.0
T0 = L.T0
PESO_MIN = 0.5
LIMPIAS = ("S_tem", "S_tono", "S_sk", "X_min", "X_max", "X_concepto", "X_sk", "X_contenido",
           "B_flag", "B_weight", "B_angulos", "Cat")
GRUPO_SX = ("S_tem", "S_tono", "S_sk", "X_min", "X_max", "X_concepto", "X_sk", "X_contenido")
REFERENCIA = ("R",)
ANGULOS = ("sinonimo", "problema", "solucion", "situacion", "ingenuo")
RAMA = L.RAMA


# ================================================================== corpus y unidades con frecuencia
def corpus(idioma):
    c = json.load(open(os.path.join(TMP, "corpus_%s.json" % idioma)))
    if SECO:   # documentos enteros hasta N_SECO recuerdos
        out, docs = [], set()
        for r in c:
            if len(out) >= N_SECO and r["doc"] not in docs:
                break
            docs.add(r["doc"])
            out.append(r)
        c = out
    return c


def unidades_lista(texto):
    """Las mismas unidades que `lab.unidades` (palabras latinas; bigramas CJK), pero con repetición y en orden."""
    t = unicodedata.normalize("NFKC", texto).casefold()
    t = "".join(ch if unicodedata.category(ch)[0] in "LN" else " " for ch in t)
    out = []
    for trozo in t.split():
        corr, tipo, partes = "", None, []
        for ch in trozo:
            k = lab._sin_espacios(ch)
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
                out += [txt[i:i + 2] for i in range(len(txt) - 1)]
            else:
                out.append(txt)
    return out


# ================================================================== escritores
def escritor_mecanico(c):
    """Regla local fijada antes de medir (seco del 27-11 solo probó la tubería): candidatas = unidades válidas cuyo
    largo ≥ mediana de los largos de las unidades distintas del propio texto (sin listas de palabras); orden =
    frecuencia DESC, largo DESC, primera aparición. sk = 6 primeras; nombre = 2 primeras + id; bridges = pares
    disjuntos de las siguientes (3ª+4ª, 5ª+6ª, …), dando la vuelta si faltan."""
    out = {}
    for r in c:
        us = [u for u in unidades_lista(r["contenido"]) if L._sk_valido(u)]
        distintas = sorted(len(u) for u in set(us))
        med = distintas[len(distintas) // 2] if distintas else 0
        cand = [u for u in us if len(u) >= med]
        cnt = Counter(cand)
        prim = {}
        for i, u in enumerate(cand):
            prim.setdefault(u, i)
        orden = sorted(cnt, key=lambda u: (-cnt[u], -len(u), prim[u]))
        while len(orden) < 2:
            orden.append("nota%d" % len(orden))
        sk = orden[:6]
        cjk = any(lab._sin_espacios(ch) for ch in "".join(sk))
        sep = "" if cjk else " "
        resto = orden[2:] if len(orden) >= 4 else orden
        bridges, vistos = [], set()
        for k, ang in enumerate(ANGULOS):
            a = resto[(2 * k) % len(resto)]
            b = resto[(2 * k + 1) % len(resto)]
            txt = sep.join((a, b))
            while cjk and len(txt) < 4:
                txt += b
            if txt in vistos:
                txt = sep.join((txt, resto[(2 * k + 2) % len(resto)]))
            vistos.add(txt)
            bridges.append({"text": txt, "angle": ang, "weight": 0.8})
        out[r["rid"]] = {"concepto": "%s_%s_%s" % (sk[0], sk[1], r["rid"]), "dims": {}, "sk": ",".join(sk),
                         "bridges": bridges, "cat": "General", "val": 0.0, "syn": ""}
    return out


def leer_ciego(idioma, c):
    """Salida de la sesión aislada: una línea JSON por recuerdo con id, concepto, dimensiones, syn, categoria,
    sustantivos_clave y bridges (contrato de `aprender`). El id del recuerdo se añade al nombre para que sea único."""
    ruta = os.path.join(TMP, "ciego_%s.jsonl" % idioma)
    if not os.path.exists(ruta):
        raise SystemExit("falta %s (declaraciones de la sesión aislada)" % ruta)
    out = {}
    for linea in open(ruta, encoding="utf-8"):
        if not linea.strip():
            continue
        x = json.loads(linea)
        dims = x.get("dimensiones") or {}
        if isinstance(dims, str):
            dims = json.loads(dims)
        sk = x.get("sustantivos_clave") or ""
        if isinstance(sk, list):
            sk = ",".join(sk)
        out[x["id"]] = {"concepto": "%s_%s" % (str(x.get("concepto") or "nodo").strip(), x["id"]),
                        "dims": dims, "sk": sk, "bridges": x.get("bridges") or [],
                        "cat": x.get("categoria") or "General", "val": 0.0, "syn": x.get("syn") or ""}
    faltan = [r["rid"] for r in c if r["rid"] not in out]
    if faltan:
        raise SystemExit("faltan %d declaraciones en %s (p. ej. %s)" % (len(faltan), ruta, faltan[:3]))
    return out


def exportar():
    """Paquete para la sesión aislada: recuerdos barajados con id opaco, sin documento ni vecinos ni verdad."""
    d = os.path.join(TMP, "paquete_ciego")
    os.makedirs(d, exist_ok=True)
    for idioma in IDIOMAS:
        c = json.load(open(os.path.join(TMP, "corpus_%s.json" % idioma)))
        g = random.Random("%d|ciego|%s" % (SEMILLA, idioma))
        orden = sorted(c, key=lambda r: r["rid"])
        g.shuffle(orden)
        with open(os.path.join(d, "recuerdos_%s.jsonl" % idioma), "w", encoding="utf-8") as f:
            for r in orden:
                f.write(json.dumps({"id": r["rid"], "contenido": r["contenido"]}, ensure_ascii=False) + "\n")
    shutil.copyfile(os.path.join(AQUI, "INSTRUCCIONES_ESCRITOR_CIEGO.md"),
                    os.path.join(d, "INSTRUCCIONES_ESCRITOR_CIEGO.md"))
    print("paquete en", d)


# ================================================================== hijo: construir (motor real)
def hijo_construir(idioma, escritor, ruta, salida):
    reloj = lab.preparar_hijo("T", False, T0)
    L.reloj_sqlite(reloj)
    import construir as c16  # noqa: F401  (exp. 16: abrir/dormir)
    from core.mcp_server._shared import _resolver_dimensiones
    from core.memory_store import normalizar_sustantivos_clave, normalizar_sustantivos_clave_exacto
    from core.sinapsis import auto_vincular, vincular_por_sinonimos
    from core.concept_hub import validar_bridges, crear_hub, agregar_bridges
    c = corpus(idioma)
    dec = escritor_mecanico(c) if escritor == "mecanico" else leer_ciego(idioma, c)
    orden = sorted(c, key=lambda r: r["rid"])
    random.Random("%d|orden|%s" % (SEMILLA, idioma)).shuffle(orden)
    for ext in ("", "-wal", "-shm"):
        if os.path.exists(ruta + ext):
            os.remove(ruta + ext)
    st = {"cer": c16.abrir(ruta)}
    info = {"bridges_rechazados": 0, "dims_inventadas": 0, "dims_error": 0, "t_sueno": 0.0, "n_suenos": 0,
            "claves": {}}

    def guardar(r):
        cer, d = st["cer"], dec[r["rid"]]
        clave = d["concepto"].lower().replace(" ", "_")
        info["claves"][r["rid"]] = clave
        sk_ex = normalizar_sustantivos_clave_exacto(d["sk"])
        sk_norm = normalizar_sustantivos_clave(sk_ex)
        dims, meta = None, {}
        if d["dims"]:
            dims, _, err, meta = _resolver_dimensiones(cer, json.dumps(d["dims"]))
            if err:
                info["dims_error"] += 1
                dims, meta = None, {}
        info["dims_inventadas"] += len((meta or {}).get("dimensiones_creadas") or [])
        cer.percibir_corto_plazo(clave, r["contenido"], d["syn"], d["cat"], dims, predicados=None,
                                 valencia_somatica=d["val"], sustantivos_clave=sk_norm,
                                 sustantivos_clave_exactos=sk_ex)
        auto_vincular(cer, clave, r["contenido"])
        if d["syn"]:
            vincular_por_sinonimos(cer, clave, d["syn"])
        val, _rech = validar_bridges(d["bridges"], clave)
        if len(val) == 5:
            hub = "hub_" + clave
            crear_hub(cer.conn, hub, clave, description="Bridges obligatorios desde aprender")
            agregar_bridges(cer.conn, hub, val)
        else:
            info["bridges_rechazados"] += 1

    def dormir():
        reloj.t += DIA
        t = time.perf_counter()
        c16.dormir(st["cer"])
        info["t_sueno"] += time.perf_counter() - t
        info["n_suenos"] += 1

    for k, r in enumerate(orden, 1):
        reloj.t += 1
        with contextlib.redirect_stdout(io.StringIO()):
            guardar(r)
        if k % CADA == 0:
            dormir()
    dormir()
    with contextlib.redirect_stdout(io.StringIO()):
        st["cer"].conn.commit()
        st["cer"].cerrar_sistema()
    con = sqlite3.connect(ruta)
    con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    info["sqlite_now"] = float(con.execute("SELECT strftime('%s','now')").fetchone()[0])
    con.close()
    info["reloj_final"] = reloj.t
    assert abs(info["sqlite_now"] - reloj.t) < 2, "reloj de SQLite no simulado"
    json.dump(info, open(salida, "w"), ensure_ascii=False)


# ================================================================== estadística (numpy puro)
def _np():
    import numpy as np
    return np


def logistica(X, y, l2=1e-3, it=50):
    np = _np()
    X = np.hstack([X, np.ones((len(X), 1))])
    w = np.zeros(X.shape[1])
    for _ in range(it):
        p = 1.0 / (1.0 + np.exp(-np.clip(X @ w, -30, 30)))
        g = X.T @ (p - y) / len(y) + l2 * np.r_[w[:-1], 0.0]
        H = (X * (p * (1 - p))[:, None]).T @ X / len(y) + l2 * np.eye(len(w))
        paso = np.linalg.solve(H, g)
        w -= paso
        if np.abs(paso).max() < 1e-9:
            break
    return w


def rr_esperado(puntajes, verdad, rng, veces=64):
    """1/rango del primer verdadero, con empates rotos al azar (esperanza sobre `veces` barajados)."""
    idx = list(range(len(puntajes)))
    s = 0.0
    for _ in range(veces):
        rng.shuffle(idx)
        orden = sorted(idx, key=lambda i: -puntajes[i])   # sort estable: el barajado decide los empates
        for pos, i in enumerate(orden, 1):
            if verdad[i]:
                s += 1.0 / pos
                break
    return s / veces


def auc(pos, neg):
    return L.auc(pos, neg)


def bootstrap_docs(por_doc, estad, B=2000, semilla=SEMILLA):
    """por_doc: {doc: lista de unidades}; estad: f(lista de unidades) → número. IC95 percentil."""
    rng = random.Random(semilla)
    docs = sorted(por_doc)
    vals = []
    for _ in range(B):
        muestra = []
        for _k in range(len(docs)):
            muestra += por_doc[docs[rng.randrange(len(docs))]]
        v = estad(muestra)
        if v is not None:
            vals.append(v)
    vals.sort()
    if not vals:
        return None, None
    return vals[int(0.025 * len(vals))], vals[min(len(vals) - 1, int(0.975 * len(vals)))]


# ================================================================== análisis de un idioma
def analizar(idioma, escritor, c, med, info):
    np = _np()
    clave = info["claves"]
    por_clave = {clave[r["rid"]]: r for r in c if r["rid"] in clave}
    rasgos = med["rasgos"]
    ag = L.Agujas(med, {}, {})
    # canal 2: mejor arista por par, vecino activo, peso ≥ 0,5
    mejor, grado = {}, Counter()
    for o, d, t, p in med["aristas"]:
        if o == d or o not in por_clave or d not in por_clave:
            continue
        if p is None or p < PESO_MIN:
            continue
        k = frozenset((o, d))
        cand = (L.PRIORIDAD.get(t, 50), -p, t)
        if k not in mejor or cand < mejor[k]:
            mejor[k] = cand
    vec = {}
    for k, (pr, mp, t) in mejor.items():
        a, b = sorted(k)
        if rasgos[a]["estado"] == "activo" and rasgos[b]["estado"] == "activo":
            grado[a] += 1
            grado[b] += 1
            vec.setdefault(a, []).append((b, pr, -mp, t))
            vec.setdefault(b, []).append((a, pr, -mp, t))
    filas = []   # (part, A, b, verdad, p, agujas..., doc de A)
    nombres = LIMPIAS + REFERENCIA
    cache = {}
    for a in sorted(vec):
        ra = por_clave[a]
        if ra["part"] == "G":
            continue
        for b, pr, p, t in vec[a]:
            rb = por_clave[b]
            if rb["part"] != ra["part"]:
                continue
            kk = (min(a, b), max(a, b))
            if kk not in cache:
                v = ag.valores(kk[0], kk[1], "locales")
                v.update(ag.valores(kk[0], kk[1], "buscador"))
                cache[kk] = v
            v = cache[kk]
            filas.append({"part": ra["part"], "A": a, "b": b, "doc": ra["doc"], "y": int(ra["doc"] == rb["doc"]),
                          "p": -100.0 * pr + p, "tipo": t, **{n: (v[n] if v[n] is not None else 0.0) for n in nombres}})
    E = [f for f in filas if f["part"] == "E"]
    V = [f for f in filas if f["part"] == "V"]
    out = {"idioma": idioma, "escritor": escritor, "n_recuerdos": len(c), "n_aristas_canal2": len(mejor),
           "n_pares_E": len(E), "n_pares_V": len(V), "positivos_E": sum(f["y"] for f in E),
           "positivos_V": sum(f["y"] for f in V), "info_construccion": {k: v for k, v in info.items() if k != "claves"},
           "tipos_V": dict(Counter(f["tipo"] for f in V)),
           "tipos_V_positivos": dict(Counter(f["tipo"] for f in V if f["y"]))}
    # nodos evaluables de V (listas con ≥1 positivo y ≥1 negativo)
    listas = {}
    for f in V:
        listas.setdefault(f["A"], []).append(f)
    nodos = sorted(a for a, fs in listas.items() if any(x["y"] for x in fs) and not all(x["y"] for x in fs))
    out["nodos_V_evaluables"] = len(nodos)
    out["nodos_V_con_lista"] = len(listas)
    rng = random.Random(SEMILLA)
    rr_piso = {a: rr_esperado([x["p"] for x in listas[a]], [x["y"] for x in listas[a]], rng) for a in nodos}
    out["MRR_piso"] = round(sum(rr_piso.values()) / len(nodos), 6) if nodos else None
    doc_de = {a: listas[a][0]["doc"] for a in nodos}

    def modelo(cols):
        if not E or len({f["y"] for f in E}) < 2:
            return None
        XE = np.array([[f["p"]] + [float(f[c_]) for c_ in cols] for f in E])
        mu, sd = XE.mean(0), XE.std(0)
        sd[sd == 0] = 1.0
        w = logistica((XE - mu) / sd, np.array([f["y"] for f in E], float))
        return lambda f: float(((np.array([f["p"]] + [float(f[c_]) for c_ in cols]) - mu) / sd) @ w[:-1])

    def c35(cols):
        m = modelo(cols)
        if m is None or not nodos:
            return {"medible": False}
        rngm = random.Random(SEMILLA)
        rr = {a: rr_esperado([m(x) for x in listas[a]], [x["y"] for x in listas[a]], rngm) for a in nodos}
        dif = {a: rr[a] - rr_piso[a] for a in nodos}
        por_doc = {}
        for a in nodos:
            por_doc.setdefault(doc_de[a], []).append(dif[a])
        lo, hi = bootstrap_docs(por_doc, lambda xs: sum(xs) / len(xs) if xs else None)
        md = sum(dif.values()) / len(nodos)
        return {"medible": True, "MRR": round(sum(rr.values()) / len(nodos), 6), "dif": round(md, 6),
                "IC95": [round(lo, 6), round(hi, 6)], "cumple": bool(lo is not None and lo > 0)}

    def c33(n, filas_):
        pos = [f[n] for f in filas_ if f["y"]]
        neg = [f[n] for f in filas_ if not f["y"]]
        if not pos or not neg:
            return {"medible": False}
        a_ = auc(pos, neg)
        por_doc = {}
        for f in filas_:
            por_doc.setdefault(f["doc"], []).append(f)

        def est(xs):
            p_ = [x[n] for x in xs if x["y"]]
            q_ = [x[n] for x in xs if not x["y"]]
            return auc(p_, q_) if p_ and q_ else None
        lo, hi = bootstrap_docs(por_doc, est, B=1000)
        return {"medible": True, "AUC": round(a_, 6), "IC95": [round(lo, 6), round(hi, 6)],
                "cumple": bool(a_ >= 0.60 and lo is not None and lo > 0.50)}

    # negativos duros: Jaccard de unidades ≥ mediana de los positivos
    def jac(f):
        ua, ub = L.U(por_clave[f["A"]]["contenido"]), L.U(por_clave[f["b"]]["contenido"])
        return len(ua & ub) / len(ua | ub) if (ua or ub) else 0.0
    for f in V:
        f["_jac"] = jac(f)
    jp = sorted(f["_jac"] for f in V if f["y"])
    umbral_duro = jp[len(jp) // 2] if jp else 1.0
    duros = [f for f in V if f["y"] or f["_jac"] >= umbral_duro]
    out["negativos_duros_V"] = sum(1 for f in duros if not f["y"])
    out["umbral_jaccard_duro"] = round(umbral_duro, 6)
    out["agujas"] = {}
    for n in nombres:
        vals = [f[n] for f in V]
        constante = len(set(vals)) <= 1
        g = [grado[f["A"]] for f in V]
        rho = L.spearman(vals, g) if not constante and len(set(g)) > 1 else None
        out["agujas"][n] = {"constante_V": constante,
                            "C3.3": c33(n, V) if not constante else {"medible": False},
                            "C3.3_duros": c33(n, duros) if not constante else {"medible": False},
                            "C3.5": c35([n]) if not constante else {"medible": False},
                            "C3.7_rho": None if rho is None else round(rho, 6)}
    # combinaciones (informativas; la regla de parada mira cada aguja y el grupo S + X)
    var = [n for n in LIMPIAS if not out["agujas"][n]["constante_V"]]
    var_sx = [n for n in GRUPO_SX if n in var]
    out["combinaciones"] = {"S+X": c35(var_sx) if var_sx else {"medible": False},
                            "12_limpias": c35(var) if var else {"medible": False},
                            "12_limpias+R": c35(var + ["R"]) if var else {"medible": False}}
    # secundario: pares al azar de V (todos los positivos de V con o sin arista + igual número de negativos)
    rv = [r for r in c if r["part"] == "V" and r["rid"] in clave]
    pos_az, neg_az = [], []
    por_d = {}
    for r in rv:
        por_d.setdefault(r["doc"], []).append(clave[r["rid"]])
    for ks in por_d.values():
        for i in range(len(ks)):
            for j in range(i + 1, len(ks)):
                pos_az.append((ks[i], ks[j]))
    g2 = random.Random(SEMILLA + 1)
    todos = [clave[r["rid"]] for r in rv]
    doc_k = {clave[r["rid"]]: r["doc"] for r in rv}
    while len(neg_az) < len(pos_az) and len(todos) > 1:
        a, b = g2.sample(todos, 2)
        if doc_k[a] != doc_k[b]:
            neg_az.append((a, b))
    out["azar"] = {"n_pos": len(pos_az), "n_neg": len(neg_az), "AUC": {}}
    for n in nombres:
        vp = [ag.valores(a, b, "buscador" if n == "R" else "locales")[n] or 0.0 for a, b in pos_az]
        vn = [ag.valores(a, b, "buscador" if n == "R" else "locales")[n] or 0.0 for a, b in neg_az]
        out["azar"]["AUC"][n] = round(auc(vp, vn), 6) if vp and vn and len(set(vp + vn)) > 1 else None
    return out


# ================================================================== orquestación
def _run(args, extra=None):
    e = dict(os.environ)
    e["HOME"] = os.path.join(TMP, "home", hashlib.sha256(repr(args).encode()).hexdigest()[:16])
    e.update(L.BASE_ENV)
    e.update(extra or {})
    shutil.rmtree(e["HOME"], ignore_errors=True)
    os.makedirs(e["HOME"])
    p = subprocess.run([PY, os.path.abspath(__file__)] + [str(a) for a in args], env=e, cwd=AQUI,
                       capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError("falló %s:\n%s" % (args, p.stderr[-4000:]))


def subir(rutas, mensaje):
    if SECO:
        return
    try:
        subprocess.run(["git", "-C", L.RAIZ, "add"] + rutas, check=True, capture_output=True)
        subprocess.run(["git", "-C", L.RAIZ, "commit", "-q", "-m", mensaje], check=True, capture_output=True)
        subprocess.run(["git", "-C", L.RAIZ, "fetch", "-q", "origin", RAMA], check=True, capture_output=True,
                       timeout=120)
        subprocess.run(["git", "-C", L.RAIZ, "rebase", "-q", "origin/" + RAMA], check=True, capture_output=True)
        subprocess.run(["git", "-C", L.RAIZ, "push", "-q", "origin", RAMA], check=True, capture_output=True,
                       timeout=120)
        print("subido:", mensaje, flush=True)
    except Exception as e:  # noqa: BLE001 — el resultado queda en disco
        print("no se pudo subir (%s): %r" % (mensaje, e), flush=True)


def un_idioma(idioma, escritor):
    final = os.path.join(RES, "v_%s_%s.json" % (escritor, idioma))
    if os.path.exists(final):
        return json.load(open(final))
    d = os.path.join(TMP, "%s_%s" % (escritor, idioma) + ("_seco" if SECO else ""))
    os.makedirs(d, exist_ok=True)
    ruta = os.path.join(d, "V.db")
    t0 = time.time()
    if not os.path.exists(ruta + ".info.json"):
        _run(["construir", idioma, escritor, ruta, ruta + ".info.json"])
    t_c = time.time() - t0
    info = json.load(open(ruta + ".info.json"))
    c = corpus(idioma)
    conceptos = [info["claves"][r["rid"]] for r in c if r["part"] != "G" and r["rid"] in info["claves"]]
    cj = os.path.join(d, "conceptos.json")
    json.dump(conceptos, open(cj, "w"))
    sal = ruta + ".med.json"
    if not os.path.exists(sal):
        _run(["medir", ruta, cj, sal], L.ENV_MEDIR)
    med = json.load(open(sal))
    an = analizar(idioma, escritor, c, med, info)
    an["t_construir_s"] = round(t_c, 1)
    an["t_total_s"] = round(time.time() - t0, 1)
    an["original_intacta"] = med.get("original_intacta")
    os.makedirs(RES, exist_ok=True)
    json.dump(an, open(final, "w"), ensure_ascii=False, indent=1)
    subir([final], "Paso 3 capa V: %s, escritor %s (corpus públicos)" % (idioma, escritor))
    return an


def main(escritor):
    os.makedirs(RES, exist_ok=True)
    t0 = time.time()
    for idioma in IDIOMAS:
        an = un_idioma(idioma, escritor)
        print(idioma, escritor, round(time.time() - t0), "pares V", an["n_pares_V"], "nodos", an["nodos_V_evaluables"],
              "MRR piso", an["MRR_piso"], flush=True)
    print("FIN", round(time.time() - t0), flush=True)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "construir":
        hijo_construir(*sys.argv[2:])
    elif cmd == "medir":
        L.hijo_medir(*sys.argv[2:])
    elif cmd == "todo":
        main(sys.argv[2] if len(sys.argv) > 2 else "mecanico")
    elif cmd == "exportar":
        exportar()
