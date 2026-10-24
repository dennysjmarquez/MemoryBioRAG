#!/usr/bin/env python3
"""Experimento 03: medir las ideas de la conversación de Dennys con otra IA (2026-10-22).

Todas usan las señales exportadas en el experimento 01 y parten EXACTAMENTE de los
pesos a mano de hoy (M0). Ideas medidas:

  I1. RE-RANQUEO EN VIVO SIN RESPUESTA (3-4 vueltas con respaldo). Por cada consulta,
      antes de entregar, se mueven las agujas para mejorar una "nota" que el motor se
      pone a sí mismo, y se entrega el mejor intento ("Plan B"). Dos notas propuestas
      en la conversación:
        - "coincidencia de señales": promedio de las señales del top-5;
        - "margen de confianza": distancia entre el 1.º y el 2.º.
      Se compara con la misma búsqueda usando el ORÁCULO (la respuesta correcta), que
      en vivo NO existe: sirve para ver qué falta.
  I2. PESOS CAMPEONES PERSISTENTES: los pesos que "mejoraron" se guardan y la siguiente
      consulta arranca de ellos; si no mejoran, no se guardan.
        - con la nota propia (sin respuesta);
        - con RETROALIMENTACIÓN real después de entregar (como feedback(util)) y una
          compuerta de REPETICIÓN de experiencias: solo se guardan si no empeoran las
          últimas consultas ya vistas. La evaluación es "en línea": cada consulta se
          responde ANTES de conocer su respuesta.
  I3. EMPATE TÉCNICO: si la neurona aprendida (R2) deja al 1.º y al 2.º casi empatados,
      se devuelve el orden de los pesos a mano (se "delega").
  I4. PESOS POR TIPO DE CONSULTA: una neurona R2 por perfil (nombre exacto en el 1.º /
      consulta corta / consulta larga), en vez de una sola para todo.
  I5. GANANCIA NETA "SOLO SI EL PERDIDO SIGUE EN EL TOP-5": de los casos que R2 baja
      del 1.º puesto, ¿cuántos siguen en el top-5?

Offline. No toca el motor, la DB ni el snapshot.
Uso: python medir_ideas.py [--semilla-folds 7]   -> stdout y resultados/ideas_<semilla>.json
"""
import json
import sys
from pathlib import Path

import numpy as np

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent / "experimento_01_pesos_aprendidos"))
import entrenar_neurona as en  # noqa: E402

SEMILLA = en.SEMILLA
NF = len(en.F_SIG)
RES = AQUI / "resultados"
RES.mkdir(exist_ok=True)


def rk(s, y):
    return en.rango(s, y)


def resumen(ranks, base, casos, nombre, salida):
    n = len(casos)
    r1 = sum(1 for c in casos if ranks[c["id"]] == 1) / n * 100
    r5 = sum(1 for c in casos if ranks[c["id"]] and ranks[c["id"]] <= 5) / n * 100
    g = [c["id"] for c in casos if base[c["id"]] != 1 and ranks[c["id"]] == 1]
    p1 = [c["id"] for c in casos if base[c["id"]] == 1 and ranks[c["id"]] != 1]
    p5 = [c["id"] for c in casos if (base[c["id"]] or 99) <= 5 and (ranks[c["id"]] or 99) > 5]
    print(f"  {nombre:52s} {r1:6.2f} {r5:6.2f}   +{len(g):<3d} -{len(p1):<3d} ({len(p5)})", flush=True)
    salida[nombre] = dict(R1=r1, R5=r5, gana=g, pierde_1=p1, pierde_top5=p5)


def cabecera(t):
    print(f"\n{t}\n  {'versión':52s} {'R@1':>6s} {'R@5':>6s}   gana/pierde 1.º (sale top-5)")


# ------------------------------------------------------------- notas en vivo
def nota_senales(c, s):
    top = np.argsort(-s, kind="stable")[:5]
    return float(c["X"][top].mean())


def nota_margen(c, s):
    o = np.sort(s)[::-1]
    return float(o[0] - o[1]) if len(o) > 1 else 0.0


def nota_oraculo(c, s):              # usa la respuesta: en vivo NO existe
    return -float(rk(s, c["y"]))


def en_vivo(c, nota, delta0, intentos, rng, sigma=.5):
    """3-4 vueltas: perturba las agujas, se queda con el mejor intento (Plan B)."""
    mejor_d = delta0
    mejor = nota(c, c["base"] + c["X"] @ delta0)
    for _ in range(intentos):
        d = mejor_d + rng.normal(0, sigma, NF)
        f = nota(c, c["base"] + c["X"] @ d)
        if f > mejor:
            mejor, mejor_d = f, d
    return mejor_d


def main():
    casos = [c for c in en.cargar(en.ARGS.entrada) if c["y"] >= 0 and len(c["X"]) > 1]
    base = {c["id"]: rk(c["base"], c["y"]) for c in casos}
    print(f"casos: {len(casos)} | semilla: {SEMILLA}")
    salida = {}
    cero = np.zeros(NF)

    # ---------------------------------------------------------------- I1
    cabecera("I1. RE-RANQUEO EN VIVO, POR CONSULTA, partiendo de los pesos a mano")
    resumen(base, base, casos, "pesos a mano (hoy)", salida)
    for intentos in (4, 50):
        for nombre, nota in (("nota = coincidencia de señales", nota_senales),
                             ("nota = margen de confianza", nota_margen),
                             ("ORÁCULO: conoce la respuesta (no existe en vivo)", nota_oraculo)):
            rng = np.random.default_rng(SEMILLA)
            r = {}
            for c in casos:
                d = en_vivo(c, nota, cero, intentos, rng)
                r[c["id"]] = rk(c["base"] + c["X"] @ d, c["y"])
            resumen(r, base, casos, f"{intentos} vueltas, {nombre}", salida)

    # ---------------------------------------------------------------- I2
    cabecera("I2. PESOS CAMPEONES PERSISTENTES (orden aleatorio fijo; respuesta ANTES de conocer el resultado)")
    orden = list(casos)
    np.random.default_rng(SEMILLA).shuffle(orden)
    for nombre, nota in (("guardar si mejora la nota de señales", nota_senales),
                         ("guardar si mejora el margen", nota_margen)):
        rng = np.random.default_rng(SEMILLA)
        G = cero.copy(); r = {}
        for c in orden:
            d = en_vivo(c, nota, G, 4, rng)
            r[c["id"]] = rk(c["base"] + c["X"] @ d, c["y"])
            if nota(c, c["base"] + c["X"] @ d) > nota(c, c["base"] + c["X"] @ G):
                G = d                                            # "queda fijo" para la siguiente
        resumen(r, base, casos, f"sin respuesta, {nombre}", salida)
        salida[f"G_final_{nombre}"] = G.tolist()

    # con retroalimentación real DESPUÉS de entregar + compuerta de repetición
    for ventana in (100, 300):
        rng = np.random.default_rng(SEMILLA)
        G = cero.copy(); r = {}; vistos = []; guardados = 0
        for c in orden:
            r[c["id"]] = rk(c["base"] + c["X"] @ G, c["y"])          # 1) se entrega con lo guardado
            vistos.append(c)                                          # 2) llega el feedback
            if r[c["id"]] == 1:
                continue
            memoria = vistos[-ventana:]
            ant = [rk(m["base"] + m["X"] @ G, m["y"]) for m in memoria]
            for _ in range(4):                                        # 3) 4 intentos de mejora
                d = G + rng.normal(0, .25, NF)
                nue = [rk(m["base"] + m["X"] @ d, m["y"]) for m in memoria]
                gana = sum(1 for a, b in zip(ant, nue) if a != 1 and b == 1)
                pierde = sum(1 for a, b in zip(ant, nue) if a == 1 and b != 1)
                if pierde == 0 and gana > 0:                          # 4) se guarda solo si nada baja
                    G = d; guardados += 1
                    break
        resumen(r, base, casos, f"con feedback + repetición (últimas {ventana}), en línea", salida)
        rf = {c["id"]: rk(c["base"] + c["X"] @ G, c["y"]) for c in casos}
        resumen(rf, base, casos, f"   pesos finales aplicados a todo (memoria {ventana})", salida)
        print(f"     (pesos guardados {guardados} veces)")

    # ---------------------------------------------------- I3, I4, I5 (R2 por folds)
    nodos = sorted({c["exp"] for c in casos}); rng2 = np.random.default_rng(SEMILLA); rng2.shuffle(nodos)
    fold = {n: i % 5 for i, n in enumerate(nodos)}

    def perfil(c):
        if c["X"][int(np.argmax(c["base"])), 15] == 1.0:
            return "exacto"
        return "corta" if c["q"][1] * 6 <= 2 else "larga"

    r2 = {}; marg = {}; s_r2 = {}; r_perfil = {}
    for f in range(5):
        tr = [c for c in casos if fold[c["exp"]] != f]
        te = [c for c in casos if fold[c["exp"]] == f]
        m = en.entrenar("R2", tr)
        por = {p: en.entrenar("R2", [c for c in tr if perfil(c) == p]) for p in ("exacto", "corta", "larga")}
        for c in te:
            s = m.score(c)[0]; s_r2[c["id"]] = s
            r2[c["id"]] = rk(s, c["y"])
            o = np.sort(s)[::-1]; marg[c["id"]] = o[0] - o[1]
            r_perfil[c["id"]] = rk(por[perfil(c)].score(c)[0], c["y"])
    cabecera("I3. EMPATE TÉCNICO: si R2 deja 1.º y 2.º a menos de ε, se entrega el orden de los pesos a mano")
    resumen(r2, base, casos, "R2 sin empate técnico", salida)
    for eps in (.01, .05, .1, .2, .5):
        r = {c["id"]: (base[c["id"]] if marg[c["id"]] < eps else r2[c["id"]]) for c in casos}
        n = sum(1 for c in casos if marg[c["id"]] < eps)
        resumen(r, base, casos, f"ε = {eps} (delega en {n} consultas)", salida)

    cabecera("I4. PESOS POR TIPO DE CONSULTA (una R2 por perfil)")
    cuenta = {p: sum(1 for c in casos if perfil(c) == p) for p in ("exacto", "corta", "larga")}
    print(f"  perfiles: {cuenta}")
    resumen(r2, base, casos, "una sola R2 para todo", salida)
    resumen(r_perfil, base, casos, "una R2 por perfil", salida)

    cabecera("I5. GANANCIA NETA SOLO SI EL CASO PERDIDO SIGUE EN EL TOP-5")
    p1 = [c for c in casos if base[c["id"]] == 1 and r2[c["id"]] != 1]
    sigue = [c["id"] for c in p1 if r2[c["id"]] <= 5]
    print(f"  R2 baja del 1.º puesto {len(p1)} casos; siguen en el top-5: {len(sigue)} ({', '.join(sigue)}); "
          f"salen: {', '.join(c['id'] for c in p1 if r2[c['id']] > 5) or 'ninguno'}")
    salida["I5"] = dict(pierde_1=[c["id"] for c in p1], siguen_top5=sigue)

    (RES / f"ideas_{SEMILLA}.json").write_text(json.dumps(salida, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
