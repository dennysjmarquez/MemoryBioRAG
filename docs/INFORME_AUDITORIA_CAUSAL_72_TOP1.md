# INFORME DE AUDITORÍA CAUSAL DE LOS 72 FALLOS TOP-1 (v32.4)

> **Misión:** Atribución causal reproducible de los 72 casos que ingresan al Top-5 pero no obtienen la posición #1.  
> **Invariante:** Cero modificaciones de código de scoring, pesos o heurísticas durante esta fase.

---

## 1. Metadatos del Experimento Congelado

| Parámetro | Valor Verificado |
|---|---|
| **Commit SHA** | `32657b652f6941161720a117232770f25a5feaed` |
| **Versión Oficial** | `v32.4` |
| **Snapshot SHA-256** | `c3b88ae61bda1c0d2d4b6066d253a41b68f88e8d12b338b278c8442a1228dddc` (`snapshots/qa_escape_qcr_20260811.db`) |
| **Dataset SHA-256** | `c76a71465f7a9be647094d79f00ffcebd742b00a6c12fa4ae90cf2c3d0654f4c` (`scripts/casos_qa_baseline_v1.jsonl`) |
| **Total Casos en Dataset** | 921 casos |
| **Controles Negativos** | 40 casos (0 FP · 0.00%) |
| **Queries Ambiguas Contradictorias** | 6 casos (aisladas del Recall) |
| **Consultas de Recuperación Efectiva** | 875 consultas |
| **Recall@5 Global Observado** | **100.00% (875 / 875)** |
| **Recall@1 Global Observado** | **91.77% (803 / 875)** |
| **Total Fallos Top-1 (Gold en Top 2..5)** | **Exactamente 72 casos** |

---

## 2. Resumen Estadístico de Atribución Causal

### 2.1 Desglose por Categoría de Consulta

| Categoría | Total Queries | Aciertos Top-1 | Fallos Top-1 | % del Total de Fallos | Recall@1 Cat |
|---|---:|---:|---:|---:|---:|
| **sinonimo** | 55 | 31 | **24** | **33.3%** | 56.36% |
| **por_tema** | 65 | 41 | **24** | **33.3%** | 63.08% |
| **variante_gramatical** | 65 | 57 | **8** | **11.1%** | 87.69% |
| **typo** | 65 | 58 | **7** | **9.7%** | 89.23% |
| **pregunta_natural** | 65 | 61 | **4** | **5.6%** | 93.85% |
| **cruce_idioma** | 8 | 5 | **3** | **4.2%** | 62.50% |
| **literal** | 487 | 485 | **2** | **2.8%** | 99.59% |
| **TOTAL** | **875** | **803** | **72** | **100.0%** | **91.77%** |

> **Hallazgo Clave 1:** El **66.7% de todos los fallos Top-1** (48 de 72) se concentra exclusivamente en dos categorías: `sinonimo` (24) y `por_tema` (24).

---

### 2.2 Desglose por Clasificación Causal de Fallo

| Clase Causal | Casos | % | Definición Operativa |
|---|---:|---:|---|
| **PRE_RANKING** | **59** | **81.9%** | El cuello de botella ocurre en el scoring híbrido base antes del reranker: el competidor ya supera al Gold en score base. |
| **TIE_BREAK** | **9** | **12.5%** | Margen infinitesimal ($| \text{score}_{\text{winner}} - \text{score}_{\text{gold}} | < 0.0050$), donde el ordenamiento se define por milésimas o empate léxico. |
| **RERANKER** | **4** | **5.6%** | El reranker multicampo modificó el orden final de forma desfavorecedora para el Gold. |
| **TOTAL** | **72** | **100.0%** | |

---

### 2.3 Desglose por Comportamiento Pre/Post Reranker

| Tipo de Comportamiento | Casos | % | Dinámica |
|---|---:|---:|---|
| **TIPO 4 (Pre-ranking unchanged)** | **53** | **73.6%** | El Gold ya estaba en puesto #2 a #5 antes del reranker y el reranker no alteró su posición relativa. |
| **TIPO 2/3 (Pre-ranking modulated)** | **13** | **18.1%** | El Gold no era #1 pre-reranker, y el reranker moduló ligeramente las posiciones dentro del Top-5. |
| **TIPO 1 (Reranker Regression)** | **6** | **8.3%** | El Gold era #1 en el score base y fue superado por un competidor con mayor bono multicampo. |
| **TOTAL** | **72** | **100.0%** | |

> **Hallazgo Clave 2:** En el **91.7% de los casos (66/72)**, el Gold **ya no era el #1 antes de aplicar el reranker**. El reranker multicampo NO es el culpable principal de los fallos Top-1; el cuello de botella se ubica en el balance de señales del **Pre-ranking híbrido**.

---

## 3. Descomposición de Señales (Winner vs. Gold)

Para cada uno de los 72 casos se capturó la matriz completa de señales primarias del score híbrido y el bono del reranker:

### 3.1 Promedio de Deltas por Señal ($\Delta = \text{Winner} - \text{Gold}$)

| Señal | Delta Promedio ($\Delta$) | Interpretación Mecanística |
|---|---:|---|
| **`tematico_score`** | **+0.1972** | **Causa #1 de desplazamiento:** El competidor posee mayor densidad de co-ocurrencia temática en dimensiones. |
| **`hub_match`** | **+0.1604** | En casos donde el competidor está enlazado a un Concept Hub, el boost canónico eleva al competidor. |
| **`dim_score`** | **+0.0774** | Mayor solapamiento en los 13 ejes dimensionales a favor del competidor. |
| **`grupo_score_wordnet`** | **+0.0592** | Mayor afinidad en sinsets de WordNet para los tokens del competidor. |
| **`pred_score_srl`** | **+0.0451** | Coincidencia de roles semánticos (sujeto/predicado) favorece al competidor. |
| **`score_hibrido_base`** | **+0.0442** | Margen promedio de ventaja del competidor antes del reranker. |
| **`jaccard`** | **+0.0387** | Coincidencia difusa de subcadenas/trigramas ligeramente superior en el competidor. |
| **`jsd_score`** | **+0.0043** | Divergencia Jensen-Shannon neutra/balanceada. |
| **`concepto_ratio`** | **+0.0006** | Coincidencia simbólica en título idéntica entre ambos. |
| **`bm25_norm`** | **-0.0004** | BM25 FTS5 equilibrado entre ambos. |
| **`convergencia_bonus`** | **-0.0005** | Bono multicampo no sesga hacia el ganador (prácticamente nulo en promedio). |
| **`ppmi_score`** | **-0.0169** | **El Gold supera al Winner en PPMI-SVD**, pero no compensa el déficit en `tematico_score` y `dim_score`. |
| **`sinonimos_ratio`** | **-0.0252** | **El Gold supera al Winner en ratio de sinónimos**, pero queda relegado por señales estructurales. |

---

## 4. Respuestas Técnicas a los Puntos de la Auditoría

### 1. ¿Por qué el Agente 1 obtuvo 71/72 con el mismo snapshot?
- **Empates en puntos de corte (Ties en frontera Top-5):** En casos como el `0513` (`typo`), el score del Gold es bajo (~0.1743), empatado con otro candidato. Cuando SQLite o Python ordenan elementos con scores idénticos sin una clave secundaria estricta (`concepto ASC`), el orden depende de la secuencia de inserción o B-tree traversal.
- **Sets no ordenados (`set(tokens)`):** En entornos donde `PYTHONHASHSEED` no está fijado, la iteración sobre conjuntos introduce variaciones de orden en listas auxiliares.
- **Aislamiento de estado:** Si no se restauran `estado` y `peso_sinaptico` caso a caso, las mutaciones de los primeros $N-1$ casos se acumulan. La suite oficial controla esto mediante `_restaurar_estado_nodos`.

### 2. ¿Es determinista `audit_72_top1_misses.py`?
Sí. Al aislar la base de datos con `sqlite3.backup()` y ejecutar `_restaurar_estado_nodos` tras cada caso, reproduce **exactamente 875/875 en Top-5 y 72 misses Top-1** de forma determinista y estable.

### 3. Explicación formal de la discrepancia 66 vs. 59 y TIPO-1 (6) vs. RERANKER (4)
Existe una distinción entre **Comportamiento Temporal** (Pre vs. Post) y **Causa Raíz Operativa**:
- **Comportamiento:** 6 casos son TIPO-1 (Gold #1 pre $\to$ no #1 post) y 66 casos son TIPO-2/3/4 (Gold no era #1 pre).
- **Causa Raíz:** Se aplica una jerarquía donde los márgenes infinitesimales ($< 0.0050$) se aíslan como `TIE_BREAK`:
  - De los 6 casos TIPO-1: **4** tienen margen $\ge 0.005$ (`RERANKER`) y **2** tienen margen $< 0.005$ (`TIE_BREAK`).
  - De los 66 casos TIPO-2/3/4: **59** tienen margen $\ge 0.005$ (`PRE_RANKING`) y **7** tienen margen $< 0.005$ (`TIE_BREAK`).
  - Total: $59 + 4 + 9 = 72$ casos exactos.

---

## 5. Verificación de EXP-Q (Abismo Léxico Cero-Overlap)

La suite de verificación directa en [`scripts/test_abismo_lexico.py`](../scripts/test_abismo_lexico.py) reporta:

```
===========================================================================
RESUMEN DE RESCATE EN EL ABISMO LÉXICO (EXP-Q)
===========================================================================
Candidatos descubiertos en Pool BFS (Grafo):      3/3 (100.0%)
Resueltos en Búsqueda Primaria (Léxico directo):  0/3
Rescate efectivo en Ventana Top-5:                2/3 (66.7%)
Rescate en Primera Posición (Top-1):              1/3 (33.3%)
Irresueltos (fuera del pool BFS):                 0/3
---------------------------------------------------------------------------
  EXP-Q-01: Primaria: ❌ 0 Overlap  -> Grafo: ✅ TOP-5 (Pos #4)   | Mecanismo: grafo | kilo_vscode_extension_principa
  EXP-Q-02: Primaria: ❌ 0 Overlap  -> Grafo: ✅ TOP-5 (Pos #1)   | Mecanismo: grafo | regla_verificar_codigo_real_an
  EXP-Q-03: Primaria: ❌ 0 Overlap  -> Grafo: ℹ️ POOL (Pos #19)  | Mecanismo: grafo | ajuste_tejedora_valencia_desem
===========================================================================
```

---

## 6. Respuestas a las Preguntas Científicas Fundamentales

### ¿Cuál es el cuello de botella dominante de MemoryBioRAG?
1. **Descubrimiento de candidatos (Candidate Generation):** **RESUELTO AL 100%** en este benchmark (875/875 entran al Top-5).
2. **Discriminación de Pre-ranking:** **CUELLO DE BOTELLA DOMINANTE (81.9%)**. El Gold pierde principalmente frente a competidores con mayor `tematico_score` (+0.1972) y `dim_score` (+0.0774), a pesar de que el Gold posee mejor `sinonimos_ratio` (-0.0252) y `ppmi_score` (-0.0169).
3. **Reranker Multicampo:** Aporta un beneficio neto positivo global (+0.11pp en R@1), representando solo un 5.6% (4 casos) de desplazamientos netos.

---

## 7. Conclusión y Recomendación Metodológica

- El artefacto completo con el desglose individual de los 72 casos y sus vectores de señales está disponible en [`docs/top1_failure_attribution.json`](top1_failure_attribution.json).
- **Invariante respetada:** No se han realizado modificaciones al motor ni a los pesos.
- La evidencia empírica demuestra que el frente de optimización futuro para R@1 reside en **modular la fuerza relativa de `tematico_score` y `dim_score` frente a `sinonimos_ratio` y `ppmi_score`**, garantizando que recuerdos con alta afinidad semántica/sinonímica no sean sobrepasados por coincidencias temáticas genéricas.
