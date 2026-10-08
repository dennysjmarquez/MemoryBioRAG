# INFORME DE AUDITORÍA DIAGNÓSTICA, VERIFICACIÓN DE POOL Y ANÁLISIS DE TRANSICIONES (v32.5)

> **Misión:** Registro reproducible de la verificación de identidad del pool observado (875/875) y análisis detallado de las 22 transiciones (17 ganancias y 5 pérdidas) de la intervención contrafactual F (`tematico + dim = 0`).  
> **Invariante Metodológica:** Cero modificaciones en el motor de producción, pesos o scoring.

---

## 1. Verificación de Identidad de Secuencia de Candidatos en Scoring (875/875)

El script [`scripts/verify_frozen_pool_and_transitions.py`](../scripts/verify_frozen_pool_and_transitions.py) auditó y hasheó la secuencia exacta de conceptos que ingresaron a `_calcular_score_hibrido()` para cada una de las 875 consultas a través de 9 configuraciones contrafactuales (A hasta I):

$$\text{pool\_hash}(q, M) = \text{SHA256}\left(\text{JSON}\left(\text{candidatos\_observados\_en\_scoring}(q, M)\right)\right)$$

### Resultados de la Verificación:
* **Total de Consultas Evaluadas:** 875 consultas.
* **Configuraciones Auditadas:** A (Baseline), B (`tematico=0`), C (`dim=0`), D (`sinonimos=0`), E (`ppmi=0`), F (`tematico+dim=0`), G (`sinonimos+ppmi=0`), H (`wordnet=0`), I (`srl=0`).
* **Discrepancias de Secuencia Observada:** **0 discrepancias (0 / 875)**.
* **Conclusión Técnica:** Se verificó la identidad de la secuencia de conceptos observados en las llamadas al scoring híbrido mediante SHA-256 en 875/875 consultas entre todas las configuraciones A–I.
* Los cambios observados en el ranking corresponden estrictamente a la intervención en las funciones de ponderación de scoring sobre el conjunto de candidatos observado.

---

## 2. Resumen de la Tabla Maestra de Ablaciones Contrafactuales

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

## 3. Matriz Vectorial Real de las 22 Transiciones de la Configuración F

Los datos a continuación provienen directamente del artefacto verificado [`docs/analisis_transiciones_config_f.json`](analisis_transiciones_config_f.json).

### 3.1 Las 17 Ganancias (Rescates Top-1 en F)

| Case ID | Categoría | Concepto Gold | Ganador Baseline A | BM25 (G / W) | Sinónimos (G / W) | PPMI (G / W) | DIM (G / W) | Temático (G / W) | Margen A (G - W) | Margen F (G - W) |
|:---|:---|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `0497` | `por_tema` | `benchmark_antes_despues_fix3` | `causa_raiz_por_tema_pooling_plano_diluye_senal_word2vec` | 1.00 / 0.63 | 0.00 / 0.00 | 0.48 / 0.50 | 0.30 / 0.88 | 1.00 / 1.00 | -0.0182 | 0.0000 *(Tie)* |
| `0560` | `variante_gramatical` | `memoria_v5_1_optimizaciones` | `privacidad_memorias_personales_oec` | 0.92 / 1.00 | 0.50 / 0.00 | 0.00 / 0.00 | 0.50 / 0.43 | 0.00 / 1.00 | -0.0055 | 0.0000 *(Tie)* |
| `0592` | `typo` | `arquitectura_memoria_biorag` | `hito_biorag_v21_arquitectura_13_ejes` | 0.94 / 0.86 | 0.62 / 0.29 | 0.46 / 0.28 | 0.39 / 0.76 | 0.00 / 1.00 | -0.0213 | 0.0000 *(Tie)* |
| `0617` | `typo` | `leccion_overengineering_oec_comms_20260615` | `oec_comms_protocolo_walkie_talkie_20260615` | 0.97 / 0.97 | 0.57 / 0.40 | 0.58 / 0.74 | 0.76 / 0.65 | 0.00 / 1.00 | -0.0327 | 0.0000 *(Tie)* |
| `0624` | `typo` | `notebooklm-chat-configure` | `notebooklm-memory-biorag-project` | 0.76 / 0.76 | 0.63 / 0.30 | 0.39 / 0.28 | 0.00 / 0.00 | 0.00 / 1.00 | -0.0001 | 0.0000 *(Tie)* |
| `0648` | `variante_gramatical` | `plugin_biorag-remember_v8.3_-_adaptación_de_dennys_+_claude` | `biorag-remember-plugin-noreply-injection` | 0.92 / 1.00 | 0.68 / 0.41 | 0.56 / 0.43 | 0.50 / 0.56 | 0.00 / 1.00 | -0.0028 | 0.0000 *(Tie)* |
| `0667` | `typo` | `identidad_y_respeto_oec` | `hermes_oec_identidad` | 0.00 / 0.00 | 0.59 / 0.33 | 0.72 / 0.73 | 0.30 / 0.43 | 0.00 / 1.00 | -0.0460 | 0.0000 *(Tie)* |
| `0672` | `variante_gramatical` | `compuerta-pre-validacion` | `oracle_auditoria_patrones_mejora_athena` | 0.72 / 0.64 | 0.94 / 0.28 | 0.66 / 0.62 | 0.00 / 0.00 | 0.00 / 1.00 | -0.0158 | 0.0000 *(Tie)* |
| `0738` | `variante_gramatical` | `fix_busqueda_solo_dimensiones_sin_texto` | `punto_medio_dimensiones_parciales_mueven_ranking_sdm` | 1.00 / 0.86 | 0.78 / 0.40 | 0.57 / 0.41 | 0.32 / 0.63 | 0.00 / 1.00 | -0.0002 | 0.0000 *(Tie)* |
| `0742` | `por_tema` | `fix_busqueda_solo_dimensiones_sin_texto` | `plan_expansion_dimensiones_8_tipos_34_valores` | 1.00 / 0.84 | 0.61 / 0.33 | 0.47 / 0.40 | 0.35 / 0.50 | 0.00 / 1.00 | -0.0191 | 0.0000 *(Tie)* |
| `0748` | `por_tema` | `biorag_v16_0_estado` | `v23_0_weight_adjustment_resultados_validados` | 1.00 / 0.69 | 0.00 / 0.00 | 0.34 / 0.30 | 0.59 / 0.73 | 1.00 / 1.00 | -0.0022 | 0.0000 *(Tie)* |
| `0765` | `por_tema` | `fin-aprendizaje-creerse-completo` | `athena_evolucion_v0001` | 1.00 / 0.63 | 0.00 / 0.00 | 0.48 / 0.16 | 0.50 / 0.63 | 1.00 / 1.00 | -0.0040 | 0.0000 *(Tie)* |
| `0767` | `variante_gramatical` | `hermes_nvidia_nim_modelos_optimos` | `resolucion_de_contradicciones_entre_insights_sumatoria_mentalidad` | 0.55 / 1.00 | 0.77 / 0.20 | 0.85 / 0.16 | 0.41 / 0.35 | 0.00 / 1.00 | -0.0185 | 0.0000 *(Tie)* |
| `0830` | `por_tema` | `interacción_social_saludo` | `athena_evolucion_v0001` | 1.00 / 0.74 | 0.00 / 0.26 | 0.30 / 0.14 | 0.43 / 0.74 | 1.00 / 1.00 | -0.0026 | 0.0000 *(Tie)* |
| `0840` | `sinonimo` | `biorag_garantia_minima_or_fallback` | `biorag_v25_1_ppr_plan_maestro_pendiente` | 1.00 / 0.91 | 1.00 / 1.00 | 0.43 / 0.39 | 0.46 / 0.74 | 0.00 / 0.00 | -0.0050 | 0.0000 *(Tie)* |
| `0848` | `por_tema` | `v13_2_limpieza_tabla_semantica` | `mentalidad_embedding_clasificacion_dimensional` | 0.78 / 1.00 | 0.63 / 0.00 | 0.00 / 0.00 | 0.35 / 0.42 | 0.00 / 1.00 | -0.0145 | 0.0000 *(Tie)* |
| `0855` | `por_tema` | `hermes_mcp_servers_configuracion` | `oec_comms_notebook_arbitro_20260615` | 1.00 / 1.00 | 0.00 / 0.00 | 0.36 / 0.34 | 0.91 / 1.00 | 1.00 / 1.00 | -0.0012 | 0.0000 *(Tie)* |

---

### 3.2 Las 5 Pérdidas (Regresiones Top-1 en F)

| Case ID | Categoría | Concepto Gold | Nuevo Ganador en F | BM25 (G / W_F) | Sinónimos (G / W_F) | PPMI (G / W_F) | DIM (G / W_F) | Temático (G / W_F) | Margen A (G - W_F) | Margen F (G - W_F) |
|:---|:---|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `0488` | `variante_gramatical` | `oracle_custom_prompt_arsitecura_que_funciona` | `oracle_custom_prompt_config_actual` | 0.95 / 1.00 | 0.00 / 0.50 | 0.68 / 0.62 | 0.44 / 0.50 | 1.00 / 0.00 | +0.0480 | -0.0327 |
| `0513` | `typo` | `dennys-identidad-profunda` | `eleccion_identidad_relacion_dennys_20260616` | 0.00 / 0.00 | 0.00 / 0.61 | 0.29 / 0.56 | 0.00 / 0.00 | 1.00 / 0.00 | +0.0791 | -0.3014 |
| `0708` | `variante_gramatical` | `aforismo_criterio_agente` | `caso_criterio_artificial_agente` | 1.00 / 0.97 | 0.67 / 0.67 | 0.67 / 0.68 | 0.88 / 0.57 | 0.00 / 0.00 | +0.0703 | -0.0023 |
| `0736` | `por_tema` | `plan_mode_biorag` | `arquitectura_memoria_biorag` | 1.00 / 0.24 | 0.00 / 0.00 | 0.52 / 0.25 | 0.35 / 0.42 | 1.00 / 1.00 | +0.0791 | -0.0690 |
| `0803` | `variante_gramatical` | `cv_seccion_d_test_vinculacion` | `athena_forensic_audit_trail_ltd_detection_fix` | 1.00 / 0.93 | 0.20 / 0.00 | 0.62 / 0.12 | 0.35 / 0.49 | 1.00 / 1.00 | +0.0971 | -0.2506 |

---

## 4. Análisis de la Interacción Competitiva entre Señales

El análisis empírico de las 22 transiciones demuestra que:

1. **No existe una regla separadora simple basada únicamente en $\text{sinonimos} > \text{winner}$ o $\text{PPMI} > \text{winner}$:**
   - El caso `0497` es un contraejemplo directo: tanto Gold como Winner tienen `sinonimos = 0.0` y el Winner supera a Gold en PPMI (`0.50` vs `0.48`). El rescate en F ocurre porque Gold supera ampliamente al Winner en BM25 (`1.0` vs `0.63`), pero en Baseline A el Winner ganaba debido a una ventaja dimensional artificial (`DIM = 0.88` vs `0.30`).
2. **Las pérdidas en F no se deben únicamente a ausencia de evidencia léxica:**
   - 4 de las 5 pérdidas (`0488`, `0708`, `0736`, `0803`) tienen $\text{BM25}_{\text{gold}} \ge 0.947$.
   - En `0708`, el Gold dependía legítimamente de su resonancia dimensional (`0.88` vs `0.57`) para desempatar a su favor. Al apagar `dim_score`, cae ante un competidor prácticamente empatado.
   - Solo `0513` representa una consulta con fallo léxico total (`BM25 = 0.0`), donde `tematico_score` actuaba como mecanismo de rescate necesario.

### Conclusión Arquitectónica:
`tematico_score` y `dim_score` son señales de afinidad amplia valiosas para la desambiguación y rescate en ausencia de señales concluyentes, pero pueden generar interferencia en el ranking cuando sobrecompensan sobre candidatos que ya poseen evidencia léxico-semántica específica superior.

---

## 5. Caracterización de las Intervenciones Contrafactuales

Las intervenciones evaluadas (A–I) representan sondas contrafactuales con efectos superpuestos, no categorías mutuamente excluyentes:

* **Efecto de apagar `tematico_score` (B):** Rescata 11 casos y pierde 5 ($\Delta = +6$).
* **Efecto de apagar `dim_score` (C):** Rescata 11 casos y pierde 2 ($\Delta = +9$).
* **Efecto conjunto `tematico + dim = 0` (F):** Rescata 17 casos y pierde 5 ($\Delta = +12$, R@1 alcanza 93.14%).
* **Efecto de apagar `sinonimos_ratio` (D) o `ppmi_score` (E):** Deteriora severamente el rendimiento (hasta -24 en G), confirmando que son pilares semánticos esenciales.

---

## 6. Siguiente Paso: Diseño de Gate Competitivo con Split Determinista

Para evaluar una modulación contextual competitiva sin sobreajuste ni optimización circular:
1. **Split Determinista y Congelado:** Se dividirá el dataset de 875 consultas en **Discovery (50%)** y **Validation (50%)**, estratificado únicamente por categoría de consulta y estado baseline (Top-1 Hit / Miss), **sin utilizar el resultado de la ablación F para construir la partición**.
2. **Espacio de Diseño:** La regla de modulación deberá ser puramente *competitiva* (relativa entre candidatos), atenuando la ventaja de señales amplias únicamente cuando el competidor presente una desventaja en evidencia específica (BM25, sinónimos, PPMI).
3. **Validación Ciega:** La formulación se fijará en el conjunto Discovery y se validará exactamente una vez en Validation.
4. **Invariante:** Cero modificaciones en el motor de producción.

---

## 7. Estado de Archivos y Artefactos

* [`docs/analisis_transiciones_config_f.json`](analisis_transiciones_config_f.json): Contiene los 22 vectores exactos verificados.
* [`docs/experimento_contrafactual_pool_congelado.json`](experimento_contrafactual_pool_congelado.json): Registro de las 9 configuraciones contrafactuales A–I.
* [`scripts/verify_frozen_pool_and_transitions.py`](file:///mnt/recursos_compartidos_y_otros/MemoryBioRAG/scripts/verify_frozen_pool_and_transitions.py): Script de verificación y auditoría de hashes.
