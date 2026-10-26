"""Igual que evaluar_qa (mismo setup, misma llamada, restaura estado entre casos) pero guarda
el PUESTO del oro en cada pregunta, para comparar caso por caso entre memorias.
uso: rangos.py <db> <salida.jsonl> [ids_coma]"""
import os, sys, json, shutil, time
R="/home/user/MemoryBioRAG"; sys.path.insert(0,R); sys.path.insert(0,R+"/scripts")
src, out = sys.argv[1], sys.argv[2]
solo=set(sys.argv[3].split(",")) if len(sys.argv)>3 and sys.argv[3] else None
tmp=out+".db"; shutil.copy(src,tmp)
for e in("-wal","-shm"):
    if os.path.exists(tmp+e): os.remove(tmp+e)
os.environ.update(BIORAG_PATH=tmp, BIORAG_NO_LOG="1")
from core.memory_store import SQLiteMemoryBioRAG
from evaluar_qa import _restaurar_estado_nodos
db=SQLiteMemoryBioRAG(tmp)
cases=[json.loads(l) for l in open(R+"/scripts/casos_qa.jsonl")]
from collections import defaultdict
g=defaultdict(set)
for c in cases:
    if c["concepto_esperado"]: g[c["query"].strip().lower()].add(c["concepto_esperado"])
amb={q for q,s in g.items() if len(s)>1}
ini={r[0]:(r[1],r[2]) for r in db.cursor.execute("select concepto,estado,peso_sinaptico from largo_plazo")}
f=open(out,"w"); t0=time.time()
for c in cases:
    e=c["concepto_esperado"]; cat=c["categoria"]
    if not e or c["query"].strip().lower() in amb: continue
    if solo and c["id"] not in solo: continue
    db.cursor.execute("UPDATE largo_plazo SET estado=? WHERE concepto=?",("dormido" if cat=="dormido" else "activo",e)); db.conn.commit()
    prof="profundo" if (c.get("deep") or cat in("dormido","negativo")) else "activos"
    res,_=db.buscar_por_frase(c["query"],profundidad=prof,limite=5,ignore_peso_sinaptico=True)
    dev=[r[0] for r in res]
    f.write(json.dumps({"id":c["id"],"cat":cat,"q":c["query"],"oro":e,"puesto":(dev.index(e)+1 if e in dev else None),
        "top":dev[:5],"sc":[round(r[4],4) for r in res][:5]},ensure_ascii=False)+"\n")
    _restaurar_estado_nodos(db,ini)
f.close(); db.cerrar_sistema()
for e in("","-wal","-shm"):
    if os.path.exists(tmp+e): os.remove(tmp+e)
print(f"LISTO {out} {time.time()-t0:.0f}s")
