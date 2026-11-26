"""Mundo sintético del protocolo H2/4b v2 (§6). Sin datos reales, sin listas de palabras de ningún idioma.

Genera, de forma determinista a partir de una semilla:
- D  : recuerdos de los temas de D.
- I0 : «I verdaderamente irrelevante» (§5.3): temas propios, inventario de caracteres DISJUNTO del de D en cada
       escritura (ni palabras función, ni genéricas, ni prefijos, ni bigramas en común), sin puentes ni homógrafos.
- I1 : «I′» con relaciones reales hacia D: mismo inventario y palabras función de D, puentes declarados con temas de
       D, homógrafos compartidos con temas de D y prefijos casuales.
Cada recuerdo lleva su verdad (tema, escritura, entidades puente) en un archivo aparte que el motor no ve.

Cuatro escrituras: lat_a y lat_b (latinas con diacríticos, inventarios distintos), han (ideogramas, sin espacios),
jpn (kanji + kana, sin espacios). Las palabras función son cadenas aleatorias frecuentes compartidas por todos los
temas de una escritura (imitan a las palabras vacías; no son palabras de ninguna lengua).
"""
import random

ESCRITURAS = ("lat_a", "lat_b", "han", "jpn")


def _rango(a, b):
    return [chr(c) for c in range(a, b + 1)]


# inventarios: «D» lo usan D e I1; «I0» lo usa solo I0 (disjunto por carácter)
INV = {
    "lat_a": {"D": ("bcdfglmnprstvzñ", "aeiouáéó"), "I0": ("ćłśźżńřť", "ąęåøæ")},
    "lat_b": {"D": ("khwyjqx", "aeiuäöü"), "I0": ("ŋɣʃʒðħ", "ɛɔəɪʊ")},
    "han": {"D": _rango(0x4E00, 0x5FFF), "I0": _rango(0x7000, 0x77FF)},
    "jpn": {"D": (_rango(0x6000, 0x6FFF), _rango(0x3041, 0x3053), _rango(0x30A1, 0x30C0)),
            "I0": (_rango(0x8000, 0x87FF), _rango(0x3055, 0x3093), _rango(0x30C1, 0x30F4))},
}
SIN_ESPACIOS = {"han", "jpn"}


class Lexico:
    """Fábrica de palabras únicas de una escritura y un inventario."""

    def __init__(self, rng, esc, inv):
        self.rng, self.esc, self.inv = rng, esc, INV[esc][inv]
        self.usadas = set()

    def _latina(self, silabas):
        c, v = self.inv
        w = ""
        for _ in range(silabas):
            w += self.rng.choice(c) + self.rng.choice(v)
            if self.rng.random() < 0.25:
                w += self.rng.choice(c)
        return w

    def nueva(self, tipo="contenido"):
        for _ in range(1000):
            if self.esc in ("lat_a", "lat_b"):
                w = self._latina(1 if tipo == "funcion" else self.rng.choice((2, 3, 3)))
                if tipo == "funcion":
                    w = w[:2]
            elif self.esc == "han":
                w = self.rng.choice(self.inv) if tipo == "funcion" else \
                    self.rng.choice(self.inv) + self.rng.choice(self.inv)
            else:  # jpn
                kanji, hira, kata = self.inv
                if tipo == "funcion":
                    w = "".join(self.rng.choice(hira) for _ in range(self.rng.choice((1, 2))))
                elif self.rng.random() < 0.3:
                    w = "".join(self.rng.choice(kata) for _ in range(3))
                else:
                    w = self.rng.choice(kanji) + self.rng.choice(kanji)
            if w not in self.usadas and len(w) >= 1:
                self.usadas.add(w)
                return w
        raise RuntimeError("inventario agotado")

    def variante(self, w):
        """Variante morfológica: mismo prefijo largo (latinas) o mismo primer carácter no hiragana (CJK)."""
        for _ in range(1000):
            if self.esc in ("lat_a", "lat_b"):
                c, v = self.inv
                base = w if len(w) >= 5 else w + self.rng.choice(c) + self.rng.choice(v)
                x = base + self.rng.choice(v) + self.rng.choice(c)
            else:
                x = w[0] + self.nueva()[-1]
            if x not in self.usadas:
                self.usadas.add(x)
                return x
        raise RuntimeError("sin variante")


def _zipf(rng, items, k, s=1.1):
    pesos = [1.0 / (r + 1) ** s for r in range(len(items))]
    return rng.choices(items, weights=pesos, k=k)


def _tam_tema(rng):
    return rng.choice((8, 10, 12)) if rng.random() < 0.08 else rng.choice((1, 2, 2, 3, 3, 4, 4, 5))


def _texto(esc, palabras):
    return ("".join(palabras) if esc in SIN_ESPACIOS else " ".join(palabras))


def generar(semilla, n_D, frac_I=0.25):
    """n_D recuerdos en D; I0 e I1 con n_D·frac_I cada uno (80/20 por tema: |I| = |D|/4)."""
    rng = random.Random(semilla)
    lex = {(e, inv): Lexico(rng, e, inv) for e in ESCRITURAS for inv in ("D", "I0")}
    funcion = {(e, inv): [lex[(e, inv)].nueva("funcion") for _ in range(14)] for e, inv in lex}
    generica = {(e, inv): [lex[(e, inv)].nueva() for _ in range(250)] for e, inv in lex}
    temas, recuerdos = {}, []
    sig = [0]

    def nuevo_tema(conj, esc, inv):
        tid = "%s_t%04d" % (conj, len(temas))
        L = lex[(esc, inv)]
        voc = [L.nueva() for _ in range(rng.choice((6, 8, 10)))]
        # variantes morfológicas dentro del tema (C1 legítimo)
        for w in list(voc[:2]):
            voc.append(L.variante(w))
        temas[tid] = {"conj": conj, "esc": esc, "inv": inv, "voc": voc, "tam": _tam_tema(rng), "entidades": [],
                      "intrusas": []}
        return tid

    n_I = int(round(n_D * frac_I))
    plan = []
    for conj, n, inv in (("D", n_D, "D"), ("I0", n_I, "I0"), ("I1", n_I, "D")):
        total = 0
        while total < n:
            esc = ESCRITURAS[len(plan) % 4]
            tid = nuevo_tema(conj, esc, inv)
            t = temas[tid]
            t["tam"] = min(t["tam"], n - total)
            total += t["tam"]
            plan.append(tid)

    temas_D = [t for t in temas if temas[t]["conj"] == "D"]
    temas_I1 = [t for t in temas if temas[t]["conj"] == "I1"]
    puentes = []

    def unir(t1, t2):
        """Puente válido: una entidad rara declarada, presente en recuerdos de los dos temas."""
        esc = temas[t1]["esc"]
        ent = lex[(esc, "D")].nueva()
        temas[t1]["entidades"].append(ent)
        temas[t2]["entidades"].append(ent)
        puentes.append({"temas": sorted([t1, t2]), "entidad": ent})

    def homografo(t1, t2):
        """Accidental: la misma cadena en dos temas sin relación (contextos distintos)."""
        w = temas[t1]["voc"][rng.randrange(len(temas[t1]["voc"]))]
        temas[t2]["intrusas"].append(w)

    def prefijo_casual(t1, t2):
        esc = temas[t1]["esc"]
        w = temas[t1]["voc"][0]
        temas[t2]["intrusas"].append(lex[(esc, "D")].variante(w))

    por_esc = lambda lista, e: [t for t in lista if temas[t]["esc"] == e]  # noqa: E731
    for e in ESCRITURAS:
        dD, dI = por_esc(temas_D, e), por_esc(temas_I1, e)
        rng.shuffle(dD)
        # dentro de D: ~12 % de temas en puentes, ~10 % con homógrafos, ~10 % con prefijos casuales
        k = min(max(2, len(dD) // 16), len(dD) // 8)
        for i in range(0, 2 * k, 2):
            unir(dD[i], dD[i + 1])
        for i in range(2 * k, 3 * k):
            homografo(dD[i], dD[-1 - i])
        for i in range(3 * k, 4 * k):
            prefijo_casual(dD[i], dD[-1 - i])
        # I1 → D: puentes, homógrafos y prefijos casuales hacia temas de D
        rng.shuffle(dI)
        kI = min(max(2, len(dI) // 5), len(dI) // 3)
        for i in range(kI):
            unir(dI[i], dD[(7 * i) % len(dD)])
        for i in range(kI, 2 * kI):
            homografo(dD[(11 * i) % len(dD)], dI[i % len(dI)])
        for i in range(2 * kI, min(3 * kI, len(dI))):
            prefijo_casual(dD[(13 * i) % len(dD)], dI[i])

    for tid in plan:
        t = temas[tid]
        esc, inv = t["esc"], t["inv"]
        fun, gen = funcion[(esc, inv)], generica[(esc, inv)]
        for j in range(t["tam"]):
            n_tema = rng.randint(3, 6)
            palabras = _zipf(rng, t["voc"], n_tema) + _zipf(rng, fun, rng.randint(3, 6)) + \
                _zipf(rng, gen, rng.randint(1, 3), s=1.0)
            ents = [x for x in t["entidades"] if rng.random() < 0.6 or j == 0]
            intr = [x for x in t["intrusas"] if rng.random() < 0.5 or j == 0]
            palabras += ents + intr
            rng.shuffle(palabras)
            sig[0] += 1
            recuerdos.append({"concepto": "x%02d%05d" % (semilla, sig[0]), "conj": t["conj"], "tema": tid,
                              "esc": esc, "contenido": _texto(esc, palabras), "entidades": ents,
                              "palabras_tema": sorted(set(w for w in palabras if w in t["voc"]))})
    rel_puente = {}
    for p in puentes:
        rel_puente.setdefault(tuple(p["temas"]), []).append(p["entidad"])
    return {"semilla": semilla, "n_D": n_D, "recuerdos": recuerdos, "temas": temas, "puentes": puentes,
            "funcion": {"%s|%s" % k: v for k, v in funcion.items()}}


def verdad_par(mundo_idx, a, b, texto_coincide):
    """tema / puente / accidental / ajeno para dos recuerdos (dicts del mundo)."""
    if a["tema"] == b["tema"]:
        return "tema"
    clave = tuple(sorted([a["tema"], b["tema"]]))
    ents = mundo_idx["puentes"].get(clave)
    if ents and any(e in a["entidades"] and e in b["entidades"] for e in ents):
        return "puente"
    return "accidental" if texto_coincide(a, b) else "ajeno"
