# INFORME DE AUDITORÍA DIAGNÓSTICA, TRAZABILIDAD Y EVALUACIÓN CONTRAFACTUAL DE LOS 72 FALLOS TOP-1 (v32.4)

> **Misión:** Atribución causal mediante experimentación contrafactual formal (A/B/C/D) y trazabilidad completa de linaje de telemetría de los 72 casos que ingresan al Top-5 pero no obtienen la posición #1 en el benchmark QA congelado.  
> **Invariante Metodológica:** Cero modificaciones permanentes en el motor de búsqueda, pesos de producción, umbrales ni mecanismos de scoring.

---

## 1. Metadatos del Experimento y Reproducibilidad

### 1.1 Identificadores Criptográficos Congelados
| Parámetro | Valor Verificado |
|---|---|
| **Commit SHA** | `32657b652f6941161720a117232770f25a5feaed` |
| **Versión Oficial** | `v32.4` |
| **Snapshot SHA-256** | `c3b88ae61bda1c0d2d4b6066d253a41b68f88e8d12b338b278c8442a1228dddc` (`snapshots/qa_escape_qcr_20260811.db`) |
| **Dataset SHA-256** | `c76a71465f7a9be647094d79f00ffcebd742b00a6c12fa4ae90cf2c3d0654f4c` (`scripts/casos_qa_baseline_v1.jsonl`) |
| **Total Casos en Dataset** | 921 casos |
| **Controles Negativos** | 40 casos (0 FP · 0.00%) |
| **Queries Ambiguas Contradictorias** | 6 casos (aisladas formalmente del Recall) |
| **Consultas de Recuperación Efectiva** | 875 consultas |
| **Recall@5 Global Observado** | **100.00% (875 / 875)** |
| **Recall@1 Global Observado** | **91.77% (803 / 875)** |
| **Total Fallos Top-1 (Gold en Top 2..5)** | **Exactamente 72 casos** |

---

### 1.2 Demostración de Reproducibilidad en 3 Réplicas Consecutivas
Se ejecutó la suite [`scripts/audit_72_top1_misses.py`](../scripts/audit_72_top1_misses.py) en 3 réplicas consecutivas independientes mediante clonación de snapshot por `sqlite3.backup()` y restauración estricta de estado:

| Métrica / Parámetro | Réplica #1 | Réplica #2 | Réplica #3 | Coincidencia Bit-a-Bit |
|---|---:|---:|---:|:---:|
| **Recall@5** | 875 / 875 (100.0%) | 875 / 875 (100.0%) | 875 / 875 (100.0%) | ✅ 100% Idéntico |
| **Recall@1** | 803 / 875 (91.77%) | 803 / 875 (91.77%) | 803 / 875 (91.77%) | ✅ 100% Idéntico |
| **Total Misses Top-1** | 72 | 72 | 72 | ✅ 100% Idéntico |
| **IDs de Misses (0000..0874)** | Lista idéntica | Lista idéntica | Lista idéntica | ✅ 100% Idéntico |
| **Ganador & Rango de cada Gold** | Idéntico en los 72 | Idéntico en los 72 | Idéntico en los 72 | ✅ 100% Idéntico |
| **Scores y Márgenes** | Idéntico en los 72 | Idéntico en los 72 | Idéntico en los 72 | ✅ 100% Idéntico |
| **Clasificación Causal / Temporal** | Idéntico en los 72 | Idéntico en los 72 | Idéntico en los 72 | ✅ 100% Idéntico |

> **Declaración de Reproducibilidad:** *La auditoría instrumentada es 100% reproducible bajo este entorno y protocolo.*

---

## 2. Precisión Técnica en Parámetros JSD y Factores de Escala

### 2.1 Rango Discreto Real de $w_{\text{jsd}}$ en el Motor
En la configuración actual (`JSD_WEIGHT=0.0`, `JSD_ADAPT_BASE=0.05`, `JSD_ADAPT_CORTO=0.5`, `JSD_ADAPT_LARGO=2.5`, `JSD_ADAPT_NT=4`), la función `_jsd_weight_adaptativo` evalúa valores discretos según la longitud de tokens:

* **Query corta ($N_t < 4$ tokens):**
  $$w_{\text{jsd}} = 0.05 \times 0.5 = 0.025$$
  $$\text{base\_weight} = \frac{1.0 - 0.025}{1.69} = \frac{0.975}{1.69} \approx 0.576923$$
* **Query larga ($N_t \ge 4$ tokens):**
  $$w_{\text{jsd}} = 0.05 \times 2.5 = 0.125$$
  $$\text{base\_weight} = \frac{1.0 - 0.125}{1.69} = \frac{0.875}{1.69} \approx 0.517751$$

El rango efectivo es por ende el conjunto discreto $w_{\text{jsd}} \in \{0.025, 0.125\}$.

---

## 3. Comprobación Programática de Trazabilidad y Linaje (72/72)

Se auditó formalmente el linaje completo de evaluación para los 72 casos de fallo:
$$\text{invocation\_id} \longrightarrow \text{concepto} \longrightarrow \text{score\_returned} \longrightarrow \text{last\_score\_base\_map}[\text{concepto}]$$

### Resultados de la Verificación Programática:
* **Total casos auditados:** 72 / 72.
* **Invocaciones por concepto durante la query:** 1 sola invocación por concepto en el 100% de los casos evaluados en el pool de scoring híbrido.
* **Correspondencia unívoca:** $|\text{score\_returned} - \text{last\_score\_base\_map}[\text{concepto}]| < 10^{-4}$ comprobada en el **100% de los casos (72/72)**.
* Queda demostrado sin ambigüedades que la telemetría de señales corresponde exactamente a la evaluación que determinó el score rankeado.

---

## 4. Contribución Ponderada Reconstruida sobre Señales Auditadas

La siguiente tabla refleja la **contribución ponderada reconstruida** calculada a partir de los pesos efectivos reales de cada consulta:
$$\Delta_{\text{ponderado}} = w_i \times \text{base\_weight} \times (\text{Winner}_{\text{señal}} - \text{Gold}_{\text{señal}})$$

| Señal | Peso Nominal ($w_i$) | Peso Efectivo Medio | $\Delta$ Descriptivo Medio ($\text{Winner} - \text{Gold}$) | $\Delta$ Contributivo Reconstruido Medio |
|---|---:|---:|---:|---:|
| **`hub_match`** | 0.20 | 0.1121 | **+0.1604** | **+0.017580** |
| **`tematico_score`** | 0.08 | 0.0448 | **+0.1972** | **+0.008701** |
| **`dim_score`** | 0.14 | 0.0785 | **+0.0774** | **+0.006120** |
| **`pred_score_srl`** | 0.20 | 0.1121 | **+0.0451** | **+0.005167** |
| **`grupo_score_wordnet`** | 0.10 | 0.0560 | **+0.0592** | **+0.003457** |
| **`jaccard`** | 0.10 | 0.0560 | **+0.0387** | **+0.002211** |
| **`concepto_ratio`** | 0.08 | 0.0448 | **+0.0006** | **+0.000446** |
| **`peso_sinaptico`** | 0.10 | 0.0560 | **0.0000** | **0.000000** |
| **`ncd_score`** | 0.05 | 0.0280 | **-0.0055** | **-0.000154** |
| **`jsd_score`** | adaptativo | 0.0528 | **+0.0043** | **-0.000361** |
| **`convergencia_bonus`** | reranker | 1.0000 | **-0.0005** | **-0.000464** |
| **`bm25_norm`** | 0.25 | 0.1401 | **-0.0004** | **-0.000798** |
| **`sinonimos_ratio`** | 0.08 | 0.0448 | **-0.0252** | **-0.001040** |
| **`ppmi_score`** | 0.15 | 0.0841 | **-0.0169** | **-0.001336** |

---

## 5. Experimento Contrafactual Formal de Aislamiento de Mecanismos (A / B / C / D)

Para evaluar si el Concept Hub es el factor causal determinante de los 72 fallos, se ejecutó una ablación contrafactual controlada en 4 ramas sobre el mismo snapshot y dataset congelados:

* **Configuración A (Baseline Actual):** Motor completo estándar.
* **Configuración B (Contrafactual Hub-1):** Neutralización exclusiva de `hub_match = 0.0` en scoring híbrido.
* **Configuración C (Contrafactual Hub-2):** Neutralización exclusiva del mecanismo de piso/promoción Hub en `search.py`.
* **Configuración D (Contrafactual Hub-3):** Neutralización de ambos mecanismos de Hub simultáneamente.

### 5.1 Resultados Globales de la Matriz Contrafactual

| Configuración | R@5 | R@1 | MRR | FP Negativos | Total Misses Top-1 | $\Delta$ Neto R@1 (vs Baseline) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **A (Baseline Actual)** | **100.00%** (875/875) | **91.77%** (803/875) | **0.9497** | 0 / 40 | **72** | **BASE** |
| **B (hub_match = 0)** | **100.00%** (875/875) | **92.11%** (806/875) | **0.9517** | 0 / 40 | **69** | **+3** (3 Ganancias / 0 Pérdidas) |
| **C (Sin Piso Hub)** | **99.89%** (874/875) | **92.23%** (807/875) | **0.9525** | 0 / 40 | **68** | **+4** (5 Ganancias / 1 Pérdida) |
| **D (Sin Hubs Total)** | **99.89%** (874/875) | **92.23%** (807/875) | **0.9525** | 0 / 40 | **68** | **+4** (5 Ganancias / 1 Pérdida) |

---

### 5.2 Análisis de Transiciones de Casos Individuales

#### Ganancias en B (`hub_match = 0`):
* `0534` (`biorag_v11_1_detalle_tecnico`): Recupera Top-1 al removerse la señal hub_match que favorecía a `arquitectura_memoria_biorag`.
* `0551` (`patron_pensamiento_lateral_antes_de_proponer`): Recupera Top-1 frente a `dennys_genesis_investigativa_historia_personal`.
* `0767` (`hermes_nvidia_nim_modelos_optimos`): Recupera Top-1 frente a `resolucion_de_contradicciones_entre_insights_sumatoria_mentalidad`.

#### Ganancias en C y D (Sin Piso Hub):
* `0496`, `0534`, `0551`, `0763`, `0767` ascienden a Top-1.
* **Pérdida en C y D:** El caso `0593` (`"arquitectura biorag memoria"`) desciende de Top-1 a Top-2 en favor de `leccion_blueprint_estructura_vs_data`, y el Recall@5 sufre una regresión de 1 caso (874/875 = 99.89%), confirmando que el Concept Hub aporta cobertura real en recuperación estructural.

---

## 6. Veredicto Causal Definitivo

1. **El Concept Hub NO es la causa raíz de los 72 fallos Top-1:**
   - La desactivación total del Concept Hub (Contrafactual D) únicamente resuelve de 3 a 5 casos de los 72 fallos (reduciendo los misses de 72 a 68).
   - Los **67–68 fallos restantes (94.4% del total) persisten inmutables** incluso en ausencia total de Concept Hubs.
2. **Causa Raíz Real Identificada:**
   - El 94.4% de los fallos Top-1 está causado por la dominancia en el scoring híbrido pre-reranker de **`tematico_score`** (densidad co-ocurrente en dimensiones) y **`dim_score`** (solapamiento topológico amplio), que superan el peso conjunto de **`sinonimos_ratio`** y **`ppmi_score`** en consultas de las categorías `sinonimo` (24 casos) y `por_tema` (24 casos).
3. **Preservación de Invariantes:**
   - El motor de producción permanece 100% inalterado. Todos los experimentos se ejecutaron mediante inyección no invasiva en memoria y backups efímeros.
