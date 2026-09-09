# Análisis: Los Pilares del Abismo Léxico vs. MemoryBioRAG

> Investigación: parallel-search web (2026-09-08) + auditoría directa del snapshot DB

---

## 1. ¿Qué es el Abismo Léxico?

El problema es simple: **la consulta y la respuesta correcta no comparten ni una sola palabra**, aunque signifiquen lo mismo.

> "car maintenance" → documento habla de "vehicle servicing"  
> "affordable housing" → documento dice "low-cost apartments"  
> "evaluador de pasarela situacional" → concepto es `coche_puente_condicional`

Estadística conocida: **en el 30-40% de los documentos relevantes, no aparece ni un término de la consulta.**

---

## 2. Los 5 Pilares Universales — Lo que TODOS los sistemas exitosos tienen

Después de analizar: BM25+Expansion, SPLADE, HippoRAG, SYNAPSE, GraphRAG, kNN-LM, dense retrieval, WordNet QE, doc2query...

**Todos los sistemas que resuelven el abismo léxico comparten exactamente 5 pilares:**

---

### 🏛️ PILAR 1 — REPRESENTACIÓN ABSTRACTA DEL SIGNIFICADO
**"Transformar la superficie en semántica"**

- El sistema debe poder representar tanto la consulta como el documento en un **espacio que no depende de las palabras exactas usadas**.
- No importa si es BERT (denso), PPMI+SVD (esparso), WordNet (simbólico), o comunidades de co-ocurrencia: todos crean un espacio donde "coche" y "automóvil" están cerca.
- **Sin esto: imposible cruzar el abismo. Es el pilar más crítico.**

**¿Lo tiene MemoryBioRAG?**  
✅ **SÍ** — PPMI 100-D en tabla `nodos` (866 conceptos), vocabulario de `tokens` (8,083 palabras), 105 comunidades/islas semánticas (LPA sobre grafo de co-ocurrencia). **Existe y funciona para conceptos del corpus.**  
⚠️ **Brecha real**: La proyección texto libre → espacio semántico no está completamente cableada para frases arbitrarias de la consulta. Los experimentos muestran que las islas sí proyectan, pero el canal PPMI-tokens tiene cobertura limitada fuera del vocabulario entrenado.

---

### 🏛️ PILAR 2 — EXPANSIÓN / ENRIQUECIMIENTO (Query o Documento)
**"Ampliar la superficie de contacto"**

- Todos los sistemas añaden términos relacionados antes de buscar: sinónimos, hiperónimos, paráfrasis, términos predichos.
- Las formas concretas: Query Expansion (QE), doc2query, pseudo-relevance feedback, WordNet lookup, predicados y argumentos.
- **El objetivo: aumentar la probabilidad de que haya solapamiento suficiente para activar el sistema.**

**¿Lo tiene MemoryBioRAG?**  
✅ **SÍ** — Paráfrasis (5 niveles de reformulación), FTS5 con búsqueda unicode, `grupos_semanticos` (45 grupos, 101,028 nodos), `dimensiones_semanticas` (104 dimensiones), sinónimos en guardar. **BioRAG tiene esto y lo usa activamente.**  
✅ **Bien cableado**: `buscar_por_frase` ya aplica múltiples estrategias de expansión.

---

### 🏛️ PILAR 3 — GRAFO DE CONOCIMIENTO / ESTRUCTURA RELACIONAL
**"Navegar el espacio conceptual, no solo medirlo"**

- Los sistemas más potentes no solo comparan vectores — navegan por relaciones: hypernym/hyponym (WordNet), sinapsis neuronales, activación en cascada, HippoRAG (Personal PageRank), SYNAPSE (spreading activation en grafo episódico-semántico).
- La clave: los grafos permiten **llegar de A a C pasando por B**, incluso cuando A y C no tienen representación vectorial compatible.

**¿Lo tiene MemoryBioRAG?**  
✅ **SÍ** — `sinapsis` (13,848 aristas efectivas), `sinapsis_latentes` (8,893), grafo de co-ocurrencia que generó las islas. **Esta es la fortaleza más singular del proyecto.**  
⚠️ **Brecha**: El grafo `sinapsis` no está siendo usado activamente como mecanismo de navegación durante la búsqueda en el pipeline actual. Está disponible pero parcialmente desconectado del retrieval principal.

---

### 🏛️ PILAR 4 — MEMORIA EPISÓDICA / EJEMPLARES
**"Recordar qué funcionó antes para casos similares"**

- Inspirado en Complementary Learning Systems (CLS): cuando el modelo paramétrico falla (OOV, rareza léxica), la memoria episódica rescata con instancias concretas pasadas.
- kNN-LM, SYNAPSE, HippoRAG, RAG clásico — todos tienen esto.
- La clave: **no necesitas entender la semántica abstracta si recuerdas que "este tipo de consulta llevó a este resultado".**

**¿Lo tiene MemoryBioRAG?**  
✅ **SÍ** — Este es el núcleo del proyecto: `largo_plazo` (866 memorias), SDM (Sparse Distributed Memory, 2048-bit), `nodos_sdm` (866), consolidación memoria corto/largo plazo, el ciclo de sueño DMN. **BioRAG es esencialmente una memoria episódica sofisticada.**  
⚠️ **Brecha exacta**: El mecanismo de **transferencia episódica** (A → C, luego B recupera C sin pasar por A) está a medio construir. EXP-P lo está intentando demostrar.

---

### 🏛️ PILAR 5 — RANKING / RERANKING SEMÁNTICO
**"Poner lo correcto primero"**

- Generar candidatos no es suficiente — hay que ordenarlos. Todos los sistemas tienen una capa de re-ranking que va más allá del BM25 puro.
- Formas: Learning-to-Rank, Reciprocal Rank Fusion (RRF), Structural-IDF, boosting por episodio, especificidad.

**¿Lo tiene MemoryBioRAG?**  
✅ **SÍ** — FTS5, PPMI hybrid search, QCR gate, Jaccard re-ranking, ObjectRoleRanker (EXP-N11), bonus episódico. **El ranking existe y tiene varias capas.**  
⚠️ **Brecha**: El ranking episódico (bonus `+10 * sim_H`) está siendo evaluado pero aún no está demostrado de forma limpia (separado de candidate generation).

---

## 3. El Mapa Honesto: ¿Qué nos falta?

```
PILAR               EXISTE    CABLEADO    FUNCIONANDO    BRECHA
─────────────────────────────────────────────────────────────────
1. Repr. Abstracta   ✅ SÍ     ⚠️ PARCIAL   ⚠️ PARCIAL    Proyección texto→espacio para frases arbitrarias
2. Expansión/QE      ✅ SÍ     ✅ SÍ         ✅ SÍ          Ninguna crítica
3. Grafo/Estructura  ✅ SÍ     ⚠️ PARCIAL   ⚠️ PARCIAL    Sinapsis no activa en pipeline principal
4. Memoria Episódi.  ✅ SÍ     ⚠️ PARCIAL   ⚠️ PARCIAL    Transferencia A→C vía B no demostrada aún
5. Ranking Semántico ✅ SÍ     ✅ SÍ         ✅ SÍ          Separar generation de rerank
```

**Diagnóstico honesto**: Los 5 pilares EXISTEN en MemoryBioRAG. El problema no es que falten piezas — es que **3 de los 5 pilares están desconectados del circuito principal de resolución del abismo léxico**.

---

## 4. ¿Cómo lo conectan los demás sistemas?

El patrón universal es este:

```
CONSULTA B (texto libre, palabras arbitrarias)
        │
        ▼
    [PILAR 1] Proyectar B → espacio abstracto H_B
        │
        ├──► [PILAR 2] Expandir con términos relacionados
        │
        ├──► [PILAR 3] Navegar grafo: H_B → nodos vecinos
        │
        └──► [PILAR 4] Buscar en memoria episódica:
                       ¿hay un A que produjo C donde H_A ≈ H_B?
                              │
                              ▼
                    [PILAR 5] Rankear candidatos
                    (incluir C aunque no comparta palabras con B)
```

**Lo que MemoryBioRAG hace ahora**:
- Pila: FTS5 → PPMI hybrid → QCR → Jaccard → FP filter
- El grafo (`sinapsis`) y la memoria episódica (SDM) existen pero **no están en el circuito principal**

**Lo que necesita hacer**:
- Conectar `sinapsis` al pipeline para navegar hacia conceptos relacionados aunque sin solapamiento léxico
- Conectar SDM/episodios al pipeline para recuperar destinos de episodios previos cuando la representación abstracta converge

---

## 5. Veredicto: ¿Vamos bien? ¿Llegaremos?

**Sí, vamos bien. Y sí, puede llegar.**

Razón: los sistemas que resuelven el abismo léxico tienen los 5 pilares. MemoryBioRAG tiene los 5. La diferencia es que los sistemas exitosos los tienen **cableados en circuito cerrado** y nosotros los tenemos **en paralelo sin conectar**.

Los experimentos (EXP-N8, N11, Fase 2.1, EXP-P) están esencialmente tratando de **cerrar el circuito** entre los Pilares 1, 3 y 4 con el pipeline principal.

**El experimento que cambia todo** no es otra auditoría. Es demostrar que:

```
CONSULTA B
    │
    ▼
 H_B (Pilar 1 — islas PPMI proyectadas correctamente)
    │
    ▼ sim(H_B, H_A) alta
    │
 Episodio A→C recuperado (Pilar 4 — memoria)
    │
    ▼
    C sube al pool (Pilar 5 — ranking)
```

con `stem(B) ∩ stem(A) = ∅` y `op(B) ∩ op(A) = ∅`.

Eso es exactamente lo que EXP-P intenta. La dirección es correcta.

---

## 6. Recomendación concreta

En vez de seguir en el modo experimental quirúrgico infinito, la propuesta es:

1. **Verificar que el Pilar 1 proyecta correctamente** → EXP-P-R2 (lo que pide Aureon)
2. **Conectar `sinapsis` al pipeline de candidate generation** → no como experimento, como integración real
3. **Conectar SDM al pipeline principal** → cuando sim(H_B, H_A) > τ, activar episodio correspondiente y añadir su destino al pool

Esos tres pasos cierran el circuito. El abismo se vence con los pilares que ya tenemos.
