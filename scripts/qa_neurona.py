"""La neurona de ranking dentro de la QA oficial (scripts/evaluar_qa.py).

POR QUÉ EXISTE
    Cada base de datos tiene su PROPIA neurona: aprende con los recuerdos de esa base
    y se guarda dentro de ella (tabla `neurona_estado`). La QA oficial mide una COPIA
    del snapshot congelado, que no trae neurona entrenada. Antes de esto, quien tenía
    la neurona trabajando en su DB viva corría la QA, veía la tabla de siempre y no
    sabía por qué la neurona "no aparecía". Este módulo hace tres cosas:

      1. DICE la verdad antes de medir: si la base medida tiene neurona o no, si tu
         DB viva sí la tiene, y qué comando usar para verla (`--con-neurona`).
      2. MIDE las dos columnas en la MISMA corrida: el orden que dio la fórmula a mano
         (antes de la neurona) y el orden que sirvió el motor (después de la neurona).
         Mismas preguntas, misma base, mismo instante: solo cambia quién ordena el top-5.
      3. VIGILA que no dañe: Recall@5 idéntico (por diseño solo reordena los mismos 5),
         el total de aciertos en 1er lugar no baja, y ninguna categoría pierde más de
         BIORAG_QA_NEURONA_TOL_CASOS casos en 1er lugar (default 1, el mismo piso que
         la neurona se exige a sí misma: BIORAG_NEURONA_TOL_CAMPEON).

CÓMO MIDE SIN CAMBIAR EL MOTOR
    Un "espía" envuelve `core.memory.neurona.reordenar` mientras corre la QA: anota la
    página que recibe (orden de la fórmula) y la que devuelve (orden servido) y mide
    cuánto tarda. No cambia ningún argumento ni ningún resultado. Si la neurona no
    tiene campeón, el motor ni siquiera la llama y las dos columnas son la misma.

QUÉ NO HACE
    No escribe en ninguna base original: lee el estado de tu DB viva en solo lectura
    (sin abrir el motor sobre ella). `--con-neurona` practica sobre la copia temporal
    de la QA, que se borra al terminar.
"""
import os
import sqlite3
import statistics
import time
from collections import defaultdict
from pathlib import Path

TOL_CASOS_DEFAULT = 1


# ───────────────────────── rutas ─────────────────────────

def _real(ruta):
    try:
        return str(Path(ruta).expanduser().resolve())
    except Exception:
        return str(ruta)


def misma_db(a, b):
    return bool(a) and bool(b) and _real(a) == _real(b)


def es_snapshot(ruta, base_dir):
    """True si la ruta está dentro de snapshots/ (la base para la que se escribieron los casos)."""
    if not ruta:
        return False
    return _real(ruta).startswith(_real(os.path.join(base_dir, "snapshots")) + os.sep)


def mostrar_ruta(ruta, base_dir):
    """Ruta corta para la pantalla: relativa al repo si está dentro."""
    r, b = _real(ruta), _real(base_dir)
    return os.path.relpath(r, b) if r.startswith(b + os.sep) else r


# ───────────────────────── estado guardado (solo lectura) ─────────────────────────

def leer_guardada(ruta):
    """Lo que la neurona dejó guardado en una base, SIN abrir el motor y sin escribir.

    Devuelve None si el archivo no existe o no es una base SQLite legible (por ejemplo
    un puntero de Git LFS sin descargar). Si es legible devuelve un dict con
    `campeon` (bool), `version`, `huella`, `stats` y `actualizado`.
    """
    import json
    if not ruta or not os.path.isfile(ruta):
        return None
    try:
        uri = Path(ruta).expanduser().resolve().as_uri() + "?mode=ro"
        con = sqlite3.connect(uri, uri=True)
    except Exception:
        return None
    try:
        try:
            con.execute("SELECT name FROM sqlite_master LIMIT 1").fetchall()
        except sqlite3.Error:
            return None  # no es una base SQLite
        info = dict(ruta=ruta, campeon=False, version=None, huella=None, stats={}, actualizado=None)
        try:
            fila = con.execute(
                "SELECT valor, actualizado FROM neurona_estado WHERE clave = 'pesos'").fetchone()
        except sqlite3.Error:
            return info  # la tabla no existe: la neurona nunca practicó en esa base
        if not fila:
            return info
        try:
            d = json.loads(fila[0])
        except Exception:
            return info
        info.update(campeon=bool(d.get("campeon")), version=d.get("version"), huella=d.get("huella"),
                    stats=d.get("stats") or {}, actualizado=fila[1])
        return info
    finally:
        con.close()


def vale_para_este_motor(info, version, huella):
    """Lo guardado solo se usa si es de esta versión de la neurona y de esta misma fórmula."""
    return bool(info) and info.get("version") == version and info.get("huella") == huella


# ───────────────────────── el espía ─────────────────────────

class Espia:
    """Envuelve `neurona.reordenar` para ver el orden ANTES y DESPUÉS de la neurona.

    Uso:
        with Espia(neurona) as espia:
            espia.nueva_busqueda()
            resultados, _ = db.buscar_por_frase(...)
            formula, servido, ok = espia.ordenes([r[0] for r in resultados])
    """

    def __init__(self, modulo):
        self.modulo = modulo
        self.original = None
        self.ultima = None
        self.llamadas = 0
        self.ms = []

    def __enter__(self):
        self.original = self.modulo.reordenar
        original = self.original

        def reordenar_espiado(motor, frase, pagina, v):
            t = time.perf_counter()
            salida = original(motor, frase, pagina, v)
            self.ms.append((time.perf_counter() - t) * 1000.0)
            self.llamadas += 1
            try:
                self.ultima = ([r[0] for r in pagina], [r[0] for r in salida])
            except Exception:
                self.ultima = None
            return salida

        self.modulo.reordenar = reordenar_espiado
        return self

    def __exit__(self, *exc):
        if self.original is not None:
            self.modulo.reordenar = self.original
        return False

    def nueva_busqueda(self):
        self.ultima = None

    def ordenes(self, servido):
        """(orden de la fórmula, orden servido, coherente).

        Si la neurona no fue llamada en esta búsqueda, la fórmula ES lo servido.
        `coherente` es False si lo servido no coincide con lo que devolvió la neurona
        (no debería pasar nunca; si pasa, la medición de esa búsqueda no es confiable).
        """
        servido = list(servido)
        if self.ultima is None:
            return servido, servido, True
        antes, despues = self.ultima
        n = len(servido)
        if despues[:n] != servido or len(antes) < n:
            return servido, servido, False
        return antes[:n], servido, True


def puesto(lista, esperado):
    """Puesto 1..n del esperado en la lista (0 si no está)."""
    for i, c in enumerate(lista):
        if c == esperado:
            return i + 1
    return 0


# ───────────────────────── las dos columnas ─────────────────────────

class Comparacion:
    """Acumula, caso por caso, el puesto con la fórmula sola y con la neurona."""

    def __init__(self):
        self.cats = defaultdict(lambda: dict(total=0, f1=0, n1=0, f5=0, n5=0, frr=0.0, nrr=0.0))
        self.cambios = dict(reordenadas=0, subio_al_1=0, bajo_del_1=0, mejoro=0, empeoro=0)
        self.incoherentes = 0

    def anotar(self, cat, p_formula, p_neurona, reordeno, coherente=True):
        """`p_*` = puesto 1..5 de la respuesta correcta (0 = no está o no cuenta)."""
        c = self.cats[cat]
        c["total"] += 1
        for p, k1, k5, krr in ((p_formula, "f1", "f5", "frr"), (p_neurona, "n1", "n5", "nrr")):
            if p:
                c[k5] += 1
                c[krr] += 1.0 / p
                if p == 1:
                    c[k1] += 1
        if not coherente:
            self.incoherentes += 1
        if reordeno:
            self.cambios["reordenadas"] += 1
        if p_formula != p_neurona:
            pf, pn = p_formula or 99, p_neurona or 99
            if pn < pf:
                self.cambios["mejoro"] += 1
            else:
                self.cambios["empeoro"] += 1
            if pn == 1:
                self.cambios["subio_al_1"] += 1
            if pf == 1:
                self.cambios["bajo_del_1"] += 1

    @staticmethod
    def _cifras(c):
        t = c["total"] or 1
        return dict(
            total=c["total"],
            hits1_formula=c["f1"], hits1_neurona=c["n1"],
            hits5_formula=c["f5"], hits5_neurona=c["n5"],
            recall_at_1_formula=round(100.0 * c["f1"] / t, 2),
            recall_at_1_neurona=round(100.0 * c["n1"] / t, 2),
            recall_at_5_formula=round(100.0 * c["f5"] / t, 2),
            recall_at_5_neurona=round(100.0 * c["n5"] / t, 2),
            mrr_formula=round(c["frr"] / t, 4),
            mrr_neurona=round(c["nrr"] / t, 4),
        )

    def resumen(self):
        total = dict(total=0, f1=0, n1=0, f5=0, n5=0, frr=0.0, nrr=0.0)
        for c in self.cats.values():
            for k in total:
                total[k] += c[k]
        return dict(
            categorias={k: self._cifras(v) for k, v in sorted(self.cats.items())},
            global_=self._cifras(total),
            cambios=dict(self.cambios),
            incoherentes=self.incoherentes,
        )


def tiempos(ms):
    if not ms:
        return dict(decisiones=0, mediana_ms=0.0, p95_ms=0.0, max_ms=0.0)
    orden = sorted(ms)
    p95 = orden[min(len(orden) - 1, int(round(0.95 * (len(orden) - 1))))]
    return dict(decisiones=len(ms), mediana_ms=round(statistics.median(orden), 3),
                p95_ms=round(p95, 3), max_ms=round(orden[-1], 3))


# ───────────────────────── control de daño ─────────────────────────

def tolerancia_casos():
    try:
        return max(0, int(os.environ.get("BIORAG_QA_NEURONA_TOL_CASOS", str(TOL_CASOS_DEFAULT))))
    except ValueError:
        return TOL_CASOS_DEFAULT


def control_de_dano(res, tol_casos):
    """Motivos por los que la neurona NO pasa en esta QA (lista vacía = pasa)."""
    motivos = []
    if res.get("incoherentes"):
        motivos.append(f"neurona: {res['incoherentes']} búsqueda(s) con medición incoherente "
                       f"(lo servido no coincide con lo que devolvió la neurona)")
    for cat, c in res["categorias"].items():
        if c["hits5_neurona"] != c["hits5_formula"]:
            motivos.append(f"neurona: {cat} cambió Recall@5 ({c['hits5_formula']} → {c['hits5_neurona']} casos); "
                           f"solo debe reordenar los mismos 5")
        perdidos = c["hits1_formula"] - c["hits1_neurona"]
        if perdidos > tol_casos:
            motivos.append(f"neurona: {cat} pierde {perdidos} casos en 1er lugar "
                           f"({c['recall_at_1_formula']:.2f}% → {c['recall_at_1_neurona']:.2f}%; "
                           f"tolerancia {tol_casos})")
    g = res["global_"]
    if g["hits1_neurona"] < g["hits1_formula"]:
        motivos.append(f"neurona: en total acierta MENOS en 1er lugar que la fórmula sola "
                       f"({g['recall_at_1_formula']:.2f}% → {g['recall_at_1_neurona']:.2f}%)")
    return motivos


# ───────────────────────── lo que se muestra ─────────────────────────

def _pct(x):
    return "—" if x is None else f"{100 * float(x):.1f} %"


def _historial(stats):
    n, a, r = int(stats.get("ciclos", 0)), int(stats.get("ascensos", 0)), int(stats.get("retiros", 0))
    return f"{n} prácticas · aprobó {a} {'vez' if a == 1 else 'veces'} · la quitaron {r}"


def _control(stats):
    u = stats.get("ultimo") or {}
    if u.get("guardia_mano") is None or u.get("guardia_campeon") is None:
        return None
    return (f"en su examen de control acierta el 1er lugar: fórmula {_pct(u['guardia_mano'])} "
            f"→ neurona {_pct(u['guardia_campeon'])}")


def lineas_aviso(ctx):
    """El aviso de la neurona, en palabras de cualquier persona.

    ctx: activa, medida (neurona.resumen de la copia), entrenada_aqui (dict o None),
         origen, origen_es_snapshot, guardada_origen (leer_guardada de la copia),
         viva (leer_guardada de la DB viva o None), viva_vale, ruta_viva, base_dir.
    """
    L = []
    base_dir = ctx.get("base_dir", ".")
    origen = mostrar_ruta(ctx["origen"], base_dir)
    tipo = "snapshot oficial" if ctx.get("origen_es_snapshot") else "NO es el snapshot oficial"
    L.append("🧠 NEURONA DE RANKING")
    L.append(f"   Base medida:  {origen}  ({tipo}; se mide una copia temporal)")
    medida = ctx.get("medida") or {}
    if not ctx.get("activa", True):
        L.append("   Neurona:      ⛔ apagada en este entorno (BIORAG_NEURONA=0)")
        L.append("                 → la tabla es la FÓRMULA A MANO SOLA (el piso)")
        return L
    if medida.get("campeon"):
        ent = ctx.get("entrenada_aqui")
        if ent:
            L.append(f"   Neurona:      🏆 ACTIVA — entrenada en esta copia con --con-neurona "
                     f"({ent['ciclos']} prácticas, {ent['segundos'] / 60:.0f} min)")
            L.append("                 Aprendió con preguntas que ella misma se hace con los recuerdos;")
            L.append("                 nunca vio las preguntas de esta QA.")
        else:
            L.append("   Neurona:      🏆 ACTIVA — entrenada con esta misma base")
            L.append(f"                 {_historial(medida)}")
        ctl = _control(medida)
        if ctl:
            L.append(f"                 {ctl}")
        L.append("   La tabla muestra lo que sirve el motor (fórmula + neurona). Al final de cada")
        L.append("   fila: 🧠 cuánto cambió la neurona el 1er lugar frente a la fórmula sola.")
        if not ctx.get("origen_es_snapshot"):
            L.append("   ⚠ Las preguntas de esta QA se escribieron para el snapshot oficial: en otra base")
            L.append("     algunas respuestas no existen o significan otra cosa, y el gate oficial está")
            L.append("     calibrado para el snapshot. No compares esta tabla con la del README;")
            L.append("     compara las dos columnas de aquí (fórmula sola → con neurona): misma base,")
            L.append("     mismas preguntas, misma corrida.")
        return L

    # Activa pero sin campeón en la base medida
    L.append("   Neurona:      ⏳ esta base no tiene una neurona entrenada")
    g = ctx.get("guardada_origen") or {}
    if g.get("campeon"):
        L.append("                 (tenía una, pero de otra versión del motor: no se usa y se vuelve")
        L.append("                 a aprender sola)")
    L.append("                 → la tabla es la FÓRMULA A MANO SOLA (el piso)")
    viva = ctx.get("viva")
    ruta_viva = mostrar_ruta(ctx.get("ruta_viva") or "", base_dir)
    viva_activa = bool(viva and viva.get("campeon") and ctx.get("viva_vale"))
    if viva_activa:
        s = viva.get("stats") or {}
        L.append(f"   Tu neurona:   🏆 ACTIVA en tu DB viva ({ruta_viva})")
        L.append(f"                 entrenada con esa memoria · {_historial(s)}")
        ctl = _control(s)
        if ctl:
            L.append(f"                 {ctl}")
        L.append("   Cada base tiene su propia neurona: lo que aprendió tu DB viva no viaja a la")
        L.append("   copia que mide esta QA. Por eso aquí no se ve (y eso es correcto).")
    elif viva and viva.get("campeon"):
        L.append(f"   Tu DB viva ({ruta_viva}) tiene una neurona, pero entrenada con otra versión")
        L.append("   del motor: allí tampoco se usa; se vuelve a entrenar sola con el uso.")
    L.append("   Para ver la neurona en esta QA (sin tocar ninguna base original):")
    L.append("     python scripts/evaluar_qa.py --con-neurona")
    L.append("       → entrena una neurona en la copia temporal y la mide (unos 20-25 min más)")
    if viva_activa:
        L.append(f"     BIORAG_PATH={ruta_viva} python scripts/evaluar_qa.py")
        L.append("       → mide tu propia memoria con tu propia neurona")
    return L


def sufijo_fila(c):
    """Lo que se agrega al final de una fila de la tabla cuando la neurona actuó."""
    d = c["recall_at_1_neurona"] - c["recall_at_1_formula"]
    if c["hits1_neurona"] == c["hits1_formula"] and abs(c["mrr_neurona"] - c["mrr_formula"]) < 5e-4:
        return f"🧠 = igual (fórmula sola {c['recall_at_1_formula']:.2f}%)"
    return f"🧠 {d:+.2f} pp (fórmula sola {c['recall_at_1_formula']:.2f}%)"


def lineas_resultado(res, t, motivos, tol_casos):
    """Bloque 'LA NEURONA EN ESTA QA' (solo cuando actuó)."""
    L = []
    L.append("LA NEURONA EN ESTA QA (misma base, mismas preguntas; solo cambia quién ordena el top-5)")
    L.append("-" * 80)
    L.append(f"{'Category':<22} | {'1er lugar (R@1): fórmula → neurona':<36} | MRR: fórmula → neurona")
    L.append("-" * 80)
    filas = list(res["categorias"].items()) + [("GLOBAL", res["global_"])]
    for cat, c in filas:
        if cat == "GLOBAL":
            L.append("-" * 80)
        d = c["recall_at_1_neurona"] - c["recall_at_1_formula"]
        r1 = f"{c['recall_at_1_formula']:>6.2f}% → {c['recall_at_1_neurona']:>6.2f}%  ({d:+.2f} pp)"
        mrr = f"{c['mrr_formula']:.3f} → {c['mrr_neurona']:.3f}"
        L.append(f"{cat:<22} | {r1:<36} | {mrr}")
    L.append("-" * 80)
    g, k = res["global_"], res["cambios"]
    L.append("  Recall@5 y falsos positivos: idénticos (la neurona solo reordena los mismos 5).")
    L.append(f"  Búsquedas que la neurona reordenó: {k['reordenadas']} de {g['total']}.")
    L.append(f"  La respuesta correcta SUBIÓ al 1er lugar en {k['subio_al_1']} y BAJÓ del 1er lugar en "
             f"{k['bajo_del_1']} (neto {k['subio_al_1'] - k['bajo_del_1']:+d}).")
    L.append(f"  Mejoró su puesto en {k['mejoro']} · empeoró en {k['empeoro']}.")
    if t["decisiones"]:
        L.append(f"  Tiempo de la neurona por búsqueda: mediana {t['mediana_ms']:.2f} ms · "
                 f"95 % bajo {t['p95_ms']:.2f} ms · peor {t['max_ms']:.2f} ms.")
    if motivos:
        L.append("  Control de daño: ✗ NO pasa")
        for m in motivos:
            L.append(f"    ✗ {m}")
    else:
        L.append(f"  Control de daño: ✅ pasa (ninguna categoría pierde más de {tol_casos} "
                 f"caso{'s' if tol_casos != 1 else ''} en 1er lugar; en total no baja)")
    return L


# ───────────────────────── --con-neurona ─────────────────────────

def leer_argumentos(argv):
    """Argumentos de evaluar_qa.py. El archivo de casos sigue siendo el 1er argumento opcional."""
    import argparse
    ap = argparse.ArgumentParser(
        prog="evaluar_qa.py",
        description="QA oficial de BioRAG (Recall@5/@1, MRR, falsos positivos) + la neurona de ranking.")
    ap.add_argument("casos", nargs="?", default="casos_qa_baseline_v1.jsonl",
                    help="archivo de casos en scripts/ (default casos_qa_baseline_v1.jsonl)")
    ap.add_argument("--con-neurona", action="store_true",
                    help="si la base medida no tiene neurona, entrena una en la copia temporal antes de medir "
                         "(la misma práctica de despertar_neurona; no toca la base original)")
    ap.add_argument("--ciclos", type=int, default=500,
                    help="prácticas para --con-neurona (default 500, como despertar_neurona)")
    ap.add_argument("--minutos", type=float, default=None,
                    help="tope de tiempo para la práctica de --con-neurona")
    return ap.parse_args(argv)
