"""Prepara la hoja de 100 pares para que Dennys los marque a mano.

Sale de la COPIA del snapshot (/tmp/e11/dennys.db, solo lectura). La hoja NO muestra la fuerza
de la neurona ni de dónde salió cada par (para no influir). Eso queda en clave_no_mirar.json.

Grupos (mezclados al azar en la hoja):
  A  40  conexiones que existen hoy (no manuales) y que la neurona CONSERVA (top 10)
  B  30  conexiones que existen hoy (no manuales) y que la neurona SOLTARÍA
  C  15  pares que Gemini sacó a cuarentena pero la neurona les da fuerza >= .60 (desacuerdo)
  D  15  pares que NO existen hoy y que la neurona propondría (sus candidatos más fuertes)

Uso:  python preparar_hoja.py [ruta_a_una_COPIA_de_la_db]
      (por defecto /tmp/e11/dennys.db · semilla fija: siempre sale la misma hoja)

PRIVACIDAD: la hoja y la clave muestran trozos de tus recuerdos. No se suben a git
(.gitignore de esta carpeta), porque el repo es público.
"""
import csv
import json
import os
import sys

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
import agujas  # noqa: E402
import corpus  # noqa: E402
import neurona_asociativa as na  # noqa: E402

SEMILLA = 11
CUPOS = {"A": 40, "B": 30, "C": 15, "D": 15}


def resumen(texto, n=240):
    cuerpo = texto.split(". ", 1)[1] if ". " in texto else texto
    cuerpo = " ".join(cuerpo.split())
    return cuerpo[:n] + ("…" if len(cuerpo) > n else "")


def main():
    rng = np.random.default_rng(SEMILLA)
    mem = corpus.dennys(sys.argv[1]) if len(sys.argv) > 1 else corpus.dennys()
    con, sin, cuar, textos = mem["conceptos"], mem["sin"], mem["cuarentena"], mem["textos"]
    m = agujas.Memoria(textos, orden=mem["orden"], etiquetas=mem["etiquetas"])
    p = na.cargar()

    pares = sorted(sin)
    f = na.fuerza(m.agujas(pares), agujas.NOMBRES_TODAS, p=p)
    k10 = na.competencia(f, pares, 10)
    no_manual = [i for i, k in enumerate(pares) if sin[k][0] not in ("manual", "manual_v7", "test")]
    A = [i for i in no_manual if k10[i]]
    B = [i for i in no_manual if not k10[i]]

    no_g = sorted(k for k, v in cuar.items() if v[2] == 0 and v[3] != "manual" and "prueba" not in v[0]
                  and k not in sin)
    fg = na.fuerza(m.agujas(no_g), agujas.NOMBRES_TODAS, p=p)
    C = [i for i in range(len(no_g)) if fg[i] >= 0.60]

    existentes = set(sin) | set(cuar)
    cand = [k for k in m.candidatos(rng=np.random.default_rng(0)) if k not in existentes]
    fc = na.fuerza(m.agujas(cand), agujas.NOMBRES_TODAS, p=p)
    kc = na.competencia(fc, cand, 10)
    D = [i for i in range(len(cand)) if kc[i] and fc[i] >= 0.60]

    filas, clave, usados = [], {}, set()

    def tomar(grupo, idx, lista_pares, fuerzas, tipo_de):
        elegidos = rng.choice(len(idx), size=min(CUPOS[grupo], len(idx)), replace=False)
        for j in elegidos:
            i = idx[j]
            a, b = lista_pares[i]
            if (a, b) in usados:
                continue
            usados.add((a, b))
            filas.append((grupo, a, b, float(fuerzas[i]), tipo_de(lista_pares[i])))

    tomar("A", A, pares, f, lambda k: sin[k][0])
    tomar("B", B, pares, f, lambda k: sin[k][0])
    tomar("C", C, no_g, fg, lambda k: "cuarentena_gemini")
    tomar("D", D, cand, fc, lambda k: "no_existe_hoy")
    rng.shuffle(filas)

    ruta_hoja = os.path.join(AQUI, "hoja_para_dennys.csv")
    with open(ruta_hoja, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "recuerdo_A", "que_dice_A", "recuerdo_B", "que_dice_B",
                    "tu_respuesta (si / no / momento / contradicen / nose)", "nota (opcional)"])
        for n, (g, a, b, fz, t) in enumerate(filas, 1):
            w.writerow([n, con[a], resumen(textos[a]), con[b], resumen(textos[b]), "", ""])
            clave[n] = {"grupo": g, "a": con[a], "b": con[b], "fuerza": round(fz, 3), "tipo_hoy": t}
    resumen_grupos = {g: {"en_hoja": sum(1 for v in clave.values() if v["grupo"] == g),
                          "poblacion": len(x)} for g, x in (("A", A), ("B", B), ("C", C), ("D", D))}
    json.dump({"semilla": SEMILLA, "grupos": resumen_grupos, "pares": clave},
              open(os.path.join(AQUI, "clave_no_mirar.json"), "w"), ensure_ascii=False, indent=1)
    print("ok", ruta_hoja, len(filas), "pares |", resumen_grupos)


if __name__ == "__main__":
    main()
