"""Experimento 16 — generador del mundo sintético (PROTOCOLO.md §1). Determinista por semilla.

No toca el motor ni ninguna base: solo produce una lista de recuerdos con su verdad conocida.
"""
import hashlib
import random

GENERICAS = ["sistema", "version", "protocolo", "proceso", "modulo", "registro",
             "estado", "archivo", "configuracion", "resultado", "servicio", "prueba"]
SIGLAS = ["qa", "db", "ux", "vm", "ia", "rpc", "tls", "cfg"]
CONECTORES = ["el", "la", "de", "que", "con", "para", "en", "los", "del", "por"]
CONS = "bdfgklmnprstvz"
VOC = "aeiou"
# ejes (tipo_id del catálogo real) usados para los perfiles de dimensiones
EJES = ["entidad", "accion", "cualidad", "dominio", "intencion", "cualia", "epistemia"]
CATEGORIAS = ["Project", "Lesson", "System", "Architecture", "Relation", "Cognition"]


def _pseudopalabras(rnd, n, usadas):
    out = []
    while len(out) < n:
        w = "".join(rnd.choice(CONS) + rnd.choice(VOC) for _ in range(rnd.choice((3, 3, 4)))) + rnd.choice("klmnrst")
        if w not in usadas:
            usadas.add(w)
            out.append(w)
    return out


def sellado(tema):
    """§3: tema sellado si sha256('tema_t')[:8] % 5 == 0. Los temas de I usan índices >= 1000."""
    return int(hashlib.sha256(("tema_%d" % tema).encode()).hexdigest()[:8], 16) % 5 == 0


def generar(semilla, catalogo, n=400, temas=20, subtemas=3, frac_generica=0.12,
            n_irrelevantes=0, irrelevantes_reales=False, permutar_sesiones=False, n_hubs=4):
    """Devuelve dict con 'eventos' (lista ordenada de recuerdos a guardar, incluye re-guardados de hubs),
    'info' {concepto: {tema, subtema, grupo}} y parámetros.

    catalogo: {eje: [nombres de dimensiones del catálogo real]}.
    Los recuerdos de D se generan SIEMPRE con el mismo RNG (independiente de I y del orden), así D es
    idéntico entre variantes; I usa un RNG propio.
    """
    rnd = random.Random(semilla)
    usadas = set(GENERICAS) | set(SIGLAS) | set(CONECTORES)
    vocab_tema, vocab_sub, perfil, cat_tema = {}, {}, {}, {}
    for t in range(temas):
        vocab_tema[t] = _pseudopalabras(rnd, 25, usadas)
        for s in range(subtemas):
            vocab_sub[(t, s)] = _pseudopalabras(rnd, 10, usadas)
        ejes = rnd.sample(EJES, 4)
        perfil[t] = {e: rnd.choice(catalogo[e]) for e in ejes}
        cat_tema[t] = rnd.choice(CATEGORIAS)

    def recuerdo(r, t, s, k, vt, vs, prf, cat, usa_genericas, etiqueta):
        n_tok = 25
        n_gen = max(1, round(n_tok * frac_generica)) if usa_genericas else 0
        palabras = r.sample(vs, 8) + r.sample(vt, 6) + [r.choice(GENERICAS) for _ in range(n_gen)]
        if usa_genericas and r.random() < 0.5:
            palabras.append(r.choice(SIGLAS))
        while len(palabras) < n_tok:
            palabras.append(r.choice(CONECTORES))
        r.shuffle(palabras)
        nombre = "%s_%s_%s%d" % (r.choice(vt), r.choice(vs), etiqueta, k)
        if usa_genericas and r.random() < 0.3:
            nombre = r.choice(GENERICAS) + "_" + nombre
        syn = []
        for _ in range(r.randint(6, 10)):
            u = r.random()
            if u < 0.7:
                syn.append(r.choice(vs + vt))
            elif u < 0.9 and usa_genericas:
                syn.append(r.choice(GENERICAS))
            else:
                syn.append(r.choice(vt) + " " + r.choice(vs))
        syn = list(dict.fromkeys(syn))
        dims = {}
        for e, v in prf.items():
            dims[e] = [v if r.random() < 0.8 else r.choice(catalogo[e])]
        sk = list(dict.fromkeys(r.sample(vs, r.randint(2, 4))))
        return {"concepto": nombre, "contenido": " ".join(palabras), "syn": ", ".join(syn),
                "cat": cat, "dims": dims, "sk": ",".join(sk), "tema": t, "subtema": s}

    # ── D ──
    D = []
    for i in range(n):
        t = rnd.randrange(temas)
        s = rnd.randrange(subtemas)
        D.append(recuerdo(rnd, t, s, i, vocab_tema[t], vocab_sub[(t, s)], perfil[t], cat_tema[t], True, "m"))
    # hubs: genéricos + palabras de 6 temas al azar
    hubs = []
    for h in range(n_hubs):
        ts = rnd.sample(range(temas), min(6, temas))
        pal = [rnd.choice(GENERICAS) for _ in range(10)] + [rnd.choice(vocab_tema[t]) for t in ts for _ in range(2)]
        pal += [rnd.choice(SIGLAS) for _ in range(2)]
        rnd.shuffle(pal)
        hubs.append({"concepto": "registro_general_%d" % h, "contenido": " ".join(pal),
                     "syn": ", ".join(rnd.sample(GENERICAS, 4)), "cat": "General",
                     "dims": {"intencion": [rnd.choice(catalogo["intencion"])]},
                     "sk": ",".join(rnd.sample(GENERICAS, 3)), "tema": None, "subtema": None})
    # sesiones de D (3–6 recuerdos; p=0.6 mismo tema)
    por_tema = {}
    for i, m in enumerate(D):
        por_tema.setdefault(m["tema"], []).append(i)
    libres = set(range(n))
    sesiones = []
    orden = list(range(n))
    rnd.shuffle(orden)
    for i in orden:
        if i not in libres:
            continue
        libres.discard(i)
        ses = [i]
        tam = rnd.randint(3, 6)
        while len(ses) < tam and libres:
            mismos = [j for j in por_tema[D[i]["tema"]] if j in libres]
            if mismos and rnd.random() < 0.6:
                j = rnd.choice(mismos)
            else:
                j = rnd.choice(sorted(libres))
            libres.discard(j)
            ses.append(j)
        sesiones.append([("D", j) for j in ses])
    # hubs: primera vez + 5 re-guardados repartidos
    pos_hubs = []
    for h in range(n_hubs):
        for rep in range(6):
            pos_hubs.append((rnd.randrange(len(sesiones) + 1), h))
    if permutar_sesiones:
        rp = random.Random(semilla * 7919 + 1)
        rp.shuffle(sesiones)

    # ── I (irrelevantes) con RNG propio ──
    I = []
    ses_I = []
    if n_irrelevantes:
        ri = random.Random(semilla * 104729 + (2 if irrelevantes_reales else 1))
        temas_i = 10
        vt_i = {t: _pseudopalabras(ri, 25, usadas) for t in range(temas_i)}
        vs_i = {(t, s): _pseudopalabras(ri, 10, usadas) for t in range(temas_i) for s in range(subtemas)}
        prf_i = {t: {e: ri.choice(catalogo[e]) for e in ri.sample(EJES, 4)} for t in range(temas_i)}
        for k in range(n_irrelevantes):
            t, s = ri.randrange(temas_i), ri.randrange(subtemas)
            m = recuerdo(ri, 1000 + t, s, k, vt_i[t], vs_i[(t, s)], prf_i[t], ri.choice(CATEGORIAS),
                         irrelevantes_reales, "x")
            I.append(m)
        idx = list(range(n_irrelevantes))
        while idx:
            tam = ri.randint(3, 6)
            ses_I.append([("I", j) for j in idx[:tam]])
            idx = idx[tam:]
        # intercalar: posición de cada sesión de I entre las sesiones de D
        pos_I = sorted((ri.randrange(len(sesiones) + 1), k) for k in range(len(ses_I)))
    else:
        pos_I = []

    eventos = []
    hubs_vistos = set()
    pi = 0
    ph = sorted(pos_hubs)
    hi = 0
    for si in range(len(sesiones) + 1):
        while hi < len(ph) and ph[hi][0] == si:
            h = ph[hi][1]
            eventos.append(dict(hubs[h], grupo="hub", reguardado=h in hubs_vistos))
            hubs_vistos.add(h)
            hi += 1
        while pi < len(pos_I) and pos_I[pi][0] == si:
            for _, j in ses_I[pos_I[pi][1]]:
                eventos.append(dict(I[j], grupo="I", reguardado=False))
            pi += 1
        if si < len(sesiones):
            for _, j in sesiones[si]:
                eventos.append(dict(D[j], grupo="D", reguardado=False))
    info = {}
    for e in eventos:
        info[e["concepto"]] = {"tema": e["tema"], "subtema": e["subtema"], "grupo": e["grupo"]}
    return {"eventos": eventos, "info": info,
            "params": dict(semilla=semilla, n=n, temas=temas, subtemas=subtemas, frac_generica=frac_generica,
                           n_irrelevantes=n_irrelevantes, irrelevantes_reales=irrelevantes_reales,
                           permutar_sesiones=permutar_sesiones)}


def relevancia(info, a, b):
    ia, ib = info.get(a), info.get(b)
    if not ia or not ib or ia["tema"] is None or ib["tema"] is None:
        return 0
    if ia["tema"] != ib["tema"]:
        return 0
    return 2 if ia["subtema"] == ib["subtema"] else 1


def par_sellado(info, a, b):
    """§3: un par es sellado si algún extremo es de un tema sellado (hub–X sigue a X)."""
    ta, tb = info[a]["tema"], info[b]["tema"]
    return any(t is not None and sellado(t) for t in (ta, tb))


# ═════════════════════════ mundo v2 (PROTOCOLO_V2.md §1) ═════════════════════════
def generar_v2(semilla, catalogo, n=400, temas=20, subtemas=3, frac_generica=0.12,
               n_irrelevantes=0, irrelevantes_reales=False, permutar_sesiones=False, n_hubs=4):
    """Mundo más difícil: SINONIMIA (un concepto tiene 1–3 palabras distintas), POLISEMIA (40 palabras
    compartidas por conceptos de temas distintos), vocabulario TRANSVERSAL compartido entre temas y
    dimensiones/categorías ruidosas. Misma salida que generar()."""
    rnd = random.Random(semilla + 50000)
    usadas = set(GENERICAS) | set(SIGLAS) | set(CONECTORES)

    def concepto_nuevo(r):
        k = 1 if r.random() < 0.5 else (2 if r.random() < 0.7 else 3)
        return _pseudopalabras(r, k, usadas)

    c_tema = {t: [concepto_nuevo(rnd) for _ in range(18)] for t in range(temas)}
    c_sub = {(t, s): [concepto_nuevo(rnd) for _ in range(8)] for t in range(temas) for s in range(subtemas)}
    transversal = [concepto_nuevo(rnd) for _ in range(80)]
    afin = {t: rnd.sample(range(80), 15) for t in range(temas)}
    # polisemia: 40 palabras compartidas por conceptos de temas distintos
    for _ in range(40):
        ta, tb = rnd.sample(range(temas), 2)
        ca = rnd.choice(c_tema[ta] + [c for s in range(subtemas) for c in c_sub[(ta, s)]])
        cb = rnd.choice(c_tema[tb] + [c for s in range(subtemas) for c in c_sub[(tb, s)]])
        cb[0] = ca[0]
    perfiles = [{e: rnd.choice(catalogo[e]) for e in rnd.sample(EJES, 4)} for _ in range(5)]
    perfil = {t: perfiles[t % 5] for t in range(temas)}
    cat_tema = {t: rnd.choice(CATEGORIAS) for t in range(temas)}

    def recuerdo(r, t, s, k, ct, cs, trans, prf, cat, usa_genericas, etiqueta):
        conc_sub = r.sample(cs, 5)
        conc = conc_sub + r.sample(ct, 4) + [r.choice(trans) for _ in range(3)]
        palabras = [r.choice(c) for c in conc]
        n_gen = max(1, round(25 * frac_generica)) if usa_genericas else 0
        palabras += [r.choice(GENERICAS) for _ in range(n_gen)]
        if usa_genericas and r.random() < 0.5:
            palabras.append(r.choice(SIGLAS))
        while len(palabras) < 25:
            palabras.append(r.choice(CONECTORES))
        r.shuffle(palabras)
        nombre = "%s_%s_%s%d" % (r.choice(conc_sub[0]), r.choice(conc[6]), etiqueta, k)
        if usa_genericas and r.random() < 0.3:
            nombre = r.choice(GENERICAS) + "_" + nombre
        syn = []
        for _ in range(r.randint(6, 10)):
            u = r.random()
            if u < 0.7:
                syn.append(r.choice(r.choice(conc)))          # otra forma (sinónimo) de un concepto presente
            elif u < 0.9 and usa_genericas:
                syn.append(r.choice(GENERICAS))
            else:
                syn.append(r.choice(r.choice(conc)) + " " + r.choice(r.choice(conc_sub)))
        syn = list(dict.fromkeys(syn))
        dims = {e: [v if r.random() < 0.65 else r.choice(catalogo[e])] for e, v in prf.items()}
        sk = list(dict.fromkeys(r.choice(c) for c in r.sample(conc_sub, r.randint(2, 4))))
        if len(sk) < 2:
            sk.append(r.choice(r.choice(cs)))
            sk = list(dict.fromkeys(sk)) if len(set(sk)) >= 2 else sk + [r.choice(ct)[0]]
        cat_m = cat if r.random() < 0.6 else r.choice(CATEGORIAS)
        return {"concepto": nombre, "contenido": " ".join(palabras), "syn": ", ".join(syn), "cat": cat_m,
                "dims": dims, "sk": ",".join(dict.fromkeys(sk)), "tema": t, "subtema": s}

    D = []
    for i in range(n):
        t, s = rnd.randrange(temas), rnd.randrange(subtemas)
        D.append(recuerdo(rnd, t, s, i, c_tema[t], c_sub[(t, s)], [transversal[j] for j in afin[t]],
                          perfil[t], cat_tema[t], True, "m"))
    return _ensamblar(rnd, semilla, D, n, temas, subtemas, frac_generica, n_irrelevantes, irrelevantes_reales,
                      permutar_sesiones, n_hubs, catalogo, usadas, recuerdo, c_tema, transversal, "v2")


def _ensamblar(rnd, semilla, D, n, temas, subtemas, frac_generica, n_irrelevantes, irrelevantes_reales,
               permutar_sesiones, n_hubs, catalogo, usadas, recuerdo, c_tema, transversal, version):
    hubs = []
    for h in range(n_hubs):
        ts = rnd.sample(range(temas), min(6, temas))
        pal = [rnd.choice(GENERICAS) for _ in range(10)] + [rnd.choice(rnd.choice(c_tema[t])) for t in ts
                                                             for _ in range(2)]
        pal += [rnd.choice(SIGLAS) for _ in range(2)]
        rnd.shuffle(pal)
        hubs.append({"concepto": "registro_general_%d" % h, "contenido": " ".join(pal),
                     "syn": ", ".join(rnd.sample(GENERICAS, 4)), "cat": "General",
                     "dims": {"intencion": [rnd.choice(catalogo["intencion"])]},
                     "sk": ",".join(rnd.sample(GENERICAS, 3)), "tema": None, "subtema": None})
    por_tema = {}
    for i, m in enumerate(D):
        por_tema.setdefault(m["tema"], []).append(i)
    libres = set(range(n))
    sesiones = []
    orden = list(range(n))
    rnd.shuffle(orden)
    for i in orden:
        if i not in libres:
            continue
        libres.discard(i)
        ses = [i]
        tam = rnd.randint(3, 6)
        while len(ses) < tam and libres:
            mismos = [j for j in por_tema[D[i]["tema"]] if j in libres]
            j = rnd.choice(mismos) if (mismos and rnd.random() < 0.6) else rnd.choice(sorted(libres))
            libres.discard(j)
            ses.append(j)
        sesiones.append(ses)
    pos_hubs = sorted((rnd.randrange(len(sesiones) + 1), h) for h in range(n_hubs) for _ in range(6))
    if permutar_sesiones:
        random.Random(semilla * 7919 + 1).shuffle(sesiones)
    I, ses_I, pos_I = [], [], []
    if n_irrelevantes:
        ri = random.Random(semilla * 104729 + (2 if irrelevantes_reales else 1) + 7)
        temas_i = 10

        def cn(r):
            k = 1 if r.random() < 0.5 else (2 if r.random() < 0.7 else 3)
            return _pseudopalabras(r, k, usadas)
        ct_i = {t: [cn(ri) for _ in range(18)] for t in range(temas_i)}
        cs_i = {(t, s): [cn(ri) for _ in range(8)] for t in range(temas_i) for s in range(subtemas)}
        tr_i = transversal if irrelevantes_reales else [cn(ri) for _ in range(80)]
        prf_i = {t: {e: ri.choice(catalogo[e]) for e in ri.sample(EJES, 4)} for t in range(temas_i)}
        for k in range(n_irrelevantes):
            t, s = ri.randrange(temas_i), ri.randrange(subtemas)
            I.append(recuerdo(ri, 1000 + t, s, k, ct_i[t], cs_i[(t, s)], ri.sample(tr_i, 15), prf_i[t],
                              ri.choice(CATEGORIAS), irrelevantes_reales, "x"))
        idx = list(range(n_irrelevantes))
        while idx:
            tam = ri.randint(3, 6)
            ses_I.append(idx[:tam])
            idx = idx[tam:]
        pos_I = sorted((ri.randrange(len(sesiones) + 1), k) for k in range(len(ses_I)))
    eventos, vistos = [], set()
    pi = hi = 0
    for si in range(len(sesiones) + 1):
        while hi < len(pos_hubs) and pos_hubs[hi][0] == si:
            h = pos_hubs[hi][1]
            eventos.append(dict(hubs[h], grupo="hub", reguardado=h in vistos))
            vistos.add(h)
            hi += 1
        while pi < len(pos_I) and pos_I[pi][0] == si:
            for j in ses_I[pos_I[pi][1]]:
                eventos.append(dict(I[j], grupo="I", reguardado=False))
            pi += 1
        if si < len(sesiones):
            for j in sesiones[si]:
                eventos.append(dict(D[j], grupo="D", reguardado=False))
    info = {e["concepto"]: {"tema": e["tema"], "subtema": e["subtema"], "grupo": e["grupo"]} for e in eventos}
    return {"eventos": eventos, "info": info,
            "params": dict(version=version, semilla=semilla, n=n, temas=temas, subtemas=subtemas,
                           frac_generica=frac_generica, n_irrelevantes=n_irrelevantes,
                           irrelevantes_reales=irrelevantes_reales, permutar_sesiones=permutar_sesiones)}
