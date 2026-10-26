import sys,json,os
from core.memory_store import SQLiteMemoryBioRAG
ids=sys.argv[1].split(',')
casos={json.loads(l)["id"]:json.loads(l) for l in open('/home/user/MemoryBioRAG/scripts/casos_qa.jsonl')}
db=SQLiteMemoryBioRAG(os.environ['BIORAG_PATH'])
for i in ids:
    d=casos[i]; oro=d['concepto_esperado']
    res,_=db.buscar_por_frase(d['query'],profundidad='profundo' if d.get('deep') else 'activos',limite=5,ignore_peso_sinaptico=True)
    org=db.last_origen_scores or {}
    n=[r[0] for r in res]
    print(i,repr(d['query']),'oro',oro[:40],'→',n.index(oro)+1 if oro in n else 'FUERA')
    for r in res: print('    %.3f %-22s %s'%(r[4],str(org.get(r[0]))[:22],r[0][:48]))
