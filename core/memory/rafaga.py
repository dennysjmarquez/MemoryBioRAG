"""
Módulo de búsqueda y validación por ráfaga de reminiscencia.

Extraído de SQLiteMemoryBioRAG (Paso 3.4f - T17).
"""

import sqlite3
import time
import re
import math
import sys
from itertools import combinations

from core.memory import constants


def validar_rafaga(self, rafaga_palabras):
    """Valida palabras de ráfaga contra FTS5 y prioriza por frecuencia.
    
    Retorna lista de palabras (strings) ordenada por relevancia.
    Solo retorna palabras que existen en al menos un nodo de la DB.
    """
    if not rafaga_palabras:
        return []
    
    validadas = []
    for palabra in rafaga_palabras:
        if len(palabra) < 3:
            continue
        try:
            self.cursor.execute(
                "SELECT COUNT(*) FROM largo_plazo_fts WHERE largo_plazo_fts MATCH ?",
                (f'"{palabra}"',)
            )
            count = self.cursor.fetchone()[0]
            if count > 0:
                validadas.append((palabra, count))
        except sqlite3.OperationalError:
            pass
    
    validadas.sort(key=lambda x: x[1], reverse=True)
    return [palabra for palabra, _ in validadas]


def buscar_por_rafaga(self, query, rafaga_palabras, pagina=1, limite=None, dimensiones_ids=None):
    """Búsqueda por ráfaga de reminiscencia: emula el proceso humano de recordar.
    
    Cuando la búsqueda normal falla, usa palabras asociadas al azar para encontrar
    nodos dormidos o aislados. Si encuentra un match, crea sinapsis automáticamente
    y despierta el nodo.
    
    Retorna (resultados, total) y lista de sinapsis creadas.
    """
    if pagina < 1:
        pagina = 1
    if limite is None:
        limite = constants.LIMITE_RAFTAGA
    
    if not rafaga_palabras:
        return [], 0, []
    
    # Fase 0: Verificar errores previos de interpretación
    errores_previos = set()
    try:
        self.cursor.execute(
            "SELECT concepto, contenido FROM largo_plazo "
            "WHERE concepto LIKE 'error_interpretacion_%' AND estado = 'activo'"
        )
        for c, contenido in self.cursor.fetchall():
            for palabra in rafaga_palabras:
                if palabra in (contenido or ""):
                    errores_previos.add(palabra)
    except Exception:
        pass  # ponytail: historial_fallos puede estar vacío o malformado
    
    rafaga_limpia = [p for p in rafaga_palabras if p not in errores_previos]
    
    if not rafaga_limpia:
        return [], 0, []
    
    todos = []
    palabra_ganadora = None
    seen_rowids = set()

    # Filtrar palabras válidas (>= 3 chars, sin comillas dobles)
    palabras_validas = [p for p in rafaga_limpia if len(p) >= 3 and '"' not in p]
    if not palabras_validas:
        return [], 0, []

    # Construir query FTS5 con OR — un solo MATCH para todas las palabras.
    # Esto elimina el cuello de botella de variables SQL y permite
    # cantidad ilimitada de términos en la ráfaga.
    fts_terms = " OR ".join(f'"{p}"' for p in palabras_validas)
    limite_batch = max(limite * len(palabras_validas), 50)

    # Filtro PALABRA_COMPLETA: previene falsos positivos de FTS5 trigram.
    # "raro" no debe matchear "increíblemente" vía trigram parcial.
    pc_rafaga_clauses = []
    pc_rafaga_params = []
    for p in palabras_validas:
        pc_rafaga_clauses.append(
            "(PALABRA_COMPLETA(?, l.contenido) = 1 OR PALABRA_COMPLETA(?, l.concepto) = 1 OR PALABRA_COMPLETA(?, COALESCE(l.sinonimos, '')) = 1)"
        )
        pc_rafaga_params.extend([p, p, p])
    pc_rafaga_clause = " AND (" + " OR ".join(pc_rafaga_clauses) + ")"

    # Buscar en activos — query único con PALABRA_COMPLETA
    try:
        self.cursor.execute(
            "SELECT l.rowid, l.concepto, l.contenido, l.peso_sinaptico, "
            "l.estado, l.asociaciones, "
            "bm25(largo_plazo_fts, 5.0, 1.0, 2.0, 4.0) AS bm25_val "
            "FROM largo_plazo_fts f CROSS JOIN largo_plazo l ON l.rowid = f.rowid "
            "WHERE largo_plazo_fts MATCH ? AND l.estado = 'activo' "
            + pc_rafaga_clause + " LIMIT ?",
            (fts_terms,) + tuple(pc_rafaga_params) + (limite_batch,)
        )
        resultados = self.cursor.fetchall()
        for r in resultados:
            if r[0] not in seen_rowids:
                todos.append(r)
                seen_rowids.add(r[0])
        if resultados and not palabra_ganadora:
            texto = f"{resultados[0][1] or ''} {resultados[0][2] or ''}".lower()
            for p in palabras_validas:
                if p.lower() in texto:
                    palabra_ganadora = p
                    break
            if not palabra_ganadora:
                palabra_ganadora = palabras_validas[0]
    except sqlite3.OperationalError:
        pass

    # SIEMPRE buscar en dormidos también (la ráfaga rescata del olvido)
    try:
        self.cursor.execute(
            "SELECT l.rowid, l.concepto, l.contenido, l.peso_sinaptico, "
            "l.estado, l.asociaciones, "
            "bm25(largo_plazo_fts, 5.0, 1.0, 2.0, 4.0) AS bm25_val "
            "FROM largo_plazo_fts f CROSS JOIN largo_plazo l ON l.rowid = f.rowid "
            "WHERE largo_plazo_fts MATCH ? AND l.estado = 'dormido' "
            + pc_rafaga_clause + " LIMIT ?",
            (fts_terms,) + tuple(pc_rafaga_params) + (limite_batch,)
        )
        resultados = self.cursor.fetchall()
        for r in resultados:
            if r[0] not in seen_rowids:
                todos.append(r)
                seen_rowids.add(r[0])
        if resultados and not palabra_ganadora:
            texto = f"{resultados[0][1] or ''} {resultados[0][2] or ''}".lower()
            for p in palabras_validas:
                if p.lower() in texto:
                    palabra_ganadora = p
                    break
            if not palabra_ganadora:
                palabra_ganadora = palabras_validas[0]
    except sqlite3.OperationalError:
        pass
    
    if not todos:
        return [], 0, []
    
    # Fase 2: Calcular score por densidad de coincidencia y boost de dimensiones
    dim_scores_map = {}
    if dimensiones_ids and len(dimensiones_ids) > 0:
        conceptos_todos = [r[1] for r in todos if r[1]]
        if conceptos_todos:
            placeholders = ",".join(["?" for _ in conceptos_todos])
            dim_ids_str = ",".join([str(d) for d in dimensiones_ids])
            dim_sql = f"""
                SELECT concepto, dimension_id
                FROM largo_plazo_dimensiones
                WHERE concepto IN ({placeholders})
                AND dimension_id IN ({dim_ids_str})
            """
            try:
                self.cursor.execute(dim_sql, conceptos_todos)
                # Agrupar IDs por concepto
                concepto_dim_ids = {}
                for concepto, dim_id in self.cursor.fetchall():
                    if concepto not in concepto_dim_ids:
                        concepto_dim_ids[concepto] = []
                    concepto_dim_ids[concepto].append(dim_id)
                # Coseno binario: shared / sqrt(|query| × |doc|)
                query_dim_set = set(dimensiones_ids)
                query_len = len(query_dim_set)
                for concepto, doc_ids in concepto_dim_ids.items():
                    doc_set = set(doc_ids)
                    shared = len(query_dim_set & doc_set)
                    if shared > 0:
                        dim_scores_map[concepto] = shared / math.sqrt(query_len * len(doc_set))
            except Exception:
                dim_scores_map = {}  # ponytail: fallback a scores vacíos si falla el batch dimensional

    # Fase 1.5: Despertar temprano de nodos dormidos en la ráfaga
    todos_actualizados = []
    nodos_despertados = False
    for r in todos:
        rowid, concepto, contenido, peso, estado, asoc, *bm25_rest = r
        if estado == 'dormido':
            nuevo_peso = min(1.0, peso + 0.3)
            self.cursor.execute(
                "UPDATE largo_plazo SET estado = 'activo', peso_sinaptico = ?, ultimo_acceso = ? WHERE concepto = ?",
                (nuevo_peso, time.time(), concepto)
            )
            nodos_despertados = True
            todos_actualizados.append((rowid, concepto, contenido, nuevo_peso, 'activo', asoc) + tuple(bm25_rest))
        else:
            todos_actualizados.append(r)
    
    if nodos_despertados:
        self.conn.commit()
    todos = todos_actualizados

    total = len(todos)

    # Normalización BM25 consistente con buscar_por_frase (Opción 1: Reúso y extensión de escala)
    # Para garantizar comparabilidad cuando mcp_server combina resultados de frase + ráfaga
    # y reordena por score (r[4]), ráfaga normaliza contra la misma escala [lo, hi] de frase.
    # Si un candidato de ráfaga excede los límites previos, el rango se extiende sin recortar.
    rafaga_raw_vals = [abs(r[6] if len(r) > 6 else 0.0) for r in todos]
    if rafaga_raw_vals:
        r_lo, r_hi = min(rafaga_raw_vals), max(rafaga_raw_vals)
        if getattr(self, '_last_bm25_bounds', None) is not None:
            base_lo, base_hi, _ = self._last_bm25_bounds
            lo = min(base_lo, r_lo)
            hi = max(base_hi, r_hi)
        else:
            lo, hi = r_lo, r_hi
        rango = hi - lo if hi > lo else 1.0
        escala = min(1.0, hi) if hi > 0 else 1.0
        if hi > lo:
            bm25_norm_map = {
                r[1]: ((abs(r[6] if len(r) > 6 else 0.0) - lo) / rango) * escala for r in todos
            }
        elif len(todos) == 1 and hi >= 3.0:
            bm25_norm_map = {r[1]: escala for r in todos}
        else:
            bm25_norm_map = {r[1]: 0.0 for r in todos}
    else:
        bm25_norm_map = {}

    scored = []
    for r in todos:
        rowid, concepto, contenido, peso, estado, asoc, *bm25_rest = r
        texto_nodo = f"{concepto} {contenido or ''}".lower()
        texto_norm = texto_nodo.replace('_', ' ').replace('-', ' ')
        matches = sum(
            1 for pv in palabras_validas
            if re.search(r'\b' + re.escape(pv.lower()) + r'\b', texto_norm)
        )
        densidad = matches / len(palabras_validas) if palabras_validas else 0.0
        num_asoc = len([v for v in (asoc or "").split(",") if v.strip()]) if asoc else 0
        dim_score = dim_scores_map.get(concepto, 0.0)

        match_exacto = False
        from core.fallback_simbolico import _tokenizar_normalizado
        for pv in palabras_validas:
            _c_norm = (concepto or "").lower().replace(" ", "_").replace("-", "_")
            _pv_norm = pv.lower().replace(" ", "_").replace("-", "_")
            if _pv_norm == _c_norm:
                match_exacto = True
                break
            tokens_pv = _tokenizar_normalizado(pv)
            if tokens_pv and tokens_pv == _tokenizar_normalizado(concepto):
                match_exacto = True
                break

        # Signal #11: JSD (rafaga path)
        jsd_val = 0.0
        if constants.JSD_WEIGHT > 0.0:
            node_text = f"{concepto} {contenido or ''}"
            jsd_val = self._calcular_jsd(query, node_text)

        score_hibrido = self._calcular_score_hibrido(
            bm25_norm=bm25_norm_map.get(concepto, 0.0),
            dim_score=dim_score,
            peso_sinaptico=peso,
            concepto_ratio=0.0,
            sinonimos_ratio=0.0,
            score_latente=densidad,
            score_cadena=0.0,
            asoc_count=num_asoc,
            match_exacto=match_exacto,
            tematico_score=0.0,
            jsd_score=jsd_val,
            jsd_weight=constants.JSD_WEIGHT,
            pred_score=0.0,   # Rafaga path: no predicate data precomputed
            ppmi_score=0.0    # Signal #13: neutral en ráfaga (queries ya son muy específicas)
        )

        scored.append((concepto, contenido, peso, estado, score_hibrido, asoc or ""))
    
    scored.sort(key=lambda r: r[4], reverse=True)
    
    # Fase 3: Auto-sinapsis y despertar TODOS los nodos dormidos encontrados
    sinapsis_creadas = []
    query_tokens = set(re.findall(r'\w{4,}', query.lower()))
    
    # Primero: despertar TODOS los nodos dormidos (ya realizado en Fase 1.5, bucle omitido)
    
    # Segundo: crear sinapsis solo para los top resultados con score válido
    UMBRAL_SCORE_RAFAGA = 0.5
    for concepto, contenido, peso, estado, score, asoc in scored[:limite]:
        
        # No crear sinapsis si el score es muy bajo (match por trigram parcial)
        if score < UMBRAL_SCORE_RAFAGA:
            continue
        
        # Verificar que al menos una palabra de la ráfaga aparece como palabra completa
        texto_nodo = f"{concepto} {contenido or ''}".lower()
        texto_nodo_norm = texto_nodo.replace('_', ' ').replace('-', ' ')
        alguna_palabra_completa = False
        for pv in palabras_validas:
            if re.search(r'\b' + re.escape(pv.lower()) + r'\b', texto_nodo_norm):
                alguna_palabra_completa = True
                break
        if not alguna_palabra_completa:
            continue
        
        # Crear sinapsis entre query y nodo encontrado
        # CRÍTICO: solo crear sinapsis si el token del query aparece como
        # palabra completa en el nodo. Evita sinapsis basura cuando el query
        # es una palabra inventada (ej: "xylqvembra") que no existe en ningún nodo.
        if palabra_ganadora and query_tokens:
            for qt in query_tokens:
                if qt != concepto and len(qt) >= 4:
                    # Verificar que el token del query existe como palabra completa en el nodo
                    if not re.search(r'\b' + re.escape(qt) + r'\b', texto_nodo_norm):
                        continue
                    # ponytail: solo crear sinapsis si el token existe como concepto en largo_plazo
                    self.cursor.execute(
                        "SELECT 1 FROM largo_plazo WHERE concepto = ? AND estado = 'activo'",
                        (qt,)
                    )
                    if not self.cursor.fetchone():
                        continue
                    # Verificar si ya existe la sinapsis
                    self.cursor.execute(
                        "SELECT peso FROM sinapsis WHERE "
                        "(origen = ? AND destino = ?) OR (origen = ? AND destino = ?)",
                        (qt, concepto, concepto, qt)
                    )
                    existente = self.cursor.fetchone()
                    
                    if not existente:
                        self.cursor.execute(
                            "INSERT INTO sinapsis (origen, destino, peso, tipo, creado_en) "
                            "VALUES (?, ?, 0.6, 'rafaga_rememb', ?)",
                            (qt, concepto, time.time())
                        )
                        sinapsis_creadas.append((qt, concepto, 0.6))
                    else:
                        # Reforzar sinapsis existente
                        nuevo_peso = min(0.95, existente[0] + 0.1)
                        self.cursor.execute(
                            "UPDATE sinapsis SET peso = ?, ultimo_uso = ? "
                            "WHERE (origen = ? AND destino = ?) OR (origen = ? AND destino = ?)",
                            (nuevo_peso, time.time(), qt, concepto, concepto, qt)
                        )
    
    self.conn.commit()

    # Reindex SDM selectivo: marcar dirty las sinapsis rafaga_rememb nuevas
    # (sinapsis_creadas solo acumula inserciones reales, no refuerzos)
    if sinapsis_creadas:
        try:
            from core.sdm import marcar_sdm_dirty
            dirty_rafaga = {e for par in sinapsis_creadas for e in par[:2]}
            marcar_sdm_dirty(self, dirty_rafaga)
        except Exception:
            pass
    
    # Fase 4: Métricas de ráfaga
    if sinapsis_creadas:
        print(f"[Ráfaga] Palabra ganadora: '{palabra_ganadora}'", file=sys.stderr)
        print(f"[Ráfaga] Sinapsis creadas: {len(sinapsis_creadas)}", file=sys.stderr)
        for origen, destino, peso in sinapsis_creadas:
            print(f"  {origen} → {destino} (peso: {peso})", file=sys.stderr)
    
    inicio = (pagina - 1) * limite
    return scored[inicio:inicio + limite], len(scored), sinapsis_creadas
