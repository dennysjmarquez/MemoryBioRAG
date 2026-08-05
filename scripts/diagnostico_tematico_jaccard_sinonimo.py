import sys
import os
import json
import sqlite3
import time
import re
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.stopwords import _STOPWORDS_QUERY
from core.memory_store import SQLiteMemoryBioRAG

def strip_accents(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text) if not unicodedata.combining(c))

def tokens(text):
    t = re.sub(r'[^\w\s_-]', ' ', text.lower())
    out = []
    for w in t.split():
        wc = strip_accents(w)
        if wc not in _STOPWORDS_QUERY and len(w) >= 2:
            out.append(w)
    return set(out)

def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)

def load_cases():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cases = []
    with open(os.path.join(base_dir, "scripts", "casos_qa_baseline_v1.jsonl"), encoding="utf-8") as f:
        for line in f:
            if line.strip():
                cases.append(json.loads(line))
    return cases

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src_db = os.path.join(base_dir, "MemoryBioRAG_Data", "memory_biorag.db")
    temp_db = os.path.join(base_dir, "MemoryBioRAG_Data", "memory_biorag_diag2_temp.db")

    with sqlite3.connect(src_db) as src, sqlite3.connect(temp_db) as dst:
        src.backup(dst)

    casos = load_cases()
    db = SQLiteMemoryBioRAG(db_path=temp_db)

    # Pre-warm thematic cache exactly like production (single search does it)
    db.buscar_por_frase("warmup cache", profundidad="activos", limite=5, ignore_peso_sinaptico=True)
    cache = getattr(db, '_thematic_scores_cache', None)
    print(f"Caché temática: {len(cache) if cache else 0} pares precomputados")
    print()

    # ---------- MEDICIÓN 1: Jaccard de aciertos de sinonimo ----------
    sinonimo = [c for c in casos if c["categoria"] == "sinonimo"]
    print("=" * 80)
    print("MEDICIÓN 1 — Jaccard léxico (query↔contenido) de casos sinonimo")
    print("=" * 80)
    print(f"{'ID':<6} {'pos':<5} {'jaccard':<9} {'tokens_q':<8} {'coinc_en_exp':<12} {'esperado'}")
    aciertos_j = []
    fallos_j = []
    for c in sinonimo:
        q_tok = tokens(c["query"])
        exp = c["concepto_esperado"]
        db.cursor.execute("UPDATE largo_plazo SET estado = 'activo' WHERE concepto = ?", (exp,))
        db.conn.commit()
        results, _ = db.buscar_por_frase(c["query"], profundidad="activos", limite=5, ignore_peso_sinaptico=True)
        returned = [r[0] for r in results]
        pos = -1
        for idx, conc in enumerate(returned):
            if conc == exp:
                pos = idx + 1
                break
        db.cursor.execute("SELECT contenido FROM largo_plazo WHERE concepto = ?", (exp,))
        row = db.cursor.fetchone()
        contenido = row[0] if row else ""
        j = jaccard(q_tok, tokens(contenido[:3000]))
        coin = len(q_tok & tokens(exp))
        es_acierto = pos != -1
        label = "ACIERTO" if es_acierto else "fallo"
        print(f"{c['id']:<6} {pos:<5} {j:<9.3f} {len(q_tok):<8} {coin:<12} {label} | {exp}")
        (aciertos_j if es_acierto else fallos_j).append(j)

    if aciertos_j:
        avg_ac = sum(aciertos_j) / len(aciertos_j)
        print(f"\n  Aciertos sinonimo: {len(aciertos_j)}/{len(sinonimo)} — jaccard promedio: {avg_ac:.3f}")
        print(f"  % aciertos con jaccard < 0.10: {sum(1 for j in aciertos_j if j < 0.10)/len(aciertos_j)*100:.1f}%")
    if fallos_j:
        print(f"  Fallos sinonimo: {len(fallos_j)}/{len(sinonimo)} — jaccard promedio: {sum(fallos_j)/len(fallos_j):.3f}")

    # ---------- MEDICIÓN 2: tematico_score esperado vs top-1 en 23 fallos por_tema ----------
    print()
    print("=" * 80)
    print("MEDICIÓN 2 — tematico_score replicado (pool real last_todos[:50]) — 23 fallos por_tema")
    print("=" * 80)
    if cache is None or not cache:
        print("  SIN CACHE temática — no se puede replicar. Abortando medición 2.")
    else:
        with open(os.path.join(base_dir, "scripts", "diagnostico_posicion_detalle.json"), encoding="utf-8") as f:
            dets = json.load(f)
        fallos_pt = [d for d in dets if d["posicion"] < 0 or d["posicion"] > 5]
        print(f"{'ID':<6} {'pos':<5} {'tematico_esp':<12} {'tematico_top1':<13} {'top1_>_esp?':<12} {'top1'}")
        count_top1_mayor = 0
        for d in sorted(fallos_pt, key=lambda x: x["posicion"] if x["posicion"] > 0 else 999):
            exp = d["expected"]
            top1 = d["top5"][0]
            db.cursor.execute("UPDATE largo_plazo SET estado = 'activo' WHERE concepto = ?", (exp,))
            db.conn.commit()
            db.buscar_por_frase(d["query"], profundidad="activos", limite=1000, ignore_peso_sinaptico=True)
            pool = getattr(db, 'last_todos', None)
            if not pool:
                print(f"  [{d['id']}] last_todos vacío")
                continue
            pool_50 = pool[:50]

            def calc_tematico(concepto):
                sims = []
                for t in pool_50:
                    other_concepto = t[1]
                    if other_concepto != concepto:
                        key = (concepto, other_concepto)
                        if key in cache:
                            sims.append(cache[key])
                if not sims:
                    return 0.0
                return min(1.0, sum(sims) / len(sims) * 3.0)

            t_esp = calc_tematico(exp)
            t_top1 = calc_tematico(top1)
            mayor = t_top1 > t_esp
            if mayor:
                count_top1_mayor += 1
            pos = d["posicion"] if d["posicion"] > 0 else -1
            print(f"{d['id']:<6} {pos:<5} {t_esp:<12.4f} {t_top1:<13.4f} {str(mayor):<12} {top1}")
        print(f"\n  Top-1 con tematico_score MAYOR que el esperado: {count_top1_mayor}/{len(fallos_pt)}")

    db.conn.close()
    os.remove(temp_db)

if __name__ == "__main__":
    main()
