"""Para cada caso: ¿el oro fue candidato?, ¿por qué capa entró?, su score, puesto. En dos memorias."""
import os, sys, json, shutil
R="/home/user/MemoryBioRAG"; sys.path.insert(0,R)
ids=sys.argv[1].split(","); dbs=sys.argv[2:]
cases={json.loads(l)["id"]:json.loads(l) for l in open(R+"/scripts/casos_qa.jsonl")}
from core.memory_store import SQLiteMemoryBioRAG
os.environ["BIORAG_NO_LOG"]="1"
out={}
for src in dbs:
    tmp=f"/tmp/v/diag_{os.path.basename(src)}"; shutil.copy(src,tmp)
    db=SQLiteMemoryBioRAG(tmp)
    for i in ids:
        c=cases[i]; e=c["concepto_esperado"]
        db.cursor.execute("UPDATE largo_plazo SET estado='activo' WHERE concepto=?",(e,)); db.conn.commit()
        res,_=db.buscar_por_frase(c["query"],profundidad="activos",limite=int(os.environ.get("LIM","5")),ignore_peso_sinaptico=True)
        todos=[r[1] for r in (db.last_todos or [])]
        org=(db.last_origen_scores or {}).get(e)
        sb=(round([r[4] for r in res][[r[0] for r in res].index(e)],4) if e in [r[0] for r in res] else None)
        dev=[r[0] for r in res]
        nc=len(todos); orgs={}
        for k,v in (db.last_origen_scores or {}).items(): orgs[v[0]]=orgs.get(v[0],0)+1
        out.setdefault(i,[]).append((os.path.basename(src), e in todos, org, sb, dev.index(e)+1 if e in dev else None, nc, orgs))
    db.cerrar_sistema()
    for x in ("","-wal","-shm"):
        try: os.remove(tmp+x)
        except FileNotFoundError: pass
for i,rows in out.items():
    print(i, cases[i]["categoria"][:8], repr(cases[i]["query"])[:50], "oro:", cases[i]["concepto_esperado"][:40])
    for r in rows: print("    %-10s candidato=%s capa=%s score_base=%s puesto=%s n_cand=%s capas=%s"%r)
