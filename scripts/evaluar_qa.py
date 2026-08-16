import sys
import os
import json
import shutil
import sqlite3
import time
from collections import defaultdict

# Add workspace root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.memory_store import SQLiteMemoryBioRAG

def run_evaluation():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Cargar .env.local automáticamente si existe
    env_local = os.path.join(base_dir, ".env.local")
    if os.path.exists(env_local):
        with open(env_local, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

    # No contaminar log_busquedas con consultas del benchmark
    os.environ["BIORAG_NO_LOG"] = "1"

    src_db = os.environ.get('BIORAG_PATH') or os.path.join(base_dir, "MemoryBioRAG_Data", "memory_biorag.db")

    temp_db = os.path.join(base_dir, "MemoryBioRAG_Data", "memory_biorag_qa_temp.db")
    cases_filename = sys.argv[1] if len(sys.argv) > 1 else "casos_qa_baseline_v1.jsonl"
    cases_file = os.path.join(base_dir, "scripts", cases_filename)
    failed_file = os.path.join(base_dir, "scripts", "casos_fallidos.jsonl")
    
    if not os.path.exists(cases_file):
        print(f"Error: Test cases file not found at {cases_file}.")
        sys.exit(1)
        
    print(f"Creating isolated database copy at: {temp_db}")
    for ext in ["", "-wal", "-shm"]:
        f = temp_db + ext
        if os.path.exists(f):
            try:
                os.remove(f)
            except OSError:
                pass
    conn_src = sqlite3.connect(src_db)
    conn_src.execute("PRAGMA wal_checkpoint(FULL);")
    conn_dst = sqlite3.connect(temp_db)
    conn_src.backup(conn_dst)
    conn_dst.close()
    conn_src.close()


    
    # Load cases
    cases = []
    with open(cases_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                cases.append(json.loads(line))
                
    print(f"Loaded {len(cases)} test cases.")
    
    # Initialize BioRAG against the temp DB copy
    db = SQLiteMemoryBioRAG(db_path=temp_db)
    
    # Stats tracking
    stats = defaultdict(lambda: {"total": 0, "hits_at_5": 0, "hits_at_1": 0, "reciprocal_rank_sum": 0, "false_positives": 0})
    failures_by_category = defaultdict(list)
    spreading_activation_count = 0  # Contador de queries que activan spreading activation
    
    start_time = time.time()
    
    for case in cases:
        case_id = case["id"]
        category = case["categoria"]
        query = case["query"]
        expected = case["concepto_esperado"]
        deep = case.get("deep", False)
        
        stats[category]["total"] += 1
        
        # 1. Setup phase: only set active/dormant state for target concept (weights are 1.00 for ALL nodes globally)
        if category == "dormido" and expected:
            db.cursor.execute("UPDATE largo_plazo SET estado = 'dormido' WHERE concepto = ?", (expected,))
            db.conn.commit()
        elif expected:
            db.cursor.execute("UPDATE largo_plazo SET estado = 'activo' WHERE concepto = ?", (expected,))
            db.conn.commit()
            
        # 2. Execute query
        profundidad = "profundo" if (deep or category == "dormido" or category == "negativo") else "activos"
        results, total = db.buscar_por_frase(query, profundidad=profundidad, limite=5, ignore_peso_sinaptico=True)
        
        # Track spreading activation usage
        if hasattr(db, 'last_parent_map') and db.last_parent_map:
            spreading_activation_count += 1
        
        # Extract returned concepts
        returned = [r[0] for r in results]
        scores = [r[4] for r in results]
        
        # 3. Evaluation phase
        if expected is None:
            # Negative control case: check if we retrieved any matches with high score
            # Noise threshold: configurable via BIORAG_FP_THRESHOLD (default 0.25)
            fp_threshold = float(os.environ.get('BIORAG_FP_THRESHOLD', '0.25'))
            fps = [r for r in results if r[4] >= fp_threshold]
            if len(fps) > 0:
                stats[category]["false_positives"] += 1
                failures_by_category[category].append({
                    "id": case_id,
                    "query": query,
                    "expected": None,
                    "returned": returned[:3],
                    "scores": scores[:3],
                    "error": f"False positive returned with score {scores[0]}"
                })
        else:
            # Normal or awakening case
            found_at = -1
            for idx, concept in enumerate(returned):
                if concept == expected:
                    found_at = idx + 1
                    break
                    
            if found_at != -1:
                stats[category]["hits_at_5"] += 1
                stats[category]["reciprocal_rank_sum"] += 1.0 / found_at
                if found_at == 1:
                    stats[category]["hits_at_1"] += 1
                    
                # Extra validation for dormant nodes: check if the state was updated to 'activo'
                if category == "dormido":
                    db.cursor.execute("SELECT estado FROM largo_plazo WHERE concepto = ?", (expected,))
                    row = db.cursor.fetchone()
                    if not row or row[0] != "activo":
                        failures_by_category[category].append({
                            "id": case_id,
                            "query": query,
                            "expected": expected,
                            "returned": returned[:3],
                            "scores": scores[:3],
                            "error": f"Node found but remained dormant (state is {row[0] if row else 'None'})"
                        })
                        # Revert stats change since awakening failed
                        stats[category]["hits_at_5"] -= 1
                        if found_at == 1:
                            stats[category]["hits_at_1"] -= 1
                        stats[category]["reciprocal_rank_sum"] -= 1.0 / found_at
            else:
                failures_by_category[category].append({
                    "id": case_id,
                    "query": query,
                    "expected": expected,
                    "returned": returned[:3],
                    "scores": scores[:3],
                    "error": "Expected concept not found in top 5 results"
                })
                
    elapsed_time = time.time() - start_time
    db.conn.close()
    
    # Export failed cases to JSONL
    print(f"\nExporting failed cases to: {failed_file}")
    with open(failed_file, "w", encoding="utf-8") as f:
        for cat, fails in failures_by_category.items():
            for fail in fails:
                fail_record = {"categoria": cat, **fail}
                f.write(json.dumps(fail_record, ensure_ascii=False) + "\n")
                
    # Cleanup temp database
    print(f"Cleaning up temporary database copy at {temp_db}...")
    if os.path.exists(temp_db):
        os.remove(temp_db)
        
    # Generate report
    print("\n" + "="*80)
    print("                      BIORAG QA EVALUATION REPORT")
    print("="*80)
    print(f"Total time elapsed: {elapsed_time:.2f} seconds")
    print("-"*80)
    print(f"{'Category':<22} | {'Total':<6} | {'Recall@5':<9} | {'Recall@1':<9} | {'MRR':<8} | {'Errors/FPs':<10}")
    print("-"*80)
    
    total_queries = 0
    total_hits_at_5 = 0
    total_hits_at_1 = 0
    total_mrr_sum = 0
    total_negatives = 0
    total_false_positives = 0
    
    for cat in sorted(stats.keys()):
        stat = stats[cat]
        cnt = stat["total"]
        if cat == "negativo":
            total_negatives += cnt
            total_false_positives += stat["false_positives"]
            fp_rate = (stat["false_positives"] / cnt) * 100 if cnt > 0 else 0
            print(f"{cat:<22} | {cnt:<6} | {'N/A':<9} | {'N/A':<9} | {'N/A':<8} | {stat['false_positives']:<10} ({fp_rate:.1f}% FP)")
        else:
            total_queries += cnt
            total_hits_at_5 += stat["hits_at_5"]
            total_hits_at_1 += stat["hits_at_1"]
            total_mrr_sum += stat["reciprocal_rank_sum"]
            
            recall_5 = (stat["hits_at_5"] / cnt) * 100 if cnt > 0 else 0
            recall_1 = (stat["hits_at_1"] / cnt) * 100 if cnt > 0 else 0
            mrr = stat["reciprocal_rank_sum"] / cnt if cnt > 0 else 0
            num_failures = cnt - stat["hits_at_5"] if cat != "dormido" else len(failures_by_category[cat])
            print(f"{cat:<22} | {cnt:<6} | {recall_5:>7.2f}% | {recall_1:>7.2f}% | {mrr:>6.3f} | {num_failures:<10}")
            
    print("-"*80)
    global_recall_5 = (total_hits_at_5 / total_queries) * 100 if total_queries > 0 else 0
    global_recall_1 = (total_hits_at_1 / total_queries) * 100 if total_queries > 0 else 0
    global_mrr = total_mrr_sum / total_queries if total_queries > 0 else 0
    global_fp_rate = (total_false_positives / total_negatives) * 100 if total_negatives > 0 else 0
    
    print(f"{'GLOBAL SUMMARY (Retrieval)':<22} | {total_queries:<6} | {global_recall_5:>7.2f}% | {global_recall_1:>7.2f}% | {global_mrr:>6.3f} | {total_queries - total_hits_at_5:<10}")
    print(f"{'GLOBAL SUMMARY (Noise/FP)':<22} | {total_negatives:<6} | {'N/A':<9} | {'N/A':<9} | {'N/A':<8} | {total_false_positives:<10} ({global_fp_rate:.2f}% FP)")
    print(f"{'SPREADING ACTIVATION':<22} | {spreading_activation_count}/{len(cases)} queries ({spreading_activation_count/len(cases)*100:.1f}%)")
    print("="*80)
    
    # Output detailed failures per category (up to 3 cases per category)
    if len(failures_by_category) > 0:
        print("\nSAMPLE FAILURES BY CATEGORY FOR ACTIONABLE DIAGNOSIS:")
        print("="*80)
        for cat in sorted(failures_by_category.keys()):
            fails = failures_by_category[cat]
            print(f"\n[Category: {cat}] ({len(fails)} total failures)")
            print("-" * 40)
            for idx, fail in enumerate(fails[:3]):
                print(f"  #{idx+1} [ID {fail['id']}] Query: \"{fail['query']}\"")
                print(f"      Expected:  {fail['expected']}")
                print(f"      Returned:  {fail['returned']} (scores: {[round(s, 3) for s in fail['scores']]})")
                print(f"      Reason:    {fail['error']}")
        print("="*80)
        print(f"Note: All failed cases have been saved to {failed_file} for full debug analysis.")
    else:
        print("\nAmazing! Zero failures detected across all test categories.")
        print("="*80)

if __name__ == "__main__":
    run_evaluation()
