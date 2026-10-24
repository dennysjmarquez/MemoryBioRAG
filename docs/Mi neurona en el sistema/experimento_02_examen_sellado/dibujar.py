#!/usr/bin/env python3
"""Figuras del experimento 02 a partir de resultados/parte_{A,B}_7.json. Requiere matplotlib."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

AQUI = Path(__file__).resolve().parent
RES, FIG = AQUI / "resultados", AQUI / "figuras"
FIG.mkdir(exist_ok=True)


def fig_a():
    d = json.loads((RES / "parte_A_7.json").read_text(encoding="utf-8"))
    fig, axs = plt.subplots(1, 2, figsize=(12, 4.4), sharey=True)
    for ax, (h, filas) in zip(axs, d["curvas"].items()):
        x = [f["paso"] for f in filas]
        ax.plot(x, [f["estudio"] for f in filas], "o-", color="#ef6c00", label="lo que estudió")
        ax.plot(x, [f["nuevos"] for f in filas], "s-", color="#1565c0", label="nodos que nunca vio")
        mejor = max(filas, key=lambda f: f["nuevos"])
        ax.axvline(mejor["paso"], ls=":", color="#2e7d32")
        ax.text(mejor["paso"], 92, f" mejor punto\n paso {mejor['paso']}", color="#2e7d32", fontsize=9)
        ax.set_title(f"Neurona con {h} neuronas ocultas"); ax.set_xlabel("pasadas de entrenamiento")
        ax.grid(alpha=.3); ax.legend(loc="center right")
    axs[0].set_ylabel("R@1 %")
    fig.suptitle("Entrenar hasta 100 %: lo estudiado sube a 100, lo nuevo empeora (memoriza en vez de aprender)")
    fig.tight_layout(); fig.savefig(FIG / "A_hasta_100.png", dpi=110); plt.close(fig)


def fig_b():
    nombres = {"sin_compuerta": "neurona\nsin compuerta", "compuerta_lambda": "compuerta λ",
               "compuerta_margen": "compuerta de\nmargen", "compuerta_ambas": "λ + margen",
               "compuerta_lambda_exacto": "λ + nombre\nexacto"}
    parts = [s for s in (7, 11, 23) if (RES / f"parte_B_{s}.json").exists()]
    ds = {s: json.loads((RES / f"parte_B_{s}.json").read_text(encoding="utf-8")) for s in parts}
    vs = [v for v in nombres if all(v in ds[s]["versiones"] for s in parts)]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 4.6))
    ancho = .8 / len(parts)
    for j, s in enumerate(parts):
        x = [i + (j - (len(parts) - 1) / 2) * ancho for i in range(len(vs))]
        a1.bar(x, [len(ds[s]["versiones"][v]["gana"]) for v in vs], ancho, color="#2e7d32",
               alpha=.45 + .25 * j, label=f"partición {s}")
        perd = [len(set(ds[s]["versiones"][v]["pierde_1"]) | set(ds[s]["versiones"][v]["pierde_top5"])) for v in vs]
        a2.bar(x, perd, ancho, color="#c62828", alpha=.45 + .25 * j, label=f"partición {s}")
        for xi, p in zip(x, perd):
            a2.text(xi, p + .1, str(p), ha="center", fontsize=7)
    for ax, t in ((a1, "Casos GANADOS (puesto 1) frente a los pesos a mano"),
                  (a2, "Casos que BAJAN (pierden el 1.º o salen del top-5)")):
        ax.set_xticks(range(len(vs))); ax.set_xticklabels([nombres[v] for v in vs], fontsize=8)
        ax.set_title(t, fontsize=10); ax.grid(axis="y", alpha=.3); ax.legend(fontsize=8)
    fig.suptitle("Examen sellado: la compuerta 'ningún caso baja' casi elimina las pérdidas… y se lleva la mayor parte de la ganancia")
    fig.tight_layout(); fig.savefig(FIG / "B_examen_sellado.png", dpi=110); plt.close(fig)


if __name__ == "__main__":
    for f in (fig_a, fig_b):
        try:
            f()
        except FileNotFoundError as e:
            print("falta", e.filename)
    print("figuras en", FIG)
