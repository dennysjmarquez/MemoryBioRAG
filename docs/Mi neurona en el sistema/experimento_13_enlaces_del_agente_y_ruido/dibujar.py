"""Dibuja las figuras de cierre de la neurona asociativa (v35) en figuras/.

Mismo estilo que las figuras de la primera neurona y del experimento 11.
Todo sale del código y de los resultados versionados (no hace falta ninguna DB):
  - fórmula y constantes:   core/neurona_asociativa.py (PISO, VERSION, MUESTRA_MAX…)
  - números:                resultados/escenarios.json y resultados/mediciones.json
                            ../experimento_11_neurona_asociativa/resultados/*.json

Uso:  python dibujar.py
"""
import json
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch  # noqa: E402
import numpy as np  # noqa: E402

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.abspath(os.path.join(AQUI, "..", "..", ".."))
sys.path.insert(0, RAIZ)
from core import neurona_asociativa as na  # noqa: E402

RES = os.path.join(AQUI, "resultados")
E11 = os.path.join(AQUI, "..", "experimento_11_neurona_asociativa", "resultados")
FIG = os.path.join(AQUI, "figuras")
os.makedirs(FIG, exist_ok=True)


def _j(carpeta, nombre):
    with open(os.path.join(carpeta, nombre), encoding="utf-8") as fh:
        return json.load(fh)


ESC = _j(RES, "escenarios.json")
MED = _j(RES, "mediciones.json")
NUNCA = _j(E11, "examen_nunca_vista.json")
HOJA = _j(E11, "examen_hoja_dennys.json")

FONDO, PANEL, TINTA, TENUE, LINEA = "#0b1426", "#111f3a", "#e8eef8", "#8fa3c4", "#2a3b5c"
ORO, CIAN, VIOLETA, VERDE, ROJO, NARANJA, ROSA, AZUL = (
    "#f2c14e", "#4fd1e8", "#b48cff", "#5ee08f", "#ff6b6b", "#ff9f43", "#ff7eb6", "#5b8cff")
plt.rcParams.update({
    "figure.facecolor": FONDO, "axes.facecolor": FONDO, "savefig.facecolor": FONDO,
    "text.color": TINTA, "axes.labelcolor": TINTA, "xtick.color": TENUE, "ytick.color": TENUE,
    "axes.edgecolor": LINEA, "font.family": "DejaVu Sans", "font.size": 10,
    "axes.spines.top": False, "axes.spines.right": False,
})


def _guardar(fig, nombre):
    ruta = os.path.join(FIG, nombre)
    fig.savefig(ruta, dpi=110, bbox_inches="tight")
    plt.close(fig)
    print("  ✓", os.path.relpath(ruta, AQUI))


def _caja(ax, x, y, w, h, color=PANEL, borde=LINEA, lw=1.6, ls="-", r=0.25, z=2):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0.02,rounding_size={r}",
                                fc=color, ec=borde, lw=lw, ls=ls, zorder=z))


def _flecha(ax, a, b, color=TENUE, lw=1.8, ls="-", rad=0.0, cs=None):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-|>", mutation_scale=14, color=color, lw=lw,
                                 ls=ls, connectionstyle=cs or f"arc3,rad={rad}", zorder=3))


def _lienzo(w, h, xl, yl):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(*xl)
    ax.set_ylim(*yl)
    ax.axis("off")
    return fig, ax


# ───────────────────────── 1. la neurona tal como vive en el motor ─────────────────────────
def fig_motor():
    fig, ax = _lienzo(16, 8.6, (0, 16), (0, 8.6))
    ax.text(8, 8.25, "LA NEURONA ASOCIATIVA DE BIORAG (v35) — cómo decide",
            ha="center", fontsize=17, weight="bold")
    ax.text(8, 7.8, "¿Estos dos recuerdos tienen que ver de verdad?  Nace calibrada de fábrica, "
            "es cerrada (no aprende de tu memoria) y cada decisión es de tiempo constante.",
            ha="center", color=TENUE, fontsize=10.5)

    for y, txt in ((5.7, "recuerdo A"), (2.9, "recuerdo B")):
        _caja(ax, 0.2, y, 2.0, 0.85, color="#16294d", borde=AZUL)
        ax.text(1.2, y + 0.42, txt, ha="center", va="center", fontsize=11, weight="bold")
    ax.text(1.2, 4.7, "texto · momento · dims\nde la propia memoria,\nen cualquier idioma",
            ha="center", va="center", color=TENUE, fontsize=8.6)
    ax.plot([2.45, 2.6, 2.6, 2.45], [6.55, 6.55, 2.9, 2.9], color=LINEA, lw=1.5)
    _flecha(ax, (2.6, 4.72), (2.95, 4.72), color=LINEA, lw=1.5)

    agujas = [
        ("parecido", "¿usan las mismas palabras?", ORO, na.PISO["parecido"]),
        ("semantica", "¿significan lo mismo? (LSA 100 d)", ORO, na.PISO["semantica"]),
        ("rareza_max", "¿comparten una pista muy rara?", ROSA, na.PISO["rareza_max"]),
        ("episodio", "¿se guardaron cerca en el tiempo?", CIAN, na.PISO["episodio"]),
        ("etiquetas", "¿comparten etiquetas (dims)?", VERDE, na.PISO["etiquetas"]),
    ]
    cx, cy, rad = 10.0, 4.45, 0.95
    xd = 5.75
    for i, (nombre, dice, color, peso) in enumerate(agujas):
        y = 6.75 - i * 1.07
        ax.add_patch(Circle((xd, y), 0.17, color=color, zorder=4))
        ax.text(xd - 0.3, y + 0.1, nombre, ha="right", va="center", fontsize=11, weight="bold")
        ax.text(xd - 0.3, y - 0.24, dice, ha="right", va="center", color=TENUE, fontsize=8.3)
        ax.plot([xd + 0.17, cx - rad], [y, cy], color=color, lw=1.2 + 1.3 * peso, alpha=0.9, zorder=2)
        llave = " · llave" if nombre in ("episodio", "etiquetas") else ""
        xm = 7.25
        ym = y + (cy - y) * (xm - xd - 0.17) / (cx - rad - xd - 0.17)
        ax.text(xm, ym, f"×{peso:g}{llave}", ha="center", va="center", fontsize=8.5,
                color=color, weight="bold",
                bbox=dict(boxstyle="round,pad=0.25", fc=FONDO, ec=color, lw=1.2), zorder=5)

    ax.add_patch(Circle((cx, cy), rad, color=AZUL, zorder=4))
    ax.text(cx, cy + 0.2, "Σ", ha="center", va="center", fontsize=28, weight="bold", zorder=5)
    ax.text(cx, cy - 0.45, f"sesgo {na.PISO['sesgo']:g}", ha="center", fontsize=9, zorder=5)

    sub = ax.inset_axes([11.6, 3.6, 1.7, 1.6], transform=ax.transData)
    z = np.linspace(-5, 5, 200)
    sub.plot(z, 1 / (1 + np.exp(-z)), color=AZUL, lw=2.5)
    sub.axhline(0.6, color=VERDE, ls="--", lw=1)
    sub.set_facecolor(PANEL)
    sub.set_xticks([])
    sub.set_yticks([0, 0.6, 1])
    sub.tick_params(labelsize=7)
    ax.text(12.45, 5.45, "fuerza = 1 / (1 + e^−z)", ha="center", fontsize=9)
    ax.text(12.45, 3.2, "fuerza de 0 a 1", ha="center", color=TENUE, fontsize=9)
    _flecha(ax, (cx + rad, cy), (11.3, cy), color=AZUL, lw=2.2)

    corte = HOJA["corte_0_6"]
    _caja(ax, 13.9, 5.35, 1.95, 1.3, borde=VERDE)
    ax.text(14.87, 6.25, "≥ 0.6", ha="center", color=VERDE, fontsize=12, weight="bold")
    ax.text(14.87, 5.72, f"tu examen:\n{corte['arriba'][0]} «sí» de {corte['arriba'][1]}",
            ha="center", va="center", fontsize=8.5)
    _caja(ax, 13.9, 2.3, 1.95, 1.3, borde=ORO)
    ax.text(14.87, 3.2, "< 0.6", ha="center", color=ORO, fontsize=12, weight="bold")
    ax.text(14.87, 2.67, f"tu examen:\n{corte['abajo'][0]} «sí» de {corte['abajo'][1]}",
            ha="center", va="center", fontsize=8.5)
    _flecha(ax, (13.45, 4.8), (13.9, 5.6), color=VERDE)
    _flecha(ax, (13.45, 4.1), (13.9, 3.3), color=ORO)

    _caja(ax, 4.3, 0.25, 11.55, 1.15, borde=VIOLETA, ls="--")
    ax.text(10.07, 1.0, f"z = {na.PISO['sesgo']:g} + 2·parecido + 1·semantica + 1·rareza_max + "
            "4·episodio + 1·etiquetas", ha="center", fontsize=10.5, family="DejaVu Sans Mono")
    ax.text(10.07, 0.52, f"Cerrada (no aprende) · versión {na.VERSION} · solo numpy · estado con techo "
            f"({na.MUESTRA_MAX} recuerdos) · BIORAG_NEURONA_ASOCIATIVA=0 la apaga",
            ha="center", color=TENUE, fontsize=8.8)
    ax.text(0.2, 0.8, "Línea gruesa = más peso.\nLa «llave»: el tiempo y las dims\nvalen solo si en ESA memoria\n"
            "coinciden con el texto\n(se mide sola, sin verdad).", color=TENUE, fontsize=8.3, va="center")
    _guardar(fig, "01_neurona_del_motor.png")


# ───────────────────────── 2. el viaje: de la idea al cierre ─────────────────────────
def fig_viaje():
    fig, ax = _lienzo(14.5, 6.0, (0, 14.5), (0, 6.0))
    ax.text(7.25, 5.6, "EL VIAJE DE LA NEURONA ASOCIATIVA — de la idea al cierre (v35)",
            ha="center", fontsize=16, weight="bold")
    pasos = [
        ("Exp 10", "Diseño", "el molde, el mapa de\ndónde nacen sinapsis,\nla hormiguita estudiada", AZUL, "hecho"),
        ("Exp 11", "Construcción", "5 agujas, 7 memorias\nde fábrica, examen\n«nunca vista» .88–.997", ORO, "hecho"),
        ("Examen", "Dennys, 100 pares", "AUC .73 (.62–.83)\nfuerza ≥ .6: 31 «sí» de 42\nfuerza < .6: 16 de 44", VERDE, "hecho"),
        ("Exp 12", "Poner el peso", "QA idéntico: el\npeso no mueve la\nbúsqueda", NARANJA, "revertido"),
        ("Exp 13", "¿Cortar al nacer?", "baja el recall con\ncualquier umbral\n(0.40: 99.89 %)", ROJO, "descartado"),
        ("Cierre", "Neurona cerrada", "lista y examinada;\nsu lugar: decidir qué\nve el agente", VIOLETA, "próximo"),
    ]
    xs = np.linspace(1.3, 13.2, len(pasos))
    ax.plot([xs[0], xs[-1]], [3.6, 3.6], color=LINEA, lw=3, zorder=1)
    for x, (tag, titulo, txt, color, estado) in zip(xs, pasos):
        ax.add_patch(Circle((x, 3.6), 0.32, color=color, zorder=3))
        ax.text(x, 4.25, tag, ha="center", fontsize=11, weight="bold", color=color)
        ax.text(x, 4.7, titulo, ha="center", fontsize=10.5, weight="bold")
        _caja(ax, x - 1.05, 1.25, 2.1, 1.85, borde=color)
        ax.text(x, 2.2, txt, ha="center", va="center", fontsize=8.6)
        ax.text(x, 0.85, estado.upper(), ha="center", fontsize=8.5, weight="bold",
                color={"hecho": VERDE, "revertido": NARANJA, "descartado": ROJO, "próximo": VIOLETA}[estado])
    ax.text(7.25, 0.25, "Además en v35: los enlaces del agente son intocables y el MCP ya no sugiere qué "
            "vincular ni qué desvincular.", ha="center", color=TENUE, fontsize=9.5)
    _guardar(fig, "02_el_viaje.png")


# ───────────────────────── 3. el ruido y la búsqueda ─────────────────────────
ORDEN = ["hoy", "hormiguita_apagada", "neurona_040", "neurona_050", "neurona_060", "sin_automaticos"]
NOMBRE = {"hoy": "hoy", "hormiguita_apagada": "sin\nhormiguita",
          "neurona_040": "corta\n< 0.40", "neurona_050": "corta\n< 0.50",
          "neurona_060": "corta\n< 0.60", "sin_automaticos": "sin\nautomáticos"}


def fig_ruido():
    fig, axs = plt.subplots(1, 3, figsize=(16, 5.4), gridspec_kw={"width_ratios": [1.2, 1.2, 1]})
    fig.suptitle("¿EL «RUIDO» AYUDA A BUSCAR?  QA oficial (875 búsquedas) en copias del snapshot",
                 fontsize=15, weight="bold", y=1.02)
    x = np.arange(len(ORDEN))
    cols = [AZUL, VERDE, ORO, NARANJA, ROJO, "#6b7a99"]
    r5 = [ESC[k]["r5"] for k in ORDEN]
    ax = axs[0]
    ax.bar(x, r5, color=cols)
    ax.set_ylim(99.0, 100.15)
    ax.axhline(100, color=VERDE, ls="--", lw=1)
    for i, v in enumerate(r5):
        ax.text(i, v + 0.03, f"{v:.2f}%\n{ESC[ORDEN[i]]['fallos']} fallo{'' if ESC[ORDEN[i]]['fallos'] == 1 else 's'}", ha="center", fontsize=8.3)
    ax.set_xticks(x, [NOMBRE[k] for k in ORDEN], fontsize=8)
    ax.set_title("Encuentra lo correcto entre los 5 primeros (R@5)", fontsize=10.5)
    ax = axs[1]
    r1 = [ESC[k]["r1"] for k in ORDEN]
    ax.bar(x, r1, color=cols)
    ax.set_ylim(91.4, 92.15)
    for i, v in enumerate(r1):
        ax.text(i, v + 0.015, f"{v:.2f}%", ha="center", fontsize=8.5)
    ax.set_xticks(x, [NOMBRE[k] for k in ORDEN], fontsize=8)
    ax.set_title("Lo pone primero (R@1)", fontsize=10.5)
    ax = axs[2]
    si = [ESC[k]["examen"]["quedan_si"] for k in ORDEN[:-1]]
    no = [ESC[k]["examen"]["quedan_no"] for k in ORDEN[:-1]]
    xx = np.arange(len(si))
    ax.bar(xx, si, color=VERDE, label="buenos (tu examen)")
    ax.bar(xx, no, bottom=si, color=ROJO, alpha=0.85, label="malos (tu examen)")
    for i in xx:
        ax.text(i, si[i] + no[i] + 0.8, f"{si[i]} / {no[i]}", ha="center", fontsize=8.5)
    ax.set_xticks(xx, [NOMBRE[k] for k in ORDEN[:-1]], fontsize=8.5)
    ax.set_title("Enlaces de tu examen que quedan", fontsize=10.5)
    ax.legend(fontsize=8, frameon=False, loc="upper right")
    fig.text(0.5, -0.11, "«corta» = la neurona no deja nacer los enlaces automáticos con fuerza menor.\nLectura: el ruido rescata 5 búsquedas; cortar al nacer baja el recall con cualquier "
             "umbral; apagar la hormiguita no baja nada y sube un poco el primer puesto.",
             ha="center", color=TENUE, fontsize=10)
    _guardar(fig, "03_el_ruido_y_la_busqueda.png")


# ───────────────────────── 4. lo que ve el agente ─────────────────────────
def fig_agente():
    c2 = MED["canal2_con_filtro_neurona"]
    claves = [("None", "hoy"), ("0.5", "la neurona filtra\n≥ 0.50"), ("0.6", "la neurona filtra\n≥ 0.60")]
    fig, axs = plt.subplots(1, 2, figsize=(13.5, 5.0), gridspec_kw={"width_ratios": [1, 1.35], "wspace": 0.45})
    fig.suptitle("LO QUE VE EL AGENTE (asociaciones junto a cada resultado — no toca el ranking)",
                 fontsize=14.5, weight="bold", y=1.02)
    ax = axs[0]
    x = np.arange(len(claves))
    si = [c2[k]["examen_visibles"].get("si", 0) for k, _ in claves]
    no = [c2[k]["examen_visibles"].get("no", 0) for k, _ in claves]
    ax.bar(x - 0.18, si, 0.36, color=VERDE, label="buenos")
    ax.bar(x + 0.18, no, 0.36, color=ROJO, label="malos")
    for i in x:
        ax.text(i - 0.18, si[i] + 0.2, str(si[i]), ha="center", fontsize=11, weight="bold")
        ax.text(i + 0.18, no[i] + 0.2, str(no[i]), ha="center", fontsize=11, weight="bold")
    ax.set_xticks(x, [t for _, t in claves])
    ax.set_title("Pares de tu examen que el agente llega a ver", fontsize=10.5)
    ax.legend(frameon=False, fontsize=9)
    ax = axs[1]
    tipos = [("del_agente", "del agente (siempre)", VERDE), ("automaticos", "automáticos", ORO)]
    base = np.zeros(len(claves))
    for campo, txt, color in tipos:
        v = np.array([c2[k][campo] for k, _ in claves], dtype=float)
        ax.barh(x, v, left=base, color=color, label=txt)
        for i in x:
            ax.text(base[i] + v[i] / 2, i, f"{int(v[i]):,}", ha="center", va="center", fontsize=9,
                    color=FONDO, weight="bold")
        base += v
    for i, (k, _) in enumerate(claves):
        ax.text(base[i] + 40, i, f"nodos sin vecinos: {c2[k]['nodos_sin_vecinos']}", va="center",
                fontsize=8.5, color=TENUE)
    ax.set_yticks(x, [t for _, t in claves], fontsize=9)
    ax.set_xlim(0, 4300)
    ax.invert_yaxis()
    ax.set_title("Asociaciones que se muestran en total (851 recuerdos activos)", fontsize=10.5)
    ax.legend(frameon=False, fontsize=9, loc="lower right")
    fig.text(0.5, -0.06, "Muestra chica (10–13 pares de tu examen caen aquí) y parte del examen se armó con la "
             "fuerza de la neurona: es una señal, no una prueba firme. Medido en copia; no está en el motor.",
             ha="center", color=TENUE, fontsize=9.5)
    _guardar(fig, "04_lo_que_ve_el_agente.png")


# ───────────────────────── 5. dónde va en el motor (pendiente) ─────────────────────────
def fig_donde():
    fig, ax = _lienzo(16, 9.2, (0, 16), (0, 9.2))
    ax.text(8, 8.85, "DÓNDE VA LA NEURONA ASOCIATIVA EN EL MOTOR — lo que hay hoy y lo que queda pendiente",
            ha="center", fontsize=16, weight="bold")
    ax.text(8, 8.42, "Línea llena = funciona hoy (v35).  Línea punteada violeta = pendiente, un paso a la vez, "
            "con QA antes y después.  El ranking no se toca.", ha="center", color=TENUE, fontsize=10)

    def caja(x, y, w, h, titulo, sub, borde, ls="-", fc=PANEL, ct=TINTA):
        _caja(ax, x, y, w, h, color=fc, borde=borde, ls=ls)
        ax.text(x + w / 2, y + h - 0.32, titulo, ha="center", va="center", fontsize=10.5,
                weight="bold", color=ct)
        ax.text(x + w / 2, y + (h - 0.45) / 2, sub, ha="center", va="center", fontsize=8.4, color=TENUE)

    ax.text(0.3, 7.75, "AL GUARDAR", color=ORO, fontsize=11, weight="bold")
    caja(0.3, 6.0, 2.2, 1.5, "Agente", "busca antes\n(recordar)", AZUL)
    caja(3.1, 6.0, 2.6, 1.5, "aprender", "busqueda_previa\n+ vincular_con", AZUL)
    caja(6.3, 6.65, 3.0, 0.95, "enlaces del agente", "manual · intocables (v35)", VERDE)
    caja(6.3, 5.25, 3.0, 1.2, "5 reglas automáticas", "sinónimo · PMI · co-ocurrencia\nco-nombre · co-semántica", ORO)
    caja(10.2, 5.4, 2.6, 2.2, "GRAFO", "sinapsis + SDM\n(como CA3)\n13,342 conexiones\nen la memoria de Dennys", CIAN)
    caja(13.4, 5.4, 2.3, 2.2, "hormiguita", "Gemini limpia el grafo\n(API externa)\nsigue en v35", ROJO)
    _flecha(ax, (2.5, 6.75), (3.1, 6.75))
    _flecha(ax, (5.7, 7.0), (6.3, 7.12), color=VERDE)
    _flecha(ax, (5.7, 6.4), (6.3, 5.85), color=ORO)
    _flecha(ax, (9.3, 7.12), (10.2, 6.9), color=VERDE)
    _flecha(ax, (9.3, 5.85), (10.2, 6.0), color=ORO)
    _flecha(ax, (13.4, 6.5), (12.8, 6.5), color=ROJO)

    ax.text(0.3, 4.25, "AL BUSCAR", color=CIAN, fontsize=11, weight="bold")
    caja(0.3, 2.5, 2.2, 1.5, "Agente", "recordar", AZUL)
    caja(3.1, 2.5, 3.4, 1.5, "RANKING (intacto)", "fórmula a mano +\nneurona del ranking (v34)", AZUL)
    caja(7.1, 2.5, 2.4, 1.5, "top-5", "los recuerdos\nencontrados", AZUL)
    caja(10.2, 2.5, 2.6, 1.5, "canal 2", "5 asociaciones por\nrecuerdo, peso ≥ 0.5", CIAN)
    caja(13.4, 2.5, 2.0, 1.5, "el agente ve", "hoy: 5 buenos /\n8 malos\n(pares de tu examen)", AZUL)
    _flecha(ax, (2.5, 3.25), (3.1, 3.25))
    _flecha(ax, (6.5, 3.25), (7.1, 3.25))
    _flecha(ax, (9.5, 3.25), (10.2, 3.25))
    _flecha(ax, (12.8, 3.25), (13.4, 3.25))
    _flecha(ax, (11.5, 5.4), (11.5, 4.0), color=CIAN)

    nx, ny = 7.4, 0.25
    _caja(ax, nx, ny, 3.6, 1.75, color="#1b1640", borde=VIOLETA, ls="--", lw=2.2)
    ax.add_patch(Circle((nx + 0.55, ny + 0.9), 0.32, color=VIOLETA, zorder=4))
    ax.text(nx + 2.05, ny + 1.35, "NEURONA ASOCIATIVA", ha="center", fontsize=10.5, weight="bold", color=VIOLETA)
    ax.text(nx + 2.05, ny + 0.72, "cerrada · examinada\nlista, sin cablear", ha="center", va="center",
            fontsize=8.6, color=TINTA)
    _flecha(ax, (nx + 3.6, ny + 1.2), (11.0, 2.5), color=VIOLETA, ls="--", lw=2.0)
    ax.text(11.9, 1.75, "① filtra el canal 2 (≥ 0.5)\n   medido en copia: 9 / 1  → próximo paso",
            fontsize=8.6, color=VIOLETA, weight="bold")
    _flecha(ax, (nx + 3.6, ny + 0.55), (15.62, 5.4), color=VIOLETA, ls="--", lw=1.6,
            cs="angle,angleA=0,angleB=90,rad=0.3")
    ax.text(15.5, 4.7, "② reemplaza a\nla hormiguita", ha="right", va="center", fontsize=8.6,
            color=VIOLETA, weight="bold")
    _flecha(ax, (nx, ny + 0.9), (6.8, 5.25), color=VIOLETA, ls="--", lw=1.4,
            cs="angle,angleA=180,angleB=90,rad=0.3")
    ax.text(3.2, 4.55, "③ revisa los sinónimos y propone\n    enlaces que faltan (80 % aprobados)",
            fontsize=8.6, color=VIOLETA, weight="bold")

    ax.text(0.3, 1.45, "Probado y dejado fuera:", fontsize=9.5, weight="bold", color=TINTA)
    ax.text(0.3, 0.95, "✗ poner el peso de nacimiento (QA idéntica → revertido)", fontsize=8.8, color=NARANJA)
    ax.text(0.3, 0.5, "✗ cortar sinapsis al nacer (baja el recall)", fontsize=8.8, color=ROJO)
    _guardar(fig, "05_donde_va_en_el_motor.png")


if __name__ == "__main__":
    print("Dibujando figuras de cierre de la neurona asociativa (v35)…")
    fig_motor()
    fig_viaje()
    fig_ruido()
    fig_agente()
    fig_donde()
