"""C) Lo mismo que A pero como llega por el MCP (pool 30 → top 10, peso sináptico,
sustantivos_clave sacados de la consulta) y con preguntas más difíciles:
- casos QA no literales, y
- preguntas del autoexamen (contenido, por tema, sinónimo...) de 150 recuerdos al azar.
"""
import sys, os, io, json, random, contextlib, time
os.environ["BIORAG_NEURONA"] = "0"
sys.path.insert(0, "/home/user/MemoryBioRAG"); os.chdir("/home/user/MemoryBioRAG")
DB = "/tmp/q/m/b.db"
from core.memory_store import SQLiteMemoryBioRAG
from core.memory.neurona_examen import preguntas, sustantivos_de
with contextlib.redirect_stdout(io.StringIO()):
    db = SQLiteMemoryBioRAG(DB)

def buscar(q):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        res = db.buscar_por_frase(q, profundidad="activos", limite=30, convergencia_limite=10,
                                  sustantivos_clave_boost=sustantivos_de(q) or None)
    lista = res[0] if res and isinstance(res[0], list) else res
    return [(r[0], float(r[4])) for r in lista if isinstance(r, (list, tuple))][:10]

def fila(origen, cat, gold, q):
    top = buscar(q)
    nombres = [n for n, _ in top]
    return dict(origen=origen, cat=cat, rank=(nombres.index(gold) + 1) if gold in nombres else None,
                scores=[s for _, s in top])

t0 = time.time()
C = []
for linea in open("scripts/casos_qa_baseline_v1.jsonl", encoding="utf-8"):
    c = json.loads(linea)
    if c["categoria"] in ("negativo", "dormido", "ambiguo", "literal") or not c.get("concepto_esperado"):
        continue
    C.append(fila("qa", c["categoria"], c["concepto_esperado"], c["query"]))
print(f"C-qa: {len(C)} en {time.time()-t0:.0f}s", flush=True)
activos = [r[0] for r in db.cursor.execute(
    "SELECT concepto FROM largo_plazo WHERE estado='activo' ORDER BY concepto")]
rng = random.Random(11); rng.shuffle(activos)
for concepto in activos[:150]:
    f = db.cursor.execute("SELECT contenido, COALESCE(sinonimos,'') FROM largo_plazo WHERE concepto=?",
                          (concepto,)).fetchone()
    for cat, q in preguntas(concepto, f[0], f[1]):
        C.append(fila("examen", cat, concepto, q))
json.dump(C, open("/tmp/q/m/C.json", "w"))
print(f"C: {len(C)} en {time.time()-t0:.0f}s", flush=True)
