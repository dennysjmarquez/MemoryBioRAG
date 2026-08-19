# AUDITORÍA PROFUNDA — 26 MECANISMOS CIENTÍFICOS DE BIORAG
**Fecha:** 2026-08-19  
**Autor:** Artemis-OEC (auditoría de código real)  
**Objetivo:** Diagnosticar qué está bien ubicado, qué está desconectado, qué se desperdicia, y qué falta inventar — para que BioRAG encuentre cualquier cosa, como sea que se busque, sin GPU ni embeddings externos.

---

## METODOLOGÍA

Este documento **no es una lista de lo que debería existir**. Es una auditoría del código real, función por función, conexión por conexión. Cada hallazgo está respaldado por una línea de código verificada.

---

## PARTE 1 — EL PIPELINE REAL DE BÚSQUEDA

### Cómo fluye una búsqueda de punta a punta (`buscar_por_frase`, línea 4098)

```
QUERY ENTRANTE
    │
    ├─ Filtro SRL por roles semánticos (buscar_por_rol) → conceptos_validos_rol
    ├─ Normalización y filtro de stopwords
    ├─ Protección de términos entre comillas dobles ("CV", "IA")
    │
    ╔══ CAPA DE RECUPERACIÓN (candidatos) ══════════════════════════════════╗
    │  0.0  Filtro por roles SRL (si buscar_por_rol)                        │
    │  0.1  LIKE en concepto (substring, siempre activa)                    │
    │  1.0  FTS5 NEAR (palabras cercanas entre sí, radio=15)                │
    │  1.0b FTS5 AND exacto + paráfrasis                                    │
    │  1.4  FTS5 unicode61 + prefix wildcards (< 3 resultados)              │
    │  1.7  Trigramas best-word (tolerancia typos, < 3 resultados)          │
    │  1.8a Similitud latente Jaccard (< 3 resultados)                      │
    │  1.8b Snap reciente (últimos 7 días, < 3 resultados)                  │
    │  1.9  Evocación por cadena multi-hop (< 3 resultados)                 │
    │  2.0  Substring + PALABRA_COMPLETA (< 3 resultados)                   │
    │  2.1  Fallback simbólico: Levenshtein + WordNet + Traducción           │
    │  3.0  Pseudo-relevance feedback dimensional (si FTS ≥ 3 resultados)   │
    │  3.1  Fallback dimensional con umbral (si FTS devuelve 0)             │
    │  4.0  Sinónimos explícitos + WordNet (palabras_like)                  │
    │  4.5  Precompute predicados SRL (contexto keywords)                   │
    │  5.0  Content-based expansion (palabras en contenido, ≥ 2 matches)    │
    ╚═══════════════════════════════════════════════════════════════════════╝
    │
    ╔══ SCORING HÍBRIDO (13 señales) ═══════════════════════════════════════╗
    │  #1  BM25 normalizado (peso=0.25)                                     │
    │  #2  Dimensiones semánticas (peso=0.14)                               │
    │  #3  Match en concepto (peso=0.08)                                    │
    │  #4  Match en sinónimos (peso=0.08)                                   │
    │  #5  Peso sináptico LTP/LTD (peso=0.10)                               │
    │  #6  Jaccard/cadena multi-hop (peso=0.10)                             │
    │  #7  Grupo semántico WordNet (peso=0.10)                              │
    │  #8  Similitud temática IDF (peso=0.08)                               │
    │  #9  Recencia temporal (peso=0.04)                                    │
    │  #10 Asociaciones (peso=0.02)                                         │
    │  #11 Jensen-Shannon Divergence (peso=JSD_WEIGHT, default bajo)        │
    │  #12 Predicados SRL (peso=0.20 — el más alto)                        │
    │  #13 PPMI+SVD+Retrofitting (peso=0.15)                                │
    ╚═══════════════════════════════════════════════════════════════════════╝
    │
    ╔══ POST-PROCESADO ══════════════════════════════════════════════════════╗
    │  - Bonos logit (match_exacto, sinónimo_exacto)                        │
    │  - Puerta QCR (Query Coverage Ratio ≥ 50%)                            │
    │  - Re-ranking Jaccard léxico (Fase C, OFF por defecto)                │
    │  - Inhibición lateral GABA (top_score ≥ 0.80)                        │
    │  - Filtro PALABRA_PREFIJO (queries de 1 sola palabra)                 │
    │  - Ampliación por empate (queries cortas ≤ 2 palabras)                │
    │  - Ordenamiento temporal post-hoc (si recencia/antiguedad)            │
    │  - Expansión por context_window (vecinos sinápticos)                  │
    │  - Signal #14 ADN Conceptual (OFF por defecto, flag experimental)     │
    │  - Calibración conforme (solo en MCP, no en motor)                    │
    ╚═══════════════════════════════════════════════════════════════════════╝
    │
    RESULTADO RETORNADO
```

---

## PARTE 2 — AUDITORÍA POR MECANISMO: ¿ESTÁ DONDE DEBE ESTAR?

### TABLA MAESTRA DE ESTADO

| # | Mecanismo | Módulo real | Conectado al pipeline | Estado |
|---|-----------|-------------|----------------------|--------|
| 1 | PPMI+SVD (Señal #13) | `core/ppmi_vectorizer.py` + `core/ppmi_hybrid_search.py` | ✅ scoring loop L5285 | Activo, peso=0.15 |
| 2 | LSA/SVD truncado | `core/ppmi_vectorizer.py` (PPMISVD class) | ✅ parte del motor PPMI | Activo (dentro del #13) |
| 3 | Fusión multi-señal (13 señales) | `_calcular_score_hibrido()` L3235 | ✅ core del scoring | Activo |
| 4 | HDC — VSA Binding | `core/sdm.py` L186 (`hdc_bind_bytes`) | ⚠️ Solo en indexación, NO en búsqueda | PARCIAL — tecnología desperdiciada |
| 5 | SDM — Sparse Distributed Memory | `core/sdm.py` (`buscar_sdm` L502) | ❌ `buscar_sdm()` existe pero NADIE la llama en búsqueda | DESCONECTADO — tecnología dormida |
| 6 | Curva del olvido / LTD | `ciclo_sueno_consolidacion()` | ✅ en consolidación | Activo (asíncrono) |
| 7 | PMI / auto-vincular | `core/pmi_semantico.py` | ✅ consolidación + auto-link | Activo |
| 8 | Retrofitting de grafo | `core/ppmi_vectorizer.py` | ✅ ajusta vectores PPMI con sinapsis | Activo (dentro del #13) |
| 9 | LTP/LTD sináptico | `core/sinapsis.py` | ✅ actualización de pesos | Activo |
| 10 | Consolidación corto→largo | `ciclo_sueno_consolidacion()` | ✅ pipeline completo | Activo (asíncrono) |
| 11 | Spreading activation multi-hop | `_evocacion_por_cadena()` L3052 | ✅ Fallback 1.9 | Activo (solo como fallback tardío) |
| 12 | Inhibición lateral GABA | `buscar_por_frase()` L5372 | ✅ post-scoring | Activo |
| 13 | RPE / Dopamina | `mcp_server.py::biorag_feedback()` | ✅ señal explícita de feedback | Activo |
| 14 | Marcador somático | `dmn_engine.py` + `memory_store.py` | ⚠️ Guardado pero impacto en scoring no medido | PARCIAL |
| 15 | Escalado sináptico homeostático | `memory_store.py` (consolidación) | ✅ normaliza corteza activa | Activo |
| 16 | Léxico generativo (cualia) | Dimensiones semánticas — scoring #2 | ✅ 13 ejes activos | Activo |
| 17 | Evidencialidad (epistemia) | Dimensiones semánticas — scoring #2 | ✅ eje epistemia | Activo |
| 18 | Efecto autorreferencia | Dimensiones semánticas | ⚠️ eje existe, diferencial en scoring no | PARCIAL |
| 19 | Modalidad deóntica | Dimensiones semánticas | ⚠️ eje existe, diferencial no | PARCIAL |
| 20 | Clasificación WordNet | `core/clasificador_wordnet.py` — señal #7 | ✅ grupo_score activo | Activo |
| 21 | SRL predicados | `core/srl_extractor.py` + señal #12 | ✅ señal más pesada (0.20) | Activo pero con advertencia de canibalización |
| 22 | DMN / Spindles Replay | `core/dmn_engine.py` + `sleep_cycle.py` | ⚠️ Daemon autónomo, no integrado en búsqueda | Activo (aislado) |
| 23 | Pattern Separation hipocampal | `core/inferencia_transitiva.py` | ✅ validación dual PMI+dim | Activo |
| 24 | Divergencia Jensen-Shannon | `_calcular_jsd()` — señal #11 | ✅ pero peso bajo | Activo con peso subóptimo |
| 25 | Label Propagation | `core/auto_clustering.py` | ⚠️ corre en consolidación, NO en búsqueda | PARCIAL |
| 26 | Levenshtein | `core/fallback_simbolico.py` — Fallback 2.1 | ✅ fallback simbólico | Activo (último recurso) |

---

## PARTE 3 — DIAGNÓSTICO DE PROBLEMAS CRÍTICOS

### PROBLEMA 1 (ROJO): SDM completamente desconectada del pipeline de búsqueda

**Hallazgo verificado:** `buscar_sdm()` existe en `core/sdm.py:502`. `indexar_nodo_sdm()` corre al guardar. Pero **CERO llamadas a `buscar_sdm()` existen en `memory_store.py` o `mcp_server.py`**.

El sistema indexa 2048 bits por nodo en `nodos_sdm`, los mantiene frescos con dirty-sets y reindex selectivo, y luego... no los usa para buscar. Es como construir un motor de búsqueda por similitud binaria completo y dejarlo apagado.

**El potencial perdido:** SDM puede recuperar nodos aunque la query esté incompleta, tenga ruido, o sea solo una descripción parcial — sin necesidad de tokens exactos. Eso es exactamente lo que no tiene BioRAG hoy para queries muy vagas.

**Oportunidad:** Convertir `buscar_sdm()` en Fallback 2.5 — activarlo cuando las capas 1.0–2.1 devuelven 0 resultados. La similitud por Hamming distance del vector binario 2048-bit encuentra nodos temáticamente relacionados sin match léxico.

---

### PROBLEMA 2 (ROJO): HDC Binding solo vive en indexación, no en ranking

**Hallazgo:** `hdc_bind_bytes()` en `core/sdm.py:153` vincula tokens con categoría/contexto. Se usa al generar el vector SDM, pero ese vector SDM no entra al scoring.

El vector 2048-bit de cada nodo codifica `(contenido, concepto, dimensiones_hebbianas, categoría, vecinos)` con ortogonalidad VSA. Esta representación rica se desaprovecha totalmente al no entrar al scoring.

**Oportunidad:** El score de similitud SDM (Hamming/Jaccard ponderado por segmentos) podría ser la Señal #14 real — más rica que el JSD porque incluye estructura dimensional y vecinal en el vector.

---

### PROBLEMA 3 (AMARILLO): Spreading activation es el penúltimo fallback, no una señal proactiva

**Hallazgo:** `_evocacion_por_cadena()` (Fallback 1.9) solo se activa cuando hay **menos de 3 resultados** de todas las capas anteriores.

El problema: una query semántica válida puede encontrar 5+ nodos por tokens parciales — pero ninguno es el correcto. En ese caso, la evocación por cadena **nunca se activa** porque `len(todos) >= 3`. Los 5 nodos incorrectos bloquean el mecanismo más bio-inspirado del sistema.

**Oportunidad:** La activación en cadena debería ser una señal de re-ranking, no un fallback. Calcular el score de evocación para los top-K candidatos y usarlo como boost en `_calcular_score_hibrido()`.

---

### PROBLEMA 4 (AMARILLO): Predicados SRL (#12 = 0.20) con advertencia documentada de canibalización

**Hallazgo en código L5274:**
```
# CANIBALIZACIÓN DEMOSTRADA 2026-08-04: si se re-corre el backfill de
# predicados, re-verificar contra el re-ranking jaccard (Fase C). El backfill
# restaura recuperación perdida pero canibaliza la señal #12 con jaccard activo.
```

La señal más pesada del sistema (0.20) tiene un conflicto documentado con otra señal. Esto significa que hay casos donde subir los predicados baja el recall general.

**Oportunidad:** Los predicados deberían actuar como gate condicional — si la query tiene estructura predicativa detectada, amplificar; si no, dejar en 0.0.

---

### PROBLEMA 5 (AMARILLO): Label Propagation genera comunidades pero no se usa para buscar

**Hallazgo:** `core/auto_clustering.py` detecta comunidades densas en el grafo de sinapsis. Se guardan con nombre temático. **Pero en `buscar_por_frase`, no hay señal que use la membresía de comunidad del candidato vs. la comunidad de la query**.

**Oportunidad:** Si la query activa nodos de la comunidad C1, los demás nodos de C1 deberían recibir un boost de "co-comunidad" — semántica emergente sin diccionario externo.

---

### PROBLEMA 6 (AMARILLO): DMN genera insights autónomos pero no retroalimenta el grafo

**Hallazgo:** El daemon DMN genera hipótesis en `core/dmn_engine.py` y las guarda como nodos normales. Pero esas hipótesis no crean sinapsis reforzadas entre los conceptos que sintetizaron.

**El potencial:** Si el DMN conecta A→B→C en una hipótesis, esa cadena debería crear una sinapsis latente de alta confianza entre A y C, disponible para spreading activation en búsquedas. Hoy el DMN piensa pero no escribe en el grafo de búsqueda.

---

### PROBLEMA 7 (VERDE): JSD activa pero con peso subóptimo y no adaptativo

La JSD es la única señal que mide la distribución completa de tokens, no presencia individual. Para queries por tema ("qué aprendí sobre JavaScript"), debería pesar más que BM25.

**Oportunidad:** Peso adaptativo — si la query tiene ≥ 4 tokens (temática), JSD_WEIGHT × 2 dinámicamente.

---

### PROBLEMA 8 (VERDE): Dimensiones semánticas con coseno binario, sin IDF dimensional

El scoring de dimensiones usa coseno binario ponderado. Pero dos nodos que comparten una dimensión rarísima vs. una ubícua deberían discriminarse. No hay IDF para las dimensiones.

**Oportunidad:** Las dimensiones deberían tener peso por rareza (IDF dimensional): una dimensión compartida por 5% de nodos es más discriminante que una compartida por 80%.

---

## PARTE 4 — EL PROBLEMA MATEMÁTICO DE FONDO: EL QCR IGNORA EL IDF

El sistema tiene dos tipos de fallo estructuralmente distintos:

**Tipo A — Fallo léxico:** La query usa palabras que no aparecen en ningún nodo. Las capas literales fallan. Las capas simbólicas y sinónimos deberían rescatar.

**Tipo B — Fallo semántico por ambigüedad:** La query es válida léxicamente pero el QCR Gate puede estar eliminando candidatos legítimos. Un nodo puede tener score_hibrido 0.65 pero ratio_qcr 0.40 (2 de 5 tokens matchean) → filtrado por QCR. Si esos 2 tokens son los más raros y específicos de la query, el filtro es incorrecto.

**El QCR actual:**
```
ratio_qcr = tokens_match / tokens_total
```

**QCR propuesto — ponderado por IDF:**
```
ratio_qcr_idf = Σ(idf(t) para t ∈ query ∩ nodo) / Σ(idf(t) para t ∈ query)
```

Si el 40% de tokens matchean pero son los tokens más raros (informativos), el QCR-IDF puede dar 0.70+, clasificando correctamente el nodo como relevante. Si el 90% de tokens matchean pero son stopwords "informativas", el QCR-IDF baja porque esos tokens no discriminan.

Este cambio afecta la frontera de decisión sin tocar el scoring híbrido — es la pieza matemáticamente más correcta del plan.

---

## PARTE 5 — OPORTUNIDADES PRIORIZADAS

### PRIORIDAD ALTA — Alto impacto, bajo riesgo

**OPT-1: Activar SDM como Fallback 2.5**
En `buscar_por_frase`, después del Fallback 2.1 (simbólico):
```python
# Fallback 2.5: SDM — recuperación asociativa por similitud binaria
# Activa cuando todas las capas léxicas devuelven 0 resultados.
# No requiere match de tokens; busca por Hamming distance en vectores 2048-bit.
if not modo_estricto and len(todos) < 3:
    from core.sdm import buscar_sdm
    sdm_results = buscar_sdm(cerebro=self, query=query, radio_max=400, limite=5)
    # Merge evitando duplicados
```

**OPT-2: SDM score como Señal #14 en el scoring loop**
Pre-cargar vector SDM de la query una sola vez. Para cada candidato, calcular Jaccard ponderado por segmentos (PESO_DIMENSION=2.5, PESO_TOKEN=1.0). Peso en scoring: 0.05–0.08.

**OPT-3: QCR ponderado por IDF**
Reemplazar `ratio_qcr = matches/total` por ratio ponderado por frecuencia inversa de tokens. Los tokens raros pesan más en la decisión de filtrar.

### PRIORIDAD MEDIA — Mejora de señales existentes

**OPT-4: Spreading activation como señal proactiva (no fallback)**
Calcular score de evocación para top-50 candidatos post-FTS5, añadir como señal al scoring con peso 0.05.

**OPT-5: Comunidades de grafo como señal de co-pertenencia**
Recuperar la comunidad del nodo semilla FTS5 top-1. Todos los miembros de esa comunidad reciben +0.05 de boost. Semántica emergente del uso real.

**OPT-6: DMN → sinapsis latentes (cierre del loop autónomo)**
Cuando el DMN sintetiza hipótesis A→B→C, crear sinapsis `A↔C` tipo `dmn_synthesized` con peso=0.3. La inferencia transitiva existente la propagará al índice de búsqueda.

**OPT-7: IDF dimensional en la señal #2**
Calcular qué % de nodos tiene cada dimensión. Las dimensiones raras (< 10%) deberían tener peso mayor en el coseno dimensional.

### PRIORIDAD BAJA — Experimentación controlada

**OPT-8: PPMI+SVD enriquecido con paráfrasis**
Las paráfrasis enriquecen FTS5 pero no el vector PPMI. Promediar vector principal con paráfrasis con factor 0.3.

**OPT-9: Co-activación temporal (señal nueva)**
Si dos nodos fueron accedidos en la misma sesión (ventana 30 min), crear señal de co-activación Hebbiana. Cuando uno se recupera, el otro recibe boost proporcional a `exp(-Δt/1800)`.

**OPT-10: Predicados SRL como gate condicional**
Solo activar la señal #12 cuando la query tiene estructura predicativa detectada (sujeto+verbo+objeto). Si no, peso=0.0 para no robar relevancia en queries simples.

---

## PARTE 6 — LO QUE HABRÍA QUE INVENTAR (MATEMÁTICA NUEVA)

### IDEA A: Memoria Episódica Temporal
Los sistemas de memoria humana almacenan el contexto temporal de cuándo aprendieron los hechos. Una query como "qué estaba haciendo la semana pasada" es recuperación episódica, no semántica.

**Propuesta:** Índice de episodios — clusters de nodos creados en la misma ventana temporal (sesión ± 24h). Cuando se busca con intención temporal, activar el episodio completo como unidad, no nodos individuales. El score episódico sería `coherencia_temporal × relevancia_semántica`.

### IDEA B: Score de Coherencia Narrativa
BioRAG recupera nodos individuales. Pero el conocimiento real tiene narrativa: A causa B, B permite C. Un conjunto de nodos con coherencia narrativa (cadena de predicados SRL donde objeto de A = sujeto de B) debería tener score colectivo mayor que la suma de sus partes.

**Fórmula sugerida:**
```
score_narrativa(A,B,C) = score(A) + score(B) + score(C) + 0.2 × coherencia_srl(A→B→C)
coherencia_srl = 1.0 si objeto(A) == sujeto(B) y objeto(B) == sujeto(C), 0 si no
```

### IDEA C: Umbral Adaptativo por Densidad de Corpus
Cuando el corpus crece, el umbral QCR debería ajustarse. Un corpus de 100 nodos tiene tokens únicos — QCR alto es correcto. Un corpus de 10,000 nodos tiene tokens compartidos — QCR debería ser más selectivo. El principio conforme ya hace esto para FP; aplicar el mismo principio al QCR.

---

## PARTE 7 — PLAN DE IMPLEMENTACIÓN

### Fase 1 — Conectar lo que ya existe pero está apagado (SDM)
- Tiempo estimado: 1 sesión
- Verificación: eval QA antes/después vs. snapshot
- Pasos: Fallback 2.5 → Señal #14 → medir R@5, R@1, MRR, FP

### Fase 2 — QCR ponderado por IDF
- Tiempo estimado: 1 sesión
- Pasos: calcular IDF del corpus (ya disponible en `token_freq` del índice PPMI) → reemplazar fórmula QCR → calibrar umbral

### Fase 3 — Spreading activation como señal proactiva
- Tiempo estimado: 2 sesiones
- Precaución: medir costo computacional
- Pasos: calcular score_cadena para top-50 post-FTS5 → señal 0.05 en scoring

### Fase 4 — DMN cierra el loop → sinapsis latentes
- Tiempo estimado: 1 sesión
- Pasos: en `_bucle_dmn()`, crear sinapsis `dmn_synthesized` al sintetizar hipótesis

### Fase 5 — Señales experimentales
- Método: un cambio a la vez, benchmark continuo, nunca combinar dos experimentos

---

## RESUMEN EJECUTIVO

| Categoría | Cantidad | Urgencia |
|-----------|----------|----------|
| Tecnología completamente desconectada | 1 (SDM) | ROJO — Alta |
| Tecnología parcialmente conectada | 4 (HDC, Comunidades, Marcador somático, DMN loop) | AMARILLO — Media |
| Señales subóptimas en peso/posición | 4 (JSD, SRL Predicados, Spreading activation, Dimensiones) | AMARILLO — Media |
| Mejoras matemáticas nuevas | 3 (QCR-IDF, PPMI+paráfrasis, Co-activación temporal) | VERDE — Baja |
| Inventar desde cero | 3 (Episódica temporal, Coherencia narrativa, Umbral adaptativo) | VERDE — Investigación |

**La mayor oportunidad inmediata es SDM.** El sistema ya tiene los vectores calculados y el índice mantenido. Solo falta enchufar `buscar_sdm()` al pipeline. Es tecnología de 1988 que el mundo descartó por embeddings, pero que aquí es exactamente la pieza faltante para queries vagas y semánticamente ricas sin match léxico.

**La mejora matemática más correcta es QCR-IDF.** Resuelve el problema de fondo de que tokens raros y discriminantes se traten igual que tokens comunes al decidir si un candidato pasa el filtro de cobertura.

---

*Próxima acción recomendada: Fase 1 — conectar SDM como Fallback 2.5 y Señal #14.*  
*Nunca implementar dos fases al mismo tiempo — un cambio a la vez, medido antes/después.*
