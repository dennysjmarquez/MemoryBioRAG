"""Hace crecer una COPIA del snapshot con recuerdos de relleno reales (no toca el original).
uso: crecer.py <tipo: tema|ajeno> <n> <salida.db> [semilla]"""
import os, sys, re, glob, random, shutil, time, inspect, importlib, collections, unicodedata
R="/home/user/MemoryBioRAG"; SNAP=R+"/snapshots/qa_escape_qcr_20260811.db"
tipo, n, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
seed=int(sys.argv[4]) if len(sys.argv)>4 else 7
STOP=set("""para como esta este esto pero porque cuando donde desde hasta sobre entre todo todos todas cada otro otra otros otras sólo solo tiene tienen puede pueden hace hacer sino según sería será están estos estas aquí ahora antes después mismo misma también nunca siempre about which there their would could should these those other where while after before because being through value values return returns default object""".split())
def slug(s,k=4):
    s=unicodedata.normalize("NFKD",s.lower()); s="".join(ch for ch in s if not unicodedata.combining(ch))
    w=re.findall(r"[a-z0-9]+",s); return "_".join(w[:k])
def claves(p,k=5):
    w=[x for x in re.findall(r"[a-záéíóúñ]{5,}",p.lower()) if x not in STOP]
    return ",".join(x for x,_ in collections.Counter(w).most_common(k))
def tema():
    fs=sorted(f for f in glob.glob(R+"/**/*.md",recursive=True) if "/.git/" not in f)
    vistos=set(); out=[]
    for f in fs:
        t=open(f,encoding="utf-8",errors="ignore").read()
        for p in re.split(r"\n\s*\n",t):
            p=p.strip()
            if len(p)<200 or p.startswith(("|","```")) or p.count("|")>6 or p in vistos: continue
            vistos.add(p); out.append(("doc_"+slug(os.path.basename(f),2), p[:1500]))
    return out
def ajeno():
    out=[]; vistos=set()
    for m in sorted(sys.stdlib_module_names):
        if m.startswith("_") or m in("antigravity","this","idlelib","tkinter","turtle","turtledemo"): continue
        try: mod=importlib.import_module(m)
        except Exception: continue
        for name,obj in inspect.getmembers(mod):
            if not (inspect.isfunction(obj) or inspect.isclass(obj)): continue
            d=inspect.getdoc(obj)
            if d and len(d)>=200 and d not in vistos:
                vistos.add(d); out.append((f"py_{m}_{name}".lower(), d[:1500]))
    return out
pool = tema() if tipo=="tema" else ajeno()
if os.environ.get("LIMPIO")=="1":
    # Excluir párrafos que citan textualmente alguna pregunta de la QA (contaminación)
    import json as _j
    qs=[_j.loads(l)["query"].lower() for l in open(R+"/scripts/casos_qa.jsonl")]
    qs=[q for q in qs if len(q)>=8]
    antes=len(pool); pool=[(b,p) for b,p in pool if not any(q in p.lower() for q in qs)]
    print(f"limpio: {antes-len(pool)} párrafos citaban preguntas de la QA y se excluyeron")
random.Random(seed).shuffle(pool)
if n>len(pool): sys.exit(f"solo hay {len(pool)} textos de tipo {tipo}")
shutil.copy(SNAP,out)
for e in("-wal","-shm"):
    if os.path.exists(out+e): os.remove(out+e)
os.environ["BIORAG_PATH"]=out; os.environ["BIORAG_NO_LOG"]="1"
sys.path.insert(0,R)
from core.memory_store import SQLiteMemoryBioRAG
from core import memory_service as MS
db=SQLiteMemoryBioRAG(out)
t0=time.time(); ok=0
for i,(base,p) in enumerate(pool[:n]):
    c=f"relleno_{tipo}_{i:05d}_{base}_{slug(p,3)}"[:120]
    try:
        MS.aprender(db,c,p,sinonimos=claves(p),categoria="General"); ok+=1
    except Exception as e:
        print("fallo",c,repr(e)[:120])
    if (i+1)%200==0: print(f"  {i+1}/{n} {time.time()-t0:.0f}s",flush=True)
tot=db.cursor.execute("select count(*) from largo_plazo").fetchone()[0]
db.cerrar_sistema()
print(f"LISTO tipo={tipo} insertados={ok}/{n} nodos_totales={tot} {time.time()-t0:.0f}s")
