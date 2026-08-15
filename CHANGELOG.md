# BioRAG Changelog

## [Unreleased]

### Mar 11-ago-2026 — Fix: catálogo de dimensiones desincronizado + reactivación de `biorag_feedback`

**Bug reportado:** "Dimensiones inválidas" a cada rato al guardar (`aprender`) con dimensiones del system prompt.

**Causa raíz:** el `ORACLE_PROMPT` y las `description` de las tools (`recordar`, `aprender`) documentaban el catálogo de dimensiones **viejo** (75 valores: `herramienta_software`, `accion_correccion`, `cualidad_tecnica`, `qualia_agentivo`, `epistemia_directa`...). La DB real (seed v26.x en `core/memory_store.py::_asegurar_catalogo_dimensiones`) tiene **13 tipos / 102 valores con nombres distintos** (`identidad_artificial`, `accion_cognitiva`, `cualidad_abstracta_conceptual`, `telica_funcion`, `directa_experiencial`...). Todo agente que seguía la doc fallaba.

**Cambios:**
- `mcp_server.py` — 4 bloques de documentación corregidos con el catálogo real: referencia rápida del `ORACLE_PROMPT`, "LOS 13 EJES" de `recordar`, "LOS 13 EJES" de `aprender`, y el ejemplo JSON del protocolo de guardado. Se añadió aviso "⚠️ ESTE ES EL CATÁLOGO REAL".
- `mcp_server.py` — bloque `ORACLE_PROMPT` PROTOCOLO DE FEEDBACK DOPAMINÉRGICO: reescrito de 3 casos excepcionales a **5 casos accionables** (confirmación usuario, verificación test/build, uso de recuerdo recuperado en respuesta = caso más común, cierre de sesión, única excepción: duda real) y description de `biorag_feedback` actualizada para invitar al uso post-recuperación.

**Nota:** los cambios surten efecto al reiniciar el servidor MCP (el `ORACLE_PROMPT` se inyecta en cada arranque).

## v28.0 (2026-08-15)

### Canal 2 Integrado: Asociaciones Enriquecidas del Neocórtex de Sangre

**Objetivo:** llevar el Neocórtex de Sangre del blueprint (v27.0) al core de producción — el halo subconsciente (Canal 2 del manifiesto) entregado desde el grafo sináptico real sin contaminar la pureza del Canal 1.

**Cambios:**
- `core/memory_store.py` — `obtener_asociaciones_enriquecidas()`: consulta la tabla `sinapsis` real (16.121 aristas) con `LEFT JOIN` a `largo_plazo`; filtra `peso >= 0.50` (mediana real 0.72); prioriza `pmi_hebbiano`/`co_semantica`/`manual`/`latente_confirmada`; limita `sinonimo_explicito` (hiperdensa, 7.021) a 2 por nodo. **Fix de deduplicación** de aristas simétricas (`vistos_por_raiz`, conserva la de mayor peso; el grafo guarda `A→B` y `B→A` como filas independientes — 15 pares `legacy_csv`/`manual` de peso 0.5). 0 duplicados en 5 consultas verificadas.
- `mcp_server.py` — campo `asociaciones_enriquecidas` por resultado (`fuerza_arista`, `tipo_sinapsis`, `peso_vecino`, `resumen`) cuando `asociados=true`. NO toca `score_hibrido` ni el ranking.
- `core/adn_conceptual.py`, `core/neocortex_teleologico.py`, `core/hipotesis_teleologica.py`, `core/dmn_engine.py` — integración señal ADN Conceptual v29 + honestidad epistémica, **apagada por defecto** (`BIORAG_ADN_RANKING_ENABLED=false`; fórmulas `S_final_directo = 0.85·S_base + 0.15·S_adn`, `S_final_asociativo = min(0.49, 0.70·S_base + 0.30·S_adn)`). Tablas `adn_firmas` e `hipotesis_teleologicas` en `_crear_estructura_cerebral`. Marca `_adn_pendiente_recalculo` al escribir (reconstrucción batch en sueño DMN, sin inferencia en el camino caliente).
- `AGENTS.md` — verificación dual obligatoria (snapshot + copia de DB viva) antes de declarar un fix rescatado en producción (proof: 0757 rescatado en snapshot pero no en producción, fix `d6678b3`).
- `tests/test_sdm_query_by_example.py` — `test_03_bit_masking` corregido al layout SDM v2 (`SEGMENTO_*` de `core/sdm.py`: contenido 0-512, concepto 512-768, dimensiones 768-1792, categoría 1792-1920, vecinos 1920-2048; `SDM_BITS=2048`). El test viejo usaba el layout v1 (0-599/600-1023) y fallaba con `ZeroDivisionError` — preexistente al fix de Canal 2. 16/16 tests PASS.

**Hallazgos:**
- **10 tipos de aristas reales** en `sinapsis` (no 4 como sugiere `TIPOS_HOP`): sinonimo_explicito 7.021, pmi_hebbiano 2.725, co_ocurrencia 2.204, co_nombre 1.851, co_semantica 1.456, manual 705, latente_confirmada 120, legacy_csv 25, manual_v7 13, test 1 (total 16.121).
- **105 islas semánticas auto-organizadas** (kNN mutuo k=15 + LPA sobre PPMI), sanas y coherentes (mediana 15, ninguna >50). Cuello de botella del rescate: proyección de la query a la isla correcta (5/13); isla oráculo + coseno intra-isla rescata 9/13. Fase B (softmax top-3 de comunidades) **refutada** el 14/08.

**Verificación:** benchmark 921 casos contra snapshot `snapshots/qa_escape_qcr_20260811.db`: ORIGINAL == FASE A byte a byte (R@5 96.14%, R@1 88.76%, MRR 0.916, FP 25%, 34 errores) — cero regresiones. El eval no usa `asociados`, por lo que el Canal 2 no afecta el benchmark.

**Pendiente:** prueba canónica del manifiesto ("playa → piscina/mar/fotos" sin palabras compartidas); ablación OFF/ON del ADN Conceptual sobre snapshot congelado; ticket FP 25% gate QCR (queries negativas).

### Fix de dedup — aristas simétricas en asociaciones enriquecidas

**Bug:** el grafo sinapsis guarda aristas simétricas como dos filas independientes (`A→B` y `B→A`), y `obtener_asociaciones_enriquecidas()` no deduplicaba — el vecino aparecía 2 veces en el halo (detectado en `naturaleza_sistema_oec_cerebro_memoria`: `v13_4_dimensiones_en_resultados` y `principio_dimensiones_genericas_no_nicho`).

**Fix:** `vistos_por_raiz` (set por raíz) en el loop de aristas; la query ordena por `peso DESC`, así se conserva la arista de mayor peso. Commit `b3da1e0`.

**Verificado:** 0 duplicados en 5 consultas (familia 19, arquitectura 22, playa 25, memoria 19, dennys 25 items de halo). NO afecta el benchmark QA ni el ranking.

## v27.0 (2026-08-12)

### Blueprint del Neocórtex de Sangre: ADN Conceptual y Razonamiento por Esencia

**Objetivo:** documentar y congelar como blueprint la siguiente etapa de evolución de BioRAG — pasar de biblioteca estática (recuperación estadística de palabras) a cerebro vivo con **memoria genética conceptual**: cada recuerdo tiene un *ADN* (firma de esencia, no de vocabulario), y el sistema razona por esencia en vez de por coincidencia textual, formulando hipótesis teleológicas propias en reposo.

**Estado honesto:** es un **experimento en evaluación**, presentado a nadie todavía. La implementación viva (`core/memory_store.py`) NO contiene el neocórtex; el blueprint vive como copia de referencia modificada y documentación reproducible en `docs/¿Cuál es la Meta Final del Proyecto_Neocortex_nivel_2/`. La decisión de integración queda pendiente — bitácora en `EXPERIMENTS.md`.

**Contenido del blueprint (`docs/¿Cuál es la Meta Final del Proyecto_Neocortex_nivel_2/`):**
- `memory_store.py` (variante experimental, 5229 líneas, +75 vs core): fork del core con init de `NeocortexTeleologico` + `ADNConceptualEngine` y métodos `_cargar_firmas_adn()` / `_persistir_firma_adn()` para la tabla `adn_firmas`.
- `adn_conceptual.py` — motor de ADN Conceptual: infiere la firma genética (esencia) de un concepto.
- `neocortex_teleologico.py` — capa de razonamiento teleológico que vincula firmas y genera hipótesis autónomas.
- `hipotesis_teleologica.py` — generación proactiva de hipótesis por detección de "gaps genéticos".
- `dmn_engine.py` (variante modificada) — DMN con curiosidad teleológica y escaneo de gaps en reposo.
- Módulos de apoyo (copias o variantes): `auto_clustering.py`, `clasificador_wordnet.py`, `stemmer_es.py`, `ppmi_hybrid_search.py`, `dmn_reflexion.py`.
- Demos y tests: `demo_vivo_neocortex.py`, `run_adn_test.py`, `run_neocortex_test.py`, `run_teleology_test.py`, `test_neocortex_teleologico.py`, `test_sdm_completo.py`.
- Documentación: 4 documentos de arquitectura/briefing, `info.md`, `teoria_de_ejes_semanticos.md`, `slide_content.md`, `SKILL.md`, y presentación `Neocórtex de Sangre: La Evolución Genética de BioRAG.pptx`.

**Concepto central:** *"razonar por esencia, no por palabras"* — dos conceptos se relacionan si comparten genes mecánicos/abstractos (p.ej. "un error de código", "frustración" o "entropía") solo por sus firmas de ADN, sin explicación previa. Añade **honestidad epistémica** (filtro de incertidumbre: si el ADN no encaja, lanza error en vez de adivinar) y **evolución proactiva** (la memoria "sueña" y marca huecos a investigar).

### AGENTS.md — Guía de instrucciones para agentes

**Cambio:** nuevo `AGENTS.md` (152 líneas) con arquitectura del repo, comandos de corrida, evaluación QA, disciplina de snapshots, herramientas MCP, errores comunes, key files y checklist de verificación.

**Por qué:** el repo carecía de onboarding legible por máquina; cada sesión de agente re-derivaba comandos y reglas de snapshot.

### mcp_server.py — Fix de arranque: daemon en hilo de fondo

**Cambio:** en `main()`, `ensure_daemon_alive(intervalo_horas=0.5)` ahora corre dentro de un `threading.Thread(daemon=True)` con try/except interno, en vez de bloquear el hilo principal.

**Por qué:** la espera bloqueante del PID file (~5s) retrasaba el handshake MCP stdio (initialize), causando "context deadline exceeded" en el cliente. El daemon igual queda spawneado (proceso detachado).

**Archivos modificados:** `docs/.../Neocortex_nivel_2/*` (26 archivos nuevos), `AGENTS.md` (nuevo), `mcp_server.py`, `README.md`, `VERSION`, `CHANGELOG.md`.

## v26.4 (2026-08-11)

### Escape del Gate QCR con Umbral de Capa 0.60

**Problema:** el escape binario del gate QCR dejaba pasar Falsos Positivos en orígenes de capa semántica/dimensional (ratio de cobertura bajo, capa 0.25–0.33).

**Cambio en `core/memory_store.py`:** el escape de capa ya no es binario — exige `score_capa >= umbral`. Default `0.60`, configurable con `BIORAG_QCR_ESCAPE_CAPA_MIN`. Condición final: `ratio_qcr >= 0.50 OR (origen in ESCAPE_SET AND score_capa >= 0.60)`. Costo residual documentado: 2 FP (capa 0.667/1.0) aceptados — no existe señal que los separe de los TP.

**Re-run A/B real (921 casos, snapshot congelado `snapshots/qa_escape_qcr_20260811.db`):**

| Métrica | Binario | Umbral 0.6 | Δ |
|---|---|---|---|
| Recall@5 | 95.12% | 96.03% | +0.91pp |
| Recall@1 | 88.31% | 88.76% | +0.45pp |
| MRR | 0.910 | 0.916 | +0.006 |
| Errores positivas | 43 | 35 | -8 |
| FP binario (40 neg) | 10 | 10 | 0 |

**Resultado:** POSITIVO — 8 queries ganadas, 0 perdidas (todas typo/variante_gramatical), 0 TP perdidos. El umbral NO redujo los FP binarios (10→10): el gate es NO-MONOTÓNICO — si `filtrados_qcr` queda vacío, el gate se auto-desactiva y deja pasar ruido literal. Decisión pendiente sobre ruido literal en queries negativas documentada en `scripts/reporte_umbral_060_qcr_20260811.md`.

**Artefactos:** `scripts/reporte_umbral_060_qcr_20260811.md`, `scripts/run_a_baseline_escape_binario.txt`, `scripts/run_b_umbral_060.txt`, `scripts/casos_fallidos_run_a_binario.jsonl`, `scripts/casos_fallidos_run_b_umbral060.jsonl`.

**Archivos modificados:** `core/memory_store.py`, `README.md`, `VERSION`, `CHANGELOG.md`.

---

## v26.1 (2026-08-09)

### Optimización de Rendimiento: ciclo_sueno_consolidacion — 89% de reducción

**Objetivo:** Reducir el tiempo de consolidación de ~54s a niveles aceptables en laptops de usuarios, sin sacrificar la calidad del aprendizaje ni la integridad de los datos.

**Resultado:**

| Métrica | v26.0 | v26.1 | Reducción |
|---|---|---|---|
| `ciclo_sueno_consolidacion` (cold) | ~54s | ~10–12s | **78%** |
| `ciclo_sueno_consolidacion` (warm) | ~54s | **~5.8s** | **89%** |
| Búsqueda post-consolidación | — | 237–740ms | ✅ |

**Diagnóstico (cProfile sobre corpus real 257 nodos):**
El cuello de botella original era `calcular_sinapsis_latentes` consumiendo 120.9s (85% del total), dominado por 352,898 llamadas al stemmer NLTK y 176,216 llamadas a `score_pmi_nodo` por ciclo.

**Optimizaciones aplicadas:**

#### 1. `@lru_cache` en `_tokenizar` — `core/pmi_semantico.py`
Retorno de `tuple` (hashable) y cache LRU con `maxsize=8192`. Reduce 352,898 invocaciones al stemmer NLTK a ~800 únicas. **Impacto en calidad: nulo** (función determinista).

#### 2. Cache de pares en `score_pmi_nodo` — `core/pmi_semantico.py`
Dict `_score_pmi_pair_cache` a nivel de módulo: `(frozenset_q, frozenset_c) → float`. Se invalida en `recalcular()` cuando el corpus PMI cambia. **Impacto en calidad: nulo.**

#### 3. Umbral CTE configurable `BIORAG_UMBRAL_SINAPSIS_CTE=0.25` — `core/inferencia_transitiva.py`
Antes: `WHERE peso >= 0.1`. Ahora: `WHERE peso >= 0.25` (configurable). Los arcos 0.1–0.25 producen caminos con peso acumulado por debajo de `UMBRAL_MINIMO_LATENTE=0.05` y son rechazados de todas formas. **Impacto en calidad: negligible** (los latentes perdidos son los que ya se descartaban en el filtro Python).

#### 4. `max_saltos=2` en la llamada — `core/memory_store.py`
La CTE recursiva de 3 saltos genera O(N³) paths; con 2 saltos es O(N²). Justificación:
- Con `FACTOR_DECAY=0.7`, caminos de 3 saltos tienen peso máximo `0.7³ = 0.343`.
- Arcos promedio ~0.4: camino 3-hop produce `0.4³ × 0.343 = 0.022` < `UMBRAL_MINIMO=0.05` → se descartaba igual.
- Resultado: 8,106 latentes (vs 10,016 con 3 saltos) — **19% menos, los más débiles**.
- **Impacto en calidad: menor.** Conexiones de tercer grado de transitividad muy débil se pierden. Restaurable con `max_saltos=3` en máquinas más potentes.

#### 5. Selective `IndicesBioRAG` update — `core/memory_store.py`
En fold-in (1–2 nodos nuevos): actualiza `self._ppmi_index.vecs[concepto]` en RAM en vez de recargar 1,600+ vectores desde disco. Full reload solo en reindex periódico. **Impacto en calidad: nulo.**

#### 6. Cache `_obtener_pares_dimension_comun` — `core/inferencia_transitiva.py`
Caché de módulo para el JOIN `largo_plazo_dimensiones × largo_plazo_dimensiones`. Las dimensiones del ciclo actual las asigna `auto_clustering` **después** de `calcular_sinapsis_latentes`, por lo que el cache no cambia la información disponible. **Impacto en calidad: nulo.**

#### 7. Sin `_benchmark_rendimiento` en ciclo — `core/memory_store.py`
Eliminado del ciclo automático (activar manualmente con `cerebro._benchmark_rendimiento()`). Las búsquedas internas actualizaban `ultimo_acceso` y generaban ~10 commits extra. **Impacto en calidad: nulo** (función diagnóstica).

#### 8. Batch commits en `auto_vincular` — `core/sinapsis.py`
4 commits intermedios (uno por pasada) → 1 commit al final. Los mismos datos se escriben; solo cambia el boundary de transacción. **Impacto en calidad: nulo.**

#### 9. Índice cubriente `sinapsis(peso, origen, destino)` — `core/sinapsis.py`
Acelera el range scan `WHERE peso >= X` de la CTE con un índice cubriente en vez de full-scan. **Impacto en calidad: nulo** (índices no afectan datos).

#### 10. Fold-in incremental PPMI — `core/ppmi_vectorizer.py`
Nuevos nodos usan promedio IDF-weighted de tokens existentes (fold-in) en lugar de reentrenar SVD completo. Full reindex periódico cada 7 días o ≥50 nodos nuevos. **Impacto en calidad: mínimo** (aproximación corregida periódicamente).

**Variables de entorno configurables:**
```bash
# Threshold de aristas en CTE (default 0.25 laptops / 0.1 servidores)
BIORAG_UMBRAL_SINAPSIS_CTE=0.25

# Máximo saltos transitivos (memory_store.py llama con max_saltos=2 explícitamente)
# Para servidores: editar memory_store.py línea ~1920 → max_saltos=3
```

**Archivos modificados:**
- `core/pmi_semantico.py` — `@lru_cache` en `_tokenizar`, `_score_pmi_pair_cache`, invalidación en `recalcular`
- `core/inferencia_transitiva.py` — `UMBRAL_SINAPSIS_CTE`, `_pares_dim_cache`, `invalidar_cache_pares_dim()`
- `core/memory_store.py` — `max_saltos=2`, selective IndicesBioRAG update, sin `_benchmark_rendimiento`
- `core/sinapsis.py` — batch commits en `auto_vincular`, `idx_sin_peso_cobertura`
- `core/ppmi_vectorizer.py` — `fold_in_nodos()`, `_ppmi_full_reindex_due()`

---

## v26.0 (2026-08-08)

### Motor Híbrido PPMI+SVD + Retrofitting de Grafo + IDF-Synonym Specificity Scoring

**Objetivo:** Destrabar la categoría `sinonimo` y resolver el plateau de búsqueda distribucional sin modelos preentrenados ni dependencias externas de IA.

**Features Principales:**
- **PPMI+SVD (100 Dims) + Retrofitting de Grafo (Faruqui et al., 2015)**: Factorización determinista de la matriz término-documento con Smoothing $\alpha=0.75$ y Shift $k=1.0$. Ajuste geométrico de nodos mediante el grafo de sinapsis hebbianas en 5 iteraciones ($\lambda=0.2$). Cómputo de la corteza completa en $< 0.8$ segundos.
- **IDF-Synonym Specificity Scoring (Pilar 1)**: Trata la lista de sinónimos curados como una distribución TF-IDF: $\text{Score}_{\text{IDF-Sin}} = \frac{1}{\log(1 + n_{\text{sin\_nodo}})} \times \frac{1}{\log(1 + k_{\text{pool}})}$. Nodos con sinónimos específicos e intencionales se posicionan en `#1` y `#2` frente a términos omnipresentes (`perfil`, `biorag`, `identidad`).
- **Nodos & Tokens Binarios**: Tablas `tokens`, `nodos` y `meta` integradas en la base SQLite principal.
- **Modo Dual de Búsqueda (PPMI+IDF)**: Modo Sinónimo IDF para queries de 1 token; Modo Temático PPMI Coseno con vector de consulta IDF-weighted para queries de 2+ tokens.
- **Propagación Multi-Hop**: Incorpora energía de nodos vecinos de 1 salto con factor de atenuación $\text{decay}=0.4$.

**Resultados Benchmark Validado (35 casos):**
- `por_tema` top-5: **14 / 21** ✔ (Gate $\ge 10$)
- `sinonimo` top-5: **8 / 14** ✔ (Gate $\ge 6$)
- `sinonimia limpia`: **2** ✔ (Gate $\ge 1$)
- **Todos los 3 gates pasan simultáneamente por primera vez.**

### Validación sobre QA completo (921 casos, snapshot congelado — 2026-08-08)

Se validó el peso de la señal PPMI sobre `casos_qa_baseline_v1.jsonl` (921 casos, DB congelada de 803 nodos para comparación determinista):

| Métrica | OFF (0.0) | PPMI 0.10 | **PPMI 0.15 (default)** |
|---|---|---|---|
| `por_tema` R@5 | 78.46% (14 fail) | 84.62% (10) | **86.15% (9)** |
| `sinonimo` R@5 | 73.77% (16) | 83.61% (10) | **83.61% (10)** |
| GLOBAL R@5 | 95.23% | 96.59% | **96.71%** |
| GLOBAL R@1 | 86.61% | 87.74% | **88.20%** |
| FP (negativo) | 20.0% (8/40) | 22.5% (9/40) | 22.5% (9/40) |

- Diff caso-a-caso (0.15 vs OFF, mismo snapshot): **16 arreglados** (8 `sinonimo`, 4 `por_tema`, 3 `variante`, 1 `typo`) / **4 regresiones** (`0733` typo, `0750` variante, `0840` sinonimo, `0904` negativo/FP).
- **Decisión:** `BIORAG_PPMI_WEIGHT=0.15` por defecto. Sobre el QA completo, `por_tema` supera el mejor v25.2 (81.54% con Jaccard). Costo: +2.5pp FP (8→9 de 40).

---

## v25.2 (2026-08-04)

### Re-Ranking Jaccard Léxico — Activación Gradual (Cierre del Proyecto por_tema)

**Objetivo:** Rescatar candidatos correctos hundidos por señales ruidosas en el ranking base, usando coincidencia léxica jaccard como señal de matching pura.

**Features:**
- **Re-ranking jaccard condicional** (`core/memory_store.py`, Fase C): re-sort del head (`topk=20`) con `score + alpha × jaccard/max_j` (alpha=0.25), gate de activación (max jaccard ventana de 50 ≥ 0.04), y **protect-r0** (restaura a posición 0 el ítem que ocupaba la primera posición antes del re-ranking — rescata hundidos, no hunde ganadores).
- **Flag OFF por defecto** (`BIORAG_RERANKING_JACCARD_ENABLED=0`) con activación gradual monitoreada contra el benchmark — aplicando la lección de PPR.
- **Fidelidad de réplica verificada**: 921/921 rankings idénticos al experimento.

**Resultados (921 casos, corpus real 2026-08-04, peso excluido del scoring):**
- `por_tema` Recall@5: baseline real 67.69% → **81.54%** (+13.85pp)
- `por_tema` Recall@1: baseline real 60.00% → **76.92%** (+16.92pp)
- Cero regresiones en variante/PN/typo/literal; R@1 global intacto (86.38)
- Sensibilidad residual única: `sinonimo` R@5 -1 caso (id 0656, mitad A)

**Corrección de veracidad (importante):** el `84.62%` histórico de por_tema (v23.1) correspondía a un snapshot de 614 nodos con backfill parcial de predicados. El baseline real sobre el corpus actual es 67.69%. Signal #12 (predicados) queda documentada con nota de canibalización — su backfill completo canibaliza la señal; queda como capacidad disponible no enganchada.

**Archivos modificados:**
- `core/memory_store.py` — `_rerank_jaccard_protect_r0`, constantes `RERANKING_JACCARD_*`, llamada condicional en `buscar_por_frase`, nota de canibalización Signal #12
- `EXPERIMENTS.md` — bitácora de hipótesis probadas/descartadas (nuevo)
- `README.md` — benchmark v25.2 corregido, env vars del re-ranking, badge DOI Zenodo
- `.env.example` — variables del re-ranking jaccard

**Protocolo de cierre:** activación con `BIORAG_RERANKING_JACCARD_ENABLED=1` y monitoreo del benchmark con atención específica a la categoría `sinonimo` durante los primeros días. Si `sinonimo` se mantiene estable → cierre definitivo del proyecto.

**Changelog científico (ver EXPERIMENTS.md):**
| Hallazgo | Veredicto |
|---|---|
| PPR (Diffusion of Heat): 0% ganancia honesta, +100–190ms | Descarta do (v25.1) |
| FCA (Reticulados de Galois): frecuencia ≠ semántica, sin clusters coherentes | Descarta do (v25.1) |
| Boost dimensional: techo estructural de discriminación | Descarta do (v25.0–v25.1) |
| SDM segmento de dimensiones: multi-proyección K regresa recall | Revertido (v25.1) |
| Signal #12 (predicados): +13.85pp era snapshot parcial; backfill completo canibaliza | Desenganchado (v25.2) |
| Re-ranking jaccard: +13.85pp por_tema, holdout 50/50 sostiene | **Integrado** (v25.2) |

## v25.1 (2026-08-03)

### HDC Binding y Multi-Proyección SDM — Confiabilidad y Precisión de Representación

**Objetivo:** Eliminar colisiones de hash en la generación de vectores SDM mediante multi-hashing con semillas independientes, e integrar una capa de Computación Hiperdimensional (HDC) para representación estructurada de predicados.

**Features:**
- **Multi-proyección SDM** (`core/sdm.py`): `_hash_token_a_bit` ahora acepta parámetro `seed` para hashing independiente. Nueva función `_activar_proyecciones` activa k posiciones de bits independientes por token. Reemplaza hash único + ventana contigua en segmentos de contenido (k=4), concepto (k=4), categoría (k=8) y vecinos sinápticos (k=4). Segmento de dimensiones conserva ventana contigua por regresión de recall medido (54.3%→43.1%).
- **HDC Binding** (`scripts/hdc_binding.py`): Operaciones núcleo de HDC — `generar_rol`, `item_denso_desde_string` (SHA256 i.i.d. p=0.5 por bit), `densificar`, `xor`, `majority_vote`, `sim_ham`, `bind`, `unbind`, `recuperar_rol`. Acierto 38/38 en predicados reales, 10/10 en stress test de conceptos versionados.
- **Reindexación automática SDM** (`core/dmn_reflexion.py`): 5 hooks que reindexan vectores SDM tras mutaciones del grafo — `_reindexar_sdm` en `_aplicar_veredicto`, `_restaurar_cuarentena`, `_aplicar_veredicto_nodo`, `procesar_nodo_unico`, `ejecutar_ciclo_reflexivo`.
- **Scripts de verificación**: `medir_hdc_margen_pares_duros.py`, `medir_hdc_predicados_reales.py`, `medir_rangos_hamming_sdm.py`, `test_hdc_binding_sintetico.py`, `test_hdc_stress_versionado.py`, `verificar_fallback18_queries_cortas.py`, `verificar_hdc_hash_no_colisiona.py`.

**Resultados:**
- Colisiones Fallback 1.8: 0 en 89,676 pares (antes: 182 colisiones, 0.203%)
- HDC binding: acierto 100% (38/38 predicados reales), separación media 0.128→0.144
- Stress test: 10/10 conceptos versionados (antes: 9/10 con hash viejo)
- Fallback 1.8 queries cortas: 0 colisiones en 1,653 pares query×query y 40,890 pares query×nodo

**Archivos modificados:**
- `core/sdm.py` — multi-proyección K con seed, `_activar_proyecciones`
- `core/dmn_reflexion.py` — 5 hooks de reindexación SDM
- `mcp_server.py` — rutas corregidas para scripts de notebooks
- `scripts/hdc_binding.py` — primitivas HDC (nuevo)
- `scripts/medir_hdc_margen_pares_duros.py` — medición margen HDC (nuevo)
- `scripts/medir_hdc_predicados_reales.py` — evaluación HDC en predicados reales (nuevo)
- `scripts/medir_rangos_hamming_sdm.py` — recalibración rangos Hamming (nuevo)
- `scripts/test_hdc_binding_sintetico.py` — prueba sintética HDC (nuevo)
- `scripts/test_hdc_stress_versionado.py` — stress test conceptos versionados (nuevo)
- `scripts/verificar_fallback18_queries_cortas.py` — verificación colisiones Fallback 1.8 (nuevo)
- `scripts/verificar_hdc_hash_no_colisiona.py` — verificación reducción colisiones (nuevo)
- `.gitignore` — artefactos temporales de scripts

## v25.0 (2026-07-31)

### Expansión Dimensional: 13 Ejes Semánticos (7 → 13, 73 → 102 sub-valores)

**Objetivo:** Cerrar los huecos estructurales del catálogo dimensional detectados por dos análisis independientes —evidencialidad (cómo se sabe) y modalidad deóntica (qué se debe/puede)— y enriquecer la discriminación semántica con ejes genéricos de la información.

**Features:**
- **Catálogo expandido 7 → 13 ejes, 73 → 102 sub-valores** en `core/memory_store.py` (`_asegurar_catalogo_dimensiones`)
- **6 ejes nuevos:** cualia (4), epistemia (6), escala_abstraccion (5), centralidad_identitaria (5), textura_experiencial (5), modalidad (4)
- **Siembra idempotente**: INSERT OR IGNORE por nombre — corre en DB nueva y existente sin duplicar, con backup pre-migración
- **Verificación**: DB limpia 13/102 ✓, re-siembra idempotente ✓, DB real migrada 13/104 ✓
- **Principio de dimensiones genéricas**: dimensiones = características de cualquier información, no taxonomía del sistema (se rechazaron ejes de auto-descripción tipo agencia/alcance/ubicación)

**Referencias teóricas:**
- Evidencialidad — Aikhenvald (2004)
- Modalidad deóntica — Palmer (2001)
- Generative Lexicon / cualia — Pustejovsky (1995)
- Self-reference effect — Rogers et al. (1977)
- Experiencia de flujo — Csikszentmihalyi

**Archivos modificados:**
- `core/memory_store.py` — seed ampliado + `_asegurar_catalogo_dimensiones` idempotente
- `README.md` — documentación v25.0 con fundamento científico
- `VERSION` — v25.0

**Nota de tests:** 116/117 pasan. Test 83 (`test_memory.py:1609`, búsqueda SRL por rol `sujeto:Artemis`) falla **de forma preexistente** — verificado también con `memory_store.py` en estado HEAD sin cambios v25.0. No es regresión de esta versión.

## v24.1 (2026-07-27)

### La Hormiguita — Sistema de Mantenimiento Seguro y Automedible

**Objetivo:** Proteger el grafo contra degradación con cuarentena, benchmark gate, two-strike pruning, batching con resume y pre-filter opcional.

**Features:**
- **Cuarentena de sinapsis** (`sinapsis_cuarentena`): soft-delete reversible por 30 días. Sinapsis eliminadas van a cuarentena, restaurables con `restaurar_cuarentena()`
- **Benchmark gate**: Mini-eval automática de 40 casos cada 25 nodos. Si recall cae >2.0 pts → auto-restaurar cuarentena + alertar. Baseline: 80.0% (32/40 positivos)
- **Two-strike pruning** (latentes): strike 1 = attenuate (peso×0.5), strike 2 = cuarentena. conf≥0.90 = cuarentena directa. "confirmar" resetea strikes
- **Batching con resume**: `TAMANO_LOTE_SINAPSIS=10` sinapsis por llamada a Gemini. Estado persistido después de cada lote. Resume exacto tras crash
- **Pre-filter opcional**: `BIORAG_HORMIGA_PRE_FILTRO=0` por defecto. Gemini juzga TODAS las sinapsis con contenido completo. Pre-filtrado determinista opcional para ahorrar tokens
- **Anti-over-pruning floor**: `MIN_CONEXIONES_POR_NODO=5` — corte diferido cuando nodo llega al mínimo
- **WAL mode + busy_timeout=5000**: SQLite permite lectores paralelos + 1 writer en ext4 local
- **Tablas nuevas**: `sinapsis_cuarentena` con índices en origen + timestamp; `strikes` en `sinapsis_latentes`
- **Herramientas MCP**: `hormiguita` (con `max_nodos`, `nodo_especifico`) y `hormiguita_estado`
- **Daemon wrapper**: `graph_maintenance_daemon.py` — lock file, scheduler, resume, CLI (--once/--status/--reset)

**Archivos modificados:**
- `core/dmn_reflexion.py` — batching, cuarentena, benchmark gate, two-strike, pre-filter opcional
- `mcp_server.py` — herramientas hormiguita y hormiguita_estado
- `graph_maintenance_daemon.py` — daemon wrapper (nuevo)

**Constants configurables via env:**
- `BIORAG_HORMIGA_LOTE_SINAPSIS`, `BIORAG_HORMIGA_MIN_CONEXIONES`
- `BIORAG_HORMIGA_BENCHMARK_CADA_N`, `BIORAG_HORMIGA_BENCHMARK_TOLERANCIA`
- `BIORAG_HORMIGA_PRE_FILTRO`, `BIORAG_HORMIGA_UMBRAL_LATENTE_DIRECTO`
- `BIORAG_HORMIGA_RETENCION_CUARENTENA_DIAS`, `BIORAG_HORMIGA_PESO_ATENUACION`

---

## v24.0 (2026-07-27)

### La Hormiguita — Grafo Maintenance Daemon con Gemini AI

**Objetivo:** Daemon background que valida y poda conexiones del grafo usando Gemini como juez experto.

**Implementación:**
- `core/dmn_reflexion.py`: `_reflexionar_nodo()` — batched Gemini evaluation, pre-filtering determinista
- `graph_maintenance_daemon.py`: daemon con lock, scheduler, resume
- MCP tools: `hormiguita` y `hormiguita_estado`
- Pre-filtrado: redujo 1173 candidates a 60 para Gemini (verificación en `biorag_v21_hypothesis_natural_selection`)
- Primer ciclo exitoso: 15 nodos → 24 sinapsis eliminadas, 0 huérfanos

## v23.1 (2026-07-26)

### Predicados SRL + Feedback-Driven Graph Learning

**Objetivo:** Mejorar `por_tema` mediante señales específicas que capturen el contenido real del nodo, y hacer que el grafo aprenda con el uso real.

### Feature 1: Predicados SRL como Signal #12

**Implementación:**
- `scripts/backfill_predicados.py`: Backfill de keyword predicates para todos los nodos (5.6%→100% cobertura)
- Extracción de keywords técnicos del contenido (top50 por nodo)
- Integración como signal #12 en `_calcular_score_hibrido()` con peso configurable
- Precomputación de `pred_contexto_map` en `buscar_por_frase()` para O(1) lookup

**Ablation (pesos0.01→0.25, snapshot congelado,921 test cases):**

| Peso | por_tema R@5 | por_tema R@1 | GLOBAL R@5 | FP |
|------|-------------|-------------|------------|-----|
|0.00 (baseline) |70.77% |35.38% |96.25% |7.50% |
|0.04 |76.92% |38.46% |96.59% |7.50% |
|0.10 |78.46% |49.23% |97.05% |7.50% |
|0.15 |81.54% |55.38% |97.28% |7.50% |
|**0.20** |**84.62%*** |**58.46%** |**97.05%** |**7.50%** |
|0.25 |84.62%* |58.46% |97.28% |10.00% ❌ |

> \* ⚠️ Snapshot con backfill parcial de predicados (614 nodos) — el baseline real sobre el corpus actual (921 casos) es 67.69%. Ver Corrección de veracidad (sección v25.2).

**Peso óptimo:0.20** — por_tema Recall@5 +13.85pp, Recall@1 +23.08pp, FP sin regresión.

**Determinismo:** por_tema (84.62%*/58.46%) y FP (3/40=7.50%) idénticos en2 corridas. GLOBAL variación±0.11pp por estado de DB durante sesión.

### Feature 2: Feedback-Driven Graph Learning

**Implementación:**
- `_evocacion_por_cadena` ahora devuelve `parent_map` — diccionario `{nodo: (padre, peso_arista)}` para rastrear caminos de spreading activation
- `aplicar_refuerzo_dopaminergico` cuando `exito=True`: fortalece aristas del camino exacto con LTP asintótico (`peso += 0.05*(1-peso)`)
- `_reconstruir_camino` traza el camino desde la semilla hasta el nodo exitoso
- Reset de `parent_map` entre queries para evitar acumulación

**Diseño:** Solo refuerzo positivo (no atribución de culpa). Decay multiplicativo (`peso*=0.95` para aristas no usadas en7+ días) debilita naturalmente los caminos no reforzados.

**Ablation:** Parent pointers es100% inocuo — números idénticos sobre misma DB congelada.

**Alcance real:** Spreading activation se activa en SOLO21/921 queries (2.3%). Por categoría: literal13, negativo2, por_tema2, sinonimo3, typo2, variante_gramatical1. Es un mecanismo de nicho, no central — pero potencialmente significativo en los casos más difíciles de por_tema.

### Experimentos rechazados (documentados)

**JSD (Signal #11):** -0.34pp GLOBAL, -1.53pp por_tema. Señales distribucionales perjudican queries genéricas. Código queda desactivado (`JSD_WEIGHT=0.0`).

**Bayesian BM25:** -12.83pp GLOBAL, -63.08pp por_tema (regresión catastrófica). El error fue el `abs()` sobre scores negativos de FTS5, no la idea de calibrar probabilísticamente. Código queda desactivado (`BAYESIAN_BM25=false`).

### Principio generalizable

"Señales que miden similitud distribucional/genérica tienden a perjudicar queries cortas y ambiguas porque homogeneizan candidatos que las señales específicas (BM25, concepto_ratio) ya distinguían bien." — Los4 experimentos negativos de la semana (content_ratio, eco sináptico, JSD, Bayesian BM25) comparten este patrón.

### Baselines v23.1 (DB614 nodos,2026-07-26)

| Métrica | v23.0 (593 nodos) | v23.1 (614 nodos) | Nota |
|---------|-------------------|-------------------|------|
| por_tema Recall@5 |70.77% |81.54% |+10.77pp (predicados SRL) |
| por_tema Recall@1 |40.00% |56.92% |+16.92pp |
| GLOBAL Recall@5 |95.91% |96.82% |+0.91pp |
| FP |7.50% |7.50% |sin regresión |

**Nota:** Los números de v23.1 no son directamente comparables con v23.0 — el corpus creció de593 a614 nodos (crecimiento orgánico + backfill de predicados).

### Archivos modificados
- `core/memory_store.py`: Signal #12 (pred_score), parent pointers, refuerzo LTP
- `scripts/backfill_predicados.py`: Nuevo — backfill de keyword predicates
- `scripts/evaluar_qa.py`: Tracking de spreading activation
- `test_memory.py`: Actualizado para parent pointers
- `CHANGELOG.md`, `VERSION`: Actualizados

---

## v23.0 (2026-07-26)

### Rebalanceo de Señales de Scoring para por_tema + Fix FTS5 Hyphens

**Problema:** `por_tema` con 58.46% seguía siendo la categoría más débil (78–100% el resto). Las causas identificadas en auditoría de 50 casos fallidos:
1. **44%** gap de vocabulario — query words no presentes en contenido ni sinónimos del nodo
2. **33%** queries genéricas con muchos competidores
3. **11%** crashes de FTS5 por sintaxis de guiones (hyphens)
4. El problema no es retrieval (FTS5 OR encuentra targets en pos 1-6), sino scoring (pipeline híbrido los baja)

**Solución — Part 1: Fix FTS5 Hyphens:**
- `_fts_safe_term()` y `_fts_safe_phrase()` en `buscar_por_frase()` para dividir tokens con guiones
- Corregidos 5 crashes de FTS5 ("no such column") en búsquedas con guiones

**Solución — Part 4: Rebalanceo de Pesos (Ablation en Snapshot):**
- `bm25_norm`: 0.18 → **0.25** (+38.9%) — BM25 es la señal más informativa para por_tema
- `concepto_ratio`: 0.12 → **0.08** (-33.3%) — match en nombre no discriminaba lo suficiente
- `sinonimos_ratio`: 0.12 → **0.08** (-33.3%) — misma razón que concepto_ratio
- Snapshot congelado en `snapshots/before_part4_weight_adjustment.db` para reproducibilidad

**Resultados — Ablation completa (snapshot frozen, 3 corridas idénticas):**

| Métrica | v22.2 (antes) | **v23.0 (después)** | Delta |
|---|---|---|---|
| por_tema Recall@5 | 58.46% | **70.77%** | **+12.31 pp** |
| por_tema Recall@1 | 20.00% | **40.00%** | **+20.00 pp** |
| GLOBAL Recall@5 | 95.01% | **95.91%** | +0.90 pp |
| NEGATIVO FP | 7.50% | 7.50% | sin regresión |

**Experimentos documentados que NO funcionaron:**
- Sinónimos ciegos (TF-IDF, frecuencia, content-relevant) — mejoraban solo cuando query compartía vocabulario con contenido
- Sinónimos manuales del query — circular (pos 8→1 pero no generalizable)

**Lección de Arquitectura:**
- El problema de por_tema no es retrieval sino scoring. FTS5 OR encuentra el target en pos 1-6 para la mayoría de casos. El rebalanceo de pesos reordena correctamente.
- `oracle_custom_prompt_arsitecura_que_funciona` permanece fuera de top-5 — requiere predicates/SRL, no pesos.

**Archivos modificados:**
- `core/memory_store.py`: Fix FTS5 hyphens + pesos en `_calcular_score_hibrido()`
- `scripts/evaluar_qa.py`: Metodología de ablation con snapshot
- `snapshots/before_part4_weight_adjustment.db`: Snapshot frozen para reproducibilidad

---

### Experimento JSD (Signal #11) — RECHAZADO

**Hipótesis:** JSD (Jensen-Shannon Divergence) como signal #11 de scoring mediría solapamiento distribucional entre query y nodo, complementando BM25 (que mide relevancia por IDF).

**Implementación:**
- `_calcular_jsd()` en `core/memory_store.py:2504` — distribuciones de frecuencia de palabras, Laplace smoothing, `1 - sqrt(JSD)` como score [0,1]
- `_calcular_score_hibrido()` acepta `jsd_score` + `jsd_weight` — weight default=0.0 (zero overhead: `_calcular_jsd()` solo se ejecuta si `JSD_WEIGHT > 0.0`)
- Configurable vía env var `BIORAG_JSD_WEIGHT`

**Protocolo:** Snapshot DB actual (605 nodos), 921 test cases, ablation peso 0.0 vs 0.05.

**Resultados:**

| Métrica | JSD=0.0 | JSD=0.05 | Delta |
|---------|---------|----------|-------|
| GLOBAL Recall@5 | 96.14% | 95.80% | **-0.34pp** |
| GLOBAL Recall@1 | 88.65% | 88.20% | **-0.45pp** |
| por_tema Recall@5 | 75.38% | 73.85% | **-1.53pp** |
| FP | 7.50% | 7.50% | 0.00 |

**Causa raíz:** JSD mide solapamiento distribucional — para queries genéricas ("perfil", "memoria", "arquitectura"), muchos nodos tienen distribuciones similares → JSD empata scores que BM25/dim_score distinguían → nodos genéricos suben, específicos bajan.

**Principio generalizable (regla de diseño):** Señales que miden similitud distribucional/genérica tienden a perjudicar queries cortas y ambiguas porque homogeneizan candidatos que las señales específicas (BM25, concepto_ratio) ya distinguían bien. Cualquier señal candidata debe evaluarse contra queries genéricas — no solo contra las específicas donde funciona.

**Baselines post-JSD (DB 605 nodos, 2026-07-26):**
- GLOBAL Recall@5: 96.14% | FP: 7.50%
- por_tema Recall@5: 75.38% | Recall@1: 35.38%
- **Nota:** Estos números no son directamente comparables con los 70.77% del v23.0 original (medidos sobre corpus de ~593 nodos). El crecimiento de 593→605 nodos es crecimiento orgánico del corpus, no mejora de código. Leer como "evolución natural del corpus", no como mejora de algoritmo.

---

### Experimento Bayesian BM25 (Calibración Sigmoid) — RECHAZADO

**Hipótesis:** Bayesian BM25 (`sigmoid(α(s-β))`) reemplazaría la normalización fija `abs(x)/(abs(x)+3)` con calibración probabilística, mejorando la mezcla de BM25 con otras señales en `_calcular_score_hibrido()`.

**Implementación:**
- `_calcular_bm25_bayesiano()` en `core/memory_store.py` — sigmoid con β=mediana×0.7 estimado del corpus
- Env vars: `BIORAG_BAYESIAN_BM25=true/false`, `BIORAG_BAYESIAN_BM25_ALPHA=1.0`
- Reemplaza normalización en buscar_por_frase (línea 3695) y rafaga (línea 4204)

**Protocolo:** Snapshot DB actual (605 nodos), 921 test cases.

**Resultados:**

| Métrica | Baseline | Bayesian α=1.0 | Delta |
|---------|----------|----------------|-------|
| GLOBAL Recall@5 | 96.14% | 83.31% | **-12.83pp** |
| GLOBAL Recall@1 | 88.20% | 76.28% | **-11.92pp** |
| por_tema Recall@5 | 73.85% | 10.77% | **-63.08pp** |
| FP | 7.50% | 7.50% | 0.00 |

**Causa raíz:** BM25 de FTS5 produce scores **negativos** (más negativo = mejor match). La implementación aplicaba `abs(raw)` antes de la sigmoid, lo que invertía el signo real del score — literalmente daba vuelta el ranking, tratando los documentos menos relevantes como más relevantes.

**Corrección importante:** El error fue el `abs()`, NO la idea de calibrar probabilísticamente. Bayesian BM25 con FTS5 requiere manejar los scores negativos correctamente antes de aplicar sigmoid. Si alguna vez se retoma, el punto exacto a corregir es: aplicar sigmoid directamente al score crudo negativo (sin abs), o negar el score antes de la sigmoid.

**Lección:** Bayesian BM25 está diseñado para fusionar BM25 con vectores densos en hybrid search. En BioRAG (sin vectores densos), la calibración no aporta valor y destruye el ranking. La fórmula `abs(x)/(abs(x)+3)` es monotónica y funcional — NO necesita calibración probabilística.

**Código revertido:** `_calcular_bm25_bayesiano()` queda implementado pero desactivado. Config `BAYESIAN_BM25` default=false.

---

### Predicados SRL como Signal #12 — APROBADO

**Hipótesis:** Los predicados SRL (keywords extraídos del contenido de cada nodo) proporcionarían una señal específica que captura el contenido semántico del nodo, complementando BM25 y dimensiones.

**Implementación:**
- `scripts/backfill_predicados.py`: Backfill de keyword predicates para todos los nodos (5.6%→100% cobertura)
- Extracción de keywords técnicos del contenido (top50 por nodo)
- Integración como signal #12 en `_calcular_score_hibrido()` con peso configurable
- Precomputación de `pred_contexto_map` en `buscar_por_frase()` para O(1) lookup

**Protocolo:** Snapshot DB actual (609 nodos),921 test cases, ablation con pesos0.01→0.04→0.06→0.08→0.10→0.12→0.15→0.20→0.25.

**Resultados (peso óptimo:0.20, verificado con2 corridas idénticas):**

| Métrica | Baseline | Con Predicados | Delta |
|---------|----------|----------------|-------|
| GLOBAL Recall@5 |96.25%|97.05%|**+0.80pp** |
| GLOBAL Recall@1 |88.08%|91.15%|**+3.07pp** |
| por_tema Recall@5 |70.77%|84.62%*|**+13.85pp** |
| por_tema Recall@1 |35.38%|58.46%|**+23.08pp** |
| FP |7.50%|7.50%|0.00 |

**Determinismo:** por_tema (84.62%*/58.46%) y FP (3/40=7.50%) idénticos en2 corridas. GLOBAL variación±0.11pp por estado de DB durante sesión.

> \* ⚠️ Snapshot con backfill parcial de predicados — valor no representativo del corpus real (baseline real `por_tema`: 67.69%).

**Peso0.25 causó FP+2.50pp (10.00%) — rechazado.**

**Causa raíz:** El problema de por_tema no era retrieval sino scoring — los nodos específicos tenían el mejor BM25 pero eran penalizados por bajo peso sináptico y pocas dimensiones. Los predicados proporcionan una señal adicional que captura el contenido semántico del nodo, permitiendo que nodos específicos con contenido relevante pero pocas dimensiones sean mejor rankeados.

**Lección:** La clave no era agregar más señales genéricas sino agregar señales ESPECÍFICAS que capturen el contenido real del nodo. Los predicados son específicos porque extraen keywords únicos de cada nodo, no distribuciones compartidas.

---

## v22.2 (2026-07-24)

### Capa 3: Pseudo-Relevance Feedback Dimensional & Normalización Metodológica de QA

**Problema:** El evaluador externo (MiMo) identificó 3 capas afectando por_tema:
1. **Capa 1:** `tematico_score` compara candidatos entre sí, no contra la query
2. **Capa 2:** `similitud_tematica` no discriminativa — mantenida limpia con dimensiones sueltas
3. **Capa 3 (NUEVA - v22.2):** La query no tiene dimensiones explícitas — se inyectan dinámicamente vía PRF
4. **Drift Metodológico de LTD (Págs 43-44 PDF):** 51 de 65 nodos objetivo en `por_tema` sufrieron decaimiento pasivo LTD ($W \le 0.30$) por falta de valencia somática, distorsionando el score híbrido.

**Solución Capa 3 (Pseudo-Relevance Feedback) + Fix Metodológico Validado:**
- **PRF:** Cuando `buscar_por_frase` no recibe `dimensiones_ids` explícitos pero la query tiene ≥3 resultados FTS5, usa los **top-5 resultados FTS5 puros** como "pseudo-relevantes" para inyectar sus dimensiones implícitas.
- **Fix Metodológico Riguroso en `evaluar_qa.py`:** Se normalizan **TODOS los nodos** a $W = 1.00$ globalmente antes de cada corrida (`UPDATE largo_plazo SET peso_sinaptico = 1.0` — sin filtro WHERE). Ningún nodo recibe ventaja exclusiva sobre los distractores (zero data leakage).
- **Fix de Robustez:** `_crear_tabla_historial_si_falta()` garantiza existencia de `nodos_sdm` y `sinapsis_latentes` antes de cualquier `DELETE` trigger.

**Resultados Definitivos y Validados — Determinísticos (3 corridas idénticas, 58.46% estable):**

#### Comparativa de Evolución de `por_tema`
| Métrica | Antes (v18.0 - v21.0) | Con Ruidos de LTD (baseline ruidoso) | v22.2 Validado (verificado determinista) | Estado |
|---|---|---|---|---|
| **Recall@5** | 36.92% | 41.54% | **58.46%** | 🚀 **+21.54 pp** |
| **Recall@1** | 12.31% | 16.92% | **20.00%** | 📈 **+7.69 pp** |
| **MRR** | 0.213 | 0.250 | **0.344** | 📈 **+0.131** |

#### Desglose por Categoría de Recuperación (corrida determinista, 3 repeticiones idénticas)
- `dormido`: **100.00%** Recall@5 (MRR 1.000) — 0 fallos
- `literal`: **100.00%** Recall@5 (MRR 0.999) — 0 fallos
- `typo`: **98.46%** Recall@5 (MRR 0.926) — 1 fallo
- `variante_gramatical`: **96.92%** Recall@5 (MRR 0.910) — 2 fallos
- `pregunta_natural`: **93.85%** Recall@5 (MRR 0.913) — 4 fallos
- `cruce_idioma`: **87.50%** Recall@5 (MRR 0.875) — 1 fallo
- `sinonimo`: **78.69%** Recall@5 (MRR 0.581) — 13 fallos
- `por_tema`: **58.46%** Recall@5 (MRR 0.344) — 27 fallos

> **GLOBAL SUMMARY (881 casos):** Recall@5: **94.55%** | Recall@1: **87.74%** | MRR: **0.902** | FP Negativo: **7.5%** (3/40, baseline histórico)

> **Determinismo verificado:** 3 corridas consecutivas idénticas (con y sin PYTHONHASHSEED=0) → **58.46% exacto**. Sin varianza.

**⚠️ Deuda técnica pendiente:** Variación puntual 61.54% → 58.46% observada en corrida aislada previa; 4 corridas consecutivas confirman 58.46% determinista, pero **causa raíz de la variación aislada no identificada** (descartado PYTHONHASHSEED, DMN inactivo). Pendiente: investigación completa (DMN hilo latente, orden de iteración dict/set en Python 3.7+, interacción con caché temática) para garantía bajo carga/distinto orden de casos.

**Lección de Arquitectura Documentada:**

- **Tests Biológicos:** 112/112 pasados con 100% de éxito ✓

**Lección de Arquitectura Documentada:**
- **¿Por qué `query_dimension_classifier.py` (WordNet) falló para dimensiones sintéticas?** WordNet clasifica 45 categorías lexicográficas generales (`noun.artifact`, `verb.communication`) pero no puede inferir dimensiones sintéticas de dominio (`identidad_artificial`, `intencion_documentar`, `dominio_tecnico`). PRF las extrae dinámicamente del corpus en tiempo de consulta.
- **Causa raíz del decaimiento LTD:** Nodos sintéticos creados sin valencia somática ($V_s = 0.0$) decayeron $-0.05$ por ciclo de sueño. Fix: todos los nodos arquitectónicos críticos deben tener $V_s \ge 0.80$.

**Archivos modificados:**
- `core/memory_store.py`: Inyección PRF en Capa 3 + fix de tablas en `_crear_tabla_historial_si_falta()`
- `scripts/evaluar_qa.py`: Normalización global de pesos (zero data leakage)
- `CHANGELOG.md`, `README.md`, `VERSION`: Documentación de resultados validados

---

## v22.1 (2026-07-24)

### Fix: Scoring Híbrido — Rebalanceo de Pesos para por_tema
- **Problema:** `concepto_ratio` (match en nombre del nodo, peso 0.16) dominaba la fórmula de scoring. Un nodo con la palabra del query en su nombre ganaba sobre el nodo correcto con mejor BM25 pero nombre diferente. BM25 rankeaba el nodo esperado en posición 4, pero la fórmula híbrida lo empujaba hacia abajo.
- **Fix:** Rebalanceo de pesos en `_calcular_score_hibrido()`: `bm25_norm` 0.14→0.18, `concepto_ratio` 0.16→0.12.
- **Resultado por_tema:** Recall@5: 36.92% → 43.08% (+6.16%), Recall@1: 12.31% → 20.00% (+7.69%).
- **Resultado global:** GLOBAL Recall@5: 92.96% → 93.64% (+0.68%). Negativo FP: 12.5% → 7.5% (-5.0%).
- **Archivos modificados:** `core/memory_store.py` (pesos en `_calcular_score_hibrido()`), `VERSION`, `README.md`, `CHANGELOG.md`.
- **Validación:** Suite de 921 casos de prueba (881 recuperación + 40 ruido). Ninguna categoría empeoró.

### Experimentos que NO funcionaron (documentados)
- **content_ratio como señal #11:** Agregar `content_ratio` (fracción de palabras del query en contenido) como undécima señal emporó por_tema de 36.92% a 35.38%. El problema: boosteaba todos los nodos con palabras del query en contenido por igual, ahogando el nodo esperado. Revertido.

---

## v22.0 (2026-07-23)

### Features & Architecture
- **SDM Query-by-Example (`core/sdm.py`)**: `buscar_sdm()` ahora acepta `vector_fijo` (bytes) como parámetro opcional. Cuando se proporciona, usa ese vector en vez de generar uno desde texto. Esto habilita "buscar nodos similares a ESTE nodo" — búsqueda semántica pura por Hamming distance.
- **`buscar_similares_a(cerebro, concepto_semilla)`**: Función de conveniencia que toma el vector SDM de un nodo conocido y retorna los nodos más cercanos. El SDM funciona como base vectorial ligera (128 bytes/nodo, 0 GPU, SQLite puro).
- **Validación empírica completa**: Tests con sinónimos técnicos (bug↔error: 5 bits), abreviaturas (DB↔base de datos: 7 bits), cross-domain (base_de_datos↔cache: 9 bits), y query-by-example real sobre 570 nodos (5/5 semillas con hits).
- **Pipeline de búsqueda enriquecido**: Capa SDM query-by-example como fallback cuando FTS5 y dimensiones no encuentran suficientes candidatos. Scoring híbrido incorpora similitud SDM como señal adicional.

### Tests
- Suite ampliada a 117/117 tests biológicos aprobados (100% Éxito) ✓
- Tests SDM: sinónimos técnicos, abreviaturas, cross-domain, query-by-example real

---

## v21.0 (2026-07-23)

### Features & Architecture
- **Default Mode Network (DMN) & Motor de Curiosidad Espontánea (`core/dmn_engine.py`)**: Hilo autónomo en segundo plano (`DMNEngine`) para ideación espontánea (mind-wandering) en periodos de inactividad del usuario, 100% libre de dependencias nativas externas.
- **Interrupción de Latencia Cero (`threading.Event()`)**: Interrupción inmediata del hilo autónomo DMN al recibir actividad del usuario para garantizar 0% de latencia en la atención de consultas.
- **Muestreo Resonante Cortical (Spindles Replay)**: Selección de nodos ancla de alta valencia/peso y exploración latente a 2-3 saltos para sintetizar "Insights" autónomos.
- **Concurrencia Aislada Thread-Local**: Conexión SQLite aislada por hilo en modo WAL con `PRAGMA busy_timeout = 5000`.
- **Selección Natural de Hipótesis (Decaimiento LTD Pasivo)**: Insights autónomos generados con peso inicial $W=0.50$ y valencia protegida $V_s=0.85$, sujetos a decaimiento pasivo por sueño si no reciben atención futura.
- **Presupuesto de Energía & Período Refractario**: Límite de máximo 3 ideas por ciclo de reposo con 60s de enfriamiento.
- **Integración MCP & Neuro-Visor Backend**: Herramienta `biorag_estado_dmn` y endpoint HTTP `/api/corteza/dmn`.
- **Suite de Pruebas Biológicas**: Ampliada a **112/112 pruebas biológicas aprobadas con éxito (100%)**.

---

## v20.0 (2026-07-22)

### Features & Architecture
- **Inhibición Lateral GABA en Tiempo Real en Evocación (Edelman 1987)**: Atenuación dinámica ($\times 0.60$) de competidores semánticos secundarios cuando el nodo Top-1 domina ($\ge 0.80$).
- **Error de Predicción de Recompensa Dopaminérgica (Dopamina RPE - Schultz 1997) con Factor de Inercia Sináptica**: Modulación de peso vía `biorag_feedback` ($\Delta W = +0.15$ en éxitos, depresión ajustada por inercia histórica en fallos).
- **Marcadores Somáticos e Inmunidad Cortical por Valencia (Damasio 1994)**: Columna `valencia_somatica` (0.0 a 1.0) con inmunidad absoluta a decaimiento LTD y borrado para nodos con valencia $\ge 0.80$ o categorías axiomáticas (`Principle`, `Protocol`).
- **Escalado Sináptico Homeostático (Turrigiano 2008)**: Normalización multiplicativa ($\times 0.98$) durante el sueño cuando la energía activa promedio supera $0.70$.

---

## v18.2 (2026-07-20)

### Features & Robustness
- **Neuro-Visor Dashboard v2 — Página Salud (Graph Health Audit)**: Health Score (0-100), breakdown por severidad (crítico/advertencia/ok), auditoría completa de integridad referencial, aislamiento semántico, dimensiones inactivas, nodos huérfanos. Endpoints: `/health/summary`, `/health/audit`, `/health/cleanup`. Modal de confirmación con dry-run.
- **Neuro-Visor Dashboard v2 — Página Explorar (Node Inspection)**: Panel unificado con pestañas Identidad, Conexiones (sinapsis agrupadas por tipo con pesos), Contenido (edición inline), Latentes (sinapsis transitivas con score y ruta). Toolbar con acciones: Merge, Link, Delete, Sleep.
- **Toolbar Unificado + Modales de Gestión de Nodos**: MergeModal (combinar nodos preservando sinapsis), LinkModal (crear sinapsis manual con tipo/peso), DeleteConfirm (borrado en cascada con preview), SleepConfirm (consolidación ciclo).
- **CSS Design System — Migración a Radix Themes**: Tokens unificados (`--radius-*`, `--spacing-*`, `--color-*`, `--font-*`). 12+ componentes con CSS Modules consistentes. Eliminado `globals.css` legacy.
- **Edición Inline de Contenido**: NodeIdentityPanel permite editar contenido directamente con guardado inmediato vía API.
- **Prevención de Grupos Semánticos Duplicados**: Fix en node detail y ego-graph queries. Chips de sinapsis con mejor legibilidad.
- **Text Overflow Prevention + Reorder**: NodeIdentityPanel reordenado para mejor legibilidad.

### Database & Architecture
- **metricas_cognitivas Refactor (FK-based)**: Claves foráneas reales `largo_plazo_id` → `largo_plazo.id` y `categoria_dominante_id` → `categorias.id`. Eliminada columna `concepto` duplicada. Índices optimizados. Migración idempotente con validación de integridad.

### Tests & Calidad
- 95/95 tests ✓
- Latencia búsqueda: ~2.8ms
- RAM: ~20 MB

---

## v18.1 (2026-05-15)

### Features & Robustness
- **Prevención de Caminos Cíclicos en Inferencia Transitiva**: Implementación del rastreo del camino recorrido (`ruta`) en la CTE recursiva de SQLite para prevenir la acumulación de ciclos fantasma de 3 o más saltos (ej. A -> B -> C -> B).
- **Filtro de Compatibilidad de Tipos de Relación**: Restricción estricta de la propagación de sinapsis latentes para evitar la acumulación de ruido estadístico casual (`co_ocurrencia -> co_ocurrencia`). Ahora solo se extienden relaciones compatibles semánticamente (`co_semantica`, `co_nombre`) o a través de puentes de alta confianza (`manual`, `sinonimo_explicito`, `test`).
- **Alineamiento de Timezones en Consultas MCP**: Estandarización de `timezone.utc` en el parseo de filtros de fecha relativa (`desde`/`hasta`) en `mcp_server.py`, garantizando búsquedas e inferencias independientes de la zona horaria local del host.
- **Suite de Verificación de Inferencia**: Validación de los asserts del grafo en una base de datos en memoria para prevención de ciclos, bloqueo de ruido y propagación por puente de confianza.

---

## v18.0 (2026-07-12)

### Features & Robustness
- **Capa 13 de Fallback Simbólico (Capa 2.1)**: Integración de distancia de Levenshtein normalizada y WordNet bilingüe (ES + EN) con traducción opcional (`BIORAG_TRADUCCION_ACTIVA=1`).
- **Relajación de Tokens Cortos**: Soporte mejorado para acrónimos y versiones breves de longitud `>= 2` (como `"cv"`, `"v6"`, `"ia"`) en WordNet, mientras que el filtro trigram de SQLite (`PALABRA_COMPLETA`) ahora se aplica selectivamente solo a tokens `<= 4` caracteres para prevenir colisiones ruidosas sin afectar palabras largas.
- **Scoring Simbólico Integrado**: Los nuevos puntuadores `score_simbolico_concepto` y `score_simbolico_sinonimos` actúan como un boost (`max()`) sobre las señales del score híbrido.
- **Unificación de BM25**: Consolidación de la constante de normalización a `abs(val) / (abs(val) + 3.0)` en todas las rutas de búsqueda para garantizar la comparabilidad matemática de resultados.
- **Rebalanceo Equitativo de Pesos**: Corrección del exceso de pesos en la fórmula del score híbrido (reduciendo la suma de 1.05 a exactamente 1.0) mediante el rebalanceo de `concepto_ratio` a 0.175 y `sinonimos_ratio` a 0.125. Esto previno la distorsión por saturación del techo de score y elevó el Recall@1 al **78.02%** en la suite QA.
- **Optimización de Consultas FTS5 con `CROSS JOIN`**: Reestructuración de 8 consultas clave de búsqueda entre tablas virtuales FTS5 (`largo_plazo_fts`, `largo_plazo_fts_unicode`) y la tabla indexada `largo_plazo` utilizando `CROSS JOIN`. Esto fuerza al planificador de consultas de SQLite a resolver primero el `MATCH` de FTS5, logrando una reducción masiva de latencia de ~500ms a **<10ms** (~100x de aceleración) al evitar escaneos de tablas completas.
- **Suite de QA Fase 1 (Precisión Semántica)**: Transición de aserciones unitarias básicas a un dataset estático estandarizado (`casos_qa_baseline_v1.jsonl`) con **921 casos de prueba reales** que evalúan el motor de búsqueda en 8 categorías lingüísticas, logrando un **93.76% de Recall@5** y **87.63% de Recall@1** sin regresiones.
- **Suite de QA Fase 2 (Estrés, Robustez y Escala)**: Implementación de scripts de diagnóstico avanzados:
  - `fuzz_qa.py` (Fase 2A): Evalúa la resiliencia ante inyecciones de SQL, desbalanceos y cadenas corruptas (**33/33 casos aprobados**).
  - `concurrencia_qa.py` (Fase 2B): Valida el aislamiento multi-hilo en SQLite WAL y el transporte asíncrono HTTP SSE de MCP (**0 bloqueos o colisiones**).
  - `escala_qa.py` (Fase 2C): Benchmarking de latencia en volúmenes crecientes de datos de grafos sintéticos (hasta 50,000 nodos).
  - Telemetría pasiva (Fase 2D): Logging de búsquedas y retroalimentación interactiva con `biorag_marcar_resultado`.
- **Pruebas QA Adversarias**: Ampliación de la suite QA local a 534 casos, incluyendo 30 controles negativos adicionales para validar la robustez de tokens de 2 caracteres (manteniendo 0% de Falsos Positivos).
- **Centralización de Stopwords**: Creación de `core/stopwords.py` para unificar y aislar listas de stopwords en español, inglés y tokens de control, previniendo la contaminación lingüística en Levenshtein.

---

## v17.1 (2026-07-11)

### Features & Robustness
- **Auto-Clustering Robusto**: Implementación de una migración única (`migration_autoclustering_v1`) para limpiar dimensiones auto-generadas legacy inactivas.
- **Desambiguación Dinámica Jaccard**: Reutilización inteligente de nombres de dimensiones mediante el cálculo del solapamiento Jaccard contra miembros de clusters existentes (con umbral de coincidencia >= 0.5).
- **Saneamiento de Miembros Locales**: Eliminación automática de miembros obsoletos locales al reutilizar y renombrar una dimensión existente.
- **Purga Global Inactiva**: Eliminación definitiva de dimensiones auto-generadas inactivas que no tengan miembros asociados al final del ciclo de consolidación.
- **Similitud Conceptual Stateless**: Remoción del diccionario mutable global `_grafo_cache` en `core/similitud_conceptual.py` para garantizar la seguridad de hilos frente a accesos concurrentes de múltiples agentes.

---

## v17.0 (2026-07-10)

### Features
- **Oráculo de NotebookLM Mejorado**: Nueva herramienta `biorag_oraculo_preguntar` para realizar consultas cruzadas directas con el nombre obligatorio del agente. Redefinición de `oraculo_inicio` para tareas exclusivas de arranque.
- **Mensajería Broadcast**: Rastreo de lectura individual en el canal compartido por medio de la columna `leido_por` en la tabla `comunicaciones`.
- **Higiene de Mensajería**: Nueva herramienta `marcar_como_leido` para evitar el re-procesamiento de notificaciones de cartelera, y obligatoriedad del parámetro `origen` en las comunicaciones.
- **Configuración de Agentes**: Actualización de la documentación interna y directrices de persistencia/firma en BioRAG.

---

## v16.0 (2026-07-09)

### Features
- **Etiquetado de Roles Semánticos (SRL)**: Soporte para análisis de estructura relacional (Sujeto-Verbo-Objeto-Contexto). Almacenamiento persistente e indexación de roles en SQLite para búsquedas por roles relacionales.
- **Inferencia Transitiva en Grafos (Fuzzy Reasoning)**: Descubrimiento de relaciones conceptuales indirectas. Cálculo por caminos multi-hop con atenuación matemática (decay 0.7) y prevención de bucles infinitos usando CTE recursiva en SQLite.
- **Auto-Clustering de Dimensiones Emergentes**: Detección autónoma de comunidades temáticas mediante el algoritmo de Label Propagation (LPA) sobre el grafo de sinapsis. Creación e indexación de dimensiones dinámicas emergentes (`auto_`) asociadas a los nodos de forma nativa en Python.
- **Búsqueda por Rol y Boost de Confianza**: Parámetro `buscar_por_rol` y scoring híbrido mejorado mediante la adición de dimensiones autogeneradas multiplicadas por su confianza.

### Database Changes
- **`predicados` y `corto_plazo_predicados`**: Nuevas tablas para almacenar estructura de roles SRL.
- **`sinapsis_latentes`**: Tabla caché de sinapsis transitivas indirectas con índices por origen y destino.
- **`dimensiones_semanticas`**: Columnas añadidas: `auto_generada` (INTEGER), `confianza` (REAL) y `generado_en` (REAL).

### Tests
- **Tests 80-86**: Verificación completa del pipeline de inferencia transitiva, prevención de bucles, almacenamiento SRL, búsqueda por rol, auto-clustering LPA, coseno ponderado y regresión.

---

## v15.0 (2026-07-09)

### Features
- **Clasificación Simbólica WordNet**: Mapeo léxico-semántico de conceptos y sinónimos a las 45 categorías ontológicas de WordNet (lexnames).
- **nltk_data Local y Aislada**: Descarga e inicialización de WordNet en la ruta del proyecto `MemoryBioRAG_Data/nltk_data` para garantizar la autonomía y soporte 100% offline.
- **Score Híbrido de 9 Señales**: Incorporación del `grupo_score` como la 9ª señal de relevancia con un 10% de peso en la fórmula del score híbrido.
- **Cascaded Node Deletion**: Soporte de borrado en cascada (`ON DELETE CASCADE`) para remover automáticamente registros en la tabla puente `nodo_grupos_semanticos` cuando se elimina un concepto de largo plazo.

### Database Changes
- **`grupos_semanticos`**: Tabla de catálogo que indexa las categorías lexicográficas fijas de WordNet.
- **`nodo_grupos_semanticos`**: Tabla puente relacional que asocia conceptos con sus respectivos grupos semánticos, con restricciones de clave foránea en cascada.

---

## v14.0 (2026-07-08)

### Features
- **Auditoría Técnica Completa**: Mapeo de 25 técnicas y algoritmos biológicos frente a sus equivalentes de la industria (Elasticsearch, Lucene, ACT-R, etc.).
- **Optimización y Estabilidad**: Refactor del pipeline de búsqueda de 12 capas en cascada, auto-guardado en sesiones y ráfaga de reminiscencia integrada.

---

## v13.0 (2026-07-05)

### Features
- **Filtro temporal PRE-hoc**: `desde_ts`/`hasta_ts` como parámetros de `buscar_por_frase`. El filtro `creado_en` se aplica en SQL FTS5 durante la búsqueda, no post-hoc. Elimina desperdicio de cómputo en búsquedas con filtro de fecha.
- **Índices SQL `estado` y `creado_en`**: `idx_estado` y `idx_creado_en` en `largo_plazo`. Queries temporales y por estado usan índice en vez de full scan.

### Bug Fixes
- **`score_parafrasis_best` siempre 0.0**: Corregido (de verdad esta vez). Ahora calcula el mejor score desde `last_origen_scores` cuando el origen es "parafrasis".
- **Doble asignación `score_top`**: Eliminada línea duplicada en `_recordar_impl`.
- **LIKE concepto sin `temporal_params`**: La búsqueda LIKE en concepto (Capa 2) inyectaba `clause` con `?` temporales pero no pasaba los parámetros. Crasheaba con "Incorrect number of bindings" cuando se usaba filtro temporal.
- **`sql_unicode` sin `temporal_params`**: Fallback unicode61 prefix no pasaba parámetros temporales.
- **`sql` (expansión semántica) sin `temporal_params`**: Fallback de expansión semántica no pasaba parámetros temporales.
- **Tests JSON parsing**: Tests 69h, 69i y 78 ahora manejan warnings prependidos al JSON.

### Architecture
- **Filtro temporal en 6 execute calls**: `temporal_params` inyectado en NEAR, FTS5 AND, FTS5 OR, unicode61, expansión semántica, y Snap reciente.
- **Safety net post-hoc**: Fallbacks no-FTS5 (LIKE, trigram, latente) mantienen filtro post-hoc como respaldo, ahora acelerado por `idx_creado_en`.

### Tests
- 78/78 tests verdes

---

## v12.0 (2026-07-04)

### Features
- **`creado_en` en largo_plazo**: Columna temporal que registra cuándo se consolidó cada concepto. Registros antiguos heredan `ultimo_acceso`. Permite filtros temporales en búsquedas.
- **Filtros temporales en `recordar`**: Nuevos parámetros `dias`, `desde`, `hasta` para buscar por rango de fechas. Ejemplo: `recordar(query='error', dias=5)` trae errores de los últimos 5 días.
- **Filtro por autor**: Nuevo parámetro `autor` en `recordar` para filtrar por nombre del agente en memoria compartida. Ejemplo: `recordar(query='lesson', autor='athena')`.
- **`query` opcional en `recordar`**: Si se omite `query`, `recordar` funciona como log cronológico puro — trae los N recuerdos más recientes ordenados por `creado_en DESC`. Combina con `dias`/`desde`/`hasta`/`autor`.
- **`desvincular(a, b)`**: Tool de plasticidad negativa interactiva. Elimina la sinapsis bidireccional entre dos conceptos cuando aparece un falso positivo. El cerebro mejora con cada corrección.
- **Ráfaga con dimensiones**: `buscar_por_rafaga` ahora acepta `dimensiones_ids` para scoring dimensional (25% del score híbrido). Coseno binario discreto.
- **Match exacto ×2.0**: Concepto normalizado == query normalizado recibe multiplicador de score ×2.0.
- **Degradación progresiva 3 niveles**: FTS5 → fuzzy → sinonimos cuando la query no tiene resultados.
- **Trazaabilidad completa**: Response JSON incluye scores por capa (`capa_literal`, `capa_parafrasis`, `capa_rafaga`), `match_exacto`, `total_candidatos_todos`, y `dimensiones_solicitadas`.
- **Directiva de Higiene de Falsos Positivos**: Cuando un agente detecta un falso positivo que llegó por sinapsis, ejecuta `desvincular` automáticamente para limpiar el grafo.

### Bug Fixes
- **Validación de dimensiones simétrica**: `_recordar_impl` ahora BLOQUEA búsqueda si recibe dimensiones inválidas (antes las ignoraba silenciosamente). Consistente con `_aprender_impl`.
- **`score_parafrasis_best` siempre 0.0**: Corregido — ahora trackea correctamente el mejor score de paráfrasis.
- **`NameError` en trazabilidad**: `self.last_todos` y `self.last_origen_scores` ahora se inicializan correctamente.
- **Ráfaga creaba sinapsis con tokens sueltos**: Ahora solo crea sinapsis si el token existe como concepto activo en `largo_plazo`. Previene hiperconectividad (ej: nodo "flor" con 59 sinapsis irrelevantes).
- **`vincular_por_sinonimos` buscaba en contenido**: Ahora solo busca en `concepto` y `sinonimos`, NO en `contenido`. Previene conexiones espurias por mención incidental.
- **`asociaciones` CSV desincronizado**: `_sincronizar_asociaciones()` se ejecuta en las 4 rutas de escritura (auto_vincular, vincular_por_sinonimos, desvincular, establecer_asociacion). CSV siempre refleja el estado real de sinapsis.
- **Filtros temporales post-truncado**: `dias/desde/hasta/autor` ahora se aplican ANTES del truncado, no después. Previene 0 resultados cuando los top-score no coinciden con el filtro temporal.
- **`parafrasis_list` desconectado en `buscar_por_frase`**: `fts_match` se calculaba pero nunca se usaba. Ahora se conecta directamente a las queries FTS5. Eliminado el hack de `mcp_server.py` que pasaba el string OR como texto natural.
- **`biorag_buscar` sin `dimensiones=None`**: Alias legado ahora acepta `dimensiones` como opcional, consistente con `biorag_recordar`.
- **`dim_dict` → `dimensiones_dict`**: Refactor de `_resolver_dimensiones` como helper compartido. Fix de `NameError` en `_aprender_impl`.
- **`dimensiones_invalidas` no definida**: Fix de `NameError` post-refactor. Variable restaurada después del helper.
- **Bug argumentos posicionales en scoring**: `_calcular_score_hibrido` recibía `contenido` en el parámetro `pesos_tokens`. Fix: usar keyword argument `contenido=contenido`. El scoring ahora ajusta correctamente por centralidad del token.
- **score_hibrido 0.0 en modo cronológico**: Ahora retorna `min(1.0, peso_sinaptico)` en vez de 0.0. Los resultados cronológicos muestran relevancia real.

### Architecture
- **Pipeline colapsado a 2 pasos**: PASO 1 obligatorio (paráfrasis+dimensiones), PASO 2 fallback (ráfaga). De 4 pasos a 2.
- **Fórmula score híbrido**: 55% BM25 + 25% peso_sináptico + 10% asociaciones + 10% dim_score.
- **Fórmula ráfaga con dimensiones**: 0.40 densidad + 0.25 peso + 0.10 asoc + 0.25 dim_score.
- **Paráfrasis optimizado**: 1 query FTS5 OR en vez de N queries separadas. Penalización ×0.95 en Python.
- **Homeostasis sináptica**: `sinapsis` y `largo_plazo.asociaciones` siempre sincronizados.
- **Reordenar fallbacks**: Typo (trigram) ahora corre ANTES de latente (Jaccard). Un typo match es más confiable que similitud latente. Benchmark: promedio 186ms → 58.8ms.
- **Helpers compartidos**: `_resolver_dimensiones()` y `_parsear_fechas()` extraídos para eliminar duplicación entre `_recordar_impl` y `_aprender_impl`.

### Data Cleanup
- 681 sinapsis espurias eliminadas (477 rafaga_rememb huérfanas + 204 sinonimo_explicito de arquitectura_busqueda_dimensional)
- 362 nodos activos sincronizados

### Tests
- Tests 73-78: ráfaga con dimensiones, score con dim_score, match exacto ×2.0, fallback dimensional, penalización paráfrasis ×0.95, trazabilidad.
- 78/78 tests verdes

### Coordinación Athena ↔ Artemis
- Canal simbiótico: diseño colaborativo de created_en, desvincular, higiene de falsos positivos
- Artemis detectó bug de `asociaciones` desincronizado y ejecutó fix completo
- Protocolo de memoria compartida documentado en docstring de `recordar`

---

## v11.1 (2026-06-29)

### Features
- **Etiquetado Emocional y Cognitivo (Opción B)**: Integración nativa de etiquetas sinápticas estandarizadas (`emocion_afecto`, `emocion_frustracion`, `emocion_preocupacion`, `emocion_satisfaccion`) a través de la columna existente `sinonimos`.
- **Diccionario Semántico Auto-Sustentable**: El motor siembra equivalencias bidireccionales en tiempo de inicio para que búsquedas por palabras cotidianas (ej. `"cariño"`, `"molesto"`) evoquen los recuerdos correspondientes.
- **Middleware de Autoguardado Emocional**: Adaptación del detector de la sesión para capturar expresiones de sentimientos y clasificar de forma autónoma con la etiqueta emocional correspondiente.

### Tests
- **Test 72**: Cobertura completa de evocado de recuerdos mediante tags emocionales y verificación del interceptor.
- 72/72 tests verdes exitosos.

---

## v11.0 (2026-06-29)

### Features
- **Indexación de concept_ids**: Indexación persistente de identificadores conceptuales únicos (`conceptos_ids`) basados en grupos conexos (Union-Find) de equivalencias semánticas.
- **Boosting de Relevancia Conceptual**: Aumento del factor de relevancia (1.2x) en el cálculo del score híbrido para coincidencias semánticas del mismo clúster conceptual.

### Tests
- **Test 71**: Verificación de la propagación del boost conceptual y validez del score tras consolidación.

---

## v10.2 (2026-06-28)

### Features
- **Parafrasis SIEMPRE**: cuando se pasa `parafrasis`, el sistema busca TODAS las variantes sin excepción. El objetivo es cognición, no eficiencia. El agente piensa siempre, el sistema busca siempre.
- **Umbral ELIMINADO**: `PARAFRASIS_THRESHOLD` removido. El threshold 0.5 era un gate de eficiencia que contradecía el objetivo de cognición del diseño.
- **Penalización conservada**: ×0.95 para variantes no exactas. El query original (i==0) mantiene factor 1.0.

### Fixes
- `parafrasis` de `List[str]` → `Optional[str]` (estilo `rafaga_palabras`)
- Validación obligatoria: si `parafrasis` se pasa y está vacío → error con mensaje explicativo
- Errores de sintaxis en edición del bloque paráfrasis corregidos

### Tests
- 70/70 tests verdes

### Principios aprendidos
- `principio_tres_capas_biorag`: tres capas para cerrar gap semántico sin embeddings (paráfrasis + rafaga + inferencia)
- `leccion_feature_b_inferencia_ruido`: inferencia automática produce ruido, usar como herramienta de sugerencia

---

## v10.1 (2026-06-28)

### Bug Fixes
- **ORDER BY corregido**: fórmula `(1.0 - 0.5 * peso)` → `(0.5 + 0.5 * peso)`. El bug penalizaba nodos con peso alto (0.99 → factor 0.505). Ahora prioriza correctamente (0.99 → factor 0.995).

### Features
- `poblar_sinonimos_desde_contenido()`: extrae keywords del contenido de nodos con peso ≥ 0.5, guarda en columna `sinónimos`. Triggers AFTER UPDATE reindexan FTS automáticamente. Idempotente.

### Tests
- Test 70: verifica ORDER BY con dos nodos mismo contenido (peso 0.95 vs 0.1) — pesado aparece primero. Verifica garbled query extrema no crashea.
- 70/70 tests verdes

---

## v10.0 (2026-06-27) — Anterior

- Recall semántico vía sinónimos y typo-tolerance
- Búsqueda fuzzy: resiliencia ante garbled queries
- Boost sináptico: nodos Profile priorizados en ORDER BY
- Auto-vincular: pasadas co_nombre y co_semantica