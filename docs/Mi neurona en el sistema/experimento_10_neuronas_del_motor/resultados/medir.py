"""Medición exploratoria (solo lectura lógica, copia del snapshot):
A) ruido en la cola: con los casos oficiales de la QA, qué tanto de la lista se podría
   recortar sin perder la respuesta correcta.
B) saltos: preguntas del autoexamen cuya respuesta NO aparece en el top-10, ¿está a 1 o 2
   saltos de sinapsis de lo que sí apareció?
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
    return [(r[0], float(r[4])) for r in lista if isinstance(r, (list, tuple))]

t0 = time.time()
A = []
for linea in open("scripts/casos_qa_baseline_v1.jsonl", encoding="utf-8"):
    c = json.loads(linea)
    if c["categoria"] in ("negativo", "dormido", "ambiguo") or not c.get("concepto_esperado"):
        continue
    top = buscar(c["query"])
    nombres = [n for n, _ in top]
    gold = c["concepto_esperado"]
    A.append(dict(cat=c["categoria"], rank=(nombres.index(gold) + 1) if gold in nombres else None,
                  scores=[s for _, s in top]))
json.dump(A, open("/tmp/q/m/A.json", "w"))
print(f"A: {len(A)} casos en {time.time()-t0:.0f}s", flush=True)

# B) saltos
vec = collections.defaultdict(set)
for o, d, p in db.cursor.execute("SELECT origen, destino, peso FROM sinapsis"):
    vec[o].add(d); vec[d].add(o)
activos = [r[0] for r in db.cursor.execute(
    "SELECT concepto FROM largo_plazo WHERE estado='activo' ORDER BY concepto")]
rng = random.Random(7); rng.shuffle(activos)
B = []
for concepto in activos[:300]:
    fila = db.cursor.execute("SELECT contenido, COALESCE(sinonimos,'') FROM largo_plazo WHERE concepto=?",
                             (concepto,)).fetchone()
    for cat, q in preguntas(concepto, fila[0], fila[1]):
        top = [n for n, _ in buscar(q)]
        if concepto in top:
            B.append(dict(cat=cat, en_top=True)); continue
        semillas = set(top)
        h1 = set().union(*[vec[s] for s in semillas]) - semillas if semillas else set()
        h2 = set().union(*[vec[s] for s in h1]) - semillas - h1 if h1 else set()
        B.append(dict(cat=cat, en_top=False, vacio=not top, h1=concepto in h1, h2=concepto in h2,
                      n_h1=len(h1), n_h2=len(h2)))
json.dump(B, open("/tmp/q/m/B.json", "w"))
print(f"B: {len(B)} preguntas en {time.time()-t0:.0f}s", flush=True)
