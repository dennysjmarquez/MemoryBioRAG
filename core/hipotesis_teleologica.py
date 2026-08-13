"""hipotesis_teleologica.py — Motor de Formulación de Hipótesis Autónomas para BioRAG.

Propósito:
    Permitir que el Neocórtex de Sangre no solo recupere información, sino que busque
    activamente nuevas conexiones (teleología). Identifica "huecos genéticos" y
    propone sinapsis potenciales basadas en la afinidad de ADN Conceptual.

Flujo Teleológico:
    1. Escaneo de Gaps: Busca pares de conceptos con alta afinidad genética pero sin
       sinapsis existente en la base de datos.
    2. Formulación de Hipótesis: Genera una proposición lógica ("A y B están vinculados
       por la esencia X") con un nivel de confianza inicial.
    3. Validación Epistémica: Cruza la hipótesis con la incertidumbre actual del sistema.

Adaptación v29 (integración BioRAG):
    v29 elimina el catálogo fijo de cromosomas (``CROMOSOMAS_CATALOGO`` quedó vacío):
    los cromosomas ahora emergen del clustering real en ``reconstruir_indice_nocturno``.
    Este módulo usa ``ADNConceptualEngine.nombres_cromosomas`` (dinámicos) en lugar del
    catálogo eliminado, para que el "puente genético" de cada hipótesis sea significativo.
"""

import logging
from typing import List, Dict, Any
from core.adn_conceptual import ADNConceptualEngine, _vector_firma, _coseno

logger = logging.getLogger("BioRAG.HipotesisTeleologica")

class HipotesisTeleologica:
    """Motor de curiosidad y generación de hipótesis del neocórtex."""

    def __init__(self, adn_engine: ADNConceptualEngine, db_path: str = None):
        self.adn = adn_engine
        self.db_path = db_path

    def generar_hipotesis_proactivas(self, umbral_afinidad: float = 0.65) -> List[Dict[str, Any]]:
        """Escanea el mapa genético actual en busca de relaciones no evidentes.

        Retorna una lista de hipótesis formuladas autónomamente.
        """
        conceptos = list(self.adn.firmas.keys())
        hipotesis = []
        # v29: cromosomas dinámicos emergentes (nunca un catálogo fijo).
        cromosomas = self.adn.nombres_cromosomas

        for i in range(len(conceptos)):
            for j in range(i + 1, len(conceptos)):
                c1, c2 = conceptos[i], conceptos[j]
                
                v1 = _vector_firma(self.adn.firmas[c1])
                v2 = _vector_firma(self.adn.firmas[c2])
                
                sim = _coseno(v1, v2)
                
                if sim >= umbral_afinidad:
                    # Identificar el "puente genético" (cromosomas dominantes comunes)
                    genes_puente = []
                    for k, crom in enumerate(cromosomas):
                        if k < len(v1) and k < len(v2) and v1[k] >= 0.5 and v2[k] >= 0.5:
                            genes_puente.append(crom)
                    
                    if genes_puente:
                        hipotesis.append({
                            "tipo": "vinculo_esencial",
                            "sujetos": [c1, c2],
                            "afinidad": round(sim, 4),
                            "puente_genetico": genes_puente,
                            "proposicion": f"El concepto '{c1}' y '{c2}' podrían estar profundamente vinculados por su naturaleza compartida de: {', '.join(genes_puente)}.",
                            "estado": "por_validar"
                        })

        # Ordenar por afinidad (las más probables primero)
        hipotesis.sort(key=lambda x: x["afinidad"], reverse=True)
        return hipotesis

    def razonar_sobre_nuevo_concepto(self, concepto: str, firma: Dict[str, float]) -> Dict[str, Any]:
        """Integra un nuevo concepto y genera hipótesis inmediatas sobre su lugar en el mundo."""
        self.adn.registrar_concepto(concepto, firma)
        relaciones = self.adn.buscar_por_esencia(concepto, top_k=5)
        
        hipotesis_inmediatas = []
        for rel in relaciones:
            if rel["afinidad_genetica"] >= 0.5:
                hipotesis_inmediatas.append({
                    "objetivo": rel["concepto"],
                    "afinidad": rel["afinidad_genetica"],
                    "porque": f"Comparten los cromosomas: {', '.join(rel['genes_compartidos'])}"
                })
        
        return {
            "concepto": concepto,
            "firma": firma,
            "hipotesis_de_integracion": hipotesis_inmediatas
        }
