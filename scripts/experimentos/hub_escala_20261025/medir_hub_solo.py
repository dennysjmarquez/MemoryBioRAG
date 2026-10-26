import json, sqlite3, sys, time
import os; sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
from core.concept_hub import expandir_query_con_hub
casos = [json.loads(l) for l in open(os.path.join(os.path.dirname(__file__), "..", "..", "casos_qa.jsonl"), encoding="utf-8")]
for db in sys.argv[1:]:
    c = sqlite3.connect(f"file:{db}?mode=ro&immutable=1", uri=True)
    reg = []; disp = bien = mal = neg = 0; t0 = time.time(); malos = []
    for k in casos:
        e = expandir_query_con_hub(k["query"], c, threshold=0.40)
        if not e: continue
        if k.get("categoria") == "negativo": neg += 1; continue
        disp += 1
        gold = k.get("concepto_esperado")
        golds = gold if isinstance(gold, list) else [gold]
        if e["canonical_nodes"][0] in golds: bien += 1
        else: mal += 1; malos.append((k["id"], e["hub_confidence"]))
        reg.append({"id": k["id"], "cat": k["categoria"], "hub": e["canonical_nodes"][0], "conf": e["hub_confidence"], "ok": e["canonical_nodes"][0] in golds})
    ms = (time.time() - t0) / len(casos) * 1000
    print(f"{db.split('/')[-1]:14s} hub se dispara en {disp:3d} casos: acierta {bien:3d}, se equivoca {mal:3d} | en negativos {neg} | {ms:.1f} ms/consulta")
    json.dump(reg, open(db + ".proxy.json", "w"))
