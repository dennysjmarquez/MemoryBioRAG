import sqlite3
import os
import re
import sys
_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _RAIZ)

db_path = os.path.join(_RAIZ, "MemoryBioRAG_Data", "test_memory.db")
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
    return 1 if re.search(r'\b' + re.escape(token_norm) + r'\b', texto_norm) else 0

conn.create_function("PALABRA_COMPLETA", 2, palabra_completa)

print("All concepts in largo_plazo:")
cursor.execute("SELECT rowid, concepto, sinonimos FROM largo_plazo")
for r in cursor.fetchall():
    print(r)

print("\nRunning MATCH on largo_plazo_fts for test_auto_v4:")
cursor.execute("""
    SELECT l.concepto, bm25(largo_plazo_fts)
    FROM largo_plazo_fts f
    JOIN largo_plazo l ON l.rowid = f.rowid
    WHERE largo_plazo_fts MATCH 'test_auto_v4'
""")
for r in cursor.fetchall():
    print(r)

print("\nRunning Fallback Simbólico debug:")
from core.fallback_simbolico import buscar_fallback_simbolico
cursor.execute(
    "SELECT rowid, concepto, contenido, peso_sinaptico, "
    "estado, asociaciones, sinonimos "
    "FROM largo_plazo WHERE estado = 'activo' LIMIT 1000"
)
candidatos = cursor.fetchall()
fb_res = buscar_fallback_simbolico("test_auto_v4", candidatos, umbral=0.60)
for r in fb_res:
    print(r)

conn.close()
