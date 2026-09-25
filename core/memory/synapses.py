"""
Módulo de operaciones de grafo sináptico de BioRAG.

Contiene las 8 funciones de topología y dinámica sináptica:
- establecer_asociacion: creación bidireccional manual de enlaces sinápticos
- aplicar_refuerzo_dopaminergico: RPE Hebbiano asintótico (LTP/LTD)
- _reconstruir_camino: reconstrucción de caminos sinápticos vía parent_map
- _evocacion_por_cadena: spreading activation con decay logarítmico y Fan Effect
- expandir_contexto_vecinos: expansión BFS con límite de retención
- _expandir_contexto_bfs: búsqueda BFS en la red sináptica con ordenamiento level-first
- obtener_asociaciones_enriquecidas: canal 2 de asociaciones sinápticas enriquecidas
- _multihop_vecinos: extracción determinista de vecinos a 1 salto

Nota de arquitectura: Este módulo excede 500 líneas (~523 líneas) deliberadamente para mantener la cohesión integral de los algoritmos de grafo sináptico, BFS topológico y plasticidad Hebbiana sin fragmentación artificial.
"""

import os
import math
import time
import logging
from core.memory import constants

logger = logging.getLogger("BioRAG.Memory.Synapses")


def aplicar_refuerzo_dopaminergico(self, concepto: str, exito: bool, motivo: str = None) -> bool:
    """
    Refuerzo Dopaminérgico por Error de Predicción de Recompensa (RPE v20.0 - Schultz 1997).
    Aplica el Factor de Inercia Sináptica (Dopaminergic Inertia):
    - Éxito: Delta W = +0.15 * (1.0 - peso_actual * 0.3) sobre el nodo
    - Éxito: LTP asintótico sobre aristas del camino exacto (si hay parent_map)
    - Fallo: Delta W = -0.10 / (1.0 + ln(1 + exitos_previos)) solo sobre nodo
    """
    key = concepto.lower().strip()
    self.cursor.execute(
        "SELECT peso_sinaptico, COALESCE(exitos_dopamina, 0), COALESCE(fallos_dopamina, 0) "
        "FROM largo_plazo WHERE concepto = ?", (key,)
    )
    row = self.cursor.fetchone()
    if not row:
        return False

    peso_actual, exitos, fallos = row[0] or 0.5, row[1], row[2]

    if exito:
        delta = 0.15 * (1.0 - peso_actual * 0.3)
        nuevo_peso = min(1.0, round(peso_actual + delta, 2))
        nuevos_exitos = exitos + 1
        self.cursor.execute("""
            UPDATE largo_plazo
            SET peso_sinaptico = ?, exitos_dopamina = ?, ultimo_acceso = ?, estado = 'activo'
            WHERE concepto = ?
        """, (nuevo_peso, nuevos_exitos, time.time(), key))

        # Feedback-Driven Graph Learning: fortalecer aristas del camino exacto
        if hasattr(self, 'last_parent_map') and self.last_parent_map:
            camino = self._reconstruir_camino(key)
            for nodo_a, nodo_b, peso_arista in camino:
                # LTP asintótico: peso += 0.05 * (1.0 - peso)
                nuevo_peso_arista = min(1.0, round(peso_arista + 0.05 * (1.0 - peso_arista), 3))
                self.cursor.execute("""
                    UPDATE sinapsis SET peso = ?, ultimo_uso = ?
                    WHERE (origen = ? AND destino = ?) OR (origen = ? AND destino = ?)
                """, (nuevo_peso_arista, time.time(), nodo_a, nodo_b, nodo_b, nodo_a))
    else:
        inercia = 1.0 + math.log(1.0 + exitos)
        delta = -0.10 / inercia
        nuevo_peso = max(0.05, round(peso_actual + delta, 2))
        nuevos_fallos = fallos + 1
        nuevo_estado = 'dormido' if nuevo_peso <= 0.05 else 'activo'
        self.cursor.execute("""
            UPDATE largo_plazo
            SET peso_sinaptico = ?, fallos_dopamina = ?, estado = ?
            WHERE concepto = ?
        """, (nuevo_peso, nuevos_fallos, nuevo_estado, key))

    # Registrar el evento de refuerzo en tabla propia (sin FK a ciclos).
    # POR QUÉ: el LTP dopaminérgico era la única regla de actualización de peso
    # sin rastro persistente (P3, 2026-08-15), lo que la hacía imposible de
    # validar contra la teoría. El try/except es deliberado: perder una fila
    # de telemetría es aceptable; romper el bucle de feedback no.
    try:
        delta = round(nuevo_peso - peso_actual, 4)
        self.cursor.execute("""
            INSERT INTO eventos_refuerzo
            (concepto, exito, peso_anterior, peso_nuevo, delta, exitos_previos, motivo, created_at)
            VALUES (?,?,?,?,?,?,?,?)""",
            (key, 1 if exito else 0, peso_actual, nuevo_peso,
             delta, exitos, motivo, time.time())
        )
    except Exception as e:
        print(f"[BioRAG] aviso: no se pudo registrar evento_refuerzo para '{key}': {e}")

    # Propagar feedback a log_busquedas.util atribuyéndolo a la búsqueda
    # más reciente que devolvió este concepto (ver docs/FIX_FEEDBACK_NO_ALCANZABLE.md).
    # Usamos conceptos_top (CSV) en lugar de last_log_id (estado en memoria),
    # porque el MCP crea una instancia nueva por llamada y last_log_id no
    # sobrevive entre herramientas. El WHERE utiliza LIKE con delimitadores
    # para coincidencia exacta del concepto en la lista CSV.
    try:
        self.cursor.execute(
            "UPDATE log_busquedas SET util = ? "
            "WHERE id = (SELECT id FROM log_busquedas "
            "            WHERE util IS NULL "
            "              AND (',' || conceptos_top || ',') LIKE ? "
            "            ORDER BY creado_en DESC LIMIT 1)",
            (1 if exito else 0, f"%,{key},%"),
        )
        if self.cursor.rowcount == 0:
            print(f"[BioRAG] aviso: feedback sobre '{key}' sin búsqueda asociada "
                  f"pendiente; no se propagó a log_busquedas.")
    except Exception as e:
        print(f"[BioRAG] aviso: no se pudo propagar feedback a log_busquedas: {e}")

    self.conn.commit()
    return True


def _reconstruir_camino(self, destino):
    """Reconstruye el camino exacto desde la semilla hasta el destino usando parent_map.
    Retorna lista de (nodo_a, nodo_b, peso_arista) para cada arista del camino."""
    if not hasattr(self, 'last_parent_map') or not self.last_parent_map:
        return []

    camino = []
    actual = destino.lower().strip()
    visitados = set()

    while actual in self.last_parent_map and actual not in visitados:
        visitados.add(actual)
        padre, peso_arista = self.last_parent_map[actual]
        camino.append((padre, actual, peso_arista))
        actual = padre

    camino.reverse()  # Desde la semilla hasta el destino
    return camino


def establecer_asociacion(self, concepto_a, concepto_b):
    """Crea un enlace sináptico bidireccional entre dos conceptos en el grafo de largo plazo."""
    concepto_a, concepto_b = concepto_a.lower().strip(), concepto_b.lower().strip()
    inserto = False
    for a, b in [(concepto_a, concepto_b), (concepto_b, concepto_a)]:
        self.cursor.execute("SELECT 1 FROM sinapsis WHERE origen = ? AND destino = ?", (a, b))
        if not self.cursor.fetchone():
            self.cursor.execute(
                "INSERT INTO sinapsis (origen, destino, peso, tipo, creado_en) VALUES (?, ?, 0.5, 'manual', ?)",
                (a, b, time.time())
            )
            inserto = True
    from core.sinapsis import _sincronizar_asociaciones
    _sincronizar_asociaciones(self, concepto_a)
    _sincronizar_asociaciones(self, concepto_b)
    self.conn.commit()
    if inserto:
        try:
            from core.sdm import marcar_sdm_dirty
            marcar_sdm_dirty(self, (concepto_a, concepto_b))
        except Exception:
            pass
    print(f"[MemoryBioRAG] Sinapsis establecida: '{concepto_a}' <--> '{concepto_b}'")


def _evocacion_por_cadena(self, semillas, max_saltos=None, limite=None):
    """Evocación por cadena: spreading activation multi-hop con decay logarítmico.
    
    Sigue aristas de sinapsis en cadena. Cada salto reduce el score
    con decay logarítmico: 1/(2^salto). Más fiel al proceso cognitivo
    humano donde el tercer salto es mucho más débil que el segundo.
    
    Retorna: (resultados, parent_map)
      - resultados: lista de (nodo, score, salto)
      - parent_map: dict {nodo: (nodo_padre, peso_arista)} para rastrear caminos
    """
    if max_saltos is None:
        max_saltos = constants.MAX_SALTOS_CADENA
    if limite is None:
        limite = constants.LIMITE_EVOCACION
    visitados = set()
    resultados = []
    parent_map = {}  # {nodo: (nodo_padre, peso_arista)}
    actuales = [(n, 1.0) for n in semillas]

    for salto in range(max_saltos):
        decay = 1.0 / (2 ** salto)
        siguientes = []

        for nodo, score in actuales:
            if nodo in visitados:
                continue
            visitados.add(nodo)

            # Fan Effect (ACT-R): atenuación conservativa por grado de dispersión del nodo emisor
            self.cursor.execute(
                "SELECT COUNT(*) FROM ("
                "SELECT destino FROM sinapsis WHERE origen = ? "
                "UNION "
                "SELECT origen FROM sinapsis WHERE destino = ?"
                ")",
                (nodo, nodo)
            )
            fan_grado = self.cursor.fetchone()[0] or 1
            fan_factor = 1.0 / math.log(math.e + max(0, fan_grado - 1))

            self.cursor.execute(
                "SELECT destino, peso FROM sinapsis WHERE origen = ? "
                "UNION "
                "SELECT origen, peso FROM sinapsis WHERE destino = ? "
                "ORDER BY peso DESC LIMIT 10",
                (nodo, nodo)
            )
            for vecino, peso in self.cursor.fetchall():
                if vecino not in visitados:
                    sv = score * (peso or 0.5) * fan_factor * decay
                    if sv > 0.05:
                        siguientes.append((vecino, sv))
                        resultados.append((vecino, sv, salto + 1))
                        # Track parent for path reconstruction
                        if vecino not in parent_map:
                            parent_map[vecino] = (nodo, peso or 0.5)

        actuales = siguientes

    resultados.sort(key=lambda x: x[1], reverse=True)
    return resultados[:limite], parent_map


def expandir_contexto_vecinos(self, pagina_resultados, depth, profundidad="activos", preview_chars=None):
    """Expande el contexto de una página devolviendo (primarios, contextos).
    Usa BFS. Capa los contextos con un corte configurable que escala con depth:
    BIORAG_MAX_CONTEXTOS * max(1, depth).
    
    Configuración de Freno / Retención:
      - Histórico: max_contextos = 15 * depth
      - Actual: max_contextos = int(os.environ.get("BIORAG_MAX_CONTEXTOS", "50")) * max(1, depth)
      - Si BIORAG_MAX_CONTEXTOS <= 0, no se aplica corte (pool BFS completo sin truncar).
    """
    if not depth or depth <= 0 or not pagina_resultados:
        return pagina_resultados, []

    primarios, contextos = self._expandir_contexto_bfs(pagina_resultados, depth, profundidad=profundidad, preview_chars=preview_chars)
    
    # ── Control de Retención de Contextos ─────────────────────────────────
    # HISTÓRICO: max_contextos = 15 * max(1, int(depth or 1))
    # Para restaurar el comportamiento original estricto, definir BIORAG_MAX_CONTEXTOS=15
    cap_base = int(os.environ.get("BIORAG_MAX_CONTEXTOS", "50"))
    if cap_base > 0:
        max_contextos = cap_base * max(1, int(depth or 1))
        return primarios, contextos[:max_contextos]
    
    # Si cap_base <= 0, entrega el conjunto completo sin límite de retención
    return primarios, contextos


def _expandir_contexto_bfs(self, pagina_resultados, depth, profundidad="activos", preview_chars=None):
    """Búsqueda BFS real en la red sináptica hasta una profundidad 'depth'.
    Atenúa recursivamente los scores de los vecinos encontrados.
    Deduplica nodos de forma estricta.

    Freno de seguridad y delimitación de profundidad:
      - HISTÓRICO (Hardcap rígido):
          depth = min(int(depth), 3)
        Este freno evitaba recorridos profundos en grafos grandes.
      - ACTUAL (Configurable con guardia):
          max_bfs_depth = int(os.environ.get("BIORAG_MAX_BFS_DEPTH", "5"))
          depth = min(int(depth), max_bfs_depth) if max_bfs_depth > 0 else int(depth)
        Permite explorar saltos mayores (ej. depth=4 o 5) si se solicita, manteniendo
        un tope de seguridad por defecto para prevenir bucles o explosión combinatoria.
        Para desactivar el techo completamente: BIORAG_MAX_BFS_DEPTH=0.

    Ordenamiento level-first (EXP-Q-R3, 2026-09-09):
      Ordena los contextos por (nivel_descubierto ASC, score DESC) en vez de
      solo score DESC. Principio: un nodo más cercano en el grafo siempre
      gana a uno más lejano, independientemente del peso de una arista puntual.
      La regla de orden es agnóstica al cap — no introduce hiperparámetros.
      Resultado en EXP-Q-R3: 0 violaciones monotónicas, 0 FP, mismas generaciones.
      Referencia: scripts/experimentos/expQ_r3_level_first_ordering.py
    """
    if not depth or depth <= 0 or not pagina_resultados:
        return pagina_resultados, []

    # ── Freno de Seguridad de Profundidad (Configurable y Reversible) ─────
    # HISTÓRICO: depth = min(int(depth), 3)
    # Para reactivar el límite rígido histórico de 3 saltos, exportar BIORAG_MAX_BFS_DEPTH=3
    max_bfs_depth = int(os.environ.get("BIORAG_MAX_BFS_DEPTH", "5"))
    if max_bfs_depth > 0:
        depth = min(int(depth), max_bfs_depth)
    else:
        depth = int(depth)

    vistos = {}  # concepto -> item
    for r in pagina_resultados:
        vistos[r[0]] = r

    frontera = list(pagina_resultados)
    # Cada entrada guarda (item, nivel_descubierto) para el ordenamiento level-first
    contextos_con_nivel = []
    filtro_estado = " AND l.estado = 'activo'" if profundidad != "profundo" else ""
    hubo_despertar = False

    for nivel in range(1, depth + 1):
        siguiente_frontera = []
        for r in frontera:
            concepto = r[0]
            score_actual = r[4]
            
            # Recuperar vecinos directos de la base de datos (anti-trampa alfabética de SQLite)
            self.cursor.execute(f"""
                SELECT l.concepto, l.contenido, l.peso_sinaptico, l.estado, l.asociaciones, s.peso
                FROM (
                    SELECT destino as vecino, peso, rowid FROM sinapsis WHERE origen = ?
                    UNION ALL
                    SELECT origen as vecino, peso, rowid FROM sinapsis WHERE destino = ?
                ) s
                JOIN largo_plazo l ON l.concepto = s.vecino
                WHERE 1=1{filtro_estado}
                ORDER BY s.peso DESC, s.rowid DESC
            """, (concepto, concepto))
            
            agregados = 0
            max_vecinos_nodo = int(os.environ.get("BIORAG_MAX_VECINOS_POR_NODO", "6"))
            vecinos_padre_vistos = set()
            for row in self.cursor.fetchall():
                if agregados >= max_vecinos_nodo:
                    break
                vecino_concepto = row[0]
                if vecino_concepto in vecinos_padre_vistos:
                    continue
                vecinos_padre_vistos.add(vecino_concepto)
                
                # Despertar bajo demanda (wake-on-access con refuerzo LTP) si la búsqueda es profunda:
                # Cuando la búsqueda solicita profundidad="profundo", los nodos en estado 'dormido'
                # alcanzados por resonancia sináptica son reactivados, reciben incremento LTP (+0.15)
                # y se actualiza su marca temporal de acceso, respetando la intención de búsqueda.
                if profundidad == "profundo" and row[3] == "dormido":
                    nuevo_peso = min(1.0, (row[2] or 0.5) + 0.15)
                    self.cursor.execute(
                        "UPDATE largo_plazo SET estado = 'activo', peso_sinaptico = ?, ultimo_acceso = ? WHERE concepto = ?",
                        (nuevo_peso, time.time(), vecino_concepto),
                    )
                    vecino_peso = nuevo_peso
                    vecino_estado = "activo"
                    hubo_despertar = True
                else:
                    vecino_peso = row[2]
                    vecino_estado = row[3]

                # Atenuación del score híbrido según la distancia
                score_contexto = round(min(1.0, score_actual * 0.6 + min(row[5], 1.0) * 0.2), 4)

                if vecino_concepto in vistos:
                    # Refuerzo Hebbiano multi-padre: si múltiples caminos convergen en este nodo, reforzar su score
                    old_item = vistos[vecino_concepto]
                    if isinstance(old_item, (tuple, list)) and len(old_item) >= 5:
                        boost_multi = round(min(0.08, score_contexto * 0.15), 4)
                        nuevo_score = round(min(1.0, old_item[4] + boost_multi), 4)
                        list_item = list(old_item)
                        list_item[4] = nuevo_score
                        # Si despertó en esta pasada, reflejar estado activo y peso actualizado
                        if profundidad == "profundo" and list_item[3] == "dormido":
                            list_item[2] = vecino_peso
                            list_item[3] = "activo"
                        updated_item = tuple(list_item)
                        vistos[vecino_concepto] = updated_item
                        for idx_ctx, (ci, niv) in enumerate(contextos_con_nivel):
                            if ci[0] == vecino_concepto:
                                contextos_con_nivel[idx_ctx] = (updated_item, niv)
                                break
                    continue
                
                # Limitar caracteres del contenido de los vecinos si preview_chars está definido
                vecino_contenido = row[1] or ""
                if preview_chars and preview_chars > 0:
                    if len(vecino_contenido) > preview_chars:
                        vecino_contenido = vecino_contenido[:preview_chars] + "..."
                        
                new_item = (vecino_concepto, vecino_contenido, vecino_peso, vecino_estado, score_contexto, row[4] or "")
                contextos_con_nivel.append((new_item, nivel))  # guarda nivel para level-first sort
                vistos[vecino_concepto] = new_item
                siguiente_frontera.append(new_item)
                agregados += 1
                
        frontera = siguiente_frontera
        if not frontera:
            break

    if hubo_despertar:
        self.conn.commit()

    # Level-first ordering: nodos más cercanos al grafo de primarios siempre
    # tienen prioridad sobre nodos más lejanos. Dentro del mismo nivel, el
    # score decide. Esto garantiza que un nodo de nivel-2 nunca sea desplazado
    # por uno de nivel-3, independientemente del peso de sus aristas.
    contextos_con_nivel.sort(key=lambda x: (x[1], -x[0][4]))
    contextos = [item for item, _nivel in contextos_con_nivel]

    # Propagar refuerzo Hebbiano multi-padre a los primarios (Fix P1 / Auditoría 2026-09-09):
    # Nodos primarios que recibieron convergencia Hebbiana son actualizados con su
    # nuevo score desde 'vistos' y reordenados para mantener monotonía estricta.
    primarios_actualizados = [vistos.get(r[0], r) for r in pagina_resultados]
    primarios_actualizados.sort(key=lambda r: r[4], reverse=True)
    return primarios_actualizados, contextos


def obtener_asociaciones_enriquecidas(self, conceptos_top, top_vecinos=5, peso_min=0.50):
    """Canal 2 — Asociaciones enriquecidas desde el grafo sináptico real.

    POR QUÉ existe: el canal 1 (ranking top-5 por score_hibrido) es un juego de
    suma cero y NO debe mezclarse con el halo asociativo (lección del 13/08:
    la comunidad no sirve para re-rankear, sí para asociar). Este método entrega
    los vecinos de la tabla `sinapsis` con su fuerza real, ordenados por prioridad
    de tipo y fuerza de arista, para exponerlos como campo aparte.

    Filtros anti-ruido (basados en el diagnóstico del grafo, 2026-08-14):
    - peso >= peso_min (default 0.50): la mediana real de pesos es 0.72, así que
      0.50 corta aristas débiles sin perder el núcleo fuerte.
    - Tipos prioritarios: pmi_hebbiano, co_semantica, manual, latente_confirmada.
    - sinonimo_explicito: hiperdenso (6,494 aristas) — se limita a 2 por nodo
      para no inundar el canal de asociaciones con ruido redundante.
    - Excluye vecinos dormidos y nodos inexistentes en largo_plazo.

    Complejidad: 1 query SQL con IN clause + filtrado/orden en memoria.

    Retorna dict {concepto_raiz: [ {concepto, fuerza_arista, tipo_sinapsis, peso_vecino}, ... ]}
    """
    if not conceptos_top:
        return {}
    conceptos_top = [c for c in conceptos_top if c]
    if not conceptos_top:
        return {}

    placeholders = ",".join("?" * len(conceptos_top))
    # Prioridad de tipo para el orden final (más semántico primero).
    # Tipos EXPLÍCITOS (manual, sinonimo, co_semantica) PRIMERO — son señal semántica real.
    # pmi_hebbiano va al final: es estadístico, hiperdenso (7k aristas) y ruidoso (hubs genéricos).
    prioridad_tipo = {
        "manual": 0,
        "sinonimo_explicito": 1,
        "co_semantica": 2,
        "latente_confirmada": 3,
        "co_ocurrencia": 4,
        "co_nombre": 5,
        "legacy_csv": 6,
        "manual_v7": 7,
        "test": 8,
        "pmi_hebbiano": 9,
    }
    MAX_SINONIMO_EXPLICITO = 2

    try:
        # El LEFT JOIN resuelve el vecino: si el origen está en el top, el vecino
        # es el destino; si no (caso donde solo el destino está en el top), el origen.
        # El filtro l.estado='activo' elimina aristas hacia nodos dormidos/inexistentes.
        # ORDER BY: prioridad de tipo (explícitos primero) + peso DESC.
        # CASE mapea tipo -> prioridad numérica (menor = mejor).
        self.cursor.execute(
            f"""
            SELECT s.origen, s.destino, s.peso, s.tipo,
                   l.peso_sinaptico AS peso_vecino,
                   substr(l.contenido, 1, 120) AS resumen_vecino,
                   CASE s.tipo
                       WHEN 'manual' THEN 0
                       WHEN 'sinonimo_explicito' THEN 1
                       WHEN 'co_semantica' THEN 2
                       WHEN 'latente_confirmada' THEN 3
                       WHEN 'co_ocurrencia' THEN 4
                       WHEN 'co_nombre' THEN 5
                       WHEN 'legacy_csv' THEN 6
                       WHEN 'manual_v7' THEN 7
                       WHEN 'test' THEN 8
                       ELSE 9
                   END AS prioridad_tipo
            FROM sinapsis s
            LEFT JOIN largo_plazo l ON l.concepto = CASE
                WHEN s.origen IN ({placeholders}) THEN s.destino
                ELSE s.origen
            END
            WHERE (s.origen IN ({placeholders}) OR s.destino IN ({placeholders}))
              AND s.peso >= ?
              AND l.estado = 'activo'
            ORDER BY prioridad_tipo ASC, s.peso DESC
            """,
            list(conceptos_top) * 3 + [peso_min],
        )
        filas = self.cursor.fetchall()
    except Exception as exc:
        logger.warning("obtener_asociaciones_enriquecidas falló: %s", exc)
        return {}

    asoc_map = {c: [] for c in conceptos_top}
    # Deduplicación por (raíz, vecino): el grafo guarda aristas simétricas como
    # dos filas independientes (A->B y B->A). Como la query ya viene ordenada
    # por prioridad de tipo + peso, el primer borde que llega por cada (raiz,vecino)
    # es el MEJOR (tipo explícito > pmi_hebbiano; y dentro del mismo tipo, mayor peso).
    vistos_por_raiz = {c: set() for c in conceptos_top}
    for origen, destino, peso, tipo, peso_vecino, resumen_vecino, p_tipo_col in filas:
        raiz = origen if origen in asoc_map else destino
        vecino = destino if raiz == origen else origen
        if vecino == raiz:
            continue
        if vecino in vistos_por_raiz[raiz]:
            continue
        vistos_por_raiz[raiz].add(vecino)
        asoc_map[raiz].append({
            "concepto": vecino,
            "fuerza_arista": round(float(peso or 0.5), 3),
            "tipo_sinapsis": tipo,
            "peso_vecino": round(float(peso_vecino or 0.5), 2),
            "resumen": resumen_vecino or "",
        })

    resultado = {}
    for raiz, aristas in asoc_map.items():
        aristas.sort(key=lambda a: (prioridad_tipo.get(a["tipo_sinapsis"], 50), -a["fuerza_arista"]))
        sinonimo_cont = 0
        filtradas = []
        for a in aristas:
            if a["tipo_sinapsis"] == "sinonimo_explicito":
                if sinonimo_cont >= MAX_SINONIMO_EXPLICITO:
                    continue
                sinonimo_cont += 1
            filtradas.append(a)
            if len(filtradas) >= top_vecinos:
                break
        resultado[raiz] = filtradas
    return resultado


def _multihop_vecinos(self, semillas, excluir, limite):
    """Vecinos 1-salto ordenados (peso DESC, concepto ASC). Solo lectura.

    Determinista per DB bytes. Nunca lanza (devuelve []).
    """
    try:
        semillas = [s for s in dict.fromkeys(semillas or []) if s]
        if not semillas or limite <= 0:
            return []
        ph = ",".join("?" * len(semillas))
        rows = self.cursor.execute(
            "SELECT destino, peso FROM sinapsis WHERE origen IN (%s)"
            " UNION SELECT origen, peso FROM sinapsis WHERE destino IN (%s)"
            " ORDER BY 2 DESC, 1 ASC" % (ph, ph),
            tuple(semillas) * 2,
        ).fetchall()
        out, vistos = [], set(excluir or ())
        for concepto, peso in rows:
            if concepto in vistos:
                continue
            vistos.add(concepto)
            try:
                _p = float(peso or 0.0)
            except Exception:
                _p = 0.0
            out.append((concepto, _p))
            if len(out) >= limite:
                break
        return out
    except Exception as e:
        logger.warning("multihop: vecinos fallo (%s: %s)", type(e).__name__, e)
        return []
