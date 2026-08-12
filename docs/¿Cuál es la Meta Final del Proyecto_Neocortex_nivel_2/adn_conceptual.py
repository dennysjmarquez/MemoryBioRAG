"""adn_conceptual.py — Motor de ADN Conceptual ("Neocórtex de Sangre") para MemoryBioRAG.

Propósito:
    Implementar el razonamiento por significado puro y esencia conceptual mediante
    "Cromosomas Semánticos" (Genes del Significado). Permite relacionar conceptos
    profundamente (ej. 'gato' con 'soledad' o 'independencia') sin compartir palabras,
    sinónimos ni enlaces léxicos, basándose en su perfil genético estructural.

Principios:
    1. Esencia sobre Etiqueta: Un concepto se define por sus propiedades fundamentales
       (cromosomas), no por su nombre o vecinos de co-ocurrencia.
    2. Distancia Genética: Las conexiones surgen de la similitud en el espacio de
       cromosomas semánticos (ortogonales y abstractos).
    3. Explicabilidad Biológica: Cada vínculo entre conceptos dispares se justifica
       explicitando qué cromosomas comparten (ej. 'ambos comparten el gen autónomo').
"""

import math
import numpy as np
from typing import Dict, List, Tuple, Any

# Catálogo de Cromosomas Semánticos Fundamentales (Genes del Significado)
# Representan los ejes esenciales de la cognición biológica y abstracta.
CROMOSOMAS_CATALOGO = [
    "biologico",      # Vivo, orgánico, celular
    "autonomo",       # Independiente, libre, soberano
    "depredador",     # Caza, supervivencia, activo
    "domestico",      # Hogar, convivencia, pacífico
    "abstracto",      # Idea, intangible, formal
    "social",         # Colectivo, manada, interacción
    "mecanico",       # Artificial, eléctrico, instrumental
    "contemplativo"   # Observación, quietud, reflexivo
]

# Firma genética innata para conceptos clave (ejemplo de "cerebro de sangre")
# Permite demostrar el salto conceptual puro sin requerir entrenamiento masivo.
FIRMAS_INNATAS = {
    "gato": {
        "biologico": 1.0,
        "autonomo": 0.9,
        "depredador": 0.8,
        "domestico": 0.7,
        "abstracto": 0.1,
        "social": 0.2,
        "mecanico": 0.0,
        "contemplativo": 0.9
    },
    "soledad": {
        "biologico": 0.0,
        "autonomo": 1.0,
        "depredador": 0.0,
        "domestico": 0.2,
        "abstracto": 0.9,
        "social": 0.0,
        "mecanico": 0.0,
        "contemplativo": 1.0
    },
    "tigre": {
        "biologico": 1.0,
        "autonomo": 0.95,
        "depredador": 1.0,
        "domestico": 0.0,
        "abstracto": 0.1,
        "social": 0.1,
        "mecanico": 0.0,
        "contemplativo": 0.5
    },
    "filosofia": {
        "biologico": 0.1,
        "autonomo": 0.8,
        "depredador": 0.0,
        "domestico": 0.1,
        "abstracto": 1.0,
        "social": 0.4,
        "mecanico": 0.0,
        "contemplativo": 1.0
    },
    "reloj": {
        "biologico": 0.0,
        "autonomo": 0.3,
        "depredador": 0.0,
        "domestico": 0.9,
        "abstracto": 0.2,
        "social": 0.0,
        "mecanico": 1.0,
        "contemplativo": 0.1
    }
}


def _vector_firma(firma: Dict[str, float]) -> np.ndarray:
    """Convierte un diccionario de firma genética en un vector ordenado de NumPy."""
    return np.array([firma.get(c, 0.0) for c in CROMOSOMAS_CATALOGO], dtype='float64')


def _coseno(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    return float(np.dot(a, b) / (na * nb)) if na > 1e-10 and nb > 1e-10 else 0.0


class ADNConceptualEngine:
    """Motor de razonamiento por ADN Conceptual.

    Evalúa la afinidad genética entre conceptos y descubre saltos conceptuales puros
    basados en la similitud de cromosomas semánticos, incluso cuando no existen
    coincidencias léxicas ni sinónimos.
    """

    def __init__(self, firmas_extra: Dict[str, Dict[str, float]] = None):
        self.firmas = dict(FIRMAS_INNATAS)
        if firmas_extra:
            self.firmas.update(firmas_extra)

    def registrar_concepto(self, concepto: str, firma: Dict[str, float]):
        """Registra o actualiza la firma genética de un concepto en el neocórtex."""
        self.firmas[concepto.lower().strip()] = firma

    def inferir_firma_por_texto(self, texto: str) -> Dict[str, float]:
        """Heurística avanzada para estimar cromosomas a partir de contenido textual."""
        t = texto.lower()
        firma = {c: 0.1 for c in CROMOSOMAS_CATALOGO}
        
        if any(w in t for w in ['animal', 'vida', 'mamifero', 'felino', 'criatura', 'gato']):
            firma['biologico'] = 0.9
            firma['depredador'] = 0.6
        if any(w in t for w in ['solo', 'independiente', 'soledad', 'aislado', 'autonomo']):
            firma['autonomo'] = 0.95
            firma['contemplativo'] = 0.8
        if any(w in t for w in ['casa', 'hogar', 'compania', 'familia', 'domestico']):
            firma['domestico'] = 0.8
            firma['social'] = 0.6
        if any(w in t for w in ['idea', 'concepto', 'pensamiento', 'teoria', 'abstracto']):
            firma['abstracto'] = 0.95
            firma['contemplativo'] = 0.8
        if any(w in t for w in ['maquina', 'motor', 'rueda', 'mecanico', 'codigo', 'programa']):
            firma['mecanico'] = 0.9
            firma['biologico'] = 0.0

        return firma

    def buscar_por_esencia(self, query_concepto: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Realiza una búsqueda puramente por ADN conceptual (esencia compartida).

        Encuentra conceptos emparentados genéticamente aunque no compartan letras.
        """
        q_key = query_concepto.lower().strip()
        if q_key not in self.firmas:
            # Inferir si no existe
            self.firmas[q_key] = self.inferir_firma_por_texto(query_concepto)

        v_q = _vector_firma(self.firmas[q_key])
        resultados = []

        for concepto, firma in self.firmas.items():
            if concepto == q_key:
                continue
            v_cand = _vector_firma(firma)
            sim = _coseno(v_q, v_cand)
            
            # Identificar cromosomas compartidos clave (genes dominantes comunes)
            genes_comunes = []
            for i, crom in enumerate(CROMOSOMAS_CATALOGO):
                val_q = v_q[i]
                val_c = v_cand[i]
                if val_q >= 0.5 and val_c >= 0.5:
                    genes_comunes.append(crom)

            resultados.append({
                "concepto": concepto,
                "afinidad_genetica": round(sim, 4),
                "genes_compartidos": genes_comunes,
                "firma": firma
            })

        resultados.sort(key=lambda x: x["afinidad_genetica"], reverse=True)
        return resultados[:top_k]
