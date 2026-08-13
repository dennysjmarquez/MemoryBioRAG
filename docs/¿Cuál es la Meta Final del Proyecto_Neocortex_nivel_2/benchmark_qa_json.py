"""Ejecutor neutral de 921 casos; el código importado se elige mediante PYTHONPATH."""
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path

from core.memory_store import SQLiteMemoryBioRAG

if len(sys.argv) != 4:
    raise SystemExit("Uso: benchmark_qa_json.py SNAPSHOT_DB CASES_JSONL OUTPUT_JSON")

snapshot, cases_path, output = map(Path, sys.argv[1:])
work_dir = Path(tempfile.mkdtemp(prefix="biorag_bench_"))
temp_db = work_dir / "snapshot.db"

src = sqlite3.connect(snapshot)
dst = sqlite3.connect(temp_db)
src.backup(dst)
dst.close()
src.close()

casos = [json.loads(line) for line in cases_path.read_text(encoding="utf-8").splitlines() if line.strip()]
db = SQLiteMemoryBioRAG(db_path=str(temp_db))
stats = defaultdict(lambda: {"total": 0, "hits_at_5": 0, "hits_at_1": 0, "rr_sum": 0.0, "false_positives": 0})
fallos = []

inicio = time.time()
for caso in casos:
    categoria = caso["categoria"]
    esperado = caso.get("concepto_esperado")
    query = caso["query"]
    stats[categoria]["total"] += 1
    if categoria == "dormido" and esperado:
        db.cursor.execute("UPDATE largo_plazo SET estado='dormido' WHERE concepto=?", (esperado,))
        db.conn.commit()
    elif esperado:
        db.cursor.execute("UPDATE largo_plazo SET estado='activo' WHERE concepto=?", (esperado,))
        db.conn.commit()
    profundo = "profundo" if (caso.get("deep", False) or categoria in {"dormido", "negativo"}) else "activos"
    resultados, _total = db.buscar_por_frase(query, profundidad=profundo, limite=5, ignore_peso_sinaptico=True)
    devueltos = [r[0] for r in resultados]
    scores = [float(r[4]) for r in resultados]
    if esperado is None:
        if any(score >= 0.25 for score in scores):
            stats[categoria]["false_positives"] += 1
            fallos.append({"id": caso["id"], "categoria": categoria, "query": query, "esperado": None, "devueltos": devueltos[:5], "scores": scores[:5], "error": "falso_positivo"})
        continue
    try:
        posicion = devueltos.index(esperado) + 1
    except ValueError:
        posicion = 0
    if posicion:
        stats[categoria]["hits_at_5"] += 1
        stats[categoria]["rr_sum"] += 1.0 / posicion
        if posicion == 1:
            stats[categoria]["hits_at_1"] += 1
    else:
        fallos.append({"id": caso["id"], "categoria": categoria, "query": query, "esperado": esperado, "devueltos": devueltos[:5], "scores": scores[:5], "error": "ausente_top_5"})

elapsed = time.time() - inicio
por_categoria = {}
positivos = 0
hits5 = 0
hits1 = 0
rr = 0.0
negativos = 0
fps = 0
for categoria, s in sorted(stats.items()):
    if categoria == "negativo":
        negativos += s["total"]
        fps += s["false_positives"]
        por_categoria[categoria] = {"total": s["total"], "falsos_positivos": s["false_positives"], "tasa_fp": s["false_positives"] / s["total"] if s["total"] else 0.0}
    else:
        positivos += s["total"]
        hits5 += s["hits_at_5"]
        hits1 += s["hits_at_1"]
        rr += s["rr_sum"]
        por_categoria[categoria] = {"total": s["total"], "recall_at_5": s["hits_at_5"] / s["total"] if s["total"] else 0.0, "recall_at_1": s["hits_at_1"] / s["total"] if s["total"] else 0.0, "mrr": s["rr_sum"] / s["total"] if s["total"] else 0.0}

reporte = {
    "suite": "casos_qa_baseline_v1",
    "casos_total": len(casos),
    "snapshot": str(snapshot),
    "metricas_globales": {
        "consultas_positivas": positivos,
        "recall_at_5": hits5 / positivos if positivos else 0.0,
        "recall_at_1": hits1 / positivos if positivos else 0.0,
        "mrr": rr / positivos if positivos else 0.0,
        "controles_negativos": negativos,
        "falsos_positivos": fps,
        "tasa_fp": fps / negativos if negativos else 0.0,
        "segundos": elapsed,
    },
    "por_categoria": por_categoria,
    "fallos": fallos,
}
output.write_text(json.dumps(reporte, ensure_ascii=False, indent=2), encoding="utf-8")
db.conn.close()
shutil.rmtree(work_dir, ignore_errors=True)
print(json.dumps({"casos": len(casos), **reporte["metricas_globales"]}, ensure_ascii=False, indent=2))
