import sys
import os
import json
import sqlite3
import time
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.memory_store import SQLiteMemoryBioRAG

def bucket(pos):
    if pos == 1:
        return "1"
    if pos <= 5:
        return "2-5"
    if pos <= 15:
        return "6-15"
    if pos <= 50:
        return "16-50"
    if pos <= 200:
        return "51-200"
    return "201+"

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src_db = os.environ.get('BIORAG_PATH') or os.path.join(base_dir, "MemoryBioRAG_Data", "memory_biorag.db")
    temp_db = os.path.join(base_dir, "MemoryBioRAG_Data", "memory_biorag_diag_pos_temp.db")
    cases_file = os.path.join(base_dir, "scripts", "casos_qa_baseline_v1.jsonl")

    print(f"Creando copia aislada con sqlite3.backup(): {temp_db}")
    t0 = time.time()
    with sqlite3.connect(src_db) as src, sqlite3.connect(temp_db) as dst:
        src.backup(dst)
    print(f"Copia en {time.time()-t0:.2f}s")

    cases = []
    with open(cases_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                cases.append(json.loads(line))
    casos_por_tema = [c for c in cases if c["categoria"] == "por_tema"]
    print(f"Casos por_tema: {len(casos_por_tema)}\n")

    db = SQLiteMemoryBioRAG(db_path=temp_db)

    dist = Counter()
    casi_aciertos = []
    fallos_totales = []
    aciertos = []
    detalles = []

    t0 = time.time()
    for i, case in enumerate(casos_por_tema, 1):
        case_id = case["id"]
        query = case["query"]
        expected = case["concepto_esperado"]
        deep = case.get("deep", False)

        db.cursor.execute("UPDATE largo_plazo SET estado = 'activo' WHERE concepto = ?", (expected,))
        db.conn.commit()

        profundidad = "profundo" if deep else "activos"
        results, total = db.buscar_por_frase(query, profundidad=profundidad, limite=1000, ignore_peso_sinaptico=True)

        returned = [r[0] for r in results]
        pos = -1
        for idx, concept in enumerate(returned):
            if concept == expected:
                pos = idx + 1
                break

        if pos == -1:
            b = "NO_APARECE"
            dist["no_aparece"] += 1
            fallos_totales.append((case_id, query, expected, total))
        else:
            b = bucket(pos)
            dist[b] += 1
            if pos <= 5:
                aciertos.append((case_id, query, expected, pos, total))
            elif pos <= 15:
                casi_aciertos.append((case_id, query, expected, pos, total))
            else:
                fallos_totales.append((case_id, query, expected, pos, total))

        detalles.append({
            "id": case_id, "query": query, "expected": expected,
            "posicion": pos, "total_ranking": total,
            "top5": returned[:5],
            "scores_top5": [round(r[4], 4) for r in results[:5]]
        })

    elapsed = time.time() - t0
    db.conn.close()
    os.remove(temp_db)

    print("=" * 80)
    print("DISTRIBUCIÓN DE POSICIÓN DEL ESPERADO (65 casos por_tema, ranking completo)")
    print("=" * 80)
    for b in ["1", "2-5", "6-15", "16-50", "51-200", "201+", "no_aparece"]:
        if dist[b]:
            print(f"  {b:<12} {dist[b]:>4}  ({dist[b]/len(casos_por_tema)*100:.1f}%)")
    print("-" * 80)
    print(f"Total: {len(casos_por_tema)} | Recuperados top-5: {dist['1']+dist['2-5']} ({ (dist['1']+dist['2-5'])/len(casos_por_tema)*100:.1f}%)")
    print(f"Casi-aciertos (6-15): {len(casi_aciertos)} | Fallos totales (16+ o invisible): {len(fallos_totales)}")
    print(f"Tiempo: {elapsed:.1f}s")

    if casi_aciertos:
        print("\n" + "=" * 80)
        print("CASI-ACIERTOS (6-15): CANDIDATOS A RE-RANKING FINO")
        print("=" * 80)
        for cid, q, exp, pos, total in sorted(casi_aciertos, key=lambda x: x[3]):
            print(f"  [{cid}] pos={pos}/{total}  q='{q}' → '{exp}'")

    if fallos_totales:
        print("\n" + "=" * 80)
        print("FALLOS TOTALES (16+ o NO_APARECE): NECESITAN SEÑAL NUEVA")
        print("=" * 80)
        for cid, q, exp, pos, total in sorted(fallos_totales, key=lambda x: (x[3] == -1, x[3] if x[3] > 0 else 10**9)):
            pos_str = "NO_APARECE" if pos == -1 else str(pos)
            print(f"  [{cid}] pos={pos_str}/{total}  q='{q}' → '{exp}'")

    out = os.path.join(base_dir, "scripts", "diagnostico_posicion_detalle.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(detalles, f, ensure_ascii=False, indent=2)
    print(f"\nDetalle completo guardado en {out}")

if __name__ == "__main__":
    main()
