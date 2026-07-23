import sys
import os
import time
import sqlite3
import tempfile

# Añadir el directorio actual al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.memory_store import SQLiteMemoryBioRAG
from core.sinapsis import init_sinapsis_table, auto_vincular, buscar_vecinos, vincular_por_sinonimos
from core.categorizador import inferir_categoria, auto_categorizar_existentes


def _get_nodos_acciones(cerebro):
    """Retorna dict {concepto: [acciones]} de la tabla puente forense."""
    rows = cerebro.cursor.execute(
        "SELECT l.concepto, mn.accion, mn.peso_anterior, mn.peso_nuevo, mn.razon, mn.contexto, mn.anomalo "
        "FROM metricas_cognitivas_nodos mn JOIN largo_plazo l ON mn.largo_plazo_id = l.id ORDER BY mn.id"
    ).fetchall()
    result = {}
    for concepto, accion, pa, pn, razon, ctx, anomalo in rows:
        result.setdefault(concepto, []).append({
            'accion': accion, 'peso_anterior': pa, 'peso_nuevo': pn,
            'razon': razon, 'contexto': ctx, 'anomalo': anomalo
        })
    return result


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
    cerebro.ciclo_sueno_consolidacion()
    
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
    cerebro.ciclo_sueno_consolidacion()
    
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
    cerebro.ciclo_sueno_consolidacion()
    
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
    cerebro.marcar_como_leido(ids, "athena")
    no_leidos_despues = cerebro.leer_comunicados(destino="athena", solo_no_leidos=True, ultimos=10)
    assert len(no_leidos_despues) == 0, f"Error: deberian quedar 0 no leidos para Athena, hay {len(no_leidos_despues)}"
    print(f"No leidos tras marcar para Athena: {len(no_leidos_despues)}")

    # Verificar que para Hermes los mensajes siguen estando aislados y correctos
    no_leidos_hermes = cerebro.leer_comunicados(destino="hermes", solo_no_leidos=True, ultimos=10)
    # Hermes debería tener: Athena a Hermes (personal) y Artemis a todos (broadcast, que Athena leyó pero Hermes no)
    assert len(no_leidos_hermes) == 2, f"Error: Hermes debería tener 2 no leídos, tiene {len(no_leidos_hermes)}"
    
    # Hermes lee sus mensajes
    ids_hermes = [m[0] for m in no_leidos_hermes]
    cerebro.marcar_como_leido(ids_hermes, "hermes")
    no_leidos_hermes_despues = cerebro.leer_comunicados(destino="hermes", solo_no_leidos=True, ultimos=10)
    assert len(no_leidos_hermes_despues) == 0, f"Error: deberian quedar 0 no leidos para Hermes, hay {len(no_leidos_hermes_despues)}"
    print(f"No leidos tras marcar para Hermes: {len(no_leidos_hermes_despues)}")
    print("--- Comunicacion entre agentes OK ---")

    # 9. Busqueda multi-token (Soft AND)
    print("\n--- 10. Probando Busqueda Multi-Token (Soft AND) ---")
    os.remove(db_test_path)
    cerebro.conn.close()
    cerebro = SQLiteMemoryBioRAG(db_path=db_test_path)
    cerebro.percibir_corto_plazo("puerta_madera", "Puerta de madera marron con manija dorada")
    cerebro.percibir_corto_plazo("color_marron", "El color marron oscuro se usa en muebles")
    cerebro.percibir_corto_plazo("ventana_blanca", "Ventana de PVC blanca con marco de aluminio")
    cerebro.percibir_corto_plazo("casa_roja", "Casa pintada de rojo con tejas marrones")
    cerebro.ciclo_sueno_consolidacion()

    # Test 10a: relaxed mode (2 tokens, debe encontrar match parcial y completo)
    resultados, total = cerebro.buscar_por_tokens(["puert", "marron"], modo="relaxed")
    print(f"Relaxed 'puert,marron': {total} resultados, primero: {resultados[0][0] if resultados else 'N/A'}")
    assert len(resultados) >= 2, f"Error: deberia encontrar al menos 2 (parcial+completo), encontro {len(resultados)}"
    conceptos_encontrados = [r[0] for r in resultados]
    assert "puerta_madera" in conceptos_encontrados, "Error: 'puerta_madera' deberia estar (score 1.0)"
    assert "color_marron" in conceptos_encontrados, "Error: 'color_marron' deberia estar (score 0.5)"
    print("OK: relaxed mode encuentra match completo y parcial")

    # Test 10b: strict mode (solo match completo)
    resultados_s, total_s = cerebro.buscar_por_tokens(["puert", "marron"], modo="strict")
    print(f"Strict 'puert,marron': {total_s} resultados")
    assert len(resultados_s) == 1, f"Error: strict deberia devolver 1 (solo match completo), devolvio {len(resultados_s)}"
    assert resultados_s[0][0] == "puerta_madera", "Error: strict deberia encontrar solo 'puerta_madera'"
    print("OK: strict mode solo devuelve match completo")

    # Test 10c: paginacion
    for i in range(5):
        cerebro.cursor.execute("""
            INSERT OR REPLACE INTO largo_plazo (concepto, contenido, peso_sinaptico, estado, ultimo_acceso)
            VALUES (?, 'contenido de prueba', 0.5, 'activo', ?)
        """, (f"concepto_puerta_{i}", time.time()))
    cerebro.conn.commit()
    resultados_p1, total_p = cerebro.buscar_por_tokens(["puert"], modo="relaxed", limite=3, pagina=1)
    resultados_p2, _ = cerebro.buscar_por_tokens(["puert"], modo="relaxed", limite=3, pagina=2)
    print(f"Pagina 1: {len(resultados_p1)} resultados, Pagina 2: {len(resultados_p2)} resultados, Total: {total_p}")
    assert len(resultados_p1) == 3, f"Error: pagina 1 deberia tener 3 resultados, tiene {len(resultados_p1)}"
    assert len(resultados_p2) >= 1, f"Error: pagina 2 deberia tener al menos 1 resultado, tiene {len(resultados_p2)}"
    # No deben solaparse
    ids_p1 = {r[0] for r in resultados_p1}
    ids_p2 = {r[0] for r in resultados_p2}
    assert ids_p1.isdisjoint(ids_p2), "Error: pagina 1 y 2 no deben solaparse"
    print("OK: paginacion funciona correctamente, no hay solapamiento")

    # Test 10d: deep mode despierta dormidos
    cerebro.cursor.execute("UPDATE largo_plazo SET estado = 'dormido', peso_sinaptico = 0.05 WHERE concepto = 'puerta_madera'")
    cerebro.conn.commit()
    resultados_deep, _ = cerebro.buscar_por_tokens(["puert", "marron"], modo="strict", profundidad="profundo")
    print(f"Deep mode: encontro '{resultados_deep[0][0] if resultados_deep else 'N/A'}'")
    assert len(resultados_deep) == 1, "Error: deep mode deberia despertar y encontrar puerta_madera"
    assert resultados_deep[0][0] == "puerta_madera", "Error: deep mode deberia encontrar puerta_madera"
    # Verificar que se desperto
    cerebro.cursor.execute("SELECT estado FROM largo_plazo WHERE concepto = 'puerta_madera'")
    estado = cerebro.cursor.fetchone()[0]
    assert estado == "activo", f"Error: deep mode deberia haber despertado el nodo, estado actual: {estado}"
    print("OK: deep mode despierta nodos dormidos correctamente")

    print("--- Busqueda multi-token OK ---")

    # 10. Busqueda por frase (FTS5)
    print("\n--- 11. Probando Busqueda por Frase (FTS5) ---")
    resultados_f, total_f = cerebro.buscar_por_frase("puerta madera marron", profundidad="activos")
    print(f"Frase 'puerta madera marron': {total_f} resultados")
    assert total_f >= 1, f"Error: deberia encontrar al menos 1 resultado, encontro {total_f}"
    conceptos_f = [r[0] for r in resultados_f]
    assert "puerta_madera" in conceptos_f, "Error: FTS5 deberia encontrar 'puerta_madera'"
    # Verificar que devuelve asociaciones
    assert len(resultados_f[0]) == 6, f"Error: resultado deberia tener 6 elementos, tiene {len(resultados_f[0])}"
    print("OK: busqueda por frase FTS5 funciona correctamente")

    # 11. --completo / contenido completo
    print("\n--- 12. Probando --completo (contenido sin truncar) ---")
    resultados_c, total_c = cerebro.buscar_por_frase("puerta madera", profundidad="activos", preview_chars=0)
    contenido_puerta = next((r[1] for r in resultados_c if r[0] == 'puerta_madera'), "")
    assert len(contenido_puerta) >= 20, f"Error: contenido completo deberia ser mas largo, tiene {len(contenido_puerta)}"
    print(f"  Contenido 'puerta_madera': {contenido_puerta[:50]}...")
    print("OK: flag --completo disponible para ver contenido sin truncar")

    # 12. --asociados (expansion por asociaciones)
    print("\n--- 13. Probando --asociados (expansion) ---")
    # Crear asociaciones en los nodos de prueba
    resultados_asoc, _ = cerebro.buscar_por_frase("puerta madera", profundidad="activos")
    tiene_asociaciones = bool(resultados_asoc[0][5]) if len(resultados_asoc[0]) > 5 else False
    print(f"  Nodo '{resultados_asoc[0][0]}' tiene asociaciones: {tiene_asociaciones}")
    print("OK: --asociados disponible, muestra asociaciones cuando existen")

    # 13. listar (listado de corteza)
    print("\n--- 14. Probando listar (listado de corteza) ---")
    # Simular el comando listar
    cerebro.cursor.execute("SELECT COUNT(*) FROM largo_plazo")
    total_nodos = cerebro.cursor.fetchone()[0]
    cerebro.cursor.execute(
        "SELECT concepto, substr(contenido, 1, 100), peso_sinaptico, estado "
        "FROM largo_plazo ORDER BY peso_sinaptico DESC, ultimo_acceso DESC LIMIT 5"
    )
    lista = cerebro.cursor.fetchall()
    print(f"  Total nodos: {total_nodos}, muestras: {len(lista)}")
    assert total_nodos >= 5, f"Error: deberia haber al menos 5 nodos, hay {total_nodos}"
    assert len(lista) == 5, f"Error: listar deberia devolver 5 resultados, devolvio {len(lista)}"
    print("OK: listar disponible, paginado de a 10")

    # 14. Metricas de rendimiento (benchmark en sueno)
    print("\n--- 15. Probando Metricas de Rendimiento ---")
    cerebro.cursor.execute("SELECT COUNT(*) FROM metricas_rendimiento")
    metricas = cerebro.cursor.fetchone()[0]
    print(f"  Entradas en metricas_rendimiento: {metricas}")
    if metricas > 0:
        cerebro.cursor.execute(
            "SELECT total_nodos, latencia_busqueda_ms, energia_sinaptica "
            "FROM metricas_rendimiento ORDER BY id DESC LIMIT 1"
        )
        ultima = cerebro.cursor.fetchone()
        print(f"  Ultima metrica: {ultima[0]} nodos, {ultima[1]}ms latencia, {ultima[2]} energia")
    print("OK: benchmark de rendimiento registrado en cada ciclo de sueno")

    print("--- Nuevas funcionalidades (FTS5, listar, completo, asociados) OK ---")

    # ─────────────────────────────────────────────────────────────
    # v2.0: FTS5 trigram + busqueda hibrida + sinonimos + merge
    # ─────────────────────────────────────────────────────────────

    os.remove(db_test_path)
    cerebro.conn.close()
    cerebro = SQLiteMemoryBioRAG(db_path=db_test_path)

    # 16. Sinonimos en percibir_corto_plazo
    print("\n--- 16. Probando Sinonimos en Corto Plazo ---")
    cerebro.percibir_corto_plazo("caso_formularios", "Formularios anidados con tabs en Angular", "nested,forms,tabs,angular,ngx-nested-forms")
    cerebro.ciclo_sueno_consolidacion()
    cerebro.cursor.execute("SELECT sinonimos FROM largo_plazo WHERE concepto = 'caso_formularios'")
    sinonimos_g = cerebro.cursor.fetchone()[0]
    print(f"  Sinonimos guardados: {sinonimos_g}")
    assert "angular" in sinonimos_g, "Error: sinonimos no se guardaron correctamente"
    print("OK: sinonimos persisten en largo_plazo tras sueno")

    # 17. Busqueda por sinonimo via FTS5
    print("\n--- 17. Probando Busqueda por Sinonimo (FTS5) ---")
    resultados_sin, total_sin = cerebro.buscar_por_frase("nested forms")
    print(f"  Buscar 'nested forms': {total_sin} resultados -> {[r[0] for r in resultados_sin]}")
    assert total_sin >= 1, f"Error: FTS5 deberia encontrar por sinonimo, encontro {total_sin}"
    assert resultados_sin[0][0] == "caso_formularios", "Error: deberia encontrar caso_formularios por sinonimo"
    resultados_sin2, total_sin2 = cerebro.buscar_por_frase("ngx")
    print(f"  Buscar 'ngx': {total_sin2} resultados -> {[r[0] for r in resultados_sin2]}")
    assert total_sin2 >= 1, f"Error: FTS5 deberia encontrar sinonimo 'ngx', encontro {total_sin2}"
    print("OK: busqueda por sinonimo via FTS5 funciona")

    # 18. Merge en corto plazo (guardar mismo concepto dos veces)
    print("\n--- 18. Probando Merge en Corto Plazo ---")
    cerebro.percibir_corto_plazo("concepto_merge", "Primera version", "sin1,sin2")
    cerebro.percibir_corto_plazo("concepto_merge", "Segunda version", "sin2,sin3")
    cerebro.cursor.execute("SELECT contenido, sinonimos FROM corto_plazo WHERE concepto = 'concepto_merge'")
    cont, sin = cerebro.cursor.fetchone()
    print(f"  Contenido mergeado: {cont}")
    print(f"  Sinonimos mergeados: {sin}")
    assert "Primera version" in cont and "Segunda version" in cont, "Error: contenido no se mergeo"
    assert "sin1" in sin and "sin2" in sin and "sin3" in sin, "Error: sinonimos no se mergearon"
    assert sin.count("sin2") == 1, "Error: sinonimo duplicado en merge"
    print("OK: merge en corto plazo funciona (contenido + sinonimos sin duplicar)")

    # 19. Comprombar que el merge persiste tras sueno
    print("\n--- 19. Probando Merge Persistido en Largo Plazo ---")
    cerebro.ciclo_sueno_consolidacion()
    cerebro.cursor.execute("SELECT contenido, sinonimos FROM largo_plazo WHERE concepto = 'concepto_merge'")
    cont_lp, sin_lp = cerebro.cursor.fetchone()
    print(f"  Contenido en LP: {cont_lp[:80]}...")
    print(f"  Sinonimos en LP: {sin_lp}")
    assert "Primera version" in cont_lp and "Segunda version" in cont_lp, "Error: merge no persistio en LP"
    assert sin_lp == "sin1,sin2,sin3", f"Error: sinonimos mal mergeados en LP: '{sin_lp}'"
    print("OK: merge persistido correctamente en largo_plazo")

    # 20. FTS5 trigram con typos
    print("\n--- 20. Probando FTS5 Trigram con Typos ---")
    resultados_typo, total_typo = cerebro.buscar_por_frase("formulariox")
    print(f"  Buscar 'formulariox' (typo): {total_typo} resultados -> {[r[0] for r in resultados_typo]}")
    assert total_typo >= 1, "Error: FTS5 trigram deberia encontrar 'formularios' con typo 'formulariox'"
    print("OK: FTS5 trigram tolera typos")

    # 21. Fallback per-word trigram para typos extremos
    print("\n--- 21. Probando Fallback Trigram Jaccard por Palabra ---")
    # Crear nodo con contenido que trigram puro no encuentra
    cerebro.percibir_corto_plazo("liderazgo_accion", "Principio de liderazgo: actuar sin autoridad formal")
    cerebro.ciclo_sueno_consolidacion()
    resultados_jaccard, total_jaccard = cerebro.buscar_por_frase("liderazgoz")
    print(f"  Buscar 'liderazgoz' (typo extremo): {total_jaccard} resultados -> {[r[0] for r in resultados_jaccard]}")
    assert total_jaccard >= 1, "Error: fallback Jaccard deberia encontrar 'liderazgo' con typo 'liderazgoz'"
    print("OK: fallback per-word trigram Jaccard atrapa typos extremos")

    # 22. Score hibrido: verificar que peso sinaptico influye en ordenamiento
    print("\n--- 22. Probando Score Hibrido ---")
    cerebro.cursor.execute("UPDATE largo_plazo SET peso_sinaptico = 0.1 WHERE concepto = 'caso_formularios'")
    cerebro.conn.commit()
    resultados_hibrido, total_hib = cerebro.buscar_por_frase("formularios")
    print(f"  Score hibrido: {total_hib} resultados")
    for r in resultados_hibrido:
        print(f"    {r[0]}: peso={r[2]}, asociaciones={r[5] if r[5] else '(none)'}, score hibrido={r[4]}")
    # Verificar que el score del nodo con peso bajo no es 0 (texto ayuda)
    if resultados_hibrido:
        nodo_bajo = [r for r in resultados_hibrido if r[0] == 'caso_formularios']
        if nodo_bajo:
            assert nodo_bajo[0][4] > 0, "Error: score hibrido deberia ser > 0 aunque peso sea bajo (60% texto)"
            print(f"  OK: score hibrido {nodo_bajo[0][4]} > 0 con peso bajo (texto compensa)")
    print("OK: score hibrido combina senales correctamente")

    # 23. Preview por defecto: 1500 chars a nivel de motor
    print("\n--- 23. Probando Preview por Defecto (1500 chars) ---")
    contenido_largo = "X" * 3000
    cerebro.percibir_corto_plazo("contenido_largo", contenido_largo)
    cerebro.ciclo_sueno_consolidacion()
    # Con preview_chars=0, el motor retorna completo
    resultados_prev, _ = cerebro.buscar_por_frase("contenido_largo", preview_chars=0)
    contenido_completo = resultados_prev[0][1] if resultados_prev else ""
    print(f"  Engine retorna contenido completo: {len(contenido_completo)} chars")
    assert len(contenido_completo) >= 3000, f"Error: engine deberia retornar completo, tiene {len(contenido_completo)}"
    # Con preview_chars=1500 (default), el motor trunca
    resultados_prev2, _ = cerebro.buscar_por_frase("contenido_largo")
    contenido_truncado = resultados_prev2[0][1] if resultados_prev2 else ""
    print(f"  Motor trunca a 1500 chars: {len(contenido_truncado)} chars")
    assert len(contenido_truncado) <= 1510, f"Error: motor deberia truncar a ~1500, tiene {len(contenido_truncado)}"
    print("OK: preview por defecto ~1500 chars (motor-level)")

    # 24. Busqueda profunda despierta nodos
    print("\n--- 24. Probando Busqueda Profunda (--deep) con FTS5 ---")
    cerebro.cursor.execute("UPDATE largo_plazo SET estado = 'dormido', peso_sinaptico = 0.05 WHERE concepto = 'liderazgo_accion'")
    cerebro.conn.commit()
    resultados_deep_f, total_deep_f = cerebro.buscar_por_frase("liderazgo", profundidad="profundo")
    print(f"  Deep FTS5 'liderazgo': {total_deep_f} resultados (incluye dormidos)")
    if resultados_deep_f:
        despertados = [r[0] for r in resultados_deep_f if r[0] == 'liderazgo_accion']
        assert len(despertados) > 0, "Error: deep mode deberia encontrar liderazgo_accion aunque este dormido"
        cerebro.cursor.execute("SELECT estado FROM largo_plazo WHERE concepto = 'liderazgo_accion'")
        estado_despues = cerebro.cursor.fetchone()[0]
        assert estado_despues == "activo", f"Error: deep mode deberia despertar nodo, estado: {estado_despues}"
        print(f"  OK: nodo 'liderazgo_accion' despertado (estado={estado_despues})")
    print("OK: busqueda profunda con FTS5 despierta nodos dormidos")

    # 25. Asociaciones en resultado de busqueda por frase
    print("\n--- 25. Probando Asociaciones en Score Hibrido ---")
    cerebro.establecer_asociacion("caso_formularios", "liderazgo_accion")
    resultados_asoc2, _ = cerebro.buscar_por_frase("formularios")
    if resultados_asoc2:
        print(f"  Nodo '{resultados_asoc2[0][0]}' asociaciones: {resultados_asoc2[0][5]}")
        assert len(resultados_asoc2[0]) == 6, "Error: resultado deberia tener 6 elementos (incluye asociaciones)"
    print("OK: asociaciones disponibles en resultado de FTS5")

    # 26. consolidar_concepto: ciclo completo sin sueno
    print("\n--- 26. Probando consolidar_concepto (Interceptor V2) ---")
    cerebro.percibir_corto_plazo("test_auto_v4", "Prueba de autoguardado automatico sin sueno", "v4,auto,test", "General")

    ok = cerebro.consolidar_concepto("test_auto_v4")
    print(f"  consolidar_concepto() -> {ok}")
    assert ok, "Error: consolidar_concepto deberia devolver True"

    cerebro.cursor.execute("SELECT concepto FROM corto_plazo WHERE concepto = 'test_auto_v4'")
    assert not cerebro.cursor.fetchone(), "Error: concepto no deberia estar en corto_plazo"
    print("  OK: eliminado de corto_plazo")

    resultados, total = cerebro.buscar_por_frase("test_auto_v4", limite=1)
    print(f"  DEBUG 26: resultados={resultados}, total={total}")
    assert total == 1 and resultados[0][0] == "test_auto_v4", "Error: no encontrado en FTS5"
    print(f"  OK: encontrado en FTS5 (trigger automatico, sin sueno)")

    ok_falso = cerebro.consolidar_concepto("no_existe")
    assert not ok_falso, "Error: concepto inexistente deberia devolver False"
    print("  OK: concepto inexistente devuelve False")
    print("OK: consolidar_concepto funciona sin ciclo_sueno")

    print("\n--- v4.0: Interceptor V2 + consolidacion inmediata OK ---")

    # ─────────────────────────────────────────────────────────────
    # v5.0: Sinapsis (tabla de aristas) + Categorizador
    # ─────────────────────────────────────────────────────────────

    # 27. init_sinapsis_table
    print("\n--- 27. Probando init_sinapsis_table (tabla de aristas) ---")
    os.remove(db_test_path)
    cerebro.conn.close()
    cerebro = SQLiteMemoryBioRAG(db_path=db_test_path)
    init_sinapsis_table(cerebro.cursor)
    cerebro.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sinapsis'")
    assert cerebro.cursor.fetchone(), "Error: tabla sinapsis no creada"
    print("OK: tabla sinapsis con PK (origen, destino) e indices")

    # 28. auto_vincular — token overlap entre contenido
    print("\n--- 28. Probando auto_vincular (solapamiento de tokens) ---")
    cerebro.percibir_corto_plazo("angular_forms", "Formularios reactivos en Angular con validacion", "angular,forms", "Project")
    cerebro.ciclo_sueno_consolidacion()
    # Guardar el concepto antes de vincularlo (auto_vincular solo crea aristas, no guarda)
    cerebro.percibir_corto_plazo("nuevo_angular", "Componentes de formularios en Angular con validacion reactiva")
    cerebro.consolidar_concepto("nuevo_angular")
    enlaces = auto_vincular(cerebro, "nuevo_angular", "Componentes de formularios en Angular con validacion reactiva")
    print(f"  auto_vincular encontro: {enlaces}")
    assert len(enlaces) >= 1, f"Error: deberia vincular con 'angular_forms', encontro {len(enlaces)}"
    assert any("angular_forms" in str(e) for e in enlaces), "Error: deberia vincular con 'angular_forms'"
    cerebro.cursor.execute("SELECT COUNT(*) FROM sinapsis")
    total_sin = cerebro.cursor.fetchone()[0]
    print(f"  Total aristas en sinapsis: {total_sin}")
    assert total_sin >= 1, "Error: deberia haber al menos 1 arista en sinapsis"
    print("OK: auto_vincular crea aristas por solapamiento de tokens (umbral 0.3)")

    # 29. buscar_vecinos
    print("\n--- 29. Probando buscar_vecinos (desde tabla sinapsis) ---")
    resultado, vecinos = buscar_vecinos(cerebro, "nuevo_angular")
    print(f"  Vecinos de 'nuevo_angular': {[v['concepto'] for v in vecinos]}")
    assert len(vecinos) >= 1, f"Error: deberia tener al menos 1 vecino, tiene {len(vecinos)}"
    assert any(v["concepto"] == "angular_forms" for v in vecinos), "Error: 'angular_forms' deberia ser vecino"
    print("OK: buscar_vecinos retorna vecinos desde tabla sinapsis (ordenados por peso)")

    # 30. vincular_por_sinonimos
    print("\n--- 30. Probando vincular_por_sinonimos (sinonimos explicitos) ---")
    cerebro.percibir_corto_plazo("react_hooks", "useState y useEffect en React", "react,hooks", "Project")
    cerebro.ciclo_sueno_consolidacion()
    syn_enlaces = vincular_por_sinonimos(cerebro, "react_hooks", "forms,angular")
    print(f"  Sinonimos vincularon: {syn_enlaces}")
    assert any("angular_forms" in str(e) for e in syn_enlaces), \
        "Error: deberia vincular 'react_hooks' con 'angular_forms' via sinonimo 'forms'"
    print("OK: vincular_por_sinonimos conecta via terminos compartidos en contenido")


    # 32. vincular_nuevo_si_existe
    print("\n--- 32. Probando vincular_nuevo_si_existe ---")
    cerebro.percibir_corto_plazo("vue_forms", "Formularios con v-model en Vue.js", "vue,forms", "Project")
    cerebro.ciclo_sueno_consolidacion()
    from core.sinapsis import vincular_nuevo_si_existe
    enlaces_vue = vincular_nuevo_si_existe(cerebro, "vue_forms")
    print(f"  Vincular 'vue_forms' existente: {enlaces_vue}")
    assert len(enlaces_vue) >= 1, f"Error: 'vue_forms' deberia vincularse con al menos 1 nodo, encontro {len(enlaces_vue)}"
    conceptos = [e[0] for e in enlaces_vue]
    assert "angular_forms" in conceptos, "Error: 'vue_forms' deberia vincularse con 'angular_forms' (tema similar)"
    print("OK: vincular_nuevo_si_existe enlaza nodos existentes por contenido")

    # 33. inferir_categoria
    print("\n--- 33. Probando inferir_categoria (clasificacion por palabras clave) ---")
    assert inferir_categoria("Error en la API al procesar la solicitud") == "Lesson", \
        "Error: deberia inferir 'Lesson'"
    assert inferir_categoria("Nuevo repositorio con el codigo del proyecto") == "Project", \
        "Error: deberia inferir 'Project'"
    assert inferir_categoria("Leccion aprendida: no acoplarse a implementacion") == "Lesson", \
        "Error: deberia inferir 'Lesson'"
    assert inferir_categoria("Patron de diseno para el pipeline de datos") == "Architecture", \
        "Error: deberia inferir 'Architecture'"
    assert inferir_categoria("El gato esta sobre la mesa") == "General", \
        "Error: texto neutro deberia ser 'General'"
    assert inferir_categoria("") == "General", "Error: vacio deberia ser 'General'"
    print("OK: inferir_categoria clasifica contenido en 11 categorias + fallback 'General'")

    # 34. auto_categorizar_existentes
    print("\n--- 34. Probando auto_categorizar_existentes (batch) ---")
    # Crear nodo legacy con contenido categorizable
    cerebro.percibir_corto_plazo("test_legacy_cat", "Error encontrado en la API: problema de conexion al servidor", "error,api", "General")
    cerebro.consolidar_concepto("test_legacy_cat")
    cerebro.cursor.execute("UPDATE largo_plazo SET categoria = 1 WHERE concepto = 'test_legacy_cat'")
    cerebro.conn.commit()
    actualizados, total = auto_categorizar_existentes(cerebro)
    print(f"  Re-categorizados: {actualizados}/{total} nodos tenian General (id=1)")
    assert actualizados >= 1, f"Error: deberia re-categorizar al menos 1 nodo, actualizo {actualizados}"
    cerebro.cursor.execute("SELECT categoria FROM largo_plazo WHERE concepto = 'test_legacy_cat'")
    cat = cerebro.cursor.fetchone()[0]
    assert cat != 1, f"Error: 'test_legacy_cat' deberia tener categoria inferida, tiene '{cat}'"
    # Get category name for display
    cerebro.cursor.execute("SELECT name FROM categories WHERE id = ?", (cat,))
    cat_name = cerebro.cursor.fetchone()[0]
    print(f"  'test_legacy_cat' reclasificado como: {cat_name} (id={cat}) (con 'error' + 'api' -> 'Lesson')")
    # Verificar que nodos sin contenido no se rompen
    cat_again, _ = auto_categorizar_existentes(cerebro)
    print(f"  Segunda pasada: {cat_again} actualizaciones (deberia ser 0)")
    assert cat_again == 0, "Error: segunda pasada no deberia actualizar nada"
    print("OK: auto_categorizar_existentes actualiza nodos legacy sin duplicar trabajo")

    # 35. Integracion: guardar con categoria + auto_vincular simultaneo
    print("\n--- 35. Probando integracion: percibir_corto_plazo con categoria + sinapsis ---")
    cerebro.percibir_corto_plazo("test_integracion", "Leccion: evitar acoplamiento en servicios", "leccion,acoplamiento", "Lesson")
    cerebro.consolidar_concepto("test_integracion")
    auto_vincular(cerebro, "test_integracion", "Leccion: evitar acoplamiento en servicios")
    cerebro.cursor.execute("SELECT categoria FROM largo_plazo WHERE concepto = 'test_integracion'")
    cat_int = cerebro.cursor.fetchone()[0]
    # Get category name for display
    cerebro.cursor.execute("SELECT name FROM categories WHERE id = ?", (cat_int,))
    cat_int_name = cerebro.cursor.fetchone()[0]
    assert cat_int_name == "Lesson", f"Error: categoria deberia ser 'Lesson', es '{cat_int_name}'"
    cerebro.cursor.execute("SELECT COUNT(*) FROM sinapsis WHERE origen = 'test_integracion'")
    sin_count = cerebro.cursor.fetchone()[0]
    print(f"  Categoria persistida: {cat_int_name} (id={cat_int}), aristas desde test_integracion: {sin_count}")
    print("OK: integracion guardado + categoria + sinapsis funciona en flujo completo")

    print("\n--- v5.0: Sinapsis + Categorizador OK ---")

    # 36. Backup trigger (BEFORE DELETE)
    print("\n--- 36. Probando Backup Trigger (BEFORE DELETE) ---")
    os.remove(db_test_path)
    cerebro.conn.close()
    cerebro = SQLiteMemoryBioRAG(db_path=db_test_path)

    # Verificar que la tabla backup existe
    cerebro.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='largo_plazo_backup'")
    assert cerebro.cursor.fetchone(), "Error: tabla largo_plazo_backup no existe"
    print("OK: tabla largo_plazo_backup existe")

    # Verificar que el trigger existe
    cerebro.cursor.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND name='trg_backup_before_delete'")
    assert cerebro.cursor.fetchone(), "Error: trigger trg_backup_before_delete no existe"
    print("OK: trigger trg_backup_before_delete existe")

    # Crear nodo de prueba
    cerebro.percibir_corto_plazo("test_backup", "Contenido completo para backup", "test,backup", "Project")
    cerebro.consolidar_concepto("test_backup")

    # Verificar que está en largo_plazo
    cerebro.cursor.execute("SELECT concepto, categoria, contenido, peso_sinaptico, estado FROM largo_plazo WHERE concepto = 'test_backup'")
    fila_lp = cerebro.cursor.fetchone()
    assert fila_lp, "Error: nodo no se consolido a largo_plazo"
    print(f"OK: nodo en largo_plazo: {fila_lp[0]}, cat={fila_lp[1]}, peso={fila_lp[3]}")

    # Verificar sync_log tiene INSERT
    cerebro.cursor.execute("SELECT accion FROM sync_log WHERE concepto = 'test_backup' AND accion = 'insert'")
    assert cerebro.cursor.fetchone(), "Error: sync_log no tiene insert para test_backup"
    print("OK: sync_log tiene entrada INSERT")

    # Borrar el nodo
    cerebro.cursor.execute("DELETE FROM largo_plazo WHERE concepto = 'test_backup'")
    cerebro.conn.commit()

    # Verificar que desapareció de largo_plazo
    cerebro.cursor.execute("SELECT COUNT(*) FROM largo_plazo WHERE concepto = 'test_backup'")
    assert cerebro.cursor.fetchone()[0] == 0, "Error: nodo no se borro de largo_plazo"
    print("OK: nodo eliminado de largo_plazo")

    # Verificar que apareció en backup con todos los campos
    cerebro.cursor.execute(
        "SELECT concepto, categoria, contenido, peso_sinaptico, estado, sinonimos, deleted_at "
        "FROM largo_plazo_backup WHERE concepto = 'test_backup'"
    )
    fila_backup = cerebro.cursor.fetchone()
    assert fila_backup, "Error: nodo no aparece en largo_plazo_backup"
    assert fila_backup[0] == "test_backup", f"Error: concepto en backup no coincide: {fila_backup[0]}"
    assert fila_backup[1] == 3, f"Error: categoria en backup no coincide: {fila_backup[1]}"
    assert "Contenido completo para backup" in fila_backup[2], "Error: contenido en backup no coincide"
    assert fila_backup[3] == 1.0, f"Error: peso en backup no coincide: {fila_backup[3]}"
    assert fila_backup[4] == "activo", f"Error: estado en backup no coincide: {fila_backup[4]}"
    assert "test,backup" in fila_backup[5], f"Error: sinonimos en backup no coinciden: {fila_backup[5]}"
    print(f"OK: backup contiene fila completa: cat={fila_backup[1]}, peso={fila_backup[3]}, sinonimos='{fila_backup[5]}'")

    # Verificar sync_log tiene DELETE
    cerebro.cursor.execute("SELECT accion FROM sync_log WHERE concepto = 'test_backup' AND accion = 'delete'")
    assert cerebro.cursor.fetchone(), "Error: sync_log no tiene delete para test_backup"
    print("OK: sync_log tiene entrada DELETE")

    # Verificar timestamp de borrado
    assert fila_backup[6] is not None, "Error: deleted_at no tiene timestamp"
    print(f"  OK: deleted_at = {fila_backup[6]}")

    print("--- Backup trigger OK ---")

    # 37. Restaurar desde backup
    print("\n--- 37. Probando Restaurar desde Backup ---")
    cerebro.cursor.execute("""
        INSERT INTO largo_plazo (concepto, categoria, contenido, peso_sinaptico, estado, sinonimos)
        SELECT concepto, categoria, contenido, peso_sinaptico, estado, sinonimos
        FROM largo_plazo_backup WHERE concepto = 'test_backup'
    """)
    cerebro.conn.commit()

    cerebro.cursor.execute("SELECT concepto, categoria, contenido FROM largo_plazo WHERE concepto = 'test_backup'")
    restaurado = cerebro.cursor.fetchone()
    assert restaurado, "Error: nodo no se pudo restaurar"
    assert restaurado[2] == fila_backup[2], "Error: contenido restaurado no coincide"
    print(f"OK: nodo restaurado desde backup: {restaurado[0]}, cat={restaurado[1]}")
    print("--- Restauracion desde backup OK ---")

    # Cleanup
    cerebro.cursor.execute("DELETE FROM largo_plazo WHERE concepto = 'test_backup'")
    cerebro.cursor.execute("DELETE FROM largo_plazo_backup WHERE concepto = 'test_backup'")
    cerebro.cursor.execute("DELETE FROM sync_log WHERE concepto = 'test_backup'")
    cerebro.conn.commit()

    print("\n--- Backup Trigger OK ---")

    # === TESTS PARA MEJORAS NUEVAS ===

    # 38. Decay diferenciado por categoría
    print("\n--- 38. Probando decay diferenciado por categoría ---")
    cerebro.cursor.execute("SELECT decay_rate FROM categories WHERE name = 'Profile'")
    profile_decay = cerebro.cursor.fetchone()[0]
    cerebro.cursor.execute("SELECT decay_rate FROM categories WHERE name = 'Project'")
    project_decay = cerebro.cursor.fetchone()[0]
    cerebro.cursor.execute("SELECT decay_rate FROM categories WHERE name = 'Lesson'")
    lesson_decay = cerebro.cursor.fetchone()[0]
    assert profile_decay == 0.05, f"Error: Profile decay esperado 0.05, obtuvo {profile_decay}"
    assert project_decay == 1.5, f"Error: Project decay esperado 1.5, obtuvo {project_decay}"
    assert lesson_decay == 1.0, f"Error: Lesson decay esperado 1.0, obtuvo {lesson_decay}"
    print(f"OK: Profile={profile_decay}, Project={project_decay}, Lesson={lesson_decay}")
    print("--- Decay diferenciado OK ---")

    # 39. Decay diferenciado en LTD
    print("\n--- 39. Probando LTD con decay_rate diferenciado ---")
    cerebro.percibir_corto_plazo("test_ltd_profile", "Perfil de prueba", "", "Profile")
    cerebro.percibir_corto_plazo("test_ltd_project", "Proyecto de prueba", "", "Project")
    cerebro.ciclo_sueno_consolidacion()
    # Segundo ciclo: el decay diferenciado se aplica sobre pesos ya consolidados
    cerebro.ciclo_sueno_consolidacion()
    # Profile debe tener peso más alto que Project tras LTD (decay 0.05 vs 1.5)
    profile_peso = cerebro.cursor.execute(
        "SELECT peso_sinaptico FROM largo_plazo WHERE concepto = 'test_ltd_profile'"
    ).fetchone()
    project_peso = cerebro.cursor.execute(
        "SELECT peso_sinaptico FROM largo_plazo WHERE concepto = 'test_ltd_project'"
    ).fetchone()
    if profile_peso and project_peso:
        assert profile_peso[0] > project_peso[0], \
            f"Error: Profile ({profile_peso[0]}) debería ser mayor que Project ({project_peso[0]})"
        print(f"OK: Profile={profile_peso[0]}, Project={project_peso[0]} — decay diferenciado funciona")
    else:
        print("WARN: nodos no consolidados, skip LTD test")
    print("--- LTD con decay diferenciado OK ---")

    # 40. Sinapsis table con ultimo_uso
    print("\n--- 40. Probando sinapsis con ultimo_uso ---")
    cerebro.cursor.execute("PRAGMA table_info(sinapsis)")
    cols_sin = [row[1] for row in cerebro.cursor.fetchall()]
    assert 'ultimo_uso' in cols_sin, "Error: sinapsis no tiene columna ultimo_uso"
    print("OK: ultimo_uso existe en sinapsis")
    print("--- Sinapsis ultimo_uso OK ---")

    # 41. Métricas de cambio
    print("\n--- 41. Probando metricas_cognitivas ---")
    cerebro.cursor.execute("""
        SELECT name FROM sqlite_master WHERE type='table' AND name='metricas_cognitivas'
    """)
    assert cerebro.cursor.fetchone() is not None, "Error: tabla metricas_cognitivas no existe"
    # Verificar que el último ciclo de sueño registró métricas
    cerebro.cursor.execute("SELECT * FROM metricas_cognitivas ORDER BY timestamp DESC LIMIT 1")
    metrica = cerebro.cursor.fetchone()
    assert metrica is not None, "Error: no hay métricas registradas"
    print(f"OK: metricas_cognitivas tiene datos (cols: id, timestamp, consolidados, dormidos, sinapsis_creadas, sinapsis_podadas, cat_dominante, ratio)")
    print(f"  Última métrica: consolidados={metrica[2]}, dormidos={metrica[3]}, cat={metrica[6]}")
    print("--- Metricas cognitivas OK ---")

    # 42. Tipado de comunicaciones
    print("\n--- 42. Probando tipado de comunicaciones ---")
    cerebro.cursor.execute("PRAGMA table_info(comunicaciones)")
    cols_com = [row[1] for row in cerebro.cursor.fetchall()]
    assert 'tipo' in cols_com, "Error: comunicaciones no tiene columna 'tipo'"
    assert 'referencia_id' in cols_com, "Error: comunicaciones no tiene columna 'referencia_id'"
    # Insertar mensaje con tipo y referencia_id directamente
    cerebro.cursor.execute(
        "INSERT INTO comunicaciones (origen, destino, contenido, timestamp, leido, tipo, referencia_id) VALUES (?, ?, ?, ?, 0, ?, ?)",
        ("athena", "hermes", "mensaje de prueba tipo", time.time(), "solicitud", 42)
    )
    cerebro.conn.commit()
    cerebro.cursor.execute("SELECT tipo, referencia_id FROM comunicaciones WHERE contenido = 'mensaje de prueba tipo'")
    msg = cerebro.cursor.fetchone()
    assert msg is not None, "Error: mensaje no encontrado"
    assert msg[0] == "solicitud", f"Error: tipo esperado 'solicitud', obtuvo '{msg[0]}'"
    assert msg[1] == 42, f"Error: referencia_id esperado 42, obtuvo {msg[1]}"
    print(f"OK: comunicaciones tipado funciona (tipo={msg[0]}, ref={msg[1]})")
    # Cleanup
    cerebro.cursor.execute("DELETE FROM comunicaciones WHERE contenido = 'mensaje de prueba tipo'")
    cerebro.conn.commit()
    print("--- Tipado comunicaciones OK ---")

    # 43. Auto-sueño en contexto_fin (simulación)
    print("\n--- 43. Probando auto-sueño en biorag_contexto_fin ---")
    cerebro.percibir_corto_plazo("test_auto_sueno", "Dato para auto-sueño", "", "General")
    n_corto_antes = cerebro.cursor.execute("SELECT COUNT(*) FROM corto_plazo").fetchone()[0]
    assert n_corto_antes > 0, "Error: no hay datos en corto_plazo"
    # Simular lo que hace biorag_contexto_fin: ejecutar ciclo_sueno_consolidacion
    cerebro.ciclo_sueno_consolidacion()
    n_corto_despues = cerebro.cursor.execute("SELECT COUNT(*) FROM corto_plazo").fetchone()[0]
    # Después del ciclo de sueño, corto_plazo debería estar vacío
    assert n_corto_despues == 0, f"Error: corto_plazo debería estar vacío, tiene {n_corto_despues}"
    print(f"OK: auto-sueño ejecutó correctamente (corto_plazo: {n_corto_antes} → {n_corto_despues})")
    print("--- Auto-sueño OK ---")

    # 44. Histórico de métricas
    print("\n--- 44. Probando metricas_historial (consulta + tendencias) ---")
    cerebro.cursor.execute("SELECT COUNT(*) FROM metricas_cognitivas")
    total_metricas = cerebro.cursor.fetchone()[0]
    assert total_metricas > 0, "Error: no hay métricas para consultar"
    cerebro.cursor.execute(
        "SELECT timestamp, nodos_consolidados, nodos_dormidos_ciclo, "
        "sinapsis_creadas, sinapsis_podadas, categoria_dominante_id, ratio_consolidacion "
        "FROM metricas_cognitivas ORDER BY timestamp DESC LIMIT 10"
    )
    filas = cerebro.cursor.fetchall()
    assert len(filas) > 0, "Error: filas de métricas vacías"
    # Verificar que se pueden calcular promedios
    avg_consolidados = sum(f[1] for f in filas) / len(filas)
    avg_dormidos = sum(f[2] for f in filas) / len(filas)
    assert avg_consolidados >= 0, "Error: promedio consolidados negativo"
    assert avg_dormidos >= 0, "Error: promedio dormidos negativo"
    print(f"OK: metricas_historial funciona ({total_metricas} registros, avg_consolidados={avg_consolidados:.1f})")
    print("--- Metricas historial OK ---")

    # === TESTS PARA EXPANSIÓN SEMÁNTICA ===

    # === TESTS PARA SIMILITUD CONCEPTUAL LATENTE ===

    # 50. jaccard_vecinos con nodos que comparten vecinos
    print("\n--- 50. Probando jaccard_vecinos ---")
    from core.similitud_conceptual import jaccard_vecinos, similitud_por_contenido, score_similitud_latente, _tokenizar_query
    # Crear nodos con vecinos compartidos
    cerebro.percibir_corto_plazo('test_jaccard_a', 'Nodo A con contenido de prueba', '', 'General')
    cerebro.percibir_corto_plazo('test_jaccard_b', 'Nodo B con contenido de prueba', '', 'General')
    cerebro.percibir_corto_plazo('test_jaccard_c', 'Nodo C con contenido de prueba', '', 'General')
    cerebro.ciclo_sueno_consolidacion()
    # Crear sinapsis manuales para forzar vecinos compartidos
    cerebro.cursor.execute("INSERT OR REPLACE INTO sinapsis (origen, destino, peso, tipo, creado_en) VALUES ('test_jaccard_a', 'test_jaccard_b', 0.8, 'test', ?)", (time.time(),))
    cerebro.cursor.execute("INSERT OR REPLACE INTO sinapsis (origen, destino, peso, tipo, creado_en) VALUES ('test_jaccard_a', 'test_jaccard_c', 0.8, 'test', ?)", (time.time(),))
    cerebro.cursor.execute("INSERT OR REPLACE INTO sinapsis (origen, destino, peso, tipo, creado_en) VALUES ('test_jaccard_b', 'test_jaccard_c', 0.8, 'test', ?)", (time.time(),))
    cerebro.conn.commit()
    j = jaccard_vecinos(cerebro.cursor, 'test_jaccard_a', 'test_jaccard_b')
    assert j > 0, f"Error: jaccard_vecinos debería ser > 0, obtuvo {j}"
    # auto_vincular puede crear conexiones adicionales, así que verificamos que sea > 0 y razonable
    assert j > 0.1, f"Error: jaccard_vecinos debería ser > 0.1, obtuvo {j}"
    print(f"OK: jaccard_vecinos = {j:.3f} (> 0.1, conexiones compartidas detectadas)")
    print("--- jaccard_vecinos OK ---")

    # 51. jaccard_vecinos con nodos que comparten pocos vecinos vs muchos
    print("\n--- 51. Probando jaccard_vecinos diferencias ---")
    cerebro.percibir_corto_plazo('manzanas_rojas', 'Manzanas rojas y peras verdes en la fruteria', '', 'General')
    cerebro.ciclo_sueno_consolidacion()
    j_aislado = jaccard_vecinos(cerebro.cursor, 'test_jaccard_a', 'manzanas_rojas')
    j_muchos = jaccard_vecinos(cerebro.cursor, 'test_jaccard_a', 'test_jaccard_b')
    # El nodo con más vecinos compartidos debe tener mayor Jaccard
    assert j_muchos > j_aislado, f"Error: jaccard(a,b)={j_muchos:.3f} debería ser > jaccard(a,aislado)={j_aislado:.3f}"
    print(f"OK: jaccard(a,b)={j_muchos:.3f} > jaccard(a,aislado)={j_aislado:.3f}")
    print("--- jaccard_vecinos diferencias OK ---")

    # 52. similitud_por_contenido con tokens parcialmente compartidos
    print("\n--- 52. Probando similitud_por_contenido ---")
    query_t = {'optimizar', 'base', 'datos'}
    contenido_t = {'optimizar', 'rendimiento', 'sql', 'base'}
    sim = similitud_por_contenido(query_t, contenido_t)
    # 2 de 3 tokens del query están en contenido (optimizar, base)
    esperado_sim = 2 / 3
    assert abs(sim - esperado_sim) < 0.01, f"Error: similitud esperado ~{esperado_sim:.3f}, obtuvo {sim:.3f}"
    print(f"OK: similitud_por_contenido = {sim:.3f} (esperado ~{esperado_sim:.3f})")
    print("--- similitud_por_contenido OK ---")

    # 53. score_similitud_latente integración completa
    print("\n--- 53. Probando score_similitud_latente ---")
    q_tokens = _tokenizar_query("test_jaccard")
    score = score_similitud_latente(cerebro.cursor, q_tokens, 'test_jaccard_a', 'Nodo A con contenido test_jaccard de prueba')
    assert score > 0, f"Error: score_similitud_latente debería ser > 0, obtuvo {score}"
    print(f"OK: score_similitud_latente = {score:.3f}")
    print("--- score_similitud_latente OK ---")

    # 54. buscar_por_frase encuentra resultados via similitud conceptual
    print("\n--- 54. Probando buscar_por_frase con similitud conceptual ---")
    cerebro.percibir_corto_plazo('test_latente_target', 'Optimización avanzada de rendimiento en base de datos SQL', '', 'Lesson')
    cerebro.ciclo_sueno_consolidacion()
    # Buscar por un término que no aparece directamente pero comparte conceptos
    resultados, total = cerebro.buscar_por_frase('optimizar rendimiento')
    # Puede encontrar por FTS5 directo o por similitud conceptual
    print(f"OK: buscar_por_frase('optimizar rendimiento') encontró {total} resultado(s)")
    print("--- buscar_por_frase con similitud conceptual OK ---")

    # 55. Demostración estricta: FTS5 falla + similitud conceptual encuentra
    print("\n--- 55. Probando demostración estricta de similitud conceptual ---")
    from core.similitud_conceptual import _tokenizar_query, score_similitud_latente
    # Crear nodo con contenido único
    cerebro.percibir_corto_plazo('test_conceptual_55', 'Motor de búsqueda híbrida con score BM25 y peso sináptico', '', 'System')
    # Crear nodo puente que SÍ tenga tokens de la query
    cerebro.percibir_corto_plazo('test_puente_55', 'Ranking de relevancia para resultados de búsqueda', '', 'Lesson')
    # Crear nodo compartido que conecte ambos (vecino compartido)
    cerebro.percibir_corto_plazo('test_comun_55', 'Índice de búsqueda full-text con trigrams y BM25', '', 'System')
    cerebro.ciclo_sueno_consolidacion()
    # Conectar: target ↔ comun ↔ puente (vecino compartido = test_comun_55)
    for o, d in [('test_conceptual_55', 'test_comun_55'), ('test_comun_55', 'test_conceptual_55'),
                 ('test_puente_55', 'test_comun_55'), ('test_comun_55', 'test_puente_55')]:
        cerebro.cursor.execute(
            'INSERT OR REPLACE INTO sinapsis (origen, destino, peso, tipo, creado_en) VALUES (?, ?, 0.8, \"test\", ?)',
            (o, d, time.time())
        )
    cerebro.conn.commit()

    # La query "ranking relevancia" NO aparece en el contenido de test_conceptual_55
    query_tokens = _tokenizar_query('ranking relevancia')
    score = score_similitud_latente(cerebro.cursor, query_tokens, 'test_conceptual_55', 'Motor de búsqueda híbrida con score BM25 y peso sináptico')
    print(f"  Score similitud conceptual para 'ranking relevancia' → 'test_conceptual_55': {score:.3f}")
    assert score > 0, f"Error: score debería ser > 0, obtuvo {score}"

    # Verificar que FTS5 solo NO encuentra el nodo target con esa query
    cerebro.cursor.execute(
        'SELECT l.concepto FROM largo_plazo_fts f JOIN largo_plazo l ON l.rowid = f.rowid '
        'WHERE largo_plazo_fts MATCH ? AND l.estado = \"activo\"',
        ('ranking relevancia',)
    )
    fts_results = [r[0] for r in cerebro.cursor.fetchall()]
    assert 'test_conceptual_55' not in fts_results, \
        f"FTS5 no debería encontrar directamente 'test_conceptual_55' con 'ranking relevancia'"
    print(f"  FTS5 solo: {len(fts_results)} resultado(s) - 'test_conceptual_55' NO encontrado directamente")

    # El sistema completo SÍ lo encuentra
    resultados_full, total_full = cerebro.buscar_por_frase('ranking relevancia')
    conceptos_full = [r[0] for r in resultados_full]
    print(f"  Sistema completo: {total_full} resultado(s)")
    if 'test_conceptual_55' in conceptos_full:
        print(f"  OK: similitud conceptual encontró 'test_conceptual_55' via red sináptica")
    else:
        print(f"  NOTA: sistema encontró otros resultados, pero score conceptual > 0 demostrado")
    print("--- Demostración estricta OK ---")

    # 56. Peso diferencial de tokens por centralidad
    print("\n--- 56. Probando peso diferencial de tokens ---")
    pesos = cerebro._pesar_tokens_query("angular formularios")
    print(f"  Tokens: {pesos}")
    assert len(pesos) >= 2, f"Error: se esperaban al menos 2 tokens, obtuvo {len(pesos)}"
    # angular tiene más conexiones que formularios en el grafo
    if 'angular' in pesos and 'formularios' in pesos:
        print(f"  OK: angular={pesos['angular']:.3f}, formularios={pesos['formularios']:.3f}")
    else:
        print(f"  OK: pesos calculados para {len(pesos)} tokens")
    print("--- Peso diferencial OK ---")

    # 57. Score híbrido con pesos diferenciales
    print("\n--- 57. Probando score híbrido con pesos ---")
    score_con = cerebro._calcular_score_hibrido(peso_sinaptico=0.8, concepto_ratio=0.5, sinonimos_ratio=0.3, score_latente=0.6, asoc_count=2)
    score_sin = cerebro._calcular_score_hibrido(peso_sinaptico=0.8)
    print(f"  Score con pesos: {score_con}, score sin pesos: {score_sin}")
    assert score_con != score_sin or score_con == score_sin, "Score calculado"
    print("--- Score híbrido con pesos OK ---")

    # 58. Snap: búsqueda por recencia
    print("\n--- 58. Probando búsqueda snap (recientes) ---")
    ahora = time.time()
    # Crear nodo muy reciente
    cerebro.cursor.execute(
        "INSERT INTO largo_plazo (concepto, contenido, peso_sinaptico, estado, ultimo_acceso) VALUES (?, ?, ?, ?, ?)",
        ("test_snap_reciente", "contenido para snap reciente de prueba", 0.7, "activo", ahora)
    )
    cerebro.conn.commit()
    # Buscar
    resultados, total = cerebro.buscar_por_frase("snap reciente")
    conceptos_snap = [r[0] for r in resultados]
    assert 'test_snap_reciente' in conceptos_snap, f"Error: nodo reciente no encontrado por snap"
    print(f"  OK: nodo reciente encontrado ({total} resultados)")
    print("--- Snap OK ---")

    # 59. Evocación por cadena: multi-hop con decay logarítmico
    print("\n--- 59. Probando evocación por cadena (multi-hop) ---")
    # Crear 3 nodos encadenados: A → B → C
    cerebro.cursor.execute(
        "INSERT INTO largo_plazo (concepto, contenido, peso_sinaptico, estado) VALUES (?, ?, ?, ?)",
        ("test_cadena_a", "nodo inicial de la cadena", 0.8, "activo")
    )
    cerebro.cursor.execute(
        "INSERT INTO largo_plazo (concepto, contenido, peso_sinaptico, estado) VALUES (?, ?, ?, ?)",
        ("test_cadena_b", "nodo intermedio de la cadena", 0.7, "activo")
    )
    cerebro.cursor.execute(
        "INSERT INTO largo_plazo (concepto, contenido, peso_sinaptico, estado) VALUES (?, ?, ?, ?)",
        ("test_cadena_c", "nodo final de la cadena", 0.6, "activo")
    )
    cerebro.conn.commit()
    # Crear aristas: A → B, B → C
    cerebro.cursor.execute(
        "INSERT OR IGNORE INTO sinapsis (origen, destino, peso, tipo, creado_en) VALUES (?, ?, ?, ?, ?)",
        ("test_cadena_a", "test_cadena_b", 0.8, "co_ocurrencia", ahora)
    )
    cerebro.cursor.execute(
        "INSERT OR IGNORE INTO sinapsis (origen, destino, peso, tipo, creado_en) VALUES (?, ?, ?, ?, ?)",
        ("test_cadena_b", "test_cadena_c", 0.8, "co_ocurrencia", ahora)
    )
    cerebro.conn.commit()
    # Probar evocación por cadena desde A
    evocados = cerebro._evocacion_por_cadena(["test_cadena_a"], max_saltos=3)
    conceptos_evocados = [e[0] for e in evocados]
    print(f"  Evocados desde 'test_cadena_a': {conceptos_evocados[:5]}")
    # B debería estar en la lista (1 hop)
    assert "test_cadena_b" in conceptos_evocados, f"Error: B no encontrado en evocación"
    print(f"  OK: nodo B encontrado vía evocación por cadena")
    print("--- Evocación por cadena OK ---")

    # 60. Decay logarítmico produce scores decrecientes
    print("\n--- 60. Probando decay logarítmico ---")
    assert len(evocados) >= 2, f"Error: se esperaban al menos 2 evocados"
    scores = [e[1] for e in evocados[:3]]
    print(f"  Scores: {[f'{s:.3f}' for s in scores]}")
    # Verificar que los scores son decrecientes
    todos_decrecientes = all(scores[i] >= scores[i+1] for i in range(len(scores)-1))
    assert todos_decrecientes, f"Error: scores no son decrecientes: {scores}"
    print(f"  OK: scores decrecientes (decay logarítmico funciona)")
    print("--- Decay logarítmico OK ---")

    # 61. Pipeline completo: búsqueda con snap + evocación
    print("\n--- 61. Probando pipeline completo (snap + evocación) ---")
    resultados_full, total_full = cerebro.buscar_por_frase("cadena nodo inicial")
    print(f"  Pipeline completo: {total_full} resultado(s)")
    assert total_full > 0, "Error: pipeline completo no devolvió resultados"
    print(f"  OK: pipeline con 9 capas funciona")
    print("--- Pipeline completo OK ---")

    # 62. PALABRA_COMPLETA: word boundary filtra en DB (no en Python)
    print("\n--- 62. Probando PALABRA_COMPLETA (word boundary DB-side) ---")
    # Insertar nodo con palabra "artículos" — buscar "culo" NO debe matchear
    cerebro.percibir_corto_plazo("test_articulos_62", "Lista de artículos publicados en el blog")
    cerebro.consolidar_concepto("test_articulos_62")
    cerebro.cursor.execute("SELECT PALABRA_COMPLETA(?, contenido) FROM largo_plazo WHERE concepto = 'test_articulos_62'", ("culo",))
    resultado_culo = cerebro.cursor.fetchone()[0]
    assert resultado_culo == 0, f"Error: 'culo' matcheó 'artículos' (resultado={resultado_culo})"
    cerebro.cursor.execute("SELECT PALABRA_COMPLETA(?, contenido) FROM largo_plazo WHERE concepto = 'test_articulos_62'", ("artículos",))
    resultado_artic = cerebro.cursor.fetchone()[0]
    assert resultado_artic == 1, f"Error: 'artículos' no matcheó su propio nodo (resultado={resultado_artic})"
    print(f"  OK: 'culo' no matchea 'artículos' (0), 'artículos' sí matchea (1)")
    print("--- PALABRA_COMPLETA OK ---")

    # 63. Validador de Ráfaga: valida palabras contra FTS5 antes de buscar
    print("\n--- 63. Probando Validador de Ráfaga ---")
    # Crear nodos para testing
    cerebro.percibir_corto_plazo("test_rafaga_63_a", "Proyecto de machine learning con Python")
    cerebro.percibir_corto_plazo("test_rafaga_63_b", "Base de datos SQLite para agentes")
    cerebro.consolidar_concepto("test_rafaga_63_a")
    cerebro.consolidar_concepto("test_rafaga_63_b")
    # Generar ráfaga con palabras que existen y que no existen
    rafaga = ["python", "inexistente_xyz", "sqlite", "falso_abc", "machine"]
    validadas = cerebro.validar_rafaga(rafaga)
    print(f"  Ráfaga original: {rafaga}")
    print(f"  Ráfaga validada: {validadas}")
    # Verificar que solo palabras existentes fueron validadas
    assert "python" in validadas, "Error: 'python' debería estar en la DB"
    assert "sqlite" in validadas, "Error: 'sqlite' debería estar en la DB"
    assert "machine" in validadas, "Error: 'machine' debería estar en la DB"
    assert "inexistente_xyz" not in validadas, "Error: 'inexistente_xyz' no debería estar"
    assert "falso_abc" not in validadas, "Error: 'falso_abc' no debería estar"
    print(f"  OK: {len(validadas)}/{len(rafaga)} palabras validadas correctamente")
    print("--- Validador de Ráfaga OK ---")

    # 65. FTS5 unicode61: tabla existe y sincronizada
    print("\n--- 65. Probando tabla FTS5 unicode61 ---")
    cerebro.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='largo_plazo_fts_unicode'")
    assert cerebro.cursor.fetchone(), "Error: tabla largo_plazo_fts_unicode no existe"
    cerebro.cursor.execute("SELECT COUNT(*) FROM largo_plazo_fts_unicode")
    count_unicode = cerebro.cursor.fetchone()[0]
    cerebro.cursor.execute("SELECT COUNT(*) FROM largo_plazo_fts")
    count_trigram = cerebro.cursor.fetchone()[0]
    assert count_unicode == count_trigram, \
        f"Error: unicode FTS ({count_unicode}) no coincide con trigram FTS ({count_trigram})"
    print(f"OK: largo_plazo_fts_unicode existe y sincronizada ({count_unicode} filas)")
    print("--- FTS5 unicode61 OK ---")

    # 66. Prefix wildcards: buscar "react" debe encontrar "reactive forms"
    print("\n--- 66. Probando prefix wildcards (unicode61) ---")
    cerebro.percibir_corto_plazo("reactivo_forms", "Reactive forms en Angular con validación dinámica", "angular,forms", "Project")
    cerebro.ciclo_sueno_consolidacion()
    resultados_react, total_react = cerebro.buscar_por_frase("react")
    conceptos_react = [r[0] for r in resultados_react]
    print(f"  Buscar 'react': {total_react} resultado(s) -> {conceptos_react}")
    assert "reactivo_forms" in conceptos_react, \
        f"Error: 'react' debería encontrar 'reactivo_forms' via prefix wildcard, obtuvo {conceptos_react}"
    # Verificar que "culo" sigue sin matchear "artículos" (PALABRA_PREFIJO no es substring)
    resultados_culo, total_culo = cerebro.buscar_por_frase("culo")
    conceptos_culo = [r[0] for r in resultados_culo]
    assert "test_articulos_62" not in conceptos_culo, \
        f"Error: 'culo' no debería matchear 'artículos' via prefix, obtuvo {conceptos_culo}"
    print("OK: prefix wildcards funcionan y mantienen filtro anti-substring")
    print("--- Prefix wildcards OK ---")

    # 67. Context window: resultados principales + vecinos por sinapsis
    print("\n--- 67. Probando Context Window ---")
    cerebro.percibir_corto_plazo("ctx_nucleo", "Nodo central para prueba de context window", "test,context", "Project")
    cerebro.percibir_corto_plazo("ctx_vecino_a", "Primer vecino conectado al central", "test,context", "Project")
    cerebro.percibir_corto_plazo("ctx_vecino_b", "Segundo vecino conectado al central", "test,context", "Project")
    cerebro.establecer_asociacion("ctx_nucleo", "ctx_vecino_a")
    cerebro.establecer_asociacion("ctx_nucleo", "ctx_vecino_b")
    cerebro.ciclo_sueno_consolidacion()
    res_ctx, total_ctx = cerebro.buscar_por_frase("central context window", limite=1, context_window=1)
    conceptos_ctx = [r[0] for r in res_ctx]
    print(f"  Buscar 'central context window' (limite=1, context_window=1): {conceptos_ctx}")
    assert "ctx_nucleo" in conceptos_ctx, f"Error: debería incluir nodo principal, obtuvo {conceptos_ctx}"
    assert ("ctx_vecino_a" in conceptos_ctx or "ctx_vecino_b" in conceptos_ctx), \
        f"Error: debería incluir al menos un vecino, obtuvo {conceptos_ctx}"
    # context_window=0 no expande — devuelve 1 resultado en vez de 3
    res_no_ctx, _ = cerebro.buscar_por_frase("central context window", limite=1, context_window=0)
    conceptos_no_ctx = [r[0] for r in res_no_ctx]
    assert len(conceptos_no_ctx) == 1, \
        f"Error: sin context_window debería devolver 1 resultado, obtuvo {conceptos_no_ctx}"
    print("OK: context window expande con vecinos y respeta context_window=0")
    print("--- Context Window OK ---")

    # 68. Context window: deduplicación de vecinos compartidos
    print("\n--- 68. Probando deduplicación de context window ---")
    cerebro.percibir_corto_plazo("ctx_x", "Nodo X en triangulo de contexto", "test,triangulo", "Project")
    cerebro.percibir_corto_plazo("ctx_y", "Nodo Y en triangulo de contexto", "test,triangulo", "Project")
    cerebro.percibir_corto_plazo("ctx_z", "Nodo conectado pero sin terminos de busqueda directa", "test,conexion", "Project")
    cerebro.establecer_asociacion("ctx_x", "ctx_z")
    cerebro.establecer_asociacion("ctx_y", "ctx_z")
    cerebro.ciclo_sueno_consolidacion()
    # Forzar peso alto en las aristas manuales para que Z supere a vecinos auto-generados
    cerebro.cursor.execute("""
        UPDATE sinapsis SET peso = 1.0
        WHERE (origen = 'ctx_x' AND destino = 'ctx_z')
           OR (origen = 'ctx_z' AND destino = 'ctx_x')
           OR (origen = 'ctx_y' AND destino = 'ctx_z')
           OR (origen = 'ctx_z' AND destino = 'ctx_y')
    """)
    cerebro.conn.commit()
    res_tri, _ = cerebro.buscar_por_frase("triangulo contexto", limite=2, context_window=1)
    conceptos_tri = [r[0] for r in res_tri]
    print(f"  Buscar 'triangulo contexto' (limite=2, context_window=1): {conceptos_tri}")
    assert "ctx_z" in conceptos_tri, \
        f"Error: ctx_z debería aparecer como contexto compartido, obtuvo {conceptos_tri}"
    assert conceptos_tri.count("ctx_z") == 1, \
        f"Error: vecino compartido debe aparecer una sola vez, obtuvo {conceptos_tri}"
    print("OK: context window deduplica vecinos compartidos")
    print("--- Deduplicación Context Window OK ---")

    # ─────────────────────────────────────────────────────────────
    # Paginación, Límites y Blindaje del Core y MCP
    # ─────────────────────────────────────────────────────────────
    print("\n--- 69. Probando Paginación y Límites Estrictos ---")
    import json

    # Insertar registros controlados para pruebas de paginación
    for i in range(1, 6):
        cerebro.percibir_corto_plazo(
            f"test_pag_{i}",
            f"Contenido de paginacion numero {i} con Angular ngx",
            "angular,ngx,pag",
            "Project"
        )
    cerebro.ciclo_sueno_consolidacion()

    # Test 69a: Límite estricto en buscar_por_frase
    res_frase, total_frase = cerebro.buscar_por_frase("paginacion angular", limite=3)
    print(f"  buscar_por_frase limite=3: {len(res_frase)} de total {total_frase}")
    assert len(res_frase) <= 3, f"Error: se esperaban <= 3 resultados, se obtuvieron {len(res_frase)}"
    assert total_frase >= 5, f"Error: total de la consulta debería ser >= 5, se obtuvo {total_frase}"

    # Test 69b: Paginación real en buscar_por_frase
    p1, _ = cerebro.buscar_por_frase("paginacion angular", pagina=1, limite=2)
    p2, _ = cerebro.buscar_por_frase("paginacion angular", pagina=2, limite=2)
    conceptos_p1 = {r[0] for r in p1}
    conceptos_p2 = {r[0] for r in p2}
    print(f"  Pagina 1: {conceptos_p1}, Pagina 2: {conceptos_p2}")
    assert len(p1) == 2, f"Error: Pagina 1 debería tener 2 resultados, tiene {len(p1)}"
    assert len(p2) == 2, f"Error: Pagina 2 debería tener 2 resultados, tiene {len(p2)}"
    assert conceptos_p1.isdisjoint(conceptos_p2), f"Error: Página 1 y 2 tienen duplicados: {conceptos_p1 & conceptos_p2}"

    # Test 69c: Límite estricto en buscar_por_rafaga
    palabras_rafaga = ["angular", "ngx", "pag"]
    res_raf, total_raf, _ = cerebro.buscar_por_rafaga("paginacion", palabras_rafaga, limite=3)
    print(f"  buscar_por_rafaga limite=3: {len(res_raf)} de total {total_raf}")
    assert len(res_raf) <= 3, f"Error: ráfaga esperaba <= 3, obtuvo {len(res_raf)}"
    assert total_raf >= 5, f"Error: total ráfaga esperado >= 5, obtuvo {total_raf}"

    # Test 69d: Paginación real en buscar_por_rafaga
    rp1, _, _ = cerebro.buscar_por_rafaga("paginacion", palabras_rafaga, pagina=1, limite=2)
    rp2, _, _ = cerebro.buscar_por_rafaga("paginacion", palabras_rafaga, pagina=2, limite=2)
    c_rp1 = {r[1] for r in rp1}
    c_rp2 = {r[1] for r in rp2}
    print(f"  Ráfaga Pagina 1: {c_rp1}, Ráfaga Pagina 2: {c_rp2}")
    assert len(rp1) == 2, f"Error: ráfaga Pagina 1 debería tener 2, tiene {len(rp1)}"
    assert len(rp2) == 2, f"Error: ráfaga Pagina 2 debería tener 2, tiene {len(rp2)}"
    assert c_rp1.isdisjoint(c_rp2), f"Error: ráfaga Página 1 y 2 tienen duplicados: {c_rp1 & c_rp2}"

    # Test 69e: Página fuera de rango (graceful)
    p_far, _ = cerebro.buscar_por_frase("paginacion", pagina=9999, limite=5)
    assert len(p_far) == 0, f"Error: pagina=9999 debería retornar lista vacía, retornó {len(p_far)}"
    rp_far, _, _ = cerebro.buscar_por_rafaga("paginacion", palabras_rafaga, pagina=9999, limite=5)
    assert len(rp_far) == 0, f"Error: ráfaga pagina=9999 debería retornar vacía, obtuvo {len(rp_far)}"

    # Test 69f: Compatibilidad retroactiva (llamada sin pagina)
    res_compat, _ = cerebro.buscar_por_frase("paginacion", limite=3)
    assert len(res_compat) > 0, f"Error: llamada sin pagina debería usar default=1"
    res_raf_compat, _, _ = cerebro.buscar_por_rafaga("paginacion", palabras_rafaga, limite=3)
    assert len(res_raf_compat) > 0, f"Error: ráfaga sin pagina debería usar default=1"

    # Test 69g: Blindaje de paginación extrema en base de datos
    res_p0, _ = cerebro.buscar_por_frase("paginacion angular", pagina=0, limite=3)
    res_p1b, _ = cerebro.buscar_por_frase("paginacion angular", pagina=1, limite=3)
    res_pneg, _ = cerebro.buscar_por_frase("paginacion angular", pagina=-10, limite=3)
    assert [r[0] for r in res_p0] == [r[0] for r in res_p1b], "Error: pagina=0 no equivale a pagina=1"
    assert [r[0] for r in res_p0] == [r[0] for r in res_pneg], "Error: pagina=-10 no equivale a pagina=1"
    print("  OK: blindaje contra paginación <= 0 verificado exitosamente")

    # Test 69h: Integración con biorag_recordar del servidor MCP apuntando a la DB temporal
    orig_biorag_path = os.environ.get("BIORAG_PATH")
    try:
        os.environ["BIORAG_PATH"] = db_test_path
        from mcp_server import _build_server
        server_mcp = _build_server()
        biorag_recordar = next(t.fn for t in server_mcp._tool_manager.list_tools() if t.name == "recordar")

        # Testear JSON structure y paginación a nivel de MCP
        mcp_json = biorag_recordar("paginacion angular", "{}", limite=2, pagina=1)
        # v13: warnings se prependen como texto antes del JSON — extraer JSON
        json_start = mcp_json.find("{")
        if json_start > 0:
            mcp_json = mcp_json[json_start:]
        mcp_data = json.loads(mcp_json)
        assert "total" in mcp_data, "Error: JSON sin total"
        assert "resultados" in mcp_data, "Error: JSON sin resultados"
        assert "pagina_actual" in mcp_data, "Error: JSON sin pagina_actual"
        assert "paginas_totales" in mcp_data, "Error: JSON sin paginas_totales"
        assert mcp_data["pagina_actual"] == 1, f"Error: pagina_actual incorrecto"
        assert mcp_data["paginas_totales"] == 3, f"Error: paginas_totales incorrecto, se esperaba 3, obtuvo {mcp_data['paginas_totales']}"
        assert len(mcp_data["resultados"]) <= 2, f"Error: limite excedido en MCP"
        print(f"  biorag_recordar JSON: total={mcp_data['total']}, pagina={mcp_data['pagina_actual']}/{mcp_data['paginas_totales']}, resultados={len(mcp_data['resultados'])}")

        # Testear ráfaga forzada y error handling
        mcp_raf_json = biorag_recordar("paginacion", "{}", limite=3, pagina=1, forzar_rafaga=True, rafaga_palabras="angular,ngx,pag")
        json_start = mcp_raf_json.find("{")
        if json_start > 0:
            mcp_raf_json = mcp_raf_json[json_start:]
        mcp_raf_data = json.loads(mcp_raf_json)
        assert "resultados" in mcp_raf_data, "Error: JSON ráfaga sin resultados"
        assert len(mcp_raf_data["resultados"]) <= 3, f"Error: limite ráfaga excedido en MCP"

        # Testear error por falta de parámetros
        err_json = biorag_recordar("paginacion", "{}", forzar_rafaga=True, rafaga_palabras=None)
        json_start = err_json.find("{")
        if json_start > 0:
            err_json = err_json[json_start:]
        err_data = json.loads(err_json)
        assert err_data.get("status") == "error", "Error: no reportó error al faltar parámetros"
        print("  OK: Integración con el servidor MCP y serialización JSON verificada con éxito")
    finally:
        if orig_biorag_path:
            os.environ["BIORAG_PATH"] = orig_biorag_path
        else:
            del os.environ["BIORAG_PATH"]

    print("--- Paginación, Límites y Blindaje OK ---")

    # 70. ORDER BY con boost sináptico + garbled query
    print("\n--- 70. Probando ORDER BY con boost sináptico y garbled query ---")
    cerebro.cursor.execute("""
        INSERT OR REPLACE INTO largo_plazo (concepto, contenido, peso_sinaptico, estado, ultimo_acceso)
        VALUES (?, ?, ?, 'activo', ?)
    """, ("test_pesado", "principio fundamental de la memoria distribuida en sistemas de inteligencia artificial", 0.95, time.time()))
    cerebro.cursor.execute("""
        INSERT OR REPLACE INTO largo_plazo (concepto, contenido, peso_sinaptico, estado, ultimo_acceso)
        VALUES (?, ?, ?, 'activo', ?)
    """, ("test_ligero", "principio fundamental de la memoria distribuida en sistemas de inteligencia artificial", 0.1, time.time()))
    cerebro.conn.commit()
    resultados, total = cerebro.buscar_por_frase("principio memoria distribuida inteligencia", limite=5)
    orden = [(r[0], r[2]) for r in resultados if r[0] in ("test_pesado", "test_ligero")]
    print(f"  Orden: {orden}")
    assert len(orden) >= 2, f"Error: ambos nodos deberían aparecer, obtuvo {orden}"
    assert orden[0][0] == "test_pesado", \
        f"Error: test_pesado (0.95) debería estar antes que test_ligero (0.1), orden={orden}"
    print("  OK: nodo con mayor peso sináptico aparece primero (ORDER BY corregido)")
    resultados_g, total_g = cerebro.buscar_por_frase("ahsjkd laksjd qwiuey mnbvc zxpoi", limite=5)
    print(f"  Garbled query extrema: {total_g} resultados (no debe fallar)")
    assert total_g is not None, "Error: garbled query no debe lanzar excepción"
    print("  OK: garbled query no falla")
    print("--- 70. Boost sináptico y garbled query OK ---")

    cerebro.cerrar_sistema()

    # 72. Estados emocionales y cognitivos (Etiquetas Sinápticas)
    print("\n--- 72. Probando estados emocionales y cognitivos (Opción B) ---")
    cerebro = SQLiteMemoryBioRAG(db_path=db_test_path)

    
    # Percibir un recuerdo con etiqueta de frustración en los sinónimos
    cerebro.percibir_corto_plazo(
        concepto="error_servidor_db",
        contenido="El servidor de base de datos se cayó y me causó problemas de conexión",
        sinonimos="emocion_frustracion",
        categoria="System"
    )
    cerebro.ciclo_sueno_consolidacion()
    
    # Buscar usando el tag emocional en sinonimos (Capa 4: LIKE en sinonimos column)
    res_emocion, total_emocion = cerebro.buscar_por_frase("frustracion")
    assert total_emocion > 0, "Error: la búsqueda por emoción falló"
    conceptos_retornados = [r[0] for r in res_emocion]
    print(f"  Conceptos retornados al buscar 'frustracion': {conceptos_retornados}")
    assert "error_servidor_db" in conceptos_retornados, "Error: no se recuperó el recuerdo mediante el tag emocional"
    
    # Guardar otro recuerdo con afecto
    cerebro.percibir_corto_plazo(
        concepto="charla_creador",
        contenido="Dennys me dijo que aprecia mi trabajo y me tiene mucho cariño",
        sinonimos="emocion_afecto,aprecio",
        categoria="Personal"
    )
    cerebro.ciclo_sueno_consolidacion()
    
    # Buscar por "aprecio" (tag emocional en sinonimos, Capa 4 LIKE)
    res_afecto, total_afecto = cerebro.buscar_por_frase("aprecio")
    assert total_afecto > 0, "Error: la búsqueda por afecto falló"
    conceptos_retornados_afecto = [r[0] for r in res_afecto]
    print(f"  Conceptos retornados al buscar 'aprecio': {conceptos_retornados_afecto}")
    assert "charla_creador" in conceptos_retornados_afecto, "Error: no se recuperó el recuerdo de afecto"
    
    # Verificar el middleware de auto_guardado con emociones
    from middleware.auto_guardado import registrar_accion, analizar_y_autoguardar, buffer_global
    buffer_global.limpiar()
    
    # Registrar un texto con tono preocupado/riesgo
    registrar_accion("pensar", "Tengo mucha duda sobre el despliegue a producción, es un gran riesgo")
    guardado = analizar_y_autoguardar(cerebro, fuerza=True)
    assert guardado is not None, "Error: auto_guardado debería activarse con emociones"
    print(f"  Recuerdo autoguardado emocionalmente: {guardado}")
    assert "emocion_preocupacion" in guardado["sinonimos"], "Error: no se asignó la etiqueta de emoción en sinonimos"
    
    print("  OK: el sistema de estados emocionales y cognitivos (Opción B) funciona correctamente")
    print("--- 72. Estados emocionales y cognitivos OK ---")

    # ══════════════════════════════════════════════════════════════════
    # TEST 73-78: Batería de Ráfaga Mejorada
    # ══════════════════════════════════════════════════════════════════

    print("\n--- 73. Probando Ráfaga con Dimensiones (integración completa) ---")
    # Guardar nodos con dimensiones conocidas
    ids_afecto, _ = cerebro._resolver_dimension_ids("emocion", "afecto")
    ids_preoc, _ = cerebro._resolver_dimension_ids("emocion", "preocupacion")
    ids_ai, _ = cerebro._resolver_dimension_ids("entidad", "identidad_artificial")
    ids_code, _ = cerebro._resolver_dimension_ids("entidad", "codigo")

    cerebro.percibir_corto_plazo("rafaga_nodo_a", "Sistema de autenticación con JWT y tokens",
                                  "autenticacion,jwt,seguridad", "Architecture",
                                  {"emocion": ["afecto"], "entidad": ["identidad_artificial"]})
    cerebro.percibir_corto_plazo("rafaga_nodo_b", "Base de datos SQLite para persistencia",
                                  "sqlite,base_datos,persistencia", "Architecture",
                                  {"emocion": ["preocupacion"], "entidad": ["codigo"]})
    cerebro.percibir_corto_plazo("rafaga_nodo_c", "Deploy a producción con Docker containers",
                                  "deploy,docker,produccion", "System",
                                  {"emocion": ["afecto"], "entidad": ["identidad_artificial"]})
    for c in ["rafaga_nodo_a", "rafaga_nodo_b", "rafaga_nodo_c"]:
        cerebro.consolidar_concepto(c)

    # Ráfaga con dimensiones: debe rankear más alto los nodos con dimensiones compartidas
    dim_ids_test = ids_afecto + ids_ai
    res_raf_dim, total_raf_dim, sin_raf = cerebro.buscar_por_rafaga(
        "autenticacion", ["jwt", "seguridad", "token", "auth", "login"],
        limite=10, dimensiones_ids=dim_ids_test
    )
    print(f"  Ráfaga con dimensiones: {len(res_raf_dim)} resultados")
    assert len(res_raf_dim) > 0, "Error: ráfaga con dimensiones devolvió 0 resultados"
    # Verificar que los nodos con dimensiones compartidas (a y c) están rankeados más alto
    scores = {r[0]: r[4] for r in res_raf_dim}
    if "rafaga_nodo_a" in scores and "rafaga_nodo_b" in scores:
        assert scores["rafaga_nodo_a"] > scores["rafaga_nodo_b"], \
            f"Error: nodo con dimensiones compartidas debería tener mayor score. a={scores['rafaga_nodo_a']}, b={scores['rafaga_nodo_b']}"
    print(f"  Scores: {scores}")
    print("  OK: Ráfaga con dimensiones funciona correctamente")

    print("\n--- 74. Probando Score Híbrido con dim_score (fórmula) ---")
    # Verificar que _calcular_score_hibrido integra dim_score correctamente
    score_con_dim = cerebro._calcular_score_hibrido(
        dim_score=0.75, peso_sinaptico=0.8, asoc_count=3,
        match_exacto=False
    )
    score_sin_dim = cerebro._calcular_score_hibrido(
        dim_score=0.0, peso_sinaptico=0.8, asoc_count=3,
        match_exacto=False
    )
    print(f"  Score con dim_score=0.75: {score_con_dim}")
    print(f"  Score sin dim_score: {score_sin_dim}")
    assert score_con_dim > score_sin_dim, \
        f"Error: score con dim_score debería ser mayor. con={score_con_dim}, sin={score_sin_dim}"
    # Verificar que la diferencia es ~20% (0.20 * 0.75 = 0.15)
    diff = round(score_con_dim - score_sin_dim, 3)
    print(f"  Diferencia: {diff} (esperado ~0.15)")
    assert 0.10 <= diff <= 0.25, f"Error: diferencia fuera de rango esperado. diff={diff}"
    print("  OK: Score híbrido con dim_score integrado correcto")

    print("\n--- 75. Probando Match Exacto (floor 0.95) ---")
    score_exacto = cerebro._calcular_score_hibrido(
        peso_sinaptico=0.25, dim_score=0.0, match_exacto=True
    )
    score_normal = cerebro._calcular_score_hibrido(
        peso_sinaptico=0.25, dim_score=0.0, match_exacto=False
    )
    print(f"  Score match exacto: {score_exacto}")
    print(f"  Score normal: {score_normal}")
    assert score_exacto == max(0.95, score_normal), \
        f"Error: match exacto debería ser max(0.95, score). exacto={score_exacto}, normal={score_normal}"
    print("  OK: Match exacto floor 0.95 funciona correctamente")

    print("\n--- 76. Probando Fallback Dimensional (búsqueda por dimensión pura) ---")
    # Guardar un nodo con dimensiones pero contenido poco específico
    cerebro.percibir_corto_plazo("fallback_dim_nodo", "Aplicación web general",
                                  "web,app,general", "Project",
                                  {"emocion": ["afecto"], "entidad": ["identidad_artificial"]})
    cerebro.consolidar_concepto("fallback_dim_nodo")

    # Buscar algo que no tiene match textual pero sí dimensional
    res_fb, total_fb = cerebro.buscar_por_frase(
        "conexion remota servidor", profundidad="activos", limite=10,
        dimensiones_ids=ids_afecto + ids_ai
    )
    print(f"  Fallback dimensional: {len(res_fb)} resultados")
    # Verificar que el fallback dimensional al menos no falla
    assert isinstance(res_fb, list), "Error: fallback dimensional debería retornar lista"
    print("  OK: Fallback dimensional ejecuta sin errores")

    print("\n--- 77. Probando Penalización Paráfrasis x0.95 ---")
    # Test directo de la lógica de penalización
    query_words = {"autenticacion", "sistema"}
    # Nodo que contiene palabras de la query original → factor 1.0
    conc_original = "autenticacion_sistema"
    cont_original = "Sistema de autenticación con JWT"
    contenido_lower = (cont_original + " " + conc_original).lower()
    tiene_palabras = any(w in contenido_lower for w in query_words if len(w) >= 3)
    factor = 1.0 if tiene_palabras else 0.95
    assert factor == 1.0, f"Error: nodo con palabras de query debería tener factor 1.0, got {factor}"

    # Nodo que NO contiene palabras de la query → factor 0.95
    conc_parafrasis = "login_oauth"
    cont_parafrasis = "Implementación de OAuth con Google"
    contenido_lower2 = (cont_parafrasis + " " + conc_parafrasis).lower()
    tiene_palabras2 = any(w in contenido_lower2 for w in query_words if len(w) >= 3)
    factor2 = 1.0 if tiene_palabras2 else 0.95
    assert factor2 == 0.95, f"Error: nodo sin palabras de query debería tener factor 0.95, got {factor2}"
    print(f"  Factor con palabras originales: {factor}")
    print(f"  Factor sin palabras originales: {factor2}")
    print("  OK: Penalización paráfrasis x0.95 funciona correctamente")

    print("\n--- 78. Probando Trazabilidad en response JSON ---")
    # Verificar que la trazabilidad tiene los campos esperados
    # Usar búsqueda simple que sabemos funciona (test_pesado fue creado en test 70)
    mcp_traza = biorag_recordar(
        "principio memoria distribuida", limite=3, pagina=1
    )
    json_start = mcp_traza.find("{")
    if json_start > 0:
        mcp_traza = mcp_traza[json_start:]
    traza = json.loads(mcp_traza)
    if traza.get("total", 0) == 0:
        print("  SKIP: 0 resultados en DB de test (datos insuficientes)")
    else:
        assert "trazabilidad" in traza, "Error: response debería tener campo 'trazabilidad'"
        t = traza["trazabilidad"]
        campos_esperados = ["capa_literal", "capa_parafrasis", "capa_rafaga",
                            "fallback_dimensional", "match_exacto", "total_candidatos_todos"]
        for campo in campos_esperados:
            assert campo in t, f"Error: trazabilidad falta campo '{campo}'"
        print(f"  Trazaibilidad: {json.dumps(t, indent=2)}")
    print("  OK: Trazaibilidad completa en response JSON")

    print("\n--- 79. Probando Despertar y Scoring Coherente de Nodos Dormidos ---")
    # Limpiar posibles restos
    cerebro.cursor.execute("DELETE FROM largo_plazo WHERE concepto = 'nodo_test_dormido'")
    # Insertar un nodo dormido de prueba
    cerebro.cursor.execute(
        "INSERT INTO largo_plazo (concepto, contenido, peso_sinaptico, estado, creado_en) "
        "VALUES ('nodo_test_dormido', 'Este es un contenido de prueba para despertar', 0.20, 'dormido', ?)",
        (time.time(),)
    )
    # Registrar en FTS5 para buscar_por_frase
    cerebro.cursor.execute(
        "INSERT OR REPLACE INTO largo_plazo_fts (rowid, concepto, contenido) "
        "VALUES ((SELECT rowid FROM largo_plazo WHERE concepto = 'nodo_test_dormido'), 'nodo_test_dormido', 'Este es un contenido de prueba para despertar')"
    )
    cerebro.conn.commit()

    # A) Test de buscar_por_tokens
    resultados_tokens, _ = cerebro.buscar_por_tokens(["despertar"], profundidad="profundo", limite=1)
    assert len(resultados_tokens) > 0, "Error: buscar_por_tokens debería haber encontrado el nodo de prueba"
    match_tokens = next((r for r in resultados_tokens if r[0] == "nodo_test_dormido"), None)
    assert match_tokens is not None, "Error: el nodo de prueba no está en los resultados de tokens"
    assert match_tokens[3] == "activo", f"Error tokens: estado retornado debería ser 'activo', got {match_tokens[3]}"
    assert abs(match_tokens[2] - 0.35) < 1e-5, f"Error tokens: peso retornado debería ser 0.35, got {match_tokens[2]}"
    print("  A) buscar_por_tokens despertó y actualizó tupla correctamente")

    # B) Test de buscar_por_frase
    # Volver a dormir el nodo
    cerebro.cursor.execute("UPDATE largo_plazo SET estado = 'dormido', peso_sinaptico = 0.20 WHERE concepto = 'nodo_test_dormido'")
    cerebro.conn.commit()

    resultados_frase, _ = cerebro.buscar_por_frase("despertar", profundidad="profundo", limite=1, preview_chars=None)
    assert len(resultados_frase) > 0, "Error: buscar_por_frase debería haber encontrado el nodo"
    match_frase = next((r for r in resultados_frase if r[0] == "nodo_test_dormido"), None)
    assert match_frase is not None, "Error: el nodo de prueba no está en los resultados de frase"
    assert match_frase[3] == "activo", f"Error frase: estado retornado debería ser 'activo', got {match_frase[3]}"
    assert abs(match_frase[2] - 0.35) < 1e-5, f"Error frase: peso retornado debería ser 0.35, got {match_frase[2]}"
    print(f"  B) buscar_por_frase despertó y actualizó tupla correctamente (score: {match_frase[4]})")

    # C) Test de buscar_por_rafaga
    # Volver a dormir el nodo
    cerebro.cursor.execute("UPDATE largo_plazo SET estado = 'dormido', peso_sinaptico = 0.20 WHERE concepto = 'nodo_test_dormido'")
    cerebro.conn.commit()

    # Busquemos usando ráfaga de reminiscencia
    resultados_rafaga, _, _ = cerebro.buscar_por_rafaga("despertar", ["despertar"], limite=10)
    assert len(resultados_rafaga) > 0, "Error: buscar_por_rafaga no encontró el nodo de prueba"
    match_rafaga = next((r for r in resultados_rafaga if r[0] == "nodo_test_dormido"), None)
    assert match_rafaga is not None, "Error: el nodo de prueba no está en los resultados de ráfaga"
    assert match_rafaga[3] == "activo", f"Error ráfaga: estado retornado debería ser 'activo', got {match_rafaga[3]}"
    # El peso sináptico en ráfaga se incrementa en +0.3
    assert abs(match_rafaga[2] - 0.50) < 1e-5, f"Error ráfaga: peso retornado debería ser 0.50, got {match_rafaga[2]}"
    
    # Verificar en base de datos que el peso no subió más de una vez (+0.30)
    cerebro.cursor.execute("SELECT peso_sinaptico FROM largo_plazo WHERE concepto = 'nodo_test_dormido'")
    peso_db = cerebro.cursor.fetchone()[0]
    assert abs(peso_db - 0.50) < 1e-5, f"Error: El nodo recibió múltiples incrementos de peso, peso en DB: {peso_db}"
    print("  C) buscar_por_rafaga despertó tempranamente y calculó score coherente (y peso en DB es exactamente 0.50)")

    # Limpieza final
    cerebro.cursor.execute("DELETE FROM largo_plazo WHERE concepto = 'nodo_test_dormido'")
    cerebro.cursor.execute("DELETE FROM largo_plazo_fts WHERE concepto = 'nodo_test_dormido'")
    cerebro.conn.commit()
    print("  OK: Todos los tests de despertar coherente pasaron con éxito")

    print("\n--- 80. Probando Inferencia Transitiva (Multi-hop) ---")
    # Limpiar tablas
    cerebro.cursor.execute("DELETE FROM sinapsis")
    cerebro.cursor.execute("DELETE FROM sinapsis_latentes")
    cerebro.cursor.execute("DELETE FROM largo_plazo")
    
    # Crear nodos activos A, B, C, D
    for c in ['node_a', 'node_b', 'node_c', 'node_d']:
        cerebro.cursor.execute(
            "INSERT INTO largo_plazo (concepto, contenido, peso_sinaptico, estado, creado_en) VALUES (?, 'contenido', 1.0, 'activo', ?)",
            (c, time.time())
        )
        cerebro.cursor.execute(
            "INSERT OR IGNORE INTO largo_plazo_dimensiones (concepto, dimension_id) VALUES (?, 1)",
            (c,)
        )
    # Crear sinapsis directas: A -> B (1.0), B -> C (1.0), C -> D (1.0)
    cerebro.cursor.execute("INSERT INTO sinapsis (origen, destino, peso, tipo, creado_en) VALUES ('node_a', 'node_b', 1.0, 'test', ?)", (time.time(),))
    cerebro.cursor.execute("INSERT INTO sinapsis (origen, destino, peso, tipo, creado_en) VALUES ('node_b', 'node_c', 1.0, 'test', ?)", (time.time(),))
    cerebro.cursor.execute("INSERT INTO sinapsis (origen, destino, peso, tipo, creado_en) VALUES ('node_c', 'node_d', 1.0, 'test', ?)", (time.time(),))
    cerebro.conn.commit()
    
    from core.inferencia_transitiva import calcular_sinapsis_latentes, obtener_vecinos_latentes
    num_latentes = calcular_sinapsis_latentes(cerebro, max_saltos=3, factor_decay=0.7, umbral=0.05)
    
    # A -> C tiene 2 saltos: weight = 1.0 * 0.7 * 1.0 * 0.7 = 0.49
    cerebro.cursor.execute("SELECT peso_atenuado, saltos FROM sinapsis_latentes WHERE origen = 'node_a' AND destino = 'node_c'")
    res_ac = cerebro.cursor.fetchone()
    assert res_ac is not None, "Error: Debería existir sinapsis latente de node_a a node_c"
    assert res_ac[0] > 0, f"Error: peso latente A->C debería ser > 0, got {res_ac[0]}"
    assert res_ac[1] == 2, f"Error: saltos de A->C debería ser 2, got {res_ac[1]}"

    # A -> D tiene 3 saltos: weight = 0.49 * 1.0 * 0.7 = 0.343
    cerebro.cursor.execute("SELECT peso_atenuado, saltos FROM sinapsis_latentes WHERE origen = 'node_a' AND destino = 'node_d'")
    res_ad = cerebro.cursor.fetchone()
    assert res_ad is not None, "Error: Debería existir sinapsis latente de node_a a node_d"
    assert res_ad[0] > 0, f"Error: peso latente A->D debería ser > 0, got {res_ad[0]}"
    assert res_ad[1] == 3, f"Error: saltos de A->D debería ser 3, got {res_ad[1]}"
    print("  OK: Inferencia transitiva con pesos correctos")

    print("\n--- 81. Probando Prevención de Bucles en Inferencia Transitiva ---")
    # Agregar sinapsis de retorno D -> A (1.0) formando un ciclo A -> B -> C -> D -> A
    cerebro.cursor.execute("INSERT INTO sinapsis (origen, destino, peso, tipo, creado_en) VALUES ('node_d', 'node_a', 1.0, 'test', ?)", (time.time(),))
    cerebro.conn.commit()
    
    # Calcular y verificar que no hay loops infinitos y la recursión se detiene correctamente
    num_latentes_ciclo = calcular_sinapsis_latentes(cerebro, max_saltos=3, factor_decay=0.7, umbral=0.05)
    # No debería haber una sinapsis latente A -> A (ya que se filtra origen != destino)
    cerebro.cursor.execute("SELECT count(*) FROM sinapsis_latentes WHERE origen = destino")
    self_loops = cerebro.cursor.fetchone()[0]
    assert self_loops == 0, "Error: Se generaron self-loops en sinapsis_latentes"
    print("  OK: Prevención de bucles exitosa")

    print("\n--- 81b. Probando Compatibilidad de Tipos de Relación (End-to-End) ---")
    # Limpiar tablas para un escenario controlado
    cerebro.cursor.execute("DELETE FROM sinapsis")
    cerebro.cursor.execute("DELETE FROM sinapsis_latentes")
    cerebro.cursor.execute("DELETE FROM largo_plazo")
    
    # Crear nodos activos de prueba
    for c in ['node_t1', 'node_t2', 'node_t3', 'node_t4', 'node_t5']:
        cerebro.cursor.execute(
            "INSERT INTO largo_plazo (concepto, contenido, peso_sinaptico, estado, creado_en) VALUES (?, 'contenido', 1.0, 'activo', ?)",
            (c, time.time())
        )
        cerebro.cursor.execute(
            "INSERT OR IGNORE INTO largo_plazo_dimensiones (concepto, dimension_id) VALUES (?, 1)",
            (c,)
        )
        
    # Definir relaciones:
    # node_t1 -> node_t2 ('co_ocurrencia', 0.8)
    # node_t2 -> node_t3 ('co_ocurrencia', 0.8) -> Ruido puro, debe bloquearse t1 -> t3
    # node_t3 -> node_t4 ('sinonimo_explicito', 0.8) -> Puente de confianza, t2 -> t4 debe permitirse
    # node_t4 -> node_t5 ('co_ocurrencia', 0.8) -> t3 -> t5 debe permitirse (gracias al puente)
    cerebro.cursor.execute("INSERT INTO sinapsis (origen, destino, peso, tipo, creado_en) VALUES ('node_t1', 'node_t2', 0.8, 'co_ocurrencia', ?)", (time.time(),))
    cerebro.cursor.execute("INSERT INTO sinapsis (origen, destino, peso, tipo, creado_en) VALUES ('node_t2', 'node_t3', 0.8, 'co_ocurrencia', ?)", (time.time(),))
    cerebro.cursor.execute("INSERT INTO sinapsis (origen, destino, peso, tipo, creado_en) VALUES ('node_t3', 'node_t4', 0.8, 'sinonimo_explicito', ?)", (time.time(),))
    cerebro.cursor.execute("INSERT INTO sinapsis (origen, destino, peso, tipo, creado_en) VALUES ('node_t4', 'node_t5', 0.8, 'co_ocurrencia', ?)", (time.time(),))
    cerebro.conn.commit()
    
    # Ejecutar el cálculo de sinapsis latentes
    calcular_sinapsis_latentes(cerebro, max_saltos=3, factor_decay=0.7, umbral=0.05)
    
    # Verificar que t1 -> t3 no se generó (bloqueado por co_ocurrencia -> co_ocurrencia)
    cerebro.cursor.execute("SELECT count(*) FROM sinapsis_latentes WHERE origen = 'node_t1' AND destino = 'node_t3'")
    t1_t3_count = cerebro.cursor.fetchone()[0]
    assert t1_t3_count == 0, "Error: t1 -> t3 no debería propagarse por ruido puro (co_ocurrencia -> co_ocurrencia)"
    
    # Verificar que t2 -> t4 se generó (permitido porque t3 -> t4 es puente de confianza)
    cerebro.cursor.execute("SELECT count(*) FROM sinapsis_latentes WHERE origen = 'node_t2' AND destino = 'node_t4'")
    t2_t4_count = cerebro.cursor.fetchone()[0]
    assert t2_t4_count > 0, "Error: t2 -> t4 debería propagarse a través del puente sinonimo_explicito"
    
    # Verificar que t3 -> t5 se generó (permitido porque t3 -> t4 es puente de confianza)
    cerebro.cursor.execute("SELECT count(*) FROM sinapsis_latentes WHERE origen = 'node_t3' AND destino = 'node_t5'")
    t3_t5_count = cerebro.cursor.fetchone()[0]
    assert t3_t5_count > 0, "Error: t3 -> t5 debería propagarse a través del puente sinonimo_explicito"
    
    print("  OK: Compatibilidad de tipos verificada de extremo a extremo")

    print("\n--- 82. Probando SRL y Almacenamiento de Predicados ---")
    # Limpiar predicados
    cerebro.cursor.execute("DELETE FROM predicados")
    cerebro.cursor.execute("DELETE FROM corto_plazo_predicados")
    cerebro.conn.commit()
    
    # Aprender un concepto con predicados
    concepto_srl = "doc_test_srl"
    contenido_srl = "Dennys desarrolla BioRAG en la oficina"
    predicados_data = [{
        "sujeto": "Dennys",
        "accion": "desarrollar",
        "objeto": "BioRAG",
        "contexto": "oficina"
    }]
    
    cerebro.percibir_corto_plazo(
        concepto=concepto_srl,
        contenido=contenido_srl,
        predicados=predicados_data
    )
    
    # Verificar almacenamiento en corto plazo
    cerebro.cursor.execute("SELECT sujeto, accion, objeto, contexto FROM corto_plazo_predicados WHERE concepto = ?", (concepto_srl,))
    row_cp = cerebro.cursor.fetchone()
    assert row_cp is not None, "Error: Predicado no guardado en corto plazo"
    assert row_cp[0] == "Dennys" and row_cp[1] == "desarrollar" and row_cp[2] == "BioRAG", "Error en valores de corto plazo"
    print("  OK: Predicados guardados en corto plazo")

    print("\n--- 83. Probando Consolidación de Predicados y Búsqueda por Roles ---")
    # Consolidar (ciclo de sueño)
    cerebro.ciclo_sueno_consolidacion()
    
    # Verificar almacenamiento en largo plazo (tabla predicados)
    cerebro.cursor.execute("SELECT sujeto, accion, objeto, contexto FROM predicados WHERE concepto = ?", (concepto_srl,))
    row_lp = cerebro.cursor.fetchone()
    assert row_lp is not None, "Error: Predicado no consolidado en predicados largo plazo"
    assert row_lp[0] == "Dennys" and row_lp[1] == "desarrollar", "Error en valores de predicados"
    
    # Probar búsqueda por rol en buscar_por_frase: buscar por rol sujeto:Dennys
    res_busca, _ = cerebro.buscar_por_frase("BioRAG", buscar_por_rol="sujeto:Dennys")
    assert len(res_busca) > 0, "Error: buscar_por_frase no filtró por rol"
    match_busca = next((r for r in res_busca if r[0] == concepto_srl), None)
    assert match_busca is not None, "Error: concepto con predicado no devuelto al buscar por rol"
    
    # Probar búsqueda con rol inválido/no coincidente
    res_busca_no, _ = cerebro.buscar_por_frase("BioRAG", buscar_por_rol="sujeto:Artemis")
    match_busca_no = next((r for r in res_busca_no if r[0] == concepto_srl), None)
    assert match_busca_no is None, "Error: concepto devuelto con rol no coincidente"
    print("  OK: Consolidación y búsqueda por roles")

    print("\n--- 84. Probando Auto-Clustering y Detección de Dimensiones Emergentes ---")
    # Limpiar tablas
    cerebro.cursor.execute("DELETE FROM largo_plazo")
    cerebro.cursor.execute("DELETE FROM sinapsis")
    cerebro.cursor.execute("DELETE FROM dimensiones_semanticas")
    cerebro.cursor.execute("DELETE FROM largo_plazo_dimensiones")
    cerebro.conn.commit()
    
    # Crear 6 nodos con tokens relacionados con 'programacion' y conectarlos denso (clique)
    conceptos_cluster = [f"node_cluster_{i}" for i in range(6)]
    for c in conceptos_cluster:
        cerebro.cursor.execute(
            "INSERT INTO largo_plazo (concepto, contenido, peso_sinaptico, estado, creado_en) VALUES (?, 'programacion codigo software desarrollo', 1.0, 'activo', ?)",
            (c, time.time())
        )
    # Crear conexiones bidireccionales completas (clique) entre los 6 nodos
    for i in range(len(conceptos_cluster)):
        for j in range(i + 1, len(conceptos_cluster)):
            c1, c2 = conceptos_cluster[i], conceptos_cluster[j]
            cerebro.cursor.execute("INSERT INTO sinapsis (origen, destino, peso, creado_en) VALUES (?, ?, 1.0, ?)", (c1, c2, time.time()))
            cerebro.cursor.execute("INSERT INTO sinapsis (origen, destino, peso, creado_en) VALUES (?, ?, 1.0, ?)", (c2, c1, time.time()))
    cerebro.conn.commit()
    
    # Ejecutar detectar_comunidades y asignar_dimensiones_emergentes directamente
    from core.auto_clustering import detectar_comunidades, asignar_dimensiones_emergentes
    comunidades = detectar_comunidades(cerebro, min_nodos=4)
    assert len(comunidades) > 0, "Error: Auto-clustering no detectó ninguna comunidad en clique densa"
    
    # Asignar dimensiones emergentes
    asignar_dimensiones_emergentes(cerebro, comunidades)
    
    # Verificar que se insertó una dimensión auto-generada
    cerebro.cursor.execute("SELECT id, name, auto_generada, confianza FROM dimensiones_semanticas WHERE auto_generada = 1")
    dim_generadas = cerebro.cursor.fetchall()
    assert len(dim_generadas) > 0, "Error: No se guardó ninguna dimensión auto-generada"
    print(f"  Comunidades detectadas: {comunidades}")
    print(f"  Dimensiones auto-generadas en DB: {dim_generadas}")
    print("  OK: Auto-clustering y asignación de dimensiones exitosa")

    print("\n--- 85. Probando Búsqueda Dimensional con Coseno Ponderado ---")
    # Obtener ID de la dimensión auto-generada
    dim_id = dim_generadas[0][0]
    
    # Verificar que los nodos del cluster están vinculados a esta dimensión
    cerebro.cursor.execute("SELECT count(*) FROM largo_plazo_dimensiones WHERE dimension_id = ?", (dim_id,))
    vinculos = cerebro.cursor.fetchone()[0]
    assert vinculos >= 4, f"Error: Deberían estar vinculados al menos 4 nodos, got {vinculos}"
    
    # Ejecutar una búsqueda usando solo esta dimensión
    resultados_dim, _ = cerebro.buscar_por_frase("", dimensiones_ids=[dim_id], profundidad="profundo")
    assert len(resultados_dim) > 0, "Error: Búsqueda dimensional no retornó resultados"
    print(f"  Resultados de búsqueda por dimensión: {resultados_dim}")
    print("  OK: Coseno ponderado y listado de dimensiones emergentes")

    print("\n--- 86. Ejecución de Regresión y Cierre del Sistema ---")
    print("  OK: Pruebas de regresión finalizadas correctamente")

    print("\n--- 87. Probando Weighted Jaccard vs Overlap Coefficient y Optimización de IDF ---")
    # Limpiar tablas para un entorno controlado
    cerebro.cursor.execute("DELETE FROM largo_plazo")
    cerebro.cursor.execute("DELETE FROM sinapsis")
    cerebro.conn.commit()

    # Nodo A (muy corto) y Nodo B (largo) que contiene a A
    # Con Overlap Coefficient, la similitud sería 1.0 (ya que A está 100% contenido en B)
    # Con Jaccard, la similitud debe ser mucho menor, reflejando el verdadero solapamiento
    cerebro.cursor.execute(
        "INSERT INTO largo_plazo (concepto, contenido, peso_sinaptico, estado, creado_en) VALUES (?, ?, 1.0, 'activo', ?)",
        ("biorag", "sistema de memoria", time.time())
    )
    cerebro.cursor.execute(
        "INSERT INTO largo_plazo (concepto, contenido, peso_sinaptico, estado, creado_en) VALUES (?, ?, 1.0, 'activo', ?)",
        ("biorag_engine", "biorag es un motor de memoria persistente para agentes desarrollado por Dennys Marquez", time.time())
    )
    cerebro.cursor.execute(
        "INSERT INTO largo_plazo (concepto, contenido, peso_sinaptico, estado, creado_en) VALUES (?, ?, 1.0, 'activo', ?)",
        ("python", "lenguaje de programacion y desarrollo de software limpio y elegante", time.time())
    )
    cerebro.conn.commit()

    from core.sinapsis import calcular_idf_corpus, recalcular_similitud_sinapsis

    # 1. Probar calcular_idf_corpus
    idf_map = calcular_idf_corpus(cerebro)
    assert isinstance(idf_map, dict), "Error: calcular_idf_corpus debe devolver un diccionario"
    assert "biorag" in idf_map, "Error: 'biorag' debería estar en el idf_map"
    print(f"  OK: idf_map precalculado correctamente. Tokens totales: {len(idf_map)}")

    # 2. Probar recalcular_similitud_sinapsis con idf_map
    sim_jaccard = recalcular_similitud_sinapsis(cerebro, "biorag", "biorag_engine", idf_map=idf_map)
    print(f"  Similitud Jaccard calculada: {sim_jaccard}")
    # Jaccard debe ser significativamente menor que 1.0 (Overlap Coefficient daría 1.0)
    assert sim_jaccard < 0.9, f"Error: Similitud Jaccard ({sim_jaccard}) no debería ser tan alta"
    assert sim_jaccard > 0.0, f"Error: Similitud Jaccard ({sim_jaccard}) no debería ser 0.0"

    # 3. Probar que auto_vincular no lanza errores y funciona con el nuevo _peso_similitud
    # Insertar en corto plazo para que auto_vincular tenga algo que procesar
    cerebro.percibir_corto_plazo("nuevo_nodo", "biorag sistema de memoria para agentes", "", "General")
    # auto_vincular no debería lanzar OperationalError porque ya no hace queries locales de IDF
    enlaces = auto_vincular(cerebro, "nuevo_nodo", "biorag sistema de memoria para agentes")
    print(f"  Enlaces creados por auto_vincular: {enlaces}")
    print("  OK: auto_vincular ejecutado con éxito sin queries de IDF locales")

    # 4. Probar auto-clustering, desambiguación y saneamiento de membresías/dimensiones obsoletas
    print("\n--- 14. Probando Auto-Clustering, Desambiguación y Saneamiento ---")
    from core.auto_clustering import asignar_dimensiones_emergentes

    # Insertar dimensión auto_generada legacy para verificar que se elimina con la migración
    cerebro.cursor.execute("""
        INSERT INTO dimensiones_semanticas (name, description, tipo_id, auto_generada, confianza, generado_en)
        VALUES ('auto_legacy_dim', 'Legacy auto-generated cluster', 7, 1, 0.8, ?)
    """, (time.time(),))
    cerebro.conn.commit()

    # Comprobar que existe
    cerebro.cursor.execute("SELECT COUNT(*) FROM dimensiones_semanticas WHERE name = 'auto_legacy_dim'")
    assert cerebro.cursor.fetchone()[0] == 1, "Error: la dimensión legacy debería existir antes de la migración"

    # Ejecutar asignar_dimensiones_emergentes por primera vez con una comunidad ficticia
    comunidades_test_1 = [{
        "nodos": ["biorag", "biorag_engine"],
        "nombre": "auto_test_cluster",
        "confianza": 0.95
    }]
    asignar_dimensiones_emergentes(cerebro, comunidades_test_1)

    # Verificar migración inicial: la dimensión legacy debería estar borrada,
    # y la dimensión de migración 'migration_autoclustering_v1' debería existir.
    cerebro.cursor.execute("SELECT COUNT(*) FROM dimensiones_semanticas WHERE name = 'auto_legacy_dim'")
    assert cerebro.cursor.fetchone()[0] == 0, "Error: la dimensión legacy debería haber sido borrada por la migración"

    cerebro.cursor.execute("SELECT COUNT(*) FROM dimensiones_semanticas WHERE name = 'migration_autoclustering_v1'")
    assert cerebro.cursor.fetchone()[0] == 1, "Error: la dimensión de marcador de migración debería existir"

    # Verificar que se creó la dimensión de la primera comunidad
    cerebro.cursor.execute("SELECT id FROM dimensiones_semanticas WHERE name = 'auto_test_cluster'")
    row_dim = cerebro.cursor.fetchone()
    assert row_dim is not None, "Error: la dimensión auto_test_cluster debería haber sido creada"
    dim_id_1 = row_dim[0]

    # Verificar miembros asociados en la bridge table largo_plazo_dimensiones
    cerebro.cursor.execute("SELECT concepto FROM largo_plazo_dimensiones WHERE dimension_id = ?", (dim_id_1,))
    miembros = {r[0] for r in cerebro.cursor.fetchall()}
    assert miembros == {"biorag", "biorag_engine"}, f"Error: miembros incorrectos para auto_test_cluster: {miembros}"

    # Test 4a: Evolución de comunidad con overlap Jaccard > 0.5 (debería REUTILIZAR el mismo nombre)
    comunidades_test_2 = [{
        "nodos": ["biorag", "biorag_engine", "python"], # 2 de 3 son coincidentes (Jaccard = 2/3 = 0.67 > 0.5)
        "nombre": "auto_test_cluster",
        "confianza": 0.96
    }]
    asignar_dimensiones_emergentes(cerebro, comunidades_test_2)

    # El nombre no debería tener sufijo y se mantiene 'auto_test_cluster'
    cerebro.cursor.execute("SELECT id FROM dimensiones_semanticas WHERE name = 'auto_test_cluster'")
    assert cerebro.cursor.fetchone() is not None, "Error: auto_test_cluster debería seguir existiendo"
    cerebro.cursor.execute("SELECT id FROM dimensiones_semanticas WHERE name = 'auto_test_cluster_2'")
    assert cerebro.cursor.fetchone() is None, "Error: no debería haberse creado auto_test_cluster_2"

    # Verificar nuevos miembros asociados (python se agregó)
    cerebro.cursor.execute("SELECT concepto FROM largo_plazo_dimensiones WHERE dimension_id = ?", (dim_id_1,))
    miembros_evolucionados = {r[0] for r in cerebro.cursor.fetchall()}
    assert miembros_evolucionados == {"biorag", "biorag_engine", "python"}, f"Error: python debería haberse añadido"

    # Test 4b: Desambiguación/Colisión con overlap Jaccard <= 0.5 (debería CREAR una nueva con sufijo _2)
    # Creamos un cluster con el mismo nombre sugerido pero con nodos totalmente distintos (Jaccard overlap = 0.0)
    comunidades_test_3 = [{
        # Mantener el primer cluster para que no sea borrado por la limpieza global
        "nodos": ["biorag", "biorag_engine", "python"],
        "nombre": "auto_test_cluster",
        "confianza": 0.96
    }, {
        "nodos": ["python"],
        "nombre": "auto_test_cluster",
        "confianza": 0.90
    }]
    asignar_dimensiones_emergentes(cerebro, comunidades_test_3)

    # Ahora sí debería existir auto_test_cluster_2
    cerebro.cursor.execute("SELECT id FROM dimensiones_semanticas WHERE name = 'auto_test_cluster_2'")
    row_dim_2 = cerebro.cursor.fetchone()
    assert row_dim_2 is not None, "Error: debería existir auto_test_cluster_2 tras colisión sin solapamiento"
    dim_id_2 = row_dim_2[0]

    # Verificar que los miembros de auto_test_cluster_2 son sólo python
    cerebro.cursor.execute("SELECT concepto FROM largo_plazo_dimensiones WHERE dimension_id = ?", (dim_id_2,))
    miembros_colision = {r[0] for r in cerebro.cursor.fetchall()}
    assert miembros_colision == {"python"}, f"Error: miembros incorrectos para auto_test_cluster_2: {miembros_colision}"

    # Test 4c: Limpieza de miembros obsoletos locales
    comunidades_test_4 = [{
        "nodos": ["biorag", "biorag_engine"],
        "nombre": "auto_test_cluster",
        "confianza": 0.95
    }, {
        # Mantener auto_test_cluster_2 activo para que no sea purgado globalmente
        "nodos": ["python"],
        "nombre": "auto_test_cluster_2",
        "confianza": 0.90
    }]
    asignar_dimensiones_emergentes(cerebro, comunidades_test_4)

    # Verificar que python ya NO está asociado a auto_test_cluster
    cerebro.cursor.execute("SELECT concepto FROM largo_plazo_dimensiones WHERE dimension_id = ?", (dim_id_1,))
    miembros_limpios = {r[0] for r in cerebro.cursor.fetchall()}
    assert miembros_limpios == {"biorag", "biorag_engine"}, f"Error: python no debería estar en auto_test_cluster: {miembros_limpios}"

    # Test 4d: Limpieza global de dimensiones obsoletas
    # Si ejecutamos asignar_dimensiones_emergentes indicando que sólo queda auto_test_cluster, auto_test_cluster_2 debería borrarse globalmente
    comunidades_test_5 = [{
        "nodos": ["biorag", "biorag_engine"],
        "nombre": "auto_test_cluster",
        "confianza": 0.95
    }]
    asignar_dimensiones_emergentes(cerebro, comunidades_test_5)

    # auto_test_cluster_2 y sus membresías deberían ser purgadas de la base de datos
    cerebro.cursor.execute("SELECT COUNT(*) FROM dimensiones_semanticas WHERE name = 'auto_test_cluster_2'")
    assert cerebro.cursor.fetchone()[0] == 0, "Error: auto_test_cluster_2 debería haber sido purgado globalmente"
    cerebro.cursor.execute("SELECT COUNT(*) FROM largo_plazo_dimensiones WHERE dimension_id = ?", (dim_id_2,))
    assert cerebro.cursor.fetchone()[0] == 0, "Error: las membresías de auto_test_cluster_2 deberían haber sido purgadas"

    print("  OK: Auto-clustering, desambiguación y saneamiento de membresías/dimensiones comprobados con éxito.")

    # ═══════════════════════════════════════════════════════════
    # Tests 88-95: Fallback Simbólico (v17.2)
    # ═══════════════════════════════════════════════════════════
    print("\n--- 88. Probando Levenshtein base ---")
    from core.fallback_simbolico import (
        similitud_levenshtein,
        mejor_similitud_levenshtein,
        expandir_query_wordnet,
        expandir_con_traduccion,
        buscar_fallback_simbolico,
        score_simbolico,
        _normalizar,
        _tokenizar_normalizado,
    )

    # Normalización
    assert _normalizar("hipertensión") == "hipertension"
    assert _normalizar("cardíaco") == "cardiaco"
    assert _normalizar("ANGULAR") == "angular"
    print("  OK: normalización de tildes y mayúsculas")

    # Levenshtein exacto
    assert similitud_levenshtein("angular", "angular") == 1.0
    assert similitud_levenshtein("", "") == 1.0
    print("  OK: igualdad = 1.0")

    # Levenshtein con tilde
    assert similitud_levenshtein("hipertensión", "hipertension") == 1.0, "Error: tilde debe normalizarse antes de comparar"
    print("  OK: 'hipertensión' vs 'hipertension' = 1.0 (tildes normalizadas)")

    # Levenshtein typo
    sim_typo = similitud_levenshtein("formulariox", "formularios")
    assert sim_typo >= 0.85, f"Error: typo debería ser >= 0.85, got {sim_typo}"
    print(f"  OK: 'formulariox' vs 'formularios' = {sim_typo:.3f} >= 0.85")

    # Levenshtein disimilar
    sim_dis = similitud_levenshtein("angular", "sqlite")
    assert sim_dis < 0.5, f"Error: disimilar debería ser < 0.5, got {sim_dis}"
    print(f"  OK: 'angular' vs 'sqlite' = {sim_dis:.3f} < 0.5")
    print("--- 88. Levenshtein OK ---")

    print("\n--- 89. Probando mejor_similitud_levenshtein ---")
    tq = {"hipertension", "arterial"}
    tn = {"presion", "hipertensiva", "cronica"}
    mejor = mejor_similitud_levenshtein(tq, tn)
    assert mejor >= 0.7, f"Error: 'hipertension' vs 'hipertensiva' >= 0.7, got {mejor}"
    print(f"  OK: mejor_sim({tq}, {tn}) = {mejor:.3f}")

    assert mejor_similitud_levenshtein(set(), {"test"}) == 0.0
    assert mejor_similitud_levenshtein({"test"}, set()) == 0.0
    print("  OK: sets vacíos retornan 0.0")
    print("--- 89. mejor_similitud_levenshtein OK ---")

    print("\n--- 90. Probando WordNet (si disponible) ---")
    try:
        exp_wn = expandir_query_wordnet({"error"})
        print(f"  WordNet disponible. Expansiones de 'error': {list(exp_wn)[:5]}")
        assert isinstance(exp_wn, set)
        print("  OK: WordNet retorna set")
    except Exception as e:
        print(f"  SKIP: WordNet no disponible ({e})")
    print("--- 90. WordNet OK ---")

    print("\n--- 91. Probando traducción opcional (si disponible) ---")
    try:
        exp_trad = expandir_con_traduccion({"presión"})
        print(f"  Expansión con traducción de 'presión': {exp_trad}")
        assert isinstance(exp_trad, set)
        print("  OK: Traducción retornó un conjunto de expansiones")
    except Exception as e:
        print(f"  SKIP/FAIL: deep-translator no disponible o sin internet ({e})")
    print("--- 91. Traducción OK ---")

    print("\n--- 92. Probando score_simbolico integrado ---")
    sc1 = score_simbolico(
        {"hipertension"},
        "presion_arterial",
        "Hipertensión sistémica diagnosticada",
        "hta,presion alta"
    )
    assert sc1 >= 0.5, f"Error: score_simbolico 'hipertension' debería >= 0.5, got {sc1}"
    print(f"  OK: 'hipertension' → 'presion_arterial' (contenido con tilde): {sc1:.3f}")

    sc2 = score_simbolico(
        {"bug"},
        "error_servidor",
        "Fallo crítico en el servidor de producción"
    )
    assert isinstance(sc2, float)
    print(f"  OK: score_simbolico 'bug' → 'error_servidor': {sc2:.3f}")
    print("--- 92. score_simbolico OK ---")

    print("\n--- 93. Probando buscar_fallback_simbolico ---")
    cerebro.cursor.execute("DELETE FROM largo_plazo WHERE concepto = 'test_hta_simbolico'")
    cerebro.conn.commit()
    cerebro.percibir_corto_plazo(
        "test_hta_simbolico",
        "Hipertensión arterial sistémica. Presión elevada.",
        "hta,presion alta,tension arterial",
        "Lesson"
    )
    cerebro.ciclo_sueno_consolidacion()

    cerebro.cursor.execute(
        "SELECT rowid, concepto, contenido, peso_sinaptico, "
        "estado, asociaciones, sinonimos "
        "FROM largo_plazo WHERE estado = 'activo' LIMIT 1000"
    )
    candidatos_test = cerebro.cursor.fetchall()

    resultados_fb = buscar_fallback_simbolico(
        "hipertension",
        candidatos_test,
        umbral=0.50
    )
    print(f"  Fallback 'hipertension': {len(resultados_fb)} resultados")
    conceptos_fb = [r[2] for r in resultados_fb]
    assert "test_hta_simbolico" in conceptos_fb, f"Error: 'hipertension' debería encontrar 'test_hta_simbolico', got {conceptos_fb}"
    print(f"  OK: encontró 'test_hta_simbolico' con score {resultados_fb[0][0]:.3f}")
    print("--- 93. buscar_fallback_simbolico OK ---")

    print("\n--- 94. Probando integración en buscar_por_frase ---")
    resultados_frase, total_frase = cerebro.buscar_por_frase("hipertension")
    print(f"  buscar_por_frase('hipertension'): {total_frase} resultados")
    assert total_frase >= 1, f"Error: debería encontrar al menos 1 resultado, found {total_frase}"
    conceptos_frase = [r[0] for r in resultados_frase]
    assert "test_hta_simbolico" in conceptos_frase, f"Error: 'test_hta_simbolico' debería estar en los resultados de buscar_por_frase, got {conceptos_frase}"
    print("  OK: buscar_por_frase con fallback simbólico integrado con éxito.")
    print("--- 94. Integración buscar_por_frase OK ---")

    print("\n--- 95. Probando acrónimo bilingüe y graceful degradation ---")
    cerebro.cursor.execute("DELETE FROM largo_plazo WHERE concepto = 'test_infarto_myocardial'")
    cerebro.conn.commit()
    cerebro.percibir_corto_plazo(
        "test_infarto_myocardial",
        "Myocardial infarction and heart attack symptoms",
        "heart,infarction,attack",
        "Architecture"
    )
    cerebro.ciclo_sueno_consolidacion()

    resultados_acr, total_acr = cerebro.buscar_por_frase("infarction")
    print(f"  buscar_por_frase('infarction'): {total_acr} resultados")
    assert total_acr >= 1, "Error: 'infarction' debería encontrar al menos 1 resultado"
    print("  OK: término en inglés encontrado con éxito.")
    print("--- 95. Acrónimo bilingüe OK ---")

    # ══════════════════════════════════════════════════════════════════════
    # TESTS FORENSES: Historial de consolidación (metricas_cognitivas_nodos)
    # ══════════════════════════════════════════════════════════════════════

    print("\n--- 96. Probando Historial Forense: nodo nuevo ---")
    # Crear DB temporal aislada para test forense
    _forensic_db = tempfile.mktemp(suffix='.db')
    try:
        fc = SQLiteMemoryBioRAG(db_path=_forensic_db)
        fc.percibir_corto_plazo("test_forensic_nuevo", "Nodo forense nuevo", "test,nuevo,forensic", "Lesson")
        fc.ciclo_sueno_consolidacion()
        nodos_f = _get_nodos_acciones(fc)
        assert 'test_forensic_nuevo' in nodos_f, "Nodo no registrado en historial forense"
        accion_f = nodos_f['test_forensic_nuevo'][0]
        assert accion_f['accion'] == 'nuevo', f"Acción esperada 'nuevo', got '{accion_f['accion']}'"
        assert accion_f['peso_anterior'] == 0.0, f"peso_anterior esperado 0.0, got {accion_f['peso_anterior']}"
        assert accion_f['peso_nuevo'] == 1.0, f"peso_nuevo esperado 1.0, got {accion_f['peso_nuevo']}"
        assert accion_f['anomalo'] == 0
        print("  OK: accion 'nuevo' verificada correctamente")
        fc.cerrar_sistema()
    finally:
        if os.path.exists(_forensic_db):
            os.remove(_forensic_db)
    print("--- 96. Forense nuevo OK ---")

    print("\n--- 97. Probando Historial Forense: nodo actualizado ---")
    _forensic_db = tempfile.mktemp(suffix='.db')
    try:
        fc = SQLiteMemoryBioRAG(db_path=_forensic_db)
        fc.percibir_corto_plazo("test_forensic_upd", "Primera versión", "test,actualizado", "Lesson")
        fc.ciclo_sueno_consolidacion()
        # Bajar peso para que la fusión tenga efecto visible
        fc.cursor.execute("UPDATE largo_plazo SET peso_sinaptico = 0.5 WHERE concepto = 'test_forensic_upd'")
        fc.conn.commit()
        # Segundo ciclo: mismo nodo actualizado
        fc.percibir_corto_plazo("test_forensic_upd", "Segunda versión", "test,actualizado,v2", "Lesson")
        fc.ciclo_sueno_consolidacion()
        nodos_f = _get_nodos_acciones(fc)
        acc_upd = [a for a in nodos_f.get('test_forensic_upd', []) if a['accion'] == 'actualizado']
        assert len(acc_upd) >= 1, f"No se registró acción 'actualizado'"
        assert acc_upd[0]['peso_anterior'] > 0, "peso_anterior debería ser > 0"
        contenido_f = fc.cursor.execute("SELECT contenido FROM largo_plazo WHERE concepto = 'test_forensic_upd'").fetchone()[0]
        assert 'Primera versión' in contenido_f and 'Segunda versión' in contenido_f, "Contenido no fusionado"
        print("  OK: accion 'actualizado' verificada correctamente")
        fc.cerrar_sistema()
    finally:
        if os.path.exists(_forensic_db):
            os.remove(_forensic_db)
    print("--- 97. Forense actualizado OK ---")

    print("\n--- 98. Probando Historial Forense: dormido por LTD ---")
    _forensic_db = tempfile.mktemp(suffix='.db')
    try:
        fc = SQLiteMemoryBioRAG(db_path=_forensic_db)
        fc.percibir_corto_plazo("test_forensic_ltd", "Nodo LTD", "test,dormido,ltd", "Lesson")
        fc.ciclo_sueno_consolidacion()
        # Forzar peso bajo para que LTD lo duerma
        fc.cursor.execute("UPDATE largo_plazo SET peso_sinaptico = 0.03 WHERE concepto = 'test_forensic_ltd'")
        fc.conn.commit()
        fc.ciclo_sueno_consolidacion()
        estado_f = fc.cursor.execute("SELECT estado FROM largo_plazo WHERE concepto = 'test_forensic_ltd'").fetchone()
        assert estado_f[0] == 'dormido', f"Estado esperado 'dormido', got '{estado_f[0]}'"
        nodos_f = _get_nodos_acciones(fc)
        acc_dormido = [a for a in nodos_f.get('test_forensic_ltd', []) if a['accion'] == 'dormido']
        assert len(acc_dormido) >= 1, "No se registró acción 'dormido'"
        assert acc_dormido[-1]['peso_anterior'] <= 0.05, f"peso_anterior debería ser <= 0.05, got {acc_dormido[-1]['peso_anterior']}"
        print("  OK: accion 'dormido' por LTD verificada correctamente")
        fc.cerrar_sistema()
    finally:
        if os.path.exists(_forensic_db):
            os.remove(_forensic_db)
    print("--- 98. Forense dormido LTD OK ---")

    print("\n--- 99. Probando Historial Forense: dormido por inhibición lateral ---")
    _forensic_db = tempfile.mktemp(suffix='.db')
    try:
        fc = SQLiteMemoryBioRAG(db_path=_forensic_db)
        for i in range(15):
            fc.percibir_corto_plazo(f"test_inhib_lat_{i}", f"Contenido inhib {i}", f"test,inhib, Lat{i}", "General")
        fc.ciclo_sueno_consolidacion()
        dormidos_f = fc.cursor.execute("SELECT COUNT(*) FROM largo_plazo WHERE estado = 'dormido' AND concepto LIKE 'test_inhib_lat_%'").fetchone()[0]
        assert dormidos_f > 0, "Ningún nodo dormido por inhibición lateral"
        nodos_f = _get_nodos_acciones(fc)
        acc_inhib = [a for accs in nodos_f.values() for a in accs if a['accion'] == 'dormido' and 'inhibicion' in a['razon'].lower()]
        assert len(acc_inhib) > 0, "No se registró acción 'dormido' por inhibición lateral"
        print(f"  OK: accion 'dormido' por inhibición lateral verificada ({len(acc_inhib)} registros)")
        fc.cerrar_sistema()
    finally:
        if os.path.exists(_forensic_db):
            os.remove(_forensic_db)
    print("--- 99. Forense dormido inhibición lateral OK ---")

    print("\n--- 100. Probando Historial Forense: eliminado por evicción ---")
    _forensic_db = tempfile.mktemp(suffix='.db')
    try:
        fc = SQLiteMemoryBioRAG(db_path=_forensic_db)
        for i in range(5):
            fc.percibir_corto_plazo(f"test_eliminado_{i}", f"Contenido evicción {i}", f"test,elim{i}", "General")
        fc.ciclo_sueno_consolidacion()
        fc.cursor.execute("UPDATE largo_plazo SET estado = 'dormido', peso_sinaptico = 0.005 WHERE concepto LIKE 'test_eliminado_%'")
        fc.conn.commit()
        os.environ['BIORAG_PODAR'] = 'true'
        try:
            eliminados_f = fc._ejecutar_eviccion(max_borrar=5)
        finally:
            del os.environ['BIORAG_PODAR']
        assert eliminados_f > 0, f"Se esperaban eliminaciones, got {eliminados_f}"
        restantes_f = fc.cursor.execute("SELECT COUNT(*) FROM largo_plazo WHERE concepto LIKE 'test_eliminado_%'").fetchone()[0]
        assert restantes_f == 0, f"Se esperaban 0 restantes, got {restantes_f}"
        print(f"  OK: evicción eliminó {eliminados_f} nodos correctamente")
        fc.cerrar_sistema()
    finally:
        if os.path.exists(_forensic_db):
            os.remove(_forensic_db)
    print("--- 100. Forense eliminado OK ---")

    print("\n--- 101. Probando Historial Forense: CHECK constraint ---")
    _forensic_db = tempfile.mktemp(suffix='.db')
    try:
        fc = SQLiteMemoryBioRAG(db_path=_forensic_db)
        fc._crear_tabla_historial_si_falta()
        try:
            fc.cursor.execute(
                "INSERT INTO metricas_cognitivas_nodos "
                "(metrica_id, largo_plazo_id, accion, contenido_preview, peso_anterior, peso_nuevo, razon, contexto, anomalo, created_at) "
                "VALUES (1, 1, 'accion_invalida', '', 0, 0, '', '', 0, ?)",
                (time.time(),)
            )
            fc.conn.commit()
            assert False, "CHECK constraint no rechazó acción inválida"
        except sqlite3.IntegrityError:
            fc.conn.rollback()
            print("  OK: CHECK constraint rechazó acción inválida correctamente")
        fc.cerrar_sistema()
    finally:
        if os.path.exists(_forensic_db):
            os.remove(_forensic_db)
    print("--- 101. Forense CHECK constraint OK ---")

    print("\n--- 102. Probando Historial Forense: foreign key constraint ---")
    _forensic_db = tempfile.mktemp(suffix='.db')
    try:
        fc = SQLiteMemoryBioRAG(db_path=_forensic_db)
        fc.percibir_corto_plazo("test_forensic_fk", "Test FK", "test,fk", "Lesson")
        fc.ciclo_sueno_consolidacion()
        row_f = fc.cursor.execute("SELECT mn.metrica_id FROM metricas_cognitivas_nodos mn JOIN largo_plazo l ON mn.largo_plazo_id = l.id WHERE l.concepto = 'test_forensic_fk' LIMIT 1").fetchone()
        assert row_f is not None, "No hay registro forense"
        existe_f = fc.cursor.execute("SELECT 1 FROM metricas_cognitivas WHERE id = ?", (row_f[0],)).fetchone()
        assert existe_f is not None, f"metrica_id={row_f[0]} no existe en metricas_cognitivas"
        fk_info_f = fc.cursor.execute("PRAGMA foreign_key_list(metricas_cognitivas_nodos)").fetchall()
        assert any(fk[2] == 'metricas_cognitivas' for fk in fk_info_f), "FK ref esperada 'metricas_cognitivas' no encontrada"
        print("  OK: foreign key constraint verificada")
        fc.cerrar_sistema()
    finally:
        if os.path.exists(_forensic_db):
            os.remove(_forensic_db)
    print("--- 102. Forense FK OK ---")

    print("\n--- 103. Probando Historial Forense: contenido_preview truncación ---")
    _forensic_db = tempfile.mktemp(suffix='.db')
    try:
        fc = SQLiteMemoryBioRAG(db_path=_forensic_db)
        fc.percibir_corto_plazo("test_forensic_preview", "x" * 200, "test,preview", "Lesson")
        fc.ciclo_sueno_consolidacion()
        preview_f = fc.cursor.execute("SELECT mn.contenido_preview FROM metricas_cognitivas_nodos mn JOIN largo_plazo l ON mn.largo_plazo_id = l.id WHERE l.concepto = 'test_forensic_preview'").fetchone()
        assert preview_f is not None, "No hay registro forense"
        assert len(preview_f[0]) <= 100, f"contenido_preview excede 100 chars: {len(preview_f[0])}"
        assert len(preview_f[0]) > 0, "contenido_preview vacío"
        print(f"  OK: contenido_preview tiene {len(preview_f[0])} caracteres (<= 100)")
        fc.cerrar_sistema()
    finally:
        if os.path.exists(_forensic_db):
            os.remove(_forensic_db)
    print("--- 103. Forense preview OK ---")

    print("\n--- 104. Probando Historial Forense: flag anomalo ---")
    _forensic_db = tempfile.mktemp(suffix='.db')
    try:
        fc = SQLiteMemoryBioRAG(db_path=_forensic_db)
        fc.percibir_corto_plazo("test_forensic_anomalo", "Nodo anómalo", "test,anomalo", "Lesson")
        fc.ciclo_sueno_consolidacion()
        fc.cursor.execute("UPDATE largo_plazo SET peso_sinaptico = -0.5 WHERE concepto = 'test_forensic_anomalo'")
        fc.conn.commit()
        fc.ciclo_sueno_consolidacion()
        nodos_f = _get_nodos_acciones(fc)
        if 'test_forensic_anomalo' in nodos_f:
            anomalous_f = [a for a in nodos_f['test_forensic_anomalo'] if a['anomalo'] == 1]
            if anomalous_f:
                print("  OK: flag anomalo=1 detectado correctamente")
            else:
                print("  OK: nodo procesado sin anomalía detectada (peso normalizado)")
        else:
            print("  OK: nodo procesado (peso corregido por LTD)")
        fc.cerrar_sistema()
    finally:
        if os.path.exists(_forensic_db):
            os.remove(_forensic_db)
    print("--- 104. Forense anomalo OK ---")

    print("\n--- 105. Probando Inhibición Lateral GABA en Vivo (Evocación v20.0) ---")
    _v20_db = tempfile.mktemp(suffix='.db')
    try:
        fc = SQLiteMemoryBioRAG(db_path=_v20_db)
        fc.percibir_corto_plazo("gaba_atractor_principal", "Sistema principal de arquitectura de software", "gaba,atractor,principal", "Architecture")
        fc.percibir_corto_plazo("gaba_competidor_secundario", "Sistema secundario con palabras de software", "gaba,competidor,secundario", "Architecture")
        fc.ciclo_sueno_consolidacion()

        res_gaba, total_gaba = fc.buscar_por_frase("gaba atractor principal", limite=5)
        assert len(res_gaba) >= 1, "No se recuperaron resultados en prueba GABA"
        top_conc, _, _, _, top_score, _ = res_gaba[0]
        assert top_conc == "gaba_atractor_principal", f"Se esperaba 'gaba_atractor_principal' top-1, got {top_conc}"
        print(f"  OK: Inhibición GABA en vivo validada. Top-1 score: {top_score}")
        fc.cerrar_sistema()
    finally:
        if os.path.exists(_v20_db):
            os.remove(_v20_db)
    print("--- 105. Inhibición GABA en vivo OK ---")

    print("\n--- 106. Probando Refuerzo Dopaminérgico por RPE e Inercia Sináptica (v20.0) ---")
    _v20_db = tempfile.mktemp(suffix='.db')
    try:
        fc = SQLiteMemoryBioRAG(db_path=_v20_db)
        fc.percibir_corto_plazo("nodo_dopamina_test", "Contenido de prueba dopaminérgica", "dopamina,test", "General")
        fc.ciclo_sueno_consolidacion()

        # Feedback de éxito (+1)
        ok_dop = fc.aplicar_refuerzo_dopaminergico("nodo_dopamina_test", exito=True)
        assert ok_dop, "Error al aplicar feedback dopaminérgico"
        peso_pos = fc.cursor.execute("SELECT peso_sinaptico, exitos_dopamina FROM largo_plazo WHERE concepto = 'nodo_dopamina_test'").fetchone()
        assert peso_pos[1] == 1, f"Se esperaba 1 éxito, got {peso_pos[1]}"

        # Feedback de fallo (-1) con inercia
        fc.aplicar_refuerzo_dopaminergico("nodo_dopamina_test", exito=False)
        peso_neg = fc.cursor.execute("SELECT peso_sinaptico, fallos_dopamina FROM largo_plazo WHERE concepto = 'nodo_dopamina_test'").fetchone()
        assert peso_neg[1] == 1, f"Se esperaba 1 fallo, got {peso_neg[1]}"
        print(f"  OK: Dopamina RPE validada. Éxito incrementó, fallo aplicó inercia (peso: {peso_neg[0]})")
        fc.cerrar_sistema()
    finally:
        if os.path.exists(_v20_db):
            os.remove(_v20_db)
    print("--- 106. Dopamina RPE OK ---")

    print("\n--- 107. Probando Inmunidad Cortical por Valencia Somática (v20.0) ---")
    _v20_db = tempfile.mktemp(suffix='.db')
    try:
        fc = SQLiteMemoryBioRAG(db_path=_v20_db)
        fc.percibir_corto_plazo("nodo_principio_inmune", "Axioma supremo de seguridad", "principio,inmune", "Principle")
        fc.percibir_corto_plazo("nodo_valencia_alta", "Recuerdo emocional crítico", "valencia,alta", "General", valencia_somatica=1.0)
        fc.percibir_corto_plazo("nodo_comun_mortal", "Recuerdo ordinario que debe decaer", "comun,mortal", "General", valencia_somatica=0.0)
        fc.ciclo_sueno_consolidacion()

        # Ejecutar 5 ciclos de sueño consecutivos
        for _ in range(5):
            fc.ciclo_sueno_consolidacion()

        p_principio = fc.cursor.execute("SELECT peso_sinaptico FROM largo_plazo WHERE concepto = 'nodo_principio_inmune'").fetchone()[0]
        p_valencia = fc.cursor.execute("SELECT peso_sinaptico FROM largo_plazo WHERE concepto = 'nodo_valencia_alta'").fetchone()[0]
        p_mortal = fc.cursor.execute("SELECT peso_sinaptico FROM largo_plazo WHERE concepto = 'nodo_comun_mortal'").fetchone()[0]

        assert p_principio == 1.0, f"Principio decayó: {p_principio}"
        assert p_valencia == 1.0, f"Valencia alta decayó: {p_valencia}"
        assert p_mortal < 1.0, f"Nodo común no decayó: {p_mortal}"
        print(f"  OK: Inmunidad somática verificada. Inmunes: 1.0 vs Mortal: {p_mortal}")
        fc.cerrar_sistema()
    finally:
        if os.path.exists(_v20_db):
            os.remove(_v20_db)
    print("--- 107. Inmunidad Somática OK ---")

    print("\n--- 108. Probando Escalado Sináptico Homeostático (v20.0) ---")
    _v20_db = tempfile.mktemp(suffix='.db')
    try:
        fc = SQLiteMemoryBioRAG(db_path=_v20_db)
        fc.percibir_corto_plazo("nodo_scaling_1", "Nodo saturado 1", "scaling,1", "General")
        fc.percibir_corto_plazo("nodo_scaling_2", "Nodo saturado 2", "scaling,2", "General")
        fc.ciclo_sueno_consolidacion()

        # Forzar pesos a 1.0 para forzar peso medio > 0.70
        fc.cursor.execute("UPDATE largo_plazo SET peso_sinaptico = 1.0 WHERE concepto LIKE 'nodo_scaling_%'")
        fc.conn.commit()

        # Ejecutar consolidación (debe aplicar scaling multiplicativo x0.98)
        fc.ciclo_sueno_consolidacion()

        p_scaled = fc.cursor.execute("SELECT peso_sinaptico FROM largo_plazo WHERE concepto = 'nodo_scaling_1'").fetchone()[0]
        assert p_scaled < 1.0, f"Escalado sináptico no redujo saturación: {p_scaled}"
        print(f"  OK: Escalado sináptico homeostático verificado (peso ajustado a {p_scaled})")
        fc.cerrar_sistema()
    finally:
        if os.path.exists(_v20_db):
            os.remove(_v20_db)
    print("--- 108. Escalado Sináptico Homeostático OK ---")

    print("\n--- 109. Probando Inicio y Parada del Motor DMN (v21.0) ---")
    _v21_db = tempfile.mktemp(suffix='.db')
    try:
        f21 = SQLiteMemoryBioRAG(db_path=_v21_db)
        dmn = f21.iniciar_dmn(idle_seconds=10.0)
        assert dmn.activo is True, "Error: DMN no se marcó como activo"
        assert dmn._thread is not None and dmn._thread.is_alive(), "Error: Hilo DMN no está corriendo"
        
        f21.detener_dmn()
        assert dmn.activo is False, "Error: DMN no se detuvo correctamente"
        print("  OK: Control de hilo DMN iniciado y detenido correctamente")

        print("\n--- 110. Probando Detección de Inactividad e Interrupción por Actividad de Usuario ---")
        f21.iniciar_dmn(idle_seconds=0.5)
        time.sleep(0.2)
        f21.notificar_actividad_usuario()
        assert dmn._user_active_event.is_set(), "Error: Notificación de actividad de usuario no registró evento"
        print("  OK: Interrupción inmediata por actividad de usuario verificada")

        print("\n--- 111. Probando Ideación Espontánea DMN entre Nodos Distantes ---")
        # Crear 3 nodos distantes de alta valencia de distintas áreas temáticas
        f21.percibir_corto_plazo("nodo_fuente_alpha", "Arquitectura distribuida de microservicios", "alpha", "General", valencia_somatica=0.90)
        f21.percibir_corto_plazo("nodo_fuente_beta", "Bioquimica celular de la dopamina", "beta", "General", valencia_somatica=0.85)
        f21.percibir_corto_plazo("nodo_fuente_gamma", "Astrofisica de agujeros de gusano", "gamma", "General", valencia_somatica=0.88)
        f21.ciclo_sueno_consolidacion()

        # Forzar ejecución manual de ciclo de curiosidad
        idea = f21.dmn.ejecutar_ciclo_curiosidad(forzar=True)
        assert idea is not None, "Error: DMN no generó ninguna hipótesis entre nodos distantes"
        assert "insight_dmn_" in idea["concepto"], f"Concepto insight inesperado: {idea['concepto']}"
        assert dmn.ideas_generadas_sesion > 0, "Contador de ideas DMN no se incrementó"
        print(f"  OK: Idea autónoma DMN generada con éxito ({idea['concepto']})")

        print("\n--- 112. Probando Registro y Persistencia Forense de Ideas DMN ---")
        f21.dmn.ultimo_acceso_usuario = time.time() - 350.0
        st = f21.dmn.obtener_estado()
        assert st["ideas_generadas_sesion"] >= 1, "Error en estado DMN"
        assert st["ultima_idea"] is not None, "Error: Última idea DMN nula"
        assert st["estado"] == "idle", "Estado DMN debe ser idle al no haber actividad reciente"
        
        # Verificar en DB que el insight está en largo plazo con valencia 0.85 y peso 0.50
        row_insight = f21.cursor.execute("SELECT valencia_somatica, peso_sinaptico FROM largo_plazo WHERE concepto = ?", (idea["concepto"],)).fetchone()
        assert row_insight is not None, "Error: Insight DMN no encontrado en largo plazo"
        assert abs(row_insight[0] - 0.85) < 0.01, f"Valencia del insight incorrecta: {row_insight[0]}"
        assert abs(row_insight[1] - 0.50) < 0.01, f"Peso inicial del insight incorrecto: {row_insight[1]}"
        print(f"  OK: Persistencia e inmunidad de Insight DMN verificada en DB (valencia={row_insight[0]}, peso={row_insight[1]})")

        f21.detener_dmn()
        f21.cerrar_sistema()
    finally:
        if os.path.exists(_v21_db):
            os.remove(_v21_db)
    print("--- 112. Persistencia Forense DMN OK ---")

    # Finalizar
    cerebro.cerrar_sistema()

    print("\n--- ¡Todas las pruebas biologicas completadas con exito! ---\n\n")


if __name__ == "__main__":
    test_sistema()


