"""D) ¿Las sinapsis que la hormiguita cortó llevaban a respuestas correctas?

Con las preguntas del autoexamen (respuesta conocida) se mira el top-10 de cada una.
Una arista (semilla -> respuesta) con la semilla en el top-10 y distinta de la respuesta
es una arista ÚTIL en esa pregunta (por ahí un salto traería la respuesta).
Se compara la tasa de aristas útiles entre:
  - sinapsis activas (por tipo),
  - sinapsis que la hormiguita mandó a cuarentena y siguen allí,
  - sinapsis que mandó a cuarentena y luego se restauraron.
Solo lectura sobre una copia del snapshot.
"""
import sys, os, io, json, random, contextlib, collections, time
os.environ["BIORAG_NEURONA"] = "0"
sys.path.insert(0, "/home/user/MemoryBioRAG"); os.chdir("/home/user/MemoryBioRAG")
DB = "/tmp/q/m/b.db"
from core.memory_store import SQLiteMemoryBioRAG
from core.memory.neurona_examen import preguntas
with contextlib.redirect_stdout(io.StringIO()):
    db = SQLiteMemoryBioRAG(DB)

def buscar(q, k=10):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        res = db.buscar_por_frase(q, profundidad="activos", limite=k, ignore_peso_sinaptico=True)
    lista = res[0] if res and isinstance(res[0], list) else res
    return [r[0] for r in lista if isinstance(r, (list, tuple))]

grupos = collections.defaultdict(dict)   # nodo -> {vecino: etiqueta}
def poner(a, b, etq):
    grupos[a].setdefault(b, etq); grupos[b].setdefault(a, etq)
for o, d, t in db.cursor.execute("SELECT origen, destino, tipo FROM sinapsis"):
    poner(o, d, f"activa:{t}")
for o, d, r, tab in db.cursor.execute(
        "SELECT origen, destino, restaurado, tabla_origen FROM sinapsis_cuarentena"):
    poner(o, d, f"cuarentena_{'restaurada' if r else 'vigente'}:{tab}")

oportunidades = collections.Counter()   # aristas que salen de semillas (cualquier destino)
utiles = collections.Counter()          # aristas semilla -> respuesta correcta
activos = [r[0] for r in db.cursor.execute(
    "SELECT concepto FROM largo_plazo WHERE estado='activo' ORDER BY concepto")]
rng = random.Random(7); rng.shuffle(activos)
t0 = time.time(); n = 0
for concepto in activos[:300]:
    f = db.cursor.execute("SELECT contenido, COALESCE(sinonimos,'') FROM largo_plazo WHERE concepto=?",
                          (concepto,)).fetchone()
    for cat, q in preguntas(concepto, f[0], f[1]):
        n += 1
        semillas = [s for s in buscar(q) if s != concepto]
        for s in semillas:
            for v, etq in grupos.get(s, {}).items():
                grupo = etq.split(":")[0]
                oportunidades[grupo] += 1; oportunidades[etq] += 1
                if v == concepto:
                    utiles[grupo] += 1; utiles[etq] += 1
res = {k: dict(oportunidades=oportunidades[k], utiles=utiles[k],
               tasa_por_mil=round(1000 * utiles[k] / oportunidades[k], 2) if oportunidades[k] else None)
       for k in sorted(oportunidades)}
json.dump(dict(preguntas=n, segundos=round(time.time() - t0), grupos=res),
          open("/tmp/q/m/D.json", "w"), ensure_ascii=False, indent=1)
print("D listo", n, round(time.time() - t0), flush=True)
