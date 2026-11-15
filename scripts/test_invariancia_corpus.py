"""
test_invariancia_corpus.py
Experimento de invariancia: F(D, q) == F(D ∪ I, q)
donde I son nodos sin conexión ni términos de consulta.

Mide si añadir nodos irrelevantes desconectados cambia el R@5
o el top-1 del motor.

Uso:
    python3 scripts/test_invariancia_corpus.py [--n-nodos N]

Salida:
    Tabla comparativa A (snapshot original) vs B (snapshot + N nodos irrelevantes)
"""
import sys, os, shutil, sqlite3, argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("BIORAG_NEURONA", "0")
os.environ.setdefault("BIORAG_NO_LOG", "1")
os.environ.setdefault("PYTHONHASHSEED", "0")

parser = argparse.ArgumentParser()
parser.add_argument("--n-nodos", type=int, default=100,
                    help="Número de nodos irrelevantes a añadir en la copia B")
args = parser.parse_args()

SNAP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "snapshots", "qa_escape_qcr_20260811.db")
TMP_A = "/tmp/invariance_A.db"
TMP_B = "/tmp/invariance_B.db"

# --- Preparar bases ---
shutil.copyfile(SNAP, TMP_A)
shutil.copyfile(SNAP, TMP_B)

conB = sqlite3.connect(TMP_B)
estado_activo = "activo"
for i in range(args.n_nodos):
    conB.execute(
        "INSERT INTO largo_plazo (concepto, contenido, peso_sinaptico, estado)"
        " VALUES (?, ?, 0.5, ?)",
        (f"nodo_irrelevante_xyz_{i:04d}",
         f"contenido irrelevante numero {i} sin conexion con nada",
         estado_activo)
    )
conB.commit()
conB.close()

# Verificar
cA = sqlite3.connect(TMP_A)
cB = sqlite3.connect(TMP_B)
nA = cA.execute("SELECT COUNT(*) FROM largo_plazo WHERE estado='activo'").fetchone()[0]
nB = cB.execute("SELECT COUNT(*) FROM largo_plazo WHERE estado='activo'").fetchone()[0]
cA.close()
cB.close()
print(f"A nodos activos: {nA}")
print(f"B nodos activos: {nB}  (+{args.n_nodos} irrelevantes)")

# --- Queries de prueba ---
QUERIES = [
    ("perfil",                                         "dennys-identidad-profunda"),
    ("dimensiones biorag",                             "cuando_usar_dimensiones_biorag"),
    ("arquitectura memoria biorag",                    "arquitectura_memoria_biorag"),
    ("protocolo busquedas biorag automatica",          "protocolo_busqueda_biorag_automatica"),
    ("como funciona biorag sin vectores ml",           "sin_vectores_sin_ml_sin_dependencias"),
    ("regla verificar codigo real antes diagnostico",  "regla_verificar_codigo_real_antes_de_diagnostico"),
    ("biorag version estado",                          "version_actual_biorag"),
    ("principio impacto lateral antes cambiar",        "principio_impacto_lateral_antes_de_cambiar"),
    ("familia oec",                                    "oec_familia_actual"),
    ("sleep cycle consolidacion sueno",                "biorag_v17_0_estado"),
]

# --- Ejecutar búsquedas ---
def run_queries(db_path, queries):
    os.environ["BIORAG_PATH"] = db_path
    for mod in list(sys.modules.keys()):
        if any(x in mod for x in ["memory", "biorag", "core", "calibra",
                                   "neurona", "scoring", "umbral", "ppmi",
                                   "sdm", "sinapsis"]):
            del sys.modules[mod]
    from core.memory_store import SQLiteMemoryBioRAG
    cerebro = SQLiteMemoryBioRAG(db_path)
    results = []
    for query, gold in queries:
        pagina, _total = cerebro.buscar_por_frase(query, limite=5)
        top5 = [row[0] for row in pagina[:5]] if pagina else []
        f5 = gold in top5
        f1 = (top5[0] == gold) if top5 else False
        results.append({
            "q": query, "gold": gold,
            "top1": top5[0] if top5 else "",
            "top5": top5, "f5": f5, "f1": f1,
        })
    cerebro.cerrar_sistema()
    return results

print("\nEjecutando búsquedas en A...", flush=True)
rA = run_queries(TMP_A, QUERIES)
print("Ejecutando búsquedas en B...", flush=True)
rB = run_queries(TMP_B, QUERIES)

# --- Resumen ---
n = len(QUERIES)
h5A = sum(1 for d in rA if d["f5"])
h5B = sum(1 for d in rB if d["f5"])
h1A = sum(1 for d in rA if d["f1"])
h1B = sum(1 for d in rB if d["f1"])

print(f"\n{'='*70}")
print(f"RESULTADO — {args.n_nodos} nodos irrelevantes desconectados añadidos")
print(f"{'='*70}")
print(f"{'Métrica':20s}  {'A (original)':18s}  {'B (+N irrel.)':18s}  {'Delta'}")
print(f"{'─'*70}")
print(f"{'R@5':20s}  {h5A}/{n} ({100*h5A//n}%)       {h5B}/{n} ({100*h5B//n}%)       {h5B-h5A:+d}")
print(f"{'R@1':20s}  {h1A}/{n} ({100*h1A//n}%)       {h1B}/{n} ({100*h1B//n}%)       {h1B-h1A:+d}")

print(f"\n{'─'*70}")
print(f"{'Estado':13s} | {'Query':40s} | A top1")
print(f"{'─'*70}")
cambios = 0
perdidos = 0
for a, b in zip(rA, rB):
    top1_cambio = a["top1"] != b["top1"]
    perdido = a["f5"] and not b["f5"]
    if top1_cambio: cambios += 1
    if perdido: perdidos += 1
    if perdido:
        tag = "⚠️ GOLD_PERDIDO"
    elif top1_cambio:
        tag = "↕  ORDEN_CAMBIO"
    else:
        tag = "✅ IGUAL       "
    print(f"{tag} | {a['q'][:40]:40s} | {a['top1'][:35]}")
    if top1_cambio:
        print(f"{'':13s} |   B top1: {b['top1'][:35]}")

print(f"\n{'='*70}")
print(f"Top-1 cambió:      {cambios}/{n}")
print(f"Gold perdido(R@5): {perdidos}/{n}")
if perdidos == 0:
    verdict = "✅ INVARIANTE — el R@5 no degradó con nodos irrelevantes"
else:
    verdict = f"⚠️  NO INVARIANTE — {perdidos} gold(s) perdidos al añadir nodos irrelevantes"
print(f"\nVEREDICTO: {verdict}")

# Cleanup
os.unlink(TMP_A)
os.unlink(TMP_B)

