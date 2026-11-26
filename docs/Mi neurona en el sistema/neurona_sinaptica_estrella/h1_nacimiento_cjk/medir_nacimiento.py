"""H1: ¿las reglas de nacimiento de sinapsis ven chino y japonés? Medición Antes/Después en UD PUD.

Uso:
    python medir_nacimiento.py construir <raiz_motor> <lg> <particion> <ruta_db>   (hijo)
    python medir_nacimiento.py medir <raiz_motor> <etiqueta> <particion> [lg ...]  (padre)

- <raiz_motor>: carpeta del repositorio cuyo `core/` se usa (worktree del Antes o el repo del Después).
- <particion>: "desarrollo" (~40 % de los documentos) o "sellado" (~60 %), por sha256 del documento.
- Mundo: las frases de esos documentos guardadas con el motor real (`guardar` del exp. 16), sueño cada 50
  y al final; mismo entorno que el Paso 2b (WordNet apagado, PYTHONHASHSEED=18).
- Relación real, solo para auditar: dos frases del mismo documento.
Escribe resultados/<etiqueta>_<particion>.json con las métricas y la tabla de sinapsis completa.
"""
import contextlib
import glob
import hashlib
import io
import json
import os
import subprocess
import sys
import time
from collections import Counter

AQUI = os.path.dirname(os.path.abspath(__file__))
EXP16 = os.path.abspath(os.path.join(AQUI, "..", "..", "experimento_16_protocolo_ns1_sintetico"))
PUD = "/tmp/pud"
TMP = "/tmp/h1_nacimiento"
IDIOMAS = {"es": "Spanish", "en": "English", "zh": "Chinese", "ja": "Japanese"}
CADA = 50
BASE_ENV = {"BIORAG_WORDNET_ENABLED": "0", "BIORAG_NO_LOG": "1", "PYTHONHASHSEED": "18"}


def leer(lg):
    f = glob.glob(os.path.join(PUD, "UD_%s-PUD-master" % IDIOMAS[lg], "*.conllu"))[0]
    doc, sid, out = None, None, []
    for line in open(f, encoding="utf-8"):
        if line.startswith("# newdoc id"):
            doc = line.split("=", 1)[1].strip()
        elif line.startswith("# sent_id"):
            sid = line.split("=", 1)[1].strip()
        elif line.startswith("# text ="):
            out.append({"concepto": sid, "doc": doc, "contenido": line.split("=", 1)[1].strip()})
    return out


def particion(doc):
    return "desarrollo" if int(hashlib.sha256(("h1|" + doc).encode()).hexdigest(), 16) % 5 < 2 else "sellado"


def frases(lg, part):
    return [f for f in leer(lg) if particion(f["doc"]) == part]


# ------------------------------------------------------------------ hijo
def hijo_construir(raiz, lg, part, ruta):
    sys.path[:0] = [raiz, EXP16]
    import core  # noqa: F401
    assert os.path.dirname(os.path.abspath(core.__file__)) == os.path.join(os.path.abspath(raiz), "core"), core.__file__
    import construir as c16
    assert ruta.startswith("/tmp/")
    for ext in ("", "-wal", "-shm"):
        if os.path.exists(ruta + ext):
            os.remove(ruta + ext)
    t0 = time.time()
    cer = c16.abrir(ruta)
    lote = frases(lg, part)
    for k, f in enumerate(lote, 1):
        with contextlib.redirect_stdout(io.StringIO()):
            c16.guardar(cer, {"concepto": f["concepto"], "contenido": f["contenido"], "syn": "",
                              "cat": "General", "dims": {}, "sk": ""})
        if k % CADA == 0:
            c16.dormir(cer)
    c16.dormir(cer)
    with contextlib.redirect_stdout(io.StringIO()):
        cer.conn.commit()
        cer.cerrar_sistema()
    import sqlite3
    con = sqlite3.connect(ruta)
    con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    con.close()
    json.dump({"segundos": round(time.time() - t0, 1)}, open(ruta + ".t.json", "w"))


# ------------------------------------------------------------------ análisis
def analizar(ruta, lg, part):
    import sqlite3
    fr = frases(lg, part)
    doc_de = {f["concepto"].lower().replace(" ", "_"): f["doc"] for f in fr}
    con = sqlite3.connect(ruta)
    filas = sorted(con.execute("SELECT origen, destino, tipo, ROUND(peso, 4) FROM sinapsis").fetchall())
    con.close()
    tipos = Counter(t for _, _, t, _ in filas)
    pares = {tuple(sorted((o, d))) for o, d, _, _ in filas if o in doc_de and d in doc_de and o != d}
    mismo = sum(1 for a, b in pares if doc_de[a] == doc_de[b])
    n = len(doc_de)
    tam = Counter(doc_de.values())
    azar = sum(k * (k - 1) / 2 for k in tam.values()) / (n * (n - 1) / 2)
    grado = Counter()
    for a, b in pares:
        grado[a] += 1
        grado[b] += 1
    return {
        "recuerdos": n, "filas": len(filas), "tipos": dict(tipos), "pares": len(pares),
        "pares_mismo_doc": mismo, "precision_mismo_doc": round(mismo / len(pares), 4) if pares else None,
        "tasa_azar": round(azar, 5),
        "lift": round((mismo / len(pares)) / azar, 2) if pares else None,
        "grado_medio": round(2 * len(pares) / n, 3), "grado_max": max(grado.values()) if grado else 0,
        "nodos_con_sinapsis": len(grado),
        "tabla": [list(x) for x in filas],
    }


def padre_medir(raiz, etiqueta, part, lgs):
    os.makedirs(TMP, exist_ok=True)
    os.makedirs(os.path.join(AQUI, "resultados"), exist_ok=True)
    out = {"etiqueta": etiqueta, "particion": part, "raiz": os.path.abspath(raiz),
           "commit": subprocess.run(["git", "-C", raiz, "rev-parse", "HEAD"], capture_output=True,
                                    text=True).stdout.strip(),
           "diff_core": subprocess.run(["git", "-C", raiz, "diff", "--stat", "HEAD", "--", "core"],
                                       capture_output=True, text=True).stdout.strip(),
           "idiomas": {}}
    for lg in lgs:
        ruta = os.path.join(TMP, "%s_%s_%s.db" % (etiqueta, part, lg))
        e = dict(os.environ)
        e["HOME"] = os.path.join(TMP, "home")
        e.update(BASE_ENV)
        p = subprocess.run([sys.executable, os.path.abspath(__file__), "construir", raiz, lg, part, ruta],
                           env=e, cwd=AQUI, capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError(p.stderr[-3000:])
        r = analizar(ruta, lg, part)
        r["segundos"] = json.load(open(ruta + ".t.json"))["segundos"]
        out["idiomas"][lg] = r
        print(lg, {k: v for k, v in r.items() if k != "tabla"}, flush=True)
    sal = os.path.join(AQUI, "resultados", "%s_%s.json" % (etiqueta, part))
    json.dump(out, open(sal, "w"), ensure_ascii=False, indent=1)
    print("->", sal)


if __name__ == "__main__":
    if sys.argv[1] == "construir":
        hijo_construir(*sys.argv[2:6])
    elif sys.argv[1] == "medir":
        padre_medir(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5:] or list(IDIOMAS))
