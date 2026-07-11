import sqlite3
import os
import re

db_path = "/mnt/recursos_compartidos_y_otros/MemoryBioRAG/test_memory.db"
if not os.path.exists(db_path):
    print("Database not found")
    exit()

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

def palabra_completa(token, texto):
    if not token or not texto:
        return 0
    token_norm = token.lower().replace('_', ' ').replace('-', ' ')
    texto_norm = texto.lower().replace('_', ' ').replace('-', ' ')
    res = 1 if re.search(r'\b' + re.escape(token_norm) + r'\b', texto_norm) else 0
    print(f"PALABRA_COMPLETA({token_norm!r}, {texto_norm!r}) -> {res}")
    return res

conn.create_function("PALABRA_COMPLETA", 2, palabra_completa)

cursor.execute("SELECT rowid, concepto, contenido, estado FROM largo_plazo")
print("largo_plazo records:")
for row in cursor.fetchall():
    print(row)

cursor.execute("SELECT rowid, concepto, contenido FROM largo_plazo_fts")
print("largo_plazo_fts records:")
for row in cursor.fetchall():
    print(row)

# Run a test query:
print("\nRunning FTS5 match query:")
try:
    cursor.execute("""
        SELECT l.rowid, l.concepto, l.contenido, l.peso_sinaptico, l.estado, l.asociaciones
        FROM largo_plazo_fts f
        JOIN largo_plazo l ON l.rowid = f.rowid
        WHERE largo_plazo_fts MATCH ?
    """, ("test_auto_v4",))
    print("FTS5 match without PALABRA_COMPLETA:", cursor.fetchall())
except Exception as e:
    print("FTS5 match failed:", e)

print("\nRunning FTS5 match query with PALABRA_COMPLETA:")
try:
    cursor.execute("""
        SELECT l.rowid, l.concepto, l.contenido, l.peso_sinaptico, l.estado, l.asociaciones
        FROM largo_plazo_fts f
        JOIN largo_plazo l ON l.rowid = f.rowid
        WHERE largo_plazo_fts MATCH ? AND (PALABRA_COMPLETA(?, l.contenido) = 1 OR PALABRA_COMPLETA(?, l.concepto) = 1 OR PALABRA_COMPLETA(?, COALESCE(l.sinonimos, '')) = 1)
    """, ("test_auto_v4", "test_auto_v4", "test_auto_v4", "test_auto_v4"))
    print("FTS5 match with PALABRA_COMPLETA:", cursor.fetchall())
except Exception as e:
    print("FTS5 match with PALABRA_COMPLETA failed:", e)

conn.close()
