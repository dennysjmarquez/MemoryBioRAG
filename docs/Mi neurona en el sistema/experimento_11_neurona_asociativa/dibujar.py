"""Dibuja las figuras del experimento 11 (la neurona asociativa) en figuras/.

Todo sale del código y de los resultados versionados:
  - pesos, agujas, umbrales:   neurona_asociativa.py (PISO, AGUJAS, CONTEXTO, TECHO, OCULTAS...)
  - números:                   resultados/*.json (lo que escribieron fabrica.py, variantes.py
                               y datos_figuras.py)
No hace falta ninguna base de datos para dibujar.

Uso:  python dibujar.py
"""
import json
import math
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Wedge  # noqa: E402

import neurona_asociativa as na  # noqa: E402

AQUI = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(AQUI, "resultados")
FIG = os.path.join(AQUI, "figuras")
os.makedirs(FIG, exist_ok=True)


def _j(nombre):
    with open(os.path.join(RES, nombre), encoding="utf-8") as fh:
        return json.load(fh)


BANCO = _j("banco_calibracion.json")
NUNCA = _j("examen_nunca_vista.json")
DEN = _j("examen_dennys.json")
VAR = _j("variantes.json")
FD = _j("figuras_dennys.json")
DC = DEN["completa (texto + tiempo + dims)"]
DT = DEN["solo texto (sin tiempo ni dims)"]

# ---------- estilo (el mismo de las figuras de la primera neurona) ----------
FONDO, PANEL, TINTA, TENUE, LINEA = "#0b1426", "#111f3a", "#e8eef8", "#8fa3c4", "#2a3b5c"
ORO, CIAN, VIOLETA, VERDE, ROJO, NARANJA, ROSA, AZUL = (
    "#f2c14e", "#4fd1e8", "#b48cff", "#5ee08f", "#ff6b6b", "#ff9f43", "#ff7eb6", "#5b8cff")
plt.rcParams.update({
    "figure.facecolor": FONDO, "axes.facecolor": FONDO, "savefig.facecolor": FONDO,
    "text.color": TINTA, "axes.labelcolor": TINTA, "xtick.color": TENUE, "ytick.color": TENUE,
    "axes.edgecolor": LINEA, "font.family": "DejaVu Sans", "font.size": 10,
    "axes.spines.top": False, "axes.spines.right": False,
})

MEMORIAS = ["noticias", "diccionario", "relatos", "codigo", "charla", "noticias_es", "machado"]
MEM_TXT = {"noticias": "noticias\n(en)", "diccionario": "diccionario\n(en)", "relatos": "relatos\n(en)",
           "codigo": "código\n(Python)", "charla": "chat\n(en)", "noticias_es": "noticias\n(es)",
           "machado": "Machado\n(pt)"}

# Cada aguja con la parte del hipocampo que imita
REGION = {
    "parecido": ("Corteza", ORO), "semantica": ("Corteza", ORO), "cobertura": ("Corteza", ORO),
    "rareza_max": ("Giro dentado", ROSA), "rareza_media": ("Giro dentado", ROSA),
    "pistas_raras": ("Giro dentado", ROSA), "una_sola": ("Giro dentado", ROSA),
    "mutuo": ("CA3", VIOLETA), "vecinos": ("CA3", VIOLETA),
    "hub": ("Homeostasis", NARANJA),
    "episodio": ("Células de tiempo", CIAN), "etiquetas": ("Esquemas (prefrontal)", VERDE),
}
DICE = {
    "parecido": "¿usan las mismas palabras?", "semantica": "¿significan lo mismo?",
    "rareza_max": "¿comparten una pista muy rara?", "rareza_media": "¿qué tan raras son las pistas?",
    "pistas_raras": "¿cuántas pistas raras comparten?", "cobertura": "¿lo importante de uno está en el otro?",
    "mutuo": "¿se eligen el uno al otro?", "vecinos": "¿tienen los mismos amigos?",
    "hub": "¿alguno se parece a todo?", "una_sola": "¿se tocan por una sola palabra?",
    "episodio": "¿se guardaron cerca en el tiempo?", "etiquetas": "¿comparten etiquetas (dims)?",
}
TIPO_COLOR = {"manual": VERDE, "sinonimo_explicito": ORO, "co_ocurrencia": CIAN, "co_nombre": AZUL,
              "co_semantica": VIOLETA, "pmi_hebbiano": NARANJA, "latente_confirmada": ROSA,
              "dmn_synthesized": "#c9d4e8"}
TIPO_TXT = {"manual": "manual (humano)", "sinonimo_explicito": "sinónimo", "co_ocurrencia": "co-ocurrencia",
            "co_nombre": "co-nombre", "co_semantica": "co-semántica", "pmi_hebbiano": "PMI hebbiano",
            "latente_confirmada": "latente (Gemini sí)", "dmn_synthesized": "DMN"}


def _guardar(fig, nombre):
    ruta = os.path.join(FIG, nombre)
    fig.savefig(ruta, dpi=140, bbox_inches="tight")
    plt.close(fig)
    print("ok", nombre)


def _caja(ax, x, y, w, h, color, borde=None, ls="-", lw=1.6, r=0.25, alpha=1.0, z=2):
    p = FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0.02,rounding_size={r}",
                       fc=color, ec=borde or color, lw=lw, ls=ls, alpha=alpha, zorder=z)
    ax.add_patch(p)
    return p


def _flecha(ax, a, b, color=TENUE, lw=1.8, ls="-", estilo="-|>", ms=14, rad=0.0, z=3):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle=estilo, mutation_scale=ms, color=color, lw=lw, ls=ls,
                                 connectionstyle=f"arc3,rad={rad}", zorder=z))


def _lienzo(w, h, xl, yl):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, xl)
    ax.set_ylim(0, yl)
    ax.axis("off")
    return fig, ax


# =====================================================================================
# 1. Anatomía
# =====================================================================================
def fig_anatomia():
    fig, ax = _lienzo(17, 11.5, 17, 11.5)
    ax.text(8.5, 11.15, "LA NEURONA ASOCIATIVA DE BIORAG — anatomía", ha="center", fontsize=19, weight="bold")
    ax.text(8.5, 10.72, "Decide si dos recuerdos de verdad tienen que ver. Nace calibrada de fábrica: "
            "no se entrena con tu memoria.", ha="center", color=TENUE, fontsize=11.5)

    sx, sy = 9.0, 6.2                                   # soma (Σ)
    ys = np.linspace(9.9, 3.3, len(na.AGUJAS))
    ax.text(0.15, 10.3, "12 AGUJAS  (lo que mira de cada par)", color=ORO, weight="bold", fontsize=12.5)
    for y, a in zip(ys, na.AGUJAS):
        reg, col = REGION[a]
        w = na.PISO.get(a, 0.0)
        ax.add_patch(Circle((3.55, y), 0.12, color=col, zorder=4))
        ax.text(3.3, y + 0.07, a, ha="right", va="center", fontsize=11.5, weight="bold")
        ax.text(3.3, y - 0.2, DICE[a], ha="right", va="center", fontsize=8.6, color=TENUE)
        if w > 0:
            ax.plot([3.7, sx - 0.95], [y, sy], color=col, lw=1.2 + 1.6 * w, alpha=0.9, zorder=2,
                    solid_capstyle="round")
            t = 0.32
            if a not in ("episodio", "etiquetas"):
                ax.text(3.7 + t * (sx - 0.95 - 3.7), y + t * (sy - y), f"×{w:g}", color=col, fontsize=11,
                        weight="bold", ha="center", va="center", zorder=6,
                        bbox=dict(fc=FONDO, ec=col, boxstyle="round,pad=0.25", lw=1.2))
        else:
            ax.plot([3.7, sx - 0.95], [y, sy], color=TENUE, lw=0.8, ls=(0, (3, 4)), alpha=0.45, zorder=1)
        if a in ("episodio", "etiquetas"):                # la llave de auto-regulación
            t = 0.2 if a == "episodio" else 0.5
            vx, vy = 3.7 + t * (sx - 0.95 - 3.7), y + t * (sy - y)
            _caja(ax, vx - 0.7, vy - 0.2, 1.4, 0.4, PANEL, col, lw=1.6, r=0.12, z=5)
            ax.text(vx, vy, f"×{na.PISO[a]:g} · fiabilidad", ha="center", va="center", fontsize=8.5, color=col, zorder=6,
                    weight="bold")
    ax.text(4.55, 2.95, "línea gruesa = peso en el piso   ·   punteada = peso 0 en el piso\n"
            "(la parte que aprende sí las ve todas)", fontsize=8.8, color=TENUE, ha="left")

    # leyenda de regiones
    regs = []
    for a in na.AGUJAS:
        if REGION[a] not in regs:
            regs.append(REGION[a])
    for i, (r, c) in enumerate(regs):
        x = 0.25 + (i % 3) * 2.05
        y = 2.3 - (i // 3) * 0.36
        ax.add_patch(Circle((x, y), 0.1, color=c))
        ax.text(x + 0.2, y, r, va="center", fontsize=9.5)
    ax.text(0.15, 2.68, "Cada color = la parte del hipocampo que imita", color=TENUE, fontsize=9.5)

    # soma
    ax.add_patch(Circle((sx, sy), 0.95, color=AZUL, zorder=6))
    ax.text(sx, sy + 0.25, "Σ", ha="center", va="center", fontsize=26, weight="bold", zorder=7)
    ax.text(sx, sy - 0.38, "PISO", ha="center", va="center", fontsize=11, weight="bold", zorder=7)
    ax.text(sx, sy + 1.25, f"sesgo {na.PISO['sesgo']:g}", ha="center", color=TENUE, fontsize=10)

    # contexto + corrección (apagada)
    cx, cy = 5.3, 0.55
    ax.text(cx - 0.2, 1.55, "3 SEÑALES DE CONTEXTO", color=CIAN, weight="bold", fontsize=10.5)
    for i, c in enumerate(na.CONTEXTO):
        ax.add_patch(Circle((cx + 0.05, 1.22 - i * 0.36), 0.09, color=CIAN))
        ax.text(cx + 0.25, 1.22 - i * 0.36, {"largo": "largo de los textos",
                                             "fiab_episodio": "¿el reloj es fiable aquí?",
                                             "fiab_etiquetas": "¿las etiquetas son fiables aquí?"}[c],
                va="center", fontsize=9.5)
    _caja(ax, 8.15, 0.25, 3.6, 1.6, PANEL, VIOLETA, ls=(0, (4, 3)), lw=1.8)
    ax.text(9.95, 1.55, "PARTE QUE APRENDE", ha="center", color=VIOLETA, weight="bold", fontsize=10.5)
    ax.text(9.95, 1.15, f"15 entradas → {na.OCULTAS} neuronas → ±{na.TECHO:g} (techo)", ha="center",
            fontsize=9.2)
    ax.text(9.95, 0.68, "APAGADA de fábrica (escala 0)", ha="center", color=ROJO, weight="bold",
            fontsize=10.5)
    ax.text(9.95, 0.38, "lo que ayuda a una memoria, daña a otra", ha="center", fontsize=8.5, color=TENUE)
    _flecha(ax, (8.0, 1.05), (7.95, 1.05), VIOLETA)
    ax.plot([7.75, 8.1], [1.05, 1.05], color=CIAN, lw=1.5)
    _flecha(ax, (9.95, 1.9), (sx, sy - 1.0), VIOLETA, ls=(0, (4, 3)), lw=1.6)
    ax.text(9.65, 3.6, "+ corrección\n(hoy suma 0)", color=VIOLETA, fontsize=9, ha="left")

    # axón: sigmoide → fuerza
    _flecha(ax, (sx + 0.97, sy), (11.2, sy), AZUL, lw=3)
    ia = ax.inset_axes([11.25, 5.35, 1.9, 1.7], transform=ax.transData)
    z = np.linspace(-6, 6, 200)
    ia.plot(z, 1 / (1 + np.exp(-z)), color=AZUL, lw=2.4)
    ia.axhline(na.UMBRAL_CONECTAR, color=VERDE, lw=1, ls="--")
    ia.set_xticks([])
    ia.set_yticks([0, .5, 1])
    ia.tick_params(labelsize=7)
    ia.set_facecolor(PANEL)
    ax.text(12.2, 7.25, "fuerza = 1 / (1 + e^−z)", ha="center", fontsize=9.5)
    ax.text(12.2, 5.0, "un número de 0 a 1", ha="center", fontsize=9, color=TENUE)
    _flecha(ax, (13.25, sy), (13.75, sy), AZUL, lw=3)

    # competencia
    _caja(ax, 13.8, 4.25, 3.05, 3.9, PANEL, VERDE, lw=1.8)
    ax.text(15.32, 7.75, "COMPETENCIA", ha="center", color=VERDE, weight="bold", fontsize=12)
    ax.text(15.32, 7.25, f"cada recuerdo se queda\ncon sus {na.K_COMPETENCIA} socios\nmás fuertes",
            ha="center", va="top", fontsize=10)
    ax.text(15.32, 5.8, f"+ todo lo que pase\nde {na.UMBRAL_CONECTAR:.2f} (seguro)", ha="center", va="top",
            fontsize=10)
    ax.text(15.32, 4.75, "nunca deja a nadie solo", ha="center", fontsize=9, color=TENUE)
    # estados
    for i, (t, c) in enumerate([("conectar  ≥ .80", VERDE), ("débil  .50–.80", ORO), ("no  < .50", ROJO)]):
        _caja(ax, 13.95 + i * 0.0, 3.5 - i * 0.5, 2.75, 0.38, c, alpha=0.2, r=0.1)
        ax.text(15.32, 3.69 - i * 0.5, t, ha="center", va="center", color=c, fontsize=9.5, weight="bold")
    ax.text(15.32, 1.95, "estado de lo que ganó", ha="center", fontsize=8.5, color=TENUE)

    # fórmula
    _caja(ax, 12.3, 8.45, 4.55, 1.95, PANEL, ORO, lw=1.4)
    ax.text(14.57, 10.05, "EL PISO (instinto de nacimiento)", ha="center", color=ORO, weight="bold",
            fontsize=10.5)
    ax.text(14.57, 9.25, "z = −1 + 2·parecido + 1·semantica\n   + 1·rareza_max + 4·episodio\n"
            "   + 1·etiquetas", ha="center", va="center", fontsize=10, family="DejaVu Sans Mono")
    ax.text(8.5, 0.0, "Hoy la neurona = el piso: 5 pesos elegidos con 7 memorias de fábrica · "
            "solo numpy · constante por par", ha="center", fontsize=9.5, color=TENUE)
    _guardar(fig, "01_anatomia.png")


# =====================================================================================
# 2. Hipocampo → neurona
# =====================================================================================
def fig_hipocampo():
    fig, ax = _lienzo(16, 9, 16, 9)
    ax.text(8, 8.6, "Lo que hace tu hipocampo al guardar y enlazar — y lo que copia la neurona",
            ha="center", fontsize=17, weight="bold")
    pasos = [
        ("Lo que vives", "un recuerdo nuevo\ny los que ya tienes", TENUE, "el motor propone\ncandidatos"),
        ("Corteza entorrinal", "resume lo que\nllega", ORO, "las 12 agujas\nparecido · semantica\ncobertura"),
        ("Giro dentado", "separa lo parecido\npero distinto\n(le da peso a lo raro)", ROSA,
         "rareza_max · rareza_media\npistas_raras · una_sola"),
        ("CA3", "completa patrones:\nmismos vecinos →\nse asocian", VIOLETA, "mutuo · vecinos"),
        ("CA1", "compara y decide;\nsolo ganan los\nmás fuertes", AZUL, "fuerza + competencia\n(top 10 por recuerdo)"),
        ("Sinapsis nueva", "queda unida en\nel grafo", VERDE, "propuesta → a prueba\n→ activa → consolidada"),
    ]
    w, h, y = 2.3, 2.3, 4.3
    xs = np.linspace(0.3, 13.4, len(pasos))
    for i, (t, d, c, n) in enumerate(pasos):
        x = xs[i]
        _caja(ax, x, y, w, h, PANEL, c, lw=2.2)
        ax.text(x + w / 2, y + h - 0.35, t, ha="center", color=c, weight="bold", fontsize=11.5)
        ax.text(x + w / 2, y + h / 2 - 0.25, d, ha="center", va="center", fontsize=9.6)
        ax.text(x + w / 2, y - 0.25, "en la neurona:", ha="center", fontsize=8.5, color=TENUE)
        ax.text(x + w / 2, y - 0.55, n, ha="center", va="top", fontsize=9.2, color=c)
        if i < len(pasos) - 1:
            _flecha(ax, (x + w + 0.03, y + h / 2), (xs[i + 1] - 0.03, y + h / 2), c, lw=2.2)
    # entradas laterales a CA1
    lat = [("Células de tiempo", "lo que vives junto\nse une aunque no se parezca", CIAN, "episodio"),
           ("Prefrontal (esquemas)", "encaja lo nuevo en\ncategorías que ya tienes", VERDE, "etiquetas (dims)"),
           ("Homeostasis", "quien se dispara con\ntodo pierde fuerza", NARANJA, "hub (resta)")]
    x_ca1 = xs[4] + w / 2
    for i, (t, d, c, n) in enumerate(lat):
        x = 6.3 + i * 3.25
        _caja(ax, x, 6.95, 3.0, 1.3, PANEL, c, lw=1.6)
        ax.text(x + 1.5, 7.98, t, ha="center", color=c, weight="bold", fontsize=10.5)
        ax.text(x + 1.5, 7.52, d, ha="center", va="center", fontsize=8.4)
        ax.text(x + 1.5, 7.1, f"→ {n}", ha="center", va="center", fontsize=9, color=c, weight="bold")
        _flecha(ax, (x + 1.5, 6.93), (x_ca1 - 0.6 + i * 0.6, y + h + 0.02), c, lw=1.6)
    # nacer calibrado
    _caja(ax, 0.3, 0.4, 7.5, 2.0, PANEL, ORO, lw=1.6)
    ax.text(4.05, 2.0, "Nacer con circuitos listos", ha="center", color=ORO, weight="bold", fontsize=11.5)
    ax.text(4.05, 1.2, "Los pesos vienen calibrados con 7 memorias de fábrica\n(inglés, español, portugués, "
            "código y chat).\nEn tu memoria no aprende nada: llega lista.", ha="center", va="center",
            fontsize=9.6)
    _caja(ax, 8.2, 0.4, 7.5, 2.0, PANEL, CIAN, lw=1.6)
    ax.text(11.95, 2.0, "Neuromodulación por contexto", ha="center", color=CIAN, weight="bold", fontsize=11.5)
    ax.text(11.95, 1.2, "Cada memoria mide sola si en ella el reloj y las etiquetas\ndicen lo mismo que "
            "el texto. Si no, esa aguja se apaga.\nNunca confía a ciegas en el reloj.", ha="center",
            va="center", fontsize=9.6)
    _guardar(fig, "02_hipocampo.png")


# =====================================================================================
# 3. Un par real, paso a paso
# =====================================================================================
def fig_un_par():
    ej = FD["par_ejemplo"]
    ag = ej["agujas"]
    fig = plt.figure(figsize=(17, 6.8))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.25, 1.1, 1.0], wspace=0.35)
    fig.suptitle("Un par real de tu memoria, paso a paso", fontsize=17, weight="bold", y=1.04)
    fig.text(0.5, 0.965, "leccion_discrepancia_busquedas_vocabulario…  ↔  evaluacion_ideas_evolucion_20260805…"
             "   (un enlace que pusiste tú a mano)", ha="center", color=TENUE, fontsize=11)
    # (a) agujas
    a1 = fig.add_subplot(gs[0])
    nombres = na.AGUJAS[::-1]
    vals = [ag[n] for n in nombres]
    cols = [REGION[n][1] for n in nombres]
    a1.barh(nombres, vals, color=cols, height=0.65)
    for i, v in enumerate(vals):
        a1.text(v + 0.01, i, f"{v:.2f}", va="center", fontsize=9)
    a1.set_xlim(0, 1)
    a1.set_title("① Lo que mide cada aguja (0 a 1)", loc="left", fontsize=12, color=ORO)
    a1.set_xlabel("valor")
    a1.text(0.98, 0.02, "casi no comparten palabras…\npero se guardaron cerca en el tiempo",
            transform=a1.transAxes, ha="right", va="bottom", fontsize=9.5, color=CIAN,
            bbox=dict(fc=PANEL, ec=CIAN, boxstyle="round,pad=0.4"))
    # (b) cascada
    a2 = fig.add_subplot(gs[1])
    partes = [("sesgo", na.PISO["sesgo"], TENUE)] + [
        (n, na.PISO[n] * ag[n], REGION[n][1]) for n in na.AGUJAS if na.PISO.get(n, 0) > 0]
    acc = 0.0
    for i, (n, v, c) in enumerate(partes):
        a2.bar(i, abs(v), bottom=min(acc, acc + v), color=c, width=0.65)
        etiqueta = f"{v:+.2f}" if n == "sesgo" else f"{na.PISO[n]:g}×{ag[n]:.2f}\n= {v:+.2f}"
        a2.text(i, max(acc, acc + v) + 0.06, etiqueta, ha="center", va="bottom", fontsize=8)
        if i < len(partes) - 1:
            a2.plot([i + 0.33, i + 0.67], [acc + v, acc + v], color=TENUE, lw=0.8)
        acc += v
    a2.bar(len(partes), acc, color=AZUL, width=0.65)
    a2.text(len(partes), acc / 2, f"z\n=\n{acc:.2f}", ha="center", va="center", fontsize=10.5, weight="bold")
    a2.axhline(0, color=LINEA, lw=1)
    a2.set_xticks(range(len(partes) + 1))
    a2.set_xticklabels([p[0] for p in partes] + ["total"], rotation=30, ha="right")
    a2.set_ylim(-1.3, 2.3)
    a2.set_title("② El piso suma: peso × aguja", loc="left", fontsize=12, color=ORO)
    # (c) sigmoide
    a3 = fig.add_subplot(gs[2])
    z = np.linspace(-5, 5, 300)
    a3.plot(z, 1 / (1 + np.exp(-z)), color=AZUL, lw=2.6)
    a3.axhspan(na.UMBRAL_CONECTAR, 1, color=VERDE, alpha=0.12)
    a3.axhspan(na.UMBRAL_DEBIL, na.UMBRAL_CONECTAR, color=ORO, alpha=0.10)
    a3.axhspan(0, na.UMBRAL_DEBIL, color=ROJO, alpha=0.08)
    a3.text(-4.8, 0.9, "conectar", color=VERDE, fontsize=9.5)
    a3.text(-4.8, 0.62, "débil", color=ORO, fontsize=9.5)
    a3.text(-4.8, 0.25, "no", color=ROJO, fontsize=9.5)
    a3.plot([acc], [ej["fuerza"]], "o", ms=13, color=VERDE, mec="white", mew=2, zorder=5)
    a3.annotate(f"fuerza {ej['fuerza']:.2f}", (acc, ej["fuerza"]), (0.2, 0.5), fontsize=11, weight="bold",
                arrowprops=dict(arrowstyle="->", color=TINTA))
    a3.set_ylim(0, 1)
    a3.set_xlabel("z")
    a3.set_title("③ Se convierte en fuerza", loc="left", fontsize=12, color=ORO)
    a3.text(0.5, -0.2, "Entre los 129 socios de ese recuerdo queda 3º → se queda (top 10).\n"
            "En la v1, sin la aguja de tiempo, quedaba 68º.", transform=a3.transAxes, ha="center",
            fontsize=10, color=VERDE)
    _guardar(fig, "03_un_par_paso_a_paso.png")


# =====================================================================================
# 4. Banco: qué separa cada aguja en cada memoria
# =====================================================================================
def fig_banco():
    fig, ax = plt.subplots(figsize=(13, 8.2))
    M = np.full((len(na.AGUJAS), len(MEMORIAS)), np.nan)
    for j, m in enumerate(MEMORIAS):
        b = BANCO[m]
        for i, a in enumerate(na.AGUJAS):
            sin_senal = (a == "episodio" and b["fiab_episodio"] is None) or \
                        (a == "etiquetas" and b["fiab_etiquetas"] is None)
            if not sin_senal:
                M[i, j] = b["auc_por_aguja"][a]
    cmap = matplotlib.colormaps["RdYlGn"].copy()
    cmap.set_bad(PANEL)
    im = ax.imshow(M, cmap=cmap, vmin=0.25, vmax=1.0, aspect="auto")
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            v = M[i, j]
            ax.text(j, i, "—" if np.isnan(v) else f"{v:.2f}", ha="center", va="center", fontsize=10,
                    color=TENUE if np.isnan(v) else "#0b1426", weight="bold")
    ax.set_xticks(range(len(MEMORIAS)))
    ax.set_xticklabels([MEM_TXT[m] for m in MEMORIAS])
    ax.set_yticks(range(len(na.AGUJAS)))
    ax.set_yticklabels([f"{a}  ×{na.PISO.get(a, 0):g}" for a in na.AGUJAS])
    for t, a in zip(ax.get_yticklabels(), na.AGUJAS):
        t.set_color(REGION[a][1])
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    cb = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cb.set_label("AUC: 0.5 = azar · 1 = separa perfecto · < 0.5 = señal al revés (resta)")
    ax.set_title("El banco de calibración: qué tan bien separa cada aguja «sí» de «no», en cada memoria\n"
                 "(×N = su peso en el piso · — = esa memoria no tiene esa señal)", fontsize=13.5, pad=14)
    fig.text(0.45, -0.01, "En el chat el texto casi no sirve (≈.63) y el momento lo es todo (.99). "
            "Ninguna aguja gana sola en todas: por eso se suman.", ha="center", fontsize=10.5, color=TENUE)
    _guardar(fig, "04_banco_agujas.png")


# =====================================================================================
# 5. Huella: qué mira la neurona en tu memoria
# =====================================================================================
def fig_huella():
    med = FD["medianas_agujas"]
    orden = sorted(na.AGUJAS, key=lambda a: med[a]["humano_si"] - med[a]["gemini_no"])
    fig, ax = plt.subplots(figsize=(12, 7.5))
    for i, a in enumerate(orden):
        h, g = med[a]["humano_si"], med[a]["gemini_no"]
        ax.plot([g, h], [i, i], color=REGION[a][1], lw=3, alpha=0.6)
        ax.plot(g, i, "o", ms=11, color=ROJO, mec="white", mew=1.2, zorder=4)
        ax.plot(h, i, "o", ms=11, color=VERDE, mec="white", mew=1.2, zorder=4)
    ax.set_yticks(range(len(orden)))
    ax.set_yticklabels([f"{a} — {DICE[a]}" for a in orden])
    for t, a in zip(ax.get_yticklabels(), orden):
        t.set_color(REGION[a][1])
    ax.set_xlim(-0.02, 1)
    ax.set_xlabel("valor típico de la aguja (mediana)")
    ax.plot([], [], "o", color=VERDE, ms=10, label=f"enlaces que pusiste tú ({DC['jueces']['n_humano_si']})")
    ax.plot([], [], "o", color=ROJO, ms=10, label=f"lo que Gemini sacó a cuarentena ({DC['jueces']['n_gemini_no']:,})")
    ax.legend(loc="lower right", frameon=False, fontsize=10.5)
    ax.set_title("La huella en tu memoria: dónde se separan lo humano y lo que Gemini descartó\n"
                 "(cuanto más larga la barra, más ayuda esa aguja a distinguirlos)", fontsize=13.5)
    ax.grid(axis="x", color=LINEA, lw=0.6)
    _guardar(fig, "05_huella_en_tu_memoria.png")


# =====================================================================================
# 6. Auto-regulación (las llaves)
# =====================================================================================
def fig_auto():
    fig, axs = plt.subplots(1, 2, figsize=(15, 5.8), gridspec_kw=dict(wspace=0.45))
    fig.suptitle("Auto-regulación: cada memoria decide sola si confía en el reloj y en las etiquetas",
                 fontsize=15.5, weight="bold", y=1.03)
    for ax, (clave, titulo, col, den) in zip(axs, [
            ("fiab_episodio", "Llave del TIEMPO (aguja episodio)", CIAN, DC["fiab_episodio"]),
            ("fiab_etiquetas", "Llave de las ETIQUETAS (dims)", VERDE, DC["fiab_etiquetas"])]):
        items = [(MEM_TXT[m].replace("\n", " "), BANCO[m][clave]) for m in MEMORIAS if BANCO[m][clave] is not None]
        items.append(("tu memoria (BioRAG)", den))
        nombres = [i[0] for i in items]
        vals = [i[1] for i in items]
        cols = [col] * (len(items) - 1) + [ORO]
        ax.barh(nombres, vals, color=cols, height=0.55)
        for i, v in enumerate(vals):
            ax.text(v + 0.015, i, f"{v:.2f}", va="center", fontsize=10.5, weight="bold")
        ax.set_xlim(0, 1)
        ax.invert_yaxis()
        ax.set_title(titulo, color=col, fontsize=12.5, loc="left")
        ax.set_xlabel("fiabilidad (0 = llave cerrada · 1 = abierta)")
    fig.text(0.5, -0.08, "Cómo mide: compara qué tan parecidos son, por texto, los recuerdos que el reloj "
             "(o las etiquetas) junta, contra pares al azar.\nSin mirar ninguna verdad. Si no hay relación, "
             "la llave se cierra: con un reloj al azar da ≈ 0 (hay una prueba automática que lo verifica).",
             ha="center", fontsize=10.2, color=TENUE)
    _guardar(fig, "06_auto_regulacion.png")


# =====================================================================================
# 7. Nunca vista
# =====================================================================================
def fig_nunca_vista():
    fig, ax = plt.subplots(figsize=(14, 6.3))
    x = np.arange(len(MEMORIAS))
    jac = [NUNCA[m]["regla_jaccard_0.4"]["auc"] for m in MEMORIAS]
    pis = [NUNCA[m]["piso_a_mano"]["auc"] for m in MEMORIAS]
    ax.bar(x - 0.2, jac, 0.38, color="#55657f", label="regla simple de palabras compartidas (Jaccard)")
    ax.bar(x + 0.2, pis, 0.38, color=ORO, label="la neurona (piso calibrado SIN ver esa memoria)")
    for i in range(len(MEMORIAS)):
        ax.text(x[i] - 0.2, jac[i] + 0.01, f"{jac[i]:.2f}", ha="center", fontsize=9, color=TENUE)
        ax.text(x[i] + 0.2, pis[i] + 0.01, f"{pis[i]:.2f}", ha="center", fontsize=10, weight="bold")
    ax.axhline(0.5, color=ROJO, ls="--", lw=1)
    ax.text(6.55, 0.51, "azar", color=ROJO, fontsize=9, ha="right")
    ax.set_xticks(x)
    ax.set_xticklabels([MEM_TXT[m] for m in MEMORIAS])
    ax.set_ylim(0.45, 1.05)
    ax.set_ylabel("AUC (qué tan bien ordena «sí» por encima de «no»)")
    ax.legend(loc="upper left", frameon=False, ncol=2, fontsize=10)
    ax.set_title("Examen «nunca vista»: se calibra con 6 memorias y se examina en la 7ª, las 7 veces\n"
                 "en el chat las palabras casi no sirven (.63): la llave del tiempo salva el examen (.91)",
                 fontsize=13.5, pad=12)
    _guardar(fig, "07_examen_nunca_vista.png")


# =====================================================================================
# 8. Tu memoria: tres jueces
# =====================================================================================
def fig_jueces():
    fig = plt.figure(figsize=(17, 6.3))
    gs = fig.add_gridspec(1, 3, width_ratios=[0.9, 1.15, 1.15], wspace=0.6)
    fig.suptitle("El examen real: tu memoria (851 recuerdos, español técnico, nunca vista)",
                 fontsize=16, weight="bold", y=1.04)
    a1 = fig.add_subplot(gs[0])
    et = ["peso del\nmotor hoy", "neurona\nv1", "v2\nsolo texto", "v2\ncompleta"]
    vs = [DC["auc_manual_vs_resto"]["peso_del_motor_hoy"], 0.859, DT["auc_manual_vs_resto"]["neurona"],
          DC["auc_manual_vs_resto"]["neurona"]]
    cs = [ROJO, "#55657f", "#c9a640", ORO]
    a1.bar(et, vs, color=cs, width=0.62)
    for i, v in enumerate(vs):
        a1.text(i, v + 0.015, f"{v:.3f}", ha="center", fontsize=10.5, weight="bold")
    a1.axhline(0.5, color=TENUE, ls="--", lw=1)
    a1.text(3.4, 0.51, "azar", ha="right", fontsize=8.5, color=TENUE)
    a1.set_ylim(0, 1)
    a1.set_title("¿Pone tus enlaces arriba?\n(AUC: humanos vs el resto)", fontsize=11.5, color=ORO, loc="left")
    a1.text(0, vs[0] / 2, "los pone\nabajo", ha="center", fontsize=9, color="white")

    a2 = fig.add_subplot(gs[1])
    caj = np.array(FD["cajas"])
    cen = (caj[:-1] + caj[1:]) / 2
    for k, c, t in [("gemini_no", ROJO, "Gemini dijo NO"), ("gemini_si", ROSA, "Gemini dijo sí"),
                    ("humano_si", VERDE, "tú dijiste sí")]:
        h = np.array(FD["hist_fuerza_por_juez"][k], float)
        h = h / h.sum()
        a2.fill_between(cen, h, step="mid", color=c, alpha=0.25)
        a2.step(cen, h, where="mid", color=c, lw=2, label=f"{t} — mediana {DC['jueces']['fuerza_mediana'][k]:.2f}")
    a2.set_xlim(0, 1)
    a2.set_ylim(0, 0.25)
    a2.set_xlabel("fuerza que da la neurona")
    a2.set_ylabel("proporción")
    a2.legend(frameon=False, fontsize=9.5, loc="upper right")
    a2.set_title(f"Tres jueces · tú vs Gemini-NO: AUC "
                 f"{DC['jueces']['auc_humano_si_vs_gemini_no']['neurona']:.2f}", fontsize=11.5, color=ORO,
                 loc="left")

    a3 = fig.add_subplot(gs[2])
    pt = FD["fuerza_por_tipo"]
    tipos = sorted(pt, key=lambda t: pt[t]["q"][2])
    for i, t in enumerate(tipos):
        q = pt[t]["q"]
        c = TIPO_COLOR.get(t, TENUE)
        a3.plot([q[0], q[4]], [i, i], color=c, lw=1.5)
        a3.add_patch(plt.Rectangle((q[1], i - 0.28), q[3] - q[1], 0.56, fc=c, alpha=0.55, ec=c))
        a3.plot([q[2], q[2]], [i - 0.28, i + 0.28], color="white", lw=2.2)
    a3.set_yticks(range(len(tipos)))
    a3.set_yticklabels([f"{TIPO_TXT.get(t, t)} ({pt[t]['n']:,})" for t in tipos])
    a3.set_xlim(0, 1)
    a3.set_xlabel("fuerza (caja = mitad central · línea blanca = mediana)")
    a3.set_title("Fuerza por tipo de conexión que existe hoy", fontsize=11.5, color=ORO, loc="left")
    _guardar(fig, "08_tu_memoria_tres_jueces.png")


# =====================================================================================
# 9. Competencia (el recuerdo de tu captura + curva K)
# =====================================================================================
def fig_competencia():
    fig = plt.figure(figsize=(17, 8))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.15, 1], wspace=0.25)
    fig.suptitle("Competencia: cada recuerdo se queda con sus socios más fuertes", fontsize=16,
                 weight="bold", y=1.0)
    ax = fig.add_subplot(gs[0])
    ax.set_xlim(-1.35, 1.35)
    ax.set_ylim(-1.3, 1.3)
    ax.set_aspect("equal")
    ax.axis("off")
    filas = FD["caso_neuro_visor"]
    n = len(filas)
    ax.add_patch(Circle((0, 0), 0.47, fc=VERDE, alpha=0.07, ec=VERDE, ls="--", lw=1.2))
    for i, q in enumerate(filas):
        ang = 2 * math.pi * i / n + math.pi / 2
        r = 0.18 + 1.05 * (1 - q["fuerza"])
        x, y = r * math.cos(ang), r * math.sin(ang)
        c = TIPO_COLOR.get(q["tipo"], TENUE)
        if q["k10"]:
            ax.plot([0, x], [0, y], color=c, lw=1.0, alpha=0.55, zorder=1)
        if q["tipo"] == "manual":
            ax.plot(x, y, "*", ms=21, color=VERDE, mec="white", mew=1.2, zorder=5)
            ax.text(x + 0.09, y + (0.09 if i % 2 else -0.09), f"{i + 1}º", fontsize=11, weight="bold",
                    color=VERDE, zorder=6, va="center",
                    bbox=dict(fc=FONDO, ec="none", alpha=0.8, pad=0.5))
        else:
            ax.plot(x, y, "o", ms=6.5 if q["k10"] else 4.5, color=c, alpha=1 if q["k10"] else 0.35, zorder=3)
    ax.add_patch(Circle((0, 0), 0.13, color=AZUL, zorder=7))
    ax.text(0, -1.27, "el recuerdo de tu captura del Neuro-Visor: 129 conexiones · "
            f"se quedan {sum(q['k10'] for q in filas)} (líneas)\nmás cerca del centro = más fuerte · "
            "★ = enlaces que pusiste tú\n(algunas lejanas se quedan porque están en el top 10 del OTRO recuerdo)", ha="center", fontsize=10, color=TENUE)
    vis = [t for t in TIPO_COLOR if any(q["tipo"] == t for q in filas)]
    for k, t in enumerate(vis):
        ax.plot(-1.33, 1.25 - k * 0.1, "o", color=TIPO_COLOR[t], ms=7)
        ax.text(-1.27, 1.25 - k * 0.1, TIPO_TXT[t], va="center", fontsize=9)

    a2 = fig.add_subplot(gs[1])
    ks = [5, 10, 20]
    neu = [DC["competencia"][f"k{k}"]["solo_competencia"]["manual_orden_neurona_pct"] for k in ks]
    hoy = [DC["competencia"][f"k{k}"]["solo_competencia"]["manual_orden_peso_hoy_pct"] for k in ks]
    tot = [DC["competencia"][f"k{k}"]["se_conserva_pct"] for k in ks]
    a2.plot(ks, neu, "-o", color=VERDE, lw=3, ms=10, label="tus enlaces que conserva la NEURONA")
    a2.plot(ks, hoy, "-o", color=ROJO, lw=3, ms=10, label="tus enlaces que conserva el PESO DE HOY")
    a2.plot(ks, tot, "--", color=TENUE, lw=1.5, label="todas las conexiones que se quedan")
    for k, a, b in zip(ks, neu, hoy):
        a2.text(k, a + 2.5, f"{a:.0f} %", ha="center", color=VERDE, weight="bold", fontsize=11)
        a2.text(k, b - 6, f"{b:.0f} %", ha="center", color=ROJO, weight="bold", fontsize=11)
    a2.set_xticks(ks)
    a2.set_xticklabels([f"K = {k}" for k in ks])
    a2.set_ylim(0, 105)
    a2.set_ylabel("%")
    a2.legend(frameon=False, loc="lower right", fontsize=10)
    a2.set_title("Mismo cupo, distinto juez: ¿cuántos de tus enlaces sobreviven?", fontsize=12, color=ORO,
                 loc="left")
    a2.grid(axis="y", color=LINEA, lw=0.6)
    _guardar(fig, "09_competencia.png")


# =====================================================================================
# 10. Puestos v1 → v2 en tu captura
# =====================================================================================
def fig_puestos():
    v1 = {"que_es_nodo_biorag_definicion": 2,
          "evaluacion_ideas_evolucion_20260805_interferencia_agujeros_permutacion": 68,
          "athena_leccion_grep_patron_bug_antes_de_cerrar_fix": 63,
          "leccion_bbusqueda_bilingue_nodos_tecnicos": 11}
    v2 = {q["con"]: q["puesto"] for q in DC["caso_neuro_visor"]["manual"]}
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.axhspan(0.5, 10.5, color=VERDE, alpha=0.1)
    ax.text(0.5, 8.6, "zona «se queda» (top 10)", ha="center", color=VERDE, fontsize=10)
    for nm, r1 in v1.items():
        r2 = v2[nm]
        c = VERDE if r2 < r1 else (ROJO if r2 > r1 else TINTA)
        ax.plot([0, 1], [r1, r2], "-o", color=c, lw=2.6, ms=10)
        ax.text(-0.04, r1, f"{r1}º", ha="right", va="center", fontsize=11, color=TENUE)
        yl = r2 + {2: -1.6, 3: 1.6}.get(r2, 0)
        ax.text(1.04, yl, f"{r2}º  {nm[:46]}{'…' if len(nm) > 46 else ''}", ha="left", va="center",
                fontsize=10.5, color=c, weight="bold")
    ax.set_xlim(-0.3, 2.6)
    ax.set_ylim(75, -2)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["v1\n(sin tiempo ni dims)", "v2\n(con tiempo y dims)"], fontsize=11)
    ax.set_ylabel("puesto entre las 129 conexiones (1º = la más fuerte)")
    ax.spines["bottom"].set_visible(False)
    ax.tick_params(axis="x", length=0)
    ax.set_title("Tu captura del Neuro-Visor: los 4 enlaces que pusiste tú\n"
                 "uno subió de 68º a 3º · otro bajó de 11º a 56º (lo digo claro)", fontsize=13.5)
    _guardar(fig, "10_neuro_visor_puestos.png")


# =====================================================================================
# 11. La balanza: por qué la parte que aprende queda apagada
# =====================================================================================
def fig_balanza():
    fig = plt.figure(figsize=(17, 6.8))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.2, 1], wspace=0.25)
    fig.suptitle("Por qué la parte que aprende queda apagada: lo que ayuda a una memoria, daña a otra",
                 fontsize=15.5, weight="bold", y=1.03)
    a1 = fig.add_subplot(gs[0])
    x = np.arange(len(MEMORIAS))
    A = [100 * VAR["A_cada_memoria_sola"][m] for m in MEMORIAS]
    B = [100 * VAR["B_todas_juntas"][-1][m] for m in MEMORIAS]
    C = [100 * VAR["C_todas_juntas_cuidando"][-1][m] for m in MEMORIAS]
    for dx, v, c, t in [(-0.27, A, VERDE, "A · entrenando con esa memoria SOLA"),
                        (0, B, AZUL, "B · todas juntas"),
                        (0.27, C, VIOLETA, "C · todas juntas, cuidando a la peor")]:
        a1.bar(x + dx, v, 0.26, color=c, label=t)
    for i in range(len(MEMORIAS)):
        for dx, v in ((0, B[i]), (0.27, C[i])):
            if v < -0.05:
                a1.text(x[i] + dx, v - 0.25, f"{v:+.1f}", ha="center", va="top", fontsize=8.5, color=ROJO,
                        weight="bold")
    a1.axhline(0, color=TINTA, lw=1.2)
    a1.text(4.62, -0.12, "↑ el piso: nunca se baja de aquí", fontsize=9, color=TENUE, va="top")
    a1.set_ylim(-1.6, 5.2)
    a1.set_xticks(x)
    a1.set_xticklabels([MEM_TXT[m] for m in MEMORIAS])
    a1.set_ylabel("puntos ganados (×100 de AUC por recuerdo, en la guardia)")
    a1.legend(frameon=False, fontsize=10, loc="upper left")
    a1.set_title("Cuánto se puede aprender encima del piso", fontsize=12, color=ORO, loc="left")

    a2 = fig.add_subplot(gs[1])
    pasos = [r["paso"] for r in VAR["B_todas_juntas"]]
    cols = dict(zip(MEMORIAS, [ORO, ROSA, "#9fb3d1", AZUL, CIAN, VERDE, NARANJA]))
    for m in MEMORIAS:
        a2.plot(pasos, [100 * r[m] for r in VAR["B_todas_juntas"]], color=cols[m], lw=1.8,
                label=MEM_TXT[m].replace("\n", " "))
    a2.plot(pasos, [100 * r["peor"] for r in VAR["B_todas_juntas"]], color=ROJO, lw=3.5, ls="--",
            label="la peor en cada momento")
    a2.axhline(0, color=TINTA, lw=1.2)
    a2.fill_between(pasos, 0, -3, color=ROJO, alpha=0.07)
    a2.text(pasos[-1], -2.6, "zona prohibida: bajo el piso", ha="right", color=ROJO, fontsize=9.5)
    a2.set_ylim(-3, 2)
    a2.set_xlabel("pasos de entrenamiento (B · todas juntas)")
    a2.set_ylabel("puntos vs el piso")
    a2.legend(frameon=False, fontsize=8.5, ncol=2, loc="upper left")
    a2.set_title("Mientras entrena: la peor nunca sale de la zona roja", fontsize=12, color=ORO, loc="left")
    fig.text(0.5, -0.07, "Regla «nunca bajo el piso»: solo se enciende si TODAS las memorias quedan igual o "
             "mejor. Nunca pasa → escala 0.\nY aun cuando pasa en las memorias de estudio, puede dañar una "
             "nueva (diccionario .902 → .883 en el examen «nunca vista»).", ha="center", fontsize=10.5,
             color=TENUE)
    _guardar(fig, "11_balanza_aprender.png")


# =====================================================================================
# 12. Lo que todavía le falta
# =====================================================================================
def fig_falta():
    fig = plt.figure(figsize=(15, 6.5))
    gs = fig.add_gridspec(1, 2, width_ratios=[1, 1.35], wspace=0.15)
    fig.suptitle("Lo que todavía le falta (medido, no supuesto)", fontsize=16, weight="bold", y=1.02)
    a1 = fig.add_subplot(gs[0])
    p = DC["manual_que_la_neurona_propondria_sola_pct"]
    a1.pie([p, 100 - p], colors=[VERDE, "#33435f"], startangle=90, counterclock=False,
           wedgeprops=dict(width=0.32, ec=FONDO, lw=3))
    a1.text(0, 0.08, f"{p:.0f} %", ha="center", va="center", fontsize=30, weight="bold", color=VERDE)
    a1.text(0, -0.22, "de tus enlaces\nla neurona los\npropondría sola", ha="center", va="center", fontsize=10)
    a1.set_title(f"El {100 - p:.0f} % ni siquiera llega a ser candidato", fontsize=12, color=ORO)
    a2 = fig.add_subplot(gs[1])
    a2.axis("off")
    a2.set_xlim(0, 10)
    a2.set_ylim(0, 8)
    filas = [("✓", VERDE, "Tiempo (episodio)", "con llave de fiabilidad · subió un enlace de 68º a 3º"),
             ("✓", VERDE, "Etiquetas (dims)", "con llave de fiabilidad"),
             ("✓", VERDE, "7 memorias, 4 lenguas", "inglés, español, portugués, código, chat"),
             ("✓", VERDE, "31 pruebas automáticas", "techo, nunca-bajo-el-piso, simetría, velocidad…"),
             ("✗", ROJO, "Candidatos que no dependen del texto", "lo que el agente tenía «en mente» (cambio del motor)"),
             ("✗", ROJO, "Predicados  («A causa B»)", "la tabla existe; la neurona aún no la usa"),
             ("✗", ROJO, "Contradicción", "dos recuerdos opuestos se parecen mucho en texto"),
             ("✗", ROJO, "Utilidad", "si una conexión ayudó a encontrar algo (sin trabajo para el agente)"),
             ("✗", ORO, "«Modo motor»", "solo K vecinos por recuerdo para memorias de 50.000 (ingeniería)")]
    for i, (s, c, t, d) in enumerate(filas):
        y = 7.6 - i * 0.85
        a2.text(0.2, y, s, fontsize=18, color=c, weight="bold", va="center")
        a2.text(0.9, y + 0.12, t, fontsize=11.5, weight="bold", va="center")
        a2.text(0.9, y - 0.25, d, fontsize=9.3, color=TENUE, va="center")
    _guardar(fig, "12_lo_que_falta.png")


if __name__ == "__main__":
    for f in (fig_anatomia, fig_hipocampo, fig_un_par, fig_banco, fig_huella, fig_auto, fig_nunca_vista,
              fig_jueces, fig_competencia, fig_puestos, fig_balanza, fig_falta):
        f()
