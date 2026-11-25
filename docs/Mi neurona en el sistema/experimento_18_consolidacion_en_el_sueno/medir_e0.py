"""Experimento 18, E0 — agujas del par en cuatro idiomas (PROTOCOLO.md §4). Criterios fijados en 5bfe989.

Uso:  python medir_e0.py            → imprime la tabla y escribe resultados/e0.json
No toca el motor ni ninguna base de datos. Solo biblioteca estándar.
"""
import json
import os
import re
import unicodedata
import zlib
from itertools import combinations

from mundos_espejo import D, I, etiqueta

IDIOMAS = ["es", "en", "zh", "ja"]


# ── normalización estructural (sin listas, sin tokenizador) ──
def normalizar(texto):
    t = unicodedata.normalize("NFKC", texto).casefold()
    t = "".join(ch if unicodedata.category(ch)[0] in "LN" else " " for ch in t)
    return " ".join(t.split())


def ngramas(t, ns=(2, 3)):
    return {t[i:i + n] for n in ns for i in range(len(t) - n + 1)}


# ── agujas: cada una recibe SOLO los dos textos del par ──
def n1_ngramas(a, b):
    ga, gb = ngramas(normalizar(a)), ngramas(normalizar(b))
    return len(ga & gb) / len(ga | gb) if ga | gb else 0.0


def _c(x):
    return len(zlib.compress(x, 9))


def n2_ncd(a, b):
    xa, xb = normalizar(a).encode("utf-8"), normalizar(b).encode("utf-8")
    ca, cb = _c(xa), _c(xb)
    ncd_ab = (_c(xa + b" " + xb) - min(ca, cb)) / max(ca, cb)
    ncd_ba = (_c(xb + b" " + xa) - min(ca, cb)) / max(ca, cb)
    return 1.0 - (ncd_ab + ncd_ba) / 2.0


def ref_w4(a, b):
    """Referencia (sin criterio): lo que usan hoy B6/B7 del motor."""
    ta, tb = set(re.findall(r"\w{4,}", a.lower())), set(re.findall(r"\w{4,}", b.lower()))
    return len(ta & tb) / len(ta | tb) if ta | tb else 0.0


AGUJAS = {"N1_ngramas_caracteres": n1_ngramas, "N2_compresion_ncd": n2_ncd, "ref_w4_motor_hoy": ref_w4}


# ── métricas ──
def auc(pos, neg):
    gana = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return gana / (len(pos) * len(neg))


def _rangos(v):
    orden = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v)
    i = 0
    while i < len(v):
        j = i
        while j + 1 < len(v) and v[orden[j + 1]] == v[orden[i]]:
            j += 1
        for k in range(i, j + 1):
            r[orden[k]] = (i + j) / 2.0 + 1
        i = j + 1
    return r


def spearman(x, y):
    rx, ry = _rangos(x), _rangos(y)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return num / den if den else 0.0


def puntuar(corpus, f, n_d=24):
    """Puntúa los pares de D dentro de un corpus (D o D∪I). Solo se leen los pares de D."""
    return {(i, j): f(corpus[i], corpus[j]) for i, j in combinations(range(n_d), 2)}


def correr():
    pares = list(combinations(range(24), 2))
    out = {}
    for nombre, f in AGUJAS.items():
        r = {"por_idioma": {}}
        for lg in IDIOMAS:
            s = puntuar(D[lg], f)
            s_ampliado = puntuar(D[lg] + I[lg], f)
            pos = [s[p] for p in pares if etiqueta(*p) == "pos"]
            neg = [s[p] for p in pares if etiqueta(*p) == "neg"]
            pte = [s[p] for p in pares if etiqueta(*p) == "puente"]
            r["por_idioma"][lg] = {
                "auc": round(auc(pos, neg), 4),
                "media_pos": round(sum(pos) / len(pos), 4),
                "media_neg": round(sum(neg) / len(neg), 4),
                "media_puente": round(sum(pte) / len(pte), 4),
                "pct_puente_sobre_neg": round(auc(pte, neg), 4),
                "invariantes": sum(s[p] == s_ampliado[p] for p in pares),
                "n_pos": len(pos), "n_neg": len(neg), "n_puente": len(pte),
                "_s": [s[p] for p in pares],
            }
        aucs = [r["por_idioma"][lg]["auc"] for lg in IDIOMAS]
        r["dispersion_auc"] = round(max(aucs) - min(aucs), 4)
        r["spearman_vs_es"] = {lg: round(spearman(r["por_idioma"]["es"]["_s"], r["por_idioma"][lg]["_s"]), 4)
                               for lg in IDIOMAS[1:]}
        out[nombre] = r
    return out


def criterios(r):
    pi = r["por_idioma"]
    return {
        "C0.1_auc_cada_idioma_>=0.70": all(pi[lg]["auc"] >= 0.70 for lg in IDIOMAS),
        "C0.2_dispersion_<=0.10": r["dispersion_auc"] <= 0.10,
        "C0.3_spearman_>=0.50": all(v >= 0.50 for v in r["spearman_vs_es"].values()),
        "C0.4_invariancia_276/276": all(pi[lg]["invariantes"] == 276 for lg in IDIOMAS),
    }


if __name__ == "__main__":
    a, b = correr(), correr()
    reproducible = json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    informe = {}
    for nombre, r in a.items():
        c = criterios(r)
        c["C0.5_reproducible"] = reproducible
        es_ref = nombre.startswith("ref_")
        for lg in IDIOMAS:
            r["por_idioma"][lg].pop("_s")
        informe[nombre] = {**r, "criterios": c,
                           "veredicto": "referencia (sin criterio)" if es_ref else ("PASA" if all(c.values()) else "NO PASA")}
        print("\n== %s → %s" % (nombre, informe[nombre]["veredicto"]))
        print("   idioma   AUC    pos    neg   puente  invariantes")
        for lg in IDIOMAS:
            x = r["por_idioma"][lg]
            print("   %-6s %.3f  %.3f  %.3f  %.3f   %d/276" % (lg, x["auc"], x["media_pos"], x["media_neg"],
                                                             x["media_puente"], x["invariantes"]))
        print("   dispersión AUC %.3f · Spearman vs es %s" % (r["dispersion_auc"], r["spearman_vs_es"]))
        print("   criterios:", {k: ("✅" if v else "❌") for k, v in c.items()})
    os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), "resultados"), exist_ok=True)
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "resultados", "e0.json"), "w") as fh:
        json.dump(informe, fh, ensure_ascii=False, indent=1, sort_keys=True)
