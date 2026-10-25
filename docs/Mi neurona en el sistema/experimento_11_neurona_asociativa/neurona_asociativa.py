"""La neurona asociativa de BioRAG (experimento 11, versión 2): ¿estos dos recuerdos tienen que ver?

Igual que la neurona del ranking (v34), tiene dos partes:

  1. PISO A MANO: una fórmula con pesos redondos, elegidos con el banco de
     calibración de 8 memorias de fábrica (README, sección 5). Si la parte
     aprendida no está, manda el piso.
  2. CORRECCIÓN: una red chiquita (12 agujas + 3 de contexto -> 6 neuronas -> 1 número) que se
     SUMA al piso. Viene entrenada "de fábrica" (de nacimiento) y queda FIJA:
     en la memoria del usuario no aprende nada, solo decide.

  z      = piso(agujas) + escala * corrección(agujas)    (corrección acotada a ±TECHO)
  fuerza = 1 / (1 + e^-z)                                (0..1)

Reglas de fábrica para que APRENDA y no MEMORICE (todas en `entrenar`):
  - TECHO: la corrección nunca mueve el piso más de ±TECHO.
  - GUARDIA: 20 % de los recuerdos de cada memoria nunca se estudian.
  - NUNCA BAJO EL PISO: solo se guarda una versión que, en la guardia de CADA
    memoria, ordena igual o mejor que el piso solo. Si ninguna lo logra, la
    corrección queda apagada (escala 0 = solo piso).
  - Para cuando la guardia deja de mejorar (aprender, no memorizar).

Decisión (README, sección 7):
  COMPETENCIA: cada recuerdo se queda con sus K socios de mayor fuerza (como las
  neuronas reales, que se quedan con sus entradas más fuertes). Además, todo lo
  que pase de UMBRAL_CONECTAR entra como "activa". El umbral fijo SOLO no se usa
  para decidir: no viaja de una memoria a otra.

Solo numpy. Los pesos de fábrica viven en `pesos_fabrica.json`.
"""
import json
import os

import numpy as np

VERSION = 2
AGUJAS = ["parecido", "semantica", "rareza_max", "rareza_media", "pistas_raras",
          "cobertura", "mutuo", "vecinos", "hub", "una_sola", "episodio", "etiquetas"]
CONTEXTO = ["largo", "fiab_episodio", "fiab_etiquetas"]   # solo los ve la corrección
ENTRADAS = AGUJAS + CONTEXTO

# Piso a mano (pesos redondos; README sección 5 "banco de calibración")
# Elegidos por el banco de 7 memorias (subida por pesos enteros 0..4, signos fijos, arrancando de
# cero). Las agujas que quedaron en 0 no se pierden: la corrección las sigue viendo todas.
PISO = {
    "sesgo": -1.0,        # solo decide cuándo se llega a "conectar" (precisión >= .80 en fábrica)
    "parecido": 2.0,      # corteza: palabras parecidas
    "semantica": 1.0,     # corteza: significado parecido
    "rareza_max": 1.0,    # giro dentado: una pista muy rara compartida
    "episodio": 4.0,      # células de tiempo: se guardaron juntos (solo si la memoria lo confirma)
    "etiquetas": 1.0,     # esquemas: comparten etiquetas/dims (solo si la memoria lo confirma)
}
TECHO = 1.0               # la corrección nunca mueve el piso más de ±1
OCULTAS = 6
UMBRAL_DEBIL = 0.50
UMBRAL_CONECTAR = 0.80
K_COMPETENCIA = 10
_RUTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pesos_fabrica.json")


def _columnas(F, nombres):
    """Las 15 entradas en el orden de ENTRADAS (si faltan las de contexto, valen 0)."""
    F = np.asarray(F, dtype=np.float64)
    cols = [F[:, nombres.index(a)] if a in nombres else np.zeros(len(F)) for a in ENTRADAS]
    return np.nan_to_num(np.stack(cols, axis=1) if len(F) else np.zeros((0, len(ENTRADAS))), nan=0.0)


def piso(X, P=None):
    """El piso solo usa las 12 agujas (las de contexto pesan 0 en el piso)."""
    P = PISO if P is None else P
    w = np.array([P.get(a, 0.0) if a in AGUJAS else 0.0 for a in ENTRADAS])
    return X @ w + P["sesgo"]


def correccion(p, X):
    if p is None:
        return np.zeros(len(X))
    c = TECHO * np.tanh((np.tanh(X @ p["W"].T + p["b"]) @ p["v"]) / TECHO)
    return float(np.asarray(p.get("escala", 1.0))) * c


def fuerza(F, nombres, p="fabrica"):
    """F: matriz de agujas (filas = pares). p: pesos ("fabrica", None = solo piso, o dict)."""
    X = _columnas(F, nombres)
    if isinstance(p, str) and p == "fabrica":
        p = cargar()
    z = np.clip(piso(X) + correccion(p, X), -30, 30)
    return 1.0 / (1.0 + np.exp(-z))


def decision(f):
    """Estado por umbral (solo para el ESTADO de lo que ya ganó la competencia)."""
    return np.where(f >= UMBRAL_CONECTAR, "conectar", np.where(f >= UMBRAL_DEBIL, "debil", "no"))


def competencia(f, pares, k=K_COMPETENCIA):
    """True si el par llega a 'conectar' o está entre los k más fuertes de alguno de sus dos recuerdos.
    Empates: gana el par que aparece primero (orden estable), sin azar."""
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
    return {"W": r.normal(0, 0.3, (OCULTAS, len(ENTRADAS))), "b": np.zeros(OCULTAS), "v": np.zeros(OCULTAS)}


def _auc(s, y):
    """AUC con empates = 1/2 (rangos promedio), vectorizado. Sin scipy."""
    s = np.asarray(s, float)
    y = np.asarray(y)
    p = y == 1
    n1, n0 = int(p.sum()), int((~p).sum())
    if n1 == 0 or n0 == 0:
        return 0.5
    _, inv, cnt = np.unique(s, return_inverse=True, return_counts=True)
    fin = np.cumsum(cnt)
    r = (fin - (cnt - 1) / 2.0)[inv]
    return float((r[p].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def auc_por_recuerdo(z, si, no):
    """De los pares (sí, no) que comparten recuerdo, qué fracción queda bien ordenada (empate = 1/2).
    Es lo que importa para la COMPETENCIA: dentro de cada recuerdo, ¿el bueno gana al malo?"""
    if len(si) == 0:
        return 0.5
    d = z[si] - z[no]
    return float(np.mean(d > 0) + 0.5 * np.mean(d == 0))


def entrenar(estudio, guardias, pasos=4000, lote=2048, lr=0.01, l2=1e-3, paciencia=600, cada=50, semilla=0,
             registro=None, cuidar=0.003):
    """Entrena SOLO la corrección (el piso no se toca), por COMPETENCIA.

    Aprende lo mismo que después va a decidir: dentro de un mismo recuerdo, el socio que SÍ
    tiene que ver debe quedar por encima del que NO (pares sí/no que comparten recuerdo).
    Cada memoria pesa igual.

    estudio   lista de (nombre, Z, idx_si, idx_no): filas de estudio y sus pares sí/no
    guardias  lista de (nombre, Zg, gi_si, gi_no): filas de recuerdos que NUNCA se estudian y sus
              pares sí/no por recuerdo; se mide con `auc_por_recuerdo` (lo mismo que se entrena)

    Techo y piso:
      - la corrección está acotada a ±TECHO;
      - cada `cada` pasos se mide la guardia de CADA memoria. Una versión solo se puede
        guardar si en NINGUNA memoria ordena peor que el piso solo (tolerancia .001) y si
        mejora el promedio. Si nunca pasa, la corrección queda apagada (escala 0);
      - para cuando la guardia deja de mejorar `paciencia` pasos (aprender, no memorizar).
    """
    rng = np.random.default_rng(semilla)
    p = nuevos_pesos(semilla)
    m = {k: np.zeros_like(v) for k, v in p.items()}
    s = {k: np.zeros_like(v) for k, v in p.items()}
    a_piso = {nm: auc_por_recuerdo(piso(Zg), gs, gn) for nm, Zg, gs, gn in guardias}
    utiles = [e for e in estudio if len(e[2]) > 0]

    def medir(pp):
        return {nm: auc_por_recuerdo(piso(Zg) + correccion(pp, Zg), gs, gn) - a_piso[nm]
                for nm, Zg, gs, gn in guardias}

    mejor_media, mejor_p, mejor_dif, sin_mejora = 0.0, None, None, 0
    # "Cuidar a la que va peor" (homeostasis): cada memoria tiene un peso de atención. Si en su
    # guardia la corrección va peor que el piso, su peso sube; si va bien, baja. Mitad parejo,
    # mitad según cómo le va. cuidar = 0 -> todas pesan igual siempre.
    atencion = {e[0]: 1.0 for e in utiles}
    t = 0
    for t in range(1, pasos + 1):
        gW, gb, gv = np.zeros_like(p["W"]), np.zeros_like(p["b"]), np.zeros_like(p["v"])
        for nm, Z, si, no in utiles:
            k = rng.integers(0, len(si), lote)
            Zi, Zj = Z[si[k]], Z[no[k]]
            Hi, Hj = np.tanh(Zi @ p["W"].T + p["b"]), np.tanh(Zj @ p["W"].T + p["b"])
            ui, uj = Hi @ p["v"], Hj @ p["v"]
            dz = (piso(Zi) + TECHO * np.tanh(ui / TECHO)) - (piso(Zj) + TECHO * np.tanh(uj / TECHO))
            g = -atencion[nm] / (1.0 + np.exp(np.clip(dz, -30, 30))) / lote / len(utiles)   # d pérdida / d dz
            for H, Zr, gu in ((Hi, Zi, g * (1 - np.tanh(ui / TECHO) ** 2)),
                              (Hj, Zj, -g * (1 - np.tanh(uj / TECHO) ** 2))):
                gv += H.T @ gu
                gH = np.outer(gu, p["v"]) * (1 - H ** 2)
                gW += gH.T @ Zr
                gb += gH.sum(axis=0)
        gW += l2 * p["W"]
        gv += l2 * p["v"]
        for k2, gr in (("W", gW), ("b", gb), ("v", gv)):
            m[k2] = 0.9 * m[k2] + 0.1 * gr
            s[k2] = 0.999 * s[k2] + 0.001 * gr * gr
            p[k2] -= lr * (m[k2] / (1 - 0.9 ** t)) / (np.sqrt(s[k2] / (1 - 0.999 ** t)) + 1e-8)
        if t % cada == 0:
            dif = medir(p)
            media = float(np.mean(list(dif.values())))
            if registro is not None:
                registro.append((t, {k: round(v, 4) for k, v in dif.items()}))
            if cuidar > 0:
                nms = [e[0] for e in utiles]
                x = np.array([-dif.get(n, 0.0) / cuidar for n in nms])
                x = np.exp(x - x.max())
                x = x / x.sum() * len(nms)
                atencion = {n: 0.5 + 0.5 * float(w) for n, w in zip(nms, x)}
            if min(dif.values()) >= -0.001 and media > mejor_media + 1e-5:
                mejor_media, mejor_p, mejor_dif, sin_mejora = media, {k: v.copy() for k, v in p.items()}, dif, 0
            else:
                sin_mejora += cada
                if sin_mejora >= paciencia:
                    break
    if mejor_p is None:
        mejor_p = nuevos_pesos(semilla)
        mejor_p["escala"] = 0.0
    else:
        mejor_p["escala"] = 1.0
    return mejor_p, {"pasos": t, "escala": mejor_p["escala"], "mejora_media_guardia": round(mejor_media, 4),
                     "guardia_por_memoria": {k: round(v, 4) for k, v in (mejor_dif or {}).items()}}


def guardar(p, extra=None, ruta=_RUTA):
    d = {k: np.asarray(v).tolist() for k, v in p.items()}
    d.update({"version": VERSION, "agujas": AGUJAS, "entradas": ENTRADAS, "piso": PISO, "techo": TECHO,
              "ocultas": OCULTAS})
    if extra:
        d["fabrica"] = extra
    with open(ruta, "w") as f:
        json.dump(d, f, indent=1, ensure_ascii=False)


def cargar(ruta=_RUTA):
    """Pesos de fábrica, o None (= solo piso) si no existen o son de otra versión de agujas/piso."""
    if not os.path.exists(ruta):
        return None
    try:
        d = json.load(open(ruta))
    except (OSError, ValueError):
        return None
    if d.get("agujas") != AGUJAS or d.get("entradas") != ENTRADAS or d.get("version") != VERSION \
            or d.get("piso") != PISO \
            or d.get("techo") != TECHO or d.get("ocultas") != OCULTAS:
        return None
    p = {k: np.array(d[k], dtype=np.float64) for k in ("W", "b", "v")}
    p["escala"] = float(d.get("escala", 1.0))
    if p["W"].shape != (OCULTAS, len(ENTRADAS)) or not all(np.all(np.isfinite(v)) for v in p.values()
                                                          if isinstance(v, np.ndarray)):
        return None
    return p
