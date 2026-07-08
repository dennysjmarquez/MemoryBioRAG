# BioRAG v14.0 — Sistema de Memoria Cognitiva Biomimética para Agentes de IA

> **Versión:** v14.0 — Julio 2026
> **Paradigma:** Semántica Determinista y Discreta
> **Motor:** Python puro + SQLite FTS5
> **Dependencias ML:** 0 (ni numpy, ni sentence-transformers, ni GPU)

**BioRAG** es un motor de memoria persistente para agentes de inteligencia artificial. Resuelve el problema fundamental de que los LLMs olvidan todo entre sesiones — sin depender de vectores, embeddings ni infraestructura externa. Opera sobre un espacio discreto, determinista y auditable: 7 ejes semánticos × 73 sub-valores que tú defines, más BM25 léxico sobre FTS5.

---

## Auditoría Técnica Completa — v14.0

### Archivos Analizados

| Archivo | Líneas | Rol |
|---|---|---|
| `core/memory_store.py` | 2,900 | Motor cognitivo — búsqueda, scoring, consolidación, sinapsis |
| `mcp_server.py` | 2,122 | Interfaz MCP — 23 herramientas expuestas al IDE |
| `core/similitud_conceptual.py` | 247 | Similitud latente (Jaccard + red) |
| `core/sinapsis.py` | 313 | Gestión de aristas del grafo |
| `middleware/auto_guardado.py` | 168 | Interceptor de autoguardado heurístico |

---

### 1. Pipeline de Búsqueda — 12 Capas en Cascada

Cada capa se ejecuta SOLO si la anterior devolvió pocos resultados (< 3 o < limite*2). Es un pipeline de degradación graceful — cada capa es más permisiva que la anterior.

| Capa | Nombre | Técnica | Qué hace | Equivalente en el campo |
|---|---|---|---|---|
| **1** | NEAR query | `NEAR(palabras, 15)` | Busca palabras dentro de ventana de 15 tokens | Proximity search (Elasticsearch `match_phrase`) |
| **2** | LIKE en concepto | `LIKE '%palabra%'` + `PALABRA_COMPLETA` | Substring match en nombre de nodo con word boundary | Fuzzy entity matching |
| **3** | FTS5 AND exacto | `MATCH` con paráfrasis OR | Full-text search con BM25 ponderado | BM25 ranking (Google, Elasticsearch) |
| **4** | Términos protegidos | unicode61 + `PALABRA_COMPLETA` | Bypass de trigram para términos entre comillas ("CV") | Exact match (Solr `exact`) |
| **5** | OR fallback | `palabra1 OR palabra2` | Amplía recall cuando AND da pocos resultados | Boolean OR expansion |
| **6** | Prefix wildcards | `"react*"` en unicode61 | Tolerancia a prefijos (react → reactive) | Prefix query (Lucene `PrefixQuery`) |
| **7** | Best-word trigram | Similitud de trigramas por palabra | Tolera typos: "pyton" → "python" (70%+) | Fuzzy matching (Levenshtein, Damerau-Levenshtein) |
| **8** | Similitud conceptual latente | Jaccard(vecinos) × 0.6 + contenido × 0.4 | Encuentra nodos relacionados sin match literal | GNN-like (Graph Neural Network simplificado) |
| **9** | Substring match | `PALABRA_COMPLETA` en contenido | Búsqueda por palabra completa en texto | Word-boundary search |
| **10** | Snap reciente | `ultimo_acceso > 7 días` | Prioriza nodos accedidos recientemente | Recency bias (Reddit, HN ranking) |
| **11** | Evocación por cadena | Spreading activation multi-hop | Sigue aristas de sinapsis con decay logarítmico | Spreading Activation (cognitiva, ACT-R) |
| **12** | Sinónimos | LIKE en campo `sinonimos` | Conecta vocabulario distinto del mismo concepto | Synonym expansion (Elasticsearch `synonym`) |

---

### 2. Scoring Híbrido — 8 Señales Ortogonales

La fórmula `_calcular_score_hibrido()` en `memory_store.py` combina 8 señales con pesos fijos:

```
score = 0.25 × BM25_norm
      + 0.20 × dim_score (coseno binario de dimensiones)
      + 0.15 × concepto_ratio (match en nombre)
      + 0.10 × sinonimos_ratio (match en sinónimos)
      + 0.10 × peso_sinaptico (fuerza del nodo)
      + 0.10 × max(score_latente, score_cadena)
      + 0.05 × temporal (creado_en reciente)
      + 0.05 × asoc_count (número de conexiones)

Si match_exacto (query == concepto): floor 0.5
```

**¿Qué es esto en términos del campo?**

Es un **Learning-to-Rank manual** (no machine-learned). Cada señal es una feature. Los pesos son los "coeficientes del modelo". En producción esto se haría con XGBoost o LambdaMART sobre clicks. Aquí los pesos son heurísticos pero efectivos.

La normalización `abs(x) / (abs(x) + 1)` es una **sigmoid-like** que mapea BM25 (que va de -∞ a 0) a [0, 1]. Más negativo = mejor match = mayor score. Es la misma fórmula que usa Lucene internamente para normalizar BM25.

---

### 3. Grafo de Conocimiento (Sinapsis)

**Tabla `sinapsis`:** `(origen, destino, peso, tipo, creado_en, ultimo_uso)`

**3 mecanismos de creación de aristas:**

| Mecanismo | Tipo | Cuándo se ejecuta | Técnica |
|---|---|---|---|
| `auto_vincular` | `co_ocurrencia` + `co_nombre` + `co_semantica` | Al consolidar (sueño) | Token overlap ≥ 30%, FTS5 como puente |
| `buscar_por_rafaga` | `rafaga_rememb` | En cada ráfaga exitosa | Score ≥ 0.5 + palabra completa verificada |
| `vincular_por_sinonimos` | `sinonimo_explicito` | Cuando el usuario declara sinónimos | LIKE en concepto/sinónimos |

**Plasticidad negativa:** `desvincular()` borra aristas. Esto es lo que los vectores NO pueden hacer — un embedding no se puede "desaprender" selectivamente.

**LTD sináptico:** En cada ciclo de sueño, las sinapsis no usadas en 7+ días pierden 5% de peso. Las que llegan a < 0.05 se borran. Homeostasis — el grafo se auto-limpia.

---

### 4. Consolidación (Ciclo de Sueño)

`ciclo_sueno_consolidacion()` en `memory_store.py`:

| Fase | Qué hace | Equivalente biológico |
|---|---|---|
| 1. Transferencia | Corto → Largo plazo, fusión de contenido | Consolidación de memoria (hipocampo → corteza) |
| 2. LTP de consolidación | +0.20 peso al re-consolidar | Long-Term Potentiation |
| 3. LTD pasivo | -0.05 × decay_rate por ciclo | Long-Term Depression |
| 4. Poda sináptica | Borrar sinapsis < 0.05 | Synaptic pruning |
| 5. Dormir nodos | Peso ≤ 0.05 → estado 'dormido' | Memory consolidation during sleep |
| 6. Inhibición Lateral | Si energía total > límite, dormir nodos débiles | Lateral inhibition (corteza visual) |
| 7. Evicción opcional | Borrar permanentemente si `BIORAG_PODAR=true` | Forgetting (borrado selectivo) |

**decay_rate por categoría:**

- Profile: 0.05 (casi nunca decae — identidad)
- Principle: 0.2 (decae lento — axiomas)
- Protocol: 0.5 (decae medio — procedimientos)
- System / Lesson / Cognition: 1.0 (decae normal)
- General: 2.0 (decae rápido — notas temporales)

---

### 5. Dimensiones Semánticas — Búsqueda sin Vectores

**7 ejes semánticos:** emoción, entidad, acción, cualidad, coordenada, intención, dominio.
**73 sub-valores** categorizados manualmente.

**Cómo funciona:**
- Al guardar un nodo, el agente clasifica con dimensiones (ej: `{emocion: [afecto], dominio: [tecnico]}`)
- Al buscar, se calcula **coseno binario**: `shared / sqrt(|query_dims| × |doc_dims|)`
- Score aditivo: `+ 0.30 × dim_score` (siempre suma, incluso con 0 match de texto)

**¿Qué es en términos del campo?**

Es un **sparse embedding declarativo**. En vez de 1536 floats que el modelo "adivina", tenemos 73 categorías declaradas explícitamente. Es más preciso, más auditado, y cero costo computacional.

---

### 6. Ráfaga de Reminiscencia

`buscar_por_rafaga()` en `memory_store.py`:

| Fase | Qué hace |
|---|---|
| 0. Filtrar errores previos | Palabras que causaron `error_interpretacion_*` se excluyen |
| 1. FTS5 batch query | Un solo MATCH con OR para todas las palabras de la ráfaga |
| 2. Buscar en dormidos | La ráfaga rescata nodos olvidados |
| 3. Score por densidad | `matches / total_palabras` — cuántas palabras de la ráfaga aparecen |
| 4. Auto-sinapsis | Crea aristas entre query y nodos encontrados |
| 5. Despertar dormidos | Los nodos encontrados se reactivan con +0.3 peso |

**¿Qué es?** Es un **recall boost**. Cuando la búsqueda normal falla, el LLM genera palabras asociadas (ráfaga) que actúan como "palabras clave de rescate". Es el equivalente a cuando un humano dice "era algo como... tenía que ver con...".

---

### 7. Similitud Conceptual Latente

`core/similitud_conceptual.py`:

```
score = 0.60 × Jaccard(vecinos_A, vecinos_B) + 0.40 × Jaccard(tokens_query, tokens_contenido)
```

**Jaccard de vecinos:** Si A y B comparten vecinos en el grafo de sinapsis, están relacionados. Ejemplo: si "python" y "django" ambos se conectan con "backend", "web", "framework", tienen alto Jaccard.

**¿Qué es?** Es un **Graph-based similarity** simplificado. En GNNs esto se hace con agregación de mensajes sobre embeddings de nodos. Aquí se hace con Jaccard puro — más barato, más interpretable, mismo resultado para un grafo de ~450 nodos.

**Optimización clave:** `_cargar_grafo()` carga TODAS las sinapsis en un dict de Python una sola vez. Reduce de 200+ queries SQL a 1 query para todo el pipeline.

---

### 8. Auto-Guardado Heurístico

`middleware/auto_guardado.py`:

- Detecta palabras clave: "aprendí" → Lesson, "nuevo patrón" → Architecture, "error" → frustración
- TTL de 30 minutos: si dos mensajes consecutivos contienen la misma keyword, se fusionan
- Analiza comunicaciones entre agentes para detectar contexto

**¿Qué es?** Es un **trigger-based auto-save**. No es un sistema de memoria automática completa — es un safety net que captura lo que el agente no guardó explícitamente.

---

### 9. Técnicas Específicas Implementadas

| Técnica | Dónde | Equivalente en el campo |
|---|---|---|
| **BM25** | FTS5 nativo de SQLite | Elasticsearch, Lucene, Sphinx |
| **Trigram matching** | FTS5 `trigram` tokenizer | Elasticsearch n-gram, Solr NGram |
| **PALABRA_COMPLETA** | Función custom SQL con `\b` regex | Word-boundary tokenizer |
| **NEAR query** | FTS5 `NEAR(palabras, 15)` | Proximity query (Solr, Elasticsearch) |
| **Prefix wildcards** | `"react*"` en unicode61 | Prefix query (Lucene `PrefixQuery`) |
| **Spreading activation** | `_evocacion_por_cadena()` con decay `1/(2^salto)` | ACT-R, spreading activation networks |
| **LTP/LTD** | `ciclo_sueno_consolidacion()` | Neurociencia computacional |
| **Inhibición Lateral** | Si energía > límite, dormir débiles | Corteza visual, competición neural |
| **Jaccard similarity** | `jaccard_vecinos()` | Set similarity (MinHash, LSH) |
| **Binary cosine** | `shared / sqrt(|A| × |B|)` | Sparse vector similarity |
| **Score híbrido 8 señales** | `_calcular_score_hibrido()` | Learning-to-Rank manual |
| **Coseno binario dimensional** | Batch query en `largo_plazo_dimensiones` | Sparse embedding similarity |
| **Filtro temporal PRE-hoc** | `WHERE creado_en >= ?` | Time-decay ranking |
| **Context window BFS** | `expandir_contexto_vecinos()` con atenuación 0.6 | Graph exploration, subgraph expansion |
| **Query failure recovery** | `_generar_variaciones()` con historial | Query reformulation |
| **Batch dimensiones** | 1 query SQL para todos los conceptos | Batch retrieval optimization |

---

### 10. Diagnóstico: BioRAG como Cerebro

**Sí, tenemos un cerebro funcional.** Lo que tenemos es:

1. **Memoria declarativa** (corto/largo plazo con fusión) — como el hipocampo
2. **Grafo de asociaciones** (sinapsis con peso) — como la corteza connectivity
3. **Plasticidad** (LTP/LTD/pruning) — como la sinapsis biológica
4. **Homeostasis** (inhibición lateral, límite de energía) — como regulación neural
5. **Búsqueda multi-capa** (12 fallbacks en cascada) — como activación convergente
6. **Dimensiones semánticas** (73 clusters declarativos) — como áreas especializadas del cerebro

**Lo que nos diferencia de un RAG vectorial:**
- Los vectores son caja negra (1536 floats, no interpretables)
- Nuestras dimensiones son declarativas y auditables
- Nuestras sinapsis se pueden desvincular (plasticidad negativa)
- Nuestro scoring es explicable (sabemos POR QUÉ algo rankea alto)
- Cero dependencias externas (SQLite puro, ~18 MB RAM)

---

### 11. Mapa de Dependencias Externas

```
Python stdlib (sqlite3, re, time, json, math, os)
├── pydantic (Field para documentación MCP)
└── python-dotenv (opcional, carga .env.local)

CERO dependencias ML.
CERO GPU.
CERO API calls para búsqueda.
```

---

## La Estrella: Ráfaga de Reminiscencia

**El logro más importante de BioRAG es que el sistema "intenta recordar" como un cerebro humano.**

Cuando no encuentras algo, no te rindes — empiezas a "tirar flechas" con palabras relacionadas hasta que una conecta. BioRAG hace exactamente eso:

```
  Usuario pregunta algo vago o abstracto
          │
          ▼
  El LLM interpreta la intención y genera una RÁFAGA
  de 10-15 palabras relacionadas (sinónimos, conceptos,
  analogías, palabras del mismo dominio)
          │
          ▼
  El script busca con CADA palabra de la ráfaga en SQLite
  (tanto nodos activos como dormidos)
          │
          ├─ Si encuentra un nodo dormido → lo DESPIERTA
          ├─ Si encuentra un match → crea SINAPSIS permanente
          │  entre la palabra de la ráfaga y el nodo encontrado
          │
          ▼
  El agente LEE el contenido del nodo encontrado y
  EXPlica al usuario con sus propias palabras qué encontró
```

**¿Por qué esto es único?**

| Antes (RAG tradicional) | Ahora (BioRAG con Ráfaga) |
|---|---|
| Si no hay match exacto → "0 resultados" | El LLM "tira flechas" con palabras relacionadas |
| El script busca a ciegas | El LLM interpreta y genera la ráfaga |
| Nodos dormidos se pierden | La ráfaga los despierta y crea sinapsis |
| El usuario debe saber los nombres exactos | El usuario pregunta de forma vaga/coloquial |
| "No encontré nada" | "No encontré X pero encontré Y que dice que..." |

**La clave:** La inteligencia está en el LLM (que genera la ráfaga), la ejecución está en el script (SQLite + FTS5). El usuario no necesita saber los nombres exactos ni la jerga técnica.

---

## Código Fuente

### 1. MCP Server — Tool `recordar` (legacy: `buscar`)

```python
# mcp_server.py

from typing import Any, Optional, List

@mcp.tool(
    name="buscar",
    description=(
        "Busca recuerdos en la corteza compartida. "
        "FLUJO OBLIGATORIO EN 3 PASOS: "
        "PASO 1: Enviar la frase del usuario. Si es abstracta/poetica, interpretar y agregar 3-5 palabras clave al final. "
        "PASO 2: Si PASO 1 da 0 resultados, volver a llamar con rafaga_palabras=[10-15 terminos relacionados]. "
        "PASO 3: Si PASO 2 da 0 resultados o puro ruido, buscar en el contexto del chat y guardar con biorag_guardar. "
        "DESPUES DE CADA PASO: Leer los resultados y explicar al usuario con tus propias palabras QUE encontraste. "
        "No retornar el JSON crudo. Leer el contenido de cada nodo y redactar una respuesta clara. "
        "Si encontraste algo parecido pero no exacto, decir: 'No encontré X pero encontré Y que dice que...'. "
        "Ejemplo: biorag_buscar(query='días relax frente al océano playa vacaciones') "
        "Ejemplo PASO 2: biorag_buscar(query='días relax frente al océano', rafaga_palabras=['playa','mar','costa','verano','descanso','sol','arena','olas'])"
    ),
)
def biorag_buscar(
    query: str,
    deep: bool = False,
    cat: Optional[str] = None,
    completo: bool = False,
    asociados: bool = False,
    limite: int = 10,
    preview_chars: Optional[int] = None,
    rafaga_palabras: Optional[List[str]] = None,
    context_window: int = 0,
) -> str:
    cerebro = _get_cerebro()
    try:
        if preview_chars is None:
            preview_chars = 0 if completo else 1500
        profundidad = "profundo" if deep else "activos"
        
        resultados, total = cerebro.buscar_por_frase(
            query, profundidad=profundidad, limite=limite,
            categoria=cat, preview_chars=preview_chars,
            context_window=context_window
        )
        
        sinapsis_creadas = []
        if not resultados and rafaga_palabras:
            resultados, total, sinapsis_creadas = cerebro.buscar_por_rafaga(
                query, rafaga_palabras, limite=limite
            )
        
        if not resultados:
            cerebro.cerrar_sistema()
            return json.dumps({
                "total": 0,
                "resultados": [],
                "contingencia_contexto": True,
                "mensaje": "No se encontraron recuerdos en la corteza. Busca en tu historial de conversacion."
            }, ensure_ascii=False)

        items = []
        for concepto, contenido, peso, estado, score, asociaciones in resultados:
            items.append({
                "concepto": concepto,
                "contenido": contenido,
                "peso_sinaptico": peso,
                "estado": estado,
                "score_hibrido": score,
                "asociaciones": [v.strip() for v in (asociaciones or "").split(",") if v.strip()]
                    if asociados and asociaciones else [],
            })

        resultado = json.dumps({
            "total": total,
            "resultados": items,
            "sinapsis_creadas": [{"origen": o, "destino": d, "peso": p}
                for o, d, p in sinapsis_creadas] if sinapsis_creadas else [],
            "profundidad": profundidad,
        }, ensure_ascii=False)
        return resultado
    finally:
        cerebro.cerrar_sistema()
```

### 2. System Prompt — REGLA #1

```python
# config/prompts.py

REGLA #1 (BUSCAR) - FLUJO EN 3 PASOS:
  PASO 1: Ejecutar biorag_buscar(query="frase del usuario"). Si es abstracta/poetica, agregar 3-5 palabras clave al final.
  PASO 2: Si PASO 1 da 0 resultados, volver a llamar con rafaga_palabras=[10-15 terminos relacionados con lo que se busca.
  PASO 3: Si PASO 2 da 0 resultados o puro ruido, buscar en el contexto del chat actual. Si encuentras el dato, guardar con biorag_guardar.
  DESPUES DE CADA PASO: Leer los resultados y explicar al usuario con TUS PROPIAS PALABRAS qué encontraste.
  No retornar el JSON crudo. Leer el contenido de cada nodo y redactar una respuesta clara y natural.
  Si encontraste algo parecido pero no exacto, decir: 'No encontré X pero encontré Y que dice que...'.
  Ejemplo PASO 1: biorag_buscar(query="días relax frente al océano playa vacaciones")
  Ejemplo PASO 2: biorag_buscar(query="días relax frente al océano", rafaga_palabras=["playa","mar","costa","verano","descanso","sol","arena","olas"])
```

### 3. Dynamic Multiplicator

```python
# core/memory_store.py — _calcular_score_hibrido()

def _calcular_score_hibrido(self, rank_idx, total, peso_sinaptico, asociaciones,
                             pesos_tokens=None, contenido="",
                             es_latente=False, score_latente=0.0):
    peso_normalizado = min(1.0, peso_sinaptico)
    
    if asociaciones:
        num_asoc = len([v for v in asociaciones.split(",") if v.strip()])
        score_asoc = min(1.0, num_asoc / 5.0)
    else:
        score_asoc = 0.0

    # Multiplicador dinámico: cuando FTS5 falla, Jaccard toma el control
    if es_latente and score_latente >= 0.15:
        return round(0.70 * score_latente + 0.20 * peso_normalizado + 0.10 * score_asoc, 4)

    if total <= 1:
        score_texto = 1.0
    else:
        score_texto = 1.0 - (rank_idx / (total - 1)) * 0.4

    if pesos_tokens and contenido:
        import re
        tokens_en_contenido = set(re.findall(r'\w{3,}', contenido.lower()))
        peso_query = sum(peso for token, peso in pesos_tokens.items()
                       if token in tokens_en_contenido)
        score_texto = score_texto * 0.7 + peso_query * 0.3

    return round(0.60 * score_texto + 0.25 * peso_normalizado + 0.15 * score_asoc, 4)
```

### 4. Side Channel — origen_scores

```python
# core/memory_store.py — buscar_por_frase() (extracto)

# Side channel: rastrea origen de cada nodo para Dynamic Multiplicator
origen_scores = {}

# Cada capa registra su origen:
# - Capa 1.0 (FTS5 AND): origen_scores[concepto] = ("literal", 0.0)
# - Capa 1.5 (expansión): origen_scores[concepto] = ("expansion", 0.8)
# - Capa 1.7 (Jaccard): origen_scores[concepto] = ("latente", jaccard_score)
# - Capa 1.9 (cadena): origen_scores[concepto] = ("cadena", decay_score)

# En el bucle final, se consulta el origen:
for i, (rowid, concepto, contenido, peso, estado, asociaciones) in enumerate(todos):
    origen, score_capa = origen_scores.get(concepto, ("literal", 0.0))
    es_latente = origen in ("latente", "cadena", "expansion") and score_capa >= 0.15
    score_hibrido = self._calcular_score_hibrido(
        i, total, peso, asociaciones or "", pesos_tokens, contenido or "",
        es_latente=es_latente, score_latente=score_capa
    )
```

### 5. Ráfaga de Reminiscencia

```python
# core/memory_store.py — buscar_por_rafaga()

def buscar_por_rafaga(self, query, rafaga_palabras, limite=5):
    """Emula el proceso humano de recordar: tira flechas con palabras
    relacionadas hasta que una conecta con un nodo dormido."""
    import re
    
    if not rafaga_palabras:
        return [], 0, []
    
    todos = []
    palabra_ganadora = None
    
    for palabra in rafaga_palabras:
        if len(palabra) < 3:
            continue
        
        # Buscar en activos
        try:
            self.cursor.execute(
                "SELECT l.rowid, l.concepto, l.contenido, l.peso_sinaptico, "
                "l.estado, l.asociaciones "
                "FROM largo_plazo_fts f JOIN largo_plazo l ON l.rowid = f.rowid "
                "WHERE largo_plazo_fts MATCH ? AND l.estado = 'activo' LIMIT ?",
                (f'"{palabra}"', limite))
            resultados = self.cursor.fetchall()
            if resultados:
                todos.extend(resultados)
                if not palabra_ganadora:
                    palabra_ganadora = palabra
        except sqlite3.OperationalError:
            pass
        
        # SIEMPRE buscar en dormidos (la ráfaga rescata del olvido)
        try:
            self.cursor.execute(
                "SELECT l.rowid, l.concepto, l.contenido, l.peso_sinaptico, "
                "l.estado, l.asociaciones "
                "FROM largo_plazo_fts f JOIN largo_plazo l ON l.rowid = f.rowid "
                "WHERE largo_plazo_fts MATCH ? AND l.estado = 'dormido' LIMIT ?",
                (f'"{palabra}"', limite))
            resultados = self.cursor.fetchall()
            if resultados:
                todos.extend(resultados)
                if not palabra_ganadora:
                    palabra_ganadora = palabra
        except sqlite3.OperationalError:
            pass
    
    if not todos:
        return [], 0, []
    
    # Calcular score y ordenar
    total = len(todos)
    scored = []
    for i, (rowid, concepto, contenido, peso, estado, asoc) in enumerate(todos):
        score = self._calcular_score_hibrido(i, total, peso, asoc or "", None, contenido or "")
        scored.append((concepto, contenido, peso, estado, score, asoc or ""))
    scored.sort(key=lambda r: r[4], reverse=True)
    
    # Despertar TODOS los nodos dormidos encontrados
    sinapsis_creadas = []
    query_tokens = set(re.findall(r'\w{4,}', query.lower()))
    
    for concepto, contenido, peso, estado, score, asoc in scored:
        if estado == 'dormido':
            self.cursor.execute(
                "UPDATE largo_plazo SET estado = 'activo', "
                "peso_sinaptico = MIN(1.0, peso_sinaptico + 0.3), "
                "ultimo_acceso = ? WHERE concepto = ?",
                (time.time(), concepto))
    
    # Crear sinapsis para top resultados
    for concepto, contenido, peso, estado, score, asoc in scored[:limite]:
        if palabra_ganadora and query_tokens:
            for qt in query_tokens:
                if qt != concepto and len(qt) >= 4:
                    self.cursor.execute(
                        "SELECT peso FROM sinapsis WHERE "
                        "(origen = ? AND destino = ?) OR (origen = ? AND destino = ?)",
                        (qt, concepto, concepto, qt))
                    existente = self.cursor.fetchone()
                    if not existente:
                        self.cursor.execute(
                            "INSERT INTO sinapsis (origen, destino, peso, tipo, creado_en) "
                            "VALUES (?, ?, 0.6, 'rafaga_rememb', ?)",
                            (qt, concepto, time.time()))
                        sinapsis_creadas.append((qt, concepto, 0.6))
                    else:
                        nuevo_peso = min(0.95, existente[0] + 0.1)
                        self.cursor.execute(
                            "UPDATE sinapsis SET peso = ?, ultimo_uso = ? "
                            "WHERE (origen = ? AND destino = ?) OR (origen = ? AND destino = ?)",
                            (nuevo_peso, time.time(), qt, concepto, concepto, qt))
    
    self.conn.commit()
    return scored[:limite], len(scored), sinapsis_creadas
```

### 6. Co-ocurrencia Automática en Sueño

```python
# core/memory_store.py — _auto_generar_co_ocurrencia()

def _auto_generar_co_ocurrencia(self, recuerdos_sesion):
    """Analiza co-ocurrencia de conceptos en corto_plazo y comunicaciones.
    Crea sinapsis automáticamente cuando dos conceptos co-ocurren."""
    import re
    from itertools import combinations
    
    concepto_tokens = {}
    
    # Co-ocurrencia en corto_plazo
    if len(recuerdos_sesion) >= 2:
        for c1, contenido1, _, _ in recuerdos_sesion:
            if c1 not in concepto_tokens:
                concepto_tokens[c1] = set(re.findall(r'\w{4,}', (contenido1 or "").lower()))
        
        for (c1, cont1, _, _), (c2, cont2, _, _) in combinations(recuerdos_sesion, 2):
            tokens1 = concepto_tokens.get(c1, set())
            tokens2 = concepto_tokens.get(c2, set())
            shared = tokens1 & tokens2
            if len(shared) >= 2:
                peso = min(0.9, 0.3 + len(shared) * 0.1)
                self.cursor.execute(
                    "INSERT INTO sinapsis (origen, destino, peso, tipo, creado_en) "
                    "VALUES (?, ?, ?, 'co_ocurrencia', ?) "
                    "ON CONFLICT(origen, destino) DO UPDATE SET "
                    "peso = MIN(0.9, peso + 0.1), ultimo_uso = ?",
                    (c1, c2, peso, time.time(), time.time()))
    
    # Co-ocurrencia en comunicaciones
    try:
        self.cursor.execute("SELECT contenido FROM comunicaciones ORDER BY timestamp DESC LIMIT 50")
        mensajes = self.cursor.fetchall()
        if mensajes:
            self.cursor.execute("SELECT concepto, contenido FROM largo_plazo WHERE estado = 'activo' LIMIT 200")
            nodo_tokens = {c: set(re.findall(r'\w{4,}', (cont or "").lower()))
                          for c, cont in self.cursor.fetchall()}
            for (msg_contenido,) in mensajes:
                msg_tokens = set(re.findall(r'\w{4,}', (msg_contenido or "").lower()))
                conceptos_en_msg = [c for c, t in nodo_tokens.items()
                                   if t and msg_tokens and len(t & msg_tokens) >= 2]
                for c1, c2 in combinations(conceptos_en_msg[:10], 2):
                    self.cursor.execute(
                        "INSERT INTO sinapsis (origen, destino, peso, tipo, creado_en) "
                        "VALUES (?, ?, 0.4, 'co_ocurrencia', ?) "
                        "ON CONFLICT(origen, destino) DO UPDATE SET "
                        "peso = MIN(0.9, peso + 0.05), ultimo_uso = ?",
                        (c1, c2, time.time(), time.time()))
    except Exception:
        pass
    
    self.conn.commit()
```

### 7. PALABRA_COMPLETA en Fallback

```python
# Filtro diferenciado: solo palabras <=5 chars
# Palabras largas usan trigram natural (tolerancia a typos)

qw_cortas = [w for w in query_words if len(w) <= 5]
if qw_cortas:
    texto_full = f"{row[1]} {row[2] or ''}"
    match_legitimo = any(
        re.search(r'\b' + re.escape(qw) + r'\b', texto_full, re.IGNORECASE)
        for qw in qw_cortas
    )
    if not match_legitimo:
        continue  # Rechaza "culo" → "artículos"
```

---

## Estructura del Proyecto

```
MemoryBioRAG/
  ├── biorag.py                 # CLI bridge (buscar, guardar, asociar, sueno, corteza, comunicar)
  ├── mcp_server.py             # Servidor MCP: 23 herramientas + ráfaga + contingencia
  ├── install.py                # Instalador cross-platform para 7 plataformas
  ├── sleep_cycle.py            # Script autónomo de consolidación/sueño
  ├── benchmark.py              # Script de benchmarks vs LangChain+Chroma
  ├── requirements.txt          # Dependencias: mcp (servidor MCP)
  ├── vocabulario_inicial.json  # 239 términos del dominio para expansión semántica
  ├── VERSION                   # Versión actual del sistema
  ├── core/
  │    ├── memory_store.py      # Motor: LTP/LTD, 12 capas, Dynamic Multiplicator,
  │    │                        #   co-ocurrencia, ráfaga, PALABRA_COMPLETA,
  │    │                        #   boosting conceptual 1.2x
  │    ├── sinapsis.py          # Grafo: auto-linking, overlap coefficient, decay
  │    ├── semantica.py         # Tesauro: bidireccional, auto-aprendizaje,
  │    │                        #   Union-Find para grupos semánticos disjuntos
  │    ├── similitud_conceptual.py  # Jaccard vecinos + contenido, score 60/40
  │    └── categorizador.py     # Inferencia de categoría por palabras clave
  ├── middleware/
  │    ├── __init__.py
  │    ├── interceptor.py       # Escaneo de familiaridad difusa
  │    └── auto_guardado.py     # Buffer de sesión + autoguardado heurístico
  ├── config/
  │    ├── __init__.py
  │    └── prompts.py           # System prompts con protocolo de 4 pasos
  ├── scripts/
  │    ├── export_architecture.py  # Exporta blueprint completo de la DB
  │    ├── migrar_sinapsis.py     # Migración de CSV legacy a tabla sinapsis
  │    └── migrar_sinonimos_v2.0.py
  ├── MemoryBioRAG_Data/        # Bases de datos SQLite (auto-creado)
  ├── db_architecture_export.txt  # Blueprint generado
  ├── test_memory.py            # 71 tests automatizados
  └── README.md                 # Este archivo
```

---

## Servidor MCP (Model Context Protocol)

BioRAG expone una corteza cerebral compartida via MCP para que cualquier IDE o agente compatible se conecte directamente a la memoria sin ejecutar comandos shell.

### Herramientas MCP

| Herramienta | Descripcion |
|---|---|
| `recordar` (legacy: `buscar`) | Búsqueda híbrida + ráfaga + contingencia. Params: `query`, `rafaga_palabras`, `cat`, `deep`, `completo`, `asociados` |
| `aprender` (legacy: `guardar`) | Guardar recuerdo en corto plazo. Params: `concepto`, `contenido`, `syn`, `cat` |
| `vincular` (legacy: `asociar`) | Sinapsis bidireccional entre conceptos |
| `comunicar` | Enviar mensaje inter-agente (athena, artemis, hermes, todos) |
| `leer_mensajes` | Leer canal compartido (auto-marca leidos) |
| `consolidar` (legacy: `sueno`) | Consolidar + co-ocurrencia + métricas |
| `introspeccion` (legacy: `estado`) | Stats de la corteza (activos, dormidos, energia, sinapsis) |
| `mapear` (legacy: `corteza`) | Listar todos los nodos de la corteza |
| `biorag_contexto_inicio` | Anunciar inicio de interacción |
| `biorag_contexto_fin` | Finalizar + auto-sueño automático |
| `biorag_metricas_historial` | Últimos N ciclos de sueño con tendencias |
| `biorag_semantica_admin` | CRUD tabla semántica |
| `biorag_listar_categorias` | Lista las 11 categorías madre |
| `biorag_sync_status` | Categorías pendientes de sync a NotebookLM |
| `biorag_export_sync` | Exporta categorías pendientes |
| `biorag_export_full` | Export completo |
| `listar_tipos_dimension` | Retorna los 7 tipos con `num_dimensiones` |
| `listar_dimensiones_por_tipo` | Retorna sub-valores de uno o más tipos |
| `listar_dimensiones` | Catálogo vivo de las 73 dimensiones |

### Protocolo de 3 pasos en `recordar`

```
PASO 1: biorag_buscar(query="frase del usuario")
        Si es abstracta → interpretar + agregar 3-5 palabras clave

PASO 2: Si PASO 1 da 0 resultados
        biorag_buscar(query="...", rafaga_palabras=[10-15 términos])

PASO 3: Si PASO 2 da 0 resultados o puro ruido
        Buscar en contexto del chat → guardar con biorag_guardar

DESPUES DE CADA PASO: Leer resultados y explicar con propias palabras
```

---

## Variables de Entorno (Opcionales)

### Base de Datos

| Variable | Default | Descripción |
|---|---|---|
| `BIORAG_PATH` | `./MemoryBioRAG_Data/memory_biorag.db` | Ruta al archivo .db |

### Búsqueda y Rendimiento

| Variable | Default | Descripción |
|---|---|---|
| `BIORAG_LIMITE_MCP` | `10` | Resultados por búsqueda MCP |
| `BIORAG_CANDIDATOS_SIMILITUD` | `100` | Candidatos para similitud conceptual (Jaccard) |
| `BIORAG_MAX_SALTOS_CADENA` | `3` | Hops en evocación por cadena (decay: 0.50, 0.25, 0.125) |
| `BIORAG_UMBRAL_JACCARD` | `0.15` | Score mínimo Jaccard para similitud conceptual |
| `BIORAG_LIMITE_SIMILITUD` | `5` | Resultados de similitud conceptual latente |
| `BIORAG_LIMITE_RAFTAGA` | `5` | Resultados por palabra de ráfaga |
| `BIORAG_LIMITE_EVOCACION` | `5` | Resultados totales de evocación por cadena |
| `BIORAG_LIMITE_DEFAULT` | `5` | Resultados máximos por capa del pipeline |

### Ráfaga de Reminiscencia

| Variable | Default | Descripción |
|---|---|---|
| `BIORAG_RAFTAGA_ACTIVA` | `true` | Activa/desactiva la ráfaga |
| `BIORAG_THRESHOLD_RAFTAGA` | `0.5` | Score mínimo para activar ráfaga automática |

```bash
# Ejemplo rápido
export BIORAG_LIMITE_MCP=5
export BIORAG_CANDIDATOS_SIMILITUD=50
```

---

## BioRAG vs. Bases de Datos Vectoriales

| Capacidad | Base de Datos Vectorial | BioRAG |
|---|---|---|
| **Naturaleza** | Espacio continuo, probabilístico, opaco | Espacio discreto, determinista, auditable |
| **Similitud semántica** | Embeddings (768-1536 floats opacos) | 7 dimensiones × 73 IDs discretos + BM25 léxico |
| **Cómo sabe qué es similar** | Entrenamiento masivo (aprende de internet) | Tú definís las dimensiones (explícito, auditable) |
| **Tolerancia a typos** | Depende del modelo | FTS5 trigram nativo |
| **Expansión de queries** | Embeddings implícitos | Tesauro explícito + ráfaga del agente |
| **Ranking** | Distancia coseno | Score híbrido 8 señales + Dynamic Multiplicator |
| **Explicabilidad** | Caja negra | Cada dimensión es inspeccionable |
| **Control en caliente** | Reentrenar | INSERT/DELETE en milisegundos |
| **Plasticidad negativa** | No existe | desvincular() + LTD sináptico |
| **Ciclo de vida** | Insert → Query | Corto plazo → Sueño → Largo plazo → Olvido |
| **Asociaciones explícitas** | Solo similitud | Sinapsis con tipos y pesos |
| **Dependencias** | numpy, sentence-transformers, GPU | Cero. SQLite puro |
| **Latencia** | 2-100ms | 2.84ms promedio |
| **Memoria RAM** | 100-500MB | ~18 MB |
| **Funciona offline** | No | Sí |
| **Ráfaga de reminiscencia** | No | LLM genera términos, script ejecuta |
| **Auto-aprendizaje** | No | Co-ocurrencia + sinapsis automáticas |

---

## Benchmarks

Ejecuta `python3 benchmark.py` para comparar BioRAG con LangChain+Chroma en tu máquina.

| Sistema | Latencia avg | Memoria RAM |
|---|---|---|
| **BioRAG** | 2.84 ms | **18.7 MB** |
| LangChain+Chroma | 2.10 ms | 128.7 MB |

BioRAG usa **7x menos memoria**, latencia comparable, **0 dependencias ML**, corre en Raspberry Pi.

---

## Dimensiones Semánticas — v13.4 (Julio 2026)

### Las 7 Dimensiones

| ID | Dimensión | Qué captura | Sub-valores |
|---|---|---|---|
| 1 | emoción | El "Sentir" — carga emocional | 12 (afecto, alegría, frustración, tristeza, preocupación, confusión, sorpresa, miedo, alivio, apatía, culpa, satisfacción) |
| 2 | entidad | El "Qué" — entes, objetos, conceptos | 11 (identidad_individual, social_legal, organizacional, digital, artificial, física_hardware, natural, concepto, institución, evento, vínculo) |
| 3 | acción | El "Hacer/Estar" — verbos, procesos | 11 (física, transformación_material, persistencia_computación, rutina_automática, comunicación, interacción_social, cognitiva, estado_ser, evaluar, observar, fallar) |
| 4 | cualidad | El "Cómo" — propiedades, valoraciones | 11 (dimensión_física, estado_condición, valoración, sensorial, material_composición, temporal_duración, relacional_comparativa, abstracta_conceptual, económica, urgente, auténtica) |
| 5 | coordenada | Espacio y Tiempo | 10 (cronología_absoluta, anclaje_deictico, secuencia_relativa, ciclo_periódico, inclusión_topológica, distancia_proximal, vector_direccional, trayectoria_límite, etapa, hito) |
| 6 | intención | El "Por Qué" — propósito | 8 (aprender, decidir, reflexionar, resolver, solucionar, documentar, desahogar, registrar) |
| 7 | dominio | El "Dónde" — área de aplicación | 10 (técnico, personal, profesional, académico, salud, finanzas, ambiental, social, creativo, espiritual) |

### Score aditivo

```
Score = base_BM25 + (0.30 × dim_score)
```

Las dimensiones SIEMPRE suman, incluso con cero match de texto. El fallback dimensional solo trae nodos sin match de texto si comparten **≥3 dimensiones** con la query.

---

## Historial de Versiones

### v14.0 — Auditoría Técnica Completa (Julio 2026)

Análisis exhaustivo de todo el codebase documentando cada técnica, algoritmo y su equivalencia en el campo. 12 capas de búsqueda en cascada, 8 señales de scoring híbrido, grafo de sinapsis con plasticidad negativa, ciclo de sueño con LTP/LTD/inhibición lateral, dimensiones semánticas como sparse embeddings declarativos, y ráfaga de reminiscencia como recall boost por LLM.

### v13.5 — Auto-Aprendizaje Léxico y Expansión Semántica Orgánica (Julio 2026)

- **Reingeniería de `auto_aprender_desde_sinonimos`**: cruza sinónimos todos contra todos con `itertools.combinations`
- **Soporte para frases compuestas**: límite de validación de 15→35 caracteres
- **Limpieza de ruido**: sinónimos ya no se asocian a IDs internos

### v13.4 — Expansión Dimensional: 7 Dimensiones con 73 Sub-Valores (Julio 2026)

- 7 ejes semánticos (emoción, entidad, acción, cualidad, coordenada, intención, dominio)
- 73 sub-valores categorizados manualmente
- Score aditivo dimensional (+0.30 × dim_score)
- Fallback dimensional con umbral 3
- Herramientas MCP: `listar_tipos_dimension`, `listar_dimensiones_por_tipo`

### v13.0 — Filtro Temporal PRE-hoc y Índices (Julio 2026)

- Filtro temporal en SQL (PRE-hoc, no POST-hoc)
- Índices en `estado` y `creado_en`
- Bug fixes en score de paráfrasis y temporal_params

### v12.0 — Filtros Temporales y Memoria Compartida (Julio 2026)

- `query` opcional en `recordar` — log cronológico
- Parámetros `dias`, `desde`, `hasta`, `autor`
- Warnings automáticos en output de herramientas
- Tool `desvincular` para plasticidad negativa

### v11.3 — Sistema de Dimensiones Semánticas de 5 Ejes (Julio 2026)

- 5 ejes: emocion, entidad, accion, cualidad, coordenada
- 39 valores clasificatorios
- Parámetro `dimensiones` requerido en `aprender`

### v11.2 — Clasificación Emocional (Junio 2026)

- Clasificación emocional de 350 entradas de largo_plazo
- Filtro por emoción en `recordar`
- 7 emociones: neutro, afecto, alegria, sorpresa, frustracion, preocupacion, confusion

### v11.1 — Etiquetado Emocional e Indexación Semántica (Junio 2026)

- Diccionario semántico auto-sustentable
- Union-Find para grupos semánticos disjuntos (58 grupos, 1,292 términos)
- Boost dinámico 1.2x para coincidencias del mismo clúster

### v11.0 — Scoring por Densidad de Coincidencia (Junio 2026)

- Densidad de coincidencia en ráfaga (50% densidad, 35% peso, 15% asociaciones)
- Fix regex boundary para snake_case
- 70/70 tests

### v10.2 — Paráfrasis Obligatorio (Junio 2026)

- Paráfrasis requerido con penalización ×0.95
- Ráfaga sináptica como fallback
- 70/70 tests

### v10.0 — Capas Conceptual y Semántica (Junio 2026)

- Matching por nombre de concepto (Jaccard sobre tokens)
- Expansión por tesauro bidireccional
- Side channel `origen_scores`
- 70/70 tests

### v9.5 — Síntesis de Espectro (Junio 2026)

- Combina resultados de múltiples capas del pipeline
- 94% success rate en 33 queries

### v9.4 — Empatía Sintáctica en Ráfaga (Junio 2026)

- Tolerancia a variaciones morfológicas en ráfaga

### v9.3 — Paginación de Resultados (Junio 2026)

- `pagina` y `limite` en `recordar`

### v9.2 — Ráfaga Optimizada (Junio 2026)

- Sin límite en cantidad de `rafaga_palabras`
- Reducción de queries redundantes

### v9.1 — Renombre Cognitivo (Junio 2026)

- `buscar`→`recordar`, `guardar`→`aprender`, `asociar`→`vincular`
- Aliases legacy preservados

### v9.0 — Plugin OpenCode, Oráculo NotebookLM y Context Window (Junio 2026)

- Plugin OpenCode con inyección invisible de recordatorios
- Oráculo de sesión (`biorag_oraculo_inicio`) con NotebookLM
- Context Window en búsquedas con vecinos sinápticos
- Prefix Matching nativo (FTS5 unicode61)
- 68/68 tests

### v8.2 — FTS5 unicode61, Prefix Wildcards y Context Window (Junio 2026)

- Segunda tabla FTS5 con tokenizer unicode61
- Prefix wildcards automáticos (`react*` → "reactive")
- PALABRA_PREFIJO: filtro DB-side por prefijo
- Pipeline expandido a 9 capas
- 68/68 tests

### v8.1 — Batch FTS5 Optimization (Junio 2026)

- Pre-carga de puentes FTS5 en 1 query (82% más rápido: 56ms→12ms)
- Configuración por entorno con `.env.local`

### v8.0 — Ráfaga de Reminiscencia (Junio 2026)

- **Ráfaga de Reminiscencia**: LLM genera términos, script ejecuta búsqueda
- **Auto-aprendizaje de errores**: excluye interpretaciones erróneas
- **Anclaje Temporal**: bonus por recencia (+0.15 <7d, +0.08 <30d, +0.03 <90d)
- **Dynamic Multiplicator**: fórmula 70/20/10 cuando Jaccard ≥ 0.15
- **Co-ocurrencia automática en sueño**: sinapsis por co-ocurrencia
- 161 nodos activos, 1,177 sinapsis, 1,564 equivalencias

### v7.1 — PALABRA_COMPLETA, Similitud Conceptual y Expansión Semántica (Junio 2026)

- `core/similitud_conceptual.py`: Jaccard vecinos + contenido
- `core/semantica.py`: tesauro bidireccional + auto-aprendizaje
- PALABRA_COMPLETA: word boundary en SQL
- Pipeline de 8 capas
- Decay diferenciado por categoría
- 64 tests

### v6.0 — Estandarización de Categorías e Instalador (Junio 2026)

- 11 categorías madre predefinidas
- Instalador multiplataforma para 7 plataformas
- Sincronización incremental con NotebookLM

### v5.x — Sinapsis, Red Semántica y Optimizaciones (Junio 2026)

- Auto-linking al guardar con overlap coefficient
- Tabla `sinapsis` persistente con tipos y pesos
- Evicción condicional (`BIORAG_PODAR=true`)

### v4.0 — Interceptor V2 (Junio 2026)

- Buffer de sesión con TTL
- Consolidación inmediata
- Heurísticas biomiméticas (30+ patrones léxicos)

### v3.0 — MCP Server (Junio 2026)

- 16 herramientas nativas para IDEs

### v2.x — Cimientos (Junio 2026)

- FTS5 trigram, score híbrido, pipeline multi-capa, LTP/LTD

---

## Producción

| Métrica | v9.0 | v11.1 | v13.4 | v14.0 |
|---|---|---|---|---|
| Pipeline de búsqueda | 8 capas | 8 capas | 9 capas | **12 capas** |
| Señales de scoring | 3 | 3 | 3 | **8 ortogonales** |
| Nodos activos | 135+ | 340 | 438 | — |
| Sinapsis | 1,474+ | 15,521 | — | — |
| Dimensiones | — | 5 (39 sub) | 7 (73 sub) | **7 ejes, 73 valores** |
| Técnicas documentadas | — | — | — | **25 técnicas** |
| Tests | 68/68 | 72/72 | 78/78 | 78/78 |
| Dependencias ML | 0 | 0 | 0 | **0** |
| RAM | ~4 MB | ~12 MB | ~9 MB | **~18 MB** |
| Tools MCP | — | 12 | 15 | **19** |

---

## Licencia

MIT — Dennys J. Marquez (dennysjmarquez@gmail.com)
