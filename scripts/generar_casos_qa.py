import sys
import os
import random
import json
import sqlite3

# Add workspace root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.memory_store import SQLiteMemoryBioRAG
from core.stopwords import STOPWORDS

BILINGUAL_DICT = {
    "memoria": "recollection",
    "sistema": "framework",
    "archivo": "record",
    "archivos": "records",
    "datos": "inputs",
    "red": "infrastructure",
    "error": "anomaly",
    "fallo": "breakdown",
    "conexion": "integration",
    "guardar": "persist",
    "recuperar": "fetch",
    "buscar": "query",
    "servidor": "host",
    "cliente": "consumer",
    "base": "repository",
    "usuario": "operator",
    "autenticacion": "verification",
    "autorizacion": "permissioning",
    "seguridad": "hardening",
    "arquitectura": "blueprint",
    "leccion": "insight",
    "proyecto": "undertaking",
    "pruebas": "validations",
    "prueba": "validation",
    "configuracion": "adjustments",
    "interfaz": "viewport",
    "desarrollo": "engineering",
    "codigo": "syntax",
    "nube": "cluster",
    "ruta": "endpoint",
    "controlador": "handler",
    "modelo": "representation",
    "vista": "renderer",
    "actualizar": "modify",
    "borrar": "purge",
    "crear": "instantiate",
}

# Reverse dictionary for bilingual lookup
REVERSE_BILINGUAL_DICT = {v: k for k, v in BILINGUAL_DICT.items()}

# Technical synonym map
SYNONYM_MAP = {
    "datos": "informacion",
    "informacion": "datos",
    "fallo": "error",
    "error": "falla",
    "guardar": "almacenar",
    "almacenar": "persister",
    "crear": "generar",
    "generar": "crear",
    "borrar": "eliminar",
    "eliminar": "remover",
    "conexion": "enlace",
    "configuracion": "ajustes",
    "servidor": "server",
}

def introduce_typo(word):
    """Introduces a single typo (swap, delete, or insert) in a word."""
    if len(word) <= 3:
        return word
    
    op = random.choice(["swap", "delete", "insert"])
    chars = list(word)
    
    if op == "swap":
        idx = random.randint(0, len(chars) - 2)
        chars[idx], chars[idx+1] = chars[idx+1], chars[idx]
    elif op == "delete":
        idx = random.randint(0, len(chars) - 1)
        chars.pop(idx)
    elif op == "insert":
        idx = random.randint(0, len(chars))
        random_char = random.choice("abcdefghijklmnopqrstuvwxyz")
        chars.insert(idx, random_char)
        
    return "".join(chars)

def vary_grammar(word):
    """Varies the grammatical form of a Spanish word."""
    if word.endswith("cion"):
        return word[:-4] + "ciones"
    elif word.endswith("ciones"):
        return word[:-6] + "cion"
    elif word.endswith("ador"):
        return word[:-4] + "adores"
    elif word.endswith("o") and len(word) > 3:
        return word[:-1] + "ando"
    elif word.endswith("ado") and len(word) > 3:
        return word[:-3] + "ar"
    elif word.endswith("ar") and len(word) > 3:
        return word[:-2] + "ado"
    elif word.endswith("a") and len(word) > 3:
        return word[:-1] + "as"
    return word + "s" if not word.endswith("s") else word[:-1]

def get_keywords_from_text(text):
    """Tokenizes text and returns clean keywords excluding stopwords."""
    words = []
    # Simple regex-like word extraction
    for w in text.lower().replace("_", " ").split():
        clean_w = "".join(c for c in w if c.isalnum())
        if clean_w and clean_w not in STOPWORDS and len(clean_w) > 2:
            words.append(clean_w)
    return list(set(words))

def generate_cases_for_node(node, db, only_literal=False, exclude_literal=False):
    """Generates a list of test cases for a single memory node."""
    concepto = node["concepto"]
    contenido = node["contenido"]
    sinonimos_str = node["sinonimos"] or ""
    sinonimos = [s.strip() for s in sinonimos_str.split(",") if s.strip()]
    
    concept_words = [w for w in concepto.replace("_", " ").split() if w]
    
    cases = []
    
    # 1. Literal Exacto
    if not exclude_literal:
        cases.append({
            "categoria": "literal",
            "query": concepto.replace("_", " "),
            "concepto_esperado": concepto,
            "deep": False,
            "notes": "Exact match check"
        })
    
    if only_literal:
        return cases

    
    # 2. Variante Gramatical
    gram_query_words = []
    for w in concept_words:
        if random.random() < 0.5:
            gram_query_words.append(vary_grammar(w))
        else:
            gram_query_words.append(w)
    cases.append({
        "categoria": "variante_gramatical",
        "query": " ".join(gram_query_words),
        "concepto_esperado": concepto,
        "deep": False,
        "notes": "Grammar variation check"
    })
    
    # 3. Typo
    typo_query_words = []
    for w in concept_words:
        if random.random() < 0.5 and len(w) > 3:
            typo_query_words.append(introduce_typo(w))
        else:
            typo_query_words.append(w)
    cases.append({
        "categoria": "typo",
        "query": " ".join(typo_query_words),
        "concepto_esperado": concepto,
        "deep": False,
        "notes": "Typo tolerance check"
    })
    
    # 4. Cruce Idioma
    lang_query_words = []
    translated_any = False
    for w in concept_words:
        if w in BILINGUAL_DICT:
            lang_query_words.append(BILINGUAL_DICT[w])
            translated_any = True
        elif w in REVERSE_BILINGUAL_DICT:
            lang_query_words.append(REVERSE_BILINGUAL_DICT[w])
            translated_any = True
        else:
            lang_query_words.append(w)
            
    if translated_any:
        cases.append({
            "categoria": "cruce_idioma",
            "query": " ".join(lang_query_words),
            "concepto_esperado": concepto,
            "deep": False,
            "notes": "Bilingual mapping check"
        })
        
    # 5. Sinonimo
    syn_query_words = []
    used_synonym = False
    if sinonimos:
        # Use one of the registered synonyms
        cases.append({
            "categoria": "sinonimo",
            "query": random.choice(sinonimos),
            "concepto_esperado": concepto,
            "deep": False,
            "notes": "Registered synonym match"
        })
    else:
        for w in concept_words:
            if w in SYNONYM_MAP:
                syn_query_words.append(SYNONYM_MAP[w])
                used_synonym = True
            else:
                syn_query_words.append(w)
        if used_synonym:
            cases.append({
                "categoria": "sinonimo",
                "query": " ".join(syn_query_words),
                "concepto_esperado": concepto,
                "deep": False,
                "notes": "Mapped synonym match"
            })
            
    # 6. Pregunta Natural
    templates = [
        "¿Cómo se hace {}?",
        "¿Dónde encuentro la info de {}?",
        "Me acuerdo de algo sobre {}",
        "¿Qué tenemos registrado para {}?",
        "Explicame el tema de {}",
        "¿Qué me podés decir sobre {}?"
    ]
    cases.append({
        "categoria": "pregunta_natural",
        "query": random.choice(templates).format(concepto.replace("_", " ")),
        "concepto_esperado": concepto,
        "deep": False,
        "notes": "Natural language query check"
    })
    
    # 7. Por Tema
    content_keywords = get_keywords_from_text(contenido)
    # Filter keywords to not contain any concept words literally to make it a pure thematic test
    pure_theme_keywords = [w for w in content_keywords if w not in concept_words]
    if len(pure_theme_keywords) >= 2:
        query_theme = " ".join(random.sample(pure_theme_keywords, min(3, len(pure_theme_keywords))))
        cases.append({
            "categoria": "por_tema",
            "query": query_theme,
            "concepto_esperado": concepto,
            "deep": False,
            "notes": "Content/theme check"
        })
        
    # 8. Dormido
    # We will mark it as dormido in DB copy later. For now, generate the query for it.
    cases.append({
        "categoria": "dormido",
        "query": concepto.replace("_", " "),
        "concepto_esperado": concepto,
        "deep": True,
        "notes": "Dormant node retrieval check"
    })
    
    return cases

def _normalizar_token(texto):
    """Normaliza texto para matching de tokens: sin acentos, minúsculas."""
    import unicodedata
    return ''.join(
        c for c in unicodedata.normalize('NFKD', texto)
        if not unicodedata.combining(c)
    ).lower()


def _tokens_corpus(db):
    """Tokens (>=3 chars, normalizados) presentes en el corpus completo.

    Un control negativo solo es válido si NINGÚN token de su query aparece
    como palabra en el corpus (concepto + contenido + sinónimos). De lo
    contrario la query deja de ser "ruido" y pasa a ser una coincidencia
    léxica legítima (contaminación autorreferencial): el motor la recupera
    correctamente y el QA la cuenta como falso positivo sin serlo.
    """
    import re
    tokens = set()
    db.cursor.execute(
        "SELECT concepto, COALESCE(contenido, ''), COALESCE(sinonimos, '') FROM largo_plazo"
    )
    for concepto, contenido, sinonimos in db.cursor.fetchall():
        texto = f"{concepto} {contenido} {sinonimos}".replace('_', ' ').replace('-', ' ')
        for w in re.findall(r'\w{3,}', _normalizar_token(texto)):
            tokens.add(w)
    return tokens


# Vocabulario fresco para controles negativos (v2, 2026-09-01).
# MOTIVACIÓN: el pool v1 (jirafa, helado, bufanda, ...) quedó contaminado
# porque las lecciones/hallazgos sobre la propia suite QA (gate QCR y su
# investigación de FP) citan esos términos como ejemplos DENTRO del corpus.
# Al documentarse en la memoria, dejaron de ser controles negativos válidos.
# Este pool no reutiliza ninguna palabra del pool v1 y cada query se valida
# contra el corpus actual (tokens) + búsqueda empírica top-5, garantizando
# que sea "ruido real" sin overlap léxico.
NEGATIVE_WORDS_POOL_V2 = [
    "hipopótamo", "aspiradora", "tocadiscos", "perchero", "abrelatas",
    "palangana", "cebolla", "trompeta", "acordeón", "colibrí",
    "perejil", "lavanda", "cigüeña", "mapache", "castor",
    "avestruz", "cisne", "sartén", "cucharón", "tetera",
    "hamaca", "mecedora", "regadera", "macetero", "farola",
    "noria", "tobogán", "saxofón", "clarinete", "flauta",
    "cocodrilo", "cebra", "morsa", "tapir", "jabalí",
    "albahaca", "romero", "tomillo", "jengibre", "canela",
    "tamboril", "pandereta", "cacerola", "colador", "rallador",
    "servilleta", "alfiler", "cremallera", "cinturón", "pañoleta",
    "tendedero", "escobillón", "plumero", "batidora", "exprimidor",
]


def generate_negative_queries(db, count=40, negative_words_pool=None):
    """Genera controles negativos y valida que NO existan en el corpus.

    Un control es válido si:
      1. Ningún token de la query aparece como palabra en el corpus
         (concepto + contenido + sinónimos) — evita la contaminación
         autorreferencial que infló el %FP a 60% en la corrida previa.
      2. La búsqueda profunda no devuelve nada, o todo el top-5 queda
         por debajo del umbral de ruido (score < 0.25).
    """
    if negative_words_pool is None:
        negative_words_pool = NEGATIVE_WORDS_POOL_V2

    import re
    tokens_corpus = _tokens_corpus(db)
    negatives = []
    attempts = 0
    max_attempts = 2000

    while len(negatives) < count and attempts < max_attempts:
        attempts += 1
        num_words = random.randint(2, 4)
        selected = random.sample(negative_words_pool, min(num_words, len(negative_words_pool)))
        query = " ".join(selected)

        # Guarda 1: ningún token de la query puede existir en el corpus
        q_tokens = re.findall(r'\w{3,}', _normalizar_token(query))
        if any(t in tokens_corpus for t in q_tokens):
            continue

        # Guarda 2: validación empírica contra búsqueda profunda (top-5 completo)
        results, total = db.buscar_por_frase(query, profundidad="profundo", limite=5)
        if total == 0 or (len(results) > 0 and all(r[4] < 0.25 for r in results)):
            negatives.append({
                "categoria": "negativo",
                "query": query,
                "concepto_esperado": None,
                "deep": True,  # Test under deep search as well to test robustness of all layers
                "notes": "Empirically validated negative control (v2, sin overlap léxico con el corpus)"
            })

    if len(negatives) < count:
        print(f"ADVERTENCIA: solo se validaron {len(negatives)}/{count} negativos en {attempts} intentos.")
    print(f"Validated {len(negatives)} negative queries in {attempts} generation attempts.")
    return negatives

def main():
    random.seed(42)
    db_path = os.environ.get('BIORAG_PATH') or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "MemoryBioRAG_Data", "memory_biorag.db"
    )
    
    print(f"Reading source concepts from: {db_path}")
    db = SQLiteMemoryBioRAG(db_path=db_path)
    
    # Extract real nodes sorted by concept to ensure deterministic ordering
    db.cursor.execute("SELECT concepto, contenido, sinonimos, categoria FROM largo_plazo ORDER BY concepto")
    rows = db.cursor.fetchall()
    
    all_nodes = []
    for concepto, contenido, sinonimos, categoria in rows:
        # We prefer nodes with content and decent length to generate meaningful queries
        if contenido and len(contenido) > 50:
            all_nodes.append({
                "concepto": concepto,
                "contenido": contenido,
                "sinonimos": sinonimos,
                "categoria": categoria
            })
            
    print(f"Found {len(rows)} total nodes, {len(all_nodes)} suitable for query generation.")
    
    all_cases = []
    case_id = 1
    
    # 1. Generate literal exact cases for ALL suitable nodes
    for node in all_nodes:
        literal_cases = generate_cases_for_node(node, db, only_literal=True)
        for case in literal_cases:
            case["id"] = f"{case_id:04d}"
            all_cases.append(case)
            case_id += 1
            
    # Sample nodes to generate other variants (e.g. 65 nodes)
    sample_size = min(len(all_nodes), 65)
    selected_nodes = random.sample(all_nodes, sample_size)
    print(f"Selected {sample_size} nodes for other variant test case generation.")
    
    # Track dormant candidate concepts for DB setup
    dormant_candidates = []
    
    for node in selected_nodes:
        # Generate the other categories (excluding literal)
        node_cases = generate_cases_for_node(node, db, only_literal=False, exclude_literal=True)
        for case in node_cases:
            case["id"] = f"{case_id:04d}"
            all_cases.append(case)
            case_id += 1
            if case["categoria"] == "dormido":
                dormant_candidates.append(case["concepto_esperado"])
                
    # Generate validated negative controls
    negative_cases = generate_negative_queries(db, count=40)
    for case in negative_cases:
        case["id"] = f"{case_id:04d}"
        all_cases.append(case)
        case_id += 1
        
    db.conn.close()
    
    # Save cases to cases_qa.jsonl
    output_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "scripts", "casos_qa.jsonl"
    )
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for case in all_cases:
            f.write(json.dumps(case, ensure_ascii=False) + "\n")
            
    print(f"Successfully generated {len(all_cases)} QA test cases.")
    print(f"Saved dataset to: {output_path}")
    
if __name__ == "__main__":
    main()
