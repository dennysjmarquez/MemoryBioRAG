"""Paso 3, capa L (limpieza): invariancia, bucle, costo, hubs y vacuidad de las agujas candidatas.

Protocolo: ../PROTOCOLO_PASO3.md (§2 inventario, §3 exclusiones, §4 capa L, §5 criterios C3.1–C3.8, §5.2 tipo).
Autorizado por Dennys el 27-11 («Puedes ejecutar la Capa L del Paso 3»). Solo sintético, en /tmp, motor sin tocar.

Qué NO mide: valor. Las AUC de esta capa se informan marcadas «con filtración léxica por construcción» (el mundo lo
escribe quien conoce la verdad) y NO cuentan para admitir ninguna aguja (protocolo §4).

Mundo: `h2_medicion/mundo_sintetico.py` (4 escrituras; D, D∪I0, D∪I1) + declaraciones sintéticas deterministas por
recuerdo (idénticas en los tres mundos): nombres con palabras inventadas, dimensiones del catálogo real (y algunas
inventadas → auto_generada=1), sustantivos clave, 5 bridges, `vincular_con` (aristas `manual`), categorías y
recuerdos inmunes (valencia 0,85 y Principle). Sinónimos sintéticos como en el ciclo 2.
Construcción con el motor real (camino de `aprender`), sueño T (motor tal cual) cada 50 recuerdos, reloj diario,
corte del buscador tras D. Medición en hijo con BIORAG_NEURONA=0 y BIORAG_PPMI_WEIGHT=0 (protocolo §6);
G_ciego/R sobre la copia limpia (sin sinapsis, latentes, asociaciones ni dimensiones auto_generada=1).

Bucle (C3.2): copia de D con (a) sinapsis automáticas falsas + dimensiones emergentes falsas + CSV `asociaciones`
falso, y (b) aristas `manual` falsas. Las agujas que no deben leer el grafo tienen que salir idénticas.

Uso:  python laboratorio_capa_L.py todo        (CAPA_L_SECO=1 para una prueba en seco pequeña)
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
from concurrent.futures import ThreadPoolExecutor

AQUI = os.path.dirname(os.path.abspath(__file__))
NSE = os.path.abspath(os.path.join(AQUI, "..", ".."))
H2M = os.path.join(NSE, "h2_medicion")
H2C = os.path.join(NSE, "h2_ciclo2")
EXP16 = os.path.abspath(os.path.join(NSE, "..", "experimento_16_protocolo_ns1_sintetico"))
RAIZ = os.path.abspath(os.path.join(NSE, "..", "..", ".."))
for p in (RAIZ, EXP16, H2M, H2C, AQUI):
    if p not in sys.path:
        sys.path.insert(0, p)

import laboratorio_h2 as lab  # noqa: E402
import mundo_sintetico as ms  # noqa: E402

PY = sys.executable
SECO = bool(os.environ.get("CAPA_L_SECO"))
TMP = "/tmp/capa_L"
RES = os.path.join(TMP, "resultados_seco") if SECO else os.path.join(AQUI, "resultados")
SEMILLAS = (7,) if SECO else (7, 11, 23)
TAMANOS = (60,) if SECO else (800, 2400)
MUNDOS = ("D", "DI0", "DI1")
T0 = 1_600_000_000.0
DIA = 86400.0
CADA = 50
TOPK = 10
RAMA = "arena/da3df5df-memorybiorag"
BASE_ENV = dict(lab.BASE_ENV)
# BIORAG_DMN_SINTESIS_ACTIVA=0: al abrir una base el motor crea hasta 8 aristas `dmn_synthesized` (top-40 por peso,
# global); sin esto la copia limpia vuelve a tener sinapsis (hallado en la prueba en seco).
ENV_MEDIR = {"BIORAG_NEURONA": "0", "BIORAG_PPMI_WEIGHT": "0", "BIORAG_DMN_SINTESIS_ACTIVA": "0"}
EJES_TEMATICOS = ("dominio", "entidad", "intencion", "cualia")
EJES_TONO = ("cualidad", "emocion")
CATEGORIAS = ("Project", "Lesson", "System", "Architecture", "Personal", "Cognition", "Relation", "Profile")
PRIORIDAD = {"manual": 0, "sinonimo_explicito": 1, "co_semantica": 2, "latente_confirmada": 3, "co_ocurrencia": 4,
             "co_nombre": 5, "legacy_csv": 6, "manual_v7": 7, "test": 8, "pmi_hebbiano": 9}
TIPOS_AUTOMATICOS_FALSOS = ("co_ocurrencia", "pmi_hebbiano", "co_semantica", "latente_confirmada",
                            "sinonimo_explicito", "co_nombre")


# ================================================================== declaraciones sintéticas (deterministas)
def _rng(*partes):
    return random.Random("capaL|" + "|".join(str(p) for p in partes))


def _palabras(r, esc):
    """Palabras del recuerdo tal como las escribió el generador (latinas: por espacios; CJK: unidades)."""
    if esc in ms.SIN_ESPACIOS:
        return sorted(lab.unidades(r["contenido"]))
    return sorted(set(r["contenido"].split()))


def _sk_valido(w):
    w = unicodedata.normalize("NFC", w)
    return 2 <= len(w) <= 15 and all(unicodedata.category(c)[0] in "LMN" or c == "_" for c in w)


def declarar(m, catalogo):
    """Declaraciones de un «agente» sintético. Deterministas por semilla y recuerdo: el mismo recuerdo declara lo mismo
    en D, D∪I0 y D∪I1. Conoce la verdad (tema): por eso esta capa no mide valor."""
    sem = m["semilla"]
    temas = m["temas"]
    perfil = {}
    for tid in sorted(temas):
        g = _rng(sem, "perfil", tid)
        perfil[tid] = {
            "dims": {eje: g.sample(catalogo[eje], 2 if eje == "entidad" and g.random() < 0.4 else 1)
                     for eje in EJES_TEMATICOS + EJES_TONO},
            "cat": g.choice(CATEGORIAS),
        }
    pareja_puente = {}
    for p in m["puentes"]:
        a, b = p["temas"]
        pareja_puente.setdefault(a, []).append(b)
        pareja_puente.setdefault(b, []).append(a)
    previos_por_tema, previos_por_conj = {}, {}
    out = {}
    for i, r in enumerate(m["recuerdos"]):
        g = _rng(sem, "decl", i)
        tid, esc, conj = r["tema"], r["esc"], r["conj"]
        pal = _palabras(r, esc)
        tema_w = [w for w in r["palabras_tema"] if _sk_valido(w)] or [w for w in pal if _sk_valido(w)]
        otras = [w for w in pal if w not in tema_w and _sk_valido(w)]
        # nombre: dos palabras inventadas del propio recuerdo + índice (único)
        w1 = tema_w[0] if tema_w else "n"
        w2 = g.choice(otras) if otras else (tema_w[-1] if tema_w else "m")
        concepto = "%s_%s_%d" % (w1, w2, i)
        # dimensiones: perfil del tema con ruido (15 % reemplazada al azar), 20 % una extra al azar,
        # 5 % una inventada (→ auto_generada = 1); puentes: 50 % añade el dominio del tema pareja
        dims = {}
        for eje, vals in perfil[tid]["dims"].items():
            dims[eje] = [v if g.random() >= 0.15 else g.choice(catalogo[eje]) for v in vals]
        if g.random() < 0.20:
            eje = g.choice(EJES_TEMATICOS + EJES_TONO)
            dims[eje] = sorted(set(dims[eje] + [g.choice(catalogo[eje])]))
        if r["entidades"] and pareja_puente.get(tid) and g.random() < 0.5:
            otro = g.choice(pareja_puente[tid])
            dims["dominio"] = sorted(set(dims["dominio"] + perfil[otro]["dims"]["dominio"]))
        if g.random() < 0.05:
            dims["cualia"] = sorted(set(dims["cualia"] + ["inventada_%s" % g.choice("abcdefgh")]))
        dims = {k: sorted(set(v)) for k, v in dims.items()}
        # sustantivos clave: 2–3 del tema + entidades + 1 de ruido (palabra del propio texto)
        sk = list(dict.fromkeys(tema_w[:g.choice((2, 3))] + [e for e in r["entidades"] if _sk_valido(e)]))
        if otras and g.random() < 0.5:
            sk.append(g.choice(otras))
        if len(sk) < 2:
            sk += [w for w in pal if _sk_valido(w) and w not in sk][:2 - len(sk)]
        sk = sk[:10]
        # 5 bridges (uno por ángulo): 2 palabras del vocabulario del tema (no necesariamente de este recuerdo);
        # 15 %: uno de otro tema de la misma escritura (ruido); entidades puente como bridge si las hay
        voc = [w for w in temas[tid]["voc"] if _sk_valido(w)]
        mismos = sorted(t for t in temas if temas[t]["esc"] == esc and temas[t]["conj"] == conj and t != tid)
        bridges, vistos = [], set()
        sep = "" if esc in ms.SIN_ESPACIOS else " "
        for k, ang in enumerate(("sinonimo", "problema", "solucion", "situacion", "ingenuo")):
            fuente = voc
            if mismos and g.random() < 0.15:
                fuente = [w for w in temas[g.choice(mismos)]["voc"] if _sk_valido(w)] or voc
            for _intento in range(50):
                ws = g.sample(fuente, 2) if len(fuente) >= 2 else fuente * 2
                if k == 3 and r["entidades"] and _intento == 0:
                    ws = [r["entidades"][0], ws[0]]
                if _intento >= 10:   # vocabulario corto: se completa con palabras del propio recuerdo
                    ws = ws[:1] + [g.choice([w for w in pal if _sk_valido(w)] or ws)]
                txt = sep.join(ws)
                if esc in ms.SIN_ESPACIOS:   # validar_bridges: CJK cuenta len//2 unidades → ≥ 4 caracteres
                    while len(txt) < 4:
                        txt += g.choice(fuente)
                if txt not in vistos:
                    break
            vistos.add(txt)
            bridges.append({"text": txt, "angle": ang, "weight": g.choice((0.6, 0.8, 1.0))})
        # categoría: la del tema (80 %) o al azar; inmunes: 2 % Principle (valencia 1,0), 2 % valencia 0,85
        cat = perfil[tid]["cat"] if g.random() < 0.8 else g.choice(CATEGORIAS)
        val = 0.0
        u = g.random()
        if u < 0.02:
            cat, val = "Principle", 1.0
        elif u < 0.04:
            val = 0.85
        # vincular_con (arista `manual`): 12 % enlaza con un recuerdo ANTERIOR del mismo conjunto (o de D si es I1):
        # 85 % del mismo tema (o del tema pareja de un puente), 15 % ruido al azar
        vinc = []
        if g.random() < 0.12:
            cand = list(previos_por_tema.get(tid, []))
            for otro in pareja_puente.get(tid, []):
                cand += previos_por_tema.get(otro, [])
            pool = previos_por_conj.get(conj, []) + (previos_por_conj.get("D", []) if conj == "I1" else [])
            if cand and g.random() < 0.85:
                vinc = [g.choice(cand)]
            elif pool:
                vinc = [g.choice(pool)]
        out[r["concepto"]] = {"concepto": concepto, "dims": dims, "sk": ",".join(sk), "bridges": bridges,
                              "cat": cat, "val": val, "vincular_con": vinc}
        previos_por_tema.setdefault(tid, []).append(concepto)
        previos_por_conj.setdefault(conj, []).append(concepto)
    return out


def sinonimos(m):
    """Como `laboratorio_ciclo2.sinonimos` (35 %, 1 de cada 10 de otro tema), con una corrección: el sinónimo de ruido
    sale de otro tema del MISMO conjunto (I0 → I0). En el ciclo 2 salía siempre de D, y así I0 llevaba palabras de D
    y dejaba de ser «verdaderamente irrelevante» (§5.3). I1 puede tomarlo de D (I1 sí está relacionado)."""
    temas_por = {}
    for tid, t in sorted(m["temas"].items()):
        temas_por.setdefault((t["conj"], t["esc"]), []).append(tid)
    out = {}
    for r in m["recuerdos"]:
        rng = random.Random("syn|%d|%s" % (m["semilla"], r["concepto"]))
        if rng.random() >= 0.35:
            continue
        tid = r["tema"]
        if rng.random() < 0.10:
            fuente = "I0" if r["conj"] == "I0" else "D"
            otros = [t for t in temas_por.get((fuente, r["esc"]), []) if t != tid]
            if otros:
                tid = rng.choice(otros)
        out[r["concepto"]] = rng.choice(m["temas"][tid]["voc"][:2])
    return out


def mundo_completo(semilla, n_D):
    import construir as c16
    m = ms.generar(semilla, n_D)
    cat = c16.catalogo_real()
    dec = declarar(m, cat)
    syn = sinonimos(m)
    for r in m["recuerdos"]:
        d = dec[r["concepto"]]
        r["id_gen"] = r["concepto"]
        r["syn"] = syn.get(r["concepto"], "")
        r.update({"decl": d})
        r["concepto"] = d["concepto"]
    return m


# ================================================================== reloj simulado también en SQLite
RELOJ_SQLITE = os.environ.get("CAPA_L_RELOJ_SQLITE") == "1"


def reloj_sqlite(reloj):
    """El motor compara con strftime('%s','now') / datetime('now') de SQLite (reloj real; consolidation.py L497,
    schema.py L523/L714/L722/L1236, lexical_learning.py L109/L110/L378). En el laboratorio el reloj es simulado, así
    que se sustituyen esas dos funciones en cada conexión del hijo: 'now' (o sin argumento) pasa a ser reloj.t; lo
    demás se delega a una conexión :memory: sin tocar. Solo laboratorio; el motor no cambia (27-11)."""
    import threading
    orig = sqlite3.connect
    if getattr(orig, "_reloj_lab", False):
        return

    def envolver(*a, **k):
        con = orig(*a, **k)
        h = orig(":memory:", check_same_thread=False)
        lk = threading.Lock()

        def hacer(nombre, con_fmt):
            def f(*args):
                args = list(args)
                i = 1 if con_fmt else 0
                if len(args) <= i or args[i] == "now":
                    args = args[:i] + [reloj.t, "unixepoch"] + args[i + 1:]
                with lk:
                    return h.execute("SELECT %s(%s)" % (nombre, ",".join("?" * len(args))), args).fetchone()[0]
            return f
        con.create_function("strftime", -1, hacer("strftime", True))
        con.create_function("datetime", -1, hacer("datetime", False))
        return con
    envolver._reloj_lab = True
    sqlite3.connect = envolver


# ================================================================== hijo: construir
def hijo_construir(semilla, n_D, mundo, ruta, salida):
    semilla, n_D = int(semilla), int(n_D)
    reloj = lab.preparar_hijo("T", False, T0)
    if RELOJ_SQLITE:
        reloj_sqlite(reloj)
    import construir as c16
    from core.mcp_server._shared import _resolver_dimensiones
    from core.memory_store import normalizar_sustantivos_clave, normalizar_sustantivos_clave_exacto
    from core.sinapsis import auto_vincular, vincular_por_sinonimos
    from core.concept_hub import validar_bridges, crear_hub, agregar_bridges
    m = mundo_completo(semilla, n_D)
    D = [r for r in m["recuerdos"] if r["conj"] == "D"]
    I = [r for r in m["recuerdos"] if r["conj"] == ("I1" if mundo == "DI1" else "I0")]
    for ext in ("", "-wal", "-shm"):
        if os.path.exists(ruta + ext):
            os.remove(ruta + ext)
    st = {"cer": c16.abrir(ruta)}
    info = {"bridges_rechazados": 0, "vinculos": 0, "dims_inventadas": 0, "t_sueno": 0.0, "n_suenos": 0}

    def guardar(r):
        cer, d = st["cer"], r["decl"]
        clave = d["concepto"].lower().replace(" ", "_")
        sk_ex = normalizar_sustantivos_clave_exacto(d["sk"])
        sk_norm = normalizar_sustantivos_clave(sk_ex)
        dims, _, err, meta = _resolver_dimensiones(cer, json.dumps(d["dims"]))
        if err:
            raise RuntimeError(err)
        info["dims_inventadas"] += len(meta.get("dimensiones_creadas") or [])
        cer.percibir_corto_plazo(clave, r["contenido"], r["syn"], d["cat"], dims, predicados=None,
                                 valencia_somatica=d["val"], sustantivos_clave=sk_norm,
                                 sustantivos_clave_exactos=sk_ex)
        auto_vincular(cer, clave, r["contenido"])
        if r["syn"]:
            vincular_por_sinonimos(cer, clave, r["syn"])
        for t in d["vincular_con"]:
            t = t.strip().lower().replace(" ", "_")
            if t and t != clave:
                try:
                    cer.establecer_asociacion(clave, t)
                    info["vinculos"] += 1
                except Exception:
                    pass
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

    corte = {}
    for fase, lote in (("D", D), ("I", I)):
        if fase == "I" and mundo == "D":
            break
        for k, r in enumerate(lote, 1):
            reloj.t += 1
            if not (fase == "I" and mundo == "Dt"):   # Dt: control de reloj, mismo tiempo y sueños sin documentos
                with contextlib.redirect_stdout(io.StringIO()):
                    guardar(r)
            if k % CADA == 0:
                dormir()
        dormir()
        if fase == "D":
            with contextlib.redirect_stdout(io.StringIO()):
                st["cer"].conn.commit()
                st["cer"].cerrar_sistema()
            st["cer"] = c16.abrir(ruta)
            corte = {"baseline_rowid": st["cer"]._search_baseline_rowid}
    with contextlib.redirect_stdout(io.StringIO()):
        st["cer"].conn.commit()
        st["cer"].cerrar_sistema()
    con = sqlite3.connect(ruta)
    con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    con.close()
    info.update({"corte": corte, "reloj_final": reloj.t, "reloj_sqlite": RELOJ_SQLITE})
    if RELOJ_SQLITE:   # autocomprobación: el 'now' de SQLite es el reloj simulado
        c2 = sqlite3.connect(ruta)
        info["sqlite_now"] = float(c2.execute("SELECT strftime('%s','now')").fetchone()[0])
        c2.close()
        assert abs(info["sqlite_now"] - reloj.t) < 2, info
    json.dump(info, open(salida, "w"), ensure_ascii=False)


# ================================================================== hijo: medir
def leer_rasgos(ruta):
    con = sqlite3.connect("file:%s?mode=ro" % ruta, uri=True)
    rec = {}
    for c, cont, ske, cat, est in con.execute(
            "SELECT l.concepto, l.contenido, COALESCE(l.sustantivos_clave_exactos, l.sustantivos_clave, ''), "
            "COALESCE(c.name, ''), l.estado FROM largo_plazo l LEFT JOIN categories c ON c.id = l.categoria"):
        rec[c] = {"contenido": cont, "sk": ske or "", "cat": cat, "estado": est, "dims": [], "bridges": []}
    for c, did, eje, auto in con.execute(
            "SELECT lpd.concepto, lpd.dimension_id, t.nombre, COALESCE(d.auto_generada, 0) "
            "FROM largo_plazo_dimensiones lpd JOIN dimensiones_semanticas d ON d.id = lpd.dimension_id "
            "JOIN tipos_dimension t ON t.id = d.tipo_id"):
        if c in rec:
            rec[c]["dims"].append([did, eje, int(auto)])
    try:
        for hub, txt, ang, w in con.execute("SELECT hub_id, bridge_text, angle, weight FROM concept_hub_bridges"):
            c = hub[4:] if hub.startswith("hub_") else hub
            if c in rec:
                rec[c]["bridges"].append([txt, ang, w])
    except sqlite3.OperationalError:
        pass
    for r in rec.values():
        r["dims"].sort()
        r["bridges"].sort()
    aristas = [list(x) for x in con.execute("SELECT origen, destino, tipo, peso FROM sinapsis")]
    n_corto = con.execute("SELECT COUNT(*) FROM corto_plazo").fetchone()[0]
    dims_nombre = {i: n for i, n in con.execute("SELECT id, name FROM dimensiones_semanticas")}
    con.close()
    return rec, aristas, n_corto, dims_nombre


def hijo_medir(ruta, conceptos_json, salida, buscar="1"):
    """Rasgos de la base (solo lectura) + Top-K ciego de cada recuerdo de D sobre la copia limpia."""
    sha_antes = lab.sha_tablas(ruta)
    rec, aristas, n_corto, dims_nombre = leer_rasgos(ruta)
    top, t_busq = {}, 0.0
    limpia = {}
    if buscar == "1":
        _r = lab.preparar_hijo("T", False, T0 + 10 ** 8)
        if RELOJ_SQLITE:
            reloj_sqlite(_r)
        d = os.path.join(os.path.dirname(ruta), "limpia_" + os.path.basename(ruta))
        src = sqlite3.connect("file:%s?mode=ro" % ruta, uri=True)
        dst = sqlite3.connect(d)
        src.backup(dst)
        src.close()
        dst.execute("DELETE FROM sinapsis")
        dst.execute("DELETE FROM sinapsis_latentes")
        dst.execute("UPDATE largo_plazo SET asociaciones = ''")
        dst.execute("DELETE FROM largo_plazo_dimensiones WHERE dimension_id IN "
                    "(SELECT id FROM dimensiones_semanticas WHERE auto_generada = 1)")
        dst.commit()
        dst.close()
        from core.memory_store import SQLiteMemoryBioRAG
        with contextlib.redirect_stdout(io.StringIO()):
            cer = SQLiteMemoryBioRAG(db_path=d)
        cer.conn.commit()
        assert cer.cursor.execute("SELECT COUNT(*) FROM sinapsis").fetchone()[0] == 0, "copia limpia con sinapsis"
        pristina = sqlite3.connect(":memory:")
        cer.conn.backup(pristina)
        for c in json.load(open(conceptos_json)):
            if c not in rec:
                continue
            pista = " ".join(s.strip() for s in rec[c]["sk"].split(",") if s.strip())
            if not pista:
                top[c] = []
                continue
            t = time.perf_counter()
            with contextlib.redirect_stdout(io.StringIO()):
                res, _ = cer.buscar_por_frase(pista, limite=TOPK, profundidad="profundo", usar_inferencia=False,
                                              context_window=0, ignore_peso_sinaptico=True)
            t_busq += time.perf_counter() - t
            top[c] = [r[0] for r in (res or [])][:TOPK]
            cer.conn.commit()
            pristina.backup(cer.conn)
        limpia = {
            "sinapsis_fin": cer.cursor.execute("SELECT COUNT(*) FROM sinapsis").fetchone()[0],
            "asociaciones_fin": cer.cursor.execute(
                "SELECT COUNT(*) FROM largo_plazo WHERE asociaciones <> ''").fetchone()[0],
            "emergentes_fin": cer.cursor.execute(
                "SELECT COUNT(*) FROM largo_plazo_dimensiones WHERE dimension_id IN "
                "(SELECT id FROM dimensiones_semanticas WHERE auto_generada = 1)").fetchone()[0]}
        with contextlib.redirect_stdout(io.StringIO()):
            cer.cerrar_sistema()
        os.remove(d)
    json.dump({"rasgos": rec, "aristas": aristas, "n_corto_plazo": n_corto, "top": top, "t_busqueda": t_busq,
               "n_busquedas": len(top), "copia_limpia": limpia, "dims_nombre": dims_nombre,
               "original_intacta": lab.sha_tablas(ruta) == sha_antes},
              open(salida, "w"), ensure_ascii=False)


# ================================================================== bucle: inyecciones falsas (sin el motor)
def inyectar(origen, destino, conceptos_D, semilla, modo):
    shutil.copyfile(origen, destino)
    g = _rng(semilla, "falsas", modo, len(conceptos_D))
    con = sqlite3.connect(destino)
    cs = sorted(conceptos_D)
    n = max(20, len(cs) // 2)
    hechas = 0
    tipos = ("manual",) if modo == "manual" else TIPOS_AUTOMATICOS_FALSOS
    existentes = {(a, b) for a, b in con.execute("SELECT origen, destino FROM sinapsis")}
    while hechas < n:
        a, b = g.sample(cs, 2)
        if (a, b) in existentes or (b, a) in existentes:
            continue
        con.execute("INSERT INTO sinapsis (origen, destino, peso, tipo, creado_en) VALUES (?, ?, ?, ?, ?)",
                    (a, b, round(g.uniform(0.3, 0.9), 2), g.choice(tipos), T0))
        existentes.add((a, b))
        hechas += 1
    otros = 0
    if modo == "auto":
        tid = con.execute("SELECT id FROM tipos_dimension WHERE nombre = 'cualia'").fetchone()[0]
        ids = []
        for k in range(8):
            con.execute("INSERT INTO dimensiones_semanticas (name, description, tipo_id, auto_generada) "
                        "VALUES (?, '', ?, 1)", ("emergente_falsa_%d" % k, tid))
            ids.append(con.execute("SELECT last_insert_rowid()").fetchone()[0])
        for c in g.sample(cs, max(5, len(cs) // 4)):
            con.execute("INSERT OR IGNORE INTO largo_plazo_dimensiones (concepto, dimension_id) VALUES (?, ?)",
                        (c, g.choice(ids)))
            otros += 1
        for c in g.sample(cs, max(5, len(cs) * 3 // 10)):
            con.execute("UPDATE largo_plazo SET asociaciones = ? WHERE concepto = ?",
                        (",".join(g.sample(cs, 3)), c))
    con.commit()
    con.close()
    return {"sinapsis_falsas": hechas, "dims_o_csv_falsos": otros}


# ================================================================== agujas (padre)
_U = {}


def U(texto):
    if texto not in _U:
        _U[texto] = lab.unidades(texto)
    return _U[texto]


def _nk(s):
    return unicodedata.normalize("NFKC", s).casefold().strip()


class Agujas:
    """Calcula las agujas de un par (a, b) con los datos de UN mundo medido."""

    def __init__(self, med, idf, dims_nombre_ref):
        self.r = med["rasgos"]
        self.top = med["top"]
        self.idf = idf
        self.dref = dims_nombre_ref
        self.dn = {int(k): v for k, v in med["dims_nombre"].items()}
        self.vec = {}
        self.manual = {}
        self.tipos = {}
        for o, d, t, _p in med["aristas"]:
            if o not in self.r or d not in self.r or o == d:
                continue
            self.vec.setdefault(o, set()).add(d)
            self.vec.setdefault(d, set()).add(o)
            self.tipos.setdefault(frozenset((o, d)), set()).add(t)
            if t == "manual":
                self.manual.setdefault(o, set()).add(d)
                self.manual.setdefault(d, set()).add(o)
        self._cache = {}

    def _f(self, c):
        if c not in self._cache:
            x = self.r[c]
            sk = [_nk(s) for s in x["sk"].split(",") if s.strip()]
            dims = [(i, e) for i, e, a in x["dims"] if not a]
            texto = {"concepto": _nk(c.replace("_", " ")), "sk": " ".join(sk), "contenido": _nk(x["contenido"])}
            self._cache[c] = {
                "sk": set(sk), "skl": sk,
                "tem": {i for i, e in dims if e in EJES_TEMATICOS}, "tono": {i for i, e in dims if e in EJES_TONO},
                "todas": {i for i, e in dims},
                "texto": texto, "u_todo": U(texto["concepto"] + " " + texto["contenido"] + " " + texto["sk"]),
                "bridges": [(U(t), a, w) for t, a, w in x["bridges"]],
                "u_bridges": set().union(*[U(t) for t, _a, _w in x["bridges"]]) if x["bridges"] else set(),
                "cat": x["cat"]}
        return self._cache[c]

    @staticmethod
    def _jac(a, b):
        return len(a & b) / len(a | b) if (a or b) else 0.0

    def _x(self, fa, fb, campo=None):
        if not fa["skl"]:
            return 0.0
        if campo is None:
            t = fb["texto"]["concepto"] + " " + fb["texto"]["sk"] + " " + fb["texto"]["contenido"]
        else:
            t = fb["texto"][campo]
        return sum(1 for s in fa["skl"] if s and s in t) / len(fa["skl"])

    def _b(self, fa, fb):
        hits = []
        for ub, ang, w in fb["bridges"]:
            if ub and len(ub & (fa["u_todo"] | fa["u_bridges"])) / len(ub) >= 0.5:
                hits.append((ang, w))
        return hits

    def _idf(self, ids):
        s = 0.0
        for i in ids:
            if self.dref.get(str(i)) is not None and self.dref[str(i)] == self.dn.get(i):
                s += float(self.idf.get(str(i), 0.0))
        return s

    def _k_dir(self, a, b):
        vs = sorted(self.vec.get(a, ()))
        if b not in vs:
            return None
        fa = self._f(a)
        punt = {v: self._jac(fa["tem"], self._f(v)["tem"]) + self._x(fa, self._f(v)) for v in vs}
        orden = sorted(vs, key=lambda v: (-punt[v], v))
        return 1.0 - orden.index(b) / len(vs)

    def valores(self, a, b, grupo="todas"):
        fa, fb = self._f(a), self._f(b)
        out = {}
        if grupo in ("todas", "locales"):
            out["S_tem"] = round(self._jac(fa["tem"], fb["tem"]), 9)
            out["S_tono"] = round(self._jac(fa["tono"], fb["tono"]), 9)
            out["S_sk"] = len(fa["sk"] & fb["sk"])
            out["S_idf"] = round(self._idf(fa["todas"] & fb["todas"]), 9)
            xa, xb = self._x(fa, fb), self._x(fb, fa)
            out["X_min"], out["X_max"] = round(min(xa, xb), 9), round(max(xa, xb), 9)
            for campo in ("concepto", "sk", "contenido"):
                out["X_" + campo] = round(max(self._x(fa, fb, campo), self._x(fb, fa, campo)), 9)
            hits = self._b(fa, fb) + self._b(fb, fa)
            out["B_flag"] = int(bool(hits))
            out["B_weight"] = max((w for _a, w in hits), default=0.0)
            out["B_angulos"] = len({a_ for a_, _w in hits})
            out["Cat"] = int(bool(fa["cat"]) and fa["cat"] == fb["cat"])
        if grupo in ("todas", "grafo"):
            ka, kb = self._k_dir(a, b), self._k_dir(b, a)
            ks = [k for k in (ka, kb) if k is not None]
            out["K"] = round(sum(ks) / len(ks), 9) if ks else None
            ts = self.tipos.get(frozenset((a, b)), set())
            out["T2"] = min((PRIORIDAD.get(t, 50) for t in ts), default=None)
            out["T1"] = min(ts, key=lambda t: (PRIORIDAD.get(t, 50), t)) if ts else None
            out["L1_local"] = int(bool((self.manual.get(a, set()) & self.manual.get(b, set())) - {a, b}))
        if grupo in ("todas", "buscador"):
            ta, tb = self.top.get(a), self.top.get(b)
            if ta is None or tb is None:
                out["G_ciego"] = None
                out["R"] = None
            else:
                out["G_ciego"] = round(math.log1p(len((set(ta) & set(tb)) - {a, b})), 9)
                out["R"] = int(b in ta or a in tb)
        return out


AGUJAS_LOCALES = ("S_tem", "S_tono", "S_sk", "S_idf", "X_min", "X_max", "X_concepto", "X_sk", "X_contenido",
                  "B_flag", "B_weight", "B_angulos", "Cat")
AGUJAS_BUSCADOR = ("G_ciego", "R")
AGUJAS_GRAFO = ("K", "T1", "T2", "L1_local")
TODAS = AGUJAS_LOCALES + AGUJAS_BUSCADOR + AGUJAS_GRAFO
UMBRAL_INV = {**{a: 1.0 for a in AGUJAS_LOCALES}, **{a: 0.98 for a in AGUJAS_BUSCADOR}}


def auc(pos, neg):
    if not pos or not neg:
        return None
    todos = sorted([(v, 1) for v in pos] + [(v, 0) for v in neg])
    rang, i = {}, 0
    suma_pos = 0.0
    while i < len(todos):
        j = i
        while j < len(todos) and todos[j][0] == todos[i][0]:
            j += 1
        r = (i + j + 1) / 2.0
        suma_pos += r * sum(1 for k in range(i, j) if todos[k][1] == 1)
        i = j
    return round((suma_pos - len(pos) * (len(pos) + 1) / 2.0) / (len(pos) * len(neg)), 4)


def _rangos(v):
    o = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v)
    i = 0
    while i < len(o):
        j = i
        while j + 1 < len(o) and v[o[j + 1]] == v[o[i]]:
            j += 1
        for k in range(i, j + 1):
            r[o[k]] = (i + j) / 2.0
        i = j + 1
    return r


def spearman(x, y):
    if len(x) < 3:
        return None
    rx, ry = _rangos(x), _rangos(y)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    sxy = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    sx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    sy = math.sqrt(sum((b - my) ** 2 for b in ry))
    return round(sxy / (sx * sy), 4) if sx and sy else None


# ================================================================== orquestación
def _run(args, extra=None):
    e = dict(os.environ)
    e["HOME"] = os.path.join(TMP, "home", hashlib.sha256(repr(args).encode()).hexdigest()[:16])
    e.update(BASE_ENV)
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
        subprocess.run(["git", "-C", RAIZ, "add"] + rutas, check=True, capture_output=True)
        subprocess.run(["git", "-C", RAIZ, "commit", "-q", "-m", mensaje], check=True, capture_output=True)
        subprocess.run(["git", "-C", RAIZ, "push", "-q", "origin", RAMA], check=True, capture_output=True,
                       timeout=120)
        print("subido:", mensaje, flush=True)
    except Exception as e:  # noqa: BLE001 — el resultado queda en disco; se sube en el siguiente intento
        print("no se pudo subir (%s): %r" % (mensaje, e), flush=True)


def una_config(semilla, n_D):
    final = os.path.join(RES, "config_s%d_n%d.json" % (semilla, n_D))
    if os.path.exists(final):
        return json.load(open(final))
    d = os.path.join(TMP, "s%d_n%d" % (semilla, n_D))
    os.makedirs(d, exist_ok=True)
    m = mundo_completo(semilla, n_D)
    en_D = sorted(r["concepto"].lower() for r in m["recuerdos"] if r["conj"] == "D")
    cj = os.path.join(d, "conceptos_D.json")
    json.dump(en_D, open(cj, "w"))

    # n=2400: cada construcción llega a ~2,4 GB de RSS; dos a la vez → OOM en 3,9 GB (27-11). Un solo worker.
    hilos = 1 if n_D >= 2400 else 2

    def construir(mundo):
        ruta = os.path.join(d, mundo + ".db")
        if os.path.exists(ruta + ".info.json"):   # info se escribe al final de hijo_construir: base completa
            return ruta
        _run(["construir", semilla, n_D, mundo, ruta, ruta + ".info.json"])
        return ruta

    with ThreadPoolExecutor(hilos) as ex:
        rutas = dict(zip(MUNDOS, ex.map(construir, MUNDOS)))
    falsas = {}
    rutas["Dfa"] = os.path.join(d, "Dfa.db")
    falsas["Dfa"] = inyectar(rutas["D"], rutas["Dfa"], en_D, semilla, "auto")
    rutas["Dfm"] = os.path.join(d, "Dfm.db")
    falsas["Dfm"] = inyectar(rutas["D"], rutas["Dfm"], en_D, semilla, "manual")

    def medir(w):
        sal = rutas[w] + ".med.json"
        _run(["medir", rutas[w], cj, sal, "0" if w == "Dfm" else "1"], ENV_MEDIR)
        return w, json.load(open(sal))

    with ThreadPoolExecutor(hilos) as ex:
        med = dict(ex.map(medir, list(rutas)))
    info = {w: json.load(open(rutas[w] + ".info.json")) for w in MUNDOS}
    an = analizar(semilla, n_D, m, med, info, falsas)
    os.makedirs(RES, exist_ok=True)
    json.dump(an, open(final, "w"), ensure_ascii=False, indent=1)
    shutil.rmtree(d, ignore_errors=True)
    subir([final], "Paso 3 capa L: s%d |D|=%d (sintético)" % (semilla, n_D))
    return an


def analizar(semilla, n_D, m, med, info, falsas):
    hc = json.load(open(os.path.join(RAIZ, "db", "hebbian_clusters.json")))
    idf, dref = hc["idf"], hc["dim_names"]
    idx = {r["concepto"].lower(): r for r in m["recuerdos"]}
    en_D = {c for c, r in idx.items() if r["conj"] == "D"}
    Ut = {c: lab.unidades(r["contenido"]) for c, r in idx.items()}
    midx = {"puentes": {}}
    for p in m["puentes"]:
        midx["puentes"].setdefault(tuple(p["temas"]), []).append(p["entidad"])
    texto = lambda a, b: lab.coinciden(Ut[a["concepto"].lower()], Ut[b["concepto"].lower()])  # noqa: E731
    verdad = lambda a, b: ms.verdad_par(midx, idx[a], idx[b], texto)  # noqa: E731
    A = {w: Agujas(med[w], idf, dref) for w in med}
    # población: pares D–D con al menos una arista en el mundo D (lo que ordena el canal 2)
    P = sorted(tuple(sorted(k)) for k in A["D"].tipos if set(k) <= en_D)
    out = {"semilla": semilla, "n_D": n_D, "n_pares_D": len(P), "info": info, "falsas": falsas,
           "copia_limpia": {w: med[w]["copia_limpia"] for w in med},
           "original_intacta": {w: med[w]["original_intacta"] for w in med},
           "n_corto_plazo": {w: med[w]["n_corto_plazo"] for w in med},
           "busqueda_s_por_consulta": {w: (med[w]["t_busqueda"] / med[w]["n_busquedas"]) if med[w]["n_busquedas"]
                                       else None for w in med}}
    # valores en D (y costo por par)
    vD, costo = {}, {}
    for grupo in ("locales", "buscador", "grafo"):
        t = time.perf_counter()
        for p in P:
            vD.setdefault(p, {}).update(A["D"].valores(*p, grupo=grupo))
        costo[grupo] = (time.perf_counter() - t) / max(1, len(P))
    out["costo_s_por_par"] = costo
    # C3.1 invariancia (D∪I0, D∪I1) y C3.2 bucle (Dfa, Dfm) — mismo par, otro mundo
    inv = {}
    for w in ("DI0", "DI1", "Dfa", "Dfm"):
        cmp = {a: [0, 0] for a in TODAS}
        ejemplos = {}
        for p in P:
            if not all(c in A[w].r for c in p):
                continue
            vw = A[w].valores(*p, grupo="todas" if w != "Dfm" else "locales")
            if w != "Dfm":
                pass
            else:
                vw.update(A[w].valores(*p, grupo="grafo"))
            for a in TODAS:
                if a not in vw:
                    continue
                cmp[a][1] += 1
                if vw[a] == vD[p].get(a):
                    cmp[a][0] += 1
                elif a not in ejemplos:
                    ejemplos[a] = [list(p), vD[p].get(a), vw[a]]
        inv[w] = {a: {"iguales": c[0], "n": c[1], "frac": round(c[0] / c[1], 6) if c[1] else None}
                  for a, c in cmp.items()}
        inv[w]["_ejemplos_distintos"] = ejemplos
    out["invariancia_y_bucle"] = inv
    # diagnóstico del buscador: ¿el Top-K ciego de cada recuerdo de D es idéntico en el otro mundo?
    diag = {}
    for w in ("DI0", "DI1", "Dfa"):
        tD, tW = med["D"]["top"], med[w]["top"]
        comunes = [c for c in tD if c in tW]
        ajenos = sum(1 for c in comunes for x in tW[c] if x not in en_D)
        diag[w] = {"n": len(comunes), "top_identico": sum(tD[c] == tW[c] for c in comunes),
                   "mismo_conjunto": sum(set(tD[c]) == set(tW[c]) for c in comunes),
                   "apariciones_no_D_en_tops": ajenos}
    out["topk_ciego_identico"] = diag
    # §5.2 tipo: existencia y tipo de arista entre recuerdos de D, D frente a D∪I0 / D∪I1
    tip = {}
    for w in ("DI0", "DI1"):
        por = {}
        claves = set(k for k in A["D"].tipos if set(k) <= en_D) | set(k for k in A[w].tipos if set(k) <= en_D)
        for k in claves:
            tD, tW = A["D"].tipos.get(k, set()), A[w].tipos.get(k, set())
            for t in tD | tW:
                x = por.setdefault(t, {"en_D": 0, "en_W": 0, "en_ambos": 0})
                x["en_D"] += t in tD
                x["en_W"] += t in tW
                x["en_ambos"] += (t in tD and t in tW)
        for t, x in por.items():
            x["identicas_frac"] = round(x["en_ambos"] / (x["en_D"] + x["en_W"] - x["en_ambos"]), 6)
        tip[w] = por
    out["tipo_invariancia"] = tip
    # distribución de tipos por escritura (mundo D) y verdad
    dist = {}
    for p in P:
        esc = idx[p[0]]["esc"] if idx[p[0]]["esc"] == idx[p[1]]["esc"] else "mixta"
        v = verdad(*p)
        for t in A["D"].tipos[frozenset(p)]:
            dist.setdefault(esc, {}).setdefault(t, {}).setdefault(v, 0)
            dist[esc][t][v] += 1
    out["tipos_por_escritura_y_verdad"] = dist
    # AUC por escritura (marcada: filtración léxica por construcción), vacuidad, hubs
    grado = {c: len(A["D"].vec.get(c, ())) for c in en_D}
    aucs, vac, hubs, hubs_clase = {}, {}, {}, {}
    for esc in ms.ESCRITURAS:
        Pe = [p for p in P if idx[p[0]]["esc"] == esc and idx[p[1]]["esc"] == esc]
        lab_v = {p: verdad(*p) in ("tema", "puente") for p in Pe}
        aucs[esc], vac[esc], hubs[esc], hubs_clase[esc] = {}, {}, {}, {}
        for a in TODAS:
            if a == "T1":
                continue
            vals = [(vD[p][a], lab_v[p], p) for p in Pe if vD[p].get(a) is not None]
            if a == "T2":
                vals = [(-v, l, p) for v, l, p in vals]
            pos = [v for v, l, _ in vals if l]
            neg = [v for v, l, _ in vals if not l]
            aucs[esc][a] = {"auc": auc(pos, neg), "n_pos": len(pos), "n_neg": len(neg)}
            vac[esc][a] = len({v for v, _l, _p in vals}) <= 1
            xs, ys = [], []
            for v, _l, p in vals:
                for c in p:
                    xs.append(v)
                    ys.append(grado[c])
            hubs[esc][a] = spearman(xs, ys)
            # diagnóstico (no cambia C3.7): la misma correlación dentro de cada clase de verdad
            por_clase = {}
            for clase in (True, False):
                xc, yc = [], []
                for v, l_, p in vals:
                    if l_ is clase:
                        for c in p:
                            xc.append(v)
                            yc.append(grado[c])
                por_clase["pos" if clase else "neg"] = spearman(xc, yc)
            hubs_clase[esc][a] = por_clase
    out["auc_filtracion_lexica"] = aucs
    out["vacua"] = vac
    out["spearman_grado"] = hubs
    out["spearman_grado_por_clase"] = hubs_clase
    out["recuerdos_inmunes"] = {w: sum(1 for c, x in med[w]["rasgos"].items()
                                       if x["cat"] in ("Principle", "Protocol")) for w in med}
    out["estado_D_en_D"] = {e: sum(1 for c in en_D if med["D"]["rasgos"].get(c, {}).get("estado") == e)
                            for e in ("activo", "dormido")}
    return out


def main():
    os.makedirs(RES, exist_ok=True)
    t0 = time.time()
    for n in TAMANOS:
        for s in SEMILLAS:
            an = una_config(s, n)
            print("config", s, n, round(time.time() - t0), an["n_pares_D"], flush=True)
    print("FIN", round(time.time() - t0), flush=True)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "construir":
        hijo_construir(*sys.argv[2:])
    elif cmd == "medir":
        hijo_medir(*sys.argv[2:])
    elif cmd == "todo":
        main()
