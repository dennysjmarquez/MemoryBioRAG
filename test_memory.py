import sys
import os
import time

# Añadir el directorio actual al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.memory_store import SQLiteMemoryBioRAG

def test_sistema():
    _biorag_db = os.environ.get('BIORAG_PATH')
    db_test_path = os.path.join(os.path.dirname(_biorag_db), "test_memory.db")
    
    # Limpiar base de datos de pruebas anterior si existe
    if os.path.exists(db_test_path):
        os.remove(db_test_path)
        
    print("--- Inicializando BioRAG SQLite Engine ---")
    cerebro = SQLiteMemoryBioRAG(db_path=db_test_path)
    
    # 1. Registrar percepciones en corto plazo
    print("\n--- 1. Probando Percepciones en Corto Plazo (Memoria de Trabajo) ---")
    cerebro.percibir_corto_plazo("san_cayetano", "Pedir empleo a San Cayetano. La vela dejo la forma de un caballito de mar.")
    cerebro.percibir_corto_plazo("empleo", "Entorno laboral y busqueda de trabajo profesional.")
    cerebro.percibir_corto_plazo("velas", "Velas espirituales de cera y peticiones ceremoniales.")
    
    # Crear asociaciones (sinapsis bidireccionales)
    print("\n--- 2. Estableciendo Sinapsis (Asociaciones) ---")
    cerebro.establecer_asociacion("san_cayetano", "velas")
    cerebro.establecer_asociacion("san_cayetano", "empleo")
    
    # 2. Ejecutar Consolidación (Ciclo de Sueño)
    print("\n--- 3. Consolidando Recuerdos (Ciclo de Sueño) ---")
    cerebro.ciclo_sueno_consolidacion(limite_energia=10.0)
    
    # 3. Buscar recuerdo exacto
    print("\n--- 4. Buscando Recuerdo Exacto ---")
    recuerdo = cerebro.buscar_recuerdo_microsegundos("san_cayetano")
    print(f"Recuerdo evocado: {recuerdo}")
    assert "caballito" in recuerdo, "Error: El contenido del recuerdo exacto no coincide."
    
    # 4. Verificar Spreading Activation (El vecino 'velas' debió subir su peso de 1.0 a 1.05? Bueno, tiene tope de 1.0, pero vamos a ver)
    # Vamos a reducir el peso de 'velas' primero para ver la propagación.
    cerebro.cursor.execute("UPDATE largo_plazo SET peso_sinaptico = 0.5 WHERE concepto = 'velas'")
    cerebro.conn.commit()
    print("\n--- 5. Probando Propagación de Activación (Spreading Activation) ---")
    print("Peso inicial de 'velas': 0.5")
    # Evocar 'san_cayetano' de nuevo para propagar activación a 'velas'
    cerebro.buscar_recuerdo_microsegundos("san_cayetano")
    
    # Consultar nuevo peso de 'velas'
    cerebro.cursor.execute("SELECT peso_sinaptico FROM largo_plazo WHERE concepto = 'velas'")
    nuevo_peso = cerebro.cursor.fetchone()[0]
    print(f"Nuevo peso de 'velas' tras evocar 'san_cayetano': {nuevo_peso}")
    assert nuevo_peso == 0.55, f"Error: La activación propagada falló (esperado 0.55, obtenido {nuevo_peso})"
    
    # 5. Familiaridad Difusa (Jaccard)
    print("\n--- 6. Probando Familiaridad Difusa (Jaccard) ---")
    # Buscar un término con ligeras variaciones
    recuerdo_difuso = cerebro.buscar_recuerdo_microsegundos("sancayetano")
    print(f"Recuerdo evocado con 'sancayetano': {recuerdo_difuso}")
    assert recuerdo_difuso is not None, "Error: La familiaridad difusa no coincidió."
    
    recuerdo_difuso_2 = cerebro.buscar_recuerdo_microsegundos("trabajo_profesional")
    print(f"Recuerdo evocado con 'trabajo_profesional' (Jaccard con 'empleo'): {recuerdo_difuso_2}")
    
    # 6. LTD Decaimiento Pasivo (Pruning)
    print("\n--- 7. Probando LTD (Decaimiento) ---")
    # Forzar el decaimiento de 'empleo' bajándolo a 0.15 y corriendo consolidación sin usarlo
    cerebro.cursor.execute("UPDATE largo_plazo SET peso_sinaptico = 0.15 WHERE concepto = 'empleo'")
    cerebro.conn.commit()
    # Ejecutar consolidación (cero elementos en corto plazo, por lo que 'empleo' decae de 0.15 a 0.10 y se duerme)
    cerebro.ciclo_sueno_consolidacion(limite_energia=10.0)
    
    # Verificar si 'empleo' está dormido
    cerebro.cursor.execute("SELECT estado, peso_sinaptico FROM largo_plazo WHERE concepto = 'empleo'")
    estado, peso = cerebro.cursor.fetchone()
    print(f"Estado de 'empleo' tras LTD: {estado} (Peso: {peso})")
    assert estado == "dormido", f"Error: El recuerdo no se durmió correctamente. Estado actual: {estado}"
    
    # 7. Inhibición Lateral
    print("\n--- 8. Probando Inhibición Lateral Activa ---")
    # Crear muchos nodos artificiales activos de peso 1.0
    for i in range(15):
        cerebro.cursor.execute(f"""
            INSERT OR REPLACE INTO largo_plazo (concepto, contenido, peso_sinaptico, estado, ultimo_acceso)
            VALUES ('nodo_{i}', 'contenido_{i}', 1.0, 'activo', {time.time() - i * 100})
        """)
    cerebro.conn.commit()
    
    # Ejecutar ciclo de sueño con un límite de energía estricto (ejemplo: 5.0)
    # Esto forzará a la inhibición lateral a apagar los nodos más débiles/antiguos
    cerebro.ciclo_sueno_consolidacion(limite_energia=5.0)
    
    # Comprobar cuántos nodos siguen activos
    cerebro.cursor.execute("SELECT COUNT(*) FROM largo_plazo WHERE estado = 'activo'")
    activos = cerebro.cursor.fetchone()[0]
    print(f"Nodos activos restantes tras Inhibición Lateral: {activos}")
    
    # 8. Comunicación entre agentes
    print("\n--- 9. Probando Comunicación entre Agentes ---")
    # Crear nueva DB limpia para la prueba de comunicacion
    os.remove(db_test_path)
    cerebro.conn.close()
    cerebro = SQLiteMemoryBioRAG(db_path=db_test_path)

    cerebro.enviar_comunicado("athena", "hermes", "Mensaje de prueba de Athena a Hermes")
    cerebro.enviar_comunicado("artemis", "todos", "Anuncio para todos los agentes")
    cerebro.enviar_comunicado("hermes", "athena", "Respuesta de Hermes a Athena")

    # Leer todos
    todos = cerebro.leer_comunicados(ultimos=10)
    assert len(todos) == 3, f"Error: deberian haber 3 mensajes, hay {len(todos)}"
    print(f"Mensajes totales: {len(todos)}")

    # Leer no leidos para athena
    no_leidos = cerebro.leer_comunicados(destino="athena", solo_no_leidos=True, ultimos=10)
    print(f"Mensajes no leidos para athena: {len(no_leidos)}")
    assert len(no_leidos) == 2, f"Error: Athena deberia tener 2 no leidos, tiene {len(no_leidos)}"

    # Marcar como leido y verificar
    ids = [m[0] for m in no_leidos]
    cerebro.marcar_como_leido(ids)
    no_leidos_despues = cerebro.leer_comunicados(destino="athena", solo_no_leidos=True, ultimos=10)
    assert len(no_leidos_despues) == 0, f"Error: deberian quedar 0 no leidos, hay {len(no_leidos_despues)}"
    print(f"No leidos tras marcar: {len(no_leidos_despues)}")
    print("--- Comunicacion entre agentes OK ---")

    cerebro.cerrar_sistema()
    print("\n--- ¡Todas las pruebas biológicas completadas con éxito! ---")

if __name__ == "__main__":
    test_sistema()
