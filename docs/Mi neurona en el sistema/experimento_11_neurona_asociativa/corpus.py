"""Las memorias del experimento 11 (todas con una VERDAD conocida de "tiene que ver").

Cada constructor devuelve (nombre, textos, verdad) donde verdad(a, b) es
  1    = sí tienen que ver
  0    = no tienen que ver
  None = dudoso (no se usa ni para entrenar ni para medir)

  noticias     Reuters-21578 (inglés, 2,000 noticias). Tienen que ver si tratan
               el mismo tema (mismas categorías, Jaccard >= .5); no, si no
               comparten ninguna.
  diccionario  WordNet (inglés, definiciones). Tienen que ver si WordNet los une
               directamente (es-un, parte-de, opuesto, derivado, dominio...);
               no, si no hay camino de 1 ni 2 pasos.
  relatos      Brown (inglés, 1,200 trozos de 150 palabras de 300 textos).
               Tienen que ver si son trozos del MISMO texto (mismo "episodio").
  dennys       La memoria real de Dennys (español). Verdad parcial: las 381
               conexiones `manual` (las unió una persona a propósito) = sí.
               Del resto no se sabe la verdad: se usa solo para comparar.
"""
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
    textos, cats = [], []
    for f in elegidos:
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
    return "noticias", textos, verdad


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
    return "diccionario", textos, verdad


def relatos(docs=300, trozos=4, palabras=150, semilla=3):
    _nltk()
    from nltk.corpus import brown
    rng = np.random.default_rng(semilla)
    ids = list(brown.fileids())
    rng.shuffle(ids)
    textos, doc = [], []
    for f in ids[:docs]:
        w = [x for x in brown.words(f)]
        for t in range(trozos):
            pedazo = w[t * palabras:(t + 1) * palabras]
            if len(pedazo) < palabras // 2:
                break
            textos.append(" ".join(pedazo))
            doc.append(f)

    def verdad(a, b):
        return 1 if doc[a] == doc[b] else 0
    return "relatos", textos, verdad


def dennys(ruta="/tmp/e11/dennys.db"):
    c = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True)
    filas = c.execute("SELECT concepto, COALESCE(contenido,'') FROM largo_plazo "
                      "WHERE estado='activo' ORDER BY concepto").fetchall()
    conceptos = [f[0] for f in filas]
    pos = {x: i for i, x in enumerate(conceptos)}
    textos = [f"{f[0].replace('_', ' ')}. {f[1]}" for f in filas]
    sin = {}
    for o, d, t, p in c.execute("SELECT origen, destino, tipo, peso FROM sinapsis"):
        if o in pos and d in pos and o != d:
            k = (min(pos[o], pos[d]), max(pos[o], pos[d]))
            prev = sin.get(k)
            if prev is None or t == "manual" or (prev[0] != "manual" and (p or 0) > (prev[1] or 0)):
                sin[k] = (t, p or 0.0)
    manual = {k for k, v in sin.items() if v[0] == "manual"}

    def verdad(a, b):
        return 1 if (min(a, b), max(a, b)) in manual else None
    return "dennys", textos, verdad, conceptos, sin
