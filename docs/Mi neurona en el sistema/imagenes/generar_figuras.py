"""Genera las figuras de la documentación de la neurona (README, sección "La Neurona de BioRAG").

Todo sale del código o de archivos de resultados versionados en el repo:
  - nombres y cantidades de señales: core/memory/neurona.py (F_FORMULA, F_VISTA, OCULTAS)
  - curva de aprendizaje: experimento_07_la_neurona_escucha/resultados/v5/curva_uso_snapshot.jsonl
  - números de QA / camino MCP: los reportes de experimento_07 (copiados abajo, con su fuente)

Uso:  python "docs/Mi neurona en el sistema/imagenes/generar_figuras.py"
"""
import json
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch  # noqa: E402

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(AQUI, "..", "..", ".."))
sys.path.insert(0, REPO)
from core.memory import neurona as N  # noqa: E402

E7 = os.path.join(AQUI, "..", "experimento_07_la_neurona_escucha", "resultados")

FONDO, TINTA, TENUE = "#0b1426", "#e8eef8", "#8fa3c4"
ORO, CIAN, VIOLETA, VERDE, ROJO = "#f2c14e", "#4fd1e8", "#b48cff", "#5ee08f", "#ff6b6b"

plt.rcParams.update({
    "figure.facecolor": FONDO, "axes.facecolor": FONDO, "savefig.facecolor": FONDO,
    "text.color": TINTA, "axes.labelcolor": TINTA, "xtick.color": TENUE, "ytick.color": TENUE,
    "axes.edgecolor": "#2a3b5c", "font.family": "DejaVu Sans", "font.size": 10,
})

NOMBRE = {
    # 17 agujas de la fórmula a mano (core/memory/scoring.py)
    "bm25_norm": "BM25 léxico (FTS5)", "dim_score": "dimensiones (13 ejes)",
    "concepto_ratio": "palabras en el nombre", "sinonimos_ratio": "sinónimos",
    "latcad": "latente / cadena", "grupo_score": "grupo", "tematico_g": "temático",
    "asoc": "asociaciones del grafo", "pred_score": "predicados (SRL)", "ppmi_score": "PPMI-SVD",
    "hub_match": "Concept Hub", "ncd_score": "compresión (NCD)", "episodio_score": "episodio temporal",
    "campo_score": "campo semántico", "jsd": "Jensen-Shannon", "match_exacto": "match exacto",
    "sin95": "sinónimo casi exacto",
    # 12 señales de la vista: lo que pasa después de la fórmula + lo que aporta el agente
    "bono_conv": "bono de convergencia", "ev_concepto": "evidencia: nombre",
    "ev_sinonimos": "evidencia: sinónimos", "ev_sustantivos": "evidencia: sustantivos_clave",
    "ev_contenido": "evidencia: contenido", "peso": "peso sináptico", "con_peso": "¿score con peso?",
    "con_agente": "¿vino del agente?", "or_lexico": "origen: léxico aprendido",
    "or_hub": "origen: Concept Hub", "or_no_literal": "origen: no literal", "sin_rasgos": "sin rasgos (bandera)",
}


def _guardar(fig, nombre):
    ruta = os.path.join(AQUI, nombre)
    fig.savefig(ruta, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("ok", ruta)


# ───────────────────────── 1. anatomía exacta ─────────────────────────

def anatomia():
    nF, nV, H = len(N.F_FORMULA), len(N.F_VISTA), N.OCULTAS
    n = nF + nV
    hueco = 1.6                                    # separación entre los dos grupos de señales
    ys = [n + hueco - i for i in range(nF)] + [n - i for i in range(nF, n)]
    top = ys[0]
    fig, ax = plt.subplots(figsize=(15.4, 11))
    ax.set_xlim(0, 15.35)
    ax.set_ylim(-1.2, top + 2.0)
    ax.axis("off")
    cy = (ys[0] + ys[-1]) / 2
    hy = [cy + (H / 2 - i - .5) * 2.6 for i in range(H)]
    xin, xh, xo = 3.15, 7.4, 9.6

    for i in range(n):
        col = ORO if i < nF else CIAN
        for j in range(H):
            ax.plot([xin, xh], [ys[i], hy[j]], color=col, alpha=.09, lw=.8, zorder=1)
    for i, s in enumerate(N.F_SIG):
        col = ORO if i < nF else CIAN
        ax.text(xin - .3, ys[i], NOMBRE.get(s, s), ha="right", va="center", fontsize=9.4, color=TINTA)
        ax.text(xin + .3, ys[i] + .02, s, ha="left", va="center", fontsize=6.6, color=TENUE, family="monospace")
    ax.scatter([xin] * nF, ys[:nF], s=70, color=ORO, zorder=3, edgecolors="none")
    ax.scatter([xin] * nV, ys[nF:], s=70, color=CIAN, zorder=3, edgecolors="none")
    ax.text(1.75, top + .95, f"{nF} AGUJAS DE LA FÓRMULA A MANO", color=ORO, fontsize=11, weight="bold", ha="center")
    ax.text(1.75, ys[nF] + .95, f"{nV} SEÑALES DE LA VISTA Y DEL AGENTE", color=CIAN, fontsize=11,
            weight="bold", ha="center")

    for j in range(H):
        ax.plot([xh, xo], [hy[j], cy], color=VIOLETA, alpha=.6, lw=1.5, zorder=1)
    ax.scatter([xh] * H, hy, s=1100, color=VIOLETA, zorder=3, edgecolors="#d9c8ff", linewidths=1.2)
    for j in range(H):
        ax.text(xh, hy[j], "tanh", ha="center", va="center", fontsize=8, color=FONDO, weight="bold", zorder=4)
    ax.text(xh, max(hy) + 1.4, f"{H} NEURONAS OCULTAS", color=VIOLETA, fontsize=11, weight="bold", ha="center")
    ax.text(xh, min(hy) - 1.5, f"W: {H}×{n}   b: {H}", color=TENUE, fontsize=9.5, ha="center", family="monospace")

    ax.scatter([xo], [cy], s=1500, color=VERDE, zorder=3, edgecolors="#c9f7da", linewidths=1.2)
    ax.text(xo, cy, "Σ", ha="center", va="center", fontsize=18, color=FONDO, weight="bold", zorder=4)
    ax.text(xo, cy + 1.6, "corrección c(x)", ha="center", color=VERDE, fontsize=10.5, weight="bold")
    ax.text(xo, cy - 1.6, f"v: {H}", ha="center", color=TENUE, fontsize=9.5, family="monospace")

    bx, bw, bh = 10.55, 4.35, 12.2
    ax.add_patch(FancyBboxPatch((bx, cy - bh / 2), bw, bh, boxstyle="round,pad=0.15", fc="#12213d", ec=VERDE, lw=1.4))
    ax.add_patch(FancyArrowPatch((xo + .5, cy), (bx - .05, cy), arrowstyle="-|>", mutation_scale=16, color=VERDE, lw=1.6))
    lineas = [
        ("CÓMO DECIDE EL ORDEN", VERDE, 11.5, "bold", False),
        ("", TINTA, 8, None, False),
        ("clave(i) = logit(score_i)", TINTA, 10.5, None, True),
        ("         + c(x_i)", TINTA, 10.5, None, True),
        ("         + ε·(k − puesto_i)", TINTA, 10.5, None, True),
        ("", TINTA, 8, None, False),
        ("c(x) = vᵀ · tanh(W·x + b)", VIOLETA, 10.5, None, True),
        ("ε = margen \"primero no dañar\"", ORO, 10, None, True),
        ("", TINTA, 8, None, False),
        ("Reordena SOLO el top-k que ya", TENUE, 9.5, None, False),
        ("eligió el motor (k = 5, o 10", TENUE, 9.5, None, False),
        ("por el MCP): mismos recuerdos,", TENUE, 9.5, None, False),
        ("mismos scores, nuevo orden.", TENUE, 9.5, None, False),
    ]
    paso = (bh - 1.4) / len(lineas)
    for i, (t, c, fs, w, mono) in enumerate(lineas):
        ax.text(bx + .25, cy + bh / 2 - .75 - i * paso, t, color=c, fontsize=fs, weight=w or "normal",
                family="DejaVu Sans Mono" if mono else "DejaVu Sans", va="center")

    total = H * n + H + H
    ax.text(7.5, top + 1.75, "LA NEURONA DE BIORAG — anatomía exacta", ha="center", fontsize=16, weight="bold")
    ax.text(7.5, -0.9, f"{n} entradas → {H} ocultas → 1 corrección   ·   {total} pesos en total   ·   "
            "con c(x) = 0 el motor es exactamente la fórmula a mano", ha="center", fontsize=10, color=TENUE)
    _guardar(fig, "anatomia_neurona.png")


# ───────────────────────── 2. ciclo de vida ─────────────────────────

def ciclo():
    fig, ax = plt.subplots(figsize=(15, 7.2))
    ax.set_xlim(0, 15)
    ax.set_ylim(0, 7.2)
    ax.axis("off")
    ax.text(7.5, 6.85, "EL CICLO DE VIDA: aprende al guardar, sirve al buscar", ha="center", fontsize=15, weight="bold")

    def caja(x, y, w, h, titulo, cuerpo, col):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.12", fc="#12213d", ec=col, lw=1.6))
        ax.text(x + w / 2, y + h - .32, titulo, ha="center", va="top", color=col, fontsize=10, weight="bold")
        ax.text(x + w / 2, y + h - .78, cuerpo, ha="center", va="top", color=TINTA, fontsize=8.6, linespacing=1.35)

    def flecha(a, b, col=TENUE, texto=None, curva=0.0):
        ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-|>", mutation_scale=15, color=col, lw=1.5,
                                     connectionstyle=f"arc3,rad={curva}"))
        if texto:
            ax.text((a[0] + b[0]) / 2, (a[1] + b[1]) / 2 + .18, texto, ha="center", color=col, fontsize=8)

    y1 = 4.15
    caja(.2, y1, 2.55, 2.1, "1 · CONSOLIDAR", "se guarda un recuerdo\n(o el ciclo de sueño)\n\n2 recuerdos × 2 preguntas\npor ciclo · tope 3 s", ORO)
    caja(3.15, y1, 2.75, 2.1, "2 · AUTOEXAMEN", "el recuerdo se pregunta\na sí mismo: typo, sinónimo,\nvariante, cruce de idioma,\npregunta natural, tema…", ORO)
    caja(6.3, y1, 2.75, 2.1, "3 · EN SILENCIO", "el motor responde por los\nDOS caminos reales:\nagente (MCP) y crudo (QA)\nsin log, sin DMN, sin accesos", CIAN)
    caja(9.45, y1, 2.6, 2.1, "4 · LA VISTA", "lo que se sirvió, tal cual:\n29 señales × top-k\n+ dónde quedó la respuesta\n(desfase 0)", CIAN)
    caja(12.45, y1, 2.35, 2.1, "5 · EL EXAMEN", "memoria fija:\n80 % ESTUDIO · 20 % GUARDIA\n(por hash del nombre;\nla guardia nunca se estudia)", VIOLETA)
    for a, b in ((2.75, 3.15), (5.9, 6.3), (9.05, 9.45), (12.05, 12.45)):
        flecha((a + .02, y1 + 1.05), (b - .02, y1 + 1.05))

    y2 = .45
    caja(12.45, y2, 2.35, 2.55, "6 · ESTUDIA", "el RETADOR: 30 pasos\nde Adam (lr 0.03, L2 0.001)\nsolo sobre el ESTUDIO\n\npérdida: entropía cruzada\n(softmax del top-k)", VIOLETA)
    caja(8.7, y2, 3.35, 2.55, "7 · ¿ASCIENDE?", "solo si, con el menor margen ε:\n· no pierde NINGÚN caso de guardia\n· pierde < 5 % de lo que gana\n· ninguna categoría baja (R@1, MRR, R@5)\n· le gana a la fórmula\n· la guardia no lo delata (memorizar)", VERDE)
    caja(4.75, y2, 3.55, 2.55, "8 · CAMPEÓN EN SERVICIO", "cada búsqueda normal:\nla fórmula elige el top-k,\nel campeón solo lo REORDENA\n\nsi un día daña algo → se retira\ny vuelve la fórmula a mano", VERDE)
    caja(.2, y2, 4.15, 2.55, "9 · TECHO Y DESPERTAR", "12 ciclos sin mejorar → \"tranquila\"\n(solo vigila, mitad de costo)\n\n150 preguntas nuevas → despierta\ny vuelve a estudiar", ORO)
    flecha((13.62, y1 - .02), (13.62, y2 + 2.57), VIOLETA)
    flecha((12.43, y2 + 1.27), (12.07, y2 + 1.27), VERDE)
    flecha((8.68, y2 + 1.27), (8.32, y2 + 1.27), VERDE, None)
    flecha((4.73, y2 + 1.27), (4.37, y2 + 1.27), ORO)
    flecha((2.3, y2 + 2.57), (1.5, y1 - .02), ORO, "", 0.0)
    _guardar(fig, "ciclo_de_vida.png")


# ───────────────────────── 3. curva de aprendizaje ─────────────────────────

def curva():
    L = [json.loads(x) for x in open(os.path.join(E7, "v5", "curva_uso_snapshot.jsonl"), encoding="utf-8")]
    xs, gm, gc, ms = [], [], [], []
    for r in L:
        if r.get("guardia_mano") is not None:
            xs.append(r["ciclo"])
            gm.append(100 * r["guardia_mano"])
            gc.append(100 * (r.get("guardia_campeon") if r.get("guardia_campeon") is not None else r["guardia_mano"]))
        ms.append(r["ms"])
    asc = [r["ciclo"] for r in L if r.get("fase") == "ascenso"]
    techo = [r["ciclo"] for r in L if str(r.get("fase", "")).startswith("tranquila (techo)")]

    fig, (a1, a2) = plt.subplots(2, 1, figsize=(13, 7.4), sharex=True, gridspec_kw={"height_ratios": [3, 1.25]})
    a1.plot(xs, gm, color=ORO, lw=2, label="fórmula a mano")
    a1.plot(xs, gc, color=VERDE, lw=2.2, label="con la neurona (campeón)")
    a1.fill_between(xs, gm, gc, where=[c > m for c, m in zip(gc, gm)], color=VERDE, alpha=.12)
    for c in asc:
        a1.axvline(c, color=VERDE, alpha=.35, lw=1, ls=":")
    if techo:
        a1.axvline(techo[0], color=VIOLETA, alpha=.7, lw=1.3, ls="--")
        a1.text(techo[0] + 4, min(gm) + 1, "primer techo:\nse queda tranquila", color=VIOLETA, fontsize=8.5)
    a1.text(.985, .96, f"{len(asc)} ascensos (líneas punteadas): ciclos {', '.join(map(str, asc))}\n"
            f"guardia al final: fórmula {gm[-1]:.1f} %  →  neurona {gc[-1]:.1f} %",
            transform=a1.transAxes, ha="right", va="top", color=VERDE, fontsize=9)
    a1.text(.01, .04, "antes del ciclo 84 no hay curva: está juntando el examen (mínimo 150 de estudio y 40 de guardia)",
            transform=a1.transAxes, color=TENUE, fontsize=8.3)
    a1.set_ylabel("aciertos #1 en la GUARDIA (%)\n(recuerdos que nunca estudió)")
    a1.set_title("Aprende con el uso: 500 consolidaciones sobre una copia del snapshot (~900 recuerdos)",
                 fontsize=12.5, weight="bold", loc="left")
    a1.set_ylim(min(gm) - 4.5, max(gc) + 3.0)
    a1.legend(loc="lower right", frameon=False, bbox_to_anchor=(1, .06))
    a1.grid(alpha=.12)
    a2.plot(range(1, len(ms) + 1), [m / 1000 for m in ms], color=CIAN, lw=.8, alpha=.85)
    a2.axhline(3.0, color=ROJO, lw=1, ls="--", alpha=.7)
    a2.text(.01, .93, "presupuesto 3 s: no EMPIEZA una pregunta que no cabe (los picos son una pregunta lenta ya empezada). "
            "No crece con el tamaño de la memoria.", transform=a2.transAxes, va="top", color=ROJO, fontsize=8.2)
    a2.set_ylim(0, max(m / 1000 for m in ms) * 1.35)
    a2.set_ylabel("segundos\npor ciclo")
    a2.set_xlabel("ciclo de consolidación")
    a2.grid(alpha=.12)
    _guardar(fig, "curva_aprendizaje.png")


# ───────────────────────── 4. resultados ─────────────────────────

def _barras(ax, etiquetas, series, colores, nombres, ymin, fmt="{:.2f}"):
    import numpy as np
    x = np.arange(len(etiquetas))
    w = .8 / len(series)
    for i, (s, c, nom) in enumerate(zip(series, colores, nombres)):
        b = ax.bar(x + (i - (len(series) - 1) / 2) * w, s, w * .92, color=c, label=nom)
        for r, v in zip(b, s):
            ax.text(r.get_x() + r.get_width() / 2, v + .4, fmt.format(v), ha="center", fontsize=7.6, color=TINTA)
    ax.set_xticks(x)
    ax.set_xticklabels(etiquetas)
    ax.set_ylim(ymin, 103)
    ax.grid(axis="y", alpha=.12)


def resultados(qa_neurona=None):
    # Piso = tabla oficial de Dennys (fórmula a mano). Neurona = QA oficial tras el despertar
    # (resultados/despertar/qa_tras_despertar.txt) o, si no está, la del experimento 07 (resultados/v5).
    cats = ["cruce_idioma", "dormido", "literal", "por_tema", "pregunta_natural", "sinonimo", "typo", "variante_gramatical"]
    piso = [62.50, 100.0, 99.59, 63.08, 93.85, 56.36, 87.69, 87.69]
    neu = qa_neurona or [87.50, 100.0, 99.59, 73.85, 96.92, 60.00, 96.92, 95.38]
    fig, ax = plt.subplots(figsize=(13, 5.4))
    _barras(ax, [c.replace("_", "\n") for c in cats], [piso, neu], [ORO, VERDE],
            ["piso: fórmula a mano", "con la neurona (tras despertar_neurona.sh, 500 ciclos)"], 40)
    ax.set_ylabel("Recall@1 (%) · el eje empieza en 40")
    ax.set_title("QA oficial (921 casos), Recall@1 por categoría — ninguna baja del piso · R@5 global 99.89 → 100 % · FP 0/40",
                 fontsize=11.5, weight="bold", loc="left")
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(.5, -.16), ncol=2)
    _guardar(fig, "qa_por_categoria.png")

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 4.8), gridspec_kw={"width_ratios": [1.6, 1]})
    et = ["MCP antes\n(auto-paráfrasis)", "MCP arreglado\n(fórmula a mano)", "neurona v4", "neurona v5"]
    r1 = [85.14, 92.34, 94.51, 94.97]
    cols = [ROJO, ORO, CIAN, VERDE]
    b = a1.bar(range(4), r1, color=cols, width=.62)
    for r, v in zip(b, r1):
        a1.text(r.get_x() + r.get_width() / 2, v + .3, f"{v:.2f}", ha="center", fontsize=9.5, weight="bold")
    a1.set_xticks(range(4))
    a1.set_xticklabels(et, fontsize=8.8)
    a1.set_ylim(80, 97)
    a1.set_ylabel("Recall@1 (%) · el eje empieza en 80")
    a1.set_title("El camino REAL del agente (recordar por MCP, 875 casos)", fontsize=11, weight="bold", loc="left")
    a1.grid(axis="y", alpha=.12)
    b = a2.bar([0, 1], [46.7, 0.0], color=[ROJO, VERDE], width=.55)
    a2.text(0, 48, "46.7 %", ha="center", fontsize=11, weight="bold")
    a2.text(1, 1.5, "0 %\n(0 de 289)", ha="center", fontsize=11, weight="bold", color=VERDE)
    a2.set_xticks([0, 1])
    a2.set_xticklabels(["v4", "v5"])
    a2.set_ylim(0, 58)
    a2.set_ylabel("% de consultas")
    a2.set_title("Desfase: lo que estudia ≠ lo que sirve", fontsize=11, weight="bold", loc="left")
    a2.text(.5, .9, "consultas reales cuyo top-5 estudiado\nno era el top-5 servido", transform=a2.transAxes,
            ha="center", color=TENUE, fontsize=8.5)
    a2.grid(axis="y", alpha=.12)
    _guardar(fig, "camino_mcp_y_desfase.png")


def _leer_qa_despertar():
    p = os.path.join(E7, "despertar", "qa_tras_despertar.txt")
    if not os.path.isfile(p):
        return None
    orden = ["cruce_idioma", "dormido", "literal", "por_tema", "pregunta_natural", "sinonimo", "typo", "variante_gramatical"]
    d = {}
    for linea in open(p, encoding="utf-8"):
        partes = [x.strip() for x in linea.split("|")]
        if len(partes) >= 4 and partes[0] in orden:
            d[partes[0]] = float(partes[3].rstrip("%"))
    return [d[c] for c in orden] if len(d) == len(orden) else None


if __name__ == "__main__":
    anatomia()
    ciclo()
    curva()
    resultados(_leer_qa_despertar())
