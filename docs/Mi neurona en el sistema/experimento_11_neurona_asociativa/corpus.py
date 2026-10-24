"""Las memorias del experimento 11 (todas con una VERDAD conocida de "tiene que ver").

Cada constructor devuelve un dict con:
  nombre, idioma, textos
  verdad(a, b)  1 = sí tienen que ver, 0 = no, None = dudoso (no se usa)
  orden         momento en que llegó cada recuerdo (número) o None si la
                memoria no tiene tiempo real. Solo se usa tiempo REAL.
  etiquetas     etiquetas gruesas de cada recuerdo (como las dims del motor)
                o None. Nunca son la verdad: son más gruesas que ella.

  noticias     Reuters-21578 (inglés, 2,000 noticias). Tienen que ver si tratan
               el mismo tema (mismas categorías, Jaccard >= .5); no, si no
               comparten ninguna.
  diccionario  WordNet (inglés, definiciones). Tienen que ver si WordNet los une
               directamente (es-un, parte-de, opuesto, derivado, dominio...);
               no, si no hay camino de 1 ni 2 pasos.
  relatos      Brown (inglés, 1,200 trozos de 150 palabras de 300 textos).
               Tienen que ver si son trozos del MISMO texto (mismo "episodio").
  reportes     Títulos de reportes de fallas (inglés técnico, MUY cortos) de 5
               programas. Tienen que ver si son del mismo programa.
  codigo       Métodos de la librería estándar de Python. Tienen que ver si son
               de la misma clase; no, si son de módulos distintos.
  charla       Chat real (NPS Chat): ventanas de 10 mensajes. Tienen que ver si
               son de la misma sala y día (mismo episodio). Tiempo real.
  noticias_es  Noticias de agencia en ESPAÑOL (CESS-ESP). Tienen que ver si son
               trozos de la misma noticia. Tiempo real (fecha).
  machado      Obra de Machado de Assis (PORTUGUÉS). Tienen que ver si son
               trozos de la misma obra. Etiqueta: el género.
  dennys       La memoria real de Dennys (español). Verdad parcial: las 381
               conexiones `manual` (las unió una persona a propósito) = sí.
               Del resto no se sabe la verdad: se usa solo para comparar.
"""
import re
import sqlite3

import numpy as np

NLTK = "/tmp/e11/nltk_data"


def _nltk():
    import nltk
    if NLTK not in nltk.data.path:
        nltk.data.path.insert(0, NLTK)
    return nltk


def noticias(n=2000, semilla=1, por_tema=60):
    from nltk.corpus import reuters
    _nltk()
    rng = np.random.default_rng(semilla)
    ids = list(reuters.fileids())
    rng.shuffle(ids)
    cuenta, elegidos = {}, []
    for f in ids:
        cats = reuters.categories(f)
        if not cats:
            continue
        c0 = cats[0]
        if cuenta.get(c0, 0) >= por_tema:
            continue
        cuenta[c0] = cuenta.get(c0, 0) + 1
        elegidos.append(f)
        if len(elegidos) >= n:
            break
    textos, cats, orden = [], [], []
    for f in elegidos:
        orden.append(float(f.split("/")[1]))      # NEWID: orden real de llegada (1987)
        raw = reuters.raw(f).strip().split("\n", 1)
        titulo = raw[0].strip().title()
        cuerpo = " ".join((raw[1] if len(raw) > 1 else "").split()[:120])
        textos.append(f"{titulo}. {cuerpo}")
        cats.append(frozenset(reuters.categories(f)))

    def verdad(a, b):
        ca, cb = cats[a], cats[b]
        inter = len(ca & cb)
        if inter == 0:
            return 0
        return 1 if inter / len(ca | cb) >= 0.5 else None
    tot = sum(1 for a in range(len(cats)) for b in range(a + 1, len(cats)) if verdad(a, b) == 1)
    return dict(nombre="noticias", idioma="en", textos=textos, verdad=verdad, orden=orden, etiquetas=None,
                positivos_totales=tot)


_REL = ("hypernyms", "hyponyms", "instance_hypernyms", "instance_hyponyms",
        "member_holonyms", "member_meronyms", "part_holonyms", "part_meronyms",
        "substance_holonyms", "substance_meronyms", "similar_tos", "also_sees",
        "entailments", "causes", "attributes", "verb_groups", "topic_domains",
        "region_domains", "usage_domains", "in_topic_domains", "in_region_domains",
        "in_usage_domains")


def _vecinos_wn(s):
    v = set()
    for r in _REL:
        v.update(getattr(s, r)())
    for l in s.lemmas():
        for d in l.derivationally_related_forms() + l.antonyms() + l.pertainyms():
            v.add(d.synset())
    v.discard(s)
    return v


def diccionario(n=2000, semillas=700, semilla=2):
    _nltk()
    from nltk.corpus import wordnet as wn
    rng = np.random.default_rng(semilla)
    todos = [s for s in wn.all_synsets() if s.pos() in "nva"]
    rng.shuffle(todos)
    elegidos, vistos = [], set()
    for s in todos[:semillas]:
        if s.name() in vistos:
            continue
        grupo = [s] + sorted(_vecinos_wn(s), key=lambda x: x.name())[:2]
        for g in grupo:
            if g.name() not in vistos and len(elegidos) < n:
                vistos.add(g.name())
                elegidos.append(g)
    # relleno al azar hasta n (recuerdos "sueltos", como en una memoria real)
    for s in todos[semillas:]:
        if len(elegidos) >= n:
            break
        if s.name() not in vistos:
            vistos.add(s.name())
            elegidos.append(s)
    textos = []
    for s in elegidos:
        nombres = " ".join(l.replace("_", " ") for l in s.lemma_names())
        textos.append(f"{nombres}. {s.definition()}. " + " ".join(s.examples()))
    vec = [_vecinos_wn(s) for s in elegidos]
    nombre = [s for s in elegidos]

    def verdad(a, b):
        sa, sb = nombre[a], nombre[b]
        if sb in vec[a] or sa in vec[b]:
            return 1
        if vec[a] & vec[b]:
            return None
        for x in vec[a]:
            if sb in _vecinos_wn(x):
                return None
        return 0
    etiquetas = [frozenset([s.lexname()]) for s in elegidos]   # 45 grupos gruesos (noun.animal...)
    donde = {s: i for i, s in enumerate(elegidos)}
    tot = len({(min(a, donde[x]), max(a, donde[x])) for a in range(len(elegidos)) for x in vec[a] if x in donde})
    return dict(nombre="diccionario", idioma="en", textos=textos, verdad=verdad, orden=None, etiquetas=etiquetas,
                positivos_totales=tot)


def relatos(docs=300, trozos=4, palabras=150, semilla=3):
    _nltk()
    from nltk.corpus import brown
    rng = np.random.default_rng(semilla)
    ids = list(brown.fileids())
    rng.shuffle(ids)
    textos, doc, etq = [], [], []
    for f in ids[:docs]:
        w = [x for x in brown.words(f)]
        g = frozenset(brown.categories(f))
        for t in range(trozos):
            pedazo = w[t * palabras:(t + 1) * palabras]
            if len(pedazo) < palabras // 2:
                break
            textos.append(" ".join(pedazo))
            doc.append(f)
            etq.append(g)

    def verdad(a, b):
        return 1 if doc[a] == doc[b] else 0
    return dict(nombre="relatos", idioma="en", textos=textos, verdad=verdad, orden=None, etiquetas=etq,
                positivos_totales=_pares_de_grupos(doc))


def _pares_de_grupos(grupo):
    """Cuántos pares 'sí' hay en total cuando la verdad es 'mismo grupo'."""
    from collections import Counter
    return int(sum(c * (c - 1) // 2 for c in Counter(grupo).values()))


def _trozos(palabras, largo, maximo):
    out = []
    for t in range(maximo):
        p = palabras[t * largo:(t + 1) * largo]
        if len(p) < largo // 2:
            break
        out.append(" ".join(p))
    return out


def reportes(por_programa=400, semilla=4):
    """Títulos de reportes de fallas (vienen etiquetados palabra/ETIQUETA: se quita la etiqueta)."""
    import os
    R = os.path.join(NLTK, "corpora", "problem_reports")
    rng = np.random.default_rng(semilla)
    textos, prog = [], []
    for p in ("apache", "eclipse", "firefox", "linux", "openoffice"):
        lineas = []
        for ln in open(os.path.join(R, p), encoding="utf-8", errors="replace"):
            w = [t.rsplit("/", 1)[0] for t in ln.split()]
            if len(w) >= 4:
                lineas.append(" ".join(w))
        lineas = sorted(set(lineas))
        for k in rng.choice(len(lineas), min(por_programa, len(lineas)), replace=False):
            textos.append(lineas[k])
            prog.append(p)

    def verdad(a, b):
        return 1 if prog[a] == prog[b] else 0
    return dict(nombre="reportes", idioma="en", textos=textos, verdad=verdad, orden=None, etiquetas=None,
                positivos_totales=_pares_de_grupos(prog))


def codigo(maximo=1500, por_clase=6, semilla=5):
    """Métodos de clases de la librería estándar. El texto NO incluye el nombre de la clase."""
    import ast
    import glob
    import os
    import sysconfig
    rng = np.random.default_rng(semilla)
    raiz = sysconfig.get_paths()["stdlib"]
    archivos = sorted(f for f in glob.glob(os.path.join(raiz, "**", "*.py"), recursive=True)
                      if "test" not in f and "idlelib" not in f and "site-packages" not in f)
    rng.shuffle(archivos)
    textos, clase, modulo = [], [], []
    for f in archivos:
        try:
            src = open(f, encoding="utf-8").read()
            arbol = ast.parse(src)
        except Exception:
            continue
        for nodo in arbol.body:
            if not isinstance(nodo, ast.ClassDef):
                continue
            metodos = [m for m in nodo.body if isinstance(m, ast.FunctionDef)
                       and not (m.name.startswith("__") and m.name.endswith("__"))]
            metodos = [m for m in metodos if 3 <= (m.end_lineno - m.lineno) <= 60]
            if len(metodos) < 3:
                continue
            for m in metodos[:por_clase]:
                txt = ast.get_source_segment(src, m) or ""
                textos.append(txt.replace(nodo.name, " "))
                clase.append(f"{f}:{nodo.name}")
                modulo.append(f)
            if len(textos) >= maximo:
                break
        if len(textos) >= maximo:
            break

    def verdad(a, b):
        if clase[a] == clase[b]:
            return 1
        return 0 if modulo[a] != modulo[b] else None
    return dict(nombre="codigo", idioma="python", textos=textos, verdad=verdad, orden=None, etiquetas=None,
                positivos_totales=_pares_de_grupos(clase))


def charla(ventana=10):
    """NPS Chat: 15 salas/días reales. Cada recuerdo = 10 mensajes seguidos."""
    _nltk()
    from nltk.corpus import nps_chat
    textos, sesion, orden = [], [], []
    for k, f in enumerate(sorted(nps_chat.fileids(), key=lambda x: (x[:5], x))):
        # los nombres de usuario vienen como "10-19-20sUser7" (delatan la sala): se quitan
        posts = [" ".join(w for w in p if not re.search(r"user\d", w.lower())) for p in nps_chat.posts(f)]
        for i in range(0, len(posts) - ventana + 1, ventana):
            textos.append(" ".join(posts[i:i + ventana]))
            sesion.append(f)
            orden.append(float(len(orden)))

    def verdad(a, b):
        return 1 if sesion[a] == sesion[b] else 0
    return dict(nombre="charla", idioma="en", textos=textos, verdad=verdad, orden=orden, etiquetas=None,
                positivos_totales=_pares_de_grupos(sesion))


def noticias_es(palabras=120, maximo_trozos=3):
    """CESS-ESP (agencia EFE, año 2000), solo los archivos con fecha. Los archivos 10084_..._1/_2 son partes de la misma noticia."""
    _nltk()
    from nltk.corpus import cess_esp
    textos, nota, orden = [], [], []
    for f in sorted(cess_esp.fileids()):
        base = f.split(".")[0]
        partes = base.split("_")
        nid, fecha = partes[0], (partes[1] if len(partes) > 1 else "")
        if not (fecha.isdigit() and len(fecha) == 8):
            continue                      # los archivos "104_C-4" no traen fecha: fuera (solo tiempo real)
        w = [x.replace("_", " ") for x in cess_esp.words(f) if not x.startswith("*") and not x.startswith("-F")]
        for t in _trozos(w, palabras, maximo_trozos):
            textos.append(t)
            nota.append(nid + "_" + fecha)
            orden.append(float(fecha) * 1e5 + float(nid))

    def verdad(a, b):
        return 1 if nota[a] == nota[b] else 0
    return dict(nombre="noticias_es", idioma="es", textos=textos, verdad=verdad, orden=orden, etiquetas=None,
                positivos_totales=_pares_de_grupos(nota))


def machado(obras=150, trozos=8, palabras=150, semilla=6):
    """Machado de Assis (portugués). Trozos repartidos a lo largo de cada obra. Etiqueta = género."""
    import glob
    import os
    R = os.path.join(NLTK, "corpora", "machado")
    rng = np.random.default_rng(semilla)
    archivos = sorted(glob.glob(os.path.join(R, "*", "*.txt")))
    rng.shuffle(archivos)
    textos, obra, etq = [], [], []
    for f in archivos[:obras]:
        w = open(f, encoding="latin-1").read().split()
        if len(w) < palabras * 3:
            continue
        n = min(trozos, len(w) // palabras)
        for i in np.linspace(0, len(w) - palabras, n).astype(int):
            textos.append(" ".join(w[i:i + palabras]))
            obra.append(f)
            etq.append(frozenset([os.path.basename(os.path.dirname(f))]))

    def verdad(a, b):
        return 1 if obra[a] == obra[b] else 0
    return dict(nombre="machado", idioma="pt", textos=textos, verdad=verdad, orden=None, etiquetas=etq,
                positivos_totales=_pares_de_grupos(obra))


# `reportes` se probó y se sacó: "mismo programa" es una verdad demasiado gruesa (dos fallas de
# Firefox no tienen por qué tener que ver). Ver README, sección 3.
FABRICA = (noticias, diccionario, relatos, codigo, charla, noticias_es, machado)


def dennys(ruta="/tmp/e11/dennys.db"):
    """La memoria real de Dennys (COPIA del snapshot, solo lectura).

    Además de textos/orden/etiquetas devuelve:
      conceptos   nombre de cada recuerdo
      sin         {par: (tipo, peso)} conexiones directas que existen hoy
      cuarentena  {par: (motivo, confianza, restaurado, tipo)} lo que la hormiguita
                  (Gemini) sacó del grafo por "no tienen que ver"
    """
    c = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True)
    filas = c.execute("SELECT concepto, COALESCE(contenido,''), creado_en FROM largo_plazo "
                      "WHERE estado='activo' ORDER BY concepto").fetchall()
    conceptos = [f[0] for f in filas]
    pos = {x: i for i, x in enumerate(conceptos)}
    textos = [f"{f[0].replace('_', ' ')}. {f[1]}" for f in filas]
    t0 = min((f[2] for f in filas if f[2]), default=0.0)
    orden = [float(f[2]) if f[2] else t0 for f in filas]
    dims = {}
    for a, d in c.execute("SELECT concepto, dimension_id FROM largo_plazo_dimensiones"):
        if a in pos:
            dims.setdefault(a, set()).add(d)
    etiquetas = [frozenset(dims.get(x, ())) for x in conceptos]
    sin = {}
    for o, d, t, p in c.execute("SELECT origen, destino, tipo, peso FROM sinapsis"):
        if o in pos and d in pos and o != d:
            k = (min(pos[o], pos[d]), max(pos[o], pos[d]))
            prev = sin.get(k)
            if prev is None or t == "manual" or (prev[0] != "manual" and (p or 0) > (prev[1] or 0)):
                sin[k] = (t, p or 0.0)
    cuarentena = {}
    for o, d, t, mot, conf, rest, quien in c.execute(
            "SELECT origen, destino, tipo, motivo, confianza, restaurado, origen_llamada FROM sinapsis_cuarentena"):
        if o in pos and d in pos and o != d:
            k = (min(pos[o], pos[d]), max(pos[o], pos[d]))
            cuarentena[k] = (mot or "", float(conf or 0), int(rest or 0), t or "", quien or "")
    c.close()
    manual = {k for k, v in sin.items() if v[0] == "manual"}

    def verdad(a, b):
        return 1 if (min(a, b), max(a, b)) in manual else None
    return dict(nombre="dennys", idioma="es", textos=textos, verdad=verdad, orden=orden, etiquetas=etiquetas,
                conceptos=conceptos, sin=sin, cuarentena=cuarentena)

