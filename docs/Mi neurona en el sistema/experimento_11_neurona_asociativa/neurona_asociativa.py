"""La neurona asociativa de BioRAG (experimento 11): ¿estos dos recuerdos tienen que ver?

Igual que la neurona del ranking (v34), tiene dos partes:

  1. PISO A MANO: una fórmula con pesos redondos, elegidos mirando el banco de
     calibración (sección 4 del README). Si la neurona no está, manda el piso.
  2. CORRECCIÓN: una red chiquita (10 agujas -> 6 neuronas -> 1 número) que se
     SUMA al piso. Viene entrenada "de fábrica" (de nacimiento) y queda FIJA:
     en la memoria del usuario no aprende nada, solo decide.

  z      = piso(agujas) + corrección(agujas)           (corrección acotada a ±TECHO)
  fuerza = 1 / (1 + e^-z)                              (0..1)

  fuerza >= 0.80  -> conectar
  0.50 .. 0.80    -> conexión débil (propuesta, a prueba)
  < 0.50          -> no conectar

  COMPETENCIA (como las neuronas reales: cada una se queda con sus K entradas
  más fuertes): además, cada recuerdo conserva sus K socios de mayor fuerza
  aunque no lleguen al umbral. Así la neurona nunca deja a un recuerdo solo
  y no depende de que el umbral de fábrica calce con cada memoria.

Solo numpy. Los pesos de fábrica viven en `pesos_fabrica.json`.
"""
import json
import os

import numpy as np

AGUJAS = ["parecido", "semantica", "rareza_max", "rareza_media", "pistas_raras",
          "cobertura", "mutuo", "vecinos", "hub", "una_sola"]

# Piso a mano (pesos redondos; ver README sección 4 "banco de calibración")
PISO = {
    "sesgo": -5.0,
    "mutuo": 3.0,         # inhibición lateral: ¿son de los mejores socios el uno del otro?
    "parecido": 3.0,      # corteza: palabras parecidas
    "rareza_max": 2.0,    # giro dentado: una pista muy rara compartida
    "semantica": 2.0,     # corteza: significado parecido
    "vecinos": 1.0,       # CA3: mismos vecinos
    "pistas_raras": 1.0,  # giro dentado: varias pistas raras
    "una_sola": -1.0,     # Dennys: una sola palabra no basta
    "hub": -1.0,          # homeostasis: recuerdo que se parece a todo
}
TECHO = 1.0               # la corrección nunca mueve el piso más de ±1 (con ±3 aprendía cosas que no viajan; README §6)
OCULTAS = 6
UMBRAL_DEBIL = 0.50
UMBRAL_CONECTAR = 0.80
_RUTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pesos_fabrica.json")


def _columnas(F, nombres):
    idx = [nombres.index(a) for a in AGUJAS]
    return np.asarray(F, dtype=np.float64)[:, idx]


def piso(X):
    w = np.array([PISO.get(a, 0.0) for a in AGUJAS])
    return X @ w + PISO["sesgo"]


def correccion(p, X):
    if p is None:
        return np.zeros(len(X))
    return TECHO * np.tanh((np.tanh(X @ p["W"].T + p["b"]) @ p["v"]) / TECHO)


def fuerza(F, nombres, p="fabrica"):
    """F: matriz de agujas (filas = pares). p: pesos ("fabrica", None = solo piso, o dict)."""
    X = _columnas(F, nombres)
    if p == "fabrica":
        p = cargar()
    z = piso(X) + correccion(p, X)
    return 1.0 / (1.0 + np.exp(-z))


def decision(f):
    return np.where(f >= UMBRAL_CONECTAR, "conectar", np.where(f >= UMBRAL_DEBIL, "debil", "no"))


K_COMPETENCIA = 10


def competencia(f, pares, k=K_COMPETENCIA):
    """True si el par llega a 'conectar' o está entre los k más fuertes de alguno de sus dos recuerdos."""
    f = np.asarray(f, dtype=float)
    keep = f >= UMBRAL_CONECTAR
    por = {}
    for i, (a, b) in enumerate(pares):
        por.setdefault(a, []).append(i)
        por.setdefault(b, []).append(i)
    for idx in por.values():
        if len(idx) <= k:
            keep[idx] = True
        else:
            idx = np.asarray(idx)
            keep[idx[np.argsort(-f[idx], kind="mergesort")[:k]]] = True
    return keep


def nuevos_pesos(semilla=0):
    r = np.random.default_rng(semilla)
    return {"W": r.normal(0, 0.3, (OCULTAS, len(AGUJAS))), "b": np.zeros(OCULTAS), "v": np.zeros(OCULTAS)}


def entrenar(X, y, w, X_guardia, y_guardia, w_guardia, pasos=3000, lr=0.01, l2=1e-3, paciencia=300, semilla=0):
    """Entrena SOLO la corrección (el piso no se toca). Pérdida logística con pesos
    por fila (cada memoria pesa igual y, dentro de ella, sí/no pesan igual).
    Techo: se queda con los pesos que mejor le van a la GUARDIA (recuerdos que
    nunca estudia) y para si la guardia deja de mejorar `paciencia` pasos."""
    p = nuevos_pesos(semilla)
    m = {k: np.zeros_like(v) for k, v in p.items()}
    s = {k: np.zeros_like(v) for k, v in p.items()}
    base, base_g = piso(X), piso(X_guardia)

    def perdida(pp, XX, yy, ww, bb):
        z = bb + correccion(pp, XX)
        q = 1 / (1 + np.exp(-z))
        return float(np.sum(ww * -(yy * np.log(q + 1e-9) + (1 - yy) * np.log(1 - q + 1e-9))) / np.sum(ww))

    mejor, mejor_p, sin_mejora = perdida(p, X_guardia, y_guardia, w_guardia, base_g), {k: v.copy() for k, v in p.items()}, 0
    inicial = mejor
    for t in range(1, pasos + 1):
        H = np.tanh(X @ p["W"].T + p["b"])
        u = H @ p["v"]
        c = TECHO * np.tanh(u / TECHO)
        q = 1 / (1 + np.exp(-(base + c)))
        g = w * (q - y) / np.sum(w)                       # dL/dz
        gu = g * (1 - np.tanh(u / TECHO) ** 2)            # dz/du
        gv = H.T @ gu + l2 * p["v"]
        gH = np.outer(gu, p["v"]) * (1 - H ** 2)
        gW = gH.T @ X + l2 * p["W"]
        gb = gH.sum(axis=0)
        for k, gr in (("W", gW), ("b", gb), ("v", gv)):
            m[k] = 0.9 * m[k] + 0.1 * gr
            s[k] = 0.999 * s[k] + 0.001 * gr * gr
            p[k] -= lr * (m[k] / (1 - 0.9 ** t)) / (np.sqrt(s[k] / (1 - 0.999 ** t)) + 1e-8)
        if t % 25 == 0:
            lg = perdida(p, X_guardia, y_guardia, w_guardia, base_g)
            if lg < mejor - 1e-5:
                mejor, mejor_p, sin_mejora = lg, {k: v.copy() for k, v in p.items()}, 0
            else:
                sin_mejora += 25
                if sin_mejora >= paciencia:
                    break
    return mejor_p, {"guardia_inicial": inicial, "guardia_final": mejor, "pasos": t}


def guardar(p, extra=None, ruta=_RUTA):
    d = {k: np.asarray(v).tolist() for k, v in p.items()}
    d.update({"agujas": AGUJAS, "piso": PISO, "techo": TECHO, "ocultas": OCULTAS})
    if extra:
        d["fabrica"] = extra
    with open(ruta, "w") as f:
        json.dump(d, f, indent=1)


def cargar(ruta=_RUTA):
    if not os.path.exists(ruta):
        return None
    d = json.load(open(ruta))
    if d.get("agujas") != AGUJAS:
        return None
    return {k: np.array(d[k], dtype=np.float64) for k in ("W", "b", "v")}
