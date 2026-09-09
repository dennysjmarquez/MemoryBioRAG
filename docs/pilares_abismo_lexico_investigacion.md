# Pilares que vencen el abismo léxico — investigación verificada contra fuentes primarias

**Objetivo:** no repetir la lista de la sesión anterior sin más — ir a los papers/fuentes primarias de cada sistema citado, confirmar qué mecanismo usa cada uno de verdad, y ver cuáles de esos mecanismos son replicables sin embeddings/redes neuronales, que es la restricción real de MemoryBioRAG.

**Metodología:** búsqueda web dirigida a papers (arXiv, NeurIPS, ACL) y documentación oficial de cada sistema, no blogs genéricos salvo cuando explican mejor un mecanismo ya confirmado en el paper. Todo lo que sigue está parafraseado de esas fuentes primarias, con la fuente al lado.

---

## Hallazgo principal (esto es lo importante para ustedes)

Casi todos los sistemas modernos que "venden" haber resuelto el abismo léxico **usan una red neuronal en algún punto interno**, aunque el producto final se llame "sparse" o "no-denso":

| Sistema | Mecanismo central | ¿Usa red neuronal internamente? |
|---|---|---|
| **SPLADE** | Expansión de términos aprendida vía la cabeza MLM de BERT + regularización de sparsity (Formal et al., SIGIR'21/22, repo `naver/splade`) | **Sí** — es literalmente BERT por dentro, solo que la salida es un vector sparse sobre el vocabulario |
| **kNN-LM** | Interpola la distribución del LM con una búsqueda k-NN sobre un datastore de contextos, donde las "keys" son representaciones del propio LM (Khandelwal et al. 2020) | **Sí** — las keys del datastore son embeddings del contexto generados por el LM |
| **HippoRAG / HippoRAG 2** | Extrae tripletas (OpenIE) con un LLM, construye un grafo de conocimiento, y navega con Personalized PageRank sembrado en los conceptos de la query; las "synonymy edges" del grafo se generan con un modelo de embeddings (Contriever/NV-Embed/GritLM) | **Sí, parcialmente** — el núcleo de recuperación (PPR sobre grafo) NO es una red neuronal, pero la construcción del grafo (extracción de tripletas) y las aristas de sinonimia SÍ dependen de un LLM/embeddings |
| **doc2query / DeepCT** | Generan términos de expansión de documentos con un modelo generativo (T5) | **Sí** |

Esto es clave porque ustedes dijeron "no somos modelos embebidos ni queremos serlo". La conclusión honesta es: **el linaje que sí es 100% libre de redes neuronales es más viejo y más limitado** — es la Query Expansion clásica (WordNet, tesauros) y Pseudo-Relevance Feedback (Rocchio, RM3, DFR Bo1) de la IR pre-neuronal. Eso es exactamente lo que MemoryBioRAG ya tiene (Concept Hub + WordNet + Domain Dict). No están reinventando algo raro — están en la línea simbólica clásica, que es legítima pero **tiene un límite documentado**, no una promesa de éxito garantizado.

---

## El pilar que la literatura documenta como decisivo — y su riesgo conocido

Fuente (Nature Sci Reports, 2024, paraphraseado): la expansión de query (QE) es ampliamente usada en IR porque resuelve el desajuste de vocabulario expandiendo la query original con sinónimos o términos cercanos antes de buscar.

Pero hay un hallazgo repetido en varios papers que **coincide exactamente con lo que ya midieron ustedes en la matriz de ablación A/B/C/D**: un paper sobre mejora de QE con WordNet concluye explícitamente que la expansión de query, **por sí sola, no siempre logra mejorar la recuperación** (Fernández-Reyes et al., paraphraseado). Y el fenómeno tiene nombre en la literatura clásica: **"query drift"** — cuando los términos añadidos alejan la query de la intención original en vez de acercarla (documentado en el survey de Wang, arXiv 2308.00415, citando a Manning et al. 2008).

Esto no es una casualidad de su sistema. Es un riesgo **conocido y nombrado** en la literatura desde hace 20+ años. Lo que ustedes vieron (Hub+WordNet ON vs OFF sin diferencia en el corpus grande, y hasta un poco peor en "sinónimo") es un caso de libro de query drift, no un bug exclusivo de MemoryBioRAG.

**Consecuencia práctica:** el pilar de Expansión no es "actívalo y ya" — necesita un mecanismo de control de drift (algo que decida CUÁNDO expandir y cuánto, no expandir siempre). De hecho ya tienen algo así: el comentario en el código de `buscar_por_frase` dice literalmente que expandir SIEMPRE regresionó resultados, y que ahora solo expande si la query cruda no encuentra suficiente por FTS5 primero. Eso es, sin que lo hayan llamado así, un guard anti-drift. Vale la pena que lo sepan y lo traten como principio de diseño, no como parche puntual.

---

## Mapeo: pilares de la literatura → lo que MemoryBioRAG ya tiene → qué está probado con evidencia real

| Pilar (literatura) | Equivalente simbólico sin embeddings (el que ustedes pueden usar) | ¿Lo tienen? | ¿Está probado con datos propios? |
|---|---|---|---|
| **Representación abstracta del significado** | Matrices de co-ocurrencia (PPMI+SVD), en vez de embeddings neuronales | Sí — 866 conceptos, 100-D | Parcial — la proyección de frases libres arbitrarias no está completa (visto en el código) |
| **Expansión de query** | Tesauro/WordNet + PRF simbólico (no generativo) | Sí, y con guard anti-drift ya implementado | **Sí, con evidencia fuerte**: 0/5 → 4/5 en el benchmark de abismo genuino (0 overlap real). Pero casi nulo en el corpus grande, donde la mayoría no es abismo real |
| **Navegación estructural (grafo)** | Grafo de co-ocurrencia con pesos (`sinapsis`), en vez de PPR sobre KG extraído por LLM | Sí — 13,848 aristas | Parcial — está en el pipeline (fallback, boost de inferencia) pero `context_window` (que trae vecinos) está apagado por defecto |
| **Memoria episódica / recuerdo de casos previos** | SDM (Sparse Distributed Memory), sin necesidad de un datastore de embeddings tipo kNN-LM | Sí, existe la infraestructura | **No — 0/5 rescates por generación en el experimento más reciente de la propia rama (EXP-P-R1)** |
| **Ranking / especificidad** | Peso tipo IDF estructural (lo que HippoRAG llama "node specificity") | Existe en varias capas (BM25, boost episódico) | No auditado en esta sesión |

---

## Lo que este mapeo les dice, en limpio

1. **No hay que inventar un pilar nuevo.** Los 5 pilares de la síntesis anterior siguen siendo razonables como taxonomía — la literatura primaria los confirma en distintas combinaciones (HippoRAG hace 1+3+5, SPLADE hace 1+2, kNN-LM hace 4).
2. **El pilar donde ya tienen evidencia real de que funciona es Expansión (2), pero solo para abismo genuino — no como interruptor global.** Eso hay que dejarlo así de explícito en cualquier informe: "funciona cuando el abismo es real, no cuando no lo es" — no es lo mismo que "funciona, punto".
3. **El pilar más débil de verdad, con datos propios que lo confirman, es Memoria Episódica (4).** No es cuestión de cablearlo más — el propio experimento EXP-P-R1 barrió umbrales de 0.10 a 0.40 y solo rescató 1 de 5 casos, y ni siquiera por generación, solo por rerank. Ahí sí hay trabajo real de diseño pendiente, no solo de "conectar cables".
4. **Grafo (3) es el que más se parece a lo que hace HippoRAG (PPR) sin usar LLM para extraer tripletas** — ustedes ya tienen el grafo de co-ocurrencia; lo que falta, según el propio código, es activar `context_window` por default o probarlo explícitamente en el benchmark de abismo genuino (los 5 casos), que es donde de verdad importaría medirlo.
5. **No están "atrasados" por no tener embeddings.** El linaje simbólico que usan es real, tiene historia en IR clásica, y tiene un techo conocido (query drift) que ya empezaron a mitigar sin llamarlo así. La diferencia con HippoRAG/SPLADE no es "ellos tienen algo mágico que ustedes no" — es que ellos delegan la extracción de estructura (tripletas, sinónimos) a un LLM/embeddings, y ustedes la extraen de estadística de co-ocurrencia. Es un trade-off, no una carencia.

---

## Próximo paso honesto, si quieren que lo mida yo también
Lo que no verifiqué todavía: si `sinapsis`/`context_window` activado sube el score en los 5 casos de abismo genuino (el único benchmark donde de verdad se ve el efecto, según lo que auditamos). Sería el experimento más barato y más informativo que falta — mismo formato que ya usan (`disable_semantic_layer` pero para el grafo), sobre los mismos 5 casos. Si quieren, lo corro directamente sobre el repo la próxima vez que me pasen acceso de escritura o me digan que lo haga en modo lectura con una copia.

## Fuentes consultadas
- Formal, Piwowarski, Clinchant — SPLADE (arXiv 2107.05720) y SPLADE v2 (arXiv 2109.10086)
- Khandelwal et al. — kNN-LM (referenciado vía múltiples papers de seguimiento, arXiv 2301.02828, 2102.02557)
- Jiménez Gutiérrez, Shu, Gu, Yasunaga, Su — HippoRAG (arXiv 2405.14831, NeurIPS 2024) y HippoRAG 2 (repo `OSU-NLP-Group/HippoRAG`)
- Wang — Generative Query Reformulation for Effective Adhoc Search (arXiv 2308.00415), citando Manning et al. 2008 sobre query drift
- Web Search Enhancement Using WordNet Query Expansion Technique; Pseudo Relevance Feedback by linking WordNet — sobre QE clásica y sus límites
- Auditoría directa del código y reportes de la rama `cuantificarelaporterealdeConceptHubyWordNet` (sesión anterior de este mismo hilo)
