"""R-E0b: separa estáticamente las causas dentro de la señal PPMI (#13). Solo lectura, sin buscar ni dormir.

Sobre dos bases sintéticas ya construidas (D y D∪I0, brazo −H2 −4b, corte «medir») compara:
  1. la tabla `tokens` (token, freq, vector) y los vectores `nodos` de los conceptos de D;
  2. el vector de consulta `IndicesBioRAG.vector_query` de cada consulta en D, en D∪I0 y en D∪I0 con `n_docs`
     reemplazado por el de D (prueba de sustitución: si este último coincide con D, la única causa es `n_docs`).
`IndicesBioRAG` abre la base en modo solo lectura (`connect_readonly`).

Uso:  python residual_re0b.py /tmp/h2_re0b/D.db /tmp/h2_re0b/DI0.db SEMILLA N_D
"""
import hashlib
import json
import os
import sqlite3
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import laboratorio_h2 as lab  # noqa: E402,F401  (pone RAIZ en sys.path)
import mundo_sintetico as ms  # noqa: E402
import numpy as np  # noqa: E402
from core.ppmi_hybrid_search import IndicesBioRAG, _tokenizar  # noqa: E402


def sha_tabla(ruta, sql):
    con = sqlite3.connect("file:%s?mode=ro" % ruta, uri=True)
    h = hashlib.sha256()
    filas = sorted(con.execute(sql).fetchall(), key=repr)
    for r in filas:
        h.update(repr(r).encode())
    con.close()
    return h.hexdigest()[:16], len(filas)


def main(rD, rI, semilla, n_D):
    m = ms.generar(int(semilla), int(n_D))
    qs = lab.consultas(m)
    out = {"tokens": {"D": sha_tabla(rD, "SELECT token, freq, vector FROM tokens"),
                      "DI0": sha_tabla(rI, "SELECT token, freq, vector FROM tokens")}}
    en_D = tuple(sorted(r["concepto"] for r in m["recuerdos"] if r["conj"] == "D"))
    q = "SELECT concepto, vector FROM nodos WHERE concepto IN (%s)" % ",".join("?" * len(en_D))
    for w, r in (("D", rD), ("DI0", rI)):
        con = sqlite3.connect("file:%s?mode=ro" % r, uri=True)
        h = hashlib.sha256()
        for row in sorted(con.execute(q, en_D).fetchall()):
            h.update(repr(row).encode())
        out.setdefault("nodos_D", {})[w] = h.hexdigest()[:16]
        con.close()
    iD, iI = IndicesBioRAG(rD), IndicesBioRAG(rI)
    out["n_docs"] = {"D": iD.n_docs, "DI0": iI.n_docs}
    con_tok, dif, dif_sust, ejemplos = 0, 0, 0, []
    for x in qs:
        toks = _tokenizar(x["q"])
        vD, vI = iD.vector_query(toks), iI.vector_query(toks)
        if not np.any(vD):
            continue
        con_tok += 1
        n_orig = iI.n_docs
        iI.n_docs = iD.n_docs
        vS = iI.vector_query(toks)
        iI.n_docs = n_orig
        d = not np.array_equal(vD, vI)
        dif += d
        dif_sust += not np.array_equal(vD, vS)
        if d and len(ejemplos) < 3:
            cos = float(vD @ vI / (np.linalg.norm(vD) * np.linalg.norm(vI)))
            ejemplos.append({"esc": x["esc"], "n_tokens": len(set(toks)), "coseno_vD_vDI0": round(cos, 8)})
    out["consultas"] = len(qs)
    out["consultas_con_vector_ppmi"] = con_tok
    out["consultas_con_vector_ppmi_por_escritura"] = {
        e: sum(1 for x in qs if x["esc"] == e and np.any(iD.vector_query(_tokenizar(x["q"])))) for e in ms.ESCRITURAS}
    out["vector_consulta_distinto_D_vs_DI0"] = dif
    out["vector_consulta_distinto_tras_sustituir_n_docs"] = dif_sust
    out["ejemplos"] = ejemplos
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:])
