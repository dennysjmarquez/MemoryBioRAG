import sqlite3

db_path = "MemoryBioRAG_Data/memory_biorag.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("--- Últimos 5 mensajes en 'comunicaciones' ---")
try:
    cursor.execute("SELECT id, origen, destino, contenido, timestamp, leido FROM comunicaciones ORDER BY timestamp DESC LIMIT 5")
    for r in cursor.fetchall():
        print(f"ID: {r[0]} | Origen: {r[1]} -> Destino: {r[2]} | Leído: {r[5]}")
        print(f"TS: {r[4]}")
        print(f"Contenido:\n{r[3]}")
        print("-" * 50)
except Exception as e:
    print(f"Error al consultar la tabla: {e}")

conn.close()
