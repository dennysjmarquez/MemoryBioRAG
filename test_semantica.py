import os
import sys

# Setup environment
os.environ["BIORAG_DB_PATH"] = "biorag_test.db"

from core.memory_store import SQLiteMemoryBioRAG
import sqlite3

def test_semantica():
    cerebro = SQLiteMemoryBioRAG(db_path="/tmp/biorag_test.db")
    
    # Simulate an agent learning something with synonyms
    print("Agent calls aprender...")
    cerebro.percibir_corto_plazo(
        concepto="test_nodo_alpha",
        contenido="This is a test node for testing semantic integration.",
        sinonimos="prueba_alpha, test_beta, ensayo_gamma",
        categoria="General"
    )
    
    # Check the semantica table
    print("\nChecking semantica table:")
    cerebro.cursor.execute("SELECT termino, equivalente, peso FROM semantica")
    rows = cerebro.cursor.fetchall()
    if rows:
        for term, equiv, peso in rows:
            print(f"- {term} ↔ {equiv} (Peso: {peso})")
    else:
        print("No entries found in semantica.")

    if len(rows) == 6: # 3 items cross linked bidirectionally (3 combinations * 2 = 6)
        print("\nTest passed! Equivalences generated successfully.")
    else:
        print(f"\nTest failed. Expected 6 rows, got {len(rows)}.")

if __name__ == "__main__":
    test_semantica()
