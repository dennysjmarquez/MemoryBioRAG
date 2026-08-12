import sys
import os
import json
import re
import sqlite3
import shutil
import time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.memory_store import SQLiteMemoryBioRAG

ESCAPE_SET = ("semantica", "simbolico", "expansion", "dimensional_fallback")

def replicar_qcr(query, conc, cont, sinonimos, origen_tipo):
    q_tokens = [t.lower() for t in re.findall(r'\w{3,}', query)]
    if len(q_tokens) < 2:
        return 1.0, False, True  # gate no aplica (query de 1 token)
    text_target = f"{conc} {cont} {sinonimos}".lower()
    matches = sum(1 for t in q_tokens if t in text_target)
    ratio = matches / len(q_tokens)
    pasa_escape = origen_tipo in ESCAPE_SET
    sobrevive_actual = ratio >= 0.50 or pasa_escape
    return ratio, pasa_escape, sobrevive_actual

def run():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_local = os.path.join(base_dir, ".env.local")
    if os.path.exists(env_local):
        with open(env_local, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

    src_db = os.environ.get('BIORAG_PATH') or os.path.join(base_dir, "MemoryBioRAG_Data", "memory_biorag.db")
    snap_path = os.path.join(base_dir, "snapshots", "qa_escape_qcr_20260811.db")
    cases_file = os.path.join(base_dir, "scripts", "casos_qa_baseline_v1.jsonl")

    if not os.path.exists(snap_path):
        os.makedirs(os.path.dirname(snap_path), exist_ok=True)
        print(f"Creating frozen snapshot: {snap_path}")
        conn_src = sqlite3.connect(src_db)
        conn_src.execute("PRAGMA wal_checkpoint(FULL);")
        conn_dst = sqlite3.connect(snap_path)
        conn_src.backup(conn_dst)
        conn_dst.close()
        conn_src.close()
    else:
        print(f"Reusing existing snapshot: {snap_path}")

    cases = []
    with open(cases_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                cases.append(json.loads(line))

    print(f"Loaded {len(cases)} test cases against frozen snapshot.")
    db = SQLiteMemoryBioRAG(db_path=snap_path)

    registros = []
    maxq = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else None
    start = time.time()
    for i, case in enumerate(cases):
        if maxq and i >= maxq:
            break
        qid = case["id"]
        cat = case["categoria"]
        query = case["query"]
        expected = case["concepto_esperado"]
        deep = case.get("deep", False)

        if cat == "dormido" and expected:
            db.cursor.execute("UPDATE largo_plazo SET estado = 'dormido' WHERE concepto = ?", (expected,))
            db.conn.commit()
        elif expected:
            db.cursor.execute("UPDATE largo_plazo SET estado = 'activo' WHERE concepto = ?", (expected,))
            db.conn.commit()

        profundidad = "profundo" if (deep or cat == "dormido" or cat == "negativo") else "activos"
        results, total = db.buscar_por_frase(query, profundidad=profundidad, limite=5, ignore_peso_sinaptico=True)
        origen_map = dict(getattr(db, "last_origen_scores", {}) or {})

        conceptos_top = [r[0] for r in results]
        sinonimos_map = {}
        if conceptos_top:
            ph = ",".join(["?"] * len(conceptos_top))
            db.cursor.execute(f"SELECT concepto, sinonimos FROM largo_plazo WHERE concepto IN ({ph})", conceptos_top)
            for conc, sin in db.cursor.fetchall():
                sinonimos_map[conc] = sin or ""

        for r in results:
            conc, cont, peso, est, sc, asoc = r
            origen_tipo, score_capa = origen_map.get(conc, ("literal", 0.0))
            sinon = sinonimos_map.get(conc, "")
            ratio, pasa_escape, sobrevive_actual = replicar_qcr(query, conc, cont, sinon, origen_tipo)

            tipo = None
            if expected is None:
                if sc >= 0.25:
                    tipo = "FP"
            else:
                if conc == expected:
                    tipo = "TP"
                else:
                    tipo = "otro"

            registros.append({
                "qid": qid, "categoria": cat, "query": query, "expected": expected,
                "concepto": conc, "score": sc, "score_capa": score_capa,
                "origen_tipo": origen_tipo, "ratio_qcr": round(ratio, 3),
                "pasa_escape": pasa_escape, "gate_aplica": len(re.findall(r'\w{3,}', query)) >= 2,
                "sobrevive_actual": sobrevive_actual, "tipo": tipo,
            })
        if (i + 1) % 200 == 0:
            print(f"  {i + 1}/{len(cases)} queries done ({time.time() - start:.0f}s)")

    db.conn.close()

    fps = [r for r in registros if r["tipo"] == "FP"]
    tps = [r for r in registros if r["tipo"] == "TP"]
    fps_escape = [r for r in fps if r["pasa_escape"] and r["gate_aplica"] and r["ratio_qcr"] < 0.50]
    tps_escape = [r for r in tps if r["pasa_escape"] and r["gate_aplica"] and r["ratio_qcr"] < 0.50]

    def resumen(grupo, label):
        if not grupo:
            return {"grupo": label, "n": 0}
        scores = [r["score"] for r in grupo]
        capa = [r["score_capa"] for r in grupo if r["score_capa"] is not None]
        return {
            "grupo": label, "n": len(grupo),
            "score_min": round(min(scores), 3), "score_max": round(max(scores), 3),
            "score_media": round(sum(scores) / len(scores), 3),
            "capa_min": round(min(capa), 3) if capa else None,
            "capa_max": round(max(capa), 3) if capa else None,
            "capa_media": round(sum(capa) / len(capa), 3) if capa else None,
        }

    dist = {
        "fps_escape": resumen(fps_escape, "FP-escape"),
        "tps_escape": resumen(tps_escape, "TP-escape"),
        "tps_escape_por_cat": {},
    }
    for cat in sorted({r["categoria"] for r in tps_escape}):
        dist["tps_escape_por_cat"][cat] = resumen([r for r in tps_escape if r["categoria"] == cat], cat)

    buckets = defaultdict(int)
    for r in fps_escape:
        buckets[f"{int(r['score'] * 20) * 5}-{int(r['score'] * 20) * 5 + 5}"] += 1
    dist["histograma_fp_escape"] = dict(sorted(buckets.items()))
    buckets_tp = defaultdict(int)
    for r in tps_escape:
        buckets_tp[f"{int(r['score'] * 20) * 5}-{int(r['score'] * 20) * 5 + 5}"] += 1
    dist["histograma_tp_escape"] = dict(sorted(buckets_tp.items()))

    resumen_final = {
        "total_queries": len(cases),
        "fps_totales": len(fps),
        "tps_totales": len(tps),
        "fps_via_escape": len(fps_escape),
        "tps_via_escape": len(tps_escape),
        "si_se_cerrara_escape_estimacion": {
            "FP_eliminados": len(fps_escape),
            "TP_esperados_perdidos_cota": len(tps_escape),
            "nota": "Cota de TP perdidos = esperados que HOY llegan al top5 SOLO por escape. El reemplazo por otros candidatos puede reducir el daño; requiere re-correr para exactitud.",
        },
        "distribuciones": dist,
    }

    out_json = os.path.join(base_dir, "scripts", "analisis_escape_qcr_20260811.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(resumen_final, f, ensure_ascii=False, indent=2)
    out_detalle = os.path.join(base_dir, "scripts", "escape_qcr_detalle.jsonl")
    with open(out_detalle, "w", encoding="utf-8") as f:
        for r in sorted(registros, key=lambda x: (x["categoria"], x["qid"])):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print("\n================ RESUMEN ESCAPE QCR ================")
    print(json.dumps(resumen_final, ensure_ascii=False, indent=2))
    print(f"\nDetalle guardado en {out_detalle}")
    print(f"Resumen guardado en {out_json}")

if __name__ == "__main__":
    run()
