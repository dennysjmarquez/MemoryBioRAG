# Auditoría: vuelca el top 5 COMPLETO (no solo el objetivo) de las 921 consultas oficiales,
# con parámetros de producción (peso sináptico activo, profundidad activos). Uso:
#   BIORAG_NEURONA=0 PYTHONHASHSEED=0 python scripts/comparar_listas_completas_top5.py <copia.db> <salida.json>
# Compara dos versiones con cmp sobre las salidas. Nunca usar la base original: solo copias.
import os, sys, json, tempfile
os.environ["BIORAG_DMN_ESTADO_PATH"]=tempfile.mkdtemp()+"/e.json"
from core.memory_store import SQLiteMemoryBioRAG
db=SQLiteMemoryBioRAG(sys.argv[1])
C=[json.loads(l) for l in open('scripts/casos_qa_baseline_v1.jsonl',encoding='utf-8')]
out=[]
for c in C:
    q=c.get('query') or ''
    try:
        r,_=db.buscar_por_frase(q, profundidad="activos", limite=5)
        out.append([x[0] for x in r])
    except Exception as e:
        out.append(["ERR:"+type(e).__name__])
json.dump(out, open(sys.argv[2],'w'))
print("listo", len(out))
