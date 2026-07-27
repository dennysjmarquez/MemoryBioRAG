"""
BioRAG v24.1 — DMN Fase 2: Reflexión Cognitiva vía LLM Externo (Gemini)
========================================================================
v24.1: La Hormiguita — sistema de mantenimiento seguro y automedible.
       Cuarentena de sinapsis, benchmark gate, two-strike pruning,
       batching con resume, pre-filter opcional.
========================================================================
NOTA: dmn_engine.py (Fase 1, mind-wandering) está funcional pero dormido
en producción. El candidato "insight_dmn" queda inactivo hasta que
dmn_engine se arranque. Ver dmn_engine_desconectado_produccion_2026_07_27.

Esta fase le pasa a un LLM (Gemini) un lote pequeño de candidatos —
insights DMN sin revisar, sinapsis latentes de peso dudoso, sinapsis
PMI_HEBBIANO de peso bajo, y nodos antiguos con valencia decayendo—
y le pide un veredicto estructurado en JSON. El LLM RAZONA, el backend
EJECUTA. Solo mantenimiento (evaluación y poda), sin creación de
conexiones nuevas.

Principio de diseño (Default Deny, igual que MemoryBioRAG DSL):
El LLM nunca escribe directo a la base de datos. Solo propone. Cada
veredicto pasa por un umbral de confianza determinista antes de
aplicarse. Si el LLM falla, no responde, o responde JSON inválido,
el ciclo se aborta sin tocar un solo byte de la memoria persistente.

Multi-key: Soporta múltiples API keys del mismo proveedor separadas
por coma. Si una key falla por cuota, rota a la siguiente. Si todas
fallan, aborta el ciclo.

Variables de entorno:
    GEMINI_API_KEYS                      — keys separadas por coma (recomendado).
    GEMINI_API_KEY                        — fallback legacy (una sola key).
    BIORAG_GEMINI_MODEL                   — default "gemini-3.1-flash-lite"
    BIORAG_DMN_UMBRAL_ACEPTAR             — default 0.75
    BIORAG_DMN_UMBRAL_ELIMINAR            — default 0.70
    BIORAG_DMN_LOTE_MAX_INSIGHTS          — default 10
    BIORAG_DMN_LOTE_MAX_SINAPSIS          — default 5
    BIORAG_DMN_LOTE_MAX_VALENCIA          — default 5
    BIORAG_DMN_LOTE_MAX_PMI_HEBBIANO      — default 10
    BIORAG_DMN_VALENCIA_PESO_UMBRAL       — default 0.4
    BIORAG_DMN_VALENCIA_DIAS_RECIENTES    — default 7
    BIORAG_DMN_REFLEXION_INTERVALO_HORAS  — default 12
    BIORAG_DMN_ESTADO_PATH                — default "estado_hormiga.json"
"""

import os
import json
import time
import logging
import urllib.request
import urllib.error
import sqlite3

logger = logging.getLogger("BioRAG.DMN.Reflexion")

# --- Configuración ---------------------------------------------------------

# Multi-key: GEMINI_API_KEYS (comma-separated) takes precedence.
# Falls back to legacy GEMINI_API_KEY (single) if前者 is empty.
_KEYS_RAW = os.environ.get("GEMINI_API_KEYS", "")
if _KEYS_RAW.strip():
    GEMINI_API_KEYS = [k.strip() for k in _KEYS_RAW.split(",") if k.strip()]
else:
    _legacy = os.environ.get("GEMINI_API_KEY", "")
    GEMINI_API_KEYS = [_legacy.strip()] if _legacy.strip() else []

GEMINI_MODEL = os.environ.get("BIORAG_GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_ENDPOINT_TPL = "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"

UMBRAL_CONFIANZA_ACEPTAR = float(os.environ.get("BIORAG_DMN_UMBRAL_ACEPTAR", "0.75"))
UMBRAL_CONFIANZA_ELIMINAR = float(os.environ.get("BIORAG_DMN_UMBRAL_ELIMINAR", "0.70"))
MAX_INSIGHTS_POR_LOTE = int(os.environ.get("BIORAG_DMN_LOTE_MAX_INSIGHTS", "10"))
MAX_SINAPSIS_POR_LOTE = int(os.environ.get("BIORAG_DMN_LOTE_MAX_SINAPSIS", "5"))
MAX_VALENCIA_POR_LOTE = int(os.environ.get("BIORAG_DMN_LOTE_MAX_VALENCIA", "5"))
MAX_PMI_HEBBIANO_POR_LOTE = int(os.environ.get("BIORAG_DMN_LOTE_MAX_PMI_HEBBIANO", "10"))
VALENCIA_PESO_UMBRAL = float(os.environ.get("BIORAG_DMN_VALENCIA_PESO_UMBRAL", "0.4"))
VALENCIA_ACTIVIDAD_RECIENTE_DIAS = float(os.environ.get("BIORAG_DMN_VALENCIA_DIAS_RECIENTES", "7"))
TIMEOUT_RED_SEGUNDOS = 30
ESTADO_HORMIGA_PATH = os.environ.get("BIORAG_DMN_ESTADO_PATH", "estado_hormiga.json")

# Procesamiento por lotes dentro de cada nodo: la semilla se envía con
# grupos de N sinapsis por llamada. El estado guarda el lote exacto para
# reanudar tras fallos (tokens, red, quota).
TAMANO_LOTE_SINAPSIS = int(os.environ.get("BIORAG_HORMIGA_LOTE_SINAPSIS", "10"))

# Piso anti-sobrepoda: nunca dejar un nodo con menos de N conexiones.
# Las eliminaciones que romperían el piso se aplazan (no se ejecutan).
MIN_CONEXIONES_POR_NODO = int(os.environ.get("BIORAG_HORMIGA_MIN_CONEXIONES", "5"))

# Pre-filtro determinista (corte sin juicio semántico). Default OFF:
# el diseño es que Gemini juzga TODAS las sinapsis con su contenido.
PRE_FILTRO_ACTIVO = os.environ.get("BIORAG_HORMIGA_PRE_FILTRO", "0") == "1"

# Benchmark gate: mini-eval de recall cada N nodos procesados.
BENCHMARK_CADA_N_NODOS = int(os.environ.get("BIORAG_HORMIGA_BENCHMARK_CADA_N", "25"))
BENCHMARK_TOLERANCIA = float(os.environ.get("BIORAG_HORMIGA_BENCHMARK_TOLERANCIA", "2.0"))

# Two-strike pruning para latentes: 1ra marca atenúa, 2da manda a cuarentena.
# Confianza >= este umbral salta el strike y cuarentena directo.
UMBRAL_ELIMINAR_LATENTE_DIRECTO = float(os.environ.get("BIORAG_HORMIGA_UMBRAL_LATENTE_DIRECTO", "0.90"))

ACCIONES_VALIDAS = {"aceptar", "eliminar", "fusionar", "reponderar", "reforzar_valencia", "ignorar"}

PROMPT_SISTEMA = """Eres un analizador semántico que evalúa la calidad de un grafo de \
conocimiento. Recibes un nodo con su contenido completo, sus conexiones, y los catálogos \
disponibles. Tu trabajo: decidir qué está bien y qué necesita corrección.

Vas a recibir un JSON con:
- "nodo": contenido, categoría, peso, sinónimos, dimensiones actuales, lexnames WordNet
- "sinapsis_directas": conexiones directas con su tipo, peso, y contenido del nodo destino
- "sinapsis_latentes": conexiones indirectas (calculadas por saltos)
- "catalogo_disponible": lista de dimensiones y categorías disponibles para clasificar

Para CADA capa que evalúes, devolvé un veredicto. Respondé SOLO con JSON válido, sin \
texto antes ni después, con este esquema exacto:

{"veredictos": [
  {"capa": "<dimension|sinonimo|categoria|contenido|sinapsis_directa|sinapsis_latente>",
   "ref": "<nombre de la dimensión, sinónimo, o destino de la sinapsis>",
   "accion": "<mantener|eliminar|agregar|reemplazar|reponderar|confirmar|enriquecer|ignorar>",
   "confianza": 0.0,
   "peso_sugerido": null,
   "valor_sugerido": null,
   "justificacion": "<una frase breve>"}
]}

ACCIONES POR CAPA:
- "dimension": agregar (si falta), eliminar (si sobra), reemplazar (si está mal), ignorar
- "sinonimo": agregar (si falta), eliminar (si es ruido), reemplazar (si es vago), ignorar
- "categoria": reemplazar (si está mal), ignorar (si es correcta)
- "contenido": enriquecer (si es corto/vago), ignorar (si es suficiente)
- "sinapsis_directa": mantener, eliminar (si es espuria), reponderar, fusionar, ignorar
- "sinapsis_latente": confirmar, eliminar, reponderar, ignorar

REGLAS DE DECISIÓN:

1. DIMENSIONES: El nodo debe tener las dimensiones que correspondan a su contenido. \
Usá el catálogo disponible para elegir. Si el contenido habla de programación → debe \
tener "dominio_tecnico". Si habla de aprendizaje → debe tener "intencion_aprender". \
Si tiene una dimensión que no corresponde → eliminar.

2. SINÓNIMOS: Deben ser palabras que alguien usaría para buscar este nodo. \
Si falta un término clave del contenido → agregar. Si un sinónimo es demasiado \
genérico (ej: "cosa", "info") → eliminar.

3. CATEGORÍA: Usá el catálogo disponible. Si el contenido describe un error resuelto \
→ debe ser "Lesson". Si describe una decisión de diseño → "Architecture". Si describe \
un procedimiento → "Protocol".

4. SINAPSIS DIRECTAS: Para cada conexión, compará el contenido del nodo semilla con \
el contenido del nodo destino. Si hablan de cosas distintas → eliminar. Si comparten \
solo palabras genéricas (nombre de proyecto, persona, términos vagos) → eliminar. \
REGLA ESTRICTA para conexiones tipo "pmi_hebbiano": estas fueron creadas por \
co-ocurrencia estadística, NO por comprensión semántica. Si la justificación requiere \
inventar un puente conceptual que NO está en los contenidos → ELIMINAR.

5. SINAPSIS LATENTES: Mismo criterio que directas, pero estas son conexiones \
indirectas (por saltos). Son más débiles por naturaleza. Si no hay relación real \
entre los contenidos → eliminar.

6. CONTENIDO: Si el contenido es menor a 100 caracteres o demasiado vago → \
"enriquecer" con valor_sugerido que expanda el contenido.

CONFIANZA: Tu certeza en la decisión (0.0 a 1.0). Sé conservador. \
Ante la duda en sinapsis pmi_hebbiano → preferí ELIMINAR (las espurias contaminan). \
Para otros tipos → "ignorar" con confianza baja es preferible a una decisión errónea."""


# --- Pre-filtrado determinista (ahorro de tokens, cero costo API) -----------

# Configuración de pre-filtrado
UMBRAL_PRE_FILTRADO_PESO_ALTO = float(os.environ.get("BIORAG_DMN_PF_PESO_ALTO", "0.80"))
UMBRAL_PRE_FILTRADO_PESO_BAJO = float(os.environ.get("BIORAG_DMN_PF_PESO_BAJO", "0.20"))
UMBRAL_PRE_FILTRADO_JACCARD = float(os.environ.get("BIORAG_DMN_PF_JACCARD", "0.30"))
PRE_FILTRADO_BATCH_SIZE = int(os.environ.get("BIORAG_DMN_PF_BATCH_SIZE", "15"))


def _calcular_jaccard_tokens(texto_a, texto_b):
    """
    Calcula coeficiente de Jaccard simple sobre tokens (palabras).
    Rápido, sin dependencias externas.
    """
    if not texto_a or not texto_b:
        return 0.0
    tokens_a = set(texto_a.lower().split())
    tokens_b = set(texto_b.lower().split())
    if not tokens_a or not tokens_b:
        return 0.0
    interseccion = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(interseccion) / len(union) if union else 0.0


def _pre_filtrar_conexiones(seed_contenido, sinapsis_directas, sinapsis_latentes):
    """
    Pre-filtra conexiones antes de enviar a Gemini.
    
    Retorna:
        candidatas_directas: list — las que necesitan evaluación LLM
        candidatas_latentes: list — las que necesitan evaluación LLM
        cortadas_directas: list — las que se cortan directo (sin LLM)
        cortadas_latentes: list — las que se cortan directo (sin LLM)
        mantenidas_directas: list — las que se mantienen directo (sin LLM)
        mantenidas_latentes: list — las que se mantienen directo (sin LLM)
    
    Reglas:
        SKIP (mantener directo):
            - peso > UMBRAL_PRE_FILTRADO_PESO_ALTO
            - tipo == 'sinonimo_explicito'
            - Jaccard(seed, destino) > UMBRAL_PRE_FILTRADO_JACCARD
        CORTAR directo (sin LLM):
            - peso < UMBRAL_PRE_FILTRADO_PESO_BAJO AND tipo == 'pmi_hebbiano'
        EVALUAR (Gemini):
            - Todo lo demás
    """
    candidatas_directas = []
    candidatas_latentes = []
    cortadas_directas = []
    cortadas_latentes = []
    mantenidas_directas = []
    mantenidas_latentes = []

    # --- Sinapsis directas ---
    for s in sinapsis_directas:
        peso = s.get("peso", 0.0)
        tipo = s.get("tipo", "")
        contenido_dest = s.get("contenido_destino", "")
        destino = s.get("destino", "")

        # SKIP: conexión fuerte
        if peso >= UMBRAL_PRE_FILTRADO_PESO_ALTO:
            mantenidas_directas.append(s)
            continue

        # SKIP: sinonimo explícito (siempre válido)
        if tipo == "sinonimo_explicito":
            mantenidas_directas.append(s)
            continue

        # SKIP: alta similitud textual
        jaccard = _calcular_jaccard_tokens(seed_contenido, contenido_dest)
        if jaccard >= UMBRAL_PRE_FILTRADO_JACCARD:
            mantenidas_directas.append(s)
            continue

        # CORTAR directo: espurio obvio
        if peso < UMBRAL_PRE_FILTRADO_PESO_BAJO and tipo == "pmi_hebbiano":
            cortadas_directas.append(s)
            continue

        # EVALUAR: necesita LLM
        candidatas_directas.append(s)

    # --- Sinapsis latentes ---
    for s in sinapsis_latentes:
        peso = s.get("peso_atenuado", 0.0)
        contenido_dest = s.get("contenido_destino", "")

        # SKIP: conexión fuerte
        if peso >= UMBRAL_PRE_FILTRADO_PESO_ALTO:
            mantenidas_latentes.append(s)
            continue

        # SKIP: alta similitud textual
        jaccard = _calcular_jaccard_tokens(seed_contenido, contenido_dest)
        if jaccard >= UMBRAL_PRE_FILTRADO_JACCARD:
            mantenidas_latentes.append(s)
            continue

        # CORTAR directo: peso muy bajo
        if peso < UMBRAL_PRE_FILTRADO_PESO_BAJO:
            cortadas_latentes.append(s)
            continue

        # EVALUAR: necesita LLM
        candidatas_latentes.append(s)

    return (
        candidatas_directas, candidatas_latentes,
        cortadas_directas, cortadas_latentes,
        mantenidas_directas, mantenidas_latentes,
    )


# --- Construcción de payload por nodo (6 capas + catálogos) -----------------

# Acciones válidas por capa (para validación determinista)
ACCIONES_POR_CAPA = {
    "dimension": {"agregar", "eliminar", "reemplazar", "mantener", "ignorar"},
    "sinonimo": {"agregar", "eliminar", "reemplazar", "ignorar"},
    "categoria": {"reemplazar", "ignorar"},
    "contenido": {"enriquecer", "ignorar"},
    "sinapsis_directa": {"mantener", "eliminar", "reponderar", "fusionar", "ignorar"},
    "sinapsis_latente": {"confirmar", "eliminar", "reponderar", "ignorar"},
}


def _construir_payload_nodo(concepto, cerebro):
    """
    Arma el JSON completo con las 6 capas de un nodo + catálogos para Gemini.
    
    Capas:
    1. Nodo: contenido, categoría, peso, sinónimos, dimensiones actuales
    2. Sinapsis directas: conexiones en tabla sinapsis (tipo, peso, contenido destino)
    3. Sinapsis latentes: conexiones en tabla sinapsis_latentes (peso, saltos)
    4. Catálogo de dimensiones: todas las disponibles con nombre, tipo, descripción
    5. Catálogo de categorías: todas las disponibles con nombre, descripción
    6. WordNet: (se calcula al vuelo, aquí preparamos los lexnames)
    """
    conn = cerebro.conn
    cursor = conn.cursor()

    # --- 1. NODO: contenido, categoría, peso, sinónimos ---
    cursor.execute("""
        SELECT id, contenido, categoria, peso_sinaptico, sinonimos, 
               valencia_somatica, estado
        FROM largo_plazo 
        WHERE concepto = ?
    """, (concepto,))
    row = cursor.fetchone()
    if not row:
        return None

    nodo_id, contenido, categoria_id, peso, sinonimos_str, valencia, estado = row
    if estado != "activo":
        return None

    # Sinónimos como lista
    sinonimos = [s.strip() for s in (sinonimos_str or "").split(",") if s.strip()]

    # Categoría actual
    cursor.execute("SELECT name, description FROM categories WHERE id = ?", (categoria_id,))
    cat_row = cursor.fetchone()
    categoria_actual = {"nombre": cat_row[0], "descripcion": cat_row[1]} if cat_row else {"nombre": "General", "descripcion": ""}

    # --- 2. DIMENSIONES ACTUALES del nodo ---
    cursor.execute("""
        SELECT ds.name, ds.description, td.nombre as tipo
        FROM largo_plazo_dimensiones ld
        JOIN dimensiones_semanticas ds ON ld.dimension_id = ds.id
        JOIN tipos_dimension td ON ds.tipo_id = td.id
        WHERE ld.concepto = ?
        ORDER BY ds.name
    """, (concepto,))
    dimensiones_actuales = []
    for nombre, desc, tipo in cursor.fetchall():
        dimensiones_actuales.append({
            "nombre": nombre,
            "tipo": tipo,
            "descripcion": desc or ""
        })

    # --- 3. SINAPSIS DIRECTAS (tabla sinapsis) ---
    cursor.execute("""
        SELECT s.destino, s.tipo, s.peso, 
               COALESCE(lp.contenido, '') as contenido_destino
        FROM sinapsis s
        LEFT JOIN largo_plazo lp ON lp.concepto = s.destino
        WHERE s.origen = ?
        ORDER BY s.tipo, s.peso DESC
    """, (concepto,))
    sinapsis_directas = []
    for destino, tipo, peso_dest, cont_dest in cursor.fetchall():
        sinapsis_directas.append({
            "destino": destino,
            "tipo": tipo,
            "peso": peso_dest,
            "contenido_destino": cont_dest[:300] if cont_dest else ""
        })

    # --- 4. SINAPSIS LATENTES (tabla sinapsis_latentes) ---
    cursor.execute("""
        SELECT sl.destino, sl.peso_atenuado, sl.saltos, sl.pmi_score,
               COALESCE(lp.contenido, '') as contenido_destino
        FROM sinapsis_latentes sl
        LEFT JOIN largo_plazo lp ON lp.concepto = sl.destino
        WHERE sl.origen = ?
        ORDER BY sl.peso_atenuado DESC
    """, (concepto,))
    sinapsis_latentes = []
    for destino, peso_lat, saltos, pmi, cont_dest in cursor.fetchall():
        sinapsis_latentes.append({
            "destino": destino,
            "peso_atenuado": peso_lat,
            "saltos": saltos,
            "pmi_score": pmi,
            "contenido_destino": cont_dest[:300] if cont_dest else ""
        })

    # --- 5. CATÁLOGO DE DIMENSIONES (todas las disponibles) ---
    cursor.execute("""
        SELECT ds.name, ds.description, td.nombre as tipo
        FROM dimensiones_semanticas ds
        JOIN tipos_dimension td ON ds.tipo_id = td.id
        ORDER BY td.nombre, ds.name
    """)
    catalogo_dimensiones = []
    for nombre, desc, tipo in cursor.fetchall():
        catalogo_dimensiones.append({
            "nombre": nombre,
            "tipo": tipo,
            "descripcion": desc or ""
        })

    # --- 6. CATÁLOGO DE CATEGORÍAS (todas las disponibles) ---
    cursor.execute("SELECT name, description FROM categories ORDER BY id")
    catalogo_categorias = []
    for nombre, desc in cursor.fetchall():
        catalogo_categorias.append({
            "nombre": nombre,
            "descripcion": desc or ""
        })

    # --- 7. WORDNET LEXNAMES (se calculan al vuelo) ---
    try:
        from core.clasificador_wordnet import clasificar_texto
        wordnet_clasif = clasificar_texto(contenido or "")
        wordnet_lexnames = sorted(set(
            lexname 
            for lexnames_set in wordnet_clasif.values() 
            for lexname in lexnames_set
        ))
    except Exception:
        wordnet_lexnames = []

    # --- PRE-FILTRADO (opcional, default OFF) ---
    # Visión de diseño: TODAS las sinapsis las juzga Gemini con contenido.
    # El pre-filtro determinista corta sin juicio semántico — solo se activa
    # con BIORAG_HORMIGA_PRE_FILTRO=1 si hace falta ahorrar tokens a escala.
    if PRE_FILTRO_ACTIVO:
        (
            candidatas_directas, candidatas_latentes,
            cortadas_directas, cortadas_latentes,
            mantenidas_directas, mantenidas_latentes,
        ) = _pre_filtrar_conexiones(contenido or "", sinapsis_directas, sinapsis_latentes)
    else:
        candidatas_directas, candidatas_latentes = sinapsis_directas, sinapsis_latentes
        cortadas_directas, cortadas_latentes = [], []
        mantenidas_directas, mantenidas_latentes = [], []

    total_original = len(sinapsis_directas) + len(sinapsis_latentes)
    total_candidatas = len(candidatas_directas) + len(candidatas_latentes)
    total_cortadas = len(cortadas_directas) + len(cortadas_latentes)
    total_mantenidas = len(mantenidas_directas) + len(mantenidas_latentes)

    logger.info(
        f"[Pre-filtrado] {concepto}: {total_original} conexiones → "
        f"{total_candidatas} candidatas (LLM), {total_cortadas} cortadas, "
        f"{total_mantenidas} mantenidas. Ahorro: {total_original - total_candidatas} tokens."
    )

    # --- ARMAR PAYLOAD (solo candidatas para Gemini) ---
    payload = {
        "nodo": {
            "id": nodo_id,
            "concepto": concepto,
            "contenido": contenido or "",
            "categoria_actual": categoria_actual,
            "peso": peso,
            "valencia_somatica": valencia,
            "sinonimos_actuales": sinonimos,
            "dimensiones_actuales": dimensiones_actuales,
            "wordnet_lexnames": wordnet_lexnames,
        },
        "sinapsis_directas": candidatas_directas,
        "sinapsis_latentes": candidatas_latentes,
        "catalogo_disponible": {
            "dimensiones": catalogo_dimensiones,
            "categorias": catalogo_categorias,
        },
        "_meta_prefiltrado": {
            "total_original": total_original,
            "candidatas": total_candidatas,
            "cortadas_directo": total_cortadas,
            "mantenidas_directo": total_mantenidas,
            "ahorro_tokens_aprox": (total_original - total_candidatas) * 75,
        },
    }

    return payload, {
        "cortadas_directas": cortadas_directas,
        "cortadas_latentes": cortadas_latentes,
        "mantenidas_directas": mantenidas_directas,
        "mantenidas_latentes": mantenidas_latentes,
    }


# --- Construcción del lote (legacy — batch por candidatos) ----------------

def _llamar_gemini_nodo(payload):
    """
    Envía el payload de UN nodo a Gemini con el prompt genérico.
    Devuelve lista de veredictos, o None si falla.
    Soporta multi-key rotation (429/404 → siguiente key).
    """
    if not GEMINI_API_KEYS:
        logger.warning("No hay GEMINI_API_KEYS configuradas.")
        return None
    if not payload:
        return None

    payload_usuario = json.dumps(payload, ensure_ascii=False)

    body = {
        "system_instruction": {"parts": [{"text": PROMPT_SISTEMA}]},
        "contents": [{"role": "user", "parts": [{"text": payload_usuario}]}],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
        },
    }

    ultimo_error = None
    for idx, key in enumerate(GEMINI_API_KEYS):
        key_preview = key[:12] + "..." if len(key) > 12 else key
        url = f"{GEMINI_ENDPOINT_TPL.format(modelo=GEMINI_MODEL)}?key={key}"
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_RED_SEGUNDOS) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            texto = data["candidates"][0]["content"]["parts"][0]["text"]
            resultado = json.loads(texto)
            # Extraer veredictos del JSON
            if isinstance(resultado, dict) and "veredictos" in resultado:
                return resultado["veredictos"]
            elif isinstance(resultado, list):
                return resultado
            else:
                logger.warning(f"Gemini devolvió estructura inesperada: {type(resultado)}")
                return None
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="ignore")
            if e.code in (429, 400, 404):
                logger.warning(
                    f"[Key {idx}/{len(GEMINI_API_KEYS)}] {key_preview} "
                    f"HTTP {e.code}: {error_body[:200]}"
                )
                ultimo_error = f"HTTP {e.code}"
                continue
            else:
                logger.error(
                    f"[Key {idx}/{len(GEMINI_API_KEYS)}] {key_preview} "
                    f"HTTP {e.code}: {error_body[:500]}"
                )
                ultimo_error = f"HTTP {e.code}"
                return None
        except urllib.error.URLError as e:
            logger.warning(f"[Key {idx}] {key_preview} red: {e}")
            ultimo_error = str(e)
            continue
        except (KeyError, IndexError, TypeError) as e:
            logger.warning(f"[Key {idx}] {key_preview} estructura: {e}")
            ultimo_error = str(e)
            return None
        except json.JSONDecodeError as e:
            logger.warning(f"[Key {idx}] {key_preview} JSON inválido: {e}")
            ultimo_error = str(e)
            return None

    logger.error(f"Todas las {len(GEMINI_API_KEYS)} keys agotadas. Último: {ultimo_error}")
    return None


# --- Aplicación determinista de veredictos -----------------------------------

def _aplicar_veredicto(cerebro, veredicto):
    """
    Aplica UN veredicto con reglas deterministas. Nunca confía ciegamente
    en el LLM: valida esquema, acción conocida y umbral de confianza antes
    de tocar la base de datos. Default Deny — si algo no calza, se ignora.
    """
    id_ = veredicto.get("id", "")
    accion = veredicto.get("accion", "ignorar")
    try:
        confianza = float(veredicto.get("confianza", 0.0))
    except (TypeError, ValueError):
        confianza = 0.0
    justificacion = veredicto.get("justificacion", "")

    if accion not in ACCIONES_VALIDAS or ":" not in id_:
        logger.warning(f"[DMN Fase2] Veredicto malformado, ignorado: {veredicto}")
        return False

    tipo, _, ref = id_.partition(":")
    conn = cerebro.conn
    cursor = conn.cursor()

    try:
        if accion == "eliminar" and confianza >= UMBRAL_CONFIANZA_ELIMINAR:
            if tipo == "nodo":
                cursor.execute("UPDATE largo_plazo SET estado = 'dormido' WHERE id = ?", (ref,))
            elif tipo == "sinapsis":
                origen, _, destino = ref.partition("->")
                cursor.execute(
                    "DELETE FROM sinapsis_latentes WHERE origen = ? AND destino = ?",
                    (origen, destino),
                )
            elif tipo == "sinapsis_directa":
                origen, _, destino = ref.partition("->")
                cursor.execute(
                    "DELETE FROM sinapsis WHERE origen = ? AND destino = ?",
                    (origen, destino),
                )
            logger.info(f"[DMN Fase2] ELIMINADO {id_} (confianza={confianza:.2f}): {justificacion}")

        elif accion == "aceptar" and confianza >= UMBRAL_CONFIANZA_ACEPTAR and tipo == "nodo":
            contenido_mejorado = veredicto.get("contenido_mejorado")
            if contenido_mejorado:
                cursor.execute(
                    "UPDATE largo_plazo SET contenido = ?, peso_sinaptico = MIN(peso_sinaptico + 0.1, 1.0) WHERE id = ?",
                    (contenido_mejorado, ref),
                )
            else:
                cursor.execute(
                    "UPDATE largo_plazo SET peso_sinaptico = MIN(peso_sinaptico + 0.1, 1.0) WHERE id = ?",
                    (ref,),
                )
            logger.info(f"[DMN Fase2] ACEPTADO {id_} (confianza={confianza:.2f})")

        elif accion == "reponderar" and confianza >= UMBRAL_CONFIANZA_ACEPTAR and tipo == "sinapsis":
            try:
                nuevo_peso = min(max(float(veredicto.get("peso_sugerido", 0.5)), 0.0), 1.0)
            except (TypeError, ValueError):
                nuevo_peso = 0.5
            origen, _, destino = ref.partition("->")
            cursor.execute(
                "UPDATE sinapsis_latentes SET peso_atenuado = ? WHERE origen = ? AND destino = ?",
                (nuevo_peso, origen, destino),
            )
            logger.info(f"[DMN Fase2] REPONDERADO {id_} -> {nuevo_peso:.2f} (confianza={confianza:.2f})")

        elif accion == "reponderar" and confianza >= UMBRAL_CONFIANZA_ACEPTAR and tipo == "sinapsis_directa":
            try:
                nuevo_peso = min(max(float(veredicto.get("peso_sugerido", 0.5)), 0.0), 1.0)
            except (TypeError, ValueError):
                nuevo_peso = 0.5
            origen, _, destino = ref.partition("->")
            cursor.execute(
                "UPDATE sinapsis SET peso = ? WHERE origen = ? AND destino = ?",
                (nuevo_peso, origen, destino),
            )
            logger.info(f"[DMN Fase2] REPONDERADO {id_} -> {nuevo_peso:.2f} (confianza={confianza:.2f})")

        elif accion == "fusionar" and confianza >= UMBRAL_CONFIANZA_ACEPTAR and tipo == "nodo":
            # Nunca se fusiona sola. Solo se marca para revisión humana explícita.
            cursor.execute("UPDATE largo_plazo SET estado = 'candidato_fusion' WHERE id = ?", (ref,))
            logger.info(f"[DMN Fase2] MARCADO PARA FUSIÓN {id_} (confianza={confianza:.2f}) — requiere revisión humana")

        elif accion == "reforzar_valencia" and confianza >= UMBRAL_CONFIANZA_ACEPTAR and tipo == "nodo":
            try:
                nueva_valencia = min(max(float(veredicto.get("valencia_sugerida", 0.5)), 0.0), 1.0)
            except (TypeError, ValueError):
                nueva_valencia = 0.5
            cursor.execute(
                "UPDATE largo_plazo SET valencia_somatica = ?, ultimo_acceso = ? WHERE id = ?",
                (nueva_valencia, time.time(), ref),
            )
            logger.info(f"[DMN Fase2] VALENCIA REFORZADA {id_} -> {nueva_valencia:.2f} (confianza={confianza:.2f}): {justificacion}")

        else:
            logger.info(
                f"[DMN Fase2] IGNORADO {id_} (accion={accion}, confianza={confianza:.2f}, "
                f"bajo umbral o combinación tipo/acción no soportada)"
            )
            return True  # no es error, es una decisión válida de no-acción

        conn.commit()
        return True

    except sqlite3.Error as e:
        conn.rollback()
        logger.error(f"[DMN Fase2] Error de DB aplicando veredicto {id_}: {e}")
        return False


def _mover_a_cuarentena(concepto, destino, tabla, cerebro, motivo="", confianza=0.0):
    """
    Soft-delete: mueve una sinapsis a sinapsis_cuarentena antes de borrarla.
    Nada se pierde de verdad — toda poda es reversible durante 30 días.

    tabla: "sinapsis" (directa) o "sinapsis_latentes" (latente).
    Retorna True si se movió y eliminó, False si no existía.
    """
    cursor = cerebro.conn.cursor()
    ahora = time.time()

    if tabla == "sinapsis":
        cursor.execute(
            "SELECT tipo, peso FROM sinapsis WHERE origen = ? AND destino = ?",
            (concepto, destino)
        )
        row = cursor.fetchone()
        if not row:
            return False
        tipo, peso = row
        datos_extra = None
        delete_sql = "DELETE FROM sinapsis WHERE origen = ? AND destino = ?"
    else:  # sinapsis_latentes
        cursor.execute(
            "SELECT peso_atenuado, saltos, pmi_score FROM sinapsis_latentes "
            "WHERE origen = ? AND destino = ?",
            (concepto, destino)
        )
        row = cursor.fetchone()
        if not row:
            return False
        peso, saltos, pmi = row
        tipo = "latente"
        datos_extra = json.dumps({"saltos": saltos, "pmi_score": pmi}, ensure_ascii=False)
        delete_sql = "DELETE FROM sinapsis_latentes WHERE origen = ? AND destino = ?"

    cursor.execute(
        "INSERT INTO sinapsis_cuarentena "
        "(origen, destino, tipo, tabla_origen, peso, datos_extra, motivo, confianza, eliminado_en) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (concepto, destino, tipo, tabla, peso, datos_extra, motivo, confianza, ahora)
    )
    cursor.execute(delete_sql, (concepto, destino))
    return True


def _restaurar_cuarentena(cerebro, desde_timestamp=0, max_items=None):
    """
    Restaura sinapsis de la cuarentena (soft-delete rollback).
    Se usa si el benchmark cae por debajo del umbral (auto-protección).

    desde_timestamp: solo restaurar eliminadas después de este momento.
    max_items: límite de restauraciones (None = todas las del tramo).
    Retorna: cantidad restaurada.
    """
    cursor = cerebro.conn.cursor()
    sql = (
        "SELECT id, origen, destino, tipo, tabla_origen, peso, datos_extra "
        "FROM sinapsis_cuarentena WHERE restaurado = 0 AND eliminado_en >= ? "
        "ORDER BY eliminado_en DESC"
    )
    if max_items:
        sql += f" LIMIT {int(max_items)}"
    cursor.execute(sql, (desde_timestamp,))

    restauradas = 0
    for id_, origen, destino, tipo, tabla, peso, datos_extra in cursor.fetchall():
        if tabla == "sinapsis":
            cursor.execute(
                "INSERT OR IGNORE INTO sinapsis (origen, destino, tipo, peso, creado_en) "
                "VALUES (?, ?, ?, ?, ?)",
                (origen, destino, tipo or "pmi_hebbiano", peso, time.time())
            )
        else:
            extra = json.loads(datos_extra) if datos_extra else {}
            cursor.execute(
                "INSERT OR IGNORE INTO sinapsis_latentes "
                "(origen, destino, peso_atenuado, saltos, pmi_score, calculado_en) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (origen, destino, peso, extra.get("saltos", 2),
                 extra.get("pmi_score", 0.0), time.time())
            )
        cursor.execute("UPDATE sinapsis_cuarentena SET restaurado = 1 WHERE id = ?", (id_,))
        restauradas += 1

    if restauradas > 0:
        cerebro.conn.commit()
        logger.warning(f"[Hormiguita] {restauradas} sinapsis RESTAURADAS desde cuarentena")
    return restauradas


def _benchmark_gate(cerebro, estado):
    """
    Mini-eval determinista de recall@5 sobre subset congelado de casos QA.
    Mide el impacto REAL de la poda — la hormiguita se evalúa a sí misma.

    - Subset: casos positivos (sin dormido/negativo, para no mutar estados),
      cada K-ésimo para reproducibilidad total.
    - Primera corrida: guarda baseline en estado["benchmark_baseline"].
    - Corridas siguientes: si recall cae más que BENCHMARK_TOLERANCIA puntos,
      AUTO-RESTAURA la cuarentena eliminada desde el último gate bueno.

    Retorna: dict con resultado, o None si no hay casos.
    """
    casos_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "scripts", "casos_qa_baseline_v1.jsonl"
    )
    if not os.path.exists(casos_path):
        logger.warning("[Benchmark] No existe casos_qa_baseline_v1.jsonl — gate omitido")
        return None

    casos = []
    with open(casos_path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                casos.append(json.loads(line))

    # Subset determinista: positivos, no-dormidos, muestreo uniforme
    positivos = [
        c for c in casos
        if c.get("concepto_esperado") and c.get("categoria") not in ("dormido", "negativo")
    ]
    if not positivos:
        return None
    paso = max(1, len(positivos) // 40)
    subset = positivos[::paso][:40]

    hits = 0
    for caso in subset:
        results, _ = cerebro.buscar_por_frase(
            caso["query"], profundidad="activos", limite=5,
            ignore_peso_sinaptico=True
        )
        returned = [r[0] for r in results]
        if caso["concepto_esperado"] in returned:
            hits += 1

    recall = (hits / len(subset)) * 100.0
    resultado = {
        "timestamp": time.time(),
        "recall_at5": round(recall, 2),
        "casos": len(subset),
        "hits": hits,
    }

    baseline = estado.get("benchmark_baseline")
    if baseline is None:
        # Primera medición: ESTE es el baseline. Se guarda y no se juzga.
        estado["benchmark_baseline"] = recall
        estado["benchmark_ultimo_bueno_ts"] = time.time()
        resultado["evento"] = "baseline_establecido"
        logger.info(f"[Benchmark] Baseline establecido: {recall:.2f}% ({len(subset)} casos)")
        return resultado

    delta = recall - baseline
    resultado["baseline"] = baseline
    resultado["delta"] = round(delta, 2)

    if delta < -BENCHMARK_TOLERANCIA:
        # CAÍDA REAL: auto-restaurar lo eliminado desde el último gate bueno
        desde = estado.get("benchmark_ultimo_bueno_ts", 0)
        restauradas = _restaurar_cuarentena(cerebro, desde_timestamp=desde)
        resultado["evento"] = "ALERTA_auto_restauracion"
        resultado["restauradas"] = restauradas
        estado["alerta_benchmark"] = {
            "timestamp": time.time(),
            "recall": recall,
            "baseline": baseline,
            "delta": round(delta, 2),
            "restauradas": restauradas,
        }
        logger.warning(
            f"[Benchmark] ⚠️ CAÍDA de recall: {recall:.2f}% vs baseline {baseline:.2f}% "
            f"(delta {delta:+.2f}). {restauradas} sinapsis auto-restauradas."
        )
    else:
        estado["benchmark_ultimo_bueno_ts"] = time.time()
        resultado["evento"] = "ok"
        logger.info(f"[Benchmark] OK: {recall:.2f}% (baseline {baseline:.2f}%, delta {delta:+.2f})")

    return resultado


def _aplicar_veredicto_nodo(concepto, veredicto, cerebro):
    """
    Aplica UN veredicto del nuevo formato (capa + ref) con reglas deterministas.
    Cada capa tiene su propia lógica SQL.
    
    Formato del veredicto:
    {
        "capa": "dimension|sinonimo|categoria|contenido|sinapsis_directa|sinapsis_latente",
        "ref": "nombre de la dimensión, sinónimo, o destino de la sinapsis",
        "accion": "mantener|eliminar|agregar|reemplazar|reponderar|confirmar|enriquecer|ignorar",
        "confianza": 0.0,
        "peso_sugerido": null,
        "valor_sugerido": null,
        "justificacion": "..."
    }
    """
    capa = veredicto.get("capa", "")
    ref = veredicto.get("ref", "")
    accion = veredicto.get("accion", "ignorar")
    try:
        confianza = float(veredicto.get("confianza", 0.0))
    except (TypeError, ValueError):
        confianza = 0.0
    justificacion = veredicto.get("justificacion", "")
    peso_sugerido = veredicto.get("peso_sugerido")
    valor_sugerido = veredicto.get("valor_sugerido")

    # Validar que la capa y acción sean compatibles
    if capa not in ACCIONES_POR_CAPA:
        logger.warning(f"[Hormiguita] Capa desconocida: {capa}")
        return False
    if accion not in ACCIONES_POR_CAPA[capa]:
        logger.warning(f"[Hormiguita] Acción '{accion}' no válida para capa '{capa}'")
        return False

    conn = cerebro.conn
    cursor = conn.cursor()

    try:
        # --- DIMENSION ---
        if capa == "dimension" and accion == "agregar" and confianza >= UMBRAL_CONFIANZA_ACEPTAR:
            cursor.execute("SELECT id FROM dimensiones_semanticas WHERE name = ?", (ref,))
            dim_row = cursor.fetchone()
            if dim_row:
                cursor.execute(
                    "INSERT OR IGNORE INTO largo_plazo_dimensiones (concepto, dimension_id) VALUES (?, ?)",
                    (concepto, dim_row[0])
                )
                logger.info(f"[Hormiguita] DIM +{ref} en {concepto} ({confianza:.2f}): {justificacion}")
            else:
                logger.warning(f"[Hormiguita] Dimensión '{ref}' no existe en catálogo")
                return False

        elif capa == "dimension" and accion == "eliminar" and confianza >= UMBRAL_CONFIANZA_ELIMINAR:
            cursor.execute("SELECT id FROM dimensiones_semanticas WHERE name = ?", (ref,))
            dim_row = cursor.fetchone()
            if dim_row:
                cursor.execute(
                    "DELETE FROM largo_plazo_dimensiones WHERE concepto = ? AND dimension_id = ?",
                    (concepto, dim_row[0])
                )
                logger.info(f"[Hormiguita] DIM -{ref} en {concepto} ({confianza:.2f}): {justificacion}")

        elif capa == "dimension" and accion == "reemplazar" and confianza >= UMBRAL_CONFIANZA_ACEPTAR:
            # valor_sugerido contiene el nuevo nombre de dimensión
            if valor_sugerido:
                cursor.execute("SELECT id FROM dimensiones_semanticas WHERE name = ?", (ref,))
                old_dim = cursor.fetchone()
                cursor.execute("SELECT id FROM dimensiones_semanticas WHERE name = ?", (valor_sugerido,))
                new_dim = cursor.fetchone()
                if old_dim and new_dim:
                    cursor.execute(
                        "DELETE FROM largo_plazo_dimensiones WHERE concepto = ? AND dimension_id = ?",
                        (concepto, old_dim[0])
                    )
                    cursor.execute(
                        "INSERT OR IGNORE INTO largo_plazo_dimensiones (concepto, dimension_id) VALUES (?, ?)",
                        (concepto, new_dim[0])
                    )
                    logger.info(f"[Hormiguita] DIM {ref}→{valor_sugerido} en {concepto} ({confianza:.2f})")

        # --- SINONIMO ---
        elif capa == "sinonimo" and accion == "agregar" and confianza >= UMBRAL_CONFIANZA_ACEPTAR:
            cursor.execute("SELECT sinonimos FROM largo_plazo WHERE concepto = ?", (concepto,))
            row = cursor.fetchone()
            if row:
                actuales = [s.strip() for s in (row[0] or "").split(",") if s.strip()]
                if ref not in actuales:
                    actuales.append(ref)
                    cursor.execute(
                        "UPDATE largo_plazo SET sinonimos = ? WHERE concepto = ?",
                        (",".join(actuales), concepto)
                    )
                    logger.info(f"[Hormiguita] SYN +{ref} en {concepto} ({confianza:.2f})")

        elif capa == "sinonimo" and accion == "eliminar" and confianza >= UMBRAL_CONFIANZA_ELIMINAR:
            cursor.execute("SELECT sinonimos FROM largo_plazo WHERE concepto = ?", (concepto,))
            row = cursor.fetchone()
            if row:
                actuales = [s.strip() for s in (row[0] or "").split(",") if s.strip()]
                if ref in actuales:
                    actuales.remove(ref)
                    cursor.execute(
                        "UPDATE largo_plazo SET sinonimos = ? WHERE concepto = ?",
                        (",".join(actuales), concepto)
                    )
                    logger.info(f"[Hormiguita] SYN -{ref} en {concepto} ({confianza:.2f})")

        elif capa == "sinonimo" and accion == "reemplazar" and confianza >= UMBRAL_CONFIANZA_ACEPTAR:
            if valor_sugerido:
                cursor.execute("SELECT sinonimos FROM largo_plazo WHERE concepto = ?", (concepto,))
                row = cursor.fetchone()
                if row:
                    actuales = [s.strip() for s in (row[0] or "").split(",") if s.strip()]
                    if ref in actuales:
                        actuales[actuales.index(ref)] = valor_sugerido
                        cursor.execute(
                            "UPDATE largo_plazo SET sinonimos = ? WHERE concepto = ?",
                            (",".join(actuales), concepto)
                        )
                        logger.info(f"[Hormiguita] SYN {ref}→{valor_sugerido} en {concepto}")

        # --- CATEGORIA ---
        elif capa == "categoria" and accion == "reemplazar" and confianza >= UMBRAL_CONFIANZA_ACEPTAR:
            cursor.execute("SELECT id FROM categories WHERE name = ?", (ref,))
            cat_row = cursor.fetchone()
            if cat_row:
                cursor.execute(
                    "UPDATE largo_plazo SET categoria = ? WHERE concepto = ?",
                    (cat_row[0], concepto)
                )
                logger.info(f"[Hormiguita] CAT →{ref} en {concepto} ({confianza:.2f}): {justificacion}")

        # --- CONTENIDO ---
        elif capa == "contenido" and accion == "enriquecer" and confianza >= UMBRAL_CONFIANZA_ACEPTAR:
            if valor_sugerido:
                cursor.execute(
                    "UPDATE largo_plazo SET contenido = ? WHERE concepto = ?",
                    (valor_sugerido, concepto)
                )
                logger.info(f"[Hormiguita] CONTenido enriquecido en {concepto} ({confianza:.2f})")

        # --- SINAPSIS DIRECTA ---
        elif capa == "sinapsis_directa" and accion == "eliminar" and confianza >= UMBRAL_CONFIANZA_ELIMINAR:
            _mover_a_cuarentena(concepto, ref, "sinapsis", cerebro, justificacion, confianza)
            logger.info(f"[Hormiguita] SINAP -{concepto}→{ref} ({confianza:.2f}): {justificacion}")

        elif capa == "sinapsis_directa" and accion == "reponderar" and confianza >= UMBRAL_CONFIANZA_ACEPTAR:
            if peso_sugerido is not None:
                nuevo_peso = min(max(float(peso_sugerido), 0.0), 1.0)
                cursor.execute(
                    "UPDATE sinapsis SET peso = ? WHERE origen = ? AND destino = ?",
                    (nuevo_peso, concepto, ref)
                )
                logger.info(f"[Hormiguita] SINAP {concepto}→{ref} → {nuevo_peso:.2f}")

        elif capa == "sinapsis_directa" and accion == "fusionar" and confianza >= UMBRAL_CONFIANZA_ACEPTAR:
            # Marcar para revisión humana (no ejecutar solo)
            logger.info(f"[Hormiguita] FUSION {concepto}↔{ref} marcada para revisión humana")

        # --- SINAPSIS LATENTE ---
        elif capa == "sinapsis_latente" and accion == "eliminar" and confianza >= UMBRAL_CONFIANZA_ELIMINAR:
            # Two-strike pruning: los lazos débiles tienen derecho a segunda oportunidad.
            # conf >= 0.90 → cuarentena directa (evidencia abrumadora)
            # conf 0.70-0.90 → strike 1: atenúa (peso×0.5). Solo si ya tenía strike → cuarentena.
            if confianza >= UMBRAL_ELIMINAR_LATENTE_DIRECTO:
                _mover_a_cuarentena(concepto, ref, "sinapsis_latentes", cerebro, justificacion, confianza)
                logger.info(f"[Hormiguita] LATENTE -{concepto}→{ref} ({confianza:.2f} directa): {justificacion}")
            else:
                cursor.execute(
                    "SELECT strikes FROM sinapsis_latentes WHERE origen = ? AND destino = ?",
                    (concepto, ref)
                )
                row = cursor.fetchone()
                strikes_actuales = (row[0] if row and row[0] is not None else 0)
                if strikes_actuales >= 1:
                    _mover_a_cuarentena(concepto, ref, "sinapsis_latentes", cerebro, justificacion, confianza)
                    logger.info(f"[Hormiguita] LATENTE -{concepto}→{ref} (strike 2, {confianza:.2f}): {justificacion}")
                else:
                    cursor.execute(
                        "UPDATE sinapsis_latentes SET peso_atenuado = peso_atenuado * 0.5, strikes = 1 "
                        "WHERE origen = ? AND destino = ?",
                        (concepto, ref)
                    )
                    logger.info(f"[Hormiguita] LATENTE ~{concepto}→{ref} atenuada ×0.5 (strike 1, {confianza:.2f})")

        elif capa == "sinapsis_latente" and accion == "confirmar" and confianza >= UMBRAL_CONFIANZA_ACEPTAR:
            # Lazo débil reivindicado: limpiar su strike para empezar de cero
            cursor.execute(
                "UPDATE sinapsis_latentes SET strikes = 0 WHERE origen = ? AND destino = ?",
                (concepto, ref)
            )
            logger.debug(f"[Hormiguita] LATENTE +{concepto}→{ref} confirmada (strike limpiado)")

        elif capa == "sinapsis_latente" and accion == "reponderar" and confianza >= UMBRAL_CONFIANZA_ACEPTAR:
            if peso_sugerido is not None:
                nuevo_peso = min(max(float(peso_sugerido), 0.0), 1.0)
                cursor.execute(
                    "UPDATE sinapsis_latentes SET peso_atenuado = ? WHERE origen = ? AND destino = ?",
                    (nuevo_peso, concepto, ref)
                )
                logger.info(f"[Hormiguita] LATENTE {concepto}→{ref} → {nuevo_peso:.2f}")

        # --- MANTENER / CONFIRMAR / IGNORAR ---
        elif accion in ("mantener", "confirmar", "ignorar"):
            logger.debug(f"[Hormiguita] {capa} {ref}: {accion} (confianza={confianza:.2f})")
            return True

        else:
            logger.info(f"[Hormiguita] {capa} {ref}: {accion} no aplicado (confianza={confianza:.2f})")
            return True

        conn.commit()
        return True

    except sqlite3.Error as e:
        conn.rollback()
        logger.error(f"[Hormiguita] Error DB aplicando {capa} {accion} en {concepto}: {e}")
        return False


# --- Persistencia de estado (estado_hormiga.json) ----------------------------

def _cargar_estado():
    """Carga el estado persistente del demonio. Crea uno nuevo si no existe."""
    if os.path.exists(ESTADO_HORMIGA_PATH):
        try:
            with open(ESTADO_HORMIGA_PATH, "r", encoding="utf-8") as f:
                estado = json.load(f)
            # Asegurar campos requeridos
            for campo, default in [
                ("frontier", []), ("visitados_hoy", []), ("visitados_total", []),
                ("fase_actual", "urgente"), ("ciclos_completados", 0), ("historial", []),
                ("tokens_gastados_hoy", 0), ("nodo_actual", None),
                ("lote_actual", 0), ("procesadas_nodo", []),
            ]:
                if campo not in estado:
                    estado[campo] = default
            return estado
        except (json.JSONDecodeError, OSError):
            logger.warning("estado_hormiga.json corrupto — creando uno nuevo.")
    return {
        "frontier": [],
        "visitados_hoy": [],
        "visitados_total": [],
        "fase_actual": "urgente",
        "ciclos_completados": 0,
        "historial": [],
        "tokens_gastados_hoy": 0,
        "nodo_actual": None,
        "lote_actual": 0,
        "procesadas_nodo": [],
    }


def _guardar_estado(estado):
    """Guarda el estado, rotando el historial a las últimas 50 entradas."""
    estado["historial"] = estado.get("historial", [])[-50:]
    estado["visitados_total"] = estado.get("visitados_total", [])[-500:]
    try:
        with open(ESTADO_HORMIGA_PATH, "w", encoding="utf-8") as f:
            json.dump(estado, f, ensure_ascii=False, indent=2)
    except OSError as e:
        logger.warning(f"No se pudo guardar estado_hormiga.json: {e}")


# --- Selección de semilla (3 fases: urgente → reciente → barrido) ----------

def _seleccionar_semilla(estado, cerebro):
    """
    Elige el nodo semilla según prioridad:
    1. URGENTE: nodos con muchas sinapsis PMI_HEBBIANO (>5) o categoría General
    2. RECIENTE: nodos creados en las últimas 24h
    3. BARRIDO: nodo más antiguo no visitado
    
    Retorna: concepto (str) o None si no hay nodos pendientes.
    """
    conn = cerebro.conn
    cursor = conn.cursor()
    visitados = set(estado.get("visitados_total", []))
    
    # FASE URGENTE: PMI_HEBBIANO alto (>5 conexiones) o General
    cursor.execute("""
        SELECT lp.concepto, COUNT(s.tipo) as pmi_count
        FROM largo_plazo lp
        LEFT JOIN sinapsis s ON s.origen = lp.concepto AND s.tipo = 'pmi_hebbiano'
        WHERE lp.estado = 'activo'
        GROUP BY lp.concepto
        HAVING pmi_count > 5
        ORDER BY pmi_count DESC
        LIMIT 50
    """)
    for concepto, count in cursor.fetchall():
        if concepto not in visitados:
            logger.info(f"[Hormiguita] Semilla URGENTE: {concepto} ({count} PMI_HEBBIANO)")
            return concepto
    
    # FASE RECIENTE: creadas en últimas 24h
    hace_24h = time.time() - 86400
    cursor.execute("""
        SELECT concepto FROM largo_plazo 
        WHERE estado = 'activo' AND creado_en >= ?
        ORDER BY creado_en DESC
        LIMIT 20
    """, (hace_24h,))
    for (concepto,) in cursor.fetchall():
        if concepto not in visitados:
            logger.info(f"[Hormiguita] Semilla RECIENTE: {concepto}")
            return concepto
    
    # FASE BARRIDO: nodo más antiguo sin visita
    cursor.execute("""
        SELECT concepto FROM largo_plazo 
        WHERE estado = 'activo'
        ORDER BY creado_en ASC
        LIMIT 50
    """)
    for (concepto,) in cursor.fetchall():
        if concepto not in visitados:
            logger.info(f"[Hormiguita] Semilla BARRIDO: {concepto}")
            return concepto
    
    return None  # Todos visitados


def _expandir_frontera(concepto, cerebro, visitados):
    """
    Dado un nodo, retorna sus vecinos directos no visitados.
    Metodología: BFS local — expande 1 salto desde el nodo actual.
    """
    conn = cerebro.conn
    cursor = conn.cursor()
    
    vecinos = set()
    
    # Vecinos salientes (origen → destino)
    cursor.execute("""
        SELECT DISTINCT destino FROM sinapsis WHERE origen = ?
    """, (concepto,))
    for (destino,) in cursor.fetchall():
        if destino not in visitados:
            vecinos.add(destino)
    
    # Vecinos entrantes (destino → origen)
    cursor.execute("""
        SELECT DISTINCT origen FROM sinapsis WHERE destino = ?
    """, (concepto,))
    for (origen,) in cursor.fetchall():
        if origen not in visitados:
            vecinos.add(origen)
    
    return list(vecinos)


def _siguiente_nodo(estado, cerebro):
    """
    Elige el siguiente nodo a procesar.
    0. Si hay un nodo a medio procesar (lote_actual > 0) → reanudarlo
    1. Si hay frontier → sacar el primero (FIFO)
    2. Si no → elegir nueva semilla
    """
    # Reanudación mid-node: un ciclo anterior falló a mitad de este nodo.
    # Se retoma exactamente donde quedó (procesadas_nodo tiene lo ya hecho).
    if estado.get("nodo_actual") and estado.get("lote_actual", 0) > 0:
        return estado["nodo_actual"]

    frontier = estado.get("frontier", [])
    visitados = set(estado.get("visitados_total", []))
    
    # Limpiar frontier de nodos ya visitados
    frontier = [n for n in frontier if n not in visitados]
    estado["frontier"] = frontier
    
    if frontier:
        return frontier.pop(0)
    
    # Frontier vacía → nueva semilla
    semilla = _seleccionar_semilla(estado, cerebro)
    return semilla


# --- Gestión de quota y recovery -------------------------------------------

def _verificar_quota(estado):
    """
    Verifica si hay quota disponible para llamar a Gemini.
    Retorna: (disponible: bool, motivo: str)
    """
    proveedores = estado.get("proveedores", {})
    ahora = time.time()
    
    # Verificar si todas las keys están agotadas
    keys_agotadas = 0
    for key_info in proveedores.values():
        if key_info.get("estado") == "agotado":
            hasta = key_info.get("agotado_hasta", 0)
            if ahora < hasta:
                keys_agotadas += 1
            else:
                # Quota renovada
                key_info["estado"] = "disponible"
                key_info["intentos_fallidos"] = 0
    
    total_keys = len(GEMINI_API_KEYS)
    if total_keys > 0 and keys_agotadas >= total_keys:
        # Calcular cuándo se renueva la primera key
        min_hasta = min(
            k.get("agotado_hasta", 0) 
            for k in proveedores.values() 
            if k.get("estado") == "agotado"
        )
        horas_espera = max(0, (min_hasta - ahora) / 3600)
        return False, f"Todas las keys agotadas. Renueva en {horas_espera:.1f}h"
    
    return True, "OK"


def _registrar_exito(estado, tokens_usados=0):
    """Registra una llamada exitosa a Gemini."""
    estado["tokens_gastados_hoy"] = estado.get("tokens_gastados_hoy", 0) + tokens_usados
    estado["ultimo_exito"] = time.time()


def _registrar_fallo(estado, tipo_error="unknown"):
    """Registra un fallo de API (429/404) y marca la key como agotada."""
    ahora = time.time()
    espera_horas = 24  # Esperar 24 horas antes de reintentar
    
    proveedores = estado.setdefault("proveedores", {})
    key_actual = f"key_{len(proveedores)}"
    
    proveedores[key_actual] = {
        "estado": "agotado",
        "agotado_desde": ahora,
        "agotado_hasta": ahora + (espera_horas * 3600),
        "tipo_error": tipo_error,
        "intentos_fallidos": proveedores.get(key_actual, {}).get("intentos_fallidos", 0) + 1,
    }
    
    estado["motivo_espera"] = f"{tipo_error} — reintento en {espera_horas}h"
    logger.warning(f"[Hormiguita] Quota agotada ({tipo_error}). Reintento en {espera_horas}h.")

# --- Punto de entrada (hormiguita — nodo por nodo) -------------------------

def _contar_conexiones(concepto, cerebro):
    """Cuenta las conexiones totales (directas + latentes) salientes de un nodo."""
    cursor = cerebro.conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM sinapsis WHERE origen = ?", (concepto,))
    d = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM sinapsis_latentes WHERE origen = ?", (concepto,))
    l = cursor.fetchone()[0]
    return d + l


def ejecutar_ciclo_reflexivo(cerebro, max_nodos=10):
    """
    Punto de entrada de la hormiguita. Procesa nodos uno por uno
    usando frontier-based traversal. Persiste estado entre ciclos.
    
    Flujo:
    1. Verificar quota
    2. Elegir siguiente nodo (frontier o nueva semilla)
    3. Construir payload con 6 capas
    4. Enviar a Gemini
    5. Aplicar veredictos por capa
    6. Expandir frontera con vecinos
    7. Guardar estado
    8. Repetir hasta max_nodos o quota agotada
    """
    estado = _cargar_estado()
    
    # Verificar quota
    disponible, motivo = _verificar_quota(estado)
    if not disponible:
        logger.info(f"[Hormiguita] Quota no disponible: {motivo}")
        estado["historial"].append({
            "timestamp": time.time(),
            "resultado": "quota_agotada",
            "motivo": motivo,
        })
        _guardar_estado(estado)
        return {"resultado": "quota_agotada", "motivo": motivo}
    
    visitados_hoy = estado.get("visitados_hoy", [])
    visitados_total = set(estado.get("visitados_total", []))
    resultados = []
    nodos_procesados = 0
    eliminados_total = 0
    
    while nodos_procesados < max_nodos:
        # Elegir siguiente nodo (o reanudar el que quedó a medias)
        resumiendo = bool(estado.get("nodo_actual") and estado.get("lote_actual", 0) > 0)
        concepto = _siguiente_nodo(estado, cerebro)
        if not concepto:
            logger.info("[Hormiguita] No hay más nodos por visitar. Grafo completo.")
            break

        # Marcar como visitado ANTES de procesar (evita loops)
        if concepto not in visitados_total:
            visitados_hoy.append(concepto)
            visitados_total.add(concepto)
        estado["nodo_actual"] = concepto

        # Construir payload con pre-filtrado
        resultado_payload = _construir_payload_nodo(concepto, cerebro)
        if not resultado_payload:
            logger.warning(f"[Hormiguita] No se pudo construir payload para {concepto}")
            estado["nodo_actual"] = None
            estado["lote_actual"] = 0
            estado["procesadas_nodo"] = []
            continue

        payload, prefiltro_data = resultado_payload

        # Aplicar cortes directos del pre-filtrado (solo en pasada fresca;
        # en reanudación ya se aplicaron antes del fallo)
        cortes_directos = 0
        if not resumiendo:
            for s in prefiltro_data.get("cortadas_directas", []):
                destino = s.get("destino", "")
                if _mover_a_cuarentena(
                    concepto, destino, "sinapsis", cerebro,
                    motivo=f"pre-filtro determinista (peso={s.get('peso', 0):.3f})",
                    confianza=1.0
                ):
                    cortes_directos += 1
                    logger.info(f"[Pre-filtrado] CORTE DIRECTO {concepto}→{destino} (peso={s.get('peso', 0):.3f})")

            for s in prefiltro_data.get("cortadas_latentes", []):
                destino = s.get("destino", "")
                if _mover_a_cuarentena(
                    concepto, destino, "sinapsis_latentes", cerebro,
                    motivo=f"pre-filtro determinista (peso={s.get('peso_atenuado', 0):.3f})",
                    confianza=1.0
                ):
                    cortes_directos += 1
                    logger.info(f"[Pre-filtrado] CORTE LATENTE {concepto}→{destino} (peso={s.get('peso_atenuado', 0):.3f})")

            if cortes_directos > 0:
                cerebro.conn.commit()
                eliminados_total += cortes_directos

        # Lista completa de sinapsis a evaluar, con su capa
        todas = []
        for s in payload.get("sinapsis_directas", []):
            todas.append(("sinapsis_directa", s))
        for s in payload.get("sinapsis_latentes", []):
            todas.append(("sinapsis_latente", s))

        # Excluir las ya procesadas (reanudación mid-node)
        procesadas = set(estado.get("procesadas_nodo", []))
        pendientes = [(capa, s) for capa, s in todas if s.get("destino") not in procesadas]

        if not pendientes:
            logger.info(f"[Hormiguita] {concepto}: sin candidatas para LLM")
            resultados.append({
                "nodo": concepto,
                "veredictos": 0,
                "aplicados": 0,
                "eliminados": cortes_directos,
                "prefiltrados": cortes_directos,
            })
            estado["nodo_actual"] = None
            estado["lote_actual"] = 0
            estado["procesadas_nodo"] = []
            nodos_procesados += 1
            continue

        # Dividir en lotes: la semilla viaja con cada grupo
        lotes = [
            pendientes[i:i + TAMANO_LOTE_SINAPSIS]
            for i in range(0, len(pendientes), TAMANO_LOTE_SINAPSIS)
        ]

        veredictos_totales = 0
        aplicados = 0
        eliminados = 0
        fallo = False

        for idx, lote in enumerate(lotes):
            # Mini-payload: semilla completa + solo este grupo de sinapsis
            mini_payload = {
                "nodo": payload["nodo"],
                "sinapsis_directas": [s for capa, s in lote if capa == "sinapsis_directa"],
                "sinapsis_latentes": [s for capa, s in lote if capa == "sinapsis_latente"],
                "catalogo_disponible": payload.get("catalogo_disponible"),
            }

            veredictos = _llamar_gemini_nodo(mini_payload)
            if veredictos is None:
                # FALLA DE API: guardar posición exacta (nodo + lote + procesadas)
                # y abortar el ciclo. El próximo arranque reanuda aquí mismo.
                estado["nodo_actual"] = concepto
                estado["procesadas_nodo"] = list(procesadas)
                _guardar_estado(estado)
                _registrar_fallo(estado, "api_fallo")
                fallo = True
                logger.warning(
                    f"[Hormiguita] Fallo API en {concepto} lote {idx + 1}/{len(lotes)}. "
                    f"Estado guardado — se reanuda en este punto exacto."
                )
                break

            # Separar eliminaciones de sinapsis del resto de veredictos
            eliminaciones = []
            otros = []
            for v in veredictos:
                if (
                    isinstance(v, dict)
                    and v.get("accion") == "eliminar"
                    and v.get("capa") in ("sinapsis_directa", "sinapsis_latente")
                ):
                    eliminaciones.append(v)
                else:
                    otros.append(v)

            # Eliminar de mayor a menor confianza, con piso anti-sobrepoda:
            # si el nodo llega al mínimo de conexiones, las demás se aplazan.
            eliminaciones.sort(key=lambda v: v.get("confianza", 0), reverse=True)
            conexiones_restantes = _contar_conexiones(concepto, cerebro)
            for v in eliminaciones:
                if conexiones_restantes <= MIN_CONEXIONES_POR_NODO:
                    logger.warning(
                        f"[Hormiguita] PISO anti-sobrepoda: aplazando eliminación de "
                        f"{v.get('ref')} en {concepto} (quedan {conexiones_restantes} conexiones)"
                    )
                    continue
                if _aplicar_veredicto_nodo(concepto, v, cerebro):
                    aplicados += 1
                    conexiones_restantes -= 1
                    eliminados += 1

            # El resto de veredictos (metadatos, confirmaciones) se aplican normal
            for v in otros:
                if isinstance(v, dict):
                    if _aplicar_veredicto_nodo(concepto, v, cerebro):
                        aplicados += 1

            veredictos_totales += len(veredictos)

            # Marcar lote como procesado y persistir estado DESPUÉS DE CADA LOTE
            for _, s in lote:
                procesadas.add(s.get("destino"))
            estado["procesadas_nodo"] = list(procesadas)
            estado["lote_actual"] = estado.get("lote_actual", 0) + 1
            _registrar_exito(estado, tokens_usados=len(json.dumps(mini_payload)) // 4)
            _guardar_estado(estado)

            logger.info(
                f"[Hormiguita] {concepto} lote {idx + 1}/{len(lotes)} OK — "
                f"{len(veredictos)} veredictos, {eliminados} eliminadas acumuladas"
            )

        if fallo:
            break

        eliminados_total += eliminados

        # Nodo completo — limpiar estado granular y expandir frontera
        estado["nodo_actual"] = None
        estado["lote_actual"] = 0
        estado["procesadas_nodo"] = []

        vecinos = _expandir_frontera(concepto, cerebro, visitados_total)
        frontier_actual = set(estado.get("frontier", []))
        for v in vecinos:
            if v not in visitados_total and v not in frontier_actual:
                estado["frontier"].append(v)

        resultados.append({
            "nodo": concepto,
            "veredictos": veredictos_totales,
            "aplicados": aplicados,
            "eliminados": eliminados,
            "prefiltrados": cortes_directos,
            "lotes": len(lotes),
        })

        nodos_procesados += 1

        # Benchmark gate: cada N nodos, medir recall real del grafo podado
        if nodos_procesados % BENCHMARK_CADA_N_NODOS == 0:
            gate = _benchmark_gate(cerebro, estado)
            if gate:
                estado["historial"].append({"tipo": "benchmark", **gate})
                _guardar_estado(estado)

        logger.info(
            f"[Hormiguita] {concepto}: {aplicados}/{veredictos_totales} veredictos en "
            f"{len(lotes)} lotes, {eliminados} eliminados. "
            f"Frontier: {len(estado.get('frontier', []))} nodos."
        )
    
    # Actualizar estado global
    estado["visitados_hoy"] = visitados_hoy
    estado["visitados_total"] = list(visitados_total)
    estado["ciclos_completados"] = estado.get("ciclos_completados", 0) + 1
    estado["nodo_actual"] = None
    
    estado["historial"].append({
        "timestamp": time.time(),
        "ciclos_completados": estado["ciclos_completados"],
        "resultado": "completo",
        "nodos_procesados": nodos_procesados,
        "eliminados_total": eliminados_total,
        "frontier_restante": len(estado.get("frontier", [])),
        "visitados_total": len(visitados_total),
    })
    
    _guardar_estado(estado)
    
    if eliminados_total > 0:
        logger.warning(
            f"[Hormiguita] ⚠️ {eliminados_total} conexiones eliminadas. "
            f"Verificar GLOBAL Recall@5 >= 94.55%."
        )
    
    resumen = {
        "resultado": "completo",
        "nodos_procesados": nodos_procesados,
        "eliminados_total": eliminados_total,
        "frontier_restante": len(estado.get("frontier", [])),
        "visitados_total": len(visitados_total),
        "detalle": resultados,
    }
    
    logger.info(
        f"[Hormiguita] Ciclo completo: {nodos_procesados} nodos, "
        f"{eliminados_total} eliminados, frontier: {resumen['frontier_restante']}"
    )
    
    return resumen
