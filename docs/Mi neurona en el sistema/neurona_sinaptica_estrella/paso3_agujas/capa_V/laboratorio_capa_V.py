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
  sin documento ni verdad. Se exporta el paquete con `exportar` y se importa su salida desde
  declaraciones_ciegas/ciego_{idioma}.jsonl (o /tmp/capa_V/). Sin ese archivo, este escritor no corre.

Guardia (decisión 27-11, noveno reenvío): sus recuerdos NO se ingieren en la base del Paso 3, para que ni el grado
(C3.7), ni el buscador (R), ni el grafo la vean. Las bases del escritor mecánico (27-11) sí la ingirieron; quedan
como se midieron (`guardia_en_base` en cada resultado).

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
- Secundario declarado antes de ver resultados (27-11, al ver solo el número de nodos de es): «lista ampliada», A en V
  con vecinos b en E ∪ V (nunca G); el modelo sigue ajustado solo con pares E–E.
- Regla de parada (decisión 27-11): si ninguna de las 12 limpias (en especial S + X) cumple C3.5 en cada idioma, se
  detiene y se reporta antes de inventar agujas o cambios.

Uso:
  python laboratorio_capa_V.py todo [mecanico|ciego] [idiomas…]   (CAPA_V_SECO=1: prueba en seco con 150 recuerdos)
  python laboratorio_capa_V.py exportar                   → /tmp/capa_V/paquete_ciego/ (para la sesión aislada)
  python laboratorio_capa_V.py validar es zh              → revisa ciego_{idioma}.jsonl; código de salida 1 si falla
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
MIN_NODOS, MIN_DOCS = 30, 10          # regla de potencia (decisión 27-11, hacia adelante: no se aplica al mecánico)
ENT_DF = (2, 3)                       # entidad rara: unidad presente en 2 o 3 documentos de E ∪ V …
ENT_MIN_REP = 2                       # … y repetida ≥ 2 veces dentro de cada uno de esos documentos


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


class CiegoInvalido(Exception):
    pass


def ruta_ciego(idioma):
    r = os.path.join(AQUI, "declaraciones_ciegas", "ciego_%s.jsonl" % idioma)
    return r if os.path.exists(r) else os.path.join(TMP, "ciego_%s.jsonl" % idioma)


def leer_ciego(idioma, c=None):
    """Salida de la sesión aislada: una línea JSON por recuerdo con id, concepto, dimensiones, syn, categoria,
    sustantivos_clave y bridges (contrato de `aprender`). El id del recuerdo se añade al nombre para que sea único.
    Endurecido (27-11): los ids se comparan con el corpus COMPLETO del idioma (aunque se construya en seco) y se
    rechazan JSON inválido, campos obligatorios ausentes, ids duplicados, ids extra y faltantes."""
    ruta = ruta_ciego(idioma)
    if not os.path.exists(ruta):
        raise CiegoInvalido("falta %s (declaraciones de la sesión aislada)" % ruta)
    ids_corpus = {r["rid"] for r in json.load(open(os.path.join(TMP, "corpus_%s.json" % idioma)))}
    out, errores, duplicados, extra = {}, [], [], []
    for n_linea, linea in enumerate(open(ruta, encoding="utf-8"), 1):
        if not linea.strip():
            continue
        try:
            x = json.loads(linea)
            dims = x.get("dimensiones") or {}
            if isinstance(dims, str):
                dims = json.loads(dims)
            if not isinstance(dims, dict):
                raise ValueError("dimensiones no es un objeto")
            rid = x["id"]
            if not str(x.get("concepto") or "").strip():
                raise ValueError("falta concepto")
            if not isinstance(x.get("bridges"), list):
                raise ValueError("bridges no es una lista")
        except (ValueError, KeyError, TypeError) as e:
            errores.append("línea %d: %s" % (n_linea, e))
            continue
        if rid in out:
            duplicados.append(rid)
            continue
        if rid not in ids_corpus:
            extra.append(rid)
            continue
        sk = x.get("sustantivos_clave") or ""
        if isinstance(sk, list):
            sk = ",".join(str(v) for v in sk)
        syn = x.get("syn") or ""
        if isinstance(syn, list):
            syn = ",".join(str(v) for v in syn)
        out[rid] = {"concepto": "%s_%s" % (str(x["concepto"]).strip(), rid), "dims": dims, "sk": str(sk),
                    "bridges": x["bridges"], "cat": x.get("categoria") or "General", "val": 0.0, "syn": str(syn)}
    faltan = sorted(ids_corpus - set(out) - set(duplicados))
    problemas = []
    if errores:
        problemas.append("%d líneas inválidas (p. ej. %s)" % (len(errores), errores[:3]))
    if duplicados:
        problemas.append("%d ids duplicados (p. ej. %s)" % (len(duplicados), duplicados[:3]))
    if extra:
        problemas.append("%d ids que no son del corpus (p. ej. %s)" % (len(extra), extra[:3]))
    if faltan:
        problemas.append("faltan %d declaraciones (p. ej. %s)" % (len(faltan), faltan[:3]))
    if problemas:
        raise CiegoInvalido("%s: %s" % (ruta, "; ".join(problemas)))
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


def validar(idioma):
    """Revisa ciego_{idioma}.jsonl ANTES de medir (no construye nada; no mira la verdad).
    Obligatorio (si falla, error): ids completos, únicos y del corpus; JSON y campos válidos; en CADA recuerdo, 5
    bridges aceptados por el motor con CERO rechazados (`validar_bridges`); ejes de dimensiones conocidos (los ejes son
    cerrados en el contrato); 2–10 sustantivos clave.
    Informativo (el contrato lo permite o solo avisa): valores fuera del catálogo (se auto-crean), recuerdos sin
    dimensiones, syn con menos de 8 entradas. Devuelve (ok, informe)."""
    sys.path.insert(0, L.RAIZ)
    import construir as c16
    from core.concept_hub import validar_bridges
    inf, fallos = Counter(), {}
    try:
        dec = leer_ciego(idioma)
    except CiegoInvalido as e:
        print(idioma, "NO VÁLIDO:", e, flush=True)
        return False, {"error": str(e)}
    cat = c16.catalogo_real()
    for rid, d in sorted(dec.items()):
        val, rech = validar_bridges(d["bridges"], d["concepto"].lower().replace(" ", "_"))
        if len(val) != 5 or rech:
            fallos.setdefault("bridges", []).append("%s: %s" % (rid, "; ".join(rech) or "%d válidos" % len(val)))
        dims = d["dims"] or {}
        inf["sin_dimensiones"] += not dims
        for eje, vals in dims.items():
            if eje not in cat:
                fallos.setdefault("eje_desconocido", []).append("%s: %s" % (rid, eje))
                continue
            for v in (vals if isinstance(vals, list) else [vals]):
                inf["valores"] += 1
                inf["valores_fuera_de_catalogo"] += v not in cat[eje]
        inf["syn_menos_de_8"] += len([x for x in d["syn"].split(",") if x.strip()]) < 8
        sk = [x for x in d["sk"].split(",") if x.strip()]
        if not 2 <= len(sk) <= 10:
            fallos.setdefault("sustantivos_clave", []).append("%s: %d" % (rid, len(sk)))
    inf["recuerdos"] = len(dec)
    informe = {"informativo": dict(inf), "fallos": {k: {"n": len(v), "ejemplos": v[:5]} for k, v in fallos.items()}}
    ok = not fallos
    print(idioma, "VÁLIDO" if ok else "NO VÁLIDO", json.dumps(informe, ensure_ascii=False), flush=True)
    return ok, informe


def sha256_archivo(ruta):
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def verificar_base(ruta, idioma):
    """Comprobación directa en la base (27-11): cada fila de largo_plazo y corto_plazo se identifica por el sufijo
    `_<rid>` que ambos escritores añaden al nombre. Exige: ninguna fila de la Guardia, ninguna fila sin rid conocido,
    y que el conjunto de rids de largo_plazo sea EXACTAMENTE E ∪ V del corpus usado (mismo total de filas)."""
    c = corpus(idioma)
    parte = {r["rid"]: r["part"] for r in json.load(open(os.path.join(TMP, "corpus_%s.json" % idioma)))}
    esperados = {r["rid"] for r in c if r["part"] != "G"}
    con = sqlite3.connect("file:%s?mode=ro" % ruta, uri=True)
    v = {}
    for tabla in ("largo_plazo", "corto_plazo"):
        filas = [x[0] for x in con.execute("SELECT concepto FROM %s" % tabla)]
        rids = [f.rsplit("_", 1)[-1] for f in filas]
        v[tabla] = {"filas": len(filas),
                    "de_guardia": sum(1 for r in rids if parte.get(r) == "G"),
                    "sin_rid_del_corpus": sum(1 for r in rids if r not in parte),
                    "rids_distintos": len(set(rids))}
    con.close()
    lp = v["largo_plazo"]
    con = sqlite3.connect("file:%s?mode=ro" % ruta, uri=True)
    rids_lp = {x[0].rsplit("_", 1)[-1] for x in con.execute("SELECT concepto FROM largo_plazo")}
    con.close()
    v["esperados_E_V"] = len(esperados)
    v["ok"] = (lp["de_guardia"] == 0 and v["corto_plazo"]["de_guardia"] == 0 and lp["sin_rid_del_corpus"] == 0
               and v["corto_plazo"]["sin_rid_del_corpus"] == 0 and lp["filas"] == len(esperados)
               and rids_lp == esperados)
    return v


# ================================================================== hijo: construir (motor real)
def hijo_construir(idioma, escritor, ruta, salida):
    reloj = lab.preparar_hijo("T", False, T0)
    L.reloj_sqlite(reloj)
    import construir as c16  # noqa: F401  (exp. 16: abrir/dormir)
    from core.mcp_server._shared import _resolver_dimensiones
    from core.memory_store import normalizar_sustantivos_clave, normalizar_sustantivos_clave_exacto
    from core.sinapsis import auto_vincular, vincular_por_sinonimos
    from core.concept_hub import validar_bridges, crear_hub, agregar_bridges
    # Guardia FUERA de la base (decisión 27-11): ni grado, ni buscador (R), ni grafo la ven
    c = [r for r in corpus(idioma) if r["part"] != "G"]
    dec = escritor_mecanico(c) if escritor == "mecanico" else leer_ciego(idioma)
    orden = sorted(c, key=lambda r: r["rid"])
    random.Random("%d|orden|%s" % (SEMILLA, idioma)).shuffle(orden)
    for ext in ("", "-wal", "-shm"):
        if os.path.exists(ruta + ext):
            os.remove(ruta + ext)
    st = {"cer": c16.abrir(ruta)}
    info = {"guardia_en_base": False,
            "sha_corpus": sha256_archivo(os.path.join(TMP, "corpus_%s.json" % idioma)),
            "sha_ciego": sha256_archivo(ruta_ciego(idioma)) if escritor == "ciego" else None,
            "bridges_rechazados": 0, "dims_inventadas": 0, "dims_error": 0, "t_sueno": 0.0, "n_suenos": 0,
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
    info["verificacion_base"] = verificar_base(ruta, idioma)
    if not info["verificacion_base"]["ok"]:   # sin .info.json la base no cuenta como construida
        raise SystemExit("verificación de la base falló: %s" % json.dumps(info["verificacion_base"]))
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
    guardia_en_base = info.get("guardia_en_base", True)   # bases del mecánico (27-11): la Guardia sí se ingirió
    if not guardia_en_base:
        assert not any(r["part"] == "G" and r["rid"] in clave for r in c), "recuerdo de la Guardia en la base"
    por_clave = {clave[r["rid"]]: r for r in c if r["rid"] in clave and r["part"] != "G"}
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
    # ---- verdad secundaria: documentos enlazados por una entidad rara (§4; decisión 27-11). Solo E ∪ V (la Guardia
    # no se lee). Sin listas: entidad = unidad con df de documento en ENT_DF y repetida ≥ ENT_MIN_REP veces en cada
    # documento. CIRCULAR para las agujas de superficie (X, S_sk, B): se informa aparte y no admite.
    cnt_doc = {}
    for r in c:
        if r["part"] == "G":
            continue
        cnt_doc.setdefault(r["doc"], Counter()).update(unidades_lista(r["contenido"]))
    df = Counter()
    for cn in cnt_doc.values():
        df.update(cn.keys())
    ent_doc = {d: {u for u, k in cn.items() if ENT_DF[0] <= df[u] <= ENT_DF[1] and k >= ENT_MIN_REP}
               for d, cn in cnt_doc.items()}
    _ent_r = {}

    def puente(ra, rb):
        if ra["doc"] == rb["doc"] or "G" in (ra["part"], rb["part"]):
            return False
        comunes = ent_doc.get(ra["doc"], set()) & ent_doc.get(rb["doc"], set())
        if not comunes:
            return False
        for r in (ra, rb):
            if r["rid"] not in _ent_r:
                _ent_r[r["rid"]] = L.U(r["contenido"])
        return bool(comunes & _ent_r[ra["rid"]] & _ent_r[rb["rid"]])
    filas = []   # (part, A, b, verdad, p, agujas..., doc de A)
    nombres = LIMPIAS + REFERENCIA
    cache = {}
    for a in sorted(vec):
        ra = por_clave[a]
        if ra["part"] == "G":
            continue
        for b, pr, p, t in vec[a]:
            rb = por_clave[b]
            if rb["part"] == "G":
                continue
            kk = (min(a, b), max(a, b))
            if kk not in cache:
                v = ag.valores(kk[0], kk[1], "locales")
                v.update(ag.valores(kk[0], kk[1], "buscador"))
                cache[kk] = v
            v = cache[kk]
            filas.append({"part": ra["part"] if rb["part"] == ra["part"] else ra["part"] + "amp", "A": a, "b": b,
                          "doc": ra["doc"], "y": int(ra["doc"] == rb["doc"]),
                          "yp": int(ra["doc"] == rb["doc"] or puente(ra, rb)),
                          "p": -100.0 * pr + p, "tipo": t, **{n: (v[n] if v[n] is not None else 0.0) for n in nombres}})
    E = [f for f in filas if f["part"] == "E"]
    V = [f for f in filas if f["part"] == "V"]
    out = {"idioma": idioma, "escritor": escritor, "guardia_en_base": guardia_en_base, "n_recuerdos": len(por_clave), "n_aristas_canal2": len(mejor),
           "n_pares_E": len(E), "n_pares_V": len(V), "positivos_E": sum(f["y"] for f in E),
           "positivos_V": sum(f["y"] for f in V), "info_construccion": {k: v for k, v in info.items() if k != "claves"},
           "tipos_V": dict(Counter(f["tipo"] for f in V)),
           "tipos_V_positivos": dict(Counter(f["tipo"] for f in V if f["y"]))}
    def preparar_listas(fs_, yk="y"):
        """Listas por nodo con ≥ 1 positivo y ≥ 1 negativo, y el RR del piso (orden a mano)."""
        li = {}
        for f in fs_:
            li.setdefault(f["A"], []).append(f)
        no = sorted(a for a, fs in li.items() if any(x[yk] for x in fs) and not all(x[yk] for x in fs))
        rng_ = random.Random(SEMILLA)
        rp = {a: rr_esperado([x["p"] for x in li[a]], [x[yk] for x in li[a]], rng_) for a in no}
        return {"listas": li, "nodos": no, "rr_piso": rp, "doc": {a: li[a][0]["doc"] for a in no}, "y": yk}
    # C3.5 (aclaración 27-11): UN modelo logístico compartido [piso, aguja(s)], ajustado con los pares de una partición
    # (E–E), y MRR evaluado POR NODO en la otra. Ajuste cruzado (decisión 27-11): E → V y V → E; se juntan los nodos
    # de las dos direcciones; IC95 por bootstrap de documentos. La Guardia no entra nunca.
    P = {"E": [f for f in filas if f["part"] == "E"], "V": V}
    AMP = {k: P[k] + [f for f in filas if f["part"] == k + "amp"] for k in ("E", "V")}
    LST = {(k, amp_, yk): preparar_listas(AMP[k] if amp_ else P[k], yk)
           for k in ("E", "V") for amp_ in (False, True) for yk in ("y", "yp")}
    listas, nodos, rr_piso = LST[("V", False, "y")]["listas"], LST[("V", False, "y")]["nodos"], \
        LST[("V", False, "y")]["rr_piso"]
    out["nodos_V_evaluables"] = len(nodos)
    out["nodos_V_con_lista"] = len(listas)
    out["MRR_piso"] = round(sum(rr_piso.values()) / len(nodos), 6) if nodos else None
    out["potencia"] = {}
    for amp_ in (False, True):
        for yk in ("y", "yp"):
            ns = {k: LST[(k, amp_, yk)]["nodos"] for k in ("E", "V")}
            docs = {LST[(k, amp_, yk)]["doc"][a] for k in ns for a in ns[k]}
            out["potencia"]["%s|%s" % ("ampliada" if amp_ else "primaria", "mismo_doc" if yk == "y" else
                                       "con_puente")] = {"nodos_E": len(ns["E"]), "nodos_V": len(ns["V"]),
                                                         "nodos": len(ns["E"]) + len(ns["V"]), "documentos": len(docs)}
    out["verdad_puente"] = {"documentos_con_entidad": sum(1 for v in ent_doc.values() if v),
                            "pares_puente_E": sum(f["yp"] - f["y"] for f in P["E"]),
                            "pares_puente_V": sum(f["yp"] - f["y"] for f in V)}

    def modelo(cols, filas_ent, yk):
        if not filas_ent or len({f[yk] for f in filas_ent}) < 2:
            return None
        XE = np.array([[f["p"]] + [float(f[c_]) for c_ in cols] for f in filas_ent])
        mu, sd = XE.mean(0), XE.std(0)
        sd[sd == 0] = 1.0
        w = logistica((XE - mu) / sd, np.array([f[yk] for f in filas_ent], float))
        return lambda f: float(((np.array([f["p"]] + [float(f[c_]) for c_ in cols]) - mu) / sd) @ w[:-1])

    def c35(cols, amp_=False, yk="y"):
        """Devuelve E→V (como antes), V→E y el cruzado (decide). Potencia: ≥ MIN_NODOS nodos y ≥ MIN_DOCS docs."""
        res, dif, docs_de = {}, {}, {}
        for ent, ev in (("E", "V"), ("V", "E")):
            lst = LST[(ev, amp_, yk)]
            m = modelo(cols, P[ent], yk)
            if m is None or not lst["nodos"]:
                res[ent + "→" + ev] = {"medible": False}
                continue
            rngm = random.Random(SEMILLA)
            rr = {a: rr_esperado([m(x) for x in lst["listas"][a]], [x[yk] for x in lst["listas"][a]], rngm)
                  for a in lst["nodos"]}
            d_ = {a: rr[a] - lst["rr_piso"][a] for a in lst["nodos"]}
            por_doc = {}
            for a in lst["nodos"]:
                por_doc.setdefault(lst["doc"][a], []).append(d_[a])
                dif[(ev, a)] = d_[a]
                docs_de[(ev, a)] = lst["doc"][a]
            lo, hi = bootstrap_docs(por_doc, lambda xs: sum(xs) / len(xs) if xs else None)
            res[ent + "→" + ev] = {"medible": True, "nodos": len(d_), "MRR": round(sum(rr.values()) / len(rr), 6),
                                  "dif": round(sum(d_.values()) / len(d_), 6), "IC95": [round(lo, 6), round(hi, 6)],
                                  "cumple": bool(lo is not None and lo > 0)}
        if not dif:
            res["cruzado"] = {"medible": False, "motivo": "sin nodos"}
            return res
        por_doc = {}
        for k_, v_ in dif.items():
            por_doc.setdefault(docs_de[k_], []).append(v_)
        n_docs = len(por_doc)
        lo, hi = bootstrap_docs(por_doc, lambda xs: sum(xs) / len(xs) if xs else None)
        cr = {"medible": True, "nodos": len(dif), "documentos": n_docs, "dif": round(sum(dif.values()) / len(dif), 6),
              "IC95": [round(lo, 6), round(hi, 6)]}
        if len(dif) < MIN_NODOS or n_docs < MIN_DOCS:
            cr.update({"medible": False, "motivo": "no medible por potencia (%d nodos, %d documentos)" % (len(dif), n_docs),
                       "cumple": False})
        else:
            cr["cumple"] = bool(lo is not None and lo > 0)
        res["cruzado"] = cr
        return res

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
                            "C3.5_ampliada": c35([n], True) if not constante else {"medible": False},
                            "C3.5_con_puente": c35([n], False, "yp") if not constante else {"medible": False},
                            "C3.7_rho": None if rho is None else round(rho, 6)}
    # combinaciones (informativas; la regla de parada mira cada aguja y el grupo S + X)
    var = [n for n in LIMPIAS if not out["agujas"][n]["constante_V"]]
    var_sx = [n for n in GRUPO_SX if n in var]
    for clave_, a_, y_ in (("combinaciones", False, "y"), ("combinaciones_ampliada", True, "y"),
                           ("combinaciones_con_puente", False, "yp")):
        out[clave_] = {"S+X": c35(var_sx, a_, y_) if var_sx else {"medible": False},
                       "12_limpias": c35(var, a_, y_) if var else {"medible": False},
                       "12_limpias+R": c35(var + ["R"], a_, y_) if var else {"medible": False}}
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


def _invalidar(d, ruta, final, motivo):
    print("caché invalidada (%s): se reconstruye" % motivo, flush=True)
    for x in os.listdir(d):
        if x.startswith("V.db") or x.startswith("limpia_V.db"):
            p_ = os.path.join(d, x)
            shutil.rmtree(p_) if os.path.isdir(p_) else os.remove(p_)
    if os.path.exists(final):
        os.remove(final)


def un_idioma(idioma, escritor):
    final = os.path.join(RES, "v_%s_%s.json" % (escritor, idioma))
    d = os.path.join(TMP, "%s_%s" % (escritor, idioma) + ("_seco" if SECO else ""))
    os.makedirs(d, exist_ok=True)
    ruta = os.path.join(d, "V.db")
    huellas = {"sha_corpus": sha256_archivo(os.path.join(TMP, "corpus_%s.json" % idioma)),
               "sha_ciego": sha256_archivo(ruta_ciego(idioma)) if escritor == "ciego" and
               os.path.exists(ruta_ciego(idioma)) else None}
    # caché: la base y el resultado solo se reutilizan si las huellas del corpus y del archivo ciego coinciden
    for previo in (ruta + ".info.json", final):
        if os.path.exists(previo):
            x = json.load(open(previo))
            x = x.get("info_construccion", x) if previo == final else x
            # ciego: huella ausente o distinta → invalida. Mecánico: solo si la huella existe (las bases y resultados
            # del mecánico del 27-11 no la tienen y no se tocan de forma retroactiva)
            distinto = [k for k in huellas if (escritor == "ciego" or (k != "sha_ciego" and k in x))
                        and x.get(k) != huellas[k]]
            if distinto:
                _invalidar(d, ruta, final, "cambió %s" % ", ".join(distinto))
                break
    if escritor == "ciego":   # siempre, también antes de reutilizar una base
        ok, informe = validar(idioma)
        json.dump(informe, open(os.path.join(d, "validacion.json"), "w"), ensure_ascii=False, indent=1)
        if not ok:
            raise SystemExit("ciego_%s.jsonl no pasa validar: no se mide" % idioma)
    if os.path.exists(final):
        return json.load(open(final))
    t0 = time.time()
    if not os.path.exists(ruta + ".info.json"):
        _run(["construir", idioma, escritor, ruta, ruta + ".info.json"])
    t_c = time.time() - t0
    info = json.load(open(ruta + ".info.json"))
    vb = verificar_base(ruta, idioma)   # de nuevo, directamente en la tabla, antes de medir y analizar
    if not vb["ok"]:
        raise SystemExit("verificación de la base falló: %s" % json.dumps(vb))
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
    an["verificacion_base"] = vb
    an["huellas"] = huellas
    os.makedirs(RES, exist_ok=True)
    json.dump(an, open(final, "w"), ensure_ascii=False, indent=1)
    subir([final], "Paso 3 capa V: %s, escritor %s (corpus públicos)" % (idioma, escritor))
    return an


def reanalizar(escritor):
    for idioma in IDIOMAS:
        d = os.path.join(TMP, "%s_%s" % (escritor, idioma) + ("_seco" if SECO else ""))
        ruta = os.path.join(d, "V.db")
        final = os.path.join(RES, "v_%s_%s.json" % (escritor, idioma))
        if not (os.path.exists(ruta + ".med.json") and os.path.exists(final)):
            print(idioma, "sin medición")
            continue
        viejo = json.load(open(final))
        an = analizar(idioma, escritor, corpus(idioma), json.load(open(ruta + ".med.json")),
                      json.load(open(ruta + ".info.json")))
        for k in ("t_construir_s", "t_total_s", "original_intacta"):
            an[k] = viejo.get(k)
        json.dump(an, open(final, "w"), ensure_ascii=False, indent=1)
        print(idioma, "reanalizado")


def main(escritor, idiomas=IDIOMAS):
    os.makedirs(RES, exist_ok=True)
    t0 = time.time()
    for idioma in idiomas:
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
        main(sys.argv[2] if len(sys.argv) > 2 else "mecanico", tuple(sys.argv[3:]) or IDIOMAS)
    elif cmd == "exportar":
        exportar()
    elif cmd == "validar":
        resultados = [validar(i)[0] for i in (sys.argv[2:] or IDIOMAS)]
        sys.exit(0 if all(resultados) else 1)
    elif cmd == "analizar":
        reanalizar(sys.argv[2] if len(sys.argv) > 2 else "mecanico")
