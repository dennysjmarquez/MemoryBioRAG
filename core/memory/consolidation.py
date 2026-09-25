"""core/memory/consolidation.py - Módulo de consolidación de memoria y ciclo de sueño.

Este módulo concentra las rutinas de consolidación cortical, decaimiento LTD,
clasificación WordNet y cálculo ACT-R. La función `ciclo_sueno_consolidacion`
se mantiene monolítica intacta por deuda técnica documentada en Spec 003 / RNF-1.3.

Extraído de SQLiteMemoryBioRAG siguiendo el patrón A1:
- Funciones con `self` como primer parámetro.
- Cuerpos intactos con imports internos preservados.
"""

import math
import os
import sqlite3
import time

from core.memory import constants


def _calcular_base_level_actr(self, concepto: str, ahora: float = None):
    r"""Calcula la activación de nivel base de la arquitectura cognitiva ACT-R:
    
    Ecuación:
        B_i = ln( \sum_{k=1}^n t_k^{-d} ), con parámetro canónico d = 0.5
        donde t_k es el tiempo transcurrido (en segundos) desde el k-ésimo acceso.
        
    Retorna:
        float con el nivel de activación B_i, o None si el concepto no posee
        registros de acceso previos en el historial.
    """
    if ahora is None:
        ahora = time.time()
    try:
        self.cursor.execute(
            "SELECT acceso_timestamp FROM nodo_accesos_historial WHERE concepto = ? ORDER BY acceso_timestamp DESC LIMIT 10",
            (concepto,)
        )
        rows = self.cursor.fetchall()
        if rows:
            suma_potencias = sum(max(1.0, ahora - r[0]) ** (-0.5) for r in rows)
            return math.log(max(1e-9, suma_potencias))
    except Exception:
        pass
    return None


def _auto_generar_co_ocurrencia(self, recuerdos_sesion):
    """Fase 2: Auto-generar sinapsis por co-ocurrencia.
    
    Analiza dos fuentes:
    1. corto_plazo: conceptos consolidados en la misma sesión co-ocurren
    2. comunicaciones: conceptos que aparecen en el mismo mensaje co-ocurren
    
    Crea sinapsis con tipo='co_ocurrencia' y peso basado en frecuencia.
    """
    import re
    from itertools import combinations
    
    # Reindex SDM selectivo: extremos de sinapsis NUEVAS creadas aquí
    dirty = set()
    
    # Mapa de concepto → tokens de contenido (para matching)
    concepto_tokens = {}
    
    # 1. Co-ocurrencia en corto_plazo (conceptos de la misma sesión)
    if len(recuerdos_sesion) >= 2:
        for item in recuerdos_sesion:
            c1, contenido1 = item[0], item[1]
            if c1 not in concepto_tokens:
                concepto_tokens[c1] = set(re.findall(r'\w{4,}', (contenido1 or "").lower()))
        
        # Para cada par de conceptos consolidados juntos
        for item1, item2 in combinations(recuerdos_sesion, 2):
            c1, cont1 = item1[0], item1[1]
            c2, cont2 = item2[0], item2[1]
            tokens1 = concepto_tokens.get(c1, set())
            tokens2 = concepto_tokens.get(c2, set())
            
            # Si comparten al menos 2 tokens significativos, co-ocurren
            shared = tokens1 & tokens2
            if len(shared) >= 2:
                # v26.2: Cierre Triádico en co-ocurrencia — exige vecinos/dimensiones comunes o bootstrap (<=5 sinapsis)
                try:
                    from core.sinapsis import _vecinos_comunes, _dimensiones_comunes, _CIERRE_TRIADICO
                    if _CIERRE_TRIADICO:
                        vec_com = _vecinos_comunes(self.cursor, c1, c2)
                        dim_com = _dimensiones_comunes(self.cursor, c1, c2) if vec_com == 0 else 1
                        self.cursor.execute("SELECT COUNT(*) FROM sinapsis WHERE origen = ? OR destino = ?", (c1, c1))
                        sinap_exist = self.cursor.fetchone()[0]
                        if vec_com == 0 and dim_com == 0 and sinap_exist > 5:
                            continue  # Rechazar: coincidencia tokenizada entre dominios aislados
                except Exception:
                    pass

                peso = min(0.9, 0.3 + len(shared) * 0.1)
                self.cursor.execute(
                    "SELECT 1 FROM sinapsis WHERE origen = ? AND destino = ?",
                    (c1, c2)
                )
                es_nueva = self.cursor.fetchone() is None
                self.cursor.execute(
                    "INSERT INTO sinapsis (origen, destino, peso, tipo, creado_en) "
                    "VALUES (?, ?, ?, 'co_ocurrencia', ?) "
                    "ON CONFLICT(origen, destino) DO UPDATE SET "
                    "peso = MIN(0.9, peso + 0.1), ultimo_uso = ?",
                    (c1, c2, peso, time.time(), time.time())
                )
                if es_nueva:
                    dirty.add(c1)
                    dirty.add(c2)
    
    # 2. Co-ocurrencia en comunicaciones (conceptos en el mismo mensaje)
    try:
        self.cursor.execute(
            "SELECT contenido FROM comunicaciones ORDER BY timestamp DESC LIMIT 50"
        )
        mensajes = self.cursor.fetchall()
        
        if mensajes and len(recuerdos_sesion) >= 1:
            # Tokenizar todos los conceptos activos
            self.cursor.execute(
                "SELECT concepto, contenido FROM largo_plazo WHERE estado = 'activo' LIMIT 200"
            )
            nodos_activos = self.cursor.fetchall()
            nodo_tokens = {c: set(re.findall(r'\w{4,}', (cont or "").lower())) for c, cont in nodos_activos}
            
            for (msg_contenido,) in mensajes:
                msg_tokens = set(re.findall(r'\w{4,}', (msg_contenido or "").lower()))
                
                # Encontrar qué conceptos aparecen en este mensaje
                conceptos_en_msg = []
                for c, tokens in nodo_tokens.items():
                    if tokens and msg_tokens:
                        overlap = tokens & msg_tokens
                        if len(overlap) >= 2:
                            conceptos_en_msg.append(c)
                
                # Para cada par de conceptos en el mismo mensaje
                for c1, c2 in combinations(conceptos_en_msg[:10], 2):
                    # v26.2: Cierre Triádico en comunicaciones
                    try:
                        from core.sinapsis import _vecinos_comunes, _dimensiones_comunes, _CIERRE_TRIADICO
                        if _CIERRE_TRIADICO:
                            vec_com = _vecinos_comunes(self.cursor, c1, c2)
                            dim_com = _dimensiones_comunes(self.cursor, c1, c2) if vec_com == 0 else 1
                            self.cursor.execute("SELECT COUNT(*) FROM sinapsis WHERE origen = ? OR destino = ?", (c1, c1))
                            sinap_exist = self.cursor.fetchone()[0]
                            if vec_com == 0 and dim_com == 0 and sinap_exist > 5:
                                continue
                    except Exception:
                        pass

                    self.cursor.execute(
                        "SELECT 1 FROM sinapsis WHERE origen = ? AND destino = ?",
                        (c1, c2)
                    )
                    es_nueva = self.cursor.fetchone() is None
                    self.cursor.execute(
                        "INSERT INTO sinapsis (origen, destino, peso, tipo, creado_en) "
                        "VALUES (?, ?, 0.4, 'co_ocurrencia', ?) "
                        "ON CONFLICT(origen, destino) DO UPDATE SET "
                        "peso = MIN(0.9, peso + 0.05), ultimo_uso = ?",
                        (c1, c2, time.time(), time.time())
                    )
                    if es_nueva:
                        dirty.add(c1)
                        dirty.add(c2)
    except Exception:
        pass  # Tabla comunicaciones puede no tener datos
    
    self.conn.commit()

    if dirty:
        try:
            from core.sdm import marcar_sdm_dirty
            marcar_sdm_dirty(self, dirty)
        except Exception:
            pass


def _clasificar_nodo_wordnet(self, concepto, contenido, sinonimos=""):
    """Clasifica las palabras del nodo por grupo semántico WordNet.
    Almacena en tabla puente nodo_grupos_semanticos."""
    try:
        from core.clasificador_wordnet import clasificar_texto
    except ImportError:
        return  # WordNet no disponible — fallback silencioso

    texto = f"{concepto} {contenido} {sinonimos}".replace("_", " ")
    clasificado = clasificar_texto(texto)

    for palabra, lexnames in clasificado.items():
        for ln in lexnames:
            # Obtener o crear grupo
            self.cursor.execute(
                "SELECT id FROM grupos_semanticos WHERE nombre = ?", (ln,)
            )
            row = self.cursor.fetchone()
            if row:
                grupo_id = row[0]
            else:
                self.cursor.execute(
                    "INSERT INTO grupos_semanticos (nombre) VALUES (?)", (ln,)
                )
                grupo_id = self.cursor.lastrowid

            self.cursor.execute(
                "INSERT OR IGNORE INTO nodo_grupos_semanticos "
                "(concepto, palabra, grupo_id) VALUES (?, ?, ?)",
                (concepto, palabra, grupo_id)
            )
    self.conn.commit()


def ciclo_sueno_consolidacion(self):
    """
    Consolida las experiencias de Corto Plazo a Largo Plazo (Corteza Permanente).
    Aplica LTD (Depresión a Largo Plazo) mediante decaimiento pasivo (-0.05) a los nodos no usados.
    Duerme los recuerdos cuyo peso sea <= 0.05.
    Aplica Inhibición Lateral Activa de forma 100% automática según la carga cortical (n_activos * 1.0).
    """
    print("\n--- Iniciando Ciclo de Consolidación (Sueño) ---")
    
    # Asegurar que existe la tabla de historial forense
    self._crear_tabla_historial_si_falta()
    
    # ══════════════════════════════════════════════════════════════
    # SNAPSHOT INICIAL: capturar estado ANTES de cualquier cambio
    # ══════════════════════════════════════════════════════════════
    self.cursor.execute("SELECT concepto, peso_sinaptico, estado FROM largo_plazo")
    snapshot_inicial = {row[0]: {'peso': row[1], 'estado': row[2]} for row in self.cursor.fetchall()}
    
    # Métricas del ciclo
    nodos_dormidos_antes = sum(1 for n in snapshot_inicial.values() if n['estado'] == 'dormido')
    sinapsis_antes = self.cursor.execute("SELECT COUNT(*) FROM sinapsis").fetchone()[0]
    n_activos = sum(1 for n in snapshot_inicial.values() if n['estado'] == 'activo') or 0

    # Lista para tracking de acciones del ciclo
    acciones_ciclo = []

    # 1. Transferencia y Fusión de Corto a Largo Plazo
    self.cursor.execute("SELECT concepto, contenido, sinonimos, categoria, COALESCE(valencia_somatica, 0.0), COALESCE(sustantivos_clave, '') FROM corto_plazo")
    recuerdos_sesion = self.cursor.fetchall()
    
    for concepto, contenido, sinonimos, cat_id, val_somatica, sk_corto in recuerdos_sesion:
        existente = snapshot_inicial.get(concepto)
        
        # Si categoria es Principle o Protocol, forzar valencia_somatica = 1.0
        cat_name = ""
        if cat_id:
            res_cat = self.cursor.execute("SELECT name FROM categories WHERE id = ?", (cat_id,)).fetchone()
            if res_cat:
                cat_name = res_cat[0]
        if cat_name in ('Principle', 'Protocol'):
            val_somatica = 1.0

        if existente:
            # Fusión de información por adición semántica y subida de peso (LTP de consolidación)
            peso_anterior = existente['peso']
            nuevo_peso = min(1.0, existente['peso'] + 0.20)
            
            self.cursor.execute("SELECT contenido, sinonimos, categoria, COALESCE(valencia_somatica, 0.0), COALESCE(sustantivos_clave, '') FROM largo_plazo WHERE concepto = ?", (concepto,))
            datos_actuales = self.cursor.fetchone()
            nuevo_contenido = datos_actuales[0] + f" | Actualización: {contenido}"
            sinonimos_exist = [s.strip() for s in (datos_actuales[1] or "").split(",") if s.strip()]
            sinonimos_nuevos = [s.strip() for s in (sinonimos or "").split(",") if s.strip() and s.strip() not in sinonimos_exist]
            sinonimos_final = ",".join(sinonimos_exist + sinonimos_nuevos)
            cat_id = datos_actuales[2] or cat_id
            val_final = max(datos_actuales[3], val_somatica)
            # CL-6 (RF-6): sustantivos_clave del largo se sobrescribe SOLO si corto_plazo trae valor no vacío.
            # Si corto_plazo viene vacío, se preserva el valor ya consolidado en largo_plazo (RF-15).
            sk_final = (sk_corto or "").strip() if (sk_corto or "").strip() else (datos_actuales[4] or "")
            
            self.cursor.execute("""
                UPDATE largo_plazo 
                SET contenido = ?, peso_sinaptico = ?, estado = 'activo', ultimo_acceso = ?, sinonimos = ?, categoria = ?, valencia_somatica = ?, sustantivos_clave = ?
                WHERE concepto = ?
            """, (nuevo_contenido, nuevo_peso, time.time(), sinonimos_final, cat_id, val_final, sk_final, concepto))
            
            acciones_ciclo.append({
                'concepto': concepto, 'accion': 'actualizado',
                'contenido_preview': (contenido or '')[:100],
                'peso_anterior': peso_anterior, 'peso_nuevo': nuevo_peso,
                'razon': f'Fusion: existia con peso {peso_anterior:.2f}, se actualizo contenido y peso +0.20',
                'contexto': f'peso_antes={peso_anterior:.2f}, peso_despues={nuevo_peso:.2f}, estado=activo',
                'anomalo': 0
            })
        else:
            # Creación de un nuevo nodo en el grafo con peso inicial máximo
            ahora = time.time()
            self.cursor.execute("""
                INSERT INTO largo_plazo (concepto, categoria, contenido, peso_sinaptico, estado, asociaciones, ultimo_acceso, sinonimos, creado_en, valencia_somatica, sustantivos_clave)
                VALUES (?, ?, ?, 1.0, 'activo', '', ?, ?, ?, ?, ?)
            """, (concepto, cat_id or 1, contenido, ahora, sinonimos or "", ahora, val_somatica, (sk_corto or "").strip()))
            
            acciones_ciclo.append({
                'concepto': concepto, 'accion': 'nuevo',
                'contenido_preview': (contenido or '')[:100],
                'peso_anterior': 0.0, 'peso_nuevo': 1.0,
                'razon': 'Nodo nuevo: no existia en largo_plazo, creado desde corto_plazo',
                'contexto': f'categoria={cat_id or 1}, peso_inicial=1.0, estado=activo',
                'anomalo': 0
            })

        # Propagar dimensiones de corto → largo plazo
        self.cursor.execute("""
            INSERT OR IGNORE INTO largo_plazo_dimensiones (concepto, dimension_id)
            SELECT concepto, dimension_id FROM corto_plazo_dimensiones WHERE concepto = ?
        """, (concepto,))
        self.cursor.execute(
            "DELETE FROM corto_plazo_dimensiones WHERE concepto = ?", (concepto,)
        )
        
        # SRL v16.0: Propagar predicados de corto → largo plazo
        self.cursor.execute("""
            INSERT INTO predicados (concepto, sujeto, accion, objeto, contexto, creado_en)
            SELECT concepto, sujeto, accion, objeto, contexto, creado_en FROM corto_plazo_predicados WHERE concepto = ?
        """, (concepto,))
        self.cursor.execute(
            "DELETE FROM corto_plazo_predicados WHERE concepto = ?", (concepto,)
        )

    # Auto-vincular cada concepto consolidado (aristas por solapamiento de tokens)
    from core.sinapsis import auto_vincular
    for concepto, contenido, _, _, _, _ in recuerdos_sesion:
        auto_vincular(self, concepto, contenido)

    # Clasificación simbólica: WordNet lexnames para cada nodo consolidado
    for concepto, contenido, sinonimos, _, _, _ in recuerdos_sesion:
        self._clasificar_nodo_wordnet(concepto, contenido, sinonimos or "")

    # Fase 2: Auto-generar sinapsis por co-ocurrencia
    # Si dos conceptos aparecieron en la misma sesión (corto_plazo), co-ocurren.
    # También analiza comunicaciones para detectar co-ocurrencia en mensajes.
    self._auto_generar_co_ocurrencia(recuerdos_sesion)

    # E10: aristas dmn_synthesized (tope, nodos activos, dim o co-ocurrencia).
    if constants.DMN_SINTESIS_ACTIVA:
        try:
            from core.dmn_engine import sintetizar_sinapsis_dmn
            sintetizar_sinapsis_dmn(self, max_n=constants.DMN_SINTESIS_MAX)
        except Exception:
            pass

    # Inferencia transitiva: recalcular sinapsis latentes (v16.0)
    # max_saltos=2: cubre A→B→C (transitivo de 1 intermediario), cobertura suficiente
    # para laptops. FACTOR_DECAY=0.7 hace que el 3er salto apenas supere el umbral 0.05
    # (0.7³ × 0.5 ≈ 0.17 para aristas fuertes), por lo que los saltos 3 aportan poco valor real.
    try:
        from core.inferencia_transitiva import calcular_sinapsis_latentes
        n_latentes = calcular_sinapsis_latentes(self, max_saltos=2)
        if n_latentes:
            print(f"[Inferencia Transitiva] {n_latentes} sinapsis latentes calculadas.")
    except Exception as e:
        print(f"[Inferencia Transitiva] Fallback silencioso: {e}")

    # 2. Decaimiento Pasivo (LTD): Power Law of Practice (ACT-R Base-Level Activation)
    # B_i = ln(sum_{k=1}^n t_k^{-0.5}) modula la tasa de olvido en vez del -0.05 estático.
    # Nodos protegidos (valencia_somatica >= 0.8 o categoria Principle/Protocol) son inmunes a LTD pasivo.
    # Prioridad P0-P1: inmunes. P2: 50% LTD. P3: normal (1.0). P4: 1.5x. P5: 2.5x.
    # Sin prioridad asignada (NULL): 1.5x (intermedio, no el más volátil).
    self.cursor.execute("""
        SELECT l.concepto, l.peso_sinaptico, COALESCE(c.decay_rate, 1.0),
               CASE
                   WHEN l.prioridad = 2 THEN 0.5
                   WHEN l.prioridad = 3 THEN 1.0
                   WHEN l.prioridad = 4 THEN 1.5
                   WHEN l.prioridad >= 5 THEN 2.5
                   WHEN l.prioridad IS NULL THEN 1.5
                   ELSE 0
               END AS mult_prio
        FROM largo_plazo l
        LEFT JOIN categories c ON c.id = l.categoria
        WHERE l.estado = 'activo'
          AND (l.prioridad IS NULL OR l.prioridad NOT IN (0, 1))
          AND l.concepto NOT IN (SELECT concepto FROM corto_plazo)
          AND COALESCE(l.valencia_somatica, 0.0) < 0.80
          AND (l.categoria IS NULL OR l.categoria NOT IN (SELECT id FROM categories WHERE name IN ('Principle', 'Protocol')))
    """)
    candidatos_ltd = self.cursor.fetchall()
    ahora_sueno = time.time()
    for concepto_ltd, peso_act, dec_cat, mult_prio in candidatos_ltd:
        b_i = self._calcular_base_level_actr(concepto_ltd, ahora=ahora_sueno)
        # Modulación ACT-R (Ley de Potencia de Práctica/Olvido de Anderson & Lebiere):
        # Si hay accesos, B_i modula el decaimiento de forma exponencial inversa:
        # - B_i alto (uso frecuente/reciente): decae menos (protección contra olvido).
        # - B_i bajo (uso lejano): decae más rápido (olvido acelerado).
        # - Sin accesos previos registrados: decae a la tasa estándar 0.05.
        if b_i is not None:
            decay_base = max(0.01, min(0.10, 0.05 * math.exp(-0.5 * b_i)))
        else:
            decay_base = 0.05
        nuevo_peso = round(max(0.0, peso_act - decay_base * dec_cat * mult_prio), 2)
        self.cursor.execute(
            "UPDATE largo_plazo SET peso_sinaptico = ? WHERE concepto = ?",
            (nuevo_peso, concepto_ltd)
        )

    # 2b. Decay Sináptico: reducir peso de conexiones no usadas en 7+ días
    self.cursor.execute("""
        UPDATE sinapsis
        SET peso = ROUND(MAX(0.0, peso * 0.95), 3)
        WHERE ultimo_uso IS NOT NULL
          AND ultimo_uso < strftime('%s', 'now') - 604800
    """)
    # Podar sinapsis muertas (F4: guiado termodinamico si flag ON).
    try:
        from core.dmn_engine import TERMODINAMICA_DMN, podar_ltd_guiado
        _f4_ltd = bool(TERMODINAMICA_DMN)
    except Exception:
        _f4_ltd = False
    if _f4_ltd:
        try:
            podar_ltd_guiado(self)
        except Exception:
            self.cursor.execute("DELETE FROM sinapsis WHERE peso < 0.05")
    else:
        self.cursor.execute("DELETE FROM sinapsis WHERE peso < 0.05")

    # 3. Poda selectiva por umbral de fuerza (Dormir recuerdos <= 0.05)
    # Snapshot ANTES de dormir (para detectar quiénes se duermen)
    self.cursor.execute("SELECT concepto FROM largo_plazo WHERE estado = 'activo'")
    activos_antes_dormir = set(row[0] for row in self.cursor.fetchall())
    
    self.cursor.execute("""
        UPDATE largo_plazo 
        SET estado = 'dormido' 
        WHERE peso_sinaptico <= 0.05 
          AND estado = 'activo'
          AND (prioridad IS NULL OR prioridad NOT IN (0, 1))
          AND COALESCE(valencia_somatica, 0.0) < 0.80
          AND (categoria IS NULL OR categoria NOT IN (SELECT id FROM categories WHERE name IN ('Principle', 'Protocol')))
    """)
    
    # Detectar quiénes se durmieron POR LTD (solo los que estaban activos y ahora son dormidos)
    self.cursor.execute("SELECT concepto FROM largo_plazo WHERE estado = 'dormido'")
    dormidos_after_ltd = set(row[0] for row in self.cursor.fetchall())
    nodos_dormidos_ltd = activos_antes_dormir & dormidos_after_ltd  # intersección: estaban activos Y ahora son dormidos

    # 4. Inhibición Lateral Activa (Control de Saturación de Energía)
    # Excluir cuarentena de conteo activo y energía
    self.cursor.execute("SELECT COUNT(*) FROM largo_plazo WHERE estado = 'activo'")
    n_activos = self.cursor.fetchone()[0] or 0
    limite_energia = max(10.0, n_activos * 0.8)

    self.cursor.execute("SELECT SUM(peso_sinaptico) FROM largo_plazo WHERE estado = 'activo'")
    energia_total = self.cursor.fetchone()[0] or 0.0

    nodos_inhibicion_lateral = []
    nodos_a_dormir = []
    if energia_total > limite_energia:
        exceso = energia_total - limite_energia
        print(f"[Inhibición Lateral] Alerta: Energía sináptica activa ({energia_total:.2f}) excede el límite ({limite_energia}). Aplicando inhibición...")
        # Obtener los nodos activos ordenados de menor peso y más antiguos (excluyendo inmunes y cuarentena)
        self.cursor.execute("""
            SELECT concepto, peso_sinaptico FROM largo_plazo 
            WHERE estado = 'activo' 
              AND (prioridad IS NULL OR prioridad NOT IN (0, 1))
              AND COALESCE(valencia_somatica, 0.0) < 0.80
              AND (categoria IS NULL OR categoria NOT IN (SELECT id FROM categories WHERE name IN ('Principle', 'Protocol')))
            ORDER BY peso_sinaptico ASC, ultimo_acceso ASC
        """)
        nodos_activos = self.cursor.fetchall()
        
        for concepto, peso in nodos_activos:
            if exceso <= 0:
                break
            nodos_a_dormir.append((concepto, peso))
            exceso -= peso

        if nodos_a_dormir:
            nodos_inhibicion_lateral = [n[0] for n in nodos_a_dormir]
            for i in range(0, len(nodos_a_dormir), 900):
                lote = [n[0] for n in nodos_a_dormir[i:i+900]]
                placeholders = ",".join("?" for _ in lote)
                self.cursor.execute(f"UPDATE largo_plazo SET estado = 'dormido', peso_sinaptico = MAX(0.05, ROUND(peso_sinaptico * 0.9, 2)) WHERE concepto IN ({placeholders})", lote)
            
            if len(nodos_a_dormir) <= 10:
                for concepto, peso in nodos_a_dormir:
                    print(f"[Inhibición Lateral] Recuerdo '{concepto}' puesto a dormir forzadamente para balancear la carga cortical.")
            else:
                print(f"[Inhibición Lateral] Puestos a dormir {len(nodos_a_dormir)} recuerdos débiles para liberar energía (Consolidación en lote exitosa).")

    # 4b. Escalado Sináptico Homeostático (Synaptic Scaling - Turrigiano 2008)
    # Si el peso medio activo excede 0.70, aplica normalización multiplicativa (x0.98) a nodos no inmunes
    self.cursor.execute("SELECT AVG(peso_sinaptico) FROM largo_plazo WHERE estado = 'activo'")
    peso_medio_activo = self.cursor.fetchone()[0] or 0.0
    if peso_medio_activo > 0.70:
        self.cursor.execute("""
            UPDATE largo_plazo
            SET peso_sinaptico = ROUND(peso_sinaptico * 0.98, 2)
            WHERE estado = 'activo'
              AND COALESCE(valencia_somatica, 0.0) < 0.80
              AND (categoria IS NULL OR categoria NOT IN (SELECT id FROM categories WHERE name IN ('Principle', 'Protocol')))
        """)
    
    # Registrar dormidos (LTD + inhibición lateral)
    # Obtener pesos REALES de nodos dormidos desde la DB (snapshot_inicial puede estar vacío si nodos venían de corto_plazo)
    nodos_dormidos_total = nodos_dormidos_ltd | set(nodos_inhibicion_lateral)
    pesos_dormidos = {}
    if nodos_dormidos_total:
        placeholders = ",".join("?" for _ in nodos_dormidos_total)
        for row in self.cursor.execute(
            f"SELECT concepto, peso_sinaptico FROM largo_plazo WHERE concepto IN ({placeholders})",
            list(nodos_dormidos_total)
        ).fetchall():
            pesos_dormidos[row[0]] = row[1]
    
    for concepto in nodos_dormidos_total:
        peso = pesos_dormidos.get(concepto, snapshot_inicial.get(concepto, {}).get('peso', 0))
        if concepto in nodos_dormidos_ltd:
            razon = f'LTD: peso {peso:.2f} <= umbral 0.05'
            contexto = f'peso={peso:.2f}, umbral=0.05, razon=ltd_decaimiento'
        else:
            razon = f'Inhibicion lateral: energia excedia limite'
            contexto = f'peso={peso:.2f}, energia_total={energia_total:.2f}, limite={limite_energia:.2f}'
        acciones_ciclo.append({
            'concepto': concepto, 'accion': 'dormido',
            'contenido_preview': '', 'peso_anterior': peso, 'peso_nuevo': 0.0,
            'razon': razon, 'contexto': contexto, 'anomalo': 0
        })

    # Auto-clustering (v16.0)
    try:
        from core.auto_clustering import detectar_comunidades, asignar_dimensiones_emergentes
        comunidades = detectar_comunidades(self)
        if comunidades:
            asignar_dimensiones_emergentes(self, comunidades)
            print(f"[Auto-Clustering] Detectadas y asignadas {len(comunidades)} dimensiones emergentes.")
    except Exception as e:
        print(f"[Auto-Clustering] Fallback silencioso: {e}")

    # 5. Vaciar la memoria de corto plazo (La mente amanece despejada)
    self.cursor.execute("DELETE FROM corto_plazo")
    # Transacción se mantiene abierta para commit atómico final con métricas

    # 6. Benchmark de rendimiento post-consolidacion
    # Omitido en cada ciclo: corre búsquedas reales que actualizan ultimo_acceso,
    # generan commits extra (~10 commits × 0.25s) y suman ~5s sin valor operativo.
    # Activar puntualmente con: cerebro._benchmark_rendimiento()
    # self._benchmark_rendimiento()

    # 7. Eviccion opcional (solo si BIORAG_PODAR=true)
    # Snapshot ANTES de evicción
    self.cursor.execute("SELECT concepto, contenido, peso_sinaptico FROM largo_plazo WHERE estado = 'dormido'")
    dormidos_antes_eviccion = {row[0]: {'contenido': row[1], 'peso': row[2]} for row in self.cursor.fetchall()}
    
    eliminados_count = 0
    if os.environ.get("BIORAG_PODAR") == "true":
        eliminados_count = self._ejecutar_eviccion(max_borrar=10)
        if eliminados_count:
            print(f"[Eviccion] {eliminados_count} nodos dormidos eliminados permanentemente.")
    
    # Detectar quiénes fueron eliminados
    self.cursor.execute("SELECT concepto FROM largo_plazo WHERE estado = 'dormido'")
    dormidos_despues_eviccion = set(row[0] for row in self.cursor.fetchall())
    nodos_elimidos = dormidos_antes_eviccion.keys() - dormidos_despues_eviccion
    
    for concepto in nodos_elimidos:
        info = dormidos_antes_eviccion[concepto]
        acciones_ciclo.append({
            'concepto': concepto, 'accion': 'eliminado',
            'contenido_preview': (info['contenido'] or '')[:100],
            'peso_anterior': info['peso'], 'peso_nuevo': 0.0,
            'razon': f'Eviccion: nodo dormido con peso {info["peso"]:.3f} <= 0.01',
            'contexto': f'peso={info["peso"]:.3f}, umbral_eviccion=0.01, BIORAG_PODAR=true',
            'anomalo': 0
        })

    # 8. Registrar métricas cognitivas del ciclo
    nodos_dormidos_despues = self.cursor.execute("SELECT COUNT(*) FROM largo_plazo WHERE estado = 'dormido'").fetchone()[0]
    sinapsis_despues = self.cursor.execute("SELECT COUNT(*) FROM sinapsis").fetchone()[0]
    # Contar categorías de nodos consolidados EN ESTE CICLO (no en toda la base)
    cats_ciclo = {}
    if recuerdos_sesion:
        cat_ids_unicos = list(set(r[3] for r in recuerdos_sesion if len(r) > 3 and r[3]))
        if cat_ids_unicos:
            placeholders = ",".join("?" for _ in cat_ids_unicos)
            cats_map = {}
            for row in self.cursor.execute(
                f"SELECT id, name FROM categories WHERE id IN ({placeholders})",
                cat_ids_unicos
            ):
                cats_map[row[0]] = row[1]
            for r in recuerdos_sesion:
                cat_id = r[3]
                if cat_id and cat_id in cats_map:
                    nombre = cats_map[cat_id]
                    cats_ciclo[nombre] = cats_ciclo.get(nombre, 0) + 1

    # En caso de empate en cantidad de nodos por categoría, gana la primera
    # categoría según el orden de iteración de recuerdos_sesion (no es aleatorio,
    # pero tampoco tiene un criterio de desempate más allá de eso).
    cat_dom_name = max(cats_ciclo, key=cats_ciclo.get) if cats_ciclo else None
    
    # Convertir nombre de categoría a ID para FK
    cat_dom_id = None
    if cat_dom_name:
        self.cursor.execute("SELECT id FROM categories WHERE name = ?", (cat_dom_name,))
        cat_row = self.cursor.fetchone()
        cat_dom_id = cat_row[0] if cat_row else None
    
    self.cursor.execute("""
        INSERT INTO metricas_cognitivas
        (timestamp, nodos_consolidados, nodos_dormidos_ciclo, sinapsis_creadas, sinapsis_podadas, categoria_dominante_id, ratio_consolidacion)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        time.time(),
        len(recuerdos_sesion),
        nodos_dormidos_despues - nodos_dormidos_antes,
        max(0, sinapsis_despues - sinapsis_antes),
        max(0, sinapsis_antes - sinapsis_despues),
        cat_dom_id,
        round(len(recuerdos_sesion) / max(1, n_activos), 2)
    ))
    
    # ── Guardar historial forense completo en tabla puente ──
    metrica_id = self.cursor.lastrowid
    now = time.time()
    for accion in acciones_ciclo:
        # Lookup largo_plazo_id from concepto
        self.cursor.execute("SELECT id FROM largo_plazo WHERE concepto = ?", (accion['concepto'],))
        lp_row = self.cursor.fetchone()
        largo_plazo_id = lp_row[0] if lp_row else None
        
        self.cursor.execute("""
            INSERT INTO metricas_cognitivas_nodos 
            (metrica_id, largo_plazo_id, accion, contenido_preview, peso_anterior, peso_nuevo, razon, contexto, anomalo, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            metrica_id,
            largo_plazo_id,
            accion['accion'],
            accion['contenido_preview'],
            accion['peso_anterior'],
            accion['peso_nuevo'],
            accion['razon'],
            accion['contexto'],
            accion.get('anomalo', 0),
            now
        ))
    
    # Optimizar FTS después de consolidation para reducir fragmentación
    self.cursor.execute("INSERT INTO largo_plazo_fts(largo_plazo_fts) VALUES('optimize')")
    try:
        self.cursor.execute("INSERT INTO largo_plazo_fts_unicode(largo_plazo_fts_unicode) VALUES('optimize')")
    except sqlite3.OperationalError:
        pass
    self.conn.commit()

    # SDM v2.0: Reindex selectivo por dirty-set + full reindex periódico (24h)
    # El dirty-set es explícito (marcado en cada sinapsis NUEVA): no se confía
    # en actualizado_en, que miente cuando un vecino nuevo cambia el vector.
    # indexar_todos_sdm se conserva como red de seguridad periódica.
    try:
        from core.sdm import (
            indexar_todos_sdm, reindex_selectivo_sdm, marcar_sdm_dirty,
            limpiar_sdm_dirty, _sdm_full_reindex_due, _registrar_sdm_full_reindex,
        )
        # Los nodos consolidados en este ciclo cambiaron contenido/peso → dirty
        for concepto, *_ in recuerdos_sesion:
            marcar_sdm_dirty(self, (concepto,))
        if _sdm_full_reindex_due(self):
            n_sdm = indexar_todos_sdm(self)
            limpiar_sdm_dirty(self)
            _registrar_sdm_full_reindex(self)
            if n_sdm:
                print(f"[SDM] {n_sdm} vectores reindexados (full periódico).")
        else:
            n_sdm = reindex_selectivo_sdm(self)
            if n_sdm:
                print(f"[SDM] {n_sdm} vectores reindexados (selectivo).")
    except Exception:
        pass
    # Signal #13 (v26.0): Reindexar vectores PPMI+SVD de forma incremental (fold-in < 10ms)
    # El re-entrenamiento completo (SVD full) solo se ejecuta periódicamente si han acumulado >=50 nodos y 7 días
    _ppmi_did_full = False
    try:
        from core.ppmi_vectorizer import reindexar_ppmi_svd, fold_in_nodos, _ppmi_full_reindex_due
        conceptos_nuevos = [c for c, *_ in recuerdos_sesion] if recuerdos_sesion else []
        if _ppmi_full_reindex_due(self.conn, delta_nodos_nuevos=len(conceptos_nuevos)):
            n_ppmi = reindexar_ppmi_svd(self.conn)
            _ppmi_did_full = True
            if n_ppmi:
                print(f"[PPMI] {n_ppmi} nodos reindexados con PPMI+SVD+Retrofitting (full periódico).")
        else:
            n_ppmi = fold_in_nodos(self.conn, conceptos_nuevos)
            if n_ppmi:
                print(f"[PPMI] {n_ppmi} nodos reindexados con fold-in incremental.")

        # Actualizar el índice en memoria
        if self._ppmi_index is not None:
            if _ppmi_did_full:
                # Full reindex: recargar todo desde disco
                from core.ppmi_hybrid_search import IndicesBioRAG
                self._ppmi_index = IndicesBioRAG(str(self.db_path))
            else:
                # Fold-in: actualizar solo los nodos nuevos en el dict en memoria (ahorra ~5.9s)
                import numpy as np
                for concepto in conceptos_nuevos:
                    row = self.conn.execute(
                        "SELECT vector FROM nodos WHERE concepto = ?", (concepto,)
                    ).fetchone()
                    if row:
                        self._ppmi_index.vecs[concepto] = np.frombuffer(row[0], dtype='float32').astype('float64')
        self.conn.commit()
    except Exception as _ppmi_err:
        pass  # No bloquear el sueño si PPMI falla

    # Invalidar cachés temáticos y de inferencia en RAM para que reconozcan los nuevos nodos
    self._thematic_scores_cache = None
    self._thematic_profiles_cache = None
    self._thematic_idf_cache = None
    # NO se invalida el cache de pares_dim aquí: la dimension data se transfiere
    # de corto→largo ANTES de que calcular_sinapsis_latentes la lea, así que el
    # cache del ciclo actual ya refleja los nuevos nodos. Persistirlo ahorra 2.566s
    # en el siguiente ciclo. Solo se invalida cuando auto_clustering agrega nuevas dims.

    print("[MemoryBioRAG] Proceso de consolidación y equilibrio sináptico completado con éxito.")
