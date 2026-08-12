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

        # Vector de query ponderado por IDF local
        v_q = self.indices.vector_query(toks)
        norm_q = float(np.linalg.norm(v_q))

        if norm_q < 1e-6:
            return {
                "query": query,
                "estado": "ignoto_fuera_de_distribucion",
                "confianza_epistemica": 0.0,
                "incertidumbre": 1.0,
                "razon": "Los tokens de la consulta no existen en el espacio vectorial PPMI del neocórtex."
            }

        # Calcular similitud coseno máxima con los nodos existentes en memoria
        max_sim = 0.0
        concepto_mas_cercano = None
        for concepto, v_nodo in self.indices.vecs.items():
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
            "proporcion_tokens_conocidos": round(proporcion_tokens, 4)
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

        if eval_epi["estado"].startswith("ignoto"):
            raise EpistemicUncertaintyError(
                mensaje=f"Neocórtex en estado 'Sabe que no sabe'. Ignorancia epistémica detectada para la consulta '{query}'. Razón: {eval_epi['razon']}",
                incertidumbre=incertidumbre,
                confianza=confianza
            )

        toks = eval_epi["tokens_procesados"]
        v_q = self.indices.vector_query(toks)
        pool_candidatos = set(self.indices.todos_los_conceptos)

        if not pool_candidatos:
            raise EpistemicUncertaintyError(
                mensaje="El neocórtex no posee nodos en su memoria a largo plazo.",
                incertidumbre=1.0,
                confianza=0.0
            )

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

            score_total = float(0.6 * max(0.0, sim_cos) + 0.4 * min(1.0, score_sinapsis / 2.0))
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
                
                resultados.append({
                    "concepto": concepto,
                    "score_semantico_total": round(score, 4),
                    "similitud_coseno": round(sim_cos, 4),
                    "soporte_sinaptico": round(score_sin, 4),
                    "contenido": contenido,
                    "sinonimos": sinonimos
                })
        finally:
            con.close()

        return resultados
