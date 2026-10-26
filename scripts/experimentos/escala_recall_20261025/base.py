import os,sys,json,shutil
R="/home/user/MemoryBioRAG"; sys.path.insert(0,R); os.environ["BIORAG_NO_LOG"]="1"
from core.memory_store import SQLiteMemoryBioRAG
cases={json.loads(l)["id"]:json.loads(l) for l in open(R+"/scripts/casos_qa.jsonl")}
for src in sys.argv[2:]:
    tmp="/tmp/v/b_"+os.path.basename(src); shutil.copy(src,tmp); os.environ["BIORAG_PATH"]=tmp; db=SQLiteMemoryBioRAG(tmp)
    for i in sys.argv[1].split(","):
        q=cases[i]["query"]; e=cases[i]["concepto_esperado"]
        res,tot=db.buscar_por_frase(q,profundidad="activos",limite=40,convergencia_limite=0,ignore_peso_sinaptico=True)
        org=db.last_origen_scores or {}
        n=[r[0] for r in res]
        print(os.path.basename(src),i,repr(q)[:40],"total",tot,"oro puesto(base)",n.index(e)+1 if e in n else None)
        for k,r in enumerate(res[:7],1): print("   %d %.4f %-26s %s"%(k,r[4],str(org.get(r[0]))[:26],r[0][:50]))
    db.cerrar_sistema()
    for x in("","-wal","-shm"):
        try: os.remove(tmp+x)
        except FileNotFoundError: pass
