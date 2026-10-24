#!/usr/bin/env python3
"""Experimento 02: aprender sin hacer trampa, con examen sellado y la regla "ningún caso baja".

Idea de Dennys (2026-10-22): que la neurona ajuste sus pesos hasta que el QA
llegue a 100 % y use el QA como validador.

Parte A, "hasta 100": se entrena R2 sin freno hasta 100 % en lo estudiado y se
mide a la vez en nodos que nunca vio. Muestra la memorización (sobreajuste).

Parte B, la versión correcta de la idea, en 5 rotaciones:
  - los nodos se dividen en ESTUDIO (3/5), VALIDACIÓN (1/5) y EXAMEN SELLADO (1/5);
  - se entrena con ESTUDIO y se PARA cuando la VALIDACIÓN deja de mejorar
    (parada temprana);
  - COMPUERTA "ningún caso baja": la corrección solo se adopta en la medida en
    que NO pierde ningún caso del material visto (estudio + validación) frente
    a los pesos a mano. Dos compuertas:
      * λ: cuánta corrección se aplica (0 = pesos a mano, 1 = completa);
      * margen: la neurona solo puede tocar las consultas donde los pesos a
        mano DUDAN (diferencia pequeña entre el 1.º y el 2.º candidato).
  - el EXAMEN SELLADO se mira una sola vez, al final, para dar el número honesto.

Offline: reutiliza las señales del experimento 01
(../experimento_01_pesos_aprendidos/datos/pools_semilla1.jsonl.gz).
No toca el motor, la DB ni el snapshot.

Uso:
    python entrenar_con_examen_sellado.py [--parte A|B|AB] [--semilla-folds 7]
Salida: el informe por stdout y resultados/parte_{A,B}_<semilla>.json
"""
import argparse
import copy
import json
import math
import sys
from pathlib import Path

import numpy as np

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent / "experimento_01_pesos_aprendidos"))
import entrenar_neurona as en  # noqa: E402  (mismas señales, mismo modelo, mismos datos)

ap = argparse.ArgumentParser()
ap.add_argument("--parte", default="AB", choices=["A", "B", "AB"])
ARGS, _ = ap.parse_known_args()
SEMILLA = en.SEMILLA
RES = AQUI / "resultados"
RES.mkdir(exist_ok=True)


# ---------------------------------------------------------------- utilidades
def r1(ranks, casos):
    return sum(1 for c in casos if ranks[c["id"]] == 1) / len(casos) * 100


def r5(ranks, casos):
    return sum(1 for c in casos if ranks[c["id"]] and ranks[c["id"]] <= 5) / len(casos) * 100


def perdidas(ranks, base, casos):
    """Casos que bajan frente a los pesos a mano: pierden el 1.º puesto o salen del top-5."""
    p1 = [c["id"] for c in casos if base[c["id"]] == 1 and ranks[c["id"]] != 1]
    p5 = [c["id"] for c in casos if (base[c["id"]] or 99) <= 5 and (ranks[c["id"]] or 99) > 5]
    return p1, p5


def ganados(ranks, base, casos):
    return [c["id"] for c in casos if base[c["id"]] != 1 and ranks[c["id"]] == 1]


def margen_m0(c):
    """Seguridad de los pesos a mano: logit del 1.º menos logit del 2.º."""
    b = np.sort(c["base"])[::-1]
    return float(b[0] - b[1]) if len(b) > 1 else 99.0


def top1_exacto(c):
    """¿El 1.º de los pesos a mano coincide exactamente con el nombre? (señal match_exacto)"""
    return len(c["X"]) > 0 and c["X"][int(np.argmax(c["base"])), 15] == 1.0


def puntuar(m, c, lam=1.0, tau=None, exacto=False):
    """Score con la corrección aprendida atenuada por λ y, opcionalmente, con la compuerta de margen
    y la protección del nombre exacto (si el 1.º de los pesos a mano es el nombre exacto, no se toca)."""
    s_m0 = c["base"]
    if lam == 0.0 or (tau is not None and margen_m0(c) >= tau) or (exacto and top1_exacto(c)):
        return s_m0
    return s_m0 + lam * (m.score(c)[0] - s_m0)


def rangos(m, casos, lam=1.0, tau=None, exacto=False):
    return {c["id"]: en.rango(puntuar(m, c, lam, tau, exacto), c["y"]) for c in casos}


def perdida_ce(m, casos):
    tot = 0.0
    for c in casos:
        s = m.score(c)[0]; s = s - s.max()
        tot -= s[c["y"]] - math.log(np.exp(s).sum())
    return tot / len(casos)


def particion(casos):
    nodos = sorted({c["exp"] for c in casos})
    rng = np.random.default_rng(SEMILLA)
    rng.shuffle(nodos)
    return {n: i % 5 for i, n in enumerate(nodos)}


def validos(cs):
    return [c for c in cs if c["y"] >= 0 and len(c["X"]) > 1]


# ------------------------------------------------------------------- parte A
def parte_a(casos):
    fold = particion(casos)
    estudio = [c for c in casos if fold[c["exp"]] != 0]
    nuevos = [c for c in casos if fold[c["exp"]] == 0]
    m0 = en.entrenar("M0", estudio)
    salida = {"semilla": SEMILLA, "n_estudio": len(estudio), "n_nuevos": len(nuevos), "curvas": {}}
    print(f"\nPARTE A. Entrenar sin freno hasta 100 % (estudio {len(estudio)} preguntas, "
          f"nodos nuevos {len(nuevos)})")
    for h, pasos in ((6, 4000), (64, 2000)):
        m = en.Modelo("R2", len(en.F_SIG), len(estudio[0]["q"]), h=h)
        tr = validos(estudio)
        filas = [(0, r1(en.evaluar(m0, estudio), estudio), r1(en.evaluar(m0, nuevos), nuevos))]
        print(f"  neurona con {h} neuronas ocultas | paso | R@1 en lo estudiado | R@1 en nodos nuevos")
        print(f"  {'':31s} {0:5d}   {filas[0][1]:6.2f}              {filas[0][2]:6.2f}", flush=True)
        for paso in range(1, pasos + 1):
            m.paso(tr, lr=.03, l2=0.0)            # sin regularización: puede memorizar
            if paso % 250 == 0 or paso == 100:
                f = (paso, r1(en.evaluar(m, estudio), estudio), r1(en.evaluar(m, nuevos), nuevos))
                filas.append(f)
                print(f"  {'':31s} {f[0]:5d}   {f[1]:6.2f}              {f[2]:6.2f}", flush=True)
        salida["curvas"][str(h)] = [dict(paso=a, estudio=b, nuevos=c) for a, b, c in filas]
    (RES / f"parte_A_{SEMILLA}.json").write_text(json.dumps(salida, indent=1), encoding="utf-8")


# ------------------------------------------------------------------- parte B
def entrenar_con_parada(estudio, validacion, max_pasos=3000, cada=25, paciencia=300):
    m = en.Modelo("R2", len(en.F_SIG), len(estudio[0]["q"]), h=6)
    tr, va = validos(estudio), validos(validacion)
    mejor, mejor_p, mejor_paso = perdida_ce(m, va), copy.deepcopy(m.p), 0
    for paso in range(1, max_pasos + 1):
        m.paso(tr)                                # mismos hiperparámetros que el experimento 01
        if paso % cada == 0:
            l = perdida_ce(m, va)
            if l < mejor - 1e-5:
                mejor, mejor_p, mejor_paso = l, copy.deepcopy(m.p), paso
            elif paso - mejor_paso >= paciencia:
                break
    m.p = mejor_p
    return m, mejor_paso


LAMBDAS = [round(x * .05, 2) for x in range(21)]
TAUS = [.05, .1, .2, .3, .4, .5, .75, 1.0, 1.5, 2.0, 3.0, 99.0]   # 99 = sin compuerta de margen


def parte_b(casos):
    fold = particion(casos)
    base = {}
    sellado = {"sin_compuerta": {}, "compuerta_lambda": {}, "compuerta_margen": {}, "compuerta_ambas": {},
               "compuerta_lambda_exacto": {}}
    detalle = []
    print("\nPARTE B. Examen sellado + parada temprana + compuerta 'ningún caso baja' (5 rotaciones)")
    for k in range(5):
        ex = [c for c in casos if fold[c["exp"]] == k]
        va = [c for c in casos if fold[c["exp"]] == (k + 1) % 5]
        es = [c for c in casos if fold[c["exp"]] not in (k, (k + 1) % 5)]
        visto = es + va
        m0 = en.entrenar("M0", es)
        base_v = en.evaluar(m0, visto)
        base.update(en.evaluar(m0, ex))
        m, paso = entrenar_con_parada(es, va)

        def sin_perdidas(lam, tau, exacto=False):
            rk = rangos(m, visto, lam, tau, exacto)
            p1, p5 = perdidas(rk, base_v, visto)
            return not p1 and not p5, len(ganados(rk, base_v, visto))

        # compuerta λ: el mayor λ que no pierde nada en lo visto
        lam_ok = max(l for l in LAMBDAS if sin_perdidas(l, None)[0])
        # compuerta de margen (λ=1): el mayor umbral de duda que no pierde nada en lo visto
        tau_ok = max([t for t in TAUS if sin_perdidas(1.0, t)[0]], default=0.0)
        # ambas: para cada τ, el mayor λ sin pérdidas; se elige la que más gana en lo visto
        mejor = (0, 0.0, 0.0)
        for t in TAUS:
            for l in reversed(LAMBDAS):
                ok, g = sin_perdidas(l, t)
                if ok:
                    if g > mejor[0]:
                        mejor = (g, l, t)
                    break
        _, lam_a, tau_a = mejor
        # λ + protección del nombre exacto (regla añadida tras ver el caso 0274; ver README §4)
        lam_e = max(l for l in LAMBDAS if sin_perdidas(l, None, True)[0])
        sellado["sin_compuerta"].update(rangos(m, ex))
        sellado["compuerta_lambda"].update(rangos(m, ex, lam_ok))
        sellado["compuerta_lambda_exacto"].update(rangos(m, ex, lam_e, None, True))
        sellado["compuerta_margen"].update(rangos(m, ex, 1.0, tau_ok if tau_ok else None) if tau_ok else
                                           {c["id"]: base[c["id"]] for c in ex})
        sellado["compuerta_ambas"].update(rangos(m, ex, lam_a, tau_a if tau_a < 99 else None) if lam_a else
                                          {c["id"]: base[c["id"]] for c in ex})
        detalle.append(dict(rotacion=k, paso_parada=paso, lambda_sin_perdidas=lam_ok,
                            tau_sin_perdidas=tau_ok, ambas=dict(lam=lam_a, tau=tau_a),
                            lambda_sin_perdidas_con_exacto=lam_e))
        print(f"  rotación {k}: paró en el paso {paso:4d} | λ sin pérdidas = {lam_ok:.2f} | "
              f"margen sin pérdidas = {tau_ok} | ambas: λ={lam_a:.2f}, margen={tau_a} | "
              f"λ con nombre exacto protegido = {lam_e:.2f}", flush=True)

    print(f"\n  RESULTADO EN EL EXAMEN SELLADO ({len(casos)} preguntas, cada una vista una sola vez)")
    print(f"  {'versión':34s} {'R@1':>6s} {'R@5':>6s}  gana / pierde 1.º  (sale del top-5)")
    print(f"  {'pesos a mano (hoy)':34s} {r1(base, casos):6.2f} {r5(base, casos):6.2f}")
    nombres = {"sin_compuerta": "neurona sin compuerta", "compuerta_lambda": "compuerta λ",
               "compuerta_margen": "compuerta de margen (solo si duda)", "compuerta_ambas": "compuerta λ + margen",
               "compuerta_lambda_exacto": "compuerta λ + nombre exacto"}
    salida = {"semilla": SEMILLA, "M0": dict(R1=r1(base, casos), R5=r5(base, casos)), "rotaciones": detalle,
              "versiones": {}}
    for v, rk in sellado.items():
        p1, p5 = perdidas(rk, base, casos); g = ganados(rk, base, casos)
        print(f"  {nombres[v]:34s} {r1(rk, casos):6.2f} {r5(rk, casos):6.2f}  +{len(g)} / -{len(p1)}  ({len(p5)})")
        salida["versiones"][v] = dict(R1=r1(rk, casos), R5=r5(rk, casos), gana=g, pierde_1=p1, pierde_top5=p5)
    for v in sellado:
        p1 = salida["versiones"][v]["pierde_1"]
        if p1:
            print(f"  pierde ({nombres[v]}): {', '.join(sorted(p1))}")
    (RES / f"parte_B_{SEMILLA}.json").write_text(json.dumps(salida, indent=1, ensure_ascii=False),
                                                 encoding="utf-8")


def main():
    casos = en.cargar(en.ARGS.entrada)
    print(f"casos: {len(casos)} | semilla de partición: {SEMILLA}")
    if "A" in ARGS.parte:
        parte_a(casos)
    if "B" in ARGS.parte:
        parte_b(casos)


if __name__ == "__main__":
    main()
