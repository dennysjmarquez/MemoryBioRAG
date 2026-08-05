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

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src_db = os.path.join(base_dir, "MemoryBioRAG_Data", "memory_biorag.db")
    temp_db = os.path.join(base_dir, "MemoryBioRAG_Data", "memory_biorag_diag_lex_temp.db")

    with sqlite3.connect(src_db) as src, sqlite3.connect(temp_db) as dst:
        src.backup(dst)

    with open(os.path.join(base_dir, "scripts", "diagnostico_posicion_detalle.json"), encoding="utf-8") as f:
        dets = json.load(f)

    db = SQLiteMemoryBioRAG(db_path=temp_db)
    contenido = {}
    cur = db.cursor
    for d in dets:
        for c in [d["expected"]] + d["top5"]:
            if c not in contenido:
                cur.execute("SELECT contenido FROM largo_plazo WHERE concepto = ?", (c,))
                row = cur.fetchone()
                contenido[c] = row[0] if row else ""
    db.conn.close()
    os.remove(temp_db)

    fallos = [d for d in dets if d["posicion"] < 0 or d["posicion"] > 5]
    print(f"{'ID':<6} {'pos':<6} {'j_exp':<7} {'j_top1':<7} {'j_promTop5':<10} {'tokens_q':<3} {'tokens_esperado_en_q':<3} {'coincide_en_exp'}")
    print("-" * 90)
    re_rank_potencial = 0
    for d in sorted(fallos, key=lambda x: x["posicion"] if x["posicion"] > 0 else 999):
        q = tokens(d["query"])
        te = tokens(d["expected"])
        tq = tokens(d["query"])
        j_exp = jaccard(q, tokens(contenido[d["expected"]][:3000]))
        j_top1 = jaccard(q, tokens(contenido[d["top5"][0]][:3000]))
        j_prom = sum(jaccard(q, tokens(contenido[c][:3000])) for c in d["top5"]) / len(d["top5"])
        coin = len(tq & te)
        flag = " <- esperado pierde pese a +lexico" if j_exp > j_prom else ""
        if j_exp > j_prom:
            re_rank_potencial += 1
        pos = d["posicion"] if d["posicion"] > 0 else -1
        print(f"{d['id']:<6} {pos:<6} {j_exp:<7.3f} {j_top1:<7.3f} {j_prom:<10.3f} {len(tq):<3} {coin:<3} {'OK' if coin else 'ZERO'}{flag}")

    print("-" * 90)
    print(f"Esperados con jaccard > promedio de top-5 (candidatos a re-rank por léxico): {re_rank_potencial}/{len(fallos)}")

if __name__ == "__main__":
    main()
