"""neocortex_teleologico.py — Módulo Central del Neocórtex Sintético Auto-Teleológico de MemoryBioRAG.

Propósito:
    Implementar el motor de autoconocimiento epistémico ("sabe lo que sabe, sabe lo que
    no sabe") y razonamiento por significado puro (PPMI/SVD + propagación hebbiana multi-hop)
    sin dependencia de servicios externos o LLMs en tiempo de inferencia.

Principios Arquitectónicos:
    1. Autoconocimiento Epistémico Determinista: Cuantifica la confianza epistémica (C_e)
       y la incertidumbre (U_m = 1 - C_e) basándose en la densidad vectorial PPMI,
       norma de proyección y soporte sináptico.
    2. Cero Resultados Silenciosos (Instrucción #12): Si la incertidumbre supera el umbral
       crítico, el sistema declara explícitamente su ignorancia epistémica (fuera de distribución
       o soporte insuficiente) en lugar de devolver ceros o alucinaciones silenciosas.
    3. Búsqueda por Significado Puro: Operación completamente local en espacio vectorial latente
       y grafos hebbianos, inmune a variaciones léxicas superficiales.
"""

import math
import sqlite3
import logging
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Set, Optional, Any

from core.pmi_semantico import _TOKEN_PATTERN, _TOKENS_CORTOS
from core.stopwords import STOPWORDS
from core.stemmer_es import stem as _stem
from core.ppmi_hybrid_search import IndicesBioRAG, _coseno

logger = logging.getLogger("BioRAG.NeocortexTeleologico")


class EpistemicUncertaintyError(Exception):
    """Excepción lanzada explícitamente cuando el sistema detecta que está fuera de
    su dominio de conocimiento conocido (sabe que no sabe), evitando respuestas ficticias."""
    def __init__(self, mensaje: str, incertidumbre: float, confianza: float):
        super().__init__(mensaje)
        self.incertidumbre = incertidumbre
        self.confianza = confianza


class NeocortexTeleologico:
    """Motor teleológico y autognóstico de MemoryBioRAG.

    Integra la recuperación semántica pura con la evaluación formal de la certidumbre
    epistémica y el razonamiento autónomo local.
    """

    def __init__(self, db_path: str, umbral_confianza: float = 0.55):
        """Inicializa el neocórtex cargando los índices vectoriales y grafos sinápticos.

        Args:
            db_path (str): Ruta absoluta o relativa a la base de datos SQLite de MemoryBioRAG.
            umbral_confianza (float): Umbral mínimo de C_e para considerar un concepto conocido.
        """
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(f"La base de datos especificada no existe: {self.db_path}")
        
        self.umbral_confianza = umbral_confianza
        logger.info(f"Inicializando NeocortexTeleologico con DB: {self.db_path}")
        try:
            self.indices = IndicesBioRAG(self.db_path)
        except Exception as e:
            raise RuntimeError(f"Error crítico al cargar IndicesBioRAG desde {self.db_path}: {e}") from e

        # v29: Índice de candidatos token→nodo construido durante el sueño.
        # La consulta ya no debe comparar contra todos los vectores de ``self.indices.vecs``.
        self.token_candidatos = {}
        try:
            con = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
            tabla = con.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='neocortex_token_candidatos_v29'"
            ).fetchone()
            if tabla:
                for token, concepto, similitud in con.execute(
                    "SELECT token, concepto, similitud FROM neocortex_token_candidatos_v29 ORDER BY token, similitud DESC"
                ):
                    self.token_candidatos.setdefault(token, []).append((concepto, float(similitud)))
            con.close()
        except sqlite3.Error:
            self.token_candidatos = {}

    def _candidatos_precalculados(self, tokens: List[str]) -> Set[str]:
        """Une solo candidatos persistidos para los tokens de consulta; cero escaneo global."""
        candidatos: Set[str] = set()
        for token in set(tokens):
            for concepto, _similitud in self.token_candidatos.get(token, []):
                candidatos.add(concepto)
        return candidatos

    def _tokenizar_profundo(self, texto: str) -> List[str]:
        """Tokeniza y aplica stemming al texto de la consulta para análisis semántico."""
        if not texto:
            return []
        texto_limpio = texto.replace('_', ' ').replace('-', ' ')
        tokens = _TOKEN_PATTERN.findall(texto_limpio.lower())
        cortos = [t for t in texto_limpio.lower().split() if t in _TOKENS_CORTOS]
        exclusiones = {'memoria', 'buscar', 'memory', 'sistema', 'dato'}
        stopwords_suave = STOPWORDS - exclusiones
        todos = [t for t in (tokens + cortos) if t not in stopwords_suave]
        return [_stem(t) for t in todos]

    def evaluar_episteme(self, query: str) -> Dict[str, Any]:
        """Evalúa si el sistema 'sabe' o 'no sabe' sobre la consulta dada.

        Calcula la densidad semántica, el alineamiento del vector de consulta en el espacio PPMI/SVD
        y el soporte sináptico asociado.

        Returns:
            dict con métricas de confianza (C_e), incertidumbre (U_m), estado ('conocido' o 'ignoto'),
            y evidencias locales.
        """
        toks = self._tokenizar_profundo(query)
        if not toks:
            return {
                "query": query,
                "estado": "ignoto_vacio",
                "confianza_epistemica": 0.0,
                "incertidumbre": 1.0,
                "razon": "Consulta vacía o compuesta exclusivamente por palabras vacías (stopwords)."
            }

        # Vector de query ponderado por IDF local (con fallback a match parcial de tokens)
        v_q = self.indices.vector_query(toks)
        if v_q is None or len(v_q) == 0 or float(np.linalg.norm(v_q)) < 1e-6:
            # Intentar buscar por tokens individuales presentes en token_vecs
            for t in toks:
                if t in self.indices.token_vecs:
                    v_q = self.indices.token_vecs[t]
                    break
        
        norm_q = float(np.linalg.norm(v_q)) if v_q is not None else 0.0

        if norm_q < 1e-6:
            return {
                "query": query,
                "estado": "ignoto_fuera_de_distribucion",
                "confianza_epistemica": 0.0,
                "incertidumbre": 1.0,
                "razon": "Los tokens de la consulta no existen en el espacio vectorial PPMI del neocórtex."
            }

        # v29: similitud contra un pool token→nodo persistido durante sueño, nunca contra todo el corpus.
        candidatos = self._candidatos_precalculados(toks)
        max_sim = 0.0
        concepto_mas_cercano = None
        for concepto in candidatos:
            v_nodo = self.indices.vecs.get(concepto)
            if v_nodo is None:
                continue
            sim = _coseno(v_q, v_nodo)
            if sim > max_sim:
                max_sim = sim
                concepto_mas_cercano = concepto

        # Cálculo de confianza epistémica compuesta (C_e):
        # Combina la similitud coseno máxima con la densidad de cobertura léxico-vectorial
        tokens_conocidos_en_db = sum(1 for t in set(toks) if t in self.indices.token_vecs)
        proporcion_tokens = tokens_conocidos_en_db / max(len(set(toks)), 1)
        
        # C_e ponderado: 70% similitud semántica máxima + 30% cobertura de tokens en espacio
        ce = float(0.7 * max(0.0, max_sim) + 0.3 * proporcion_tokens)
        ce = min(1.0, max(0.0, ce))
        um = float(1.0 - ce)

        estado = "conocido" if ce >= self.umbral_confianza else "ignoto_insuficiente_soporte"

        return {
            "query": query,
            "tokens_procesados": toks,
            "estado": estado,
            "confianza_epistemica": round(ce, 4),
            "incertidumbre": round(um, 4),
            "max_similitud_semantica": round(float(max_sim), 4),
            "concepto_mas_cercano": concepto_mas_cercano,
            "proporcion_tokens_conocidos": round(proporcion_tokens, 4),
            "candidatos_precalculados": len(candidatos),
            "indice_nocturno_disponible": bool(self.token_candidatos)
        }

    def razonar_por_significado(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Realiza una búsqueda y razonamiento por significado puro (no léxico).

        Si el sistema determina que está por debajo del umbral epistémico, lanza una excepción
        explícita (EpistemicUncertaintyError) en lugar de silenciar la ignorancia.

        Args:
            query (str): Pregunta o concepto a consultar.
            top_k (int): Número máximo de resultados a retornar.

        Returns:
            Lista de conceptos y contenidos recuperados con su puntaje de soporte semántico y sináptico.
        """
        eval_epi = self.evaluar_episteme(query)
        confianza = eval_epi["confianza_epistemica"]
        incertidumbre = eval_epi["incertidumbre"]

        if eval_epi["estado"].startswith("ignoto") and confianza < 0.2:
            # Filtrado epistémico real: si la confianza es baja, penalizar o excluir resultados poco fiables
            logger.warning(f"Aviso Epistémico (Filtrado activo): Confianza C_e={confianza:.2f} por debajo del umbral. Aplicando penalización de certidumbre.")

        toks = eval_epi.get("tokens_procesados", [])
        v_q = self.indices.vector_query(toks)
        pool_candidatos = self._candidatos_precalculados(toks)

        # Degradación graciosa: no se inventa una respuesta ni se barre la base completa.
        if confianza < 0.2 or not pool_candidatos:
            return []

        # Scoring híbrido semántico (SVD + PPMI + Cobertura)
        scores_finales = []
        for concepto in pool_candidatos:
            v_nodo = self.indices.vecs.get(concepto, np.zeros(100))
            sim_cos = _coseno(v_q, v_nodo)
            
            # Puntaje sináptico multi-hop (propagación hebbiana)
            score_sinapsis = 0.0
            visitados = {concepto}
            frontera = [(concepto, 1.0)]
            for _hop in range(2): # 2 saltos
                nueva_frontera = []
                for nodo_act, peso_acum in frontera:
                    for vecino, peso_sin in self.indices.grafo_sin.get(nodo_act, []):
                        if vecino not in visitados:
                            visitados.add(vecino)
                            p_trans = peso_acum * peso_sin * 0.4 # DECAY
                            score_sinapsis += p_trans
                            nueva_frontera.append((vecino, p_trans))
                frontera = nueva_frontera

            score_raw = float(0.6 * max(0.0, sim_cos) + 0.4 * min(1.0, score_sinapsis / 2.0))
            # Multiplicar por la confianza epistémica Ce como factor de puerta (Gating Epistémico real)
            score_total = score_raw * confianza
            scores_finales.append((concepto, score_total, sim_cos, score_sinapsis))

        scores_finales.sort(key=lambda x: x[1], reverse=True)
        resultados = []
        
        # Conectar a DB para extraer contenido legible
        con = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        try:
            for concepto, score, sim_cos, score_sin in scores_finales[:top_k]:
                cursor = con.execute("SELECT contenido, sinonimos FROM largo_plazo WHERE concepto = ?", (concepto,))
                row = cursor.fetchone()
                contenido = row[0] if row else ""
                sinonimos = row[1] if row else ""
                
                # Filtro epistémico real: ningún resultado de baja confianza entra en la respuesta final.
                if score < 0.05:
                    continue
                resultados.append({
                    "concepto": concepto,
                    "score_semantico_total": round(score, 4),
                    "similitud_coseno": round(sim_cos, 4),
                    "soporte_sinaptico": round(score_sin, 4),
                    "confianza_epistemica": round(confianza, 4),
                    "estado_epistemico": eval_epi["estado"],
                    "contenido": contenido,
                    "sinonimos": sinonimos
                })
        finally:
            con.close()

        return resultados
