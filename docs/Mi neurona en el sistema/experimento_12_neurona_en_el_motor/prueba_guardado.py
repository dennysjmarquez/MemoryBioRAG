"""Prueba de punta a punta: guardar 5 recuerdos nuevos con la neurona apagada y encendida.

Uso:  python prueba_guardado.py SNAPSHOT
      Crea dos COPIAS en /tmp/e12/ (apagada.db y encendida.db). El SNAPSHOT nunca se escribe.

Hace lo mismo que la herramienta `aprender` del MCP (core/mcp_server/write.py):
percibir_corto_plazo → auto_vincular → vincular_por_sinonimos. Luego compara:
  1. ¿Nacen exactamente las mismas sinapsis? (la neurona no crea ni corta)
  2. Pesos por tipo: a mano contra neurona.
  3. Tiempo de cada guardado.
  4. "Alcance": en cuántos vecinos el recuerdo nuevo queda entre sus 6 de mayor peso (los que
     usa la expansión por el grafo).
Escribe ../experimento_12_neurona_en_el_motor/resultados/prueba_guardado.json
"""
import json
import os
import shutil
import sqlite3
import statistics as st
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.abspath(os.path.join(AQUI, "..", "..", ".."))
TMP = "/tmp/e12"

MEM = [
    ("neurona_asociativa_cableada_motor",
     "La neurona asociativa de BioRAG ya decide el peso con que nace cada sinapsis en el motor. "
     "Viene calibrada de fabrica y no aprende del corpus.", "neurona, sinapsis, hipocampo, peso"),
    ("qa_baseline_antes_cableado",
     "Baseline QA oficial antes de cablear la neurona: Recall@5 100%, Recall@1 91.89%, MRR 0.950, "
     "cero falsos positivos.", "qa, baseline, recall, evaluacion"),
    ("hormiguita_gemini_cuarentena_revision",
     "La hormiguita usa gemini-2.5-flash para revisar sinapsis y mandar a cuarentena las que no tienen "
     "que ver.", "hormiguita, gemini, cuarentena"),
    ("athena_identidad_reflexion_octubre",
     "Athena reflexiona sobre su identidad y su relacion con Dennys, la familia sintetica y el oraculo.",
     "athena, identidad, dennys"),
    ("plugin_opencode_sesion_idle",
     "El plugin de OpenCode guarda la memoria al detectar session.idle, sin contar ediciones.",
     "plugin, opencode, session"),
]

HIJO = r'''
import json, os, sys, time
sys.path.insert(0, sys.argv[3])
from core.memory_store import SQLiteMemoryBioRAG
from core.sinapsis import auto_vincular, vincular_por_sinonimos
c = SQLiteMemoryBioRAG(db_path=sys.argv[1])
out = {}
for k, cont, syn in json.loads(sys.argv[2]):
    t = time.time()
    c.percibir_corto_plazo(k, cont, syn, "General", None)
    auto_vincular(c, k, cont)
    vincular_por_sinonimos(c, k, syn)
    out[k] = {"segundos": round(time.time() - t, 3),
              "sinapsis": c.cursor.execute("SELECT destino, tipo, peso FROM sinapsis WHERE origen=?", (k,)).fetchall()}
print(json.dumps(out))
'''


def alcance(db, nodos, k=6):
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    dentro = total = 0
    for a in nodos:
        for (b,) in c.execute("SELECT destino FROM sinapsis WHERE origen=?", (a,)).fetchall():
            filas = c.execute("SELECT v, p, rid FROM (SELECT destino v, peso p, rowid rid FROM sinapsis WHERE origen=? "
                              "UNION ALL SELECT origen, peso, rowid FROM sinapsis WHERE destino=?) "
                              "ORDER BY p DESC, rid DESC", (b, b)).fetchall()
            top = []
            for v, _, _ in filas:
                if v not in top:
                    top.append(v)
                if len(top) >= k:
                    break
            dentro += a in top
            total += 1
    c.close()
    return dentro, total


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    os.makedirs(TMP, exist_ok=True)
    res = {}
    for modo, flag in (("apagada", "0"), ("encendida", "1")):
        db = os.path.join(TMP, f"{modo}.db")
        for s in ("", "-wal", "-shm"):
            if os.path.exists(db + s):
                os.remove(db + s)
        shutil.copyfile(sys.argv[1], db)
        env = dict(os.environ, BIORAG_NEURONA_ASOCIATIVA=flag)
        p = subprocess.run([sys.executable, "-c", HIJO, db, json.dumps(MEM), RAIZ], env=env,
                           capture_output=True, text=True, check=True)
        res[modo] = json.loads(p.stdout.strip().splitlines()[-1])
        res[modo + "_alcance"] = alcance(db, [m[0] for m in MEM])
    out = {"recuerdos": {}}
    for k, _, _ in MEM:
        a = {(d, t): p for d, t, p in res["apagada"][k]["sinapsis"]}
        e = {(d, t): p for d, t, p in res["encendida"][k]["sinapsis"]}
        tipos = {}
        for (d, t) in a:
            tipos.setdefault(t, ([], []))
            tipos[t][0].append(a[(d, t)])
            tipos[t][1].append(e.get((d, t), float("nan")))
        out["recuerdos"][k] = {
            "mismas_sinapsis": set(a) == set(e), "n": len(a),
            "segundos_apagada": res["apagada"][k]["segundos"], "segundos_encendida": res["encendida"][k]["segundos"],
            "por_tipo": {t: {"n": len(x), "mano_mediana": st.median(x), "neurona_mediana": round(st.median(y), 3),
                             "neurona_min": min(y), "neurona_max": max(y)} for t, (x, y) in tipos.items()}}
    out["alcance_apagada"] = res["apagada_alcance"]
    out["alcance_encendida"] = res["encendida_alcance"]
    os.makedirs(os.path.join(AQUI, "resultados"), exist_ok=True)
    json.dump(out, open(os.path.join(AQUI, "resultados", "prueba_guardado.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    for k, v in out["recuerdos"].items():
        print(f"{k}: mismas sinapsis {v['mismas_sinapsis']} ({v['n']}) · "
              f"{v['segundos_apagada']}s apagada / {v['segundos_encendida']}s encendida")
        for t, d in v["por_tipo"].items():
            print(f"   {t:20s} n={d['n']:3d}  a mano {d['mano_mediana']:.2f}  neurona {d['neurona_mediana']:.3f} "
                  f"({d['neurona_min']:.3f}–{d['neurona_max']:.3f})")
    print("alcance (queda entre los 6 de mayor peso del vecino): apagada %d/%d · encendida %d/%d"
          % (*out["alcance_apagada"], *out["alcance_encendida"]))


if __name__ == "__main__":
    main()
