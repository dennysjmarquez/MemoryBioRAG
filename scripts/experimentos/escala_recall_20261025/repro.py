import os,sys,shutil,sqlite3,importlib
R="/home/user/MemoryBioRAG"; sys.path.insert(0,R)
SNAP=R+"/snapshots/qa_escape_qcr_20260811.db"; tmp="/tmp/v/repro.db"
shutil.copy(SNAP,tmp); os.environ.update(BIORAG_PATH=tmp,BIORAG_NO_LOG="1",BIORAG_NEURONA="0")
from core.memory_store import SQLiteMemoryBioRAG
from core import memory_service as MS
db=SQLiteMemoryBioRAG(tmp)
# Mecanismo 1: UNA nota que cita la pregunta con typos
MS.aprender(db,"nota_fallos_qa_hotspot","Fallo de la QA: la consulta resoluciones timeouts hotspot 5ghzs intels no encontró su respuesta.",sinonimos="qa,fallo")
# Mecanismo 2: 5 notas que comparten palabras con la pregunta, con dimensiones de recuerdos genéricos
dims=[r[0] for r in db.cursor.execute("select dimension_id from largo_plazo_dimensiones where concepto='principio_naturaleza_agente'")]
for i in range(5):
    c=f"nota_firmas_{i}"
    MS.aprender(db,c,f"Apunte {i} sobre firmas digitales en contratos y documentos legales del despacho.",sinonimos="firmas,contratos")
    for d in dims: db.cursor.execute("insert or ignore into largo_plazo_dimensiones(concepto,dimension_id) values(?,?)",(c,d))
db.conn.commit()
for esc in ("0","1"):
    os.environ["BIORAG_ESCALA"]=esc
    for q,oro in [("resoluciones timeouts hotspot 5ghzs intels","resolucion_timeout_hotspot_5ghz_intel"),("principiando firmas cada recuerdando","principio_firma_cada_recuerdo")]:
        db.cursor.execute("update largo_plazo set estado='activo' where concepto=?",(oro,)); db.conn.commit()
        res,_=db.buscar_por_frase(q,profundidad="activos",limite=5,ignore_peso_sinaptico=True)
        n=[r[0] for r in res]
        print("ESCALA",esc,repr(q)[:40],"→ oro en",n.index(oro)+1 if oro in n else None,[x[:28] for x in n])
db.cerrar_sistema()
