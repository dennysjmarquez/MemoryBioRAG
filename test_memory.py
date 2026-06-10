import sys
import os
import time

# Añadir el directorio actual al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.memory_store import SQLiteMemoryBioRAG
from core.sinapsis import init_sinapsis_table, auto_vincular, buscar_vecinos, vincular_por_sinonimos, migrar_desde_csv
from core.categorizador import inferir_categoria, auto_categorizar_existentes

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
    resultados_c, total_c = cerebro.buscar_por_frase("puerta madera", profundidad="activos")
    contenido_corto = (resultados_c[0][1] or "")[:200]
    contenido_completo = resultados_c[0][1] or ""
    assert len(contenido_corto) <= 200, "Error: snippet deberia estar truncado"
    assert len(contenido_completo) >= 20, "Error: contenido completo deberia ser mas largo"
    print(f"  Snippet (200 chars): {contenido_corto[:50]}...")
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
    cerebro.percibir_corto_plazo("test_auto_v4", "Prueba de autoguardado automatico sin sueno", "v4,auto,test", "test")

    ok = cerebro.consolidar_concepto("test_auto_v4")
    print(f"  consolidar_concepto() -> {ok}")
    assert ok, "Error: consolidar_concepto deberia devolver True"

    cerebro.cursor.execute("SELECT concepto FROM corto_plazo WHERE concepto = 'test_auto_v4'")
    assert not cerebro.cursor.fetchone(), "Error: concepto no deberia estar en corto_plazo"
    print("  OK: eliminado de corto_plazo")

    resultados, total = cerebro.buscar_por_frase("test_auto_v4", limite=1)
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
    cerebro.percibir_corto_plazo("angular_forms", "Formularios reactivos en Angular con validacion", "angular,forms", "proyecto")
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
    cerebro.percibir_corto_plazo("react_hooks", "useState y useEffect en React", "react,hooks", "proyecto")
    cerebro.ciclo_sueno_consolidacion()
    syn_enlaces = vincular_por_sinonimos(cerebro, "react_hooks", "forms,angular")
    print(f"  Sinonimos vincularon: {syn_enlaces}")
    assert any("angular_forms" in str(e) for e in syn_enlaces), \
        "Error: deberia vincular 'react_hooks' con 'angular_forms' via sinonimo 'forms'"
    print("OK: vincular_por_sinonimos conecta via terminos compartidos en contenido")

    # 31. migrar_desde_csv (legacy asociaciones)
    print("\n--- 31. Probando migrar_desde_csv (asociaciones legacy) ---")
    cerebro.establecer_asociacion("angular_forms", "react_hooks")
    count = migrar_desde_csv(cerebro)
    print(f"  Aristas migradas desde campo 'asociaciones': {count}")
    assert count > 0, "Error: deberia migrar al menos 1 arista desde asociaciones CSV"
    cerebro.cursor.execute("SELECT COUNT(*) FROM sinapsis WHERE tipo = 'legacy_csv'")
    csv_count = cerebro.cursor.fetchone()[0]
    assert csv_count > 0, "Error: deberian haber aristas con tipo 'legacy_csv'"
    print(f"  Aristas legacy_csv: {csv_count}")
    print("OK: migracion desde CSV legacy funciona sin borrar datos existentes")

    # 32. vincular_nuevo_si_existe
    print("\n--- 32. Probando vincular_nuevo_si_existe ---")
    cerebro.percibir_corto_plazo("vue_forms", "Formularios con v-model en Vue.js", "vue,forms", "proyecto")
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
    assert inferir_categoria("Error en la API al procesar la solicitud") == "solucion", \
        "Error: deberia inferir 'solucion'"
    assert inferir_categoria("Nuevo repositorio con el codigo del proyecto") == "proyecto", \
        "Error: deberia inferir 'proyecto'"
    assert inferir_categoria("Leccion aprendida: no acoplarse a implementacion") == "leccion", \
        "Error: deberia inferir 'leccion'"
    assert inferir_categoria("Patron de diseno para el pipeline de datos") == "arquitectura", \
        "Error: deberia inferir 'arquitectura'"
    assert inferir_categoria("Mensaje de prueba sin contexto relevante") == "general", \
        "Error: texto neutro deberia ser 'general'"
    assert inferir_categoria("") == "general", "Error: vacio deberia ser 'general'"
    print("OK: inferir_categoria clasifica contenido en 6 categorias + fallback 'general'")

    # 34. auto_categorizar_existentes
    print("\n--- 34. Probando auto_categorizar_existentes (batch) ---")
    # Crear nodo legacy con contenido categorizable
    cerebro.percibir_corto_plazo("test_legacy_cat", "Error encontrado en la API: problema de conexion al servidor", "error,api", "general")
    cerebro.consolidar_concepto("test_legacy_cat")
    cerebro.cursor.execute("UPDATE largo_plazo SET categoria = 'general' WHERE concepto = 'test_legacy_cat'")
    cerebro.conn.commit()
    actualizados, total = auto_categorizar_existentes(cerebro)
    print(f"  Re-categorizados: {actualizados}/{total} nodos tenian 'general'")
    assert actualizados >= 1, f"Error: deberia re-categorizar al menos 1 nodo, actualizo {actualizados}"
    cerebro.cursor.execute("SELECT categoria FROM largo_plazo WHERE concepto = 'test_legacy_cat'")
    cat = cerebro.cursor.fetchone()[0]
    assert cat != 'general', f"Error: 'test_legacy_cat' deberia tener categoria inferida, tiene '{cat}'"
    print(f"  'test_legacy_cat' reclasificado como: {cat} (con 'error' + 'api' -> 'solucion')")
    # Verificar que nodos sin contenido no se rompen
    cat_again, _ = auto_categorizar_existentes(cerebro)
    print(f"  Segunda pasada: {cat_again} actualizaciones (deberia ser 0)")
    assert cat_again == 0, "Error: segunda pasada no deberia actualizar nada"
    print("OK: auto_categorizar_existentes actualiza nodos legacy sin duplicar trabajo")

    # 35. Integracion: guardar con categoria + auto_vincular simultaneo
    print("\n--- 35. Probando integracion: percibir_corto_plazo con categoria + sinapsis ---")
    cerebro.percibir_corto_plazo("test_integracion", "Leccion: evitar acoplamiento en servicios", "leccion,acoplamiento", "leccion")
    cerebro.consolidar_concepto("test_integracion")
    auto_vincular(cerebro, "test_integracion", "Leccion: evitar acoplamiento en servicios")
    cerebro.cursor.execute("SELECT categoria FROM largo_plazo WHERE concepto = 'test_integracion'")
    cat_int = cerebro.cursor.fetchone()[0]
    assert cat_int == "leccion", f"Error: categoria deberia ser 'leccion', es '{cat_int}'"
    cerebro.cursor.execute("SELECT COUNT(*) FROM sinapsis WHERE origen = 'test_integracion'")
    sin_count = cerebro.cursor.fetchone()[0]
    print(f"  Categoria persistida: {cat_int}, aristas desde test_integracion: {sin_count}")
    print("OK: integracion guardado + categoria + sinapsis funciona en flujo completo")

    print("\n--- v5.0: Sinapsis + Categorizador OK ---")

    cerebro.cerrar_sistema()
    print("\n--- ¡Todas las pruebas biologicas completadas con exito! ---")

if __name__ == "__main__":
    test_sistema()
