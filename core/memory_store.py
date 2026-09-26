import os
import sqlite3
import time
import re
import sys
import math
import json
import logging
import numpy as np
from collections import deque

logger = logging.getLogger("BioRAG.MemoryStore")

from core.stemmer_es import _quitar_acentos

# Auto-cargar .env.local al importar (antes de leer cualquier variable de entorno)
from config import _load_env_local

try:
    from core.calibracion import (zscore_por_query, fusion_rrf, FusionLogistica,
                                   CalibradorPlatt, calibracion_isotonica,
                                   UmbralConforme, mmr)
except ImportError:
    zscore_por_query = fusion_rrf = FusionLogistica = CalibradorPlatt = None
    calibracion_isotonica = UmbralConforme = mmr = None
_load_env_local()

# Pre-cargar WordNet al importar para evitar latencia de 3s en primera consulta semántica
try:
    from core.clasificador_wordnet import obtener_lexnames_query
    obtener_lexnames_query("test")  # Trigger NLTK/WordNet lazy load
except Exception:
    pass  # WordNet opcional, ignorar si falla

# =============================================================================
# Constantes, flags de configuración y re-exports hacia core.memory.constants
# =============================================================================

from core.memory import constants
from core.memory.constants import (
    CANDIDATOS_SIMILITUD, MAX_SALTOS_CADENA, LIMITE_DEFAULT, UMBRAL_JACCARD,
    RAFTAGA_ACTIVA, THRESHOLD_RAFTAGA, LIMITE_RAFTAGA, LIMITE_EVOCACION,
    JSD_WEIGHT, JSD_ADAPTATIVO, JSD_ADAPT_BASE, JSD_ADAPT_LARGO, JSD_ADAPT_CORTO, JSD_ADAPT_NT,
    DMN_SINTESIS_ACTIVA, DMN_SINTESIS_MAX, DMN_SINTESIS_PESO,
    EPISODIO_TEMPORAL_PESO, EPISODIO_TEMPORAL_ACTIVO, EPISODIO_VENTANA_HORAS, EPISODIO_LIMITE, EPISODIO_BUCKET_SEG,
    ANALOGIA_PESO, ANALOGIA_DETECTAR,
    CAMPO_POTENCIAL_PESO, CAMPO_SIGMA, CAMPO_K,
    EPISTEMICO_METADATA,
    MULTIHOP_EXPANSION, MULTIHOP_MAX_TOTAL, MULTIHOP_PRIOR,
    BAYESIAN_BM25, BAYESIAN_BM25_ALPHA,
    RERANKING_JACCARD_ACTIVO, RERANKING_JACCARD_ALPHA, RERANKING_JACCARD_GATE, RERANKING_JACCARD_TOPK, RERANKING_JACCARD_WINDOW,
    SDM_FALLBACK_ACTIVO, SDM_FALLBACK_K,
    QCR_IDF_ACTIVO, QCR_IDF_UMBRAL,
    QCR_TYPO_ACTIVA, DIM_RESONANCIA, DIM_RESONANCIA_K, DIM_ESCAPE, DIM_ESCAPE_T, QCR_TYPO_PISO, QCR_TYPO_DIST,
    NCD_PESO, NCD_ZLIB_LEVEL,
    GABA_ACTIVO,
    PPMI_VECTOR_WEIGHT,
    ADN_RANKING_ENABLED, ADN_PESO, ADN_MAX_EXPANSION, ADN_UMBRAL_ASOCIACION,
    _qcr_levenshtein, _qcr_todos_cercanos, normalizar_sustantivos_clave,
)
from core.memory import comms
from core.memory import telemetry
from core.memory import synapses
from core.memory import episodes
from core.memory import quarantine
from core.memory import ingest
from core.memory import dmn
from core.memory import consolidation
from core.memory import scoring
from core.memory import umbral
from core.memory import context
from core.memory import catalog_methods
from core.memory import adn
from core.memory import rafaga
from core.memory import schema
from core.memory import recall
from core.memory import search

# =============================================================================

class SQLiteMemoryBioRAG:
    """
    Motor de Almacenamiento Cognitivo BioRAG basado en SQLite.
    Implementa almacenamiento biomimético con persistencia de doble capa (Corto/Largo plazo),
    plasticidad sináptica (LTP/LTD), indexación por B-Tree ultrarrápida,
    búsqueda de familiaridad difusa por coincidencia de Jaccard y propagación de activación (Grafo).
    """

    def __init__(self, db_path=None):
        if db_path:
            self.db_path = db_path
        else:
            from core.paths import resolve_db_path
            self.db_path = resolve_db_path()
        if self.db_path != ":memory:":
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        # Conectar a SQLite
        # check_same_thread=False: MCP/WAL reutiliza la instancia entre tools.
        self.conn = sqlite3.connect(self.db_path, timeout=60, check_same_thread=False)
        self._persistente = False
        try:
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA synchronous=NORMAL")
            self.conn.execute("PRAGMA busy_timeout=30000")
            self.conn.execute("PRAGMA cache_size=-64000")
            self.conn.execute("PRAGMA mmap_size=268435456")
        except sqlite3.OperationalError:
            pass
        self.cursor = self.conn.cursor()
        # Función personalizada: word boundary check del lado de la DB
        def palabra_completa(token, texto):
            if not token or not texto:
                return 0
            token_norm = token.lower().replace('_', ' ').replace('-', ' ')
            texto_norm = texto.lower().replace('_', ' ').replace('-', ' ')
            return 1 if re.search(r'\b' + re.escape(token_norm) + r'\b', texto_norm) else 0
        self.conn.create_function("PALABRA_COMPLETA", 2, palabra_completa)

        # Función personalizada: prefix word boundary check del lado de la DB
        def palabra_prefijo(token, texto):
            if not token or not texto:
                return 0
            token_norm = token.lower().replace('_', ' ').replace('-', ' ')
            texto_norm = texto.lower().replace('_', ' ').replace('-', ' ')
            return 1 if re.search(r'\b' + re.escape(token_norm), texto_norm) else 0
        self.conn.create_function("PALABRA_PREFIJO", 2, palabra_prefijo)
        self._cat_cache = {}
        self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='largo_plazo'")
        if not self.cursor.fetchone():
            self._crear_estructura_cerebral()
        self._crear_tablas_nuevas_si_faltan()
        self.conn.execute("PRAGMA foreign_keys = ON")
        # Trazaabilidad: datos de la última búsqueda para mcp_server.py
        self.last_todos = []
        self.last_origen_scores = {}
        # Signal #14 (v29): metadatos del contrato de degradación asociativa.
        # Con flag OFF queda con valores vacíos por defecto; con flag ON, el
        # último enriquecimiento ADN deja aquí su estado epistémico (Política A).
        self.last_estado_epistemico = {
            "estado": "no_evaluado",
            "confianza_epistemica": 0.0,
            "indice_adn_listo": False,
            "tipo_relacion_por_concepto": {},
            "genes_compartidos_por_concepto": {},
            "candidatos_adn_consultados": 0,
        }
        self.last_parent_map = {}  # parent pointers from last spreading activation
        # Buffer circular de memoria de trabajo (v19.0 Context Window)
        self._context_window = deque(maxlen=10)
        self.dmn = None
        self._dmn_sintesis_hecha = False
        if constants.DMN_SINTESIS_ACTIVA:
            try:
                from core.dmn_engine import sintetizar_sinapsis_dmn
                sintetizar_sinapsis_dmn(self, max_n=constants.DMN_SINTESIS_MAX)
                self._dmn_sintesis_hecha = True
            except Exception:
                pass
        # v22.1: Cache for thematic scores (precomputed once)
        self._thematic_scores_cache = None
        self._thematic_profiles_cache = None
        self._thematic_idf_cache = None
        # Signal #13 (v26.0): Índice de vectores PPMI+SVD (lazy-loaded, ~320KB en RAM)
        # Solo se carga si BIORAG_PPMI_WEIGHT > 0 para cero overhead cuando está OFF
        self._ppmi_index = None
        if constants.PPMI_VECTOR_WEIGHT > 0.0:
            try:
                from core.ppmi_hybrid_search import IndicesBioRAG
                self._ppmi_index = IndicesBioRAG(str(self.db_path))
            except Exception:
                pass  # Silencioso: si la tabla no existe aún, se crea en el próximo sueño

        # v26.1: Neocórtex de Sangre y ADN Conceptual (solo si PPMI está activo:
        # el ADN se construye sobre vectores PPMI/SVD, sin ellos no tiene señales)
        self.neocortex = None
        self.adn_engine = None
        if self._ppmi_index is not None:
            try:
                from core.neocortex_teleologico import NeocortexTeleologico
                from core.adn_conceptual import ADNConceptualEngine
                self.neocortex = NeocortexTeleologico(str(self.db_path))
                self.adn_engine = ADNConceptualEngine(db_path=str(self.db_path), indices=self._ppmi_index)
                # El índice ADN v29 se carga desde artefactos persistidos; nunca se recalcula aquí.
                self._adn_pendiente_recalculo = False
            except Exception as e:
                logger.warning(f"No se pudo inicializar el Neocórtex de Sangre: {e}")

        # v28.1: Componentes de calibración y decisión estadística (FP controlado)
        self._platt_calibrador = None
        self._umbral_conforme = None
        self._fusion_logistica = None
        self._calibracion_entrenada = False
        self._calibracion_meta = None

        # v28.1: Cargar calibración persistida si existe (rápida, sin búsquedas).
        # Esto le da al path caliente el umbral/Platt ya calibrados contra el
        # corpus del momento en que se persistieron. Si el corpus creció o se
        # redujo después, `calibrar_y_persistir()` lo detecta por n_nodos y
        # recalcula la garantía.
        try:
            if getattr(self, 'cursor', None) is not None:
                self._cargar_calibracion_persistida()
        except Exception as _e_cal:
            logger.debug(f"Calibración persistida no cargada: {_e_cal}")

    def notificar_actividad_usuario(self):
        return dmn.notificar_actividad_usuario(self)

    def iniciar_dmn(self, idle_seconds=300):
        return dmn.iniciar_dmn(self, idle_seconds=idle_seconds)

    def detener_dmn(self):
        return dmn.detener_dmn(self)

    def registrar_acceso_contexto(self, concepto: str):
        return dmn.registrar_acceso_contexto(self, concepto=concepto)

    def obtener_bonus_contexto(self, concepto: str) -> float:
        return dmn.obtener_bonus_contexto(self, concepto=concepto)


    def _resolver_categoria_id(self, nombre):
        return catalog_methods._resolver_categoria_id(self, nombre)

    def listar_categorias(self):
        return catalog_methods.listar_categorias(self)

    def _resolver_dimension_ids(self, tipo_nombre, valores_str):
        return catalog_methods._resolver_dimension_ids(self, tipo_nombre, valores_str)

    def _obtener_arbol_dimensiones(self):
        return catalog_methods._obtener_arbol_dimensiones(self)

    def sync_status(self):
        return catalog_methods.sync_status(self)

    def sync_marcado(self, categoria_ids):
        return catalog_methods.sync_marcado(self, categoria_ids)

    def sync_limpiar(self):
        return catalog_methods.sync_limpiar(self)


    def _cargar_firmas_adn(self):
        return adn._cargar_firmas_adn(self)

    def _persistir_firma_adn(self, concepto: str, firma: dict):
        return adn._persistir_firma_adn(self, concepto=concepto, firma=firma)


    def _crear_estructura_cerebral(self):
        return schema._crear_estructura_cerebral(self)

    def _crear_tabla_data(self):
        return schema._crear_tabla_data(self)


    # =========================================================================
    # TECNOLOGÍA COGNITIVA: Ley de Potencia de Práctica de ACT-R (Anderson & Lebiere, 1998)
    # Modelo formal de activación de nivel base (Base-Level Activation) y retención biológica:
    # B_i = ln( \sum_{k=1}^n t_k^{-d} ), con d = 0.5.
    # Modula la tasa de olvido pasivo (LTD) en el ciclo de consolidación de sueño.
    # =========================================================================

    def _registrar_acceso_nodo(self, concepto: str, ts: float = None):
        return dmn._registrar_acceso_nodo(self, concepto=concepto, ts=ts)


    def _calcular_base_level_actr(self, concepto: str, ahora: float = None):
        return consolidation._calcular_base_level_actr(self, concepto=concepto, ahora=ahora)


    def _crear_tablas_nuevas_si_faltan(self):
        return schema._crear_tablas_nuevas_si_faltan(self)

    def _asegurar_catalogo_dimensiones(self):
        return schema._asegurar_catalogo_dimensiones(self)

    def _idf_tokens_qcr(self, tokens):
        return scoring._idf_tokens_qcr(self, tokens=tokens)

    def _calcular_jaccard(self, str1, str2):
        return scoring._calcular_jaccard(self, str1=str1, str2=str2)


    def _buscar_en_contenido(self, query, solo_activos=True):
        return recall._buscar_en_contenido(self, query=query, solo_activos=solo_activos)

    def _buscar_todos_en_contenido(self, query, solo_activos=True):
        return recall._buscar_todos_en_contenido(self, query=query, solo_activos=solo_activos)

    def buscar_recuerdo_microsegundos(self, concepto):
        return recall.buscar_recuerdo_microsegundos(self, concepto=concepto)

    def buscar_todos_recuerdos(self, concepto):
        return recall.buscar_todos_recuerdos(self, concepto=concepto)

    def buscar_por_predicados(self, sujeto=None, accion=None, objeto=None, contexto=None, limite=10):
        return recall.buscar_por_predicados(self, sujeto=sujeto, accion=accion, objeto=objeto, contexto=contexto, limite=limite)

    def _fallback_busqueda_predicados(self, frase, limite=10):
        return recall._fallback_busqueda_predicados(self, frase=frase, limite=limite)

    def buscar_por_tokens(self, tokens, modo="relaxed", profundidad="activos", limite=3, pagina=1):
        return recall.buscar_por_tokens(self, tokens=tokens, modo=modo, profundidad=profundidad, limite=limite, pagina=pagina)

    def buscar_recuerdo_profundo(self, concepto):
        return recall.buscar_recuerdo_profundo(self, concepto=concepto)


    def percibir_corto_plazo(self, concepto, contenido, sinonimos="", categoria="General", dimensiones=None, predicados=None, valencia_somatica=0.0, sustantivos_clave=""):
        return ingest.percibir_corto_plazo(
            self,
            concepto=concepto,
            contenido=contenido,
            sinonimos=sinonimos,
            categoria=categoria,
            dimensiones=dimensiones,
            predicados=predicados,
            valencia_somatica=valencia_somatica,
            sustantivos_clave=sustantivos_clave,
        )

    def consolidar_concepto(self, concepto):
        return ingest.consolidar_concepto(self, concepto=concepto)


    def _auto_generar_co_ocurrencia(self, recuerdos_sesion):
        return consolidation._auto_generar_co_ocurrencia(self, recuerdos_sesion=recuerdos_sesion)

    def _clasificar_nodo_wordnet(self, concepto, contenido, sinonimos=""):
        return consolidation._clasificar_nodo_wordnet(self, concepto=concepto, contenido=contenido, sinonimos=sinonimos)

    def _crear_tabla_historial_si_falta(self):
        return telemetry._crear_tabla_historial_si_falta(self)

    def ciclo_sueno_consolidacion(self):
        return consolidation.ciclo_sueno_consolidacion(self)


    def aplicar_refuerzo_dopaminergico(self, concepto: str, exito: bool, motivo: str = None) -> bool:
        return synapses.aplicar_refuerzo_dopaminergico(self, concepto, exito, motivo)

    def _reconstruir_camino(self, destino):
        return synapses._reconstruir_camino(self, destino)

    def establecer_asociacion(self, concepto_a, concepto_b):
        return synapses.establecer_asociacion(self, concepto_a, concepto_b)

    # ─── CANAL DE COMUNICACION INTER-AGENTE ──────────────────────────────

    def _crear_tabla_comunicaciones(self):
        return comms._crear_tabla_comunicaciones(self)

    def enviar_comunicado(self, origen, destino, contenido):
        return comms.enviar_comunicado(self, origen, destino, contenido)

    def leer_comunicados(self, destino=None, solo_no_leidos=False, ultimos=10, agente=None):
        return comms.leer_comunicados(self, destino=destino, solo_no_leidos=solo_no_leidos, ultimos=ultimos, agente=agente)

    def marcar_como_leido(self, ids, agente=None):
        return comms.marcar_como_leido(self, ids, agente=agente)

    # ─── FULL-TEXT SEARCH (FTS5) ─────────────────────────────────

    def _crear_tabla_fts(self):
        return schema._crear_tabla_fts(self)

    def _poblar_fts(self):
        return schema._poblar_fts(self)

    def _poblar_fts_unicode(self):
        return schema._poblar_fts_unicode(self)


    def _crear_tabla_metricas(self):
        return dmn._crear_tabla_metricas(self)


    def _agregar_prefix_wildcards(self, query):
        return scoring._agregar_prefix_wildcards(self, query=query)

    def _pesar_tokens_query(self, frase):
        return scoring._pesar_tokens_query(self, frase=frase)


    def _evocacion_por_cadena(self, semillas, max_saltos=None, limite=None):
        return synapses._evocacion_por_cadena(self, semillas, max_saltos=max_saltos, limite=limite)

    @staticmethod
    def _ncd_sim(a, b, level=None):
        return scoring._ncd_sim(a=a, b=b, level=level)

    def _ncd_sims_pool(self, query, filas):
        return scoring._ncd_sims_pool(self, query=query, filas=filas)

    @staticmethod
    def _jsd_weight_adaptativo(query, n_tokens=None):
        return scoring._jsd_weight_adaptativo(query=query, n_tokens=n_tokens)

    def _ts_nodo(self, concepto):
        return episodes._ts_nodo(self, concepto)

    def _expandir_episodio_temporal(self, nodo_ancla, ventana_horas=None, limite_episodio=None):
        return episodes._expandir_episodio_temporal(self, nodo_ancla, ventana_horas=ventana_horas, limite_episodio=limite_episodio)

    def _afinidad_temporal_pool(self, conceptos):
        return episodes._afinidad_temporal_pool(self, conceptos)

    def _analogia_scores_pool(self, v_target, pool):
        return scoring._analogia_scores_pool(self, v_target=v_target, pool=pool)


    def _generar_variaciones(self, query, historial_fallos=None):
        return scoring._generar_variaciones(self, query=query, historial_fallos=historial_fallos)

    @staticmethod
    def _calcular_jsd(query_text: str, node_text: str) -> float:
        return scoring._calcular_jsd(query_text=query_text, node_text=node_text)

    @staticmethod
    def _calcular_bm25_bayesiano(raw_scores: dict, alpha: float = 1.0) -> dict:
        return scoring._calcular_bm25_bayesiano(raw_scores=raw_scores, alpha=alpha)

    def _calcular_score_hibrido(self, bm25_norm=0.0, dim_score=0.0,
                                peso_sinaptico=0.0, concepto_ratio=0.0,
                                sinonimos_ratio=0.0, score_latente=0.0,
                                score_cadena=0.0, temporal=0.0,
                                asoc_count=0, match_exacto=False,
                                grupo_score=0.0, tematico_score=0.0,
                                jsd_score: float = 0.0,
                                jsd_weight: float = 0.0,
                                pred_score: float = 0.0,
                                ppmi_score: float = 0.0,
                                hub_match: float = 0.0,
                                ncd_score: float = 0.0,
                                episodio_score: float = 0.0,
                                analogia_score: float = 0.0,
                                campo_score: float = 0.0):
        return scoring._calcular_score_hibrido(
            self,
            bm25_norm=bm25_norm,
            dim_score=dim_score,
            peso_sinaptico=peso_sinaptico,
            concepto_ratio=concepto_ratio,
            sinonimos_ratio=sinonimos_ratio,
            score_latente=score_latente,
            score_cadena=score_cadena,
            temporal=temporal,
            asoc_count=asoc_count,
            match_exacto=match_exacto,
            grupo_score=grupo_score,
            tematico_score=tematico_score,
            jsd_score=jsd_score,
            jsd_weight=jsd_weight,
            pred_score=pred_score,
            ppmi_score=ppmi_score,
            hub_match=hub_match,
            ncd_score=ncd_score,
            episodio_score=episodio_score,
            analogia_score=analogia_score,
            campo_score=campo_score,
        )


    # =============================================================================
    # v28.1: Calibración de probabilidad y decisión con garantía (FP controlado)
    # =============================================================================

    def _preparar_datos_calibracion(self, n_calibracion: int = 500) -> tuple:
        return umbral._preparar_datos_calibracion(self, n_calibracion=n_calibracion)

    def entrenar_calibracion(self, n_calibracion: int = 500, metodo: str = "platt") -> bool:
        return umbral.entrenar_calibracion(self, n_calibracion=n_calibracion, metodo=metodo)

    def calibrar_umbral_conforme(self, alpha: float = None, n_negativos: int = 100) -> float:
        return umbral.calibrar_umbral_conforme(self, alpha=alpha, n_negativos=n_negativos)

    def _score_con_calibracion(self, score_bruto: float) -> float:
        return umbral._score_con_calibracion(self, score_bruto=score_bruto)

    UMBRAL_COLD_START = 0.65

    def _debe_responder(self, score: float) -> bool:
        return umbral._debe_responder(self, score=score)

    def buscar_con_calibracion(self, query: str, limite: int = 10,
                               usar_calibracion: bool = True) -> list:
        return umbral.buscar_con_calibracion(self, query=query, limite=limite, usar_calibracion=usar_calibracion)

    # =============================================================================
    # v28.1: Calibración dinámica persistente — garantía FP independiente del corpus
    # =============================================================================

    def _contar_nodos_corpus(self) -> int:
        return umbral._contar_nodos_corpus(self)

    def _cargar_calibracion_persistida(self) -> bool:
        return umbral._cargar_calibracion_persistida(self)

    def _persistir_calibracion(self, n_positivos: int, metodo: str = "conforme") -> None:
        return umbral._persistir_calibracion(self, n_positivos=n_positivos, metodo=metodo)

    def calibrar_y_persistir(self, alpha: float = None, n_negativos: int = 40,
                             n_positivos_max: int = 300,
                             recalcular_si_drift: bool = True,
                             force: bool = False) -> dict:
        return umbral.calibrar_y_persistir(
            self,
            alpha=alpha,
            n_negativos=n_negativos,
            n_positivos_max=n_positivos_max,
            recalcular_si_drift=recalcular_si_drift,
            force=force,
        )

    def nivel_certeza(self, score: float) -> str:
        return umbral.nivel_certeza(self, score=score)

    def confianza_calibrada(self, score: float) -> float:
        return umbral.confianza_calibrada(self, score=score)

    def expandir_contexto_vecinos(self, pagina_resultados, depth, profundidad="activos", preview_chars=None):
        return synapses.expandir_contexto_vecinos(self, pagina_resultados, depth, profundidad=profundidad, preview_chars=preview_chars)

    def _expandir_contexto_bfs(self, pagina_resultados, depth, profundidad="activos", preview_chars=None):
        return synapses._expandir_contexto_bfs(self, pagina_resultados, depth, profundidad=profundidad, preview_chars=preview_chars)

    def _rerank_jaccard_protect_r0(self, resultados, frase_limpia, preview_chars=1500):
        return scoring._rerank_jaccard_protect_r0(self, resultados=resultados, frase_limpia=frase_limpia, preview_chars=preview_chars)


    def obtener_asociaciones_enriquecidas(self, conceptos_top, top_vecinos=5, peso_min=0.50):
        return synapses.obtener_asociaciones_enriquecidas(self, conceptos_top, top_vecinos=top_vecinos, peso_min=peso_min)

    # OPT-NUEVA-5: constates de evaluacion epistemica (Ce). Umbrales = HIPOTESIS
    # inicial documentada (sin set calibrado); ranking intacto por construccion.
    EPISTEMICO_TOP_K = 5
    EPISTEMICO_UMBRAL_CONOCIDO = 0.55
    EPISTEMICO_UMBRAL_INCERTIDUMBRE = 0.30
    EPISTEMICO_VACIOS_CAP = 200

    def _epistemico_coherencia_dimensional(self, top_conceptos):
        return context._epistemico_coherencia_dimensional(self, top_conceptos)

    def _epistemico_evaluar(self, pagina_resultados):
        return context._epistemico_evaluar(self, pagina_resultados)

    def _epistemico_publicar(self, frase, pagina_resultados, total):
        return context._epistemico_publicar(self, frase, pagina_resultados, total)

    def _epistemico_publicar_sin_consulta(self):
        return context._epistemico_publicar_sin_consulta(self)

    def _epistemico_encolar_vacio(self, frase, ce):
        return context._epistemico_encolar_vacio(self, frase, ce)


    def _multihop_vecinos(self, semillas, excluir, limite):
        return synapses._multihop_vecinos(self, semillas, excluir, limite)

    buscar_por_frase = search.buscar_por_frase


    def obtener_provenance_ultimo_resultado(self) -> dict:
        return telemetry.obtener_provenance_ultimo_resultado(self)

    def _enriquecer_con_adn(self, query, resultados_base, limite=None):
        return adn._enriquecer_con_adn(self, query=query, resultados_base=resultados_base, limite=limite)


    def actualizar_log_busqueda(self, params_json: str):
        return telemetry.actualizar_log_busqueda(self, params_json)

    def validar_rafaga(self, rafaga_palabras):
        return rafaga.validar_rafaga(self, rafaga_palabras=rafaga_palabras)

    def buscar_por_rafaga(self, query, rafaga_palabras, pagina=1, limite=None, dimensiones_ids=None):
        return rafaga.buscar_por_rafaga(
            self,
            query=query,
            rafaga_palabras=rafaga_palabras,
            pagina=pagina,
            limite=limite,
            dimensiones_ids=dimensiones_ids,
        )


    # ─── AUTO-MANTENIMIENTO Y EVICCION ──────────────────────────

    def _benchmark_rendimiento(self):
        return telemetry._benchmark_rendimiento(self)

    def _candidatos_eviccion(self, limite=5):
        return quarantine._candidatos_eviccion(self, limite=limite)

    def _ejecutar_eviccion(self, max_borrar=10):
        return quarantine._ejecutar_eviccion(self, max_borrar=max_borrar)

    def _ultimo_benchmark(self):
        return telemetry._ultimo_benchmark(self)

    def purgar_cuarentena_vencida(self) -> int:
        return quarantine.purgar_cuarentena_vencida(self)

    def mover_a_cuarentena(self, concepto: str, dias_expiracion: int = 30) -> bool:
        return quarantine.mover_a_cuarentena(self, concepto=concepto, dias_expiracion=dias_expiracion)

    def rescatar_de_cuarentena(self, concepto: str) -> bool:
        return quarantine.rescatar_de_cuarentena(self, concepto=concepto)

    def buscar_en_cuarentena(self, frase: str, limite: int = 3):
        return quarantine.buscar_en_cuarentena(self, frase=frase, limite=limite)

    def cerrar_sistema(self):
        """Cierra SQLite. No-op si la instancia es el singleton MCP (_persistente)."""
        if getattr(self, "_persistente", False):
            return
        try:
            self.conn.close()
        except Exception:
            pass
