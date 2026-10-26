import os,sys,json,shutil
R="/home/user/MemoryBioRAG"; sys.path.insert(0,R); os.environ["BIORAG_NO_LOG"]="1"
from core.memory_store import SQLiteMemoryBioRAG
cases={json.loads(l)["id"]:json.loads(l) for l in open(R+"/scripts/casos_qa.jsonl")}
for src in sys.argv[2:]:
    tmp="/tmp/v/h_"+os.path.basename(src); shutil.copy(src,tmp); os.environ["BIORAG_PATH"]=tmp; db=SQLiteMemoryBioRAG(tmp)
    for i in sys.argv[1].split(","):
        q=cases[i]["query"]
        res,tot=db.buscar_por_frase(q,profundidad="activos",limite=5,ignore_peso_sinaptico=True)
        h=db.last_hub_expansion or {}
        print(os.path.basename(src),i,"hub:",h.get("hub_id") or h.get("hub") or h.get("concepto_hub"),"conf:",h.get("hub_confidence"),"canon:",[c[:30] for c in (h.get("canonical_nodes") or [])][:8], "keys:",list(h.keys())[:8])
    db.cerrar_sistema()
    for x in("","-wal","-shm"):
        try: os.remove(tmp+x)
        except FileNotFoundError: pass
