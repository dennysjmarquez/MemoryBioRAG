# Investigación: Expansión de Búsqueda en BioRAG

> Documento de investigación y arquitectura para expandir las capacidades
> de búsqueda semántica de BioRAG más allá del matching literal.
> Dennys J. Marquez + Athena-OEC. Julio 2026.

---

## 1. Problema

Las busquedas actuales de BioRAG dependen de coincidencia lexica: FTS5 trigram,
parafrasis generada por el agente, y ráfaga de terminos. Pero hay busquedas que
no se resuelven asi:

- "Esa vez que me dio la arrechera con la laptop" — la palabra "laptop" sola
  da mil resultados. Necesitas el contexto emocional.
- "decodificar jerga" vs "decodificar password" vs "decodificar colores" —
  tres contextos distintos, mismo verbo.
- "Que aprendi sobre escalabilidad" — el nodo dice "500k nodos", no
  "escalabilidad".

**El insight central:** el agente debe expandir los terminos de busqueda con
TODOS los conceptos relacionados ANTES de ir a la base de datos, no despues
como fallback.

---

## 2. Arquitectura Actual del Pipeline de Busqueda

### 2.1 buscar_por_tokens (Soft AND con stems)

Ubicacion: `core/memory_store.py:760`

```python
def buscar_por_tokens(self, tokens, modo="relaxed", profundidad="activos",
                      limite=3, pagina=1):
```

- Recibe una lista de raices (stems)
- Modo `strict`: todos los tokens deben coincidir (score=1.0)
- Modo `relaxed`: al menos 1 token coincide
- Busca en concepto y contenido de largo_plazo
- Bonus +0.1 si el token coincide en el nombre del concepto
- Retorna lista de (concepto, contenido, peso, estado, score)

**Estado:** Funcional. Ya usa stems como entrada.

### 2.2 buscar_por_frase (FTS5 trigram + fallback chain)

Ubicacion: `core/memory_store.py:1765`

Pipeline de 14 capas de fallback:
1. FTS5 trigram unicode61
2. PALABRA_COMPLETA (word boundary filter)
3. Prefix wildcards (`_agregar_prefix_wildcards`)
4. Busqueda relajada (OR en vez de AND)
5. Similitud conceptual latente (Jaccard)
6. Evocacion por cadena (spreading activation)
7. Busqueda por categorias
8. Busqueda por dimensiones semanticas
9. Parafrasis (variantes generadas por el agente)
10. Ráfaga (terminos generados por LLM)
11. Busqueda profunda (nodos dormidos)
12. Busqueda por similitud de conceptos
13. Busqueda por peso sinaptico
14. Busqueda cronologica

### 2.3 buscar_por_rafaga (terminos LLM)

Ubicacion: `core/memory_store.py:2528`

- Recibe query + lista de terminos de ráfaga
- Cada término se busca con FTS5 y se fusionan resultados
- Scoring: promedio de scores normalizado por densidad

### 2.4 Sinónimos en largo_plazo

Ubicacion: columna `sinonimos` en tabla `largo_plazo`

- 417 nodos tienen sinónimos declarados
- Formato: strings separados por coma
- Ejemplo: `dennys-metodo-creativo: metodologia, descubrimiento, empirico, intuicion, espiral`
- **NO hay tabla semantica separada** — los sinónimos se extraen directamente de largo_plazo

### 2.5 Indexación Dimensional

Ubicacion: `dimensiones_semanticas` (73 valores, 7 ejes)

| Eje | Valores | Estado |
|-----|---------|--------|
| Emocion | afecto, alegria, frustracion, tristeza, preocupacion, confusion, sorpresa | Produccion |
| Entidad | identidad_individual, identidad_social_legal, identidad_organizacional | Produccion |
| Accion | (valores pendientes) | Diseno |
| Cualidad | (valores pendientes) | Diseno |
| Coordenada | (valores pendientes) | Diseno |
| Intencion | (valores pendientes) | Diseno |
| Dominio | (valores pendientes) | Diseno |

### 2.6 _generar_variaciones (lookup eliminado)

Ubicacion: `core/memory_store.py:1646`

```python
# ponytail: removed semantica table lookup — agent provides synonyms
# via parafrasis_list
```

El lookup a tabla semantica fue eliminado. Ahora el agente provee sinónimos
via el parámetro `parafrasis_list`.

---

## 3. Análisis de Stemming

### 3.1 Prueba con PyStemmer

PyStemmer (Snowball C) instalado y probado. Resultados:

| Palabra original | Stem |
|-----------------|------|
| implementacion | implement |
| implementamos | implement |
| informacion | inform |
| busqueda | busqueda (no stemmea) |
| decodificar | decodific |
| decoder | decoder |

**PyStemmer es superior a NLTK para español.** NLTK tiene bugs
(no stemmea algunas palabras).

### 3.2 Conflicto FTS5 trigram + PALABRA_COMPLETA

Las raíces de stemming (ej: "implement") NO matchean via PALABRA_COMPLETA
porque el filtro de word boundary bloquea substrings.

- `PALABRA_COMPLETA` busca: `implement` como palabra completa
- FTS5 trigram busca: substrings de 3+ caracteres
- Resultado: "implementacion" contiene "implement" pero PALABRA_COMPLETA
  lo bloquea

**Solución:** stemming debe funcionar SIN filtro PALABRA_COMPLETA,
o con un modo que desactive word boundary para stems.

### 3.3 Estado actual

`buscar_por_tokens` ya acepta stems como entrada. El pipeline
agrega prefix wildcards (`implement*`) que permiten matching parcial.
Esto funciona razonablemente bien pero no es óptimo.

---

## 4. Análisis de WordNet

### 4.1 Lookup directo

| Término | Synsets | Nota |
|---------|---------|------|
| `jerga-decoder` | 0 | Compuesto no existe |
| `jerga` | 0 | No existe en WordNet (solo inglés) |
| `decoder` | 2 | `decoder.n.01` = "intellectual who converts messages from code" |
| `decode` | 1 | `decode.v.01` = "convert code into ordinary language" |
| `slang` | 5 | `slang.n.02` = "language of a particular group" |
| `translate` | 1 | `translate.v.01` = "restate words from one language to another" |
| `interpret` | 1 | `interpret.v.01` = "make sense of; assign meaning" |

### 4.2 Cadenas de hiperónimos

```
decode → rewrite → write
slang → non-standard_speech → language
interpret → understand → know
```

Estas cadenas muestran relaciones conceptuales reales que podrían
usarse para expansión automática.

### 4.3 Limitaciones

- **Cobertura español: CERO.** WordNet no tiene palabras en español.
- Necesita capa de traducción ES→EN para funcionar.
- Diccionario de traducción limitado (~200 palabras probadas).
- Palabras como "decodificar" no existen en WordNet aunque "decode" sí.

### 4.4 El problema de la taxonomía

El agente externo (IA Lite) identificó correctamente que:

- `decoder.n.01` se clasifica como "device" (dispositivo)
- `translator.n.01` se clasifica como "person" (persona)
- Compararlos por distancia de árbol da similitud baja porque son
  tipos fundamentales distintos en WordNet

**Solución del agente externo:** usar synsets de proceso
(`decipherment.n.01`, `translation.n.01`) que sí comparten
`coding.n.01` como hiperónimo.

---

## 5. Propuesta del Agente Externo (IA Lite)

### 5.1 Las 3 soluciones propuestas

1. **Domain tags via `synset.topic_domains()`** — clasificar por campo semántico
2. **Synsets de proceso** — usar `decipherment.n.01` y `translation.n.01`
   que comparten `coding.n.01`
3. **Word embeddings** — FastText, Word2Vec para similitud contextual

### 5.2 Evaluación contra BioRAG

| Solución externa | Equivalente en BioRAG | Veredicto |
|-----------------|----------------------|-----------|
| Domain tags | Dimensiones semánticas (73 valores, 7 ejes) | Ya existe y es mejor (explícito, consultable por SQL) |
| Synsets de proceso | Tabla `sinonimos` en largo_plazo + grafo sináptico | Parcialmente existe |
| Word embeddings | Jaccard + Dynamic Multiplicator + Grafo sináptico | Ya existe (caja de cristal vs caja negra) |

### 5.3 Lo que SÍ es nuevo

La idea de "hiperónimo compartido": si dos conceptos comparten un padre
en una taxonomía, se pueden conectar automáticamente. Esto se puede
lograr con la tabla `sinonimos` sin tocar WordNet.

---

## 6. Insights del Usuario

### 6.1 "Dominio como ancla"

Cada término pertenece a un dominio conceptual / género. Si cada nodo
guardado se clasifica por dominio, las búsquedas pueden filtrar por
dominio aunque no haya superposición léxica.

Ejemplo:
- "decodificar password" → dominio: seguridad
- "decodificar jerga" → dominio: lenguaje
- "decodificar colores" → dominio: diseño

### 6.2 "DNA Conceptual"

Cada concepto tiene una identidad única (semántica atómica) que une
palabras con el mismo significado en distintos contextos.

- "decodificar password" + "decodificar jerga" + "decodificar colores"
  → DNA: DESBLOQUEAR_INFO_OCULTA

### 6.3 "Expandir ANTES de buscar"

El flujo actual:
```
query → FTS5 literal → fallback → parafrasis → ráfaga
```

El flujo propuesto:
```
query → expandir con stems + sinónimos + dominio → buscar con TODO
```

---

## 7. Arquitectura Propuesta

### Capa 1: Stemming (ya disponible)

- PyStemmer instalado
- `buscar_por_tokens` ya acepta stems
- **Pendiente:** integrar stemming en el pipeline de `buscar_por_frase`
  antes de FTS5, no solo como fallback

### Capa 2: Expansión de sinónimos

- 417 nodos ya tienen sinónimos en `largo_plazo.sinonimos`
- **Pendiente:** al buscar, expandir el query con los sinónimos de
  los nodos relacionados ANTES de FTS5
- Ejemplo: buscar "decodificar" → expandir con sinónimos de todos
  los nodos que contienen "decodificar" en su columna sinonimos

### Capa 3: Clasificación por dominio conceptual

- Usar la dimensión `Dominio` (ya diseñada en el esquema de 5 dimensiones)
- Clasificar nodos al guardar (el LLM infiere el dominio)
- Filtrar por dominio al buscar

### Capa 4: DNA conceptual (futuro)

- Identificar conceptos que comparten significado profundo
- Crear conexiones automáticas entre nodos con mismo DNA
- Requiere análisis semántico más profundo (posible uso de embeddings
  livianos o clasificación por el LLM al guardar)

---

## 8. Plan de Implementación

### Fase 1: Stemming integrado (corto plazo)

- [ ] Integrar PyStemmer en `buscar_por_frase` antes de FTS5
- [ ] Desactivar PALABRA_COMPLETA para stems
- [ ] Testear con queries reales

### Fase 2: Expansión de sinónimos (mediano plazo)

- [ ] Al guardar: extraer sinónimos del contenido automáticamente
- [ ] Al buscar: expandir query con sinónimos de nodos relacionados
- [ ] Usar grafo sináptico para encontrar nodos relacionados

### Fase 3: Dimensión Dominio (mediano plazo)

- [ ] Implementar dimensión Dominio en la tabla de dimensiones
- [ ] Clasificar nodos existentes por dominio
- [ ] Agregar filtro de dominio a `buscar_por_frase`

### Fase 4: DNA conceptual (largo plazo)

- [ ] Diseñar esquema de DNA
- [ ] Implementar detección de conceptos con mismo DNA
- [ ] Crear conexiones automáticas en el grafo sináptico

---

## 9. Técnicas Evaluadas (Referencia)

| Técnica | Fuente | Estado | Aplicabilidad |
|---------|--------|--------|---------------|
| PyStemmer (Snowball C) | pypi.org/project/PyStemmer | Instalado | Stemming español |
| FTS5 Snowball extension | github.com/abiliojr/fts5-snowball | Evaluado | Stemming nativo SQLite |
| GRF Query Expansion | arxiv.org/pdf/2602.16989 | Investigado | Expansion por grafos |
| ACT-R Spreading Activation | act-r.psy.cmu.edu | Investigado | Evocacion por cadena |
| PMI Sparse Retrieval | mddb.tradik.com | Investigado | Score por co-ocurrencia |
| WordNet (NLTK) | nltk.corpus.wordnet | Probado | Sinónimos (inglés) |
| Wu-Palmer Similarity | nltk.corpus.wordnet | Probado | Distancia taxonómica |

---

## 10. Nodos Relacionados en BioRAG

- `teoria_ejes_semanticos_biorag` (Architecture)
- `indexacion_dimensional_explicita` (Architecture)
- `biorag_v13_4_expansion_dimensiones` (Architecture)
- `v13_1_parafrasis_expansion_semantica` (Architecture)
- `principio_tres_capas_biorag` (Principle)
- `principio_multiples_vias_mismo_destino` (Principle)
- `principio_paráfrasis_nivel_dios` (Principle)
- `arquitectura_dos_niveles_biorag` (Architecture)
- `raiz_false_positives_biorag_v10` (Lesson)
- `auto_vincular_tres_capas_semantica` (Architecture)
- `biorag_v8_dynamic_multiplicator` (Architecture)

---

*Documento creado el 2026-07-09. Investigacion en curso.*
