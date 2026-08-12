import sqlite3
import numpy as np
from core.ppmi_hybrid_search import IndicesBioRAG, _tokenizar, _coseno

print("Iniciando prototipo de Cerebro Vivo (Resonancia Dimensional)...")
DB_PATH = 'MemoryBioRAG_Data/memory_biorag.db'

# 1. Cargar el índice PPMI+SVD real
print("Cargando índices PPMI+SVD...")
idx = IndicesBioRAG(DB_PATH)

# 2. Cargar las relaciones Concepto <-> Dimensiones
print("Calculando vectores de ADN genético...")
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Agrupar conceptos por dimensión
cur.execute('''
    SELECT ds.id, ds.name, td.nombre, ld.concepto
    FROM largo_plazo_dimensiones ld
    JOIN dimensiones_semanticas ds ON ds.id = ld.dimension_id
    JOIN tipos_dimension td ON td.id = ds.tipo_id
''')
dimension_conceptos = {}
dimension_nombres = {}

for dim_id, dim_name, tipo, concepto in cur.fetchall():
    if dim_id not in dimension_conceptos:
        dimension_conceptos[dim_id] = []
        dimension_nombres[dim_id] = f"{tipo}:{dim_name}"
    dimension_conceptos[dim_id].append(concepto)

# 3. Construir el vector centroide para cada dimensión (ADN latente)
vectores_adn = {}
for dim_id, conceptos in dimension_conceptos.items():
    vecs = []
    for c in conceptos:
        if c in idx.vecs:
            vecs.append(idx.vecs[c])
    if vecs:
        centroide = np.mean(vecs, axis=0)
        vectores_adn[dim_id] = centroide / (np.linalg.norm(centroide) + 1e-10)

print(f"Mapeadas {len(vectores_adn)} dimensiones genéticas al espacio PPMI+SVD.")

# 4. Probar con una query
query = "ser que vive solo y piensa mucho"
print(f"\nQuery: '{query}'")
q_toks = _tokenizar(query)
print(f"Tokens: {q_toks}")

v_q = idx.vector_query(q_toks)

# Inferir ADN de la query
afinidades = []
for dim_id, v_adn in vectores_adn.items():
    sim = _coseno(v_q, v_adn)
    afinidades.append((sim, dim_id, dimension_nombres[dim_id]))

afinidades.sort(reverse=True)
print("\nADN Inferido para la query (Top 5 dimensiones):")
top_dims = [dim_id for sim, dim_id, nombre in afinidades[:5]]
for sim, dim_id, nombre in afinidades[:5]:
    print(f"  [{sim:.4f}] {nombre}")

# 5. Búsqueda por Resonancia Dimensional pura
# Buscar qué nodos tienen esas dimensiones (ignorando texto por completo)
placeholders = ",".join("?" * len(top_dims))
cur.execute(f'''
    SELECT ld.concepto, COUNT(ld.dimension_id) as overlap
    FROM largo_plazo_dimensiones ld
    WHERE ld.dimension_id IN ({placeholders})
    GROUP BY ld.concepto
    ORDER BY overlap DESC
    LIMIT 10
''', top_dims)

print("\nConceptos resonantes recuperados puramente por ADN Dimensional (Cerebro Vivo):")
for concepto, overlap in cur.fetchall():
    print(f"  [{overlap}/5 matches genéticos] {concepto}")

conn.close()
