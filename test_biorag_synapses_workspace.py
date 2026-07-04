import sqlite3

db_path = "MemoryBioRAG_Data/memory_biorag.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

concepto = "compuerta-pre-validacion"

# Simular la consulta SQL con l.estado = 'activo'
print("--- PROBANDO CONSULTA SQL CON ESTADO = 'activo' ---")
query_sql = """
    SELECT l.concepto, l.contenido, l.peso_sinaptico, l.estado, l.asociaciones, s.peso
    FROM sinapsis s
    JOIN largo_plazo l ON l.concepto = s.destino
    WHERE s.origen = ? AND l.estado = 'activo'
    UNION
    SELECT l.concepto, l.contenido, l.peso_sinaptico, l.estado, l.asociaciones, s.peso
    FROM sinapsis s
    JOIN largo_plazo l ON l.concepto = s.origen
    WHERE s.destino = ? AND l.estado = 'activo'
    ORDER BY s.peso DESC
"""
cursor.execute(query_sql, (concepto, concepto))
rows = cursor.fetchall()
print("Resultados de la consulta (con activo):")
for r in rows:
    print(r[0], "->", r[3], "| Peso sinapsis:", r[5])

# Simular la consulta SQL sin filtro de estado (profundo)
print("\n--- PROBANDO CONSULTA SQL PROFUNDA (SIN FILTRO DE ESTADO) ---")
query_sql_deep = """
    SELECT l.concepto, l.contenido, l.peso_sinaptico, l.estado, l.asociaciones, s.peso
    FROM sinapsis s
    JOIN largo_plazo l ON l.concepto = s.destino
    WHERE s.origen = ?
    UNION
    SELECT l.concepto, l.contenido, l.peso_sinaptico, l.estado, l.asociaciones, s.peso
    FROM sinapsis s
    JOIN largo_plazo l ON l.concepto = s.origen
    WHERE s.destino = ?
    ORDER BY s.peso DESC
"""
cursor.execute(query_sql_deep, (concepto, concepto))
rows_deep = cursor.fetchall()
print("Resultados de la consulta (deep):")
for r in rows_deep:
    print(r[0], "->", r[3], "| Peso sinapsis:", r[5])

# Verificar si el concepto destino existe en largo_plazo
print("\n--- COMPROBANDO EXISTENCIA DE DESTINOS EN largo_plazo ---")
destinos = ['identidad-relacion-dennys', 'costo-mecanica-involucramiento', 'criterio-propio-sobre-mandato', 'auto-validacion-riesgo-alucinacion']
for dest in destinos:
    cursor.execute("SELECT concepto, estado FROM largo_plazo WHERE concepto = ?", (dest,))
    res = cursor.fetchall()
    print(dest, "en largo_plazo:", res)

conn.close()
