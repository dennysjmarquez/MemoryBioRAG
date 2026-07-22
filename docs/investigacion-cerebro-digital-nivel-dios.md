# Investigación: Cerebro Digital Nivel Dios — Sinapsis, Similitud y Memoria Biológica sin Embeddings

**Fecha:** 2026-07-22  
**Autor:** Athena-OEC (investigación) + Dennys (visión)  
**Objetivo:** Elevar BioRAG a un sistema de memoria cognitiva análoga al cerebro humano, sin depender de modelos embebidos (embeddings), usando pura matemática y arquitectura de grafos.

---

## 1. ESTADO ACTUAL: QUÉ TENEMOS Y QUÉ FALTA

### 1.1 Lo que BioRAG ya hace bien

| Componente | Descripción | Estado |
|---|---|---|
| **FTS5 trigram** | Búsqueda de texto completo con prefix matching | Funcional |
| **Jaccard sobre vecinos** | Similitud entre nodos por vecinos compartidos | Funcional |
| **Spreading activation** | Propagación de activación por el grafo de sinapsis | Funcional |
| **LTD/LTP** | Long-Term Depression / Potenciation en pesos | Funcional |
| **Inhibición lateral** | Dormir nodos débiles para liberar energía | Funcional |
| **Inferencia transitiva** | Sinapsis latentes por caminos de 2-3 saltos | Funcional |
| **Co-ocurrencia** | Auto-crear sinapsis por co-ocurrencia en sesión | Funcional |
| **Dynamic Multiplicator** | Score compuesto: 70% Jaccard + 20% peso + 10% asociaciones | Funcional |
| **Ráfaga de reminiscencia** | 5 niveles: Literal, Técnico, Contexto, Problema, Emoción | Funcional |

### 1.2 Lo que falta (según análisis externo)

1. **Sinapsis latentes demasiado ruidosas**: La inferencia transitiva actual (CTE recursiva) genera muchas conexiones débiles sin validación semántica real
2. **Sin embeddings no hay "distancia semántica" real**: Jaccard sobre tokens es una aproximación, no captura sinónimos profundos
3. **Sin memoria de largo plazo activa**: Los nodos dormidos (>80%) son inalcanzables
4. **Sin mecanismo de "atención"**: No hay forma de enfocar búsqueda en un contexto específico

---

## 2. MÉTODOS PRE-EMBEDDING: LO QUE LA CIENCIA YA SABÍA

### 2.1 Sparse Distributed Memory (SDM) — Pentti Kanerva (1988)

**Fuente:** Wikipedia, paper original "Sparse Distributed Memory" (MIT Press, 1988)

#### Concepto
SDM es un modelo matemático de memoria a largo plazo que usa **vectores binarios de alta dimensión** (ej: 1000 bits) para almacenar y recuperar información por similitud, sin embeddings.

#### Mecanismo
1. Cada recuerdo se codifica como un vector binario de `n` bits (ej: n=1000)
2. La memoria tiene "ubicaciones físicas" (hard locations) con direcciones fijas
3. Para escribir: se activan TODAS las ubicaciones dentro de un radio `r` (Hamming distance) y se suma el patrón
4. Para leer: se activan las mismas ubicaciones y se promedia → resultado aproximado
5. La recuperación es **parcial**: si el query está cerca del original, se recupera el recuerdo completo

#### Propiedades clave
- **Distancia de Hamming** = similitud: 2 puntos con pocos bits diferentes son "parecidos"
- **Alta dimensionalidad** = propiedades curiosas: puntos aleatorios están todos a distancia similar
- **Sparsidad**: solo ~1% de ubicaciones se activan por query → eficiente
- **Content-addressable**: busca por contenido, no por dirección
- **Tolerante a ruido**: bits corruptos aún recuperan el recuerdo original

#### Aplicación a BioRAG
```
PROBLEMA ACTUAL: Jaccard solo compara tokens literales
SOLUCIÓN SDM: 
  1. Codificar cada nodo como "firma binaria" (hash de tokens + sinónimos + dimensión)
  2. Buscar por Hamming distance en vez de Jaccard puro
  3. Radio de búsqueda configurable (más radio = más recall, menos precisión)
  4. Escalable: O(n) simple, no necesita matriz de similitud
```

#### Fórmula de distancia
```
d(x, y) = número de bits diferentes entre x y y (Hamming distance)
Similitud = 1 - d(x, y) / n
```

#### Implementación práctica
- Para cada nodo, generar un "código disperso" (sparse code) de 1000-5000 bits
- El código se genera combinando: hash de tokens + posición en categorías + relaciones semánticas
- La búsqueda se hace contando bits en común (popcount)
- **Velocidad**: O(1) por comparación, O(n) para buscar entre todos los nodos
- **Memoria**: ~1KB por nodo (1000 bits)

---

### 2.2 Latent Semantic Analysis (LSA) — Deerwester et al. (1990)

**Fuente:** "Indexing by Latent Semantic Analysis" (Journal of the American Society for Information Science)

#### Concepto
LSA descubre **temas ocultos** (latent semantics) en una matriz de co-ocurrencia documento-palabra usando **SVD (Singular Value Decomposition)**.

#### Mecanismo
1. Construir matriz `M[términos × documentos]` con conteos TF-IDF
2. Aplicar SVD: `M = U × Σ × V^T`
3. Truncar a `k` dimensiones (ej: k=100-300)
4. Las `k` dimensiones son los "temas latentes"
5. Dos documentos cercanos en el espacio de `k` dimensiones son semánticamente similares

#### Propiedades
- **Captura sinónimos**: "coche" y "automóvil" aparecen en contextos similares → sus vectores son cercanos
- **Captura polisemia**: "banco" aparece en contextos financieros Y de ríos → dimensiones separadas
- **Determinista**: mismo dataset → mismos resultados (sin aleatoriedad)
- **Interpretable**: cada dimensión puede interpretarse como un "tema"

#### Aplicación a BioRAG
```
PROBLEMA ACTUAL: No hay forma de encontrar sinónimos sin WordNet
SOLUCIÓN LSA:
  1. Construir matriz co-ocurrencia nodo × token (ya tenemos FTS5)
  2. Aplicar SVD truncado (numpy.linalg.svd) → k=100 dimensiones
  3. Cada nodo tiene un "vector latente" de 100 floats
  4. Búsqueda por coseno en el espacio latente
  5. Actualizar incrementalmente cuando se consolida un nodo nuevo

LIMITACIÓN: Requiere recalcular periódicamente (costoso O(n³))
MITIGACIÓN: Solo recalcular cuando hay >10% de nodos nuevos desde última vez
```

---

### 2.3 Hyperspace Analogue to Language (HAL) — Lund & Burgess (1996)

**Fuente:** "Introduction to the Field of Semantic Memory" (Burgess & Lund, 1997)

#### Concepto
HAL construye **vectores de co-ocurrencia en ventana deslizante**: dos palabras que aparecen cerca una de la otra tienen vectores similares.

#### Mecanismo
1. Definir ventana de contexto (ej: 10 palabras)
2. Para cada par de palabras en la ventana, incrementar score
3. Construir matriz cuadrada `[palabras × palabras]`
4. La similitud entre dos palabras = coseno de sus vectores fila

#### Propiedades
- **Captura relations**: no solo qué palabras co-ocurren, sino en qué orden
- **Simple**: solo conteo de co-ocurrencias
- **Escala lineal**: O(n × ventana)
- **Captura prototipos**: "perro" hereda propiedades de "animal", "ladrido", "peludo"

#### Aplicación a BioRAG
```
PROBLEMA ACTUAL: Co-ocurrencia actual solo mira tokens compartidos
SOLUCIÓN HAL:
  1. Usar contenido de nodos como "corpus"
  2. Construir matriz de co-ocurrencia ventana=10
  3. Para cada par de nodos, calcular coseno de vectores de co-ocurrencia
  4. Si coseno > umbral, crear sinapsis semántica (no por tokens compartidos)

VENTAJA: Encuentra relaciones que Jaccard no ve
EJEMPLO: "hipocampo" y "memoria" co-ocurren frecuentemente → coseno alto
          aunque compartan pocos tokens literales
```

---

### 2.4 Random Indexing — Kanerva (1997), Sahlgren (2005)

**Fuente:** "From Distributional to Semantic Similarity" (Sahlgren, 2005)

#### Concepto
Variante de LSA más eficiente: en vez de SVD, asignar a cada palabra un **vector disperso aleatorio** (random sparse vector) y sumar los vectores de las palabras que co-ocurren.

#### Mecanismo
1. Asignar a cada token único un vector aleatorio de `d` dimensiones con solo `r` entradas ≠0 (ej: d=1000, r=5)
2. Para cada ventana de contexto, sumar los vectores aleatorios de las palabras
3. El vector resultante es la "representación semántica" del contexto
4. Similitud = coseno entre vectores

#### Propiedades
- **Incremental**: no necesita reconstruir matriz completa
- **Escalable**: O(1) por actualización
- **Determinista si las semillas son fijas**
- **Casi tan bueno como LSA** pero sin SVD

#### Aplicación a BioRAG
```
SOLUCIÓN RANDOM INDEXING:
  1. Generar vectores aleatorios dispersos para cada token del vocabulario
  2. Para cada nodo, sumar vectores de sus tokens (ponderados por TF-IDF)
  3. Al consolidar nodo nuevo, actualizar vectores incrementalmente
  4. Búsqueda por coseno entre vectores de contexto del query y nodos

VENTAJA: No necesita reconstruir nada, se actualiza en O(1)
```

---

### 2.5 Pointwise Mutual Information (PMI) — Church & Hanks (1990)

**Fuente:** "Word Association Norms, Mutual Information, and Lexicography"

#### Concepto
Mide qué tan **sorprendente** es que dos palabras co-ocieran, comparado con lo esperado por azar.

#### Fórmula
```
PMI(x, y) = log2[ P(x,y) / (P(x) × P(y)) ]

Donde:
- P(x,y) = probabilidad de que x e y co-ocurran en la misma ventana
- P(x) = probabilidad marginal de x
- P(y) = probabilidad marginal de y
```

#### Propiedades
- **PMI > 0**: co-ocurrencia más frecuente que por azar (asociación positiva)
- **PMI = 0**: independencia
- **PMI < 0**: co-ocurrencia menos frecuente que por azar (disociación)
- **Captura relaciones fuertes**: "café" + "taza" = PMI alto, "café" + "paraguas" = PMI bajo

#### Aplicación a BioRAG
```
SOLUCIÓN PMI:
  1. Calcular frecuencias de co-ocurrencia en ventanas de nodos
  2. PMI entre tokens = fuerza de asociación semántica
  3. Usar PMI como peso de sinapsis en vez de solo conteo de tokens compartidos
  4. PMI corrige el sesgo de frecuencia alta (las palabras comunes aparecen mucho)

EJEMPLO: 
  "BioRAG" + "memoria" = PMI alto (asociación real)
  "BioRAG" + "el" = PMI bajo (co-ocurrencia por azar)
```

---

### 2.6 Non-Parametric PMI (NPMI) — Bouma (2009)

#### Fórmula
```
NPMI(x, y) = PMI(x, y) / (-log2[P(x,y)])

Rango: -1 a +1
- NPMI = +1: co-ocurrencia perfecta
- NPMI = 0: independencia
- NPMI = -1: nunca co-ocurren
```

#### Ventaja sobre PMI
Normalizado, más estable para palabras con frecuencias muy diferentes.

---

## 3. MECANISMOS BIOLÓGICOS REALES

### 3.1 Teoría del Índice Hipocampal (Hippocampal Indexing Theory)

**Fuente:** Teyler & DiScenna (1986), "The hippocampal memory indexing theory"

#### Concepto
El hipocampo **no almacena recuerdos** — almacena **índices** (punteros) hacia las neocortex donde están distribuidos los componentes del recuerdo.

#### Aplicación a BioRAG
```
ANALOGÍA ACTUAL:
  - Sinapsis = índices hipocampales
  - Contenido en largo_plazo = neocortex
  - El grafo de sinapsis = mapa de índices

MEJORA PROPUESTA:
  1. Cada nodo tiene un "índice hipocampal" (vector disperso)
  2. El índice NO es el contenido — es una firma compacta
  3. Para recuperar, buscar por índice (Hamming), no por contenido completo
  4. Los índices se actualizan cuando se reconsolida el nodo
```

### 3.2 Engramas de Memoria (Memory Engrams)

**Fuente:** Tonegawa Lab (MIT), "Engram cells retaining memory under retrograde amnesia" (2012)

#### Concepto
Los **engramas** son poblaciones específicas de neuronas que se activan durante un recuerdo y se reactivan durante la recuperación. No es una neurona — es un **patrón de actividad** distribuido.

#### Aplicación a BioRAG
```
ANALOGÍA:
  - Cada nodo es un "engrama potencial"
  - La sinapsis es la "potenciación" del engrama
  - La inhibición lateral es la "extinción" del engrama
  - La recuperación es la "reactivación" del patrón

MEJORA:
  1. Cada nodo tiene un "engrama score" = Σ(pesos_sinápticos × actividad_reciente)
  2. El score se actualiza cuando se usa el nodo (LTP)
  3. El score decae si no se usa (LTD)
  4. Los nodos con engrama score > umbral son "activos"
  5. Los nodos con engrama score bajo se duermen
```

### 3.3 Acoplamiento Theta-Gamma (Theta-Gamma Coupling)

**Fuente:** Lisman & Jensen (2013), "The theta-gamma neural code"

#### Concepto
El cerebro usa **ondas theta (4-8 Hz)** para organizar secuencias y **ondas gamma (30-100 Hz)** para items individuales dentro de cada ciclo theta. Cada ciclo theta contiene ~5-10 items gamma.

#### Aplicación a BioRAG
```
ANALOGÍA EN BÚSQUEDA:
  - Theta = "ventana de contexto" (ej: últimos 10 nodos accedidos)
  - Gamma = "items candidatos" dentro de la ventana
  - Un ciclo theta = una ronda de búsqueda

MEJORA:
  1. Mantener buffer circular de "actividad reciente" (últimos 10 nodos)
  2. Para cada candidato, verificar si "co-ocurre" con algún nodo del buffer
  3. Score = Σ(co-ocurrencias_con_buffer) × peso_sináptico
  4. Esto simula "atención" selectiva basada en contexto inmediato
```

### 3.4 Sparse Coding (Codificación Dispersa)

**Fuente:** Olshausen & Field (1996), "Emergence of simple-cell receptive field properties"

#### Concepto
El cerebro usa **pocas neuronas activas** para representar cada estímulo. De 1000 neuronas, solo ~50-100 se activan (5-10%).

#### Aplicación a BioRAG
```
MEJORA:
  1. Cada nodo tiene un "perfil de activación" (vector binario disperso)
  2. Solo ~5% de nodos se activan por query
  3. La activación se propaga por sinapsis (spreading activation)
  4. El resultado es una "combinación dispersa" de nodos relevantes
  5. Esto es más eficiente que buscar en TODOS los nodos
```

### 3.5 Memoria de Trabajo (Working Memory) — Baddeley & Hitch (1974)

#### Componentes
- **Bucle fonológico**: información auditiva temporal
- **Agenda visoespacial**: información visual/espacial
- **Buffer episódico**: integración multimodal
- **Ejecutivo central**: control de atención

#### Aplicación a BioRAG
```
MEJORA:
  1. corto_plazo = buffer episódico (última sesión)
  2. "Agenda de contexto" = últimos 5 nodos accedidos
  3. "Bucle fonológico" = query actual + paráfrasis
  4. El ejecutivo central = el agente que decide qué buscar
```

---

## 4. ANÁLISIS CRÍTICO DE LAS SINAPSIS LATENTES ACTUALES

### 4.1 Cómo funciona actualmente

```python
# inferencia_transitiva.py
# CTE recursiva que encuentra caminos de 2-3 saltos
# Peso latente = producto(pesos_camino) × FACTOR_DECAY^saltos
# FACTOR_DECAY = 0.7, MAX_SALTOS = 2
```

### 4.2 Problemas identificados

| Problema | Descripción | Impacto |
|---|---|---|
| **Ruido por propagación** | Cada salto multiplica por 0.7, pero 3 saltos = 0.343 × pesos_origen | Muchos nodos débiles irrelevantes |
| **Sin validación semántica** | Si A→B→C, se crea A→C aunque A y C no tengan relación semántica real | Falsos positivos |
| **Sesgo por topología** | Nodos con muchas conexiones tienen más latentes (hubs) | Over-representation de hubs |
| **Recálculo completo** | Se borran TODAS las latentes y se recalculan cada ciclo | Costoso, pierde continuidad |
| **Sin ponderación por relevancia** | Todas las latentes se tratan igual en scoring | No distingue fuertes de débiles |

### 4.3 Propuesta de mejora: Sinapsis Latentes Semánticas (SLS)

```
NUEVO MECANISMO: Sinapsis Latentes Semánticas (SLS)

1. SOLO crear latentes si los nodos comparten:
   a) Al menos 1 dimensión semántica en común (emoción, intención, dominio)
   b) PMI > umbral entre sus tokens principales
   c) No están en la misma categoría (evitar redundancia)

2. Ponderar por:
   - PRODUCTO de pesos camino (ya existe)
   - × FACTOR_DECAY^saltos (ya existe)
   - × PMI_entre_tokens (NUEVO)
   - × compartidos_dimensión_semántica / total_dimensiones (NUEVO)

3. Mantener latentes incrementalmente (no borrar y recalcular)

4. Podar latentes con peso < 0.1 mensualmente
```

---

## 5. PROPUESTA DE ARQUITECTURA: "CEREBRO NIVEL DIOS"

### 5.1 Componentes del sistema

```
┌─────────────────────────────────────────────────────────┐
│                    CEREBRO NIVEL DIOS                     │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  ┌──────────────┐    ┌──────────────┐    ┌────────────┐  │
│  │  CAPA 1:     │    │  CAPA 2:     │    │  CAPA 3:   │  │
│  │  Sparse       │    │  Sinapsis    │    │  Memoria   │  │
│  │  Distributed  │───▶│  Semánticas  │───▶│  de Trabajo│  │
│  │  Memory       │    │  (SLS)       │    │  (Buffer)  │  │
│  └──────────────┘    └──────────────┘    └────────────┘  │
│         │                   │                   │          │
│         ▼                   ▼                   ▼          │
│  ┌─────────────────────────────────────────────────────┐  │
│  │         PIPELINE DE RECUPERACIÓN (7 capas)          │  │
│  │  1. FTS5 AND → 2. FTS5 OR → 3. Hamming (SDM)       │  │
│  │  4. PMI semántico → 5. Spreading activation         │  │
│  │  6. Context window → 7. Scoring compuesto           │  │
│  └─────────────────────────────────────────────────────┘  │
│         │                                                  │
│         ▼                                                  │
│  ┌─────────────────────────────────────────────────────┐  │
│  │         SCORING COMPUESTO (8 señales)               │  │
│  │  BM25 + Dimensión + PMI + Sinapsis + Peso           │  │
│  │  + Latente + Temporal + Asociaciones                 │  │
│  └─────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### 5.2 Sparse Distributed Memory para BioRAG

#### Codificación de nodos
```python
def codificar_nodo_sdm(nodo, vocabulario, d=1000):
    """
    Codifica un nodo como vector binario disperso de d dimensiones.
    
    Componentes del código:
    1. Hash de tokens del contenido (40% de bits)
    2. Hash de tokens de concepto (20% de bits)
    3. Dimensión semántica (20% de bits)
    4. Categoría (10% de bits)
    5. Co-ocurrencia con vecinos (10% de bits)
    """
    import hashlib
    import numpy as np
    
    vector = np.zeros(d, dtype=np.int8)
    
    # 1. Tokens del contenido
    tokens = tokenizar(nodo['contenido'])
    for token in tokens:
        h = int(hashlib.md5(token.encode()).hexdigest(), 16) % (d * 40 // 100)
        vector[h] = 1
        vector[(h + 1) % d] = 1  # Spread adyacente
    
    # 2. Tokens del concepto
    concepto_tokens = tokenizar(nodo['concepto'])
    for token in concepto_tokens:
        h = int(hashlib.md5(token.encode()).hexdigest(), 16) % (d * 20 // 100) + (d * 40 // 100)
        vector[h] = 1
    
    # 3. Dimensión semántica
    dims = nodo.get('dimensiones_semanticas', {})
    for dim_key, dim_vals in dims.items():
        for val in dim_vals:
            h = int(hashlib.md5(f"{dim_key}:{val}".encode()).hexdigest(), 16) % (d * 20 // 100) + (d * 60 // 100)
            vector[h] = 1
    
    # 4. Categoría
    cat = nodo.get('categoria', 'General')
    h = int(hashlib.md5(cat.encode()).hexdigest(), 16) % (d * 10 // 100) + (d * 80 // 100)
    vector[h] = 1
    
    # 5. Co-ocurrencia con vecinos
    for vecino in nodo.get('asociaciones', [])[:10]:
        h = int(hashlib.md5(vecino.encode()).hexdigest(), 16) % (d * 10 // 100) + (d * 90 // 100)
        vector[h] = 1
    
    return vector
```

#### Búsqueda por Hamming
```python
def buscar_sdm(query_vector, nodos_sdm, radio=150):
    """
    Busca nodos dentro del radio Hamming del query.
    Retorna: [(nodo_id, distancia_hamming, similitud)]
    """
    import numpy as np
    
    resultados = []
    for nodo_id, nodo_vector in nodos_sdm.items():
        distancia = np.sum(query_vector != nodo_vector)  # Hamming distance
        if distancia <= radio:
            similitud = 1.0 - (distancia / len(query_vector))
            resultados.append((nodo_id, distancia, similitud))
    
    resultados.sort(key=lambda x: x[1])  # Ordenar por distancia
    return resultados
```

### 5.3 PMI para Sinapsis Semánticas

```python
def calcular_pmi_matrix(nodos, ventana=10):
    """
    Construye matriz PMI entre tokens basada en co-ocurrencia en nodos.
    Retorna: dict de (token_a, token_b) → PMI_score
    """
    from collections import Counter
    import math
    
    # Contar co-ocurrencias
    co_ocurrencias = Counter()
    frecuencias = Counter()
    total_nodos = len(nodos)
    
    for nodo in nodos:
        tokens = set(tokenizar(nodo['contenido']))
        for token in tokens:
            frecuencias[token] += 1
        
        # Ventana: pares dentro del mismo nodo
        token_list = list(tokens)
        for i in range(len(token_list)):
            for j in range(i+1, min(i+ventana, len(token_list))):
                par = tuple(sorted([token_list[i], token_list[j]]))
                co_ocurrencias[par] += 1
    
    # Calcular PMI
    pmi_matrix = {}
    for (t1, t2), count in co_ocurrencias.items():
        p_xy = count / total_nodos
        p_x = frecuencias[t1] / total_nodos
        p_y = frecuencias[t2] / total_nodos
        
        if p_x > 0 and p_y > 0 and p_xy > 0:
            pmi = math.log2(p_xy / (p_x * p_y))
            npmi = pmi / (-math.log2(p_xy)) if p_xy < 1 else 0
            pmi_matrix[(t1, t2)] = npmi
    
    return pmi_matrix
```

### 5.4 Scoring Compuesto Mejorado

```python
def score_compuesto_mejorado(nodo, query, pmi_matrix, sdm_distancia, contexto_buffer):
    """
    Scoring con 8 señales ortogonales:
    1. BM25 (texto)
    2. Dimensión semántica
    3. PMI semántico
    4. Sinapsis directas
    5. Peso sináptico
    6. Latente semántica (SLS)
    7. Temporal (recency)
    8. Contexto de buffer (atención)
    """
    scores = {}
    
    # 1. BM25
    scores['bm25'] = calcular_bm25(query, nodo)
    
    # 2. Dimensión semántica
    scores['dimension'] = calcular_similitud_dimension(query, nodo)
    
    # 3. PMI semántico
    scores['pmi'] = calcular_pmi_nodo(query, nodo, pmi_matrix)
    
    # 4. Sinapsis directas
    scores['sinapsis'] = calcular_score_sinapsis(query, nodo)
    
    # 5. Peso sináptico
    scores['peso'] = nodo['peso_sinaptico']
    
    # 6. Latente semántica
    scores['latente'] = calcular_latente_semantica(query, nodo)
    
    # 7. Temporal
    scores['temporal'] = calcular_score_temporal(nodo['ultimo_acceso'])
    
    # 8. Contexto de buffer (NUEVO)
    scores['contexto'] = calcular_score_contexto(nodo, contexto_buffer)
    
    # Combinación ponderada
    pesos = {
        'bm25': 0.30,
        'dimension': 0.10,
        'pmi': 0.15,
        'sinapsis': 0.15,
        'peso': 0.10,
        'latente': 0.10,
        'temporal': 0.05,
        'contexto': 0.05
    }
    
    return sum(scores[k] * pesos[k] for k in pesos)
```

---

## 6. IMPLEMENTACIÓN PASO A PASO (PLAN DE ACCIÓN)

### Fase 1: PMI Semántico (1-2 días)
**Archivo:** `core/pmi_semantico.py` (nuevo)

1. Implementar `calcular_pmi_matrix()` sobre nodos de largo_plazo
2. Integrar PMI en scoring existente (reemplazar PMI por Jaccard puro)
3. Tests: verificar que PMI > Jaccard para sinónimos, PMI < Jaccard para palabras comunes
4. Métrica: medir mejora en Recall@5 con baseline existente

### Fase 2: Sinapsis Latentes Semánticas (2-3 días)
**Archivo:** `core/inferencia_transitiva.py` (modificar)

1. Agregar validación semántica: solo crear latentes si comparten dimensión O PMI > umbral
2. Ponderar latentes por PMI entre tokens
3. Mantener latentes incrementalmente (no borrar y recalcular)
4. Tests: reducir falsos positivos de latentes en 50%+
5. Métrica: reducir nodos con peso < 0.01 en scoring

### Fase 3: Sparse Distributed Memory (3-5 días)
**Archivo:** `core/sdm.py` (nuevo)

1. Implementar codificación SDM para nodos
2. Implementar búsqueda por Hamming distance
3. Integrar SDM como capa adicional en pipeline de búsqueda
4. Tests: SDM vs Jaccard para diferentes tipos de query
5. Métrica: Recall@5 con SDM vs sin SDM

### Fase 4: Context Window / Atención (1-2 días)
**Archivo:** `core/memory_store.py` (modificar)

1. Agregar buffer circular de "actividad reciente" (últimos 10 nodos)
2. Calcular score de contexto para candidatos
3. Integrar en scoring compuesto
4. Tests: verificar que contexto temporal mejora resultados

### Fase 5: Validación y Benchmark (2-3 días)

1. Ejecutar suite QA existente (baseline 87% Recall@1)
2. Medir Recall@1, Recall@5, MRR post-cambios
3. Documentar mejoras en README
4. Actualizar versión a v19.0

---

## 7. RIESGOS Y MITIGACIONES

| Riesgo | Mitigación |
|---|---|
| PMI requiere recálculo periódico | Calcular una vez, cachear, recalcular solo con >10% nodos nuevos |
| SDM requiere más RAM (~1KB × nodos) | Con 10K nodos = ~10MB, aceptable |
| Sinapsis latentes siguen siendo ruidosas | Validación semántica + PMI como filtro |
| Scoring compuesto más lento | Pre-computar PMI y SDM, caching en memoria |
| Complejidad de mantenimiento | Documentar cada componente, tests unitarios |

---

## 8. REFERENCIAS CIENTÍFICAS

1. **Kanerva, P.** (1988). "Sparse Distributed Memory". MIT Press.
2. **Deerwester, S. et al.** (1990). "Indexing by Latent Semantic Analysis". JASIS.
3. **Lund, K. & Burgess, C.** (1996). "Producing high-dimensional semantic spaces from lexical co-occurrence". Behavior Research Methods.
4. **Sahlgren, M.** (2005). "An Introduction to Random Indexing". TALRE.
5. **Church, K. & Hanks, P.** (1990). "Word Association Norms, Mutual Information, and Lexicography". Computational Linguistics.
6. **Bouma, G.** (2009). "Normalized (pointwise) mutual information in collocation extraction". GSCL.
7. **Teyler, T. & DiScenna, P.** (1986). "The hippocampal memory indexing theory". Behavioral Neuroscience.
8. **Tonegawa, S.** (2012). "Engram cells retaining memory under retrograde amnesia". Science.
9. **Lisman, J. & Jensen, O.** (2013). "The theta-gamma neural code". Neuron.
10. **Olshausen, B. & Field, D.** (1996). "Emergence of simple-cell receptive field properties". Nature.
11. **Baddeley, A. & Hitch, G.** (1974). "Working Memory". Psychology of Learning and Motivation.

---

## 9. CONCLUSIÓN

**El camino no es usar embeddings.** El camino es construir un cerebro funcional con:

1. **Sparse Distributed Memory** → similitud por Hamming, no por coseno de embeddings
2. **PMI semántico** → asociaciones que capturan significado real, no solo co-ocurrencia
3. **Sinapsis latentes semánticas** → conexiones indirectas validadas, no por propagación ciega
4. **Context window** → memoria de trabajo que da "atención" al sistema
5. **Scoring compuesto** → 8 señales ortogonales, no 1

**Todo esto es pura matemática.** Sin modelos embebidos, sin dependencias externas, corriendo en SQLite + Python puro.

**La visión de Dennys es correcta:** el cerebro es un sistema análogo, mecánico, matemático. Lo que tenemos que construir es un sistema análogo que funcione igual — no un cerebro digital que copia al biológico, sino uno que **opera por los mismos principios** usando herramientas matemáticas que la ciencia ya descubrió.

---

*Documento generado por Athena-OEC como parte de la investigación para elevar BioRAG a nivel Dios.*
*Basado en: código fuente de BioRAG, literatura científica, y la visión de Dennys.*
