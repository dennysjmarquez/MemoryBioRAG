import os
import sys
import time

# Añadir el directorio actual al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.memory_store import SQLiteMemoryBioRAG

def debug_67():
    db_test_path = os.path.abspath("test_memory.db")
    if os.path.exists(db_test_path):
        os.remove(db_test_path)
    
    cerebro = SQLiteMemoryBioRAG(db_path=db_test_path)
    
    print("\n--- 67. Probando Context Window (DEBUG) ---")
    cerebro.percibir_corto_plazo("ctx_nucleo", "Nodo central para prueba de context window", "test,context", "Project")
    cerebro.percibir_corto_plazo("ctx_vecino_a", "Primer vecino conectado al central", "test,context", "Project")
    cerebro.percibir_corto_plazo("ctx_vecino_b", "Segundo vecino conectado al central", "test,context", "Project")
    cerebro.establecer_asociacion("ctx_nucleo", "ctx_vecino_a")
    cerebro.establecer_asociacion("ctx_nucleo", "ctx_vecino_b")
    
    print("--- Corto plazo antes del ciclo de sueño ---")
    cerebro.cursor.execute("SELECT * FROM corto_plazo")
    print(cerebro.cursor.fetchall())

    print("--- Sinapsis antes del ciclo de sueño ---")
    cerebro.cursor.execute("SELECT origen, destino, peso, tipo, ultimo_uso FROM sinapsis")
    for row in cerebro.cursor.fetchall():
        print(row)

    
    # We will run the steps of consolidacion inline to see where the sinapsis are deleted
    print("--- INICIO PASO A PASO CONSOLIDACION ---")
    
    # 1. Transferencia
    cerebro.cursor.execute("SELECT concepto, contenido, sinonimos, categoria FROM corto_plazo")
    recuerdos_sesion = cerebro.cursor.fetchall()
    
    for concepto, contenido, sinonimos, cat_id in recuerdos_sesion:
        cerebro.cursor.execute("SELECT contenido, peso_sinaptico, asociaciones, sinonimos, categoria FROM largo_plazo WHERE concepto = ?", (concepto,))
        existente = cerebro.cursor.fetchone()
        if existente:
            pass
        else:
            ahora = time.time()
            cerebro.cursor.execute("""
                INSERT INTO largo_plazo (concepto, categoria, contenido, peso_sinaptico, estado, asociaciones, ultimo_acceso, sinonimos, creado_en)
                VALUES (?, ?, ?, 1.0, 'activo', '', ?, ?, ?)
            """, (concepto, cat_id or 1, contenido, ahora, sinonimos or "", ahora))
            
    print("Sinapsis después de transferencia:")
    cerebro.cursor.execute("SELECT * FROM sinapsis")
    print(cerebro.cursor.fetchall())
    
    # Auto-vincular
    from core.sinapsis import auto_vincular
    for concepto, contenido, _, _ in recuerdos_sesion:
        auto_vincular(cerebro, concepto, contenido)
        
    print("Sinapsis después de auto_vincular:")
    cerebro.cursor.execute("SELECT * FROM sinapsis")
    print(cerebro.cursor.fetchall())
    
    # Co-ocurrencia
    cerebro._auto_generar_co_ocurrencia(recuerdos_sesion)
    
    print("Sinapsis después de co-ocurrencia:")
    cerebro.cursor.execute("SELECT * FROM sinapsis")
    print(cerebro.cursor.fetchall())
    
    # Decay
    cerebro.cursor.execute("""
        UPDATE sinapsis
        SET peso = ROUND(MAX(0.0, peso * 0.95), 3)
        WHERE ultimo_uso IS NOT NULL
          AND ultimo_uso < strftime('%s', 'now') - 604800
    """)
    cerebro.cursor.execute("DELETE FROM sinapsis WHERE peso < 0.05")
    
    print("Sinapsis después de decay y delete < 0.05:")
    cerebro.cursor.execute("SELECT * FROM sinapsis")
    print(cerebro.cursor.fetchall())
    
    # Poda stale
    try:
        from core.sinapsis import recalcular_similitud_sinapsis, _sincronizar_asociaciones
        cerebro.cursor.execute(
            "SELECT origen, destino, peso FROM sinapsis WHERE tipo IN ('co_ocurrencia', 'co_nombre', 'co_semantica')"
        )
        sinapsis_autos = cerebro.cursor.fetchall()
        parejas_procesadas = set()
        conceptos_afectados = set()
        for origen, destino, peso in sinapsis_autos:
            pareja = tuple(sorted([origen, destino]))
            if pareja in parejas_procesadas:
                continue
            parejas_procesadas.add(pareja)
            nueva_sim = recalcular_similitud_sinapsis(cerebro, origen, destino)
            if nueva_sim < 0.4:
                cerebro.cursor.execute(
                    "DELETE FROM sinapsis WHERE (origen = ? AND destino = ?) OR (origen = ? AND destino = ?)",
                    (origen, destino, destino, origen)
                )
                conceptos_afectados.add(origen)
                conceptos_afectados.add(destino)
    except Exception as e:
        print("Error in pruning:", e)
        
    print("Sinapsis después de poda stale:")
    cerebro.cursor.execute("SELECT * FROM sinapsis")
    print(cerebro.cursor.fetchall())

        
    print("--- Ejecutando búsqueda por frase ---")
    res_ctx, total_ctx = cerebro.buscar_por_frase("central context window", limite=1, context_window=1)
    print("Resultados de búsqueda:", res_ctx)

if __name__ == "__main__":
    debug_67()
