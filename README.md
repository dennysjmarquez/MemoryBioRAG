# BioRAG: Sistema de Memoria Cognitiva Biomimética para Agentes de IA

**BioRAG** es un motor de memoria persistente para agentes de inteligencia artificial. Resuelve el problema fundamental de que los LLMs olvidan todo entre sesiones — sin depender de vectores, embeddings ni infraestructura externa. **El sistema emula de forma nativa el comportamiento y las capacidades de una base de datos vectorial** a través de topología de grafos y lógica relacional, eliminando la necesidad de modelos de embedding costosos o servidores dedicados.

Desarrollado en **Python puro con SQLite + FTS5**. Cero dependencias de librerías ML (ni numpy, ni sentence-transformers, ni redes vectoriales). Corre en cualquier lado.

Emula la biología del cerebro humano: **plasticidad sináptica (LTP/LTD)**, **familiaridad difusa**, **inhibición lateral** y **propagación asociativa de recuerdos**. El motor de búsqueda combina coincidencia textual, peso biológico y conectividad del grafo en un score híbrido.

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
  EXPLICA al usuario con sus propias palabras qué encontró
```

**¿Por qué esto es revolucionario?**

| Antes (RAG tradicional) | Ahora (BioRAG con Ráfaga) |
|---|---|
| Si no hay match exacto → "0 resultados" | El LLM "tira flechas" con palabras relacionadas |
| El script busca a ciegas | El LLM interpreta y genera la ráfaga |
| Nodos dormidos se pierden | La ráfaga los despierta y crea sinapsis |
| El usuario debe saber los nombres exactos | El usuario pregunta de forma vaga/coloquial |
| "No encontré nada" | "No encontré X pero encontré Y que dice que..." |

**La clave:** La inteligencia está en el LLM (que genera la ráfaga), la ejecución está en el script (SQLite + FTS5). El usuario no necesita saber los nombres exactos de los archivos ni la jerga técnica. Puede preguntar de forma vaga, errónea o coloquial, y el sistema "adivina" la intención.

**Ejemplo genérico:**
- Usuario: "¿Dónde guardé lo del proyecto nuevo?"
- LLM genera ráfaga: ["proyecto", "código", "desarrollo", "repositorio", "commit", "rama", "branch"]
- Script busca → encuentra un nodo dormido sobre el proyecto
- El nodo se despierta, se crea sinapsis, y el agente responde con lo que encontró

### Comprensión Semántica sin Embeddings

La ráfaga resuelve el problema fundamental de la búsqueda semántica sin embeddings:

```
  USUARIO: "¿Qué documento firmó el monarca?"
          │
          ▼
  FTS5 busca "monarca" → 0 resultados (la palabra no existe)
          │
          ▼
  LLM INTERPRETA: "monarca = gobernante = rey"
  LLM GENERA RÁFAGA: ["rey", "corona", "trono", "reino", "soberano"]
          │
          ▼
  SCRIPT BUSCA "rey" → ENCUENTRA el nodo
          │
          ▼
  RESULTADO: "El rey firmó el decreto"
  SINAPSIS CREADA: monarca → rey (permanente)
```

**¿Por qué funciona sin embeddings?**

| Enfoque Vectorial | Enfoque BioRAG |
|---|---|
| "monarca" se convierte en vector de 1536 dimensiones | El LLM entiende que "monarca" = "rey" |
| Cálculo matemático en espacio vectorial | Ráfaga de 5 palabras relacionadas |
| Requiere GPU + servidores costosos | SQLite + Python puro |
| Comprensión estática (pre-entrenada) | Comprensión dinámica (el LLM genera la ráfaga) |

**La clave:** La comprensión semántica NO está en embeddings — está en el LLM que genera la ráfaga. El LLM es el "cerebro" que entiende el significado, y BioRAG es la "memoria" que almacena y recupera.

**Comparación:**
- **Embeddings:** comprensión semántica en el índice (estático, pre-entrenado)
- **BioRAG:** comprensión semántica en el LLM (dinámico, se adapta al contexto)

El LLM puede generar cualquier ráfaga que se le ocurra, sin limitarse a embeddings pre-entrenados. Eso es más flexible que un vector fijo.

**El sistema se auto-alimenta:** Cada búsqueda exitosa crea nuevas sinapsis. La próxima vez que busques algo similar, el camino ya está pavimentado. El grafo crece con cada uso.

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
        "DESPUES DE CADA PASO: Leer los resultados y EXPlicar al usuario con tus propias palabras QUE encontraste. "
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

### 7. PALABRA_COMPLETA en Fallback 2.5

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

### 8. Co-ocurrencia en Ciclo de Sueño

```python
# core/memory_store.py — ciclo_sueno_consolidacion() (extracto)

# Auto-vincular cada concepto consolidado (aristas por solapamiento de tokens)
from core.sinapsis import auto_vincular
for concepto, contenido, _, _ in recuerdos_sesion:
    auto_vincular(self, concepto, contenido)

# Fase 2: Auto-generar sinapsis por co-ocurrencia
self._auto_generar_co_ocurrencia(recuerdos_sesion)
```

### Resumen de Cambios

| Componente | Qué hace | Archivo |
|---|---|---|
| FTS5 unicode61 | Segunda tabla FTS5 con tokenizer unicode61 | `_crear_tabla_fts()` |
| Prefix wildcards | "react" → "react*" para encontrar "reactive" | `_agregar_prefix_wildcards()` |
| PALABRA_PREFIJO | Filtro DB-side que permite prefijos sin falsos positivos | `__init__()` + `buscar_por_frase()` |
| Batch FTS5 | Pre-carga puentes con 1 query (82% más rápido) | `_similitud_red()` |
| Dynamic Multiplicator | Fórmula 70/20/10 cuando FTS5 falla | `_calcular_score_hibrido()` |
| Side channel origen_scores | Rastrea origen de cada nodo | `buscar_por_frase()` |
| Ráfaga de Reminiscencia | LLM genera 10-15 términos, script ejecuta | `buscar_por_rafaga()` |
| Co-ocurrencia en sueño | Crea sinapsis por co-ocurrencia | `_auto_generar_co_ocurrencia()` |
| PALABRA_COMPLETA en capas | Word boundary en SQL | `buscar_por_frase()` + `_similitud_red()` |
| Protocolo MCP 3 pasos | Enriquecimiento → Ráfaga → Contingencia | `mcp_server.py` + `prompts.py` |
| Configuración por entorno | `.env.local` auto-cargado | `config/__init__.py` |

---

### ¿Es BioRAG una alternativa a una base vectorial?

**Depende de para qué. Pero en su dominio, sí.**

Para el caso de uso de **memoria persistente de un agente**, BioRAG no solo es alternativa — es **superior** en estas dimensiones:

| Dimensión | Vector DB | BioRAG |
|---|---|---|
| Olvido selectivo | No existe | Decay_rate por categoría |
| Ciclo de vida | Insert → Query | Corto plazo → Sueño → Largo plazo → Olvido |
| Introspección | No | Métricas cognitivas + tendencias |
| Asociaciones explícitas | No (solo similitud) | Sinapsis con tipos y pesos |
| Autonomía | Depende de API | 0 dependencias externas |
| Tamaño | Gigabytes | ~4 MB |
| Portabilidad | Atado a infraestructura | Un archivo .db |
| **Ráfaga de reminiscencia** | **No** | **LLM genera 10-15 términos, script ejecuta** |
| **Auto-aprendizaje** | **No** | **Co-ocurrencia + sinapsis automáticas** |
| **Entiende metáforas** | **Depende del embedding** | **Glosario cultural + ráfaga** |
| **Rescata nodos dormidos** | **No** | **La ráfaga los despierta en caliente** |
| **Funciona offline** | **No** | **Sí** |
| **Costo por query** | **Miles de tokens** | **~15 tokens (ráfaga)** |

> **BioRAG no es una alternativa genérica a una vector DB. Es una alternativa específica para memoria de agente, y en ese dominio es mejor que cualquier vector DB.**

---

### Logros Técnicos

- **0 dependencias externas de ML**: ni numpy, ni vectores, ni GPU — SQLite puro con FTS5 trigram
- **Batch FTS5 optimization**: pre-carga puentes FTS5 una sola vez (1 query SQL en vez de N), reduce latencia de 56ms a 12ms (82% más rápido)
- **Calidad preservada**: 100% overlap con búsqueda legacy — el batch FTS5 usa la misma query que el modo legacy
- **Red sináptica de 15,521 aristas**: 340 nodos conectados por auto-linking biomimético + co-ocurrencia automática
- **3,004 equivalencias semánticas**: tesauro bidireccional auto-construido desde vocabulario cargado + sinónimos
- **58 grupos semánticos disjuntos**: Union-Find agrupa 1,292 términos equivalentes para boosting de relevancia
- **Boosting conceptual 1.2x**: resultados que comparten grupo semántico con el query reciben boost dinámico en el score
- **Dynamic Multiplicator**: cuando FTS5 falla, Jaccard toma el control con fórmula 70/20/10
- **Anclaje Temporal**: +0.15 score si nodo accedido <7 días, +0.08 si <30 días, +0.03 si <90 días
- **Ráfaga de Reminiscencia**: `rafaga_palabras` en MCP — emula el proceso humano de "tirar flechas" para recordar
- **Ráfaga se activa con score < 0.5**: no solo con 0 resultados — cuando los resultados son débiles, la ráfaga mejora la búsqueda
- **Instrucción de 5 niveles**: guía para generar mejores palabras de ráfaga (literal → técnico → contexto → problema → emoción)
- **Co-ocurrencia automática en sueño**: el ciclo de sueño crea sinapsis basándose en co-ocurrencia de conceptos
- **PALABRA_COMPLETA en todas las capas FTS5**: previene falsos positivos de trigram ("culo" ≠ "artículos")
- **Protocolo de 4 pasos**: directa → paráfrasis → ráfaga → combinada → contingencia
- **Paráfrasis obligatorio**: variantes semánticas con 4 niveles (sinónimos, registro, perspectiva, abstracción) con penalización ×0.95
- **Scoring por Densidad de Coincidencia**: fórmula 50% densidad + 35% peso sináptico + 15% asociaciones en ráfaga
- **Auto-aprendizaje de errores**: registra interpretaciones erróneas, excluye en próxima búsqueda
- **Similitud conceptual latente**: Jaccard sobre vecinos compartidos + tokens en contenido (60% red + 40% contenido)
- **Expansión semántica por tesauro**: tabla `semantica` bidireccional con auto-aprendizaje
- **Pipeline de búsqueda de 9 capas**: FTS5 AND → OR → Prefix (unicode61) → Semántica → Conceptual → Snap → Cadena → Substring → Trigram
- **Prefix matching nativo**: integración FTS5 unicode61 + función custom `PALABRA_PREFIJO` para matches de prefijo sin falsos positivos de substring
- **Context Window en búsquedas**: resultados incluyen vecinos sinápticos con deduplicación automática para contexto enriquecido
- **Oráculo externo (NotebookLM)**: `biorag_oraculo_inicio` consulta NotebookLM o fallback a BioRAG local para contexto de arranque del agente
- **Decay diferenciado por categoría**: Profile=0.05, Principle=0.2, Project=1.5
- **Métricas cognitivas históricas**: tabla `metricas_cognitivas` con detección de tendencias
- **MCP nativo**: 23 herramientas para OpenCode, VS Code, Cursor, Cline, Antigravity, Claude Code
- **Plugin OpenCode**: inyección invisible de recordatorios BioRAG + toast visual al agente
- **71 tests automatizados**: cobertura completa del motor, sinapsis, semántica, similitud, ráfaga, prefix wildcards, context window, unicode FTS5 y boosting conceptual

---

---

### Arquitectura Cerebral

El sistema funciona como un cerebro artificial dentro de un solo archivo SQLite (`MemoryBioRAG_Data/memory_biorag.db`). Emula de forma nativa el comportamiento de una base de datos vectorial a través de topología de grafos sinápticos y lógica relacional — sin embeddings, sin GPU, sin servidores externos.

#### Flujo General: cómo entra y sale la información

```
  Un agente de IA (Athena, Artemis o Hermes) interactúa con BioRAG
  a través de dos operaciones fundamentales:

                       ┌──────────────────────┐
                       │ AGENTE DE IA (entrada)│
                       └─────┬──────────┬─────┘
                             │          │
                        GUARDAR        BUSCAR
                             │          │
                             ▼          ▼
                ┌────────────────┐ ┌──────────────────┐
                │  Interceptor   │ │  Pipeline de     │
                │  Filtro que    │ │  Búsqueda con    │
                │  detecta qué   │ │  8 capas +       │
                │  vale guardar  │ │  Ráfaga          │
                └───────┬────────┘ └────────┬─────────┘
                        │                   │
                        ▼                   │
              ┌──────────────────┐          │
              │  CORTO PLAZO     │          │ Cada búsqueda
              │  Mesa de trabajo │          │ exitosa refuerza
              │  temporal        │          │ el recuerdo
              └────────┬─────────┘          │ encontrado (LTP)
                       │                    │
                 Ciclo de Sueño             │
                 (consolidación +           │
                  co-ocurrencia)            │
                       │                    │
                       ▼                    ▼
              ┌───────────────────────────────────┐
              │        LARGO PLAZO (corteza)       │
              │                                    │
              │  La memoria permanente. Aquí viven │
              │  todos los recuerdos consolidados  │
              │  con su peso, categoría y          │
              │  conexiones a otros recuerdos.     │
              └───────┬────────────────┬───────────┘
                      │                │
                      ▼                ▼
            ┌────────────────┐  ┌─────────────────┐
            │ RED DE          │  │ TESAURO          │
            │ CONEXIONES      │  │ SEMÁNTICO        │
            │                 │  │                  │
            │ 1,177 aristas   │  │ 1,564 pares      │
            │ (auto + co-     │  │ de equivalencias │
            │  ocurrencia)    │  │ (auto + manual)  │
            └────────────────┘  └─────────────────┘
```

#### Pipeline de Búsqueda: cómo encuentra recuerdos

Cuando un agente busca algo, BioRAG intenta encontrarlo con 8 estrategias
progresivas. Si la primera no da resultados, pasa a la siguiente:

```
  Agente pregunta: "días relax frente al océano"
          │
          ▼
  CAPA 1: Búsqueda exacta (FTS5 AND + PALABRA_COMPLETA)
          │ Encontró? ── Sí ──► Resultados
          │
          No
          ▼
  CAPA 2: Búsqueda flexible (FTS5 OR)
          │ Encontró? ── Sí ──► Resultados
          │
          No
          ▼
  CAPA 2.5: Prefix matching (FTS5 unicode61: "react" → "reactive")
          │ Encontró? ── Sí ──► Resultados
          │
          No
          ▼
  CAPA 3: Expansión semántica (tesauro: "auto" → "vehículo")
          │ Encontró? ── Sí ──► Resultados
          │
          No
          ▼
  CAPA 4: Similitud conceptual (Jaccard vecinos compartidos)
          │ Encontró? ── Sí ──► Resultados (Dynamic Multiplicator)
          │
          No
          ▼
  CAPA 5: Snap reciente (últimos 7 días)
          │ Encontró? ── Sí ──► Resultados
          │
          No
          ▼
  CAPA 6: Evocación por cadena (multi-hop 3 saltos)
          │ Encontró? ── Sí ──► Resultados
          │
          No
          ▼
  CAPA 7: Substring (PALABRA_COMPLETA filtra falsos positivos)
          │ Encontró? ── Sí ──► Resultados
          │
          No
          ▼
  CAPA 8: Trigram tolerance (typo ≥6 chars, PC solo ≤5 chars)
          │ Encontró? ── Sí ──► Resultados
          │
          No
          ▼
  RÁFAGA DE REMINISCENCIA (si el agente usa rafaga_palabras)
          │ "Tira flechas" con 10-15 términos relacionados
          │ Encuentra nodos dormidos, los despierta
          │ Crea sinapsis automáticamente
          │ Encontró? ── Sí ──► Resultados
          │
          No
          ▼
  CONTINGENCIA: Agente busca en contexto del chat
          │ Si encuentra → guarda con biorag_guardar
          │ Si no → responde "no tengo ese recuerdo"
```

#### Dynamic Multiplicator:-score adaptativo

Cuando la búsqueda literal falla y la similitud conceptual (Jaccard) encuentra resultados, el score se recalcula dinámicamente:

```
  Score normal:    60% BM25 + 25% peso sináptico + 15% asociaciones
  Score latente:   70% Jaccard + 20% peso sináptico + 10% asociaciones

  Se activa cuando:
  - FTS5 no encontró el nodo (búsqueda literal falló)
  - Jaccard ≥ 0.15 (similitud conceptual mínima)
  - El nodo viene de capas 1.5, 1.7 o 1.9 (semánticas)
```

#### Ráfaga de Reminiscencia: cómo el sistema "intenta recordar"

Emula el proceso humano de "tirar flechas" cuando no recuerdas algo:

```
  Usuario: "¿Dónde pasé mis días de relax frente al océano?"
          │
          ▼
  Búsqueda normal: "días relax frente al océano"
          │ Resultados: solo nodos técnicos (no personales)
          │
          ▼
  Agente activa RÁFAGA: ["playa","mar","costa","verano","descanso",
                          "sol","arena","olas","hotel","viaje"]
          │
          ▼
  Script busca con cada palabra (activos + dormidos)
          │
          ├─ "playa" → encuentra hermes_oec_identidad (dormido)
          │  "Yo fui para la playa en el verano pasado..."
          │
          ├─ "mar" → encuentra más nodos relacionados
          │
          ├─ "verano" → encuentra más nodos
          │
          ▼
  Auto-despertar: hermes_oec_identidad pasa a "activo"
  Auto-sinapsis: playa → hermes_oec_identidad (peso: 0.6)
  Auto-sinapsis: mar → hermes_oec_identidad (peso: 0.6)
          │
          ▼
  Agente lee el contenido y EXPlica al usuario:
  "Encontré que fuiste a la playa en el verano pasado.
   Disfrutaste del sol, la arena y las olas del mar."
```

#### PALABRA_COMPLETA: word boundary en DB

FTS5 trigram matchea substrings de 3+ chars. PALABRA_COMPLETA evita falsos positivos:

```
  Sin filtro:    "culo" matchea "artículos" (comparte trigrama "cul")
  Con filtro:    "culo" NO matchea "artículos" (\bculo\b = word boundary)

  Aplicado en: Fallback 1.0, 1.7 (puentes), 1.8 (snap), 1.9 (semillas),
               2.5 (solo palabras ≤5 chars — preserva tolerancia a typos)
```

#### Ciclo de Sueño: cómo el cerebro se mantiene sano

```
  1. CONSOLIDAR ─── Mover de corto a largo plazo (+0.20)
  2. CO-OCURRENCIA ─── Crear sinapsis entre conceptos que co-ocurren
  3. CONECTAR ───── Auto-linking por solapamiento de tokens
  4. DEBILITAR ──── LTD: -0.05 × velocidad según categoría
  5. DORMIR ─────── Recuerdos débiles (≤0.05) pasan a dormido
  6. EQUILIBRAR ─── Inhibición lateral (límite: n_activos × 1.6)
  7. REGISTRAR ──── Métricas cognitivas del ciclo
  8. PODAR ──────── (opcional) Borrar nodos dormidos con peso ≤0.01
```

#### Protocolo de 3 pasos (MCP)

El agente sigue este flujo obligatorio al buscar:

```
  PASO 1: biorag_buscar(query="frase del usuario")
          Si es abstracta → interpretar + agregar 3-5 palabras clave

  PASO 2: Si PASO 1 da 0 resultados
          biorag_buscar(query="...", rafaga_palabras=[10-15 términos])

  PASO 3: Si PASO 2 da 0 resultados o puro ruido
          Buscar en contexto del chat → guardar con biorag_guardar

  DESPUÉS DE CADA PASO: Leer resultados y explicar con propias palabras
```

---

## Historial de Versiones

### v11.1 — Etiquetado Emocional e Indexación Semántica (Junio 2026)

**Mapeo de estados de ánimo y boosting de relevancia conceptual en el ranking híbrido.**

**Etiquetado Emocional y Cognitivo (Opción B):**
- **Clasificación emocional integrada**: El middleware de autoguardado extrae expresiones sentimentales cotidianas y las guarda con etiquetas sinápticas estandarizadas (`emocion_afecto`, `emocion_frustracion`, `emocion_preocupacion`, `emocion_satisfaccion`) en la columna `sinonimos`.
- **Diccionario semántico auto-sustentable**: Mapeo de términos cotidianos (ej. `"te quiero"`, `"molesto"`) en tiempo de inicio para que búsquedas abstractas evoquen el recuerdo correcto mediante FTS5.
- **Test 72**: Cobertura de evocado por emoción y validación del interceptor.

**Indexación Semántica y Boosting por Grupos Disjuntos:**
- **`grupos_semanticos` y `grupo_terminos`**: Algoritmo Union-Find que agrupa equivalencias en clusters disjuntos.
- **Nueva columna `conceptos_ids`**: Almacena los IDs de grupos semánticos presentes en el contenido.
- **Boost dinámico 1.2x**: Multiplica por 1.2 el score híbrido para coincidencias del mismo clúster conceptual.

- **Archivos modificados**: `core/semantica.py`, `core/memory_store.py`, `middleware/auto_guardado.py`, `test_memory.py`, `vocabulario_inicial.json`
- **Tests**: 72/72 pasando
- **Producción**: 340 nodos, 15,521 sinapsis, 3,004 equivalencias, 58 grupos semánticos, 1,292 términos mapeados

### v11.0 — Scoring por Densidad de Coincidencia (Junio 2026)

**El scoring de ráfaga ahora emula similitud coseno usando densidad de coincidencia.**

- **Reemplazo del scoring híbrido en `buscar_por_rafaga`**: fórmula de Densidad de Coincidencia (50% densidad, 35% peso sináptico, 15% asociaciones)
- **Corrección del error de regex boundary (`\b`)**: normalización de guiones a espacios en 6 puntos del pipeline para conceptos snake_case
- **Fix deduplicación en merge** (`mcp_server.py` L324): clave de concepto en lugar de contenido
- **Verificación de recall exitosa**: todas las vías (ráfaga, paráfrasis, combinación) con convergencia estable
- **Tests**: 70/70 pasando

### v10.2 — Paráfrasis Obligatorio y Semántica Inferida (Junio 2026)

**Tres capas de recall semántico: paráfrasis, ráfaga sináptica e inferencia.**

- **Paráfrasis obligatorio**: `str` comma-separated con penalización ×0.95 por variante
- **Ráfaga sináptica**: rescata nodos con palabras clave cuando paráfrasis falla
- **Inferencia como sugerencia**: `auto_guardar=False` por defecto — el agente decide si guardar
- **ORDER BY corregido**: fórmula `0.5 + 0.5 * peso` para scoring consistente
- **Tests**: 70/70 pasando

### v10.0 — Capas Conceptual y Semántica para Recall Mejorado (Junio 2026)

- **Capa conceptual**: matching por nombre de concepto con Jaccard sobre tokens
- **Capa semántica**: expansión por tesauro con matching bidireccional
- **Side channel `origen_scores`**: rastrea origen de cada resultado para Dynamic Multiplicator
- **Tests**: 70/70 pasando

### v9.5 — Síntesis de Espectro para Recall Comprehensivo (Junio 2026)

- **Spectrum synthesis**: combina resultados de múltiples capas del pipeline
- **Prueba final**: 33 queries, 94% success rate (15/15 FTS5 directo, 4/4 sinónimos, 3/3 inglés)
- **Tests**: 70/70 pasando

### v9.4 — Empatía Sintáctica en Ráfaga (Junio 2026)

- **Syntactic empathy**: la ráfaga de reminiscencia tolera variaciones morfológicas
- **Tests**: 70/70 pasando

### v9.3 — Paginación de Resultados (Junio 2026)

- **Paginación**: parámetros `pagina` y `limite` en `recordar`/`buscar`
- **Tests**: 68/68 pasando

### v9.2 — Ráfaga Optimizada y Sin Límite de Términos (Junio 2026)

- **Ráfaga ilimitada**: sin límite en cantidad de `rafaga_palabras`
- **Optimización de performance**: reducción de queries redundantes
- **Tests**: 68/68 pasando

### v9.1 — Renombre Cognitivo de Herramientas (Junio 2026)

- **Herramientas renombradas**: `buscar`→`recordar`, `guardar`→`aprender`, `asociar`→`vincular`, `sueno`→`consolidar`, `estado`→`introspeccion`, `corteza`→`mapear`
- **Aliases legacy**: las herramientas antiguas siguen funcionando
- **Tests**: 68/68 pasando

### v9.0 — Plugin OpenCode, Oráculo NotebookLM y Context Window Cognitivo (Junio 2026)

**BioRAG se expande: plugin de integración con OpenCode, contexto de sesión desde NotebookLM y búsqueda enriquecida con vecinos sinápticos.**

- **Plugin OpenCode**: inyección invisible de recordatorios BioRAG en cada turno del usuario. Hook `chat.message` agrega `<system-reminder>` con autorización de herramientas en Plan Mode. Hook `event` (`session.idle`) muestra toast visual al agente. Sin registro en `opencode.json` — auto-carga desde `~/.config/opencode/plugins/`.
- **Oráculo de sesión (`biorag_oraculo_inicio`)**: consulta NotebookLM externo o fallback a BioRAG local para contexto de arranque del agente. Configurable via `BIORAG_PROMPT_INICIO` y `BIORAG_NOTEBOOK_ID`.
- **Context Window en búsquedas**: resultados incluyen vecinos sinápticos con deduplicación automática. El agente recupera memorias con su contexto asociado, imitando la memoria humana.
- **Prefix Matching nativo**: integración FTS5 unicode61 + función `PALABRA_PREFIJO` para que "react" encuentre "reactive" sin falsos positivos de substring. Pipeline expandido a 9 capas.
- **Configuración mejorada**: parseo `.env.local` con soporte multi-línea y secuencias de escape para prompts complejos.
- **Instalación**: `python3 install.py` copia el plugin automáticamente. Instalación manual: `cp plugin/opencode-biorag-remember-plugin.ts ~/.config/opencode/plugins/`.
- **Requisitos**: OpenCode con soporte de plugins y MCP de BioRAG configurado.
- **Tests**: 68/68 pasando

### v8.2 — FTS5 unicode61, Prefix Wildcards y Context Window (Junio 2026)

**Mejora de recall sin perder precisión: prefix matching nativo en BioRAG. Los resultados ya no vienen solos: cada recuerdo trae su contexto asociado.**

- **FTS5 unicode61**: segunda tabla FTS5 con tokenizer unicode61 para búsquedas de palabras completas y prefix matching. Complementa la tabla trigram existente (typos/substrings).
- **Prefix wildcards automáticos**: cada término de búsqueda se expande con `*` (`react` → `react*`), permitiendo encontrar "reactive", "reactivity", "react hooks".
- **PALABRA_PREFIJO**: nueva función SQLite que filtra por prefijo de palabra. Permite `react` → `reactive` pero sigue bloqueando falsos positivos de substring como `culo` → `artículos`.
- **Pipeline enriquecido**: la nueva capa 2.5 (unicode61 prefix) se ejecuta junto a las capas FTS5 AND/OR, aumentando recall sin degradar velocidad.
- **Migración segura**: la tabla unicode61 se crea y puebla automáticamente al inicializar. Triggers mantienen sincronización en INSERT/UPDATE/DELETE.
- **Context window en `buscar_por_frase`**: nuevo parámetro `context_window=N` que expande cada resultado principal con hasta N vecinos obtenidos de la tabla `sinapsis` ordenados por peso.
- **Deduplicación automática**: un vecino compartido por varios resultados principales aparece una sola vez en la respuesta.
- **Score de contexto atenuado**: los nodos de contexto reciben un score menor que los resultados principales (`score_principal * 0.6 + peso_sinaptico * 0.2`), preservando la jerarquía visual.
- **Respeto de profundidad**: los vecinos heredan el filtro `activos`/`profundo` de la búsqueda principal.
- **Sin cambio de API**: `context_window=0` es el default; el formato del resultado no cambia.
- **Exposición en MCP**: `biorag_buscar` ahora acepta `context_window` para que el LLM pida contexto explícitamente.
- **Archivos modificados**: `core/memory_store.py` (`buscar_por_frase`, `_crear_tabla_fts`, `_poblar_fts_unicode`, `_agregar_prefix_wildcards`), `mcp_server.py` (`biorag_buscar`), `test_memory.py` (tests 67-68)
- **Tests**: 68/68 pasando

#### Validación Externa: Análisis de Arena AI

> *"Esto es un salto arquitectónico real. La v8 no es una mejora incremental. Es un cambio de paradigma en cómo BioRAG encuentra información."*

**Lo que destacó:**
- La Ráfaga de Reminiscencia es "la implementación más cercana al proceso humano de recordar"
- El Dynamic Multiplicator "sabe cuándo cambiar de estrategia automáticamente"
- El Protocolo de 3 pasos es "exactamente el proceso humano: intentas recordar → lanzas asociaciones → preguntas a alguien"
- "Memoria que aprende mientras recuerda — cada búsqueda exitosa deja conexiones nuevas"

**Números de crecimiento v7 → v8.2:** Sinapsis +154%, Activos +347%, Energía sináptica +358%

> *"Esto es lo que queríamos construir desde el principio."*

### v8.1 — Batch FTS5 Optimization (Junio 2026)

**Optimización de performance: 82% más rápido sin perder calidad.**

- **Batch FTS5**: pre-carga todos los nodos puente con UNA sola query FTS5 (en vez de N queries separadas por candidato). Reduce latencia de 56ms a 12ms.
- **Calidad preservada**: el batch FTS5 usa la misma query que el modo legacy — 100% overlap en resultados.
- **Configuración por entorno**: `.env.local` auto-cargado con 12 parámetros configurables.
- **Corrección de bug**: el batch anterior usaba substring matching que degradaba calidad (33% overlap). Corregido a FTS5 batch (100% overlap).
- **Archivos modificados**: `core/similitud_conceptual.py` (`_similitud_red`, `score_similitud_latente`), `core/memory_store.py` (`buscar_por_frase`)
- **Tests**: 64/64 pasando

### v8.0 — Ráfaga de Reminiscencia, Auto-aprendizaje y Dynamic Multiplicator (Junio 2026)

**El sistema aprende de sus propios errores y ahora "intenta recordar" como un cerebro humano.**

- **Anclaje Temporal en Scoring**: bonus de +0.15 si el nodo fue accedido en los últimos 7 días, +0.08 si en los últimos 30 días, +0.03 si en los últimos 90 días. Los nodos frescos suben en el ranking.
- **Auto-aprendizaje de errores**: cuando el usuario rechaza un resultado ("no es eso"), el agente registra el error como lección (`error_interpretacion_[palabra]`). La próxima vez que se busque esa palabra, el sistema excluye la interpretación errónea.
- **Glosario Cultural actualizable**: las correcciones de interpretación se guardan como lecciones que afectan búsquedas futuras.
- **Contexto motivacional**: prompts.py instruye al agente para guardar el "porqué" detrás de las enseñanzas.
- **Archivos modificados**: `core/memory_store.py` (`_calcular_score_hibrido`, `buscar_por_rafaga`), `config/prompts.py` (REGLA #1, REGLA #2)
- **Tests**: 64/64 pasando

#### Nuevos componentes:
- **`buscar_por_rafaga()`** en `memory_store.py`: búsqueda por ráfaga de reminiscencia. Cuando la búsqueda normal falla, el agente "tira flechas" con 10-15 términos relacionados. El script busca con cada palabra (activos + dormidos), despierta nodos encontrados y crea sinapsis automáticamente.
- **`_auto_generar_co_ocurrencia()`** en `memory_store.py`: crea sinapsis automáticamente durante el ciclo de sueño basándose en co-ocurrencia de conceptos en `corto_plazo` y `comunicaciones`.
- **`rafaga_palabras`** parámetro en `biorag_buscar` MCP: lista de términos relacionados que el agente inyecta para la búsqueda de reminiscencia.
- **`contingencia_contexto`** señal en respuesta MCP: cuando no hay resultados, el tool indica al agente que busque en su contexto de conversación.
- **Dynamic Multiplicator** en `_calcular_score_hibrido()`: cuando FTS5 falla y Jaccard ≥ 0.15, cambia la fórmula de scoring a 70/20/10 (Jaccard/peso/asoc) en lugar de 60/25/15.

#### Mejoras al pipeline:
- **PALABRA_COMPLETA en todas las capas FTS5**: capas 1.0, 1.7 (puentes), 1.8 (snap), 1.9 (semillas) ahora filtran con word boundary en SQL.
- **PALABRA_COMPLETA incluye sinonimos**: `COALESCE(l.sinonimos, '')` en el WHERE preserva la búsqueda por sinónimo.
- **PALABRA_COMPLETA diferenciada en 2.5**: solo aplica a palabras ≤5 chars (preserva tolerancia a typos en palabras largas).
- **Co-ocurrencia en sueño**: el ciclo de sueño ahora crea sinapsis basándose en pares de conceptos que co-ocurren en la misma sesión.

#### Protocolo MCP:
- **Descripción de `biorag_buscar`** actualizada con protocolo de 3 pasos: enriquecimiento → ráfaga → contingencia.
- **`prompts.py` REGLA #1** actualizada: flujo de 3 pasos + "explicar con propias palabras".
- **Glosario Cultural**: Principle en BioRAG con mapa de traducción de metáforas del usuario.
- **Protocolo de enriquecimiento**: Principle en BioRAG con directiva de búsqueda cognitiva.

#### Producción:
- 161 nodos activos, 17 dormidos, 1,177 sinapsis, 1,564 equivalencias
- 64 tests automatizados (sin regressiones)
- 0 dependencias externas

### v7.1 — PALABRA_COMPLETA, Similitud Conceptual y Expansión Semántica (Junio 2026)

- **`core/similitud_conceptual.py`** (módulo nuevo): Jaccard vecinos + contenido, score 60/40, umbral 0.10
- **`core/semantica.py`** (módulo nuevo): tesauro bidireccional + auto-aprendizaje, 1,564 equivalencias
- **PALABRA_COMPLETA SQLite function**: word boundary en SQL, previene "culo" → "artículos"
- **Pipeline de 8 capas**: FTS5 AND → OR → Semántica → Conceptual → Snap → Cadena → Substring → Trigram
- **Decay diferenciado**: Profile=0.05, Principle=0.2, Project=1.5
- **Métricas cognitivas**: tabla `metricas_cognitivas` + tool `biorag_metricas_historial`
- **64 tests automatizados**
- **Production**: 47 nodos activos, 451 sinapsis, 1,172 equivalencias

### v6.0 — Estandarización de Categorías e Instalador Multiplataforma (Junio 2026)

- **Esquema de categorías unificado**: 11 categorías madre predefinidas
- **Instalador multiplataforma**: `install.py` configura BioRAG en 7 plataformas
- **Base de sincronización incremental**: tabla `sync_log` + triggers selectivos
- **Nuevas herramientas MCP**: `biorag_listar_categorias`, `biorag_sync_status`, `biorag_export_sync`, `biorag_export_full`

### v5.1 — Optimizaciones de Motor (Junio 2026)

- **Truncado en el motor**: `preview_chars` ahorra RAM
- **Evicción condicional**: `BIORAG_PODAR=true` borra nodos dormidos con peso ≤0.01
- **FTS5 pre-filter en auto_vincular**: usa FTS5 MATCH para pre-filtrar candidatos

### v5.0 — Sinapsis y Red Semántica (Junio 2026)

- **Auto-linking al guardar**: overlap coefficient crea aristas automáticamente
- **Tabla `sinapsis` persistente**: aristas con tipos y pesos
- **`buscar_vecinos()`**: navegación del grafo
- **Categorización automática**: inferencia por palabras clave

### v4.0 — Interceptor V2 (Junio 2026)

- **Buffer de sesión con TTL**: autoguardado heurístico
- **Consolidación inmediata**: sin necesidad de `biorag_sueno`
- **Heurísticas biomiméticas**: detección de 30+ patrones léxicos

### v3.0 — MCP Server (Junio 2026)

- **Servidor MCP**: 16 herramientas nativas para IDEs
- **Resources MCP**: acceso directo a nodos
- **Prompt MCP**: system prompt inyectable

### v2.x — Cimientos (Junio 2026)

- **FTS5 trigram**: tolerancia a typos
- **Score híbrido**: BM25 + peso sináptico + asociaciones
- **Pipeline de búsqueda multi-capa**
- **LTP/LTD**: plasticidad sináptica

---

## BioRAG vs. Bases de Datos Vectoriales

| Capacidad | Base de Datos Vectorial | BioRAG |
|---|---|---|
| **Similitud semántica** | Embeddings (768-1536 dims) | Jaccard + co-ocurrencia + ráfaga |
| **Tolerancia a typos** | Depende del modelo | FTS5 trigram nativo |
| **Expansión de queries** | Embeddings implícitos | Tesauro explícito + ráfaga del agente |
| **Ranking** | Distancia coseno | Score híbrido + Dynamic Multiplicator |
| **Dependencias** | numpy, sentence-transformers, GPU | Cero. SQLite puro |
| **Latencia** | 2-100ms (con embeddings reales) | 2.84ms promedio |
| **Memoria RAM** | 100-500MB | **18.7MB** (7x menos) |
| **Memoria adaptativa** | Estática | Dinámica: LTP/LTD, co-ocurrencia, ráfaga |
| **Auto-aprendizaje** | No | Co-ocurrencia + sinapsis automáticas |
| **Entiende metáforas** | Depende del embedding | Glosario cultural + ráfaga |
| **Funciona offline** | No | Sí |

---

## Benchmarks (Ejecuta tus propias pruebas)

Ejecuta `python3 benchmark.py` para comparar BioRAG con LangChain+Chroma en tu máquina.

**Resultados en DB producción (135 nodos, Junio 2026):**

| Búsqueda | Latencia promedio |
|----------|-------------------|
| **FTS5 directo** | 9.3 ms |
| **Jaccard (batch FTS5)** | 10.1 ms |
| **Promedio general** | 12.0 ms |

**Comparación con LangChain+Chroma (100 nodos):**

| Sistema | Latencia avg | Memoria RAM |
|---------|--------------|-------------|
| **BioRAG** | 2.84 ms | **18.7 MB** |
| LangChain+Chroma | 2.10 ms | 128.7 MB |

**Interpretación:**
- BioRAG usa **7x menos memoria** que LangChain+Chroma (18.7 MB vs 128.7 MB)
- Latencia comparable (2.84ms vs 2.10ms)
- BioRAG tiene **0 dependencias externas de ML** (no requiere Chroma, FAISS, ni embeddings)
- BioRAG corre en cualquier lado (incluso en Raspberry Pi)
- Con batch FTS5, las búsquedas Jaccard bajan de 56ms a 12ms (82% más rápido)

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
  │    ├── memory_store.py      # Motor: LTP/LTD, 9 capas, Dynamic Multiplicator,
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

### Protocolo de 3 pasos en `recordar`

```python
# PASO 1: Búsqueda con interpretación
biorag_buscar(query="días relax frente al océano playa vacaciones")

# PASO 2: Si falla, ráfaga de términos relacionados
biorag_buscar(
    query="días relax frente al océano",
    rafaga_palabras=["playa","mar","costa","verano","descanso","sol","arena","olas"]
)

# PASO 3: Si todo falla, contingencia_contexto=True
# → El agente busca en su contexto de conversación
# → Si encuentra, guarda con biorag_guardar
```

---

## Variables de entorno (opcionales)

Los defaults están en el código. Las variables de entorno son para **override** solamente.

### Base de Datos

| Variable | Default | Descripción |
|----------|---------|-------------|
| `BIORAG_PATH` | `./MemoryBioRAG_Data/memory_biorag.db` | Ruta al archivo .db donde BioRAG guarda la memoria |

### Búsqueda y Rendimiento

| Variable | Default | Descripción |
|----------|---------|-------------|
| `BIORAG_LIMITE_MCP` | `10` | Cuántos resultados retorna cada búsqueda MCP por defecto |
| `BIORAG_CANDIDATOS_SIMILITUD` | `100` | Cuántos nodos candidatos evalúa para similitud conceptual (Jaccard). Más = más preciso pero más lento |
| `BIORAG_MAX_SALTOS_CADENA` | `3` | Cuántos hops hace en evocación por cadena. Cada salto aplica decay: salto 1=0.50, salto 2=0.25, salto 3=0.125 |
| `BIORAG_LIMITE_DEFAULT` | `5` | Cuántos resultados máximo saca cada capa del pipeline de búsqueda |
| `BIORAG_UMBRAL_JACCARD` | `0.15` | Score mínimo Jaccard para considerar similitud conceptual (0.0=acepta todo, 1.0=solo idénticos) |
| `BIORAG_LIMITE_SIMILITUD` | `5` | Cuántos resultados retorna la capa de similitud conceptual latente |
| `BIORAG_LIMITE_RAFTAGA` | `5` | Cuántos resultados retorna cada palabra de la ráfaga de reminiscencia |
| `BIORAG_LIMITE_EVOCACION` | `5` | Cuántos resultados totales permite la evocación por cadena (multi-hop) |

### Ráfaga de Reminiscencia

| Variable | Default | Descripción |
|----------|---------|-------------|
| `BIORAG_RAFTAGA_ACTIVA` | `true` | Activa o desactiva completamente la ráfaga (la feature más poderosa de BioRAG) |
| `BIORAG_THRESHOLD_RAFTAGA` | `0.5` | Score mínimo del top resultado para activar la ráfaga automáticamente. Si score < 0.5, la ráfaga se dispara |

### Ejemplo rápido

```bash
# Solo cambiar el límite de resultados
export BIORAG_LIMITE_MCP=5

# Probar con candidatos reducidos (más rápido)
export BIORAG_CANDIDATOS_SIMILITUD=50

# Desactivar ráfaga (no recomendado)
export BIORAG_RAFTAGA_ACTIVA=false
```

### Alternativa: archivo .env.local

```bash
cp .env.example .env.local
# Editar .env.local con tus valores personalizados
```

**Nota:** Si no estableces ninguna variable, el sistema usa los defaults del código.

## Producción

| Métrica | v9.0 | v11.1 |
|---|---|---|
| Nodos activos | 135+ | 340 |
| Nodos dormidos | 58+ | — |
| Sinapsis | 1,474+ | 15,521 |
| Equivalencias | 1,734+ | 3,004 |
| Grupos semánticos | — | 58 |
| Términos mapeados | — | 1,292 |
| Tests | 68/68 pasando | 72/72 pasando |
| Dependencias externas | 0 | 0 |
| Tamaño DB | ~4 MB | ~12 MB |

---

## Licencia

MIT — Dennys J. Marquez (dennysjmarquez@gmail.com)
