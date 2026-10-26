import os,sys,json,shutil
R="/home/user/MemoryBioRAG"; sys.path.insert(0,R); os.environ["BIORAG_NO_LOG"]="1"
from core.memory_store import SQLiteMemoryBioRAG
from core.fallback_simbolico import _tokenizar_normalizado as tok
cases={json.loads(l)["id"]:json.loads(l) for l in open(R+"/scripts/casos_qa.jsonl")}
for src in sys.argv[2:]:
    tmp="/tmp/v/cov_"+os.path.basename(src); shutil.copy(src,tmp); db=SQLiteMemoryBioRAG(tmp)
    for i in sys.argv[1].split(","):
        q=cases[i]["query"]; qt=tok(q)
        db.buscar_por_frase(q,profundidad="activos",limite=5,ignore_peso_sinaptico=True)
        # cobertura sobre los candidatos que existían en el momento del gate ≈ los literales
        best=sorted(((len(qt&tok(f"{r[1]} {r[2] or ''}"))/len(qt), r[1]) for r in (db.last_todos or [])), reverse=True)[:2]
        print(os.path.basename(src), i, "tokens:", sorted(qt), "→ mejor cobertura:", [(round(c,2),n[:55]) for c,n in best])
    db.cerrar_sistema()
    for x in("","-wal","-shm"):
        try: os.remove(tmp+x)
        except FileNotFoundError: pass
