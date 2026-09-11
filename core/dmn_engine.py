"""
BioRAG v21.0 — Default Mode Network (DMN) & Motor de Curiosidad Espontánea
==========================================================================
Implementa la Red por Defecto (Default Mode Network) para BioRAG.
Permite que el cerebro sintético explore asociaciones latentes, sintetice hipótesis
y genere "Insights" de forma autónoma en momentos de reposo (inactividad).

Incorpora las 5 Mejoras Estratégicas Biomiméticas:
1. Muestreo Resonante Cortical (Spindles Replay: Nodo Ancla High-Valence -> Exploración Latente 2-3 Saltos).
2. Concurrencia Aislada Thread-Local con SQLite WAL y PRAGMA busy_timeout=5000.
3. Selección Natural de Hipótesis (Decaimiento LTD pasivo si no recibe atención).
4. Presupuesto de Energía & Periodo Refractario (Máximo 3 ideas por ciclo de reposo, 60s cooldown).
5. Payload Enriquecido para biorag_estado_dmn (JSON estructurado forense).
"""

import time
import threading
import logging
import os
import re
import json
import random
import sqlite3

logger = logging.getLogger("BioRAG.DMN")

DMN_SINTESIS_ACTIVA = os.environ.get("BIORAG_DMN_SINTESIS_ACTIVA", "1").lower() in ("1", "true", "yes")
DMN_SINTESIS_MAX = int(os.environ.get("BIORAG_DMN_SINTESIS_MAX", "8"))
DMN_SINTESIS_PESO = float(os.environ.get("BIORAG_DMN_SINTESIS_PESO", "0.30"))


def sintetizar_sinapsis_dmn(cerebro, max_n=None, peso=None):
    """E10: pares activos con dim comun o tokens compartidos, sin arista directa.

    Tope max_n (default 8). No fusiona nodos. tipo='dmn_synthesized'.
    """
    if not DMN_SINTESIS_ACTIVA:
        return 0
    max_n = int(max_n if max_n is not None else DMN_SINTESIS_MAX)
    peso = float(peso if peso is not None else DMN_SINTESIS_PESO)
    if max_n <= 0:
        return 0
    # F4: pool amplio para rankear por ΔF. OFF → pool_n == max_n (idéntico).
    pool_n = max_n * TERMODINAMICA_POOL_X if TERMODINAMICA_DMN else max_n
    cur = cerebro.cursor
    ahora = time.time()
    creadas = 0
    try:
        cur.execute(
            """
            WITH seeds AS (
                SELECT concepto FROM largo_plazo
                WHERE estado = 'activo'
                ORDER BY peso_sinaptico DESC
                LIMIT 40
            )
            SELECT d1.concepto, d2.concepto, COUNT(*) AS n
            FROM largo_plazo_dimensiones d1
            JOIN seeds s1 ON s1.concepto = d1.concepto
            JOIN largo_plazo_dimensiones d2
              ON d1.dimension_id = d2.dimension_id AND d1.concepto < d2.concepto
            JOIN seeds s2 ON s2.concepto = d2.concepto
            WHERE NOT EXISTS (
                SELECT 1 FROM sinapsis s
                WHERE (s.origen = d1.concepto AND s.destino = d2.concepto)
                   OR (s.origen = d2.concepto AND s.destino = d1.concepto)
            )
            GROUP BY d1.concepto, d2.concepto
            HAVING n >= 1
            ORDER BY n DESC
            LIMIT ?
            """,
            (pool_n,),
        )
        pares = list(cur.fetchall())
    except Exception:
        pares = []
    if len(pares) < pool_n:
        falta = pool_n - len(pares)
        ya = {(p[0], p[1]) for p in pares}
        try:
            cur.execute(
                "SELECT concepto, contenido FROM largo_plazo WHERE estado = 'activo' "
                "ORDER BY peso_sinaptico DESC LIMIT 40"
            )
            nodos = cur.fetchall()
            import re
            toks = {c: set(re.findall(r"\w{4,}", (txt or "").lower())) for c, txt in nodos}
            extra = []
            for i, (c1, _) in enumerate(nodos):
                for c2, _ in nodos[i + 1 :]:
                    if (c1, c2) in ya or (c2, c1) in ya:
                        continue
                    if len(toks.get(c1, set()) & toks.get(c2, set())) < 2:
                        continue
                    cur.execute(
                        "SELECT 1 FROM sinapsis WHERE "
                        "(origen=? AND destino=?) OR (origen=? AND destino=?)",
                        (c1, c2, c2, c1),
                    )
                    if cur.fetchone():
                        continue
                    extra.append((c1, c2, 1))
                    ya.add((c1, c2))
                    if len(extra) >= falta:
                        break
                if len(extra) >= falta:
                    break
            pares.extend(extra)
        except Exception:
            pass
    # F4: mismo conteo max_n, pero elegidos por ΔF mínima. OFF → orden E10.
    if TERMODINAMICA_DMN and pares:
        try:
            _rank = rankear_pares_por_delta_f(
                cerebro, [(p[0], p[1]) for p in pares],
                temperatura=TERMODINAMICA_TEMP,
                n_semillas=TERMODINAMICA_SEMILLAS, modo="agregar",
            )
            if _rank:
                pares = [(a, b, 0) for a, b, _ in _rank[:max_n]]
        except Exception:
            pass
    for origen, destino, *_rest in pares[:max_n]:
        try:
            cur.execute(
                "INSERT INTO sinapsis (origen, destino, peso, tipo, creado_en) "
                "VALUES (?, ?, ?, 'dmn_synthesized', ?) "
                "ON CONFLICT(origen, destino) DO NOTHING",
                (origen, destino, peso, ahora),
            )
            if cur.rowcount:
                creadas += 1
        except Exception:
            continue
    if creadas:
        try:
            cerebro.conn.commit()
        except Exception:
            pass
    return creadas


class DMNEngine:
    def __init__(self, cerebro, idle_seconds=300, check_interval=2.0):
        """
        cerebro: Instancia principal de SQLiteMemoryBioRAG
        idle_seconds: Segundos de inactividad necesarios para activar DMN (default: 300s / 5min)
        """
        self.cerebro = cerebro
        self.db_path = cerebro.db_path
        self.idle_seconds = float(os.environ.get("BIORAG_DMN_IDLE_SECONDS", str(idle_seconds)))
        self.check_interval = float(check_interval)
        self.ultimo_acceso_usuario = time.time()
        self._stop_event = threading.Event()
        self._user_active_event = threading.Event()
        self._thread = None
        self.ideas_generadas_sesion = 0
        self.max_ideas_por_reposo = int(os.environ.get("BIORAG_DMN_MAX_IDEAS", "3"))
        self.periodo_refractario = float(os.environ.get("BIORAG_DMN_REFRACTARIO", "60.0"))
        self.ultima_idea = None
        self.activo = False

    def notificar_actividad_usuario(self):
        """Notifica interacción del usuario. Reinicia temporizador e interrumpe ciclo DMN."""
        self.ultimo_acceso_usuario = time.time()
        self._user_active_event.set()

    def start(self):
        """Inicia el hilo autónomo de curiosidad DMN en segundo plano."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._user_active_event.clear()
        self.activo = True
        self._thread = threading.Thread(target=self._bucle_dmn, name="BioRAG-DMN-Thread", daemon=True)
        self._thread.start()
        logger.info(f"DMN iniciado. Umbral de inactividad: {self.idle_seconds}s")

    def stop(self):
        """Detiene limpiamente el hilo DMN."""
        self.activo = False
        self._stop_event.set()
        self._user_active_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        logger.info("DMN detenido.")

    def _crear_conexion_hilo(self):
        """Crea una conexión SQLite aislada Thread-Local con WAL mode y busy_timeout=5000."""
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _bucle_dmn(self):
        """Bucle principal de la Red por Defecto (runs in background thread)."""
        ideas_en_reposo_actual = 0
        conn = self._crear_conexion_hilo()

        while not self._stop_event.is_set():
            time.sleep(self.check_interval)

            if self._user_active_event.is_set():
                self._user_active_event.clear()
                ideas_en_reposo_actual = 0
                continue

            tiempo_inactivo = time.time() - self.ultimo_acceso_usuario
            if tiempo_inactivo >= self.idle_seconds and ideas_en_reposo_actual < self.max_ideas_por_reposo:
                if not self._stop_event.is_set() and not self._user_active_event.is_set():
                    try:
                        idea = self.ejecutar_ciclo_curiosidad(conn_hilo=conn)
                        if idea:
                            ideas_en_reposo_actual += 1
                            time.sleep(min(self.periodo_refractario, 5.0))
                    except Exception as e:
                        logger.warning(f"Error en ciclo DMN: {e}")

        try:
            conn.close()
        except Exception:
            pass

    def ejecutar_ciclo_curiosidad(self, conn_hilo=None, forzar=False) -> dict | None:
        """
        Ejecuta una ronda de ideación espontánea mediante Muestreo Resonante Cortical y Teleología Genética:
        1. Selecciona Nodo Ancla (N1) con valencia_somatica >= 0.3 o peso_sinaptico >= 0.5.
        2. Busca un Nodo Resonante (N2) distinto en el espacio asociativo, dimensional o genético (ADN).
        3. Genera un Insight autónomo o una Hipótesis Teleológica basada en ADN compartido.
        4. Si no recibe atención futura (LTP/feedback), sufrirá decaimiento pasivo natural por sueño (LTD).
        """
        if not forzar:
            if self._user_active_event.is_set() or self._stop_event.is_set():
                return None

        auto_close = False
        if conn_hilo is None:
            conn = self.cerebro.conn
        else:
            conn = conn_hilo

        cursor = conn.cursor()

        try:
            # 1. Seleccionar Nodo Ancla N1 (Alta valencia somática o peso)
            cursor.execute("""
                SELECT id, concepto, contenido, COALESCE(valencia_somatica, 0.0), peso_sinaptico
                FROM largo_plazo
                WHERE estado = 'activo' AND (valencia_somatica >= 0.3 OR peso_sinaptico >= 0.5)
                ORDER BY valencia_somatica DESC, peso_sinaptico DESC
                LIMIT 30
            """)
            anclas = cursor.fetchall()
            if not anclas:
                return None

            nodo_ancla = random.choice(anclas)
            id1, c1, cont1, val1, p1 = nodo_ancla

            # 2. Buscar Nodo Resonante N2 (que comparta dimensión semántica)
            cursor.execute("""
                SELECT DISTINCT l.id, l.concepto, l.contenido, COALESCE(l.valencia_somatica, 0.0), l.peso_sinaptico
                FROM largo_plazo_dimensiones d1
                JOIN largo_plazo_dimensiones d2 ON d1.dimension_id = d2.dimension_id
                JOIN largo_plazo l ON d2.concepto = l.concepto
                WHERE d1.concepto = ? AND d2.concepto != ? AND l.estado = 'activo'
                LIMIT 30
            """, (c1, c1))
            candidatos_resonantes = cursor.fetchall()

            # Si no hay resonancia dimensional explícita, buscar candidatos generales activos distintos
            if not candidatos_resonantes:
                cursor.execute("""
                    SELECT id, concepto, contenido, COALESCE(valencia_somatica, 0.0), peso_sinaptico
                    FROM largo_plazo
                    WHERE estado = 'activo' AND concepto != ?
                    ORDER BY creado_en DESC
                    LIMIT 30
                """, (c1,))
                candidatos_resonantes = cursor.fetchall()

            # Filtrar candidatos distintos
            candidatos_validos = [cand for cand in candidatos_resonantes if cand[1] != c1]

            if not candidatos_validos:
                return None

            nodo_destino = random.choice(candidatos_validos)
            id2, c2, cont2, val2, p2 = nodo_destino

            # Abortar de inmediato si el usuario envió un prompt en este microsegundo (salvo ejecuciones forzadas manuales)
            if not forzar and self._user_active_event.is_set():
                conn.rollback()
                return None

            # Obtener dimensiones compartidas para el payload forense
            cursor.execute("""
                SELECT DISTINCT ds.name
                FROM largo_plazo_dimensiones d1
                JOIN largo_plazo_dimensiones d2 ON d1.dimension_id = d2.dimension_id
                JOIN dimensiones_semanticas ds ON d1.dimension_id = ds.id
                WHERE d1.concepto = ? AND d2.concepto = ?
            """, (c1, c2))
            dims_compartidas = [r[0] for r in cursor.fetchall()]

            concepto_insight = f"insight_dmn_{c1}_{c2}"
            
            # Verificar si ya existe este insight
            cursor.execute("SELECT id FROM largo_plazo WHERE concepto = ?", (concepto_insight,))
            if cursor.fetchone():
                return None

            contenido_insight = (
                f"Insight Autónomo DMN (Curiosidad Espontánea): Conexión sintética latente descubierta en reposo "
                f"entre '{c1}' (valencia={val1:.2f}) y '{c2}' (valencia={val2:.2f}). "
                f"Dimensiones compartidas: {', '.join(dims_compartidas) if dims_compartidas else 'Topología estructural'}."
            )
            sinonimos = f"insight dmn,curiosidad espontanea,{c1},{c2}"
            cat_id = 1  # General / Insight

            # Insertar Insight en largo_plazo con peso moderado (0.50) y valencia somática 0.85
            cursor.execute("""
                INSERT INTO largo_plazo (concepto, categoria, contenido, peso_sinaptico, estado, sinonimos, creado_en, ultimo_acceso, valencia_somatica)
                VALUES (?, ?, ?, 0.50, 'activo', ?, ?, ?, 0.85)
            """, (concepto_insight, cat_id, contenido_insight, sinonimos, time.time(), time.time()))

            # Crear sinapsis latente asociativa entre N1 y N2 con todas las columnas requeridas
            cursor.execute("""
                INSERT OR REPLACE INTO sinapsis_latentes (origen, destino, peso_atenuado, saltos, calculado_en, pmi_score, tiene_dim_comun)
                VALUES (?, ?, 0.75, 2, ?, 0.5, ?)
            """, (c1, c2, time.time(), 1 if dims_compartidas else 0))

            if DMN_SINTESIS_ACTIVA and dims_compartidas:
                try:
                    cursor.execute(
                        "INSERT INTO sinapsis (origen, destino, peso, tipo, creado_en) "
                        "VALUES (?, ?, ?, 'dmn_synthesized', ?) "
                        "ON CONFLICT(origen, destino) DO NOTHING",
                        (c1, c2, DMN_SINTESIS_PESO, time.time()),
                    )
                except Exception:
                    pass

            conn.commit()

            # SDM v19.0: Indexar vector del insight para recuperación por similitud estructural
            try:
                from core.sdm import indexar_nodo_sdm
                indexar_nodo_sdm(self.cerebro, concepto_insight)
            except Exception:
                pass

            # v29: reconstrucción batch del índice ADN durante sueño. Esta es la única
            # ruta que agrupa el corpus, recalcula centroides y materializa vecinos.
            try:
                necesita_recalculo = getattr(self.cerebro, "_adn_pendiente_recalculo", False)
                indice_no_listo = not getattr(getattr(self.cerebro, "adn_engine", None), "indice_listo", False)
                if necesita_recalculo or indice_no_listo:
                    from core.adn_conceptual import ADNConceptualEngine
                    estado_adn = ADNConceptualEngine.reconstruir_indice_nocturno(str(self.db_path))
                    if estado_adn.get("estado") == "ok":
                        # Recargar solo los artefactos persistidos, sin clustering en caliente.
                        self.cerebro.adn_engine = ADNConceptualEngine(
                            db_path=str(self.db_path),
                            indices=getattr(self.cerebro, "_ppmi_index", None),
                        )
                        from core.neocortex_teleologico import NeocortexTeleologico
                        self.cerebro.neocortex = NeocortexTeleologico(str(self.db_path))
                        self.cerebro._adn_pendiente_recalculo = False
                    logger.info("DMN sueño: índice ADN v29 procesado con estado=%s", estado_adn.get("estado"))
            except Exception as e:
                logger.warning(f"Error en reconstrucción ADN nocturna DMN: {e}")

            self.ideas_generadas_sesion += 1
            self.ultima_idea = {
                "concepto": concepto_insight,
                "nodo_a": c1,
                "nodo_b": c2,
                "coincidencia_dimensional": dims_compartidas,
                "valencia_somatica": 0.85,
                "peso_inicial": 0.50,
                "timestamp": time.time(),
                "contenido": contenido_insight
            }

            logger.info(f"💡 DMN Muestreo Resonante generó Insight autónomo: {concepto_insight}")
            return self.ultima_idea

        finally:
            if auto_close:
                conn.close()

    def obtener_estado(self) -> dict:
        """Devuelve el payload JSON estructurado y enriquecido para biorag_estado_dmn."""
        tiempo_inactivo = time.time() - self.ultimo_acceso_usuario
        return {
            "estado": "idle" if tiempo_inactivo >= self.idle_seconds else "active_user",
            "activo_hilo": self.activo,
            "segundos_inactividad": round(tiempo_inactivo, 1),
            "umbral_idle_segundos": self.idle_seconds,
            "ideas_generadas_sesion": self.ideas_generadas_sesion,
            "max_ideas_por_reposo": self.max_ideas_por_reposo,
            "ultima_idea": self.ultima_idea
        }


# ---------------------------------------------------------------------------
# F4: Termodinámica Cognitiva (Plan Maestro, INVENCIÓN 4). F = E - T·S.
# E = tensión de pares co-activos sin arista (mala). S = 1 - densidad del
# grafo cortical (dispersión estructural: 1=vacío, 0=completo). T = temp.
# Crear arista: ΔE<0 vs -T·ΔS>0 → se crea si la tensión supera T×orden.
# Podar: ΔE>=0 vs -T·ΔS<0 → se poda si T×dispersión supera la tensión.
# T alta=explorar, T baja=sueño.
# POR QUÉ densidad y no Shannon-de-grados: remover arista casi siempre
# REDUCE H(grados) (concentra la distribución) → ΔF_remover>=0 siempre y
# la poda quedaba muerta por construcción. La densidad es monótona en |E|
# y hace funcionar síntesis y poda en la dirección pedida.
# 100% local, determinista, stdlib. Cero GPU/embeddings/API.
# ---------------------------------------------------------------------------

TERMODINAMICA_DMN = os.environ.get("BIORAG_TERMODINAMICA_DMN", "0").lower() in ("1", "true", "yes")
TERMODINAMICA_TEMP = float(os.environ.get("BIORAG_TERMODINAMICA_TEMP", "1.0"))
TERMODINAMICA_SEMILLAS = int(os.environ.get("BIORAG_TERMODINAMICA_SEMILLAS", "40"))
TERMODINAMICA_POOL_X = 10  # pool candidatos = max_n * 10 cuando ON


def _contexto_corteza(cerebro, n_semillas=40):
    """Top-N activos determinista + pesos, tokens, dims, aristas, grados."""
    cur = cerebro.cursor
    n = max(2, int(n_semillas))
    cur.execute(
        "SELECT concepto, COALESCE(peso_sinaptico, 0.0), COALESCE(contenido, '') "
        "FROM largo_plazo WHERE estado = 'activo' "
        "ORDER BY peso_sinaptico DESC, concepto ASC LIMIT ?",
        (n,),
    )
    rows = cur.fetchall()
    seeds = [r[0] for r in rows]
    peso = {r[0]: float(r[1] or 0.0) for r in rows}
    toks = {r[0]: set(re.findall(r"\w{4,}", (r[2] or "").lower())) for r in rows}
    ndims = {}
    if seeds:
        ph = ",".join("?" * len(seeds))
        try:
            cur.execute(
                "SELECT d1.concepto, d2.concepto, COUNT(*) FROM largo_plazo_dimensiones d1 "
                "JOIN largo_plazo_dimensiones d2 ON d1.dimension_id = d2.dimension_id "
                "AND d1.concepto < d2.concepto "
                f"WHERE d1.concepto IN ({ph}) AND d2.concepto IN ({ph}) "
                "GROUP BY d1.concepto, d2.concepto",
                seeds + seeds,
            )
            for a, b, k in cur.fetchall():
                if a in peso and b in peso:
                    ndims[(a, b)] = int(k)
        except Exception:
            pass
    aristas = set()
    grados = {s: 0 for s in seeds}
    if seeds:
        ph = ",".join("?" * len(seeds))
        try:
            cur.execute(
                f"SELECT origen, destino FROM sinapsis WHERE origen IN ({ph}) AND destino IN ({ph})",
                seeds + seeds,
            )
            for a, b in cur.fetchall():
                if a == b or a not in peso or b not in peso:
                    continue
                key = (a, b) if a < b else (b, a)
                if key not in aristas:
                    aristas.add(key)
                    grados[a] += 1
                    grados[b] += 1
        except Exception:
            pass
    return {"seeds": seeds, "peso": peso, "toks": toks, "ndims": ndims,
            "aristas": aristas, "grados": grados}


def _afinidad_par(ctx, a, b):
    """n_dims + 0.5*min(shared_toks,4). Independiente de aristas."""
    key = (a, b) if a < b else (b, a)
    nd = float(ctx["ndims"].get(key, 0))
    nt = min(len(ctx["toks"].get(a, set()) & ctx["toks"].get(b, set())), 4)
    return nd + 0.5 * nt


def _es_candidato(ctx, a, b):
    """Mismo criterio E10: >=1 dim compartida o >=2 tokens compartidos."""
    key = (a, b) if a < b else (b, a)
    if ctx["ndims"].get(key, 0) >= 1:
        return True
    return len(ctx["toks"].get(a, set()) & ctx["toks"].get(b, set())) >= 2


def _tension_par(ctx, a, b):
    """w_a*w_b*afinidad si par candidato SIN arista; 0.0 si no."""
    key = (a, b) if a < b else (b, a)
    if key in ctx["aristas"]:
        return 0.0
    if not _es_candidato(ctx, a, b):
        return 0.0
    return float(ctx["peso"].get(a, 0.0)) * float(ctx["peso"].get(b, 0.0)) * _afinidad_par(ctx, a, b)


def _entropia_densidad(n, n_aristas):
    """1 - densidad no dirigida, [0,1]. Determinista, O(1)."""
    if n < 2:
        return 0.0
    dens = 2.0 * max(0, n_aristas) / (n * (n - 1))
    return max(0.0, min(1.0, 1.0 - dens))


def calcular_energia_libre_corteza(cerebro, temperatura=1.0, n_semillas=40):
    """F4: F = E - T·S sobre la corteza (top-N activos). Dict determinista."""
    ctx = _contexto_corteza(cerebro, n_semillas)
    seeds = ctx["seeds"]
    e = 0.0
    for i, a in enumerate(seeds):
        for b in seeds[i + 1:]:
            e += _tension_par(ctx, a, b)
    s = _entropia_densidad(len(seeds), len(ctx["aristas"]))
    t = float(temperatura)
    aislados = sum(1 for x in seeds if ctx["grados"].get(x, 0) == 0)
    return {"F": e - t * s, "E": e, "S": s, "T": t, "n": len(seeds),
            "aristas": len(ctx["aristas"]), "aislados": aislados}


def _delta_s_grados(ctx, a, b, agregar=True):
    n = len(ctx["seeds"])
    na = len(ctx["aristas"])
    na1 = na + 1 if agregar else max(0, na - 1)
    return _entropia_densidad(n, na1) - _entropia_densidad(n, na)


def delta_f_agregar(ctx, a, b, temperatura=1.0):
    """ΔF al crear arista a-b. +inf si ya existe (no re-elegir)."""
    key = (a, b) if a < b else (b, a)
    if key in ctx["aristas"]:
        return float("inf")
    de = -_tension_par(ctx, a, b)
    ds = _delta_s_grados(ctx, a, b, agregar=True)
    return de - float(temperatura) * ds


def delta_f_remover(ctx, a, b, temperatura=1.0):
    """ΔF al borrar arista a-b. 0.0 si no existe o fuera de corteza."""
    key = (a, b) if a < b else (b, a)
    if key not in ctx["aristas"]:
        return 0.0
    if _es_candidato(ctx, a, b):
        de = float(ctx["peso"].get(a, 0.0)) * float(ctx["peso"].get(b, 0.0)) * _afinidad_par(ctx, a, b)
    else:
        de = 0.0
    ds = _delta_s_grados(ctx, a, b, agregar=False)
    return de - float(temperatura) * ds


def rankear_pares_por_delta_f(cerebro, pares, temperatura=1.0, n_semillas=40, modo="agregar"):
    """F4: [(a,b,ΔF)] ascendente determinista. modo agregar|remover."""
    ctx = _contexto_corteza(cerebro, n_semillas)
    fn = delta_f_agregar if modo == "agregar" else delta_f_remover
    out = []
    for p in pares:
        a, b = p[0], p[1]
        try:
            df = float(fn(ctx, a, b, temperatura))
        except Exception:
            df = float("inf")
        out.append((a, b, df))
    out.sort(key=lambda x: (x[2], str(x[0]), str(x[1])))
    return out


def podar_ltd_guiado(cerebro, temperatura=None, peso_umbral=0.05):
    """F4: borra peso<umbral EXCEPTO aristas cuya remoción aumenta F (ΔF>0).

    Sin commit (el caller commitea, igual que el DELETE legacy). Devuelve n.
    """
    if temperatura is None:
        temperatura = TERMODINAMICA_TEMP
    cur = cerebro.cursor
    cur.execute("SELECT origen, destino FROM sinapsis WHERE peso < ?", (float(peso_umbral),))
    cands = sorted({(r[0], r[1]) for r in cur.fetchall() if r[0] and r[1]})
    if not cands:
        return 0
    ctx = _contexto_corteza(cerebro, TERMODINAMICA_SEMILLAS)
    borrar = []
    for a, b in cands:
        try:
            df = delta_f_remover(ctx, a, b, temperatura)
        except Exception:
            df = 0.0
        if df <= 0.0:
            borrar.append((a, b))
    for a, b in borrar:
        cur.execute("DELETE FROM sinapsis WHERE origen = ? AND destino = ?", (a, b))
    return len(borrar)
