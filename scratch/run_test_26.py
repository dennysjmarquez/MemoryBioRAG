import os
import sys

# Add project path to sys.path
project_root = "/mnt/recursos_compartidos_y_otros/MemoryBioRAG"
sys.path.insert(0, project_root)

from core.memory_store import SQLiteMemoryBioRAG

db_path = "/mnt/recursos_compartidos_y_otros/MemoryBioRAG/test_repro.db"
if os.path.exists(db_path):
    os.remove(db_path)

cerebro = SQLiteMemoryBioRAG(db_path=db_path)

# Add category General if not present
cerebro.cursor.execute("INSERT OR IGNORE INTO categories (name) VALUES ('General')")
cerebro.conn.commit()

# Test 26 logic
print("Perceiving...")
cerebro.percibir_corto_plazo("test_auto_v4", "Prueba de autoguardado automatico sin sueno", "v4,auto,test", "General")

print("Consolidating...")
ok = cerebro.consolidar_concepto("test_auto_v4")
print(f"consolidar_concepto() -> {ok}")

print("Checking corto_plazo...")
cerebro.cursor.execute("SELECT concepto FROM corto_plazo WHERE concepto = 'test_auto_v4'")
print("corto_plazo result:", cerebro.cursor.fetchone())

print("Checking largo_plazo...")
cerebro.cursor.execute("SELECT rowid, concepto, contenido, estado FROM largo_plazo WHERE concepto = 'test_auto_v4'")
print("largo_plazo result:", cerebro.cursor.fetchone())

print("Checking FTS5...")
cerebro.cursor.execute("SELECT rowid, concepto, contenido FROM largo_plazo_fts")
print("largo_plazo_fts result:", cerebro.cursor.fetchall())

print("Searching...")
resultados, total = cerebro.buscar_por_frase("test_auto_v4", limite=1)
print(f"Results: {resultados}, Total: {total}")

cerebro.cerrar_sistema()
if os.path.exists(db_path):
    os.remove(db_path)
