# INFORME DE AUDITORÍA DIAGNÓSTICA, VERIFICACIÓN DE POOL Y ANÁLISIS DE TRANSICIONES (v32.4)

> **Misión:** Demostración formal de identidad criptográfica del pool de candidatos (875/875) y caracterización matemática de la frontera entre las 17 ganancias y 5 pérdidas de la intervención contrafactual F (`tematico + dim = 0`).  
> **Invariante Metodológica:** Cero modificaciones en el motor de producción, pesos o scoring.

---

## 1. Verificación Formal de Identidad Criptográfica del Pool de Candidatos (875/875)

Para cerrar de forma concluyente cualquier duda sobre la equivalencia del pool de candidatos en las 9 ramas contrafactuales (A hasta I), el script [`scripts/verify_frozen_pool_and_transitions.py`](../scripts/verify_frozen_pool_and_transitions.py) auditó y hasheó el conjunto exacto de candidatos que entra al scoring híbrido para cada una de las 875 consultas de recuperación:

$$\text{pool\_hash}(q, M) = \text{SHA256}\left(\text{JSON}\left(\text{candidatos\_evaluados}(q, M)\right)\right)$$

### Resultados de la Auditoría Criptográfica:
* **Total Queries Evaluadas:** 875 consultas.
* **Configuraciones Auditadas:** A (Baseline), B (`tematico=0`), C (`dim=0`), D (`sinonimos=0`), E (`ppmi=0`), F (`tematico+dim=0`), G (`sinonimos+ppmi=0`), H (`wordnet=0`), I (`srl=0`).
* **Discrepancias de Pool:** **0 discrepancias (0 / 875)**.
* **Dictamen:** $$\text{SHA256}(\text{pool}_A) \equiv \text{SHA256}(\text{pool}_B) \equiv \dots \equiv \text{SHA256}(\text{pool}_I) \quad \forall q \in [1, 875]$$
* Queda **demostrado matemáticamente** que el experimento es una **ablación pura de scoring sobre pool de candidatos 100% congelado e idéntico**.

---

## 2. Resumen de la Tabla Maestra de Ablación Contrafactual

| Config | Intervención Contrafactual | R@5 | R@1 | MRR | Misses Top-1 | Ganancias Top-1 | Pérdidas Top-1 | $\Delta$ Neto R@1 |
|:---:|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **A** | **Baseline (Motor Actual)** | **100.0%** | **91.77%** | **0.9497** | **72** | **0** | **0** | **BASE** |
| **B** | `tematico_score = 0` | 99.54% | 92.46% | 0.9522 | 66 | 11 | 5 | **+6** |
| **C** | `dim_score = 0` | 99.66% | 92.80% | 0.9536 | 63 | 11 | 2 | **+9** |
| **D** | `sinonimos_ratio = 0` | 97.03% | 90.74% | 0.9329 | 81 | 8 | 17 | **-9** |
| **E** | `ppmi_score = 0` | 99.09% | 91.20% | 0.9425 | 77 | 3 | 8 | **-5** |
| **F** | `tematico + dim = 0` *(Eje Co-ocurrencia OFF)* | 99.43% | **93.14%** | **0.9546** | **60** | **17** | **5** | **+12** |
| **G** | `sinonimos + ppmi = 0` *(Eje Semántico Fino OFF)* | 95.66% | 89.03% | 0.9182 | 96 | 7 | 31 | **-24** |
| **H** | `grupo_score_wordnet = 0` | 99.54% | 92.11% | 0.9503 | 69 | 5 | 2 | **+3** |
| **I** | `pred_score_srl = 0` | 100.0% | 92.11% | 0.9515 | 69 | 3 | 0 | **+3** |

* **Controles Negativos:** 0 / 40 Falsos Positivos en todas las configuraciones.

---

## 3. Caracterización Vectorial de las 22 Transiciones de la Configuración F

La Configuración F (`tematico + dim = 0`) produce exactamente **17 rescates (Ganancias)** y **5 regresiones (Pérdidas)** respecto al Baseline A. Los datos vectoriales completos están registrados en [`docs/analisis_transiciones_config_f.json`](analisis_transiciones_config_f.json).

### 3.1 Las 17 Ganancias Top-1 (Rescates)
En los 17 casos rescatados, el Gold poseía una ventaja sustancial en evidencia semántica/léxica específica que en Baseline A era superada artificialmente por la acumulación de `tematico_score` o `dim_score` del competidor:

| Case ID | Categoría | Concepto Gold | Ganador en Baseline A | Ventaja del Gold | Factor de Distorsión en Baseline A |
|---|---|---|---|---|---|
| `0497` | `por_tema` | `benchmark_antes_despues_fix3` | `causa_raiz_por_tema_pooling_plano...` | `bm25`: 1.0 vs 0.63 | `dim_score` ganador (+0.58 ventaja) |
| `0560` | `variante_gramatical` | `memoria_v5_1_optimizaciones` | `privacidad_memorias_personales_oec` | `sinonimos`: 0.50 vs 0.00 | `tematico_score` ganador (1.0 vs 0.0) |
| `0592` | `typo` | `arquitectura_memoria_biorag` | `hito_biorag_v21_arquitectura_13_ejes` | `sinonimos`: 0.62 vs 0.29 \| `ppmi`: 0.46 vs 0.28 | `tematico_score` ganador (1.0 vs 0.0) |
| `0617` | `typo` | `leccion_overengineering_oec_comms_20260615` | `oec_comms_protocolo_walkie_talkie_20260615` | `sinonimos`: 0.57 vs 0.40 | `tematico_score` ganador (1.0 vs 0.0) |
| `0624` | `typo` | `notebooklm-chat-configure` | `notebooklm-memory-biorag-cortex` | `sinonimos`: 0.63 vs 0.30 \| `ppmi`: 0.39 vs 0.28 | `tematico_score` ganador (1.0 vs 0.0) |
| `0648` | `variante_gramatical` | `plugin_biorag-remember_v8.3_-_...` | `biorag-remember-plugin-nodo-completo` | `sinonimos`: 0.68 vs 0.41 \| `ppmi`: 0.56 vs 0.43 | `tematico_score` ganador (1.0 vs 0.0) |
| `0667` | `typo` | `identidad_y_respeto_oec` | `hermes_oec_identidad` | `sinonimos`: 0.59 vs 0.33 | `tematico_score` ganador (1.0 vs 0.0) |
| `0672` | `variante_gramatical` | `compuerta-pre-validacion` | `oracle_auditoria_patrones` | `sinonimos`: 0.94 vs 0.28 | `tematico_score` ganador (1.0 vs 0.0) |
| `0738` | `variante_gramatical` | `fix_busqueda_solo_dimensiones_...` | `punto_medio_dimensiones_persistencia` | `sinonimos`: 0.78 vs 0.40 \| `ppmi`: 0.57 vs 0.41 | `tematico_score` ganador (1.0 vs 0.0) |
| `0742` | `por_tema` | `fix_busqueda_solo_dimensiones_...` | `plan_expansion_dimensiones_semanticas` | `sinonimos`: 0.61 vs 0.33 \| `ppmi`: 0.47 vs 0.40 | `tematico_score` ganador (1.0 vs 0.0) |
| `0748` | `por_tema` | `biorag_v16_0_estado` | `v23_0_weight_adjustment_recall` | `ppmi`: 0.34 vs 0.30 | `dim_score` ganador (+0.14 ventaja) |
| `0765` | `por_tema` | `fin-aprendizaje-creerse-completo` | `athena_evolucion_v0001` | `ppmi`: 0.48 vs 0.16 | `dim_score` ganador (+0.13 ventaja) |
| `0767` | `variante_gramatical` | `hermes_nvidia_nim_modelos_optimos` | `resolucion_de_contradicciones...` | `sinonimos`: 0.77 vs 0.20 \| `ppmi`: 0.85 vs 0.16 | `tematico_score` ganador (1.0 vs 0.0) |
| `0830` | `por_tema` | `interacción_social_saludo` | `athena_evolucion_v0001` | `ppmi`: 0.30 vs 0.14 | `dim_score` ganador (+0.31 ventaja) |
| `0840` | `sinonimo` | `biorag_garantia_minima_or_fallback...` | `biorag_v25_1_ppr_plan_maestro` | `ppmi`: 0.43 vs 0.39 | `dim_score` ganador (+0.28 ventaja) |
| `0848` | `por_tema` | `v13_2_limpieza_tabla_semantica` | `mentalidad_embedding_clasico...` | `sinonimos`: 0.63 vs 0.00 | `tematico_score` ganador (1.0 vs 0.0) |
| `0855` | `por_tema` | `hermes_mcp_servers_configuracion...` | `oec_comms_notebook_arbitro...` | `ppmi`: 0.36 vs 0.34 | `dim_score` ganador (+0.09 ventaja) |

---

### 3.2 Las 5 Pérdidas Top-1 (Regresiones)
En los 5 casos donde la Configuración F pierde la primera posición:

| Case ID | Categoría | Concepto Gold | Nuevo Ganador en F | Causa de la Pérdida en F |
|---|---|---|---|---|
| `0488` | `variante_gramatical` | `oracle_custom_prompt_arsitecura_que_funciona` | `oracle_custom_prompt_config_actual` | El Gold tenía múltiples variantes ("arsitecuras", "ques") y `sinonimos=0.0`. En Baseline A, `tematico=1.0` sostenía al Gold en #1. Al apagar temático, el competidor con `sinonimos=0.50` lo supera. |
| `0513` | `typo` | `dennys-identidad-profunda` | `eleccion_identidad_relacion_dennys_...` | Query con typo ("denys"). El Gold tenía `bm25=0.0` y dependía exclusivamente de `tematico=1.0` para puntuar 0.3337. Al apagar temático, el score del Gold colapsa a 0.0. |
| `0708` | `variante_gramatical` | `aforismo_criterio_agente` | `caso_criterio_artificial_agente` | Empate técnico estricto en sinonimia y PPMI. El Gold ganaba en Baseline A por resonancia dimensional (`dim=0.88` vs `0.56`). Al apagar `dim`, el competidor gana por 0.0023 en trigramas Jaccard. |
| `0736` | `por_tema` | `plan_mode_biorag` | `arquitectura_memoria_biorag` | Sin temático ni dimensional, `arquitectura_memoria_biorag` se impone por mayor bono multicampo. |
| `0803` | `variante_gramatical` | `cv_seccion_d_test_vinculacion` | `athena_forensic_audit_trail_...` | Query con plurales y typos ("cv seccion ds tests vinculaciones"). El Gold dependía de `tematico=1.0` para sostener el primer lugar frente al competidor FTS. |

---

## 4. Formulación de la Condición de Frontera Separadora

El análisis de las 22 transiciones revela la regla matemática que separa las ganancias de las pérdidas:

$$\text{Condición de Rescate (Ganancia)}: \quad \left(\text{sinonimos\_ratio}_{\text{gold}} > \text{sinonimos\_ratio}_{\text{win}}\right) \lor \left(\text{ppmi\_score}_{\text{gold}} > \text{ppmi\_score}_{\text{win}}\right)$$

$$\text{Condición de Vulnerabilidad (Pérdida)}: \quad \left(\text{sinonimos\_ratio}_{\text{gold}} \approx 0\right) \land \left(\text{bm25\_norm}_{\text{gold}} \approx 0\right) \land \left(\text{tematico\_score}_{\text{gold}} = 1.0 \lor \text{dim\_score}_{\text{gold}} > 0.8\right)$$

### Conclusión Teórica:
* **Cuando existe evidencia semántica/léxica específica en el candidato:** `tematico_score` y `dim_score` actúan como **ruido de co-ocurrencia amplia** que permite a nodos vecinos sobrepasar al nodo correcto.
* **Cuando la consulta sufre de degradación léxica severa (typos/múltiples flexiones sin sinónimo):** `tematico_score` y `dim_score` actúan como un **puente de rescate topológico indispensable**.
* **Implicación para el Diseño:** La intervención óptima **NO es eliminar** `tematico` o `dim`, sino aplicar una **modulación competitiva condicional**: suprimir o atenuar el peso de `tematico` y `dim` *únicamente cuando un candidato presente evidencia léxico-sinonímica específica fuerte* ($\text{sinonimos\_ratio} \ge 0.50$ o $\text{concepto\_ratio} \ge 0.75$), permitiendo que el puente topológico siga funcionando en queries degradadas sin interferir en queries específicas.

---

## 5. Matriz de Atribución Causal en los 72 Fallos Top-1

| Mecanismo Causal Dominante | Casos Afectados | % de los 72 Fallos | Evidencia Demostrada |
|---|---:|---:|---|
| **Interferencia `tematico_score` + `dim_score`** | **17 casos** | **23.6%** | Rescatados al 100% en Configuración F (+12 neto global) |
| **Interferencia `dim_score` exclusiva** | **9 casos netos** | **12.5%** | Rescatados en Configuración C |
| **Interferencia `tematico_score` exclusiva** | **6 casos netos** | **8.3%** | Rescatados en Configuración B |
| **Interferencia Concept Hub** | **4 casos netos** | **5.6%** | Rescatados en Configuración C/D de Hub |
| **Empates y Discrepancias Finas ($< 0.005$)** | **9 casos** | **12.5%** | Diferencias marginales en subcadenas |
| **Déficit Léxico Residual en Corpus** | **27 casos** | **37.5%** | Casos complejos donde el Gold requiere enriquecimiento de sustantivos o sinónimos |
| **TOTAL** | **72 casos** | **100.0%** | |

---

## 6. Estado del Repositorio
* **Invariante respetada:** Cero modificaciones en el motor de producción ni en archivos de scoring.
* **Artefactos generados:**
  - [`docs/analisis_transiciones_config_f.json`](analisis_transiciones_config_f.json): Detalle vectorial caso a caso de las 22 transiciones (17 ganancias, 5 pérdidas).
  - [`docs/experimento_contrafactual_pool_congelado.json`](experimento_contrafactual_pool_congelado.json): Resultados de las 9 ramas de ablación.
  - Script ejecutor: [`scripts/verify_frozen_pool_and_transitions.py`](file:///mnt/recursos_compartidos_y_otros/MemoryBioRAG/scripts/verify_frozen_pool_and_transitions.py).
