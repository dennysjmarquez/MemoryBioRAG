import os,sys,json,shutil
R="/home/user/MemoryBioRAG"; sys.path.insert(0,R); os.environ["BIORAG_NO_LOG"]="1"
from core.memory_store import SQLiteMemoryBioRAG
cases={json.loads(l)["id"]:json.loads(l) for l in open(R+"/scripts/casos_qa.jsonl")}
for src in sys.argv[2:]:
    tmp="/tmp/v/top_"+os.path.basename(src); shutil.copy(src,tmp); db=SQLiteMemoryBioRAG(tmp)
    for i in sys.argv[1].split(","):
        q=cases[i]["query"]; e=cases[i]["concepto_esperado"]
        allr=[]
        for p in range(1,8):
            res,_=db.buscar_por_frase(q,profundidad="activos",limite=5,pagina=p,ignore_peso_sinaptico=True)
            if not res: break
            allr+=res
        org=db.last_origen_scores or {}
        names=[r[0] for r in allr]
        print(os.path.basename(src), i, repr(q), "oro en", names.index(e)+1 if e in names else None)
        for k,r in enumerate(allr[:8],1):
            print("   %2d %.4f %-22s %s"%(k,r[4],str(org.get(r[0]))[:22],r[0][:60]))
    db.cerrar_sistema()
    for x in("","-wal","-shm"):
        try: os.remove(tmp+x)
        except FileNotFoundError: pass
