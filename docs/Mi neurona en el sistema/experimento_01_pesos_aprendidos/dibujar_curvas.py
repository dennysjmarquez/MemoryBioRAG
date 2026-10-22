#!/usr/bin/env python3
"""Dibuja las figuras de LA_NEURONA_EXPLICADA.md a partir de los resultados reales.

Lee:
  resultados/particion_{7,11,23}.txt      (salida de entrenar_neurona.py)
  resultados/curva_aprendizaje_7.json     (salida de curva_aprendizaje.py)
  datos/pools_semilla1.jsonl.gz           (solo para la figura del caso 0739)
Escribe figuras/*.png. Requiere matplotlib (no es dependencia del motor).

Uso:  python dibujar_curvas.py
"""
import gzip
import json
import math
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

AQUI = Path(__file__).resolve().parent
RES = AQUI / "resultados"
FIG = AQUI / "figuras"
FIG.mkdir(exist_ok=True)
PARTICIONES = (7, 11, 23)

# Las agujas tal como están hoy en core/memory/scoring.py (_calcular_score_hibrido).
# (nombre en el informe, peso nominal en el código, nombre de la señal en el experimento o None si está muda en el QA)
AGUJAS = [
    ("BM25 (palabras del texto)", .25, "bm25_norm"),
    ("Dimensiones semánticas", .14, "dim_score"),
    ("Nombre del concepto", .08, "concepto_ratio"),
    ("Sinónimos", .08, "sinonimos_ratio"),
    ("Peso sináptico (Hebb)", .10, None),
    ("Jaccard / cadena", .10, "latcad"),
    ("Grupo WordNet", .10, "grupo_score"),
    ("Temático (con compuerta)", .08, "tematico_g"),
    ("Recencia", .04, None),
    ("Asociaciones", .02, "asoc"),
    ("Predicados (#12)", .20, "pred_score"),
    ("PPMI+SVD (#13)", .15, "ppmi_score"),
    ("Concept Hub (#14)", .20, "hub_match"),
    ("NCD zlib", .05, "ncd_score"),
    ("Episodio", .05, "episodio_score"),
    ("Analogía (apagada)", .00, None),
    ("Campo semántico", .05, "campo_score"),
    ("JSD (#11)", .025, "jsd"),
    ("Bono: nombre exacto", None, "match_exacto"),
    ("Bono: sinónimo ≥ .95", None, "sin95"),
]


def leer_particion(s):
    txt = (RES / f"particion_{s}.txt").read_text(encoding="utf-8")
    fila = re.search(r"^R2 manual\+capa oculta\s+([\d.]+).*?\+(\d+) / -(\d+)", txt, re.M)
    lam = {float(a): (float(b), int(c), int(d)) for a, b, c, d in
           re.findall(r"lambda=([\d.]+)\s+R@1\s+([\d.]+)\s+\+(\d+) / -(\d+)", txt)}
    lam[1.0] = (float(fila.group(1)), int(fila.group(2)), int(fila.group(3)))
    lam[0.0] = (float(re.search(r"^M0 manual \(hoy\)\s+([\d.]+)", txt, re.M).group(1)), 0, 0)
    corr = dict(re.findall(r"^\s+(\w+)\s+([+-][\d.]+)$", txt.split("corrección media")[1], re.M))
    return lam, {k: float(v) for k, v in corr.items()}


def fig_agujas(corr):
    fig, ax = plt.subplots(figsize=(11, 9))
    ax.set_xlim(0, 11); ax.set_ylim(-1, len(AGUJAS)); ax.axis("off")
    soma = (7.2, len(AGUJAS) / 2 - .5)
    for i, (nom, w, sig) in enumerate(AGUJAS):
        y = len(AGUJAS) - 1 - i
        muda = sig is None
        c = corr.get(sig, 0.0) if sig else 0.0
        color = "#bbbbbb" if muda else ("#2e7d32" if c > .3 else "#c62828" if c < -.3 else "#555555")
        grosor = 1.0 if w is None else .6 + 18 * w
        estilo = "--" if (w is None or muda) else "-"
        ax.plot([3.3, soma[0] - .9], [y, soma[1]], estilo, color=color, lw=grosor, alpha=.85)
        etiqueta = f"{nom}  " + ("bono logit" if w is None else f"{w:.3g}")
        ax.text(3.2, y, etiqueta, ha="right", va="center", fontsize=9,
                color="#999999" if muda else "black")
        if sig and not muda:
            ax.text(3.35, y + .28, f"{c:+.1f}", fontsize=7, color=color)
    ax.add_patch(plt.Circle(soma, .9, color="#1565c0", alpha=.9))
    ax.text(*soma, "Σ\nsuma\n+ bonos", ha="center", va="center", color="white", fontsize=10, weight="bold")
    ax.annotate("", xy=(10.2, soma[1]), xytext=(soma[0] + .9, soma[1]),
                arrowprops=dict(arrowstyle="-|>", lw=3, color="#1565c0"))
    ax.text(9.2, soma[1] + .5, "axón:\nscore 0–1\n→ ranking", ha="center", fontsize=10)
    ax.set_title("La neurona que ya estaba en BioRAG: core/memory/scoring.py, _calcular_score_hibrido\n"
                 "grosor = peso puesto a mano · verde/rojo = lo que R1 aprendió que falta/sobra · gris = aguja muda en el QA",
                 fontsize=10)
    fig.tight_layout(); fig.savefig(FIG / "1_neurona_agujas.png", dpi=110); plt.close(fig)


def fig_sigmoide():
    x = [i / 50 for i in range(-300, 301)]
    s = [1 / (1 + math.exp(-v)) for v in x]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(x, s, color="#1565c0", lw=2.5, label="σ(z) = 1 / (1 + e^(−z))")
    p0 = .30; z0 = math.log(p0 / (1 - p0)); z1 = z0 + 2.94; p1 = 1 / (1 + math.exp(-z1))
    ax.annotate("", xy=(z1, p1), xytext=(z0, p0), arrowprops=dict(arrowstyle="-|>", lw=2, color="#c62828"))
    ax.plot([z0, z1], [p0, p1], "o", color="#c62828")
    ax.text(z0 - .2, p0 - .09, f"score base {p0:.2f}", ha="center", fontsize=9)
    ax.text(z1 + .15, p1 - .08, f"con nombre exacto {p1:.2f}\n(+2.94 en logit)", fontsize=9)
    ax.axhline(.6212, ls=":", color="gray"); ax.text(-5.8, .64, "umbral de abstención .6212", fontsize=8, color="gray")
    ax.set_xlabel("z = logit (la suma de la neurona en escala de log-odds)"); ax.set_ylabel("score")
    ax.set_title("La curva sigmoide: así actúan los bonos de BioRAG y la corrección aprendida (en logit)")
    ax.legend(loc="upper left"); ax.grid(alpha=.3)
    fig.tight_layout(); fig.savefig(FIG / "2_curva_sigmoide.png", dpi=110); plt.close(fig)


def fig_lambda(lams):
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.3))
    for s, lam in zip(PARTICIONES, lams):
        xs = sorted(lam)
        a1.plot(xs, [lam[x][0] for x in xs], "o-", label=f"partición {s}")
        a2.plot(xs, [lam[x][1] for x in xs], "o-", color="#2e7d32", alpha=.4 + .2 * PARTICIONES.index(s))
        a2.plot(xs, [lam[x][2] for x in xs], "s--", color="#c62828", alpha=.4 + .2 * PARTICIONES.index(s))
    a1.set_title("R@1 en test según cuánto se le deja corregir"); a1.set_xlabel("λ (0 = solo pesos a mano, 1 = R2 completo)")
    a1.set_ylabel("R@1 %"); a1.legend(); a1.grid(alpha=.3)
    a2.set_title("Casos que GANA (verde) y que PIERDE (rojo)"); a2.set_xlabel("λ"); a2.set_ylabel("casos")
    a2.grid(alpha=.3)
    fig.suptitle("Curva λ: a más corrección, más gana… y más pierde. Ningún λ llega a 0 pérdidas.")
    fig.tight_layout(); fig.savefig(FIG / "3_curva_lambda.png", dpi=110); plt.close(fig)


def fig_aprendizaje():
    p = RES / "curva_aprendizaje_7.json"
    if not p.exists():
        print("falta", p, "(corre curva_aprendizaje.py)"); return
    d = json.loads(p.read_text(encoding="utf-8"))
    xs = [c["casos_train"] for c in d["curva"]]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.3))
    a1.plot(xs, [c["R1"] for c in d["curva"]], "o-", color="#1565c0", label="R2 aprendido")
    a1.axhline(d["M0_R1"], ls="--", color="gray", label=f"pesos a mano {d['M0_R1']:.2f}")
    a1.set_xscale("log"); a1.set_xlabel("preguntas de entrenamiento (escala log)"); a1.set_ylabel("R@1 % en nodos nunca vistos")
    a1.set_title("Curva de aprendizaje"); a1.legend(); a1.grid(alpha=.3)
    a2.plot(xs, [c["gana"] for c in d["curva"]], "o-", color="#2e7d32", label="gana")
    a2.plot(xs, [c["pierde"] for c in d["curva"]], "s--", color="#c62828", label="pierde")
    a2.set_xscale("log"); a2.set_xlabel("preguntas de entrenamiento"); a2.set_ylabel("casos vs pesos a mano")
    a2.set_title("Ganados y perdidos"); a2.legend(); a2.grid(alpha=.3)
    for a in (a1, a2):
        a.set_xticks(xs); a.set_xticklabels([f"{x:.0f}" for x in xs]); a.minorticks_off()
    fig.suptitle("¿Cuántos ejemplos necesita la neurona? (partición 7)")
    fig.tight_layout(); fig.savefig(FIG / "4_curva_aprendizaje.png", dpi=110); plt.close(fig)
    # 6. categoría nunca vista
    cv = d["categoria_nunca_vista"]
    fig, ax = plt.subplots(figsize=(11, 4.3))
    xs6 = range(len(cv)); ancho = .27
    ax.bar([x - ancho for x in xs6], [c["M0"] for c in cv], ancho, color="#999999", label="pesos a mano")
    ax.bar(list(xs6), [c["R2_sin_verla"] for c in cv], ancho, color="#ef6c00", label="R2 SIN haber visto la categoría")
    ax.bar([x + ancho for x in xs6], [c["R2_viendola"] for c in cv], ancho, color="#1565c0", label="R2 viéndola")
    ax.set_xticks(list(xs6)); ax.set_xticklabels([f"{c['categoria']}\n(n={c['n']})" for c in cv], fontsize=8)
    ax.set_ylabel("R@1 %"); ax.set_ylim(0, 105); ax.legend(loc="lower left", fontsize=8); ax.grid(axis="y", alpha=.3)
    ax.set_title("¿Sabe buscar lo que nunca le enseñaron? Typos sí (93.85 sin verlos). Búsqueda por tema NO (63 → 28).")
    fig.tight_layout(); fig.savefig(FIG / "6_categoria_nunca_vista.png", dpi=110); plt.close(fig)


def fig_retro(caso="0739", n=6):
    ruta = AQUI / "datos" / "pools_semilla1.jsonl.gz"
    if not ruta.exists():
        print("falta", ruta, "(corre exportar_senales.py)"); return
    with gzip.open(ruta, "rt", encoding="utf-8") as fh:
        r = next(json.loads(l) for l in fh if f'"id": "{caso}"' in l or f'"id":"{caso}"' in l)
    cs = sorted(r["cands"], key=lambda k: -k["_score"])
    # softmax sobre TODO el pool (como en el entrenamiento real); se muestran los primeros y el correcto
    z = [math.log(max(1e-4, min(1 - 1e-4, k["_score"])) / (1 - max(1e-4, min(1 - 1e-4, k["_score"])))) for k in cs]
    m = max(z); e = [math.exp(v - m) for v in z]; t = sum(e); pr = [v / t for v in e]
    pos = next(i for i, k in enumerate(cs) if k["c"] == r["exp"])
    idx = list(range(n - 1)) + [pos] if pos >= n - 1 else list(range(n))
    top = [cs[i] for i in idx]
    p = [pr[i] for i in idx]
    y = [1.0 if k["c"] == r["exp"] else 0.0 for k in top]
    emp = [yi - pi for yi, pi in zip(y, p)]            # −dL/ds: el empujón que recibe cada candidato
    nombres = [f"#{i + 1} " + cs[i]["c"][:40] + ("  ← CORRECTO" if cs[i]["c"] == r["exp"] else "") for i in idx]
    # culpa de cada aguja en este caso: −dL/dw = Σ_candidatos (correcto − prob) · señal  (regla de la cadena)
    import entrenar_neurona as en
    d_todos = [(1.0 if k["c"] == r["exp"] else 0.0) - pr[i] for i, k in enumerate(cs)]
    culpa = [sum(d_todos[i] * en.feats(k)[j] for i, k in enumerate(cs)) for j in range(len(en.F_SIG))]
    fig, (a1, a2, a3) = plt.subplots(1, 3, figsize=(15, 4.6), gridspec_kw=dict(width_ratios=[1.3, .8, 1.1]))
    col = ["#2e7d32" if yi else "#888888" for yi in y]
    a1.barh(range(len(top)), p, color=col); a1.invert_yaxis()
    a1.set_yticks(range(len(top))); a1.set_yticklabels(nombres, fontsize=8)
    a1.set_title(f"1. Lo que creen los pesos a mano\n(softmax sobre {len(cs)} candidatos)", fontsize=10)
    a1.set_xlabel("probabilidad")
    imp = sum(v for v in d_todos if v < 0)
    a2.bar([0, 1], [emp[-1] if y[-1] else max(emp), imp], color=["#2e7d32", "#c62828"])
    a2.set_xticks([0, 1]); a2.set_xticklabels(["el correcto", f"los {len(cs) - 1}\nimpostores"])
    a2.axhline(0, color="black", lw=.8)
    a2.set_title("2. El error, por candidato\n(correcto − probabilidad)", fontsize=10)
    orden = sorted(range(len(culpa)), key=lambda j: culpa[j])
    a3.barh(range(len(orden)), [culpa[j] for j in orden],
            color=["#2e7d32" if culpa[j] > 0 else "#c62828" for j in orden])
    a3.set_yticks(range(len(orden))); a3.set_yticklabels([en.F_SIG[j] for j in orden], fontsize=8)
    a3.axvline(0, color="black", lw=.8)
    a3.set_title("3. Viaja hacia atrás: la culpa de cada aguja\n(verde = debería pesar más; rojo = menos)", fontsize=10)
    fig.suptitle(f"Retropropagación en un caso real, {caso} ({r['cat']}): «{r['q']}»", fontsize=11)
    fig.tight_layout(); fig.savefig(FIG / "5_retropropagacion_caso_0739.png", dpi=110); plt.close(fig)


def main():
    datos = [leer_particion(s) for s in PARTICIONES]
    fig_agujas(datos[0][1])
    fig_sigmoide()
    fig_lambda([d[0] for d in datos])
    fig_aprendizaje()
    fig_retro()
    print("figuras en", FIG)


if __name__ == "__main__":
    main()
