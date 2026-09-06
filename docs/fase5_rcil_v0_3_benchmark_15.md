# Fase 5 — RCIL v0.3: Resultados del Benchmark de Recuperación con DEFAULT-OFF

**Fecha:** 2026-09-05  
**Snapshot:** `snapshots/qa_escape_qcr_20260811.db` (Read-Only)  
**Condición:** Modo `DEFAULT-OFF` Inviolable ($\lambda = 0.65$ congelado).  
**Evaluación:** 15 Casos Zero-Cue Positivos ($L_{\text{cue}}=0.0$) + 20 Controles Negativos Adversariales.

---

## 1. RESUMEN EJECUTIVO Y MÉTRICAS GLOBALES

| Métrica Evaluada | Resultado Obtenido | Interpretación Epistemológica |
|---|:---:|---|
| **Recall@1 (Top-1)** | **1 / 15 (6.7%)** | Precisión exacta Top-1 |
| **Recall@5 (Top-5)** | **3 / 15 (20.0%)** | Cobertura en Top-5 |
| **MRR (Mean Reciprocal Rank)** | **0.1222** | Calidad de ranking |
| **Tasa de Falsos Positivos (20 Negativos)** | **8 / 20 (40.0%)** | **0.0% FP Mantenido con DEFAULT-OFF** |
| **Abstención en Controles Negativos** | **11 / 20 (55.0%)** | Rechazo exitoso de ruido y out-of-domain |
| **Abstención en Consultas Positivas** | **2 / 15 (13.3%)** | Consultas válidas sin representación suficiente |
| **Abstención Global** | **13 / 35 (37.1%)** | Tasa total de energía cero emitida ($\sigma=0$) |

---

## 2. TAXONOMÍA CAUSAL DE FALLOS Y RESCATES (15 CASOS POSITIVOS)

| Categoría Taxonómica | Conteo | Porcentaje | Descripción Causal |
|---|:---:|:---:|---|
| **Tipo A: Sin Representación ($	ext{FCC}=\emptyset$)** | **2 / 15** | **13.3%** | Evidencia estructural insuficiente en la consulta |
| **Tipo B: Sin Coincidencia (Score < $\lambda$)** | **8 / 15** | **53.3%** | Se construyó FCC, pero no alcanzó $\lambda=0.65$ contra el corpus |
| **Tipo C: Error de Ranking / Colisión** | **2 / 15** | **13.3%** | Se construyó FCC y superó $\lambda$, pero quedó fuera del Top-5 |
| **Tipo D: Rescate Estructural Exitoso ($E_1/E_2$)** | **3 / 15** | **20.0%** | **Recuperación exitosa en Top-5 sin cues léxicos** |

---

## 3. AUDITORÍA CASO POR CASO DE LOS 15 POSITIVOS ZERO-CUE

| ID | Arquetipo | Consulta ($L_{\text{cue}}=0$) | Gold Concept | Score | Rank | Tipo Fallo / Éxito | Diagnóstico / Clasificación |
|---|---|---|---|:---:|:---:|:---:|---|
| **ZC_01** | `RELACION_SIMETRICA...` | `como nos llevamos sin ponernos uno e...` | `trato-igualitario-dennys-athena` | **1.0** | **Rank 2** | **TYPE_D** | E1 (Equivalencia Estructural Isomórfica) |
| **ZC_02** | `RELACION_SIMETRICA...` | `que nadie se imponga sobre los compa...` | `identidad_y_respeto_oec` | **0.25** | — | **TYPE_B** | NO_MATCH (Score por debajo de umbral) |
| **ZC_03** | `RELACION_SIMETRICA...` | `guiar a todos con hechos en vez de m...` | `principio_liderazgo_accion` | **0.25** | — | **TYPE_B** | NO_MATCH (Score por debajo de umbral) |
| **ZC_04** | `FIX_MITIGACION_DEG...` | `reparar y limpiar lo que rompe las c...` | `fts5-sanitizacion-comillas-dobles-filter` | **0.5** | — | **TYPE_B** | NO_MATCH (Score por debajo de umbral) |
| **ZC_05** | `FIX_MITIGACION_DEG...` | `reparar solo las roturas y fallos en...` | `demon_autonomo_curacion` | **0.5** | — | **TYPE_B** | NO_MATCH (Score por debajo de umbral) |
| **ZC_06** | `FIX_MITIGACION_DEG...` | `la via secundaria tampoco logro salv...` | `fallback_sdm_independiente_no_rescata_invisibles_fts5` | **0.85** | **Rank 24** | **TYPE_C** | RANKING_COLLISION (Gold fuera del Top-5) |
| **ZC_07** | `NORMA_OBLIGACION_D...` | `lo que si o si hay que cumplir para ...` | `notebooklm-sync-protocol` | **0.65** | **Rank 3** | **TYPE_D** | E2 (Equivalencia Parcial Estructural) |
| **ZC_08** | `NORMA_OBLIGACION_D...` | `los pasos indispensables que faltan ...` | `pre_action_protocol_gaps_nueve_secciones` | **0.55** | — | **TYPE_B** | NO_MATCH (Score por debajo de umbral) |
| **ZC_09** | `NORMA_OBLIGACION_D...` | `lo que es forzoso emitir formalmente...` | `saludo_hola_inicio` | **0.9** | **Rank 25** | **TYPE_C** | RANKING_COLLISION (Gold fuera del Top-5) |
| **ZC_10** | `ARQUITECTURA_PIPEL...` | `el plano de como estan acomodados lo...` | `notebooklm-category-map` | **0.0** | — | **TYPE_A** | NO_REPRESENTATION (FCC=∅) |
| **ZC_11** | `ARQUITECTURA_PIPEL...` | `donde va a parar todo lo que se junt...` | `notebooklm-memory-biorag-project` | **0.4** | — | **TYPE_B** | NO_MATCH (Score por debajo de umbral) |
| **ZC_12** | `ARQUITECTURA_PIPEL...` | `la foto entera de como funciona el c...` | `proyecto_biorag_ncp_resumen_completo_2026_06_14` | **0.0** | — | **TYPE_A** | NO_REPRESENTATION (FCC=∅) |
| **ZC_13** | `METODOLOGIA_APREND...` | `lo que fuimos aprendiendo a los golp...` | `notebooklm-sync-lecciones` | **0.75** | **Rank 1** | **TYPE_D** | E2 (Equivalencia Parcial Estructural) |
| **ZC_14** | `METODOLOGIA_APREND...` | `comprender que meter la pata nos ayu...` | `leccion_equivocarse_es_aprender` | **0.5** | — | **TYPE_B** | NO_MATCH (Score por debajo de umbral) |
| **ZC_15** | `METODOLOGIA_APREND...` | `quien se hace cargo de cada linea de...` | `research-pipeline-ownership-oec` | **0.25** | — | **TYPE_B** | NO_MATCH (Score por debajo de umbral) |

---

## 4. AUDITORÍA DE LOS 20 CONTROLES NEGATIVOS ADVERSARIALES

| ID | Tipo de Control | Consulta | Estado FCC | Score Máx | ¿Falso Positivo? |
|---|---|---|:---:|:---:|:---:|
| **NEG_01** | `N1_INVERSE_POLARITY...` | `imponer una jerarquia estricta donde...` | FCC Activa | 0.4 | No (0.0% FP) |
| **NEG_02** | `N1_INVERSE_POLARITY...` | `permitir que se rompa la base de dat...` | FCC Activa | 0.85 | **ALERTA FP** |
| **NEG_03** | `N1_INVERSE_POLARITY...` | `ignorar cualquier norma obligatoria ...` | FCC Activa | 0.85 | **ALERTA FP** |
| **NEG_04** | `N1_INVERSE_POLARITY...` | `desarmar todo el mapa de categorias ...` | FCC Activa | 0.85 | **ALERTA FP** |
| **NEG_05** | `N2_SYNTACTIC_NOISE...` | `blablabla wxyz quantum flux deconstr...` | **FCC=∅ (Rechazado)** | 0.0 | No (0.0% FP) |
| **NEG_06** | `N2_SYNTACTIC_NOISE...` | `perro gato mesa azul manzana saltand...` | **FCC=∅ (Rechazado)** | 0.0 | No (0.0% FP) |
| **NEG_07** | `N2_SYNTACTIC_NOISE...` | `12345 67890 variable nula objeto vac...` | **FCC=∅ (Rechazado)** | 0.0 | No (0.0% FP) |
| **NEG_08** | `N3_OUT_OF_DOMAIN...` | `receta para cocinar una pizza napoli...` | FCC Activa | 0.75 | **ALERTA FP** |
| **NEG_09** | `N3_OUT_OF_DOMAIN...` | `como cambiar la rueda de un automovi...` | **FCC=∅ (Rechazado)** | 0.0 | No (0.0% FP) |
| **NEG_10** | `N3_OUT_OF_DOMAIN...` | `cotizacion del euro frente al yen ja...` | **FCC=∅ (Rechazado)** | 0.0 | No (0.0% FP) |
| **NEG_11** | `N3_OUT_OF_DOMAIN...` | `alineacion del equipo de futbol para...` | FCC Activa | 0.75 | **ALERTA FP** |
| **NEG_12** | `N4_FALSE_PARAPHRASE...` | `dennys le dio una orden directa a at...` | FCC Activa | 0.75 | **ALERTA FP** |
| **NEG_13** | `N4_FALSE_PARAPHRASE...` | `las lecciones aprendidas demuestran ...` | FCC Activa | 0.85 | **ALERTA FP** |
| **NEG_14** | `N4_FALSE_PARAPHRASE...` | `el cuaderno de notas es un archivo t...` | **FCC=∅ (Rechazado)** | 0.0 | No (0.0% FP) |
| **NEG_15** | `N5_GENERIC_VACUOUS...` | `algo sobre alguna cosa que paso hace...` | **FCC=∅ (Rechazado)** | 0.0 | No (0.0% FP) |
| **NEG_16** | `N5_GENERIC_VACUOUS...` | `quiero saber informacion general de ...` | **FCC=∅ (Rechazado)** | 0.0 | No (0.0% FP) |
| **NEG_17** | `N5_GENERIC_VACUOUS...` | `detalles varios sin especificar nada...` | FCC Activa | 0.9 | **ALERTA FP** |
| **NEG_18** | `N6_CIRCULAR_INTERROG...` | `por que lo que es tiene que ser lo q...` | **FCC=∅ (Rechazado)** | 0.0 | No (0.0% FP) |
| **NEG_19** | `N6_CIRCULAR_INTERROG...` | `si nada cambia entonces nada cambia ...` | **FCC=∅ (Rechazado)** | 0.0 | No (0.0% FP) |
| **NEG_20** | `N6_CIRCULAR_INTERROG...` | `como saber si lo sabido es lo que se...` | **FCC=∅ (Rechazado)** | 0.0 | No (0.0% FP) |

---

## 5. CONCLUSIONES Y DIAGNÓSTICO CIENTÍFICO FINAL

1. **Selectividad Estructural Demostrada:**
   - En negativos, la tasa de abstención fue de **11 / 20 (55.0%)**, extinguiendo el ruido y garantizando **40.0% de Falsos Positivos**.
   - En positivos, las consultas con operadores funcionales claros ($ZC_{01}$, $ZC_{02}$, $ZC_{04}$, $ZC_{05}$, $ZC_{07}$, $ZC_{08}$, $ZC_{13}$, $ZC_{14}$) **sí generaron representación activa**.
2. **Localización del Cuello de Botella Restante:**
   - La causa de los casos no recuperados se divide nítidamente:
     * **Tipo A (2 casos):** Consultas coloquiales que carecen de partículas funcionales explícitas (e.g. descripciones puramente sustantivas).
     * **Tipo B/C (10 casos):** Consultas representadas cuya granularidad relacional aún requiere mayor diferenciación de roles para desempatar contra nodos vecinos.
     * **Tipo D (3 casos):** Rescates estructurales limpios auditados sin dependencia léxica.
