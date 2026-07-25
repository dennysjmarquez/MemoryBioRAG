"""
Extractor SRL Determinista Ligero (v1.0) para BioRAG
===================================================
Extrae predicados {sujeto, accion, objeto, contexto} a partir de texto en español
mediante reglas sintácticas deterministas y diccionarios de verbos canónicos.
Sin dependencias de LLMs externos ni librerías pesadas.
"""

import re
import unicodedata

# Verbos de acción canónicos comunes en memorias y relatos
VERBOS_CANONICOS = {
    "enseno": "ensena", "enseño": "ensena", "ensena": "ensena", "enseña": "ensena",
    "aprendio": "aprendio", "aprendió": "aprendio", "aprende": "aprendio",
    "falle": "fallo", "fallo": "fallo", "falló": "fallo", "fallar": "fallo",
    "rompio": "rompio", "rompió": "rompio", "romper": "rompio",
    "mato": "mato", "mató": "mato", "matar": "mato", "quemo": "mato", "quemó": "mato",
    "echo": "agrego", "echó": "agrego", "agrego": "agrego", "agregó": "agrego", "mezclo": "agrego", "mezcló": "agrego",
    "creo": "creo", "creó": "creo", "establecio": "creo", "estableció": "creo",
    "instruyo": "instruyo", "instruyó": "instruyo", "ordeno": "instruyo", "ordenó": "instruyo",
    "engano": "engano", "engañó": "engano", "engana": "engano", "engaña": "engano",
    "reacciono": "reacciono", "reaccionó": "reacciono",
    "probamos": "probo", "probo": "probo", "probó": "probo", "verifico": "probo", "verificó": "probo"
}

NOBLES_SUJETOS = {"dennys", "athena", "usuario", "agente", "companero", "mecanico", "cliente", "duena", "otro"}

def _limpiar_texto(texto: str) -> str:
    return re.sub(r'\s+', ' ', texto).strip()

def extraerte_normalizado(palabra: str) -> str:
    palabra = palabra.lower()
    return ''.join(c for c in unicodedata.normalize('NFKD', palabra) if not unicodedata.combining(c))

def extraer_predicados_determinista(texto: str) -> list[dict]:
    """
    Analiza un texto en español y extrae tripletas SRL {sujeto, accion, objeto, contexto}.
    Retorna una lista de diccionarios.
    """
    if not texto or len(texto.strip()) < 5:
        return []

    predicados = []
    texto_clean = _limpiar_texto(texto)
    oraciones = re.split(r'[.;!\n]+', texto_clean)

    for oracion in oraciones:
        oracion = oracion.strip()
        if not oracion:
            continue

        palabras = oracion.split()
        for i, word in enumerate(palabras):
            word_norm = extraerte_normalizado(word)
            
            # Detectar si la palabra es un verbo canónico o derivado
            accion_canon = VERBOS_CANONICOS.get(word_norm) or VERBOS_CANONICOS.get(word.lower())
            if not accion_canon:
                # Intento de lematización simple si termina en verbos comunes
                if word_norm.endswith(("io", "aron", "eron", "aba", "ante")):
                    accion_canon = word_norm

            if accion_canon:
                # Inferir sujeto (palabras a la izquierda)
                sujeto = "desconocido"
                if i > 0:
                    prev_words = [w.lower().strip(",.") for w in palabras[max(0, i-3):i]]
                    for pw in prev_words:
                        pw_norm = extraerte_normalizado(pw)
                        if pw_norm in NOBLES_SUJETOS or len(pw_norm) > 3:
                            sujeto = pw_norm
                            break

                # Inferir objeto (palabras a la derecha inmediatas)
                objeto = "evento"
                if i + 1 < len(palabras):
                    next_words = [w.lower().strip(",.") for w in palabras[i+1:min(len(palabras), i+4)]]
                    # Omitir artículos/preposiciones cortas
                    objs = [w for w in next_words if len(extraerte_normalizado(w)) > 3]
                    if objs:
                        objeto = "_".join([extraerte_normalizado(w) for w in objs[:2]])

                # Inferir contexto
                contexto = extraerte_normalizado(palabras[0]) if palabras else "general"

                predicados.append({
                    "sujeto": sujeto,
                    "accion": accion_canon,
                    "objeto": objeto,
                    "contexto": contexto
                })

    return predicados
