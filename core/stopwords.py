"""
Módulo centralizado de Stopwords para BioRAG.
Define conjuntos de palabras vacías (stopwords) en español e inglés,
así como términos de control internos del sistema.
"""

# Stopwords en Español (Genuinamente Español-only)
STOPWORDS_ES = {
    # Pronombres y artículos
    'el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas', 'mi', 'mis', 'tu', 'tus', 'su', 'sus',
    'nuestro', 'nuestra', 'nuestros', 'nuestras', 'yo', 'me', 'te', 'se', 'nos', 'lo', 'le', 'les',
    'otro', 'otra', 'otros', 'otras', 'aquel', 'aquella', 'aquellos', 'aquellas', 'este', 'esta',
    'estos', 'estas', 'ese', 'esa', 'esos', 'esas', 'esto', 'ello', 'ella', 'ellos', 'ellas',
    'quien', 'quién', 'cual', 'cuál', 'cuyo', 'cuya', 'cuyos', 'cuyas', 'todo', 'toda', 'todos',
    'todas', 'algun', 'alguna', 'algunos', 'algunas', 'ningun', 'ninguna', 'ninguno', 'mismo',
    'misma', 'mismos', 'mismas',
    # Preposiciones
    'a', 'ante', 'bajo', 'cabe', 'con', 'contra', 'de', 'desde', 'durante', 'en', 'entre', 'hacia',
    'hasta', 'mediante', 'para', 'por', 'segun', 'sin', 'so', 'sobre', 'tras', 'versus', 'via',
    'del', 'al',
    # Conjunciones y adverbios
    'y', 'o', 'u', 'e', 'ni', 'que', 'pero', 'mas', 'como', 'porque', 'pues', 'aunque', 'sino',
    'muy', 'tan', 'entonces', 'luego', 'despues', 'antes', 'ahora', 'hoy', 'ayer', 'mañana', 'ya',
    'aun', 'también', 'tambien', 'tampoco', 'cuando', 'donde', 'si', 'no',
    # Verbos auxiliares/comunes y palabras de relleno/de control
    'es', 'son', 'era', 'han', 'sido', 'sea', 'tiene', 'tienen', 'tenemos', 'hacer', 'hecho',
    'puede', 'pueden', 'dicho', 'tanto', 'parte', 'forma', 'tipo', 'tema', 'vez', 'caso', 'dentro',
    'algo', 'alguno', 'alguien', 'acuerdo', 'acordar', 'podes', 'podés', 'decir', 'saber', 'querer',
    'quiero', 'gustaria', 'gustaría', 'acerca', 'según',
    # Palabras y verbos conversacionales de queries
    'cómo', 'dónde', 'cuándo', 'quién', 'cuál', 'cuáles', 'qué', 'hace', 'hago',
    'encuentro', 'encuentra', 'encontrar', 'busca', 'buscar', 'tengo', 'tener',
    'puedo', 'poder', 'quiere', 'usa', 'usar', 'uso', 'sirve', 'servir'
}

# Stopwords en Inglés (Genuinamente Inglés-only)
STOPWORDS_EN = {
    # Articles & pronouns
    'the', 'a', 'an', 'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves', 'you', 'your',
    'yours', 'yourself', 'yourselves', 'he', 'him', 'his', 'himself', 'she', 'her', 'hers',
    'herself', 'it', 'its', 'itself', 'they', 'them', 'their', 'theirs', 'themselves', 'what',
    'which', 'who', 'whom', 'this', 'that', 'these', 'those', 'each', 'few', 'more', 'most',
    'other', 'some', 'such', 'own', 'same',
    # Prepositions & conjunctions
    'and', 'or', 'but', 'if', 'because', 'as', 'until', 'while', 'of', 'at', 'by', 'for', 'with',
    'about', 'against', 'between', 'into', 'through', 'during', 'before', 'after', 'above',
    'below', 'to', 'from', 'up', 'down', 'in', 'out', 'on', 'off', 'over', 'under', 'than',
    # Verbs and auxiliaries
    'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'having', 'do',
    'does', 'did', 'doing', 'can', 'will', 'should', 'would', 'could', 'am', 'don',
    # Adverbs & others
    'again', 'further', 'then', 'once', 'here', 'there', 'when', 'where', 'why', 'how', 'all',
    'any', 'both', 'no', 'nor', 'not', 'only', 'so', 'too', 'very', 's', 't', 'just', 'now',
    'something', 'someone', 'tell', 'want', 'would', 'like', 'know',
    # Conversational query words/verbs
    'find', 'get', 'make', 'use', 'look', 'search'
}

# Términos de control internos del sistema (BioRAG-specific)
STOPWORDS_CONTROL = {
    'nodo', 'prueba', 'test', 'recuerdo', 'concepto', 'contenido', 'sistema', 'memoria',
    'node', 'system', 'memory', 'concept', 'content'
}

# Conjunto unificado para búsquedas y procesamiento general
STOPWORDS = STOPWORDS_ES | STOPWORDS_EN | STOPWORDS_CONTROL

# Alias para similitud_conceptual para mantener compatibilidad bilingüe
_STOPWORDS_QUERY = STOPWORDS_ES | STOPWORDS_EN

