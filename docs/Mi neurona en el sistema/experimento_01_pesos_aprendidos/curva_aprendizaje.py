#!/usr/bin/env python3
"""¿Cuánto necesita aprender la neurona, y sabe buscar lo que nunca vio?

Usa las mismas señales y el mismo modelo R2 (manual + capa oculta) de
entrenar_neurona.py, con la misma partición en 5 folds agrupados por nodo.
Mide dos cosas:

  A. CURVA DE APRENDIZAJE: R2 entrenado con solo el 5 %, 10 %, 25 %, 50 % y
     100 % de los nodos de entrenamiento. El test se hace siempre sobre nodos
     que la neurona nunca vio. Responde: ¿cuántos ejemplos necesitaría la
     base de otra persona para que su neurona aprenda?

  B. CATEGORÍA NUNCA VISTA: para cada categoría K (typo, por_tema, ...), R2
     se entrena SIN ningún caso de K y se evalúa solo en casos de K.
     Responde: ¿la neurona aprende "a buscar" en general, o solo lo que se le
     enseñó?

Offline: lee datos/pools_semilla1.jsonl.gz (lo genera exportar_senales.py).
No toca el motor, la DB ni el snapshot.

Uso:
    python curva_aprendizaje.py [--entrada RUTA] [--semilla-folds 7]
Salida: el informe por stdout y resultados/curva_aprendizaje_<semilla>.json
"""
import json

import numpy as np

import entrenar_neurona as en

FRACCIONES = (0.05, 0.10, 0.25, 0.50, 1.00)


def r1(ranks, casos):
    return sum(1 for c in casos if ranks[c["id"]] == 1) / len(casos) * 100 if casos else float("nan")


def gana_pierde(ranks, base, casos):
    g = sum(1 for c in casos if ranks[c["id"]] == 1 and base[c["id"]] != 1)
    p = sum(1 for c in casos if ranks[c["id"]] != 1 and base[c["id"]] == 1)
    return g, p


def main():
    casos = en.cargar(en.ARGS.entrada)
    nodos = sorted({c["exp"] for c in casos})
    rng2 = np.random.default_rng(en.SEMILLA)
    rng2.shuffle(nodos)
    fold_de = {n: i % 5 for i, n in enumerate(nodos)}
    rng_sub = np.random.default_rng(1000 + en.SEMILLA)
    cats = sorted({c["cat"] for c in casos})

    base = {}
    curva = {f: {} for f in FRACCIONES}
    n_train = {f: [] for f in FRACCIONES}
    loco = {k: {} for k in cats}        # R2 entrenado sin la categoría k
    for f in range(5):
        tr = [c for c in casos if fold_de[c["exp"]] != f]
        te = [c for c in casos if fold_de[c["exp"]] == f]
        base.update(en.evaluar(en.entrenar("M0", tr), te))
        # A. curva de aprendizaje (submuestreo por NODO, no por caso)
        nodos_tr = sorted({c["exp"] for c in tr})
        orden = list(nodos_tr)
        rng_sub.shuffle(orden)
        for fr in FRACCIONES:
            elegidos = set(orden[:max(1, int(round(fr * len(orden))))])
            sub = [c for c in tr if c["exp"] in elegidos]
            n_train[fr].append(len(sub))
            curva[fr].update(en.evaluar(en.entrenar("R2", sub), te))
        # B. categoría nunca vista
        for k in cats:
            sub = [c for c in tr if c["cat"] != k]
            te_k = [c for c in te if c["cat"] == k]
            if te_k:
                loco[k].update(en.evaluar(en.entrenar("R2", sub), te_k))
        print(f"  fold {f} listo", flush=True)

    print(f"\nA. CURVA DE APRENDIZAJE (R2, test en nodos nunca vistos, partición {en.SEMILLA})")
    print(f"   M0 manual: R@1 {r1(base, casos):.2f}")
    print(f"   {'fracción':>8s} {'casos train':>11s} {'R@1':>6s}  gana/pierde vs M0")
    salida = {"semilla": en.SEMILLA, "M0_R1": r1(base, casos), "curva": [], "categoria_nunca_vista": []}
    for fr in FRACCIONES:
        g, p = gana_pierde(curva[fr], base, casos)
        nt = float(np.mean(n_train[fr]))
        print(f"   {fr*100:7.0f}% {nt:11.0f} {r1(curva[fr], casos):6.2f}  +{g} / -{p}")
        salida["curva"].append(dict(fraccion=fr, casos_train=nt, R1=r1(curva[fr], casos), gana=g, pierde=p))

    print("\nB. CATEGORÍA NUNCA VISTA (R2 entrenado sin esa categoría, evaluado solo en ella)")
    print(f"   {'categoría':20s} {'n':>4s} {'M0':>7s} {'R2 sin verla':>13s} {'R2 viéndola':>12s}  gana/pierde (sin verla)")
    full = curva[1.00]
    for k in cats:
        ck = [c for c in casos if c["cat"] == k]
        g, p = gana_pierde(loco[k], base, ck)
        print(f"   {k:20s} {len(ck):4d} {r1(base, ck):7.2f} {r1(loco[k], ck):13.2f} {r1(full, ck):12.2f}  +{g} / -{p}")
        salida["categoria_nunca_vista"].append(dict(categoria=k, n=len(ck), M0=r1(base, ck),
                                                    R2_sin_verla=r1(loco[k], ck), R2_viendola=r1(full, ck),
                                                    gana=g, pierde=p))
    destino = en.AQUI / "resultados" / f"curva_aprendizaje_{en.SEMILLA}.json"
    with open(destino, "w", encoding="utf-8") as fh:
        json.dump(salida, fh, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
