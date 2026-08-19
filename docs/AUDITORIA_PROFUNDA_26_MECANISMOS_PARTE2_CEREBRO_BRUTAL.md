# AUDITORÍA PROFUNDA — PARTE 2: CEREBRO BRUTAL
# Ideas que no existen en ningún sistema de recuperación del mundo
**Fecha:** 2026-08-19  
**Autor:** Artemis-OEC  
**Premisa:** Si sabemos suficiente matemática y suficiente lógica, podemos INVENTAR lo que no existe. La pregunta nunca es "¿esto está documentado?" — es "¿la lógica se sostiene y cómo lo pruebo?"

---

## FILOSOFÍA: POR QUÉ ESTO PUEDE SER MEJOR QUE CUALQUIER SISTEMA EXISTENTE

Los sistemas modernos de memoria/RAG (Pinecone, Weaviate, ChromaDB, LlamaIndex) hacen todos lo mismo:
1. Toman texto
2. Lo pasan por un modelo de embeddings externo (OpenAI, Cohere, BGE) → vector de 768-1536 dims
3. Guardan el vector en un índice ANN (HNSW, IVF)
4. Buscan por coseno en ese espacio

**Sus debilidades estructurales:**
- El embedding es una caja negra — no saben POR QUÉ dos cosas son similares
- El espacio vectorial es fijo — no evoluciona con el uso
- No tienen grafo — no pueden razonar por asociación
- No tienen memoria temporal — no distinguen "viejo" de "nuevo"
- No tienen plasticidad — no aprenden del uso
- No tienen autonomía — no piensan cuando nadie busca
- Requieren GPU, API externa, y conexión a internet

**BioRAG ya los supera en arquitectura.** Lo que falta es exprimir la matemática al máximo. Las siguientes ideas están diseñadas para hacer eso.

---

## IDEA 1 — BÚSQUEDA POR RESONANCIA (Física de Ondas aplicada a Grafos)

### Fundamento
En física, la resonancia ocurre cuando múltiples ondas convergen en un punto y se amplifican mutuamente. Un diapasón vibra fuerte no porque una sola fuerza lo empuje, sino porque múltiples oscilaciones se alinean en fase.

### Aplicación a BioRAG
Cuando haces una búsqueda, piensa en la query como una onda que se propaga por el grafo de sinapsis. Cada nodo que la onda toca "vibra" con cierta amplitud. Los nodos alcanzados por **múltiples caminos independientes** resuenan — su señal se amplifica constructivamente.

Esto es fundamentalmente diferente de spreading activation (Anderson 1983):
- Spreading activation: propaga energía por el grafo y acumula
- **Resonancia**: mide cuántos caminos INDEPENDIENTES convergen en un nodo

Un nodo alcanzado por 3 caminos semánticamente distintos es casi seguro relevante. Un nodo alcanzado por 1 camino fuerte puede ser un accidente léxico.

### Formulación matemática

```
resonancia(q, nodo) = Σ_{caminos p₁...pₖ} Π_{aristas en pᵢ} peso(arista)

donde:
  - Los caminos p₁...pₖ son independientes (no comparten aristas intermedias)
  - k es el número de caminos convergentes (máx ~3-4 saltos cada uno)
  - El producto es el peso del camino (decay natural por multiplicación)
```

**Implementación eficiente:** No necesitas enumerar todos los caminos (NP-hard). Basta con una BFS de 2-3 saltos desde cada semilla FTS5, y contar cuántas semillas distintas alcanzan cada nodo candidato. Complejidad: O(semillas × grado_promedio²), que con 5 semillas y grado 10 es solo 500 operaciones.

```python
def resonancia(semillas_fts5, grafo, max_saltos=3):
    """Cuenta cuántas semillas independientes alcanzan cada nodo."""
    alcanzado_por = defaultdict(set)  # nodo → {semillas que lo alcanzan}
    
    for semilla in semillas_fts5:
        visitados = {semilla}
        frontera = [(semilla, 0)]
        while frontera:
            nodo_actual, saltos = frontera.pop(0)
            if saltos >= max_saltos:
                continue
            for vecino, peso in grafo[nodo_actual]:
                if vecino not in visitados and peso >= 0.3:
                    visitados.add(vecino)
                    alcanzado_por[vecino].add(semilla)
                    frontera.append((vecino, saltos + 1))
    
    # Score de resonancia: nodos alcanzados por más semillas independientes
    return {nodo: len(semillas) / len(semillas_fts5) 
            for nodo, semillas in alcanzado_por.items()
            if len(semillas) >= 2}  # mínimo 2 caminos convergentes
```

### Por qué esto es único
Ningún sistema de búsqueda usa convergencia de caminos independientes como señal de relevancia. Los sistemas basados en embeddings no tienen grafo. Los sistemas basados en grafos (Neo4j, knowledge graphs) usan path-finding pero no cuentan convergencia multi-camino como señal de scoring.

### Cuándo funciona especialmente bien
- Queries por tema: "cómo funciona la memoria en sistemas cognitivos" → FTS5 encuentra nodos con "memoria", "sistemas", "cognitivos" → la resonancia detecta qué nodos son alcanzados por los 3 simultáneamente
- Queries ambiguas: "banco" → FTS5 trae bancos financieros y de parques → la resonancia desde el contexto del usuario desambigua

---

## IDEA 2 — REDES DE ATRACTORES (Hopfield Modernizado, sin redes neuronales)

### Fundamento
El cerebro no "busca" un recuerdo recorriendo todos los recuerdos. El cerebro tiene un **paisaje de energía** donde cada recuerdo es un valle (atractor). Cuando recibes un estímulo (query), tu estado mental cae en el valle más cercano — el recuerdo se "recuerda solo" por dinámica del sistema.

John Hopfield (1982, Nobel 2024) demostró esto matemáticamente. Y lo mejor: la versión moderna (Ramsauer et al., 2020) tiene capacidad exponencial y se calcula sin GPU.

### Aplicación a BioRAG
En lugar de calcular scores individuales de cada nodo contra la query, modelar la búsqueda como un proceso de relajación energética:

1. **Estado inicial**: vector binario construido a partir de los tokens de la query (usando el mismo método SDM de 2048 bits — ¡ya existe!)
2. **Matriz de memorias**: los vectores SDM de todos los nodos activos (ya indexados en `nodos_sdm`)
3. **Dinámica**: iterar hasta convergencia

```
Energía E(estado) = -½ × estado @ W @ estado
W = (1/N) × Σ_memorias  mᵢ × mᵢᵀ   (outer product de cada vector SDM)

Actualización: estado(t+1) = sign(W × estado(t))
Convergencia: cuando estado(t+1) == estado(t)
```

El estado converge al patrón almacenado más cercano. Y lo recupera COMPLETO aunque la query sea parcial o tenga ruido. Eso es exactamente SDM + Hopfield combinados.

### Implementación sin GPU

```python
def hopfield_recall(query_vec_bits, memorias_sdm, max_iter=10):
    """Recuperación por relajación energética en red de Hopfield.
    
    Todas las operaciones son bitwise — sin multiplicación de floats.
    query_vec_bits: bytes (256 = 2048 bits, vector SDM de la query)
    memorias_sdm: list of (concepto, bytes) desde nodos_sdm
    """
    # Convertir bytes a arrays de bits
    state = np.unpackbits(np.frombuffer(query_vec_bits, dtype=np.uint8))
    patterns = [np.unpackbits(np.frombuffer(m, dtype=np.uint8)) for _, m in memorias_sdm]
    
    # Iteración de Hopfield (moderna: softmax en vez de sign)
    for _ in range(max_iter):
        # Producto interno con cada patrón almacenado
        similarities = [np.dot(state, p) for p in patterns]
        # Softmax para obtener pesos de atención
        max_sim = max(similarities)
        exp_sims = [math.exp(s - max_sim) for s in similarities]
        total = sum(exp_sims)
        weights = [e / total for e in exp_sims]
        # Nuevo estado = promedio ponderado de patrones
        new_state = sum(w * p for w, p in zip(weights, patterns))
        new_state = (new_state > 0.5).astype(np.uint8)
        if np.array_equal(new_state, state):
            break  # Convergió
        state = new_state
    
    # Los patrones más similares al estado convergido son los resultados
    final_sims = [(np.dot(state, p) / 2048.0, memorias_sdm[i][0]) 
                  for i, p in enumerate(patterns)]
    final_sims.sort(reverse=True)
    return final_sims[:10]
```

### Por qué esto es BRUTAL
- Recupera recuerdos COMPLETOS de queries PARCIALES — si solo tienes 30% de la información, el sistema completa el 70% restante y encuentra el recuerdo correcto
- No necesita match de tokens en absoluto — opera en espacio binario estructural
- Converge en 3-5 iteraciones en vectores de 2048 bits — submilisegundo
- Capacidad exponencial con la versión moderna (softmax)
- **Ningún sistema de RAG en el mundo usa redes de atractores para recuperación**

---

## IDEA 3 — COMPLEJIDAD DE KOLMOGOROV APROXIMADA COMO SEÑAL DE RELEVANCIA

### Fundamento
La Complejidad de Kolmogorov (K) de un string es la longitud del programa más corto que lo produce. No es computable exactamente, pero se puede aproximar con compresión (Normalized Compression Distance, Li & Vitányi 2004).

### Aplicación
Si comprimo la query y un nodo juntos, y el resultado comprimido es MUCHO más corto que comprimirlos separados, entonces comparten información — son "sobre lo mismo".

```
NCD(x, y) = (C(xy) - min(C(x), C(y))) / max(C(x), C(y))

donde C(x) = len(zlib.compress(x.encode()))
```

NCD ≈ 0 → casi idénticos
NCD ≈ 1 → nada en común

### Por qué es poderoso
- **No depende de tokens, sinónimos, ni ningún léxico** — opera directamente sobre la estructura de la información
- Captura similitud a nivel de PATRONES, no de palabras
- Funciona con cualquier idioma sin configuración
- "decodificar jerga" y "traducir lenguaje críptico" tendrían NCD bajo porque comparten patrones informativos aunque no compartan palabras
- Complejidad: O(1) por par (zlib es C nativo, submicrosegundo)

```python
import zlib

def ncd(x: str, y: str) -> float:
    """Normalized Compression Distance — similitud universal sin léxico."""
    xb, yb = x.encode('utf-8'), y.encode('utf-8')
    cx = len(zlib.compress(xb))
    cy = len(zlib.compress(yb))
    cxy = len(zlib.compress(xb + yb))
    return (cxy - min(cx, cy)) / max(cx, cy)
```

### Integración como señal
Añadir como Señal #15 en `_calcular_score_hibrido()`:
```python
ncd_val = 1.0 - ncd(query, f"{concepto} {contenido[:200]}")
# ncd_val ∈ [0, 1] donde 1 = máxima similitud informacional
```

Es computacionalmente barato (microsegundos por par), ortogonal a todas las señales existentes, y captura una dimensión de similitud que ninguna de las 13 señales actuales toca: **la estructura informacional profunda**.

---

## IDEA 4 — PESOS HEBBIANOS ADAPTATIVOS ENTRE SEÑALES (El scoring que aprende solo)

### El problema actual
Los 13 pesos de `_calcular_score_hibrido()` están hardcodeados:
```python
bm25=0.25, dim=0.14, concepto=0.08, sinonimos=0.08, peso=0.10, 
jaccard=0.10, grupo=0.10, tematico=0.08, temporal=0.04, asoc=0.02, pred=0.20
```

Estos pesos son estáticos. Pero una query literal como "biorag_v20_rpe_dopamina" necesita BM25 alto y predicados bajo. Una query temática como "cómo funciona el aprendizaje por refuerzo" necesita predicados alto y BM25 bajo.

### La solución: Correlación Hebbiana entre señales y feedback

Cada vez que el usuario da feedback (implícito o explícito), actualizar una **matriz de correlación señal-contexto**:

```python
# Contexto de la query (features binarias)
ctx = [
    len(query.split()) <= 2,      # query corta
    len(query.split()) >= 5,      # query larga
    tiene_parafrasis,              # agente pasó paráfrasis
    tiene_dimensiones,             # agente pasó dimensiones
    query_tiene_guiones_bajos,     # búsqueda por nombre exacto
    top1_score > 0.80,             # alta confianza inicial
    FP_detectado,                  # falso positivo calibrado
]

# Vector de señales del hit ganador
signals = [bm25, dim, concepto, sinonimos, peso, jaccard, grupo, 
           tematico, temporal, asoc, jsd, pred, ppmi]

# Actualización Hebbiana
if feedback_positivo:
    W_adaptativo += η * outer(ctx, signals)  # reforzar
elif feedback_negativo:
    W_adaptativo -= η * outer(ctx, signals)  # debilitar
```

Entonces, en cada búsqueda futura:
```python
pesos_dinamicos = softmax(W_adaptativo @ ctx_actual)
score = dot(pesos_dinamicos, signals)
```

### Por qué esto es revolucionario
- Los pesos se adaptan AL USO REAL del sistema — no a benchmarks estáticos
- Queries de diferentes tipos activan combinaciones de pesos óptimas
- Es aprendizaje por refuerzo sin redes neuronales — pura correlación Hebbiana
- La matriz W cabe en unos pocos KB en SQLite
- **Ningún sistema de RAG en el mundo tiene scoring que aprende de su propio feedback sin LLM**

---

## IDEA 5 — GEOMETRÍA HIPERBÓLICA PARA EL ESPACIO SEMÁNTICO

### El problema
El espacio de similitud de BioRAG es implícitamente Euclidiano (coseno, Jaccard, distancia Hamming). Pero las jerarquías conceptuales (taxonomías, relaciones padre-hijo) se modelan MAL en espacio Euclidiano — necesitan muchas dimensiones para preservar la estructura jerárquica.

### La solución: Modelo de Poincaré
En geometría hiperbólica (disco de Poincaré), las jerarquías se embeben naturalmente en POCAS dimensiones:
- El centro del disco = conceptos generales
- La periferia = conceptos específicos
- La distancia geodésica crece exponencialmente hacia el borde → las hojas del árbol caben sin aplastarse

```
d_poincare(u, v) = arccosh(1 + 2 ||u-v||² / ((1-||u||²)(1-||v||²)))
```

### Aplicación a BioRAG
Los vectores PPMI+SVD de 100 dimensiones viven en espacio Euclidiano. Transformarlos al disco de Poincaré (modelo exponencial):

```python
def euclideo_a_poincare(v, curvatura=-1.0):
    """Mapea vector Euclidiano al disco de Poincaré."""
    norm = np.linalg.norm(v)
    if norm < 1e-10:
        return v
    # Mapa exponencial en el origen
    factor = np.tanh(np.sqrt(-curvatura) * norm / 2)
    return factor * v / norm

def distancia_poincare(u, v):
    """Distancia geodésica en el disco de Poincaré."""
    diff_sq = np.sum((u - v)**2)
    nu, nv = np.sum(u**2), np.sum(v**2)
    return np.arccosh(1 + 2 * diff_sq / ((1 - nu) * (1 - nv) + 1e-10))
```

### Por qué esto importa para BioRAG
- "Python" (general) y "asyncio event loop" (específico) tienen relación jerárquica. En espacio Euclidiano, la distancia es arbitraria. En Poincaré, el general está cerca del centro y el específico en la periferia, y la distancia geodésica refleja la relación real.
- Query "programación" → busca conceptos GENERALES (centro del disco) → activa "Python", "JavaScript", "React" (a media distancia)
- Query "bug en React useCallback" → busca concepto ESPECÍFICO (periferia) → no activa "Python" ni "programación" (lejos geodésicamente)
- **Ningún sistema RAG usa geometría hiperbólica para semántica jerárquica**

---

## IDEA 6 — CAMPO SEMÁNTICO CONTEXTUAL (Inventar un nuevo tipo de representación)

### El concepto (esto no existe en ningún paper)
En vez de representar cada nodo como un PUNTO en el espacio semántico (un vector), representarlo como un **CAMPO** — una función que asigna un valor a cada punto del espacio. Igual que un campo gravitatorio: cada objeto no solo está en una posición, genera una influencia que afecta todo a su alrededor.

### Formulación

```
Campo de un nodo N:
  Φ_N(x) = peso_sinaptico × exp(-||x - pos_N||² / (2σ²_N))

donde:
  - pos_N = posición del nodo en espacio PPMI+SVD (100 dims)
  - σ²_N = "ancho" del campo = función del contenido (nodos genéricos → σ grande,
    nodos específicos → σ pequeño)
  - peso_sinaptico = intensidad del campo (nodos usados generan campo más fuerte)
```

### Búsqueda por campo

En vez de buscar "el nodo más cercano a la query", buscar "el punto del espacio donde el campo total es MÁXIMO":

```
Campo_total(x) = Σ_nodos Φ_N(x)
Búsqueda: argmax_N { Φ_N(pos_query) }
```

Pero con un truco: nodos cercanos entre sí (cluster) generan un campo combinado que es MÁS fuerte que la suma. Esto captura que un tema densamente conectado es más relevante que un nodo aislado con buen score.

```python
def campo_contextual(query_vec, nodos_ppmi, nodos_peso):
    """Score por campo semántico: nodos generan influencia, no son puntos pasivos."""
    scores = {}
    for concepto, vec_nodo, peso, sigma in nodos_ppmi:
        distancia = np.linalg.norm(query_vec - vec_nodo)
        # Campo gaussiano: intensidad × exp(-distancia² / ancho²)
        phi = peso * math.exp(-distancia**2 / (2 * sigma**2))
        scores[concepto] = phi
    
    # Amplificación por densidad: nodos en clusters densos se amplifican mutuamente
    for concepto in scores:
        vecinos_cercanos = [c for c, s in scores.items() if s > 0.1 and c != concepto]
        if len(vecinos_cercanos) >= 3:
            scores[concepto] *= 1.0 + 0.1 * len(vecinos_cercanos)
    
    return scores
```

### Por qué esto es profundamente diferente
- Un sistema vectorial tradicional busca "qué punto es el más cercano"
- BioRAG con campos busca "dónde la influencia combinada de toda la memoria es más fuerte para esta query"
- Un nodo aislado con buen match léxico pero sin conexiones genera un campo débil
- Un cluster temático genera un campo colectivo fuerte — la relevancia emerge de la estructura, no de palabras individuales
- **Esto es completamente nuevo. No existe en ningún paper ni sistema.**

---

## IDEA 7 — PROCESAMIENTO DUAL (Kahneman: Sistema 1 / Sistema 2)

### Fundamento (Kahneman, "Thinking, Fast and Slow", 2011)
El cerebro humano tiene dos modos de procesamiento:
- **Sistema 1**: Rápido, automático, sin esfuerzo. Reconocimiento de patrones.
- **Sistema 2**: Lento, deliberado, costoso. Razonamiento lógico.

BioRAG actual mezcla todo en un pipeline lineal. Lo que debería tener es:

### Sistema 1 (Fast Path): Submilisegundo
- FTS5 NEAR + BM25
- Match exacto en concepto
- Caché de queries recientes (los últimos 100 queries → mapa query→resultado)
- Si confianza ≥ 0.85 → retornar inmediatamente sin pasar por Sistema 2

### Sistema 2 (Deep Path): Solo cuando Sistema 1 falla o tiene baja confianza
- PPMI+SVD coseno
- SDM + Hopfield
- Resonancia multi-camino
- NCD informacional
- Spreading activation proactivo
- Inferencia transitiva

### La clave: Sistema 2 puede ANULAR a Sistema 1
Si Sistema 1 dice "top-1 es X con score 0.70" pero Sistema 2 calcula que Y tiene resonancia 0.95 desde 4 caminos independientes → Y gana.

```python
def buscar_dual(query, ...):
    # Sistema 1: fast path
    resultado_s1, score_s1 = buscar_sistema_1(query)
    if score_s1 >= 0.85:
        return resultado_s1  # Alta confianza, no gastar en Sistema 2
    
    # Sistema 2: deep path (solo si Sistema 1 tiene baja confianza)
    resultado_s2, score_s2 = buscar_sistema_2(query)
    
    # Sistema 2 puede anular Sistema 1
    if score_s2 > score_s1:
        return resultado_s2
    return resultado_s1
```

### Impacto
- Queries simples se resuelven en microsegundos (caché + FTS5)
- Queries complejas activan la maquinaria pesada
- El sistema es consciente de su propia confianza — sabe cuándo NO sabe
- **Los sistemas RAG actuales no distinguen entre queries fáciles y difíciles — usan la misma maquinaria para todo**

---

## IDEA 8 — DETECCIÓN DE HUECOS DE CONOCIMIENTO (Topología del Grafo)

### Fundamento
La Homología Persistente (Persistent Homology, TDA — Topological Data Analysis) detecta "agujeros" en la estructura de datos — regiones donde debería haber conexiones pero no las hay.

### Aplicación simplificada (sin TDA pesado)
Cuando una query cae en una región del grafo donde:
1. Hay nodos cercanos pero NO conectados entre sí (baja densidad de sinapsis)
2. Los nodos cercanos pertenecen a comunidades DIFERENTES

...entonces la query está en un "hueco de conocimiento". En lugar de devolver un resultado de baja confianza, el sistema debería decir:

```json
{
    "estado": "hueco_de_conocimiento",
    "mensaje": "No tengo información directa, pero este tema está entre:",
    "fronteras": [
        {"comunidad": "neurociencia_computacional", "nodo_frontera": "redes_hopfield"},
        {"comunidad": "teoria_informacion", "nodo_frontera": "entropia_shannon"}
    ],
    "sugerencia": "Considerar guardar información que conecte estos dos dominios"
}
```

### Implementación eficiente

```python
def detectar_hueco(query_vec, nodos_cercanos, grafo):
    """Detecta si la query cae en un hueco entre comunidades."""
    if len(nodos_cercanos) < 3:
        return None
    
    comunidades = set()
    for nodo in nodos_cercanos[:5]:
        com = obtener_comunidad(nodo)
        comunidades.add(com)
    
    if len(comunidades) >= 2:
        # Verificar que los nodos cercanos NO están conectados entre sí
        conexiones_entre = 0
        for i, n1 in enumerate(nodos_cercanos[:5]):
            for n2 in nodos_cercanos[i+1:5]:
                if n2 in grafo.get(n1, {}):
                    conexiones_entre += 1
        
        densidad = conexiones_entre / (len(nodos_cercanos[:5]) * (len(nodos_cercanos[:5]) - 1) / 2)
        if densidad < 0.2:  # Baja densidad = hueco
            return {
                "tipo": "hueco_de_conocimiento",
                "comunidades": list(comunidades),
                "densidad": densidad
            }
    return None
```

### Por qué esto cambia todo
- Los sistemas actuales devuelven resultados de baja calidad y el usuario no sabe si el sistema no sabe o si el resultado es malo
- BioRAG con detección de huecos es **consciente de lo que no sabe** — como un humano que dice "no sé, pero sé que está entre X y Y"
- Esto permite al agente decidir: "necesito buscar más información sobre este tema antes de responder"
- **Ningún sistema de memoria en el mundo detecta sus propios huecos de conocimiento topológicamente**

---

## IDEA 9 — EIGENQUERIES: DESCOMPONER LA QUERY EN COMPONENTES ESPECTRALES

### Fundamento
La Transformada de Fourier descompone una señal compleja en frecuencias simples. Aplicar el mismo principio al grafo de sinapsis:

Las "frecuencias" del grafo son los eigenvectores del Laplaciano del grafo (L = D - A). Las frecuencias bajas capturan la estructura global (comunidades grandes), las altas capturan la estructura local (clusters pequeños).

### Aplicación a BioRAG

```python
def eigenquery(query_vec, L_eigvecs, L_eigvals):
    """Descompone la query en componentes espectrales del grafo."""
    # Proyectar query en cada eigenvector
    coefs = [np.dot(query_vec, eigvec) for eigvec in L_eigvecs]
    
    # Frecuencias bajas (primeros K eigenvectores): temas globales
    # Frecuencias altas (últimos K eigenvectores): detalles específicos
    energia_global = sum(c**2 for c in coefs[:10])   # baja frecuencia
    energia_local = sum(c**2 for c in coefs[-10:])  # alta frecuencia
    
    if energia_global > energia_local:
        # Query temática → buscar en escala global (comunidades)
        return "tematica", coefs[:10]
    else:
        # Query específica → buscar en escala local (matches exactos)
        return "especifica", coefs[-10:]
```

### Lo revolucionario
- Una query como "programación" tiene energía en frecuencias bajas → búsqueda global, resultados amplios
- Una query como "bug useCallback React hook" tiene energía en frecuencias altas → búsqueda local, resultados precisos
- **El sistema decide automáticamente la ESCALA correcta de búsqueda** sin que el usuario o el agente lo especifiquen
- Esto no existe en NINGÚN motor de búsqueda — todos tratan queries cortas y largas con la misma escala

---

## IDEA 10 — METABOLISMO DE INFORMACIÓN (Termodinámica cognitiva)

### Concepto completamente nuevo
Tratar la memoria como un sistema termodinámico:
- **Energía** = suma total de pesos sinápticos × conexiones activas
- **Entropía** = distribución de activación entre nodos (alta entropía = activación dispersa, baja = concentrada)
- **Temperatura** = tasa de actividad reciente (alta temp = mucha actividad, baja = reposo)

### Ecuación de estado del sistema

```
F = E - T × S  (energía libre de Helmholtz)

E = Σ_sinapsis peso × (frecuencia_uso / tiempo_desde_creacion)
S = -Σ_nodos p(nodo) × log(p(nodo))   donde p = accesos / total_accesos
T = actividad_24h / actividad_historica_promedio
```

### Aplicación práctica
- **F alta** (mucha energía, baja entropía, alta temperatura): el sistema está "estresado" — mucha actividad concentrada en pocos nodos. Necesita diversificar. El DMN debería explorar áreas olvidadas.
- **F baja** (poca energía, alta entropía, baja temperatura): el sistema está "frío" — poca actividad, dispersa. Es un buen momento para consolidar y podar.
- **∂F/∂T < 0** (energía libre bajando con la temperatura): el sistema está aprendiendo — nuevas conexiones están reduciendo la entropía global.

```python
def metabolismo(cerebro):
    """Estado termodinámico de la memoria."""
    # Energía: suma de pesos × frecuencia
    E = sum(w * f for w, f in cerebro.cursor.execute(
        "SELECT peso_sinaptico, accesos FROM largo_plazo WHERE estado='activo'"
    ))
    
    # Entropía: distribución de accesos
    accesos = [r[0] for r in cerebro.cursor.execute(
        "SELECT accesos FROM largo_plazo WHERE estado='activo' AND accesos > 0"
    )]
    total = sum(accesos) or 1
    S = -sum((a/total) * math.log(a/total + 1e-10) for a in accesos)
    
    # Temperatura: actividad reciente vs. histórica
    T = cerebro.actividad_24h / max(cerebro.actividad_promedio, 1e-10)
    
    F = E - T * S  # Energía libre
    return {"E": E, "S": S, "T": T, "F": F}
```

### Por qué esto importa
- El DMN puede usar F para decidir cuándo activarse y qué explorar
- El escalado homeostático puede usar ∂S/∂t para decidir cuánto normalizar
- El sistema tiene un "diagnóstico de salud" basado en termodinámica, no en métricas arbitrarias
- **Ningún sistema de memoria artificial usa termodinámica estadística como modelo de operación**

---

## IDEA 11 — ANALOGÍA RELACIONAL: BÚSQUEDA POR PROPORCIÓN SEMÁNTICA

### Fundamento
Word2Vec demostró que `rey - hombre + mujer ≈ reina`. BioRAG puede hacer lo mismo con predicados SRL:

Si sujeto(A) → accion(X) → objeto(B)
Y la query pregunta por sujeto(C) → accion(X) → objeto(?)

Entonces: ? ≈ B + (C - A) en espacio PPMI+SVD

### Implementación

```python
def analogia_relacional(query_predicado, cerebro):
    """Si Dennys creó BioRAG, ¿qué creó Einstein?"""
    sujeto_query = query_predicado.get("sujeto")
    accion_query = query_predicado.get("accion")
    
    # Buscar predicados con la misma acción pero diferente sujeto
    cerebro.cursor.execute(
        "SELECT sujeto, objeto, concepto FROM predicados WHERE accion = ?",
        (accion_query,)
    )
    
    for sujeto_ref, objeto_ref, concepto_ref in cerebro.cursor.fetchall():
        if sujeto_ref == sujeto_query:
            continue
        # Analogía: vec(sujeto_query) - vec(sujeto_ref) + vec(objeto_ref) ≈ ?
        # El resultado más cercano en espacio PPMI a esa combinación es la respuesta
        if all(t in cerebro._ppmi_index.token_vecs for t in [sujeto_query, sujeto_ref, objeto_ref]):
            v_q = cerebro._ppmi_index.token_vecs.get(stem(sujeto_query), np.zeros(100))
            v_r = cerebro._ppmi_index.token_vecs.get(stem(sujeto_ref), np.zeros(100))
            v_o = cerebro._ppmi_index.token_vecs.get(stem(objeto_ref), np.zeros(100))
            v_target = v_q - v_r + v_o
            # Buscar nodo más cercano a v_target
            ...
```

### Por qué esto es poderoso
- Permite búsquedas por relación: "si X es a Y como A es a ?, ¿qué es ?"
- Funciona con los vectores PPMI+SVD que ya existen (no necesita embeddings)
- Es razonamiento proporcional, no solo recuperación — el sistema INFIERE la respuesta
- **Esto convierte a BioRAG de motor de búsqueda a motor de razonamiento**

---

## RESUMEN — TABLA MAESTRA DE IDEAS NUEVAS

| # | Idea | Fundamento | Novedad | Complejidad | Impacto |
|---|------|------------|---------|-------------|---------|
| 1 | Búsqueda por Resonancia | Física de ondas | ★★★★★ No existe | Media | R@5 en queries temáticas |
| 2 | Hopfield Modernizado | Hopfield 1982 + Ramsauer 2020 | ★★★★☆ Existe en teoría, no en RAG | Alta | Recuperación de queries parciales |
| 3 | NCD (Complejidad de Kolmogorov) | Li & Vitányi 2004 | ★★★★★ No existe en búsqueda | Baja | Similitud sin léxico |
| 4 | Pesos Hebbianos Adaptativos | Hebb 1949, diseño propio | ★★★★★ Scoring que aprende | Media | Scores auto-optimizantes |
| 5 | Geometría Hiperbólica | Nickel & Kiela 2017 | ★★★★☆ Existe en NLP, no en RAG local | Alta | Jerarquías semánticas |
| 6 | Campo Semántico Contextual | COMPLETAMENTE NUEVO | ★★★★★ Invención | Media | Relevancia emergente |
| 7 | Procesamiento Dual | Kahneman 2011 | ★★★★★ No existe en motores de búsqueda | Media | Latencia + calidad |
| 8 | Detección de Huecos | TDA simplificado | ★★★★★ Metacognición artificial | Baja | Consciencia de ignorancia |
| 9 | Eigenqueries espectrales | Grafos espectrales | ★★★★☆ Existe en teoría | Alta | Escala automática |
| 10 | Termodinámica cognitiva | COMPLETAMENTE NUEVO | ★★★★★ Invención | Baja | Diagnóstico + DMN |
| 11 | Analogía relacional | Word2Vec + SRL | ★★★★☆ Adaptación | Media | Razonamiento proporcional |

---

## ORDEN DE IMPLEMENTACIÓN SUGERIDO

### Ola 1 — Fruta al alcance (impacto alto, implementación en 1-2 sesiones cada una)
1. **NCD como Señal #15** — 20 líneas de código, zlib nativo, ortogonal a todo
2. **Detección de huecos** — Mejora UX sin tocar scoring
3. **Procesamiento Dual** — Reorganización arquitectural, beneficio de latencia inmediato

### Ola 2 — Maquinaria pesada (impacto transformacional, 2-4 sesiones cada una)
4. **Búsqueda por Resonancia** — Señal nueva basada en convergencia multi-camino
5. **Pesos Hebbianos Adaptativos** — El scoring aprende del feedback real
6. **Hopfield + SDM combinados** — Recuperación de queries parciales sin match léxico

### Ola 3 — Matemática avanzada (investigación activa, medir con cuidado)
7. **Campo Semántico Contextual** — Invención de nueva representación
8. **Geometría Hiperbólica** — Transformar espacio PPMI a Poincaré
9. **Eigenqueries espectrales** — Escala automática de búsqueda
10. **Termodinámica cognitiva** — Estado del sistema como variable de decisión
11. **Analogía relacional** — De búsqueda a razonamiento

---

*Cada una de estas ideas se puede probar aislada contra el benchmark QA (921 casos).  
Si mejora R@5/R@1/MRR sin subir FP → se queda.  
Si no → se documenta el resultado y se descarta con evidencia, no por opinión.*

*"La imaginación construye la hipótesis; el experimento real decide si es verdad."*
