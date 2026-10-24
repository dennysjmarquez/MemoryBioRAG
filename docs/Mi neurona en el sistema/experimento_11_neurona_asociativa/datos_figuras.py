"""Saca de la COPIA de la memoria de Dennys los pocos números que las figuras necesitan
y que no están en los otros resultados. Escribe resultados/figuras_dennys.json.

No guarda ningún texto de los recuerdos: solo nombres de concepto (ya públicos en
examen_dennys.json), tipos de conexión, valores de agujas y fuerzas.

Uso (necesita la copia del snapshot en /tmp/e11/dennys.db, nunca la DB real):
    python datos_figuras.py
"""
import json
import os

import numpy as np

import agujas
import corpus
import neurona_asociativa as na

AQUI = os.path.dirname(os.path.abspath(__file__))
CASO = "leccion_discrepancia_busquedas_vocabulario_no_estocasticidad"
PAR_EJEMPLO = "evaluacion_ideas_evolucion_20260805_interferencia_agujeros_permutacion"


def main():
    mem = corpus.dennys()
    conceptos, sin, cuar = mem["conceptos"], mem["sin"], mem["cuarentena"]
    m = agujas.Memoria(mem["textos"], orden=mem["orden"], etiquetas=mem["etiquetas"])
    p = na.cargar()
    pares = sorted(sin)
    F = m.agujas(pares)
    f = na.fuerza(F, agujas.NOMBRES_TODAS, p=p)
    tipo = [sin[k][0] for k in pares]
    peso = [float(sin[k][1]) for k in pares]

    # Fuerzas por juez (histograma, 40 cajas entre 0 y 1)
    no_g = sorted(k for k, v in cuar.items() if v[2] == 0 and v[3] != "manual" and "prueba" not in v[0])
    fn = na.fuerza(m.agujas(no_g), agujas.NOMBRES_TODAS, p=p)
    fh = np.array([f[i] for i, t in enumerate(tipo) if t == "manual"])
    fg = np.array([f[i] for i, t in enumerate(tipo) if t == "latente_confirmada"])
    cajas = np.linspace(0, 1, 41)
    hist = {nm: np.histogram(x, cajas)[0].tolist() for nm, x in
            (("humano_si", fh), ("gemini_si", fg), ("gemini_no", fn))}

    # Fuerza por tipo de conexión (cuartiles)
    por_tipo = {}
    for t in sorted(set(tipo)):
        x = np.array([f[i] for i, tt in enumerate(tipo) if tt == t])
        if len(x) >= 50:
            por_tipo[t] = {"n": int(len(x)), "q": [round(float(v), 3) for v in np.percentile(x, [10, 25, 50, 75, 90])]}

    # Caso Neuro-Visor: todas sus conexiones
    ic = conceptos.index(CASO)
    k10 = na.competencia(f, pares, 10)
    filas = []
    ejemplo = None
    for i, (a, b) in enumerate(pares):
        if ic in (a, b):
            otro = conceptos[b if a == ic else a]
            filas.append({"con": otro, "tipo": tipo[i], "peso_motor": round(peso[i], 2),
                          "fuerza": round(float(f[i]), 3), "k10": bool(k10[i])})
            if otro == PAR_EJEMPLO:
                ejemplo = {"a": CASO, "b": otro,
                           "agujas": {nm: round(float(F[i, agujas.NOMBRES_TODAS.index(nm)]), 4)
                                      for nm in agujas.NOMBRES},
                           "fuerza": round(float(f[i]), 4)}
    filas.sort(key=lambda q: -q["fuerza"])   # igual que examen_dennys (3 decimales, orden estable)

    # Valores típicos de cada aguja: humano-sí vs Gemini-no (mediana)
    Fn = m.agujas(no_g)
    Fh = F[[i for i, t in enumerate(tipo) if t == "manual"]]
    medianas = {nm: {"humano_si": round(float(np.median(Fh[:, j])), 3),
                     "gemini_no": round(float(np.median(Fn[:, j])), 3)}
                for j, nm in enumerate(agujas.NOMBRES_TODAS) if nm in agujas.NOMBRES}

    out = {"fuente": "copia del snapshot qa_escape_qcr_20260811.db (solo lectura)",
           "cajas": cajas.round(3).tolist(), "hist_fuerza_por_juez": hist,
           "fuerza_por_tipo": por_tipo, "caso_neuro_visor": filas, "par_ejemplo": ejemplo,
           "medianas_agujas": medianas,
           "fiab_episodio": round(m.fiab_episodio, 3), "fiab_etiquetas": round(m.fiab_etiquetas, 3)}
    ruta = os.path.join(AQUI, "resultados", "figuras_dennys.json")
    json.dump(out, open(ruta, "w"), ensure_ascii=False, indent=1)
    print("ok", ruta, "| caso:", len(filas), "conexiones | ejemplo:", ejemplo and ejemplo["fuerza"])


if __name__ == "__main__":
    main()
