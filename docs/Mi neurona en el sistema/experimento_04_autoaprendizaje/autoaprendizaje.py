"""Paso 3 del experimento 04: la neurona aprende SOLA con el examen que la base se fabricó.

Nadie le dice a la neurona qué falló: el examen autogenerado ("tapar y adivinar")
trae la respuesta adentro. El QA oficial (921 casos) hace de "búsquedas de la
gente": la neurona NUNCA ve sus respuestas; solo se usan al final para poner la nota.

Dos juegos de pesos (lo que pidió Dennys):
  - pesos base (los de `scoring.py`, fijos): el ancla y la referencia del piso.
  - corrección aprendida: arranca en 0 (= pesos base exactos) y se mueve con el error.

Dos reglas de seguridad:
  - PISO: unos pesos nuevos solo se aceptan si en el examen ninguna categoría queda
    por debajo de lo que logran los pesos base.
  - TECHO (anti-memorización): el examen se parte por NODO en "estudio" (80 %) y
    "guardia" (20 %, la neurona nunca entrena con ella). Si en estudio sube y en
    guardia no, está memorizando y se rechaza.

Modos:
  A "sueño"  : entrena de una vez con todo el examen de estudio (parada temprana
               con la guardia) y deja fijos los pesos ganadores.
  B "en vivo": recorre las consultas del QA una por una, en orden aleatorio, como
               si las mandara la gente. Antes de responder cada una: si hay duda
               (el #1 y el #2 casi empatados), repasa las preguntas del examen cuyos
               nodos aparecen en esa búsqueda y que hoy fallan, da unos pasos de
               aprendizaje, comprueba piso y techo, y responde con los pesos
               aceptados. Mide cuánto tarda.

Uso (desde la raíz del repo):
    python "docs/Mi neurona en el sistema/experimento_04_autoaprendizaje/autoaprendizaje.py" --semilla 7
Solo numpy. No toca el motor ni ninguna DB.
"""
import argparse
import collections
import json
import sys
import time
from pathlib import Path

import numpy as np

AQUI = Path(__file__).resolve().parent
EXP01 = AQUI.parent / "experimento_01_pesos_aprendidos"
sys.path.insert(0, str(EXP01))
_argv, sys.argv = sys.argv, [sys.argv[0]]
import entrenar_neurona as en  # noqa: E402
import escala  # noqa: E402

ESCALA_ORIGINAL = en.logit
sys.argv = _argv

ap = argparse.ArgumentParser()
ap.add_argument("--semilla", type=int, default=7)
ap.add_argument("--examen", nargs="+", default=[str(AQUI / "datos" / "pools_examen_p0.jsonl.gz"),
                                                 str(AQUI / "datos" / "pools_examen_p1.jsonl.gz")])
ap.add_argument("--qa", default=str(EXP01 / "datos" / "pools_semilla1.jsonl.gz"))
ap.add_argument("--modos", default="A,B")
ap.add_argument("--piso5", action="store_true",
                help="el piso exige además que ninguna categoría pierda aciertos en el top-5")
ap.add_argument("--ancla", type=float, default=0.0,
                help="ancla de escala: castiga λ·media(corrección²) para no inflar los scores")
ap.add_argument("--escala", choices=["g", "logit"], default="g",
                help="g = los matches exactos no se recortan (por defecto); logit = la de exp01")
ARGS = ap.parse_args()
if ARGS.escala == "g":
    en.logit = escala.g
rng = np.random.default_rng(ARGS.semilla)
en.rng = np.random.default_rng(ARGS.semilla)


# ───────────────────────── datos ─────────────────────────
def cargar_examen(paths):
    casos = []
    for p in paths:
        casos += en.cargar(p)
    return casos


class Plano:
    """Todos los pools de un conjunto de casos en una sola matriz, para evaluar en ms."""

    def __init__(self, casos):
        casos = [c for c in casos if len(c["X"]) > 0]
        self.casos = casos
        self.X = np.vstack([c["X"] for c in casos])
        self.base = np.concatenate([c["base"] for c in casos])
        n = np.array([len(c["X"]) for c in casos])
        self.off = np.concatenate([[0], np.cumsum(n)[:-1]])
        self.seg = np.repeat(np.arange(len(casos)), n)
        self.loc = np.arange(len(self.X)) - np.repeat(self.off, n)
        self.y = np.array([c["y"] for c in casos])
        self.ok = self.y >= 0
        self.ygl = np.where(self.ok, self.off + np.maximum(self.y, 0), 0)
        self.cat = np.array([c["cat"] for c in casos])

    def rangos(self, s):
        sy = s[self.ygl][self.seg]
        yl = np.maximum(self.y, 0)[self.seg]
        delante = (s > sy) | ((s == sy) & (self.loc < yl))
        r = np.add.reduceat(delante.astype(np.int32), self.off) + 1
        return np.where(self.ok, r, 10 ** 6)


def info_escala(m, P):
    """¿Cuánto mueve la neurona la escala? |corrección| media en el top-5 y % de top-1 que pasa de .95."""
    sb, sm = P.base, puntuar_plano(m, P)
    c = sm - sb
    top5 = np.concatenate([o + np.argsort(-sm[o:e], kind="stable")[:5]
                           for o, e in zip(P.off, np.append(P.off[1:], len(sm))) if e > o])
    top1 = np.array([o + int(np.argmax(sm[o:e])) for o, e in zip(P.off, np.append(P.off[1:], len(sm))) if e > o])
    sat = np.mean([escala.g_inv(z) > .95 for z in sm[top1]]) * 100
    sat0 = np.mean([escala.g_inv(z) > .95 for z in sb[[o + int(np.argmax(sb[o:e])) for o, e in zip(P.off, np.append(P.off[1:], len(sb))) if e > o]]]) * 100
    return f"|corr| top5 {np.abs(c[top5]).mean():.2f}  top1>.95: {sat:.0f}% (base {sat0:.0f}%)"


def puntuar_plano(m, P):
    if m.tipo == "M0":
        return P.base
    if m.tipo == "R1":
        return P.base + P.X @ m.p["w"]
    if m.tipo == "R2":
        return P.base + np.tanh(P.X @ m.p["W"].T + m.p["b"]) @ m.p["v"]
    raise ValueError(m.tipo)


def paso_plano(m, P, lr=.03, l2=1e-3):
    """Un paso de aprendizaje (softmax por consulta + Adam) sobre TODOS los pools de P a la vez."""
    ok = P.ok & (np.diff(np.append(P.off, len(P.X))) > 1)
    if m.tipo == "R1":
        s = P.base + P.X @ m.p["w"]
    else:
        H = np.tanh(P.X @ m.p["W"].T + m.p["b"])
        s = P.base + H @ m.p["v"]
    mx = np.maximum.reduceat(s, P.off)[P.seg]
    e = np.exp(s - mx)
    pr = e / np.add.reduceat(e, P.off)[P.seg]
    d = pr * ok[P.seg]
    d[P.ygl[ok]] -= 1.0
    n = max(int(ok.sum()), 1)
    if ARGS.ancla > 0:
        # ancla de escala: la corrección debe ser pequeña (los umbrales del motor son absolutos)
        d = d + 2 * ARGS.ancla * (s - P.base) * n / len(s)
    if m.tipo == "R1":
        grads = {"w": P.X.T @ d}
    else:
        dH = np.outer(d, m.p["v"]) * (1 - H ** 2)
        grads = {"v": H.T @ d, "W": dH.T @ P.X, "b": dH.sum(0)}
    m.t += 1
    for k in m.p:
        gk = grads[k] / n + l2 * m.p[k]
        m.m[k] = .9 * m.m[k] + .1 * gk
        m.s[k] = .999 * m.s[k] + .001 * gk ** 2
        mh = m.m[k] / (1 - .9 ** m.t)
        sh = m.s[k] / (1 - .999 ** m.t)
        m.p[k] -= lr * mh / (np.sqrt(sh) + 1e-8)


def r1_por_cat(r, P):
    out = {}
    for k in sorted(set(P.cat)):
        mk = P.cat == k
        out[k] = int((r[mk] == 1).sum())
    out["_total"] = int((r == 1).sum())
    return out


def r5_por_cat(r, P):
    out = {k: int((r[P.cat == k] <= 5).sum()) for k in sorted(set(P.cat))}
    out["_total"] = int((r <= 5).sum())
    return out


def respeta_piso(r, P, piso):
    """Ninguna categoría con menos aciertos #1 (y, con --piso5, top-5) que los pesos base."""
    a = r1_por_cat(r, P)
    if not all(a[k] >= piso[k] for k in piso):
        return False
    if ARGS.piso5:
        b = r5_por_cat(r, P)
        return all(b[k] >= piso5[k] for k in piso5)
    return True


def copiar(m):
    n = en.Modelo(m.tipo, len(en.F_SIG), 6)
    n.p = {k: v.copy() for k, v in m.p.items()}
    n.m = {k: v.copy() for k, v in m.m.items()}
    n.s = {k: v.copy() for k, v in m.s.items()}
    n.t = m.t
    return n


def nota(nombre, r, rb, P, extra=""):
    n = len(P.casos)
    r1 = (r == 1).mean() * 100
    r5 = (r <= 5).mean() * 100
    gana = int(((r == 1) & (rb != 1)).sum())
    pierde = int(((r != 1) & (rb == 1)).sum())
    p5 = int(((rb <= 5) & (r > 5)).sum())
    cats = r1_por_cat(r, P)
    tot = collections.Counter(P.cat)
    txt = " ".join(f"{k[:9]}={cats[k] / tot[k] * 100:5.1f}" for k in sorted(tot))
    print(f"  {nombre:34s} R@1 {r1:6.2f}  R@5 {r5:6.2f}  +{gana:<3d}/-{pierde:<3d} (sale top5: {p5}) {extra}")
    print(f"  {'':34s} {txt}")
    return dict(r1=r1, r5=r5, gana=gana, pierde=pierde, sale_top5=p5,
                por_cat={k: cats[k] / tot[k] * 100 for k in tot})


# ───────────────────────── preparar ─────────────────────────
t0 = time.time()
examen = cargar_examen(ARGS.examen)
qa = en.cargar(ARGS.qa)
nodos = sorted({c["exp"] for c in examen})
rng.shuffle(nodos)
guardia_nodos = set(nodos[: len(nodos) // 5])
estudio = [c for c in examen if c["exp"] not in guardia_nodos]
guardia = [c for c in examen if c["exp"] in guardia_nodos]
PE, PG, PQ = Plano(estudio), Plano(guardia), Plano(qa)
PX = Plano(examen)  # examen completo: aquí se mide el PISO
print(f"examen: {len(examen)} preguntas ({len(estudio)} estudio / {len(guardia)} guardia, por nodo)  "
      f"| QA (solo nota): {len(qa)}  | carga {time.time() - t0:.0f}s")

M0 = en.Modelo("M0", len(en.F_SIG), 6)
rb_X, rb_G, rb_Q = PX.rangos(PX.base), PG.rangos(PG.base), PQ.rangos(PQ.base)
piso = r1_por_cat(rb_X, PX)
piso5 = r5_por_cat(rb_X, PX)
print(f"pesos base en el examen: R@1 {np.mean(rb_X == 1) * 100:.2f}  (estudio {np.mean(PE.rangos(PE.base) == 1) * 100:.2f}"
      f" / guardia {np.mean(rb_G == 1) * 100:.2f})   en el QA: R@1 {np.mean(rb_Q == 1) * 100:.2f}")
salida = {"semilla": ARGS.semilla, "piso5": ARGS.piso5, "escala": ARGS.escala, "ancla": ARGS.ancla, "n_examen": len(examen), "n_qa": len(qa)}
print()
print("NOTA EN EL QA (las búsquedas de la gente; la neurona nunca vio sus respuestas)")
salida["M0"] = nota("pesos base (hoy)", rb_Q, rb_Q, PQ)


def guardar_pesos(m, etiqueta):
    """Pesos aprendidos (la corrección sobre los pesos base) para probarlos en el motor real."""
    d = AQUI / "resultados" / "pesos"
    d.mkdir(parents=True, exist_ok=True)
    np.savez(d / f"{etiqueta}_semilla{ARGS.semilla}{'_piso5' if ARGS.piso5 else ''}{'_logit' if ARGS.escala == 'logit' else ''}{f'_ancla{ARGS.ancla:g}' if ARGS.ancla > 0 else ''}.npz",
             tipo=m.tipo, F_SIG=np.array(en.F_SIG), escala=ARGS.escala, **m.p)


salida["rangos_qa"] = {"M0": {c["id"]: int(x) for c, x in zip(PQ.casos, rb_Q)}}


# ───────────────────────── modo A: sueño ─────────────────────────
def modo_sueno(tipo, pasos=600, cada=10, lr=.03, l2=1e-3):
    m = en.Modelo(tipo, len(en.F_SIG), 6)
    mejor, mejor_g, historia = None, (rb_G == 1).sum(), []
    for paso in range(1, pasos + 1):
        paso_plano(m, PE, lr=lr, l2=l2)
        if paso % cada == 0:
            rg = PG.rangos(puntuar_plano(m, PG))
            re_ = PE.rangos(puntuar_plano(m, PE))
            rx = PX.rangos(puntuar_plano(m, PX))
            g, e = int((rg == 1).sum()), int((re_ == 1).sum())
            ok_piso = respeta_piso(rx, PX, piso)
            historia.append((paso, e, g, ok_piso))
            if ok_piso and g > mejor_g:
                mejor, mejor_g = copiar(m), g
    return mejor, historia


if "A" in ARGS.modos:
    for tipo in ("R1", "R2"):
        t1 = time.time()
        m, hist = modo_sueno(tipo)
        dur = time.time() - t1
        if m is None:
            print(f"  A-sueño {tipo}: ningún punto respetó el piso y mejoró la guardia -> se quedan los pesos base")
            salida[f"A_{tipo}"] = None
            continue
        rq = PQ.rangos(puntuar_plano(m, PQ))
        rg = PG.rangos(puntuar_plano(m, PG))
        guardar_pesos(m, f"A_{tipo}")
        salida.setdefault("rangos_qa", {})[f"A_{tipo}"] = {c["id"]: int(x) for c, x in zip(PQ.casos, rq)}
        mejor_paso = max((h for h in hist if h[3]), key=lambda h: h[2])[0]
        salida[f"A_{tipo}"] = nota(f"A sueño {tipo} (paso {mejor_paso})", rq, rb_Q, PQ,
                                   f"| guardia {np.mean(rg == 1) * 100:.2f} vs base {np.mean(rb_G == 1) * 100:.2f} | {dur:.0f}s | {info_escala(m, PQ)}")
        salida[f"A_{tipo}"]["historia"] = hist


# ───────────────────────── modo B: en vivo ─────────────────────────
def modo_vivo(tipo, tau=0.25, k_vecinos=10, pasos=3, replay=48, lr=.02, l2=1e-3, margen_memo=3.0):
    """Cada consulta del QA llega como una búsqueda de la gente.

    campeón = los pesos que responden.  retador = los que siguen aprendiendo.
    Antes de responder: si hay duda, el retador repasa las preguntas del examen
    cuyos nodos aparecen en esta búsqueda y que hoy fallan (+ un repaso al azar
    para no olvidar). Si el retador cumple PISO (ninguna categoría del examen
    por debajo de los pesos base) y la guardia no empeora frente al campeón,
    pasa a ser el campeón. Si se dispara la memorización (estudio sube y
    guardia no), el retador vuelve al campeón.
    """
    campeon = en.Modelo(tipo, len(en.F_SIG), 6)
    retador = copiar(campeon)
    por_nodo = collections.defaultdict(list)
    for c in estudio:
        if c["y"] >= 0 and len(c["X"]) > 1:
            por_nodo[c["exp"]].append(c)
    tr_all = [c for cs in por_nodo.values() for c in cs]
    g_camp = int((rb_G == 1).sum())
    brecha0 = np.mean(PE.rangos(PE.base) == 1) * 100 - np.mean(rb_G == 1) * 100
    orden = rng.permutation(len(PQ.casos))
    rangos = np.zeros(len(PQ.casos), dtype=int)
    stats = collections.Counter()
    tiempos = []
    for qi in orden:
        c = PQ.casos[qi]
        t1 = time.perf_counter()
        s, _ = campeon.score(c)
        o = np.argsort(-s, kind="stable")
        if len(s) > 1 and (s[o[0]] - s[o[1]]) < tau:
            stats["duda"] += 1
            vecinos = [c2 for idx in o[:k_vecinos] for c2 in por_nodo.get(c["nombres"][idx], [])]
            fallan = [c2 for c2 in vecinos if en.rango(retador.score(c2)[0], c2["y"]) != 1]
            if fallan:
                stats["con_fallos_cerca"] += 1
                rep = [tr_all[i] for i in rng.choice(len(tr_all), size=min(replay, len(tr_all)), replace=False)]
                lote = Plano(fallan + rep)
                for _ in range(pasos):
                    paso_plano(retador, lote, lr=lr, l2=l2)
                rx = PX.rangos(puntuar_plano(retador, PX))
                rg = PG.rangos(puntuar_plano(retador, PG))
                g = int((rg == 1).sum())
                if respeta_piso(rx, PX, piso) and g >= g_camp and (rx == 1).sum() > (PX.rangos(puntuar_plano(campeon, PX)) == 1).sum():
                    campeon, g_camp = copiar(retador), g
                    stats["ascensos"] += 1
                else:
                    re_ = PE.rangos(puntuar_plano(retador, PE))
                    brecha = np.mean(re_ == 1) * 100 - np.mean(rg == 1) * 100
                    if brecha > brecha0 + margen_memo:
                        retador = copiar(campeon)
                        stats["reinicios_por_memorizar"] += 1
                s, _ = campeon.score(c)
        tiempos.append((time.perf_counter() - t1) * 1000)
        rangos[qi] = en.rango(s, c["y"])
    r_final = PQ.rangos(puntuar_plano(campeon, PQ))
    return rangos, r_final, stats, tiempos, campeon


if "B" in ARGS.modos:
    # los pools del QA necesitan los NOMBRES de sus candidatos para buscar el examen cercano
    import gzip
    nombres = {}
    with gzip.open(ARGS.qa, "rt", encoding="utf-8") as fh:
        for l in fh:
            r = json.loads(l)
            nombres[r["id"]] = [k["c"] for k in r["cands"]]
    for c in PQ.casos:
        c["nombres"] = nombres[c["id"]]
    for tipo in ("R1", "R2"):
        t1 = time.time()
        r_vivo, r_final, st, tms, m = modo_vivo(tipo)
        tms = np.array(tms)
        extra = (f"| duda {st['duda']}  con fallos cerca {st['con_fallos_cerca']}  ascensos {st['ascensos']}  "
                 f"reinicios {st['reinicios_por_memorizar']} | ms/consulta mediana {np.median(tms):.1f} p95 {np.percentile(tms, 95):.1f} max {tms.max():.0f}")
        salida[f"B_{tipo}_vivo"] = nota(f"B en vivo {tipo} (respuesta en el momento)", r_vivo, rb_Q, PQ, extra)
        salida[f"B_{tipo}_final"] = nota(f"B en vivo {tipo} (pesos al final)", r_final, rb_Q, PQ)
        salida[f"B_{tipo}_vivo"]["stats"] = dict(st)
        guardar_pesos(m, f"B_{tipo}_final")
        salida["rangos_qa"][f"B_{tipo}_vivo"] = {c["id"]: int(x) for c, x in zip(PQ.casos, r_vivo)}
        salida["rangos_qa"][f"B_{tipo}_final"] = {c["id"]: int(x) for c, x in zip(PQ.casos, r_final)}
        salida[f"B_{tipo}_vivo"]["ms"] = dict(mediana=float(np.median(tms)), p95=float(np.percentile(tms, 95)),
                                            max=float(tms.max()))
        if tipo == "R1":
            print("  corrección aprendida por aguja (R1, + = el peso base la subestimaba):")
            print("   " + "  ".join(f"{n}={v:+.2f}" for n, v in sorted(zip(en.F_SIG, m.p["w"]), key=lambda x: x[1])))
            salida["B_R1_pesos"] = dict(zip(en.F_SIG, map(float, m.p["w"])))

dest = AQUI / "resultados" / f"autoaprendizaje_{ARGS.semilla}{'_piso5' if ARGS.piso5 else ''}{'_logit' if ARGS.escala == 'logit' else ''}{f'_ancla{ARGS.ancla:g}' if ARGS.ancla > 0 else ''}.json"
dest.parent.mkdir(exist_ok=True)
with open(dest, "w", encoding="utf-8") as fh:
    json.dump(salida, fh, ensure_ascii=False, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))
print(f"\n-> {dest}  ({time.time() - t0:.0f}s)")
