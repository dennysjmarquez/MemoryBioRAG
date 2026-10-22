"""Experimento offline: ¿los pesos de _calcular_score_hibrido pueden aprender?

Entrada: datos/pools_semilla1.jsonl.gz (generado por exportar_senales.py).
Solo numpy. No toca el motor ni la DB.

Uso (desde la raíz del repo):
    python "docs/Mi neurona en el sistema/experimento_01_pesos_aprendidos/entrenar_neurona.py"
    # opcional: --entrada otra.jsonl.gz  --semilla-folds 11

Modelos (todos puntúan el pool completo de cada consulta; se compara el rango
ANTES del post-proceso, contra el score base manual M0):
  M0  manual             : el score que hoy calcula _calcular_score_hibrido
  P   perceptrón puro    : regresión softmax lineal sobre las señales, desde cero
                           (la propuesta del otro agente: "logística con 14 features")
  R1  manual + lineal    : logit(M0) + w·x   (arranca EXACTO en M0, w=0)
  R2  manual + capa oculta: logit(M0) + v·tanh(Wx+b)
  R3  manual + compuerta : logit(M0) + Σ_i x_i·(w_i + A_i·q)  (la consulta modula
                           el peso de cada señal: atención mínima sobre señales)

Validación: 5 folds agrupados por nodo esperado (los casos literal/typo/variante
del MISMO nodo nunca están a la vez en train y test). Hiperparámetros fijados de
antemano, no ajustados sobre test.
"""
import argparse, gzip, json, math, sys, collections
from pathlib import Path
import numpy as np

import os
AQUI = Path(__file__).resolve().parent
_ap = argparse.ArgumentParser()
_ap.add_argument("--entrada", default=str(AQUI / "datos" / "pools_semilla1.jsonl.gz"))
_ap.add_argument("--semilla-folds", type=int, default=int(os.environ.get("SEMILLA_FOLDS", "7")))
ARGS = _ap.parse_known_args()[0]  # parse_known_args: permite importarlo desde otros scripts
SEMILLA = ARGS.semilla_folds
rng = np.random.default_rng(SEMILLA)
F_SIG = ["bm25_norm", "dim_score", "concepto_ratio", "sinonimos_ratio", "latcad",
         "grupo_score", "tematico_g", "asoc", "pred_score", "ppmi_score", "hub_match",
         "ncd_score", "episodio_score", "campo_score", "jsd", "match_exacto", "sin95"]


def feats(k):
    lex = k["bm25_norm"] > .001 or k["concepto_ratio"] > .001
    return [k["bm25_norm"], k["dim_score"], k["concepto_ratio"], k["sinonimos_ratio"],
            max(k["score_latente"], k["score_cadena"]), k["grupo_score"],
            k["tematico_score"] if lex else 0.0, min(1.0, k["asoc_count"] / 20.0),
            k["pred_score"], k["ppmi_score"], k["hub_match"], k["ncd_score"],
            k["episodio_score"], k["campo_score"], k["jsd_score"],
            1.0 if k["match_exacto"] else 0.0, 1.0 if k["sinonimos_ratio"] >= .95 else 0.0]


def logit(p):
    p = min(1 - 1e-4, max(1e-4, p))
    return math.log(p / (1 - p))


def cargar(path):
    abrir = gzip.open if str(path).endswith(".gz") else open
    with abrir(path, "rt", encoding="utf-8") as fh:
        R = [json.loads(l) for l in fh if l.strip()]
    golds = collections.defaultdict(set)
    for r in R:
        if r["exp"]:
            golds[r["q"].strip().lower()].add(r["exp"])
    amb = {q for q, g in golds.items() if len(g) > 1}
    casos = []
    for r in R:
        if not r["exp"] or r["q"].strip().lower() in amb:
            continue
        cs = r["cands"]
        X = np.array([feats(k) for k in cs], dtype=float) if cs else np.zeros((0, len(F_SIG)))
        base = np.array([logit(k["_score"]) for k in cs]) if cs else np.zeros(0)
        idx = next((i for i, k in enumerate(cs) if k["c"] == r["exp"]), -1)
        ntok = len(r["q"].split())
        # rasgos de la CONSULTA (iguales para todo el pool): lo que "mira" la compuerta
        q = np.array([1.0, min(ntok, 6) / 6.0,
                      X[:, 2].max() if len(X) else 0.0,      # mejor coincidencia en nombre
                      X[:, 15].max() if len(X) else 0.0,     # ¿hay match exacto en el pool?
                      X[:, 10].max() if len(X) else 0.0,     # ¿se activó un hub?
                      X[:, 0].max() if len(X) else 0.0])     # mejor BM25 del pool
        casos.append(dict(id=r["id"], cat=r["cat"], exp=r["exp"], X=X, base=base, y=idx,
                          q=q, final_top=r["top"]))
    return casos


def rango(scores, y):
    if y < 0:
        return None
    # desempate estable: a igual score gana el que llegó antes al pool (como sort estable)
    orden = sorted(range(len(scores)), key=lambda i: (-scores[i], i))
    return orden.index(y) + 1


class Modelo:
    def __init__(self, tipo, nf, nq, h=6):
        self.tipo = tipo
        self.p = {}
        if tipo == "P":
            self.p["w"] = np.zeros(nf); self.p["b0"] = np.zeros(1)
        if tipo in ("R1",):
            self.p["w"] = np.zeros(nf)
        if tipo == "R2":
            self.p["W"] = rng.normal(0, .1, (h, nf)); self.p["b"] = np.zeros(h); self.p["v"] = np.zeros(h)
        if tipo == "R3":
            self.p["w"] = np.zeros(nf); self.p["A"] = np.zeros((nf, nq))
        self.m = {k: np.zeros_like(v) for k, v in self.p.items()}
        self.s = {k: np.zeros_like(v) for k, v in self.p.items()}
        self.t = 0

    def score(self, c, grad=False):
        X, base, q = c["X"], c["base"], c["q"]
        g = {}
        if self.tipo == "M0":
            return base, g
        if self.tipo == "P":
            s = X @ self.p["w"]
            if grad:
                g["X"] = X
            return s, g
        if self.tipo == "R1":
            return base + X @ self.p["w"], g
        if self.tipo == "R2":
            H = np.tanh(X @ self.p["W"].T + self.p["b"])
            if grad:
                g["H"] = H
            return base + H @ self.p["v"], g
        if self.tipo == "R3":
            weff = self.p["w"] + self.p["A"] @ q
            return base + X @ weff, g

    def paso(self, lote, lr=.03, l2=1e-3):
        grads = {k: np.zeros_like(v) for k, v in self.p.items()}
        loss = 0.0
        for c in lote:
            s, aux = self.score(c, grad=True)
            s = s - s.max()
            pr = np.exp(s); pr /= pr.sum()
            loss -= math.log(max(pr[c["y"]], 1e-12))
            d = pr.copy(); d[c["y"]] -= 1.0                     # dL/ds (softmax CE)
            X = c["X"]
            if self.tipo == "P":
                grads["w"] += X.T @ d
            elif self.tipo == "R1":
                grads["w"] += X.T @ d
            elif self.tipo == "R2":
                H = aux["H"]
                grads["v"] += H.T @ d
                dH = np.outer(d, self.p["v"]) * (1 - H ** 2)
                grads["W"] += dH.T @ X
                grads["b"] += dH.sum(0)
            elif self.tipo == "R3":
                gx = X.T @ d
                grads["w"] += gx
                grads["A"] += np.outer(gx, c["q"])
        n = len(lote)
        self.t += 1
        for k in self.p:
            gk = grads[k] / n + l2 * self.p[k]
            self.m[k] = .9 * self.m[k] + .1 * gk
            self.s[k] = .999 * self.s[k] + .001 * gk ** 2
            mh = self.m[k] / (1 - .9 ** self.t); sh = self.s[k] / (1 - .999 ** self.t)
            self.p[k] -= lr * mh / (np.sqrt(sh) + 1e-8)
        return loss / n


def entrenar(tipo, train, pasos=400):
    m = Modelo(tipo, len(F_SIG), len(train[0]["q"]))
    if tipo == "M0":
        return m
    tr = [c for c in train if c["y"] >= 0 and len(c["X"]) > 1]
    for _ in range(pasos):
        m.paso(tr)
    return m


def evaluar(m, casos):
    return {c["id"]: rango(m.score(c)[0], c["y"]) for c in casos}


def resumen(nombre, ranks, casos):
    n = len(casos)
    r1 = sum(1 for c in casos if ranks[c["id"]] == 1) / n * 100
    r5 = sum(1 for c in casos if ranks[c["id"]] and ranks[c["id"]] <= 5) / n * 100
    mrr = sum(1 / ranks[c["id"]] for c in casos if ranks[c["id"]]) / n
    porcat = collections.defaultdict(list)
    for c in casos:
        porcat[c["cat"]].append(ranks[c["id"]] == 1)
    return r1, r5, mrr, {k: sum(v) / len(v) * 100 for k, v in sorted(porcat.items())}


def main(path):
    casos = cargar(path)
    print(f"casos positivos evaluables: {len(casos)}  | esperado fuera del pool: "
          f"{sum(c['y'] < 0 for c in casos)}  | candidatos totales: {sum(len(c['X']) for c in casos)}")
    # folds agrupados por nodo esperado
    nodos = sorted({c["exp"] for c in casos})
    rng2 = np.random.default_rng(SEMILLA); rng2.shuffle(nodos)
    fold_de = {n: i % 5 for i, n in enumerate(nodos)}
    tipos = ["M0", "P", "R1", "R2", "R3"]
    test_ranks = {t: {} for t in tipos}
    train_r1 = {t: [] for t in tipos}
    pesos_R1 = []
    curva = {}
    for f in range(5):
        tr = [c for c in casos if fold_de[c["exp"]] != f]
        te = [c for c in casos if fold_de[c["exp"]] == f]
        for t in tipos:
            m = entrenar(t, tr)
            test_ranks[t].update(evaluar(m, te))
            rk = evaluar(m, tr)
            train_r1[t].append(sum(1 for c in tr if rk[c["id"]] == 1) / len(tr) * 100)
            if t == "R1":
                pesos_R1.append(m.p["w"].copy())
            if t == "R2":
                for lam in (0.25, 0.5, 0.75):
                    v0 = m.p["v"].copy(); m.p["v"] = v0 * lam
                    curva.setdefault(lam, {}).update(evaluar(m, te)); m.p["v"] = v0
    print("\nRESULTADO EN TEST (5 folds por nodo; rango ANTES del post-proceso)")
    print(f"{'modelo':28s} {'R@1':>6s} {'R@5':>6s} {'MRR':>6s} {'R@1 train':>9s}  gana/pierde vs M0 (R@1)")
    base = test_ranks["M0"]
    nombres = {"M0": "M0 manual (hoy)", "P": "P perceptrón puro", "R1": "R1 manual+lineal",
               "R2": "R2 manual+capa oculta", "R3": "R3 manual+compuerta"}
    for t in tipos:
        r1, r5, mrr, cat = resumen(t, test_ranks[t], casos)
        gana = [c["id"] for c in casos if test_ranks[t][c["id"]] == 1 and base[c["id"]] != 1]
        pierde = [c["id"] for c in casos if test_ranks[t][c["id"]] != 1 and base[c["id"]] == 1]
        pierde5 = [c["id"] for c in casos if (base[c["id"]] or 99) <= 5 and (test_ranks[t][c["id"]] or 99) > 5]
        print(f"{nombres[t]:28s} {r1:6.2f} {r5:6.2f} {mrr:6.3f} {np.mean(train_r1[t]):9.2f}  "
              f"+{len(gana)} / -{len(pierde)}  (pierde top-5: {len(pierde5)})")
    print("\nR@1 por categoría (test):")
    cats = sorted({c["cat"] for c in casos})
    print(f"{'':28s} " + " ".join(f"{k[:9]:>9s}" for k in cats))
    for t in tipos:
        _, _, _, cat = resumen(t, test_ranks[t], casos)
        print(f"{nombres[t]:28s} " + " ".join(f"{cat[k]:9.2f}" for k in cats))
    print("\nR2 con la corrección atenuada (lambda): ganancia frente a casos perdidos")
    for lam in sorted(curva):
        rk = curva[lam]
        r1 = sum(1 for c in casos if rk[c["id"]] == 1) / len(casos) * 100
        gana = sum(1 for c in casos if rk[c["id"]] == 1 and base[c["id"]] != 1)
        pierde = sum(1 for c in casos if rk[c["id"]] != 1 and base[c["id"]] == 1)
        p5 = sum(1 for c in casos if (base[c["id"]] or 99) <= 5 and (rk[c["id"]] or 99) > 5)
        print(f"  lambda={lam:.2f}  R@1 {r1:6.2f}  +{gana} / -{pierde}  (pierde top-5: {p5})")
    w = np.mean(pesos_R1, 0)
    print("\nR1: corrección media aprendida sobre cada señal (positivo = el manual la subestima):")
    for nme, v in sorted(zip(F_SIG, w), key=lambda x: x[1]):
        print(f"  {nme:16s} {v:+.3f}")
    destino = AQUI / "resultados" / f"rangos_particion_{SEMILLA}.json"
    destino.parent.mkdir(exist_ok=True)
    with open(destino, "w", encoding="utf-8") as fh:
        json.dump({t: test_ranks[t] for t in tipos}, fh)


if __name__ == "__main__":
    main(ARGS.entrada)
