"""Sonda (solo laboratorio): cuáles de los `except sqlite3.OperationalError: pass` de core/ saltan de verdad.

1) Inventario estático con `ast`: cada `try` cuyo handler captura OperationalError y solo hace `pass`.
2) Traza dinámica (`sys.settrace`) en un mundo sintético de la capa L (s7, |D| = 200, D∪I1, motor real):
   apertura de la base, búsquedas (pista c2 = sustantivos clave y c1 = ventana del contenido; `activos` y
   `profundo`; con y sin `modo_estricto`), canal 2 (`obtener_asociaciones_enriquecidas`) y dos sueños.
   Un sitio «salta» si una excepción pasa por una línea de su bloque `try`.
No toca el motor ni la base viva. Uso: python sonda_except_pass.py  → escribe INVENTARIO_EXCEPT_PASS.md
"""
import ast
import contextlib
import io
import json
import os
import pathlib
import shutil
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
CAPA_L = os.path.join(AQUI, "..", "paso3_agujas", "capa_L")
sys.path.insert(0, os.path.abspath(CAPA_L))
import laboratorio_capa_L as L  # noqa: E402

RAIZ = L.RAIZ
TMP = "/tmp/sonda_except"


def inventario():
    sitios = []
    for p in sorted(pathlib.Path(RAIZ, "core").rglob("*.py")):
        src = p.read_text(encoding="utf-8")
        for n in ast.walk(ast.parse(src)):
            if isinstance(n, ast.Try):
                for h in n.handlers:
                    nombre = ast.unparse(h.type) if h.type else "(todo)"
                    if "OperationalError" in nombre and all(isinstance(b, ast.Pass) for b in h.body):
                        sitios.append({"archivo": str(p.relative_to(RAIZ)), "handler": h.lineno,
                                       "ini": n.body[0].lineno, "fin": n.body[-1].end_lineno,
                                       "primera": src.splitlines()[n.body[0].lineno - 1].strip()[:90]})
    return sitios


def hijo():
    os.environ.update(L.BASE_ENV)
    shutil.rmtree(TMP, ignore_errors=True)
    os.makedirs(TMP)
    ruta = os.path.join(TMP, "DI1.db")
    L._run(["construir", 7, 200, "DI1", ruta, ruta + ".info.json"])
    m = L.mundo_completo(7, 200)
    reloj = L.lab.preparar_hijo("T", False, L.T0 + 10 ** 8)
    eventos = {}
    vivas = {}

    def traza(frame, ev, arg):
        if ev == "exception":
            f = frame.f_code.co_filename
            if "/core/" in f:
                clave = (f.split(RAIZ + "/")[-1], frame.f_lineno)
                k2 = (id(arg[1]), clave)
                if k2 not in vivas:
                    vivas[k2] = arg[1]
                    e = eventos.setdefault("%s:%d" % clave, {"n": 0, "tipo": arg[0].__name__,
                                                             "mensaje": str(arg[1])[:140]})
                    e["n"] += 1
        return traza

    from core.memory_store import SQLiteMemoryBioRAG
    import construir as c16
    sys.settrace(traza)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            cer = SQLiteMemoryBioRAG(db_path=ruta)
        rs = [r for r in m["recuerdos"] if r["conj"] == "D"][:120]
        for k, r in enumerate(rs):
            sk = " ".join(s for s in r["decl"]["sk"].split(",") if s)
            c1 = " ".join(r["contenido"].split()[:4]) if r["esc"] not in ("han", "jpn") else r["contenido"][:8]
            for pista in (sk, c1):
                for prof in ("activos", "profundo"):
                    with contextlib.redirect_stdout(io.StringIO()):
                        cer.buscar_por_frase(pista, profundidad=prof, limite=10, context_window=0,
                                             modo_estricto=(k % 5 == 0))
            if k % 10 == 0:
                vivas.clear()
        with contextlib.redirect_stdout(io.StringIO()):
            cer.obtener_asociaciones_enriquecidas([r["concepto"].lower() for r in rs[:60]])
        for _ in range(2):
            reloj.t += L.DIA
            c16.dormir(cer)
            vivas.clear()
        with contextlib.redirect_stdout(io.StringIO()):
            cer.cerrar_sistema()
    finally:
        sys.settrace(None)
    json.dump(eventos, open(os.path.join(TMP, "eventos.json"), "w"), ensure_ascii=False, indent=1)


def main():
    t0 = time.time()
    import subprocess
    e = dict(os.environ)
    e.update(L.BASE_ENV)
    e["HOME"] = os.path.join(TMP + "_home")
    os.makedirs(e["HOME"], exist_ok=True)
    p = subprocess.run([sys.executable, os.path.abspath(__file__), "hijo"], env=e, cwd=AQUI, capture_output=True,
                       text=True)
    if p.returncode != 0:
        sys.exit(p.stderr[-4000:])
    ev = json.load(open(os.path.join(TMP, "eventos.json")))
    sitios = inventario()
    filas = []
    for s in sitios:
        hits = {k: v for k, v in ev.items() if k.rsplit(":", 1)[0] == s["archivo"]
                and s["ini"] <= int(k.rsplit(":", 1)[1]) <= s["fin"]}
        filas.append((s, hits))
    L_ = ["# Inventario de los `except sqlite3.OperationalError: pass` de `core/` (sonda del 27-11)", "",
          "> Generado por `sonda_except_pass.py`. Estático: `ast` sobre `core/`. Dinámico: traza en un mundo sintético de "
          "la capa L (s7, |D| = 200, D∪I1, motor real; búsquedas c1/c2 en `activos` y `profundo`, 1 de cada 5 en modo "
          "estricto; canal 2; 2 sueños). **«No salta» solo quiere decir que no saltó en estos caminos**, no que nunca "
          "salte. No se tocó el motor. Duración: %d s." % (time.time() - t0), "",
          "| # | sitio (handler) | bloque try | primera línea del try | ¿saltó? | excepción (n) |", "|---|---|---|---|---|---|"]
    for i, (s, hits) in enumerate(filas, 1):
        txt = "; ".join("%s ×%d: %s" % (v["tipo"], v["n"], v["mensaje"].replace("|", "/")) for v in hits.values())
        L_.append("| %d | `%s:%d` | L%d–%d | `%s` | %s | %s |" % (i, s["archivo"], s["handler"], s["ini"], s["fin"],
                                                              s["primera"].replace("|", "/"),
                                                              "**sí**" if hits else "no", txt or "—"))
    n_si = sum(1 for _s, h in filas if h)
    L_ += ["", "**Total:** %d sitios; saltaron %d en esta sonda." % (len(filas), n_si), ""]
    open(os.path.join(AQUI, "INVENTARIO_EXCEPT_PASS.md"), "w").write("\n".join(L_))
    print("\n".join(L_))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "hijo":
        hijo()
    else:
        main()
