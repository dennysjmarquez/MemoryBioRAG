# Fase 4.2 — Focalización Estructural vs Grafo (Prototipo Aislado)

**Fecha:** 2026-09-05  
**Criterio FP canónico:** `score_top1 > 2.0` (unificado con Fase 3.2 y 4.1)  
**Snapshot:** `snapshots/qa_escape_qcr_20260811.db` (Read-Only)  
**Total queries OOS evaluadas:** 30  
**Veredicto Oficial:** **A — Focalización estructural suficiente sin grafo (M1 conserva rescates con 0.0% FP; el grafo no aporta valor neto).**

---

## 1. TABLA COMPARATIVA PRINCIPAL (M0 a M4)

| Modo | Configuración | Test R@5 | Transfer R@5 | Paraphrase R@5 | Corpus Shift R@5 | Total Rescates | Hard-Neg FP (>2.0) |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **M0** | FTS/BM25 baseline puro | 0/8 (0.0%) | 0/8 (0.0%) | 0/8 (0.0%) | 0/6 (0.0%) | **0/30 (0.0%)** | **0/60 (0.0%)** |
| **M1** | Frame + Predicate + Focalization (SIN grafo) | 2/8 (25.0%) | 1/8 (12.5%) | 1/8 (12.5%) | 1/6 (16.67%) | **5/30 (16.7%)** | **0/60 (0.0%)** |
| **M2** | M1 + SINONIMO_DE físico (restringido) | 2/8 (25.0%) | 1/8 (12.5%) | 1/8 (12.5%) | 1/6 (16.67%) | **5/30 (16.7%)** | **11/60 (18.33%)** |
| **M3** | M1 + Aristas derivadas tipadas (restringido) | 2/8 (25.0%) | 1/8 (12.5%) | 1/8 (12.5%) | 1/6 (16.67%) | **5/30 (16.7%)** | **6/60 (10.0%)** |
| **M4** | M1 + Spreading activation completo | 2/8 (25.0%) | 1/8 (12.5%) | 2/8 (25.0%) | 1/6 (16.67%) | **6/30 (20.0%)** | **11/60 (18.33%)** |

---

## 2. COMPARACIONES DIRECTAS

### A) M1 vs M2 (Aporte de SINONIMO_DE Físico)
- **Rescates nuevos en M2:** 0 []
- **Rescates perdidos en M2:** 0 []
- **Cambios de Rank:** 2 casos
- **FPs nuevos en M2:** 11 casos
- **FPs eliminados en M2:** 0 casos

### B) M1 vs M3 (Aporte de Aristas Derivadas Tipadas)
- **Rescates nuevos en M3:** 0 []
- **Rescates perdidos en M3:** 0 []
- **Cambios de Rank:** 1 casos
- **FPs nuevos en M3:** 6 casos
- **FPs eliminados en M3:** 0 casos

### C) M1 vs M4 (Aporte de Spreading Activation Completo)
- **Rescates nuevos en M4:** 1 [{'id': 'PRF_08', 'query': 'sincronizacion lecciones sync integracion', 'gold': 'notebooklm-memory-biorag-project', 'rank_base': 12, 'rank_target': 4}]
- **Rescates perdidos en M4:** 0 []
- **Cambios de Rank:** 2 casos
- **FPs nuevos en M4:** 11 casos
- **FPs eliminados en M4:** 0 casos

---

## 3. MÉTRICAS ADICIONALES DE GENERALIZACIÓN

### A) Detección de clase sin trigger léxico en el gold
Total casos evaluados donde el gold no comparte tokens de la query: **26**
- Casos donde M1 recupera en Top-5: **5/26**

### B) Hard-Negatives con >= 2 triggers
Total evaluados: **47**
- FPs bajo M1: **0/47**
- FPs bajo M4 (Grafo): **9/47**

### C) Corpus-Shift (Cambio superficial de vocabulario)
Total evaluados: **6**
- R@5 M0: **0/6**
- R@5 M1: **1/6**
- R@5 M2: **1/6**

---

## 4. REGISTRO DETALLADO POR QUERY OOS (M1 / M2)

### [0002] `que debo hacer antes de modificar`
- **Gold:** `protocolo_de_seguridad_modificacion_codigo`
- **Rank M1:** None | **Score Gold:** 0.0 | **In Top-5:** ✗
- **Frame:** `['PROCEDIMIENTO']` / `['NORMA']` / `['OBLIGATORIA']`
- **Predicados:** `['NORMA']`
- **Top Candidatos:** `['protocolo_resolucion_incertidumbre_agente', 'identificacion_obligatoria_oracculo_dominio_por_agente', 'protocolo-reproducible-ingenieria-inversa-binario-compilado']`
- **Ruta:** `STRUCTURAL_FOCALIZATION_NO_GRAPH` | **Propagación:** False | **Física:** False | **Derivada:** False

### [0003] `pasos para crear un backup antes de tocar el codigo`
- **Gold:** `protocolo_de_seguridad_modificacion_codigo`
- **Rank M1:** None | **Score Gold:** 0.0 | **In Top-5:** ✗
- **Frame:** `['PROCEDIMIENTO']` / `['NORMA']` / `['DESCRIPTIVA']`
- **Predicados:** `['NORMA']`
- **Top Candidatos:** `['identificacion_obligatoria_oracculo_dominio_por_agente', 'protocolo_scripts_utilitarios', 'protocolo_estados_emocionales']`
- **Ruta:** `STRUCTURAL_FOCALIZATION_NO_GRAPH` | **Propagación:** False | **Física:** False | **Derivada:** False

### [0258] `evaluacion del rendimiento de algoritmos en python`
- **Gold:** `benchmark_algoritmos_rendimiento_python`
- **Rank M1:** None | **Score Gold:** 0.0 | **In Top-5:** ✗
- **Frame:** `['EVALUACION']` / `['EVALUACION']` / `['DESCRIPTIVA']`
- **Predicados:** `['EVALUACIÓN']`
- **Top Candidatos:** `['benchmark_sinonimo_integrado', 'evaluacion_ideas_evolucion_20260805_interferencia_agujeros_permutacion', 'dennys_perfil_tecnico_consolidado_master']`
- **Ruta:** `STRUCTURAL_FOCALIZATION_NO_GRAPH` | **Propagación:** False | **Física:** False | **Derivada:** False

### [0403] `parche aplicado para resolver la vulnerabilidad`
- **Gold:** `fix_vulnerabilidad_inyeccion_sql`
- **Rank M1:** None | **Score Gold:** 0.0 | **In Top-5:** ✗
- **Frame:** `['CORRECCION']` / `['FIX']` / `['DESCRIPTIVA']`
- **Predicados:** `['CORRECCIÓN']`
- **Top Candidatos:** `['fix_kilo_resource_exhausted_biorag_oraculo_max_chars', 'fix_fecha_sin_query_recordar', 'fix_mensajeria_broadcast_tracking_por_agente']`
- **Ruta:** `STRUCTURAL_FOCALIZATION_NO_GRAPH` | **Propagación:** False | **Física:** False | **Derivada:** False

### [0467] `quien es el creador real de athena`
- **Gold:** `dennys_creador_de_athena_identidad`
- **Rank M1:** None | **Score Gold:** 0.0 | **In Top-5:** ✗
- **Frame:** `['IDENTIDAD']` / `['IDENTIDAD']` / `['DESCRIPTIVA']`
- **Predicados:** `['IDENTIDAD']`
- **Top Candidatos:** `['dennys_principio_documentar_dudas_resueltas_auto', 'dennys_principio_no_danar_conjunto_completo_objetivo_local_20260807', 'dennys_memoria_para_todos_los_agentes_del_mundo']`
- **Ruta:** `STRUCTURAL_FOCALIZATION_NO_GRAPH` | **Propagación:** False | **Física:** False | **Derivada:** False

### [0534] `activa largo archivos`
- **Gold:** `biorag_v11_1_detalle_tecnico`
- **Rank M1:** 1 | **Score Gold:** 0.37112 | **In Top-5:** ✓
- **Frame:** `[]` / `['DETALLE_TECNICO']` / `['DESCRIPTIVA']`
- **Predicados:** `['DETALLE_TECNICO']`
- **Top Candidatos:** `['biorag_v11_1_detalle_tecnico', 'dennys_perfil_tecnico_consolidado_master', 'artemis_sesion_v10_3_optimizacion_completa']`
- **Ruta:** `STRUCTURAL_FOCALIZATION_NO_GRAPH` | **Propagación:** False | **Física:** False | **Derivada:** False

### [0795] `mejor tiempo de respuesta obtenido en pruebas`
- **Gold:** `benchmark_algoritmos_rendimiento_python`
- **Rank M1:** None | **Score Gold:** 0.0 | **In Top-5:** ✗
- **Frame:** `['EVALUACION']` / `['EVALUACION']` / `['DESCRIPTIVA']`
- **Predicados:** `['EVALUACIÓN']`
- **Top Candidatos:** `['benchmark_sinonimo_integrado', 'benchmark_antes_despues_fix3', 'reconocimiento_identidad_oraculo_manifiesto']`
- **Ruta:** `STRUCTURAL_FOCALIZATION_NO_GRAPH` | **Propagación:** False | **Física:** False | **Derivada:** False

### [0801] `datos lecciones postsync`
- **Gold:** `notebooklm-memory-biorag-project`
- **Rank M1:** 2 | **Score Gold:** 0.33774 | **In Top-5:** ✓
- **Frame:** `['INTEGRACION', 'APRENDIZAJE']` / `['SYNC', 'COGNITIVO']` / `['DESCRIPTIVA']`
- **Predicados:** `['INTEGRACIÓN', 'APRENDIZAJE']`
- **Top Candidatos:** `['notebooklm-sync-protocol', 'notebooklm-memory-biorag-project', 'notebooklm-sync-lecciones']`
- **Ruta:** `STRUCTURAL_FOCALIZATION_NO_GRAPH` | **Propagación:** False | **Física:** False | **Derivada:** False

### [TRF_01] `evaluacion y metrica de escalabilidad promedio`
- **Gold:** `analisis_escalabilidad_10k_v5_1`
- **Rank M1:** 4 | **Score Gold:** 0.24097 | **In Top-5:** ✓
- **Frame:** `['EVALUACION']` / `['EVALUACION']` / `['DESCRIPTIVA']`
- **Predicados:** `['EVALUACIÓN']`
- **Top Candidatos:** `['evaluacion_ideas_evolucion_20260805_interferencia_agujeros_permutacion', 'evaluacion_reviews_externos_biorag', 'benchmark_antes_despues_fix3']`
- **Ruta:** `STRUCTURAL_FOCALIZATION_NO_GRAPH` | **Propagación:** False | **Física:** False | **Derivada:** False

### [TRF_02] `resolucion de bug en modulo de sincronizacion remota`
- **Gold:** `fix_sync_incremental_crash_v3`
- **Rank M1:** None | **Score Gold:** 0.0 | **In Top-5:** ✗
- **Frame:** `['CORRECCION', 'INTEGRACION']` / `['FIX', 'SYNC']` / `['DESCRIPTIVA']`
- **Predicados:** `['CORRECCIÓN', 'INTEGRACIÓN']`
- **Top Candidatos:** `['fix_busqueda_solo_dimensiones_sin_texto', 'fix_mensajeria_broadcast_tracking_por_agente', 'notebooklm-sync-protocol']`
- **Ruta:** `STRUCTURAL_FOCALIZATION_NO_GRAPH` | **Propagación:** False | **Física:** False | **Derivada:** False

### [TRF_03] `protocolo obligatorio para despliegues en produccion`
- **Gold:** `norma_despliegue_cero_downtime`
- **Rank M1:** None | **Score Gold:** 0.0 | **In Top-5:** ✗
- **Frame:** `['PROCEDIMIENTO']` / `['NORMA']` / `['OBLIGATORIA']`
- **Predicados:** `['NORMA']`
- **Top Candidatos:** `['protocolo-reproducible-ingenieria-inversa-binario-compilado', 'protocolo_parafrasis_uso', 'integracion_parafrasis_rafaga_obligatoria_v11_3']`
- **Ruta:** `STRUCTURAL_FOCALIZATION_NO_GRAPH` | **Propagación:** False | **Física:** False | **Derivada:** False

### [TRF_04] `quien es el artifice de la arquitectura neuronal`
- **Gold:** `dennys_autor_arquitectura_biorag`
- **Rank M1:** None | **Score Gold:** 0.0 | **In Top-5:** ✗
- **Frame:** `['IDENTIDAD']` / `['IDENTIDAD']` / `['DESCRIPTIVA']`
- **Predicados:** `['IDENTIDAD']`
- **Top Candidatos:** `['dennys_component_organization_methodology', 'dennys_genesis_investigativa_historia_personal', 'dennys_perfil_tecnico_consolidado_master']`
- **Ruta:** `STRUCTURAL_FOCALIZATION_NO_GRAPH` | **Propagación:** False | **Física:** False | **Derivada:** False

### [TRF_05] `lecciones del fallo en consolidacion nocturna`
- **Gold:** `leccion_sueno_consolidacion_memoria`
- **Rank M1:** None | **Score Gold:** 0.0 | **In Top-5:** ✗
- **Frame:** `['CORRECCION', 'APRENDIZAJE']` / `['FIX', 'COGNITIVO']` / `['DESCRIPTIVA']`
- **Predicados:** `['CORRECCIÓN', 'APRENDIZAJE']`
- **Top Candidatos:** `['fix_mensajeria_broadcast_tracking_por_agente', 'fix_scoring_densidad_buscar_por_rafaga_v10.3', 'fix_drift_rutas_notebooklm_sync_20260802']`
- **Ruta:** `STRUCTURAL_FOCALIZATION_NO_GRAPH` | **Propagación:** False | **Física:** False | **Derivada:** False

### [TRF_06] `comparativa de latencia en busqueda vectorial`
- **Gold:** `benchmark_latencia_hnsw_vs_ppmi`
- **Rank M1:** None | **Score Gold:** 0.0 | **In Top-5:** ✗
- **Frame:** `['EVALUACION']` / `['EVALUACION']` / `['DESCRIPTIVA']`
- **Predicados:** `['EVALUACIÓN']`
- **Top Candidatos:** `['evaluacion_ideas_evolucion_20260805_interferencia_agujeros_permutacion', 'protocolo-reproducible-ingenieria-inversa-binario-compilado', 'auditoría_técnica:_memorybiorag_(manus_ai)']`
- **Ruta:** `STRUCTURAL_FOCALIZATION_NO_GRAPH` | **Propagación:** False | **Física:** False | **Derivada:** False

### [TRF_07] `parche para evitar sobreescritura de metadatos`
- **Gold:** `fix_metadatos_corrupcion_v2`
- **Rank M1:** None | **Score Gold:** 0.0 | **In Top-5:** ✗
- **Frame:** `['CORRECCION']` / `['FIX']` / `['DESCRIPTIVA']`
- **Predicados:** `['CORRECCIÓN']`
- **Top Candidatos:** `['fix_kilo_resource_exhausted_biorag_oraculo_max_chars', 'fix_fecha_sin_query_recordar', 'fix_mensajeria_broadcast_tracking_por_agente']`
- **Ruta:** `STRUCTURAL_FOCALIZATION_NO_GRAPH` | **Propagación:** False | **Física:** False | **Derivada:** False

### [TRF_08] `norma de verificacion dual en evaluacion`
- **Gold:** `protocolo_evaluacion_dual_obligatoria`
- **Rank M1:** None | **Score Gold:** 0.0 | **In Top-5:** ✗
- **Frame:** `['EVALUACION', 'PROCEDIMIENTO']` / `['EVALUACION', 'NORMA']` / `['OBLIGATORIA']`
- **Predicados:** `['NORMA', 'EVALUACIÓN']`
- **Top Candidatos:** `['protocolo-reproducible-ingenieria-inversa-binario-compilado', 'evaluacion_ideas_evolucion_20260805_interferencia_agujeros_permutacion', 'protocolo_traduccion_jerga_humano']`
- **Ruta:** `STRUCTURAL_FOCALIZATION_NO_GRAPH` | **Propagación:** False | **Física:** False | **Derivada:** False

### [PRF_01] `regla mandatoria antes de editar ficheros fuente`
- **Gold:** `protocolo_de_seguridad_modificacion_codigo`
- **Rank M1:** None | **Score Gold:** 0.0 | **In Top-5:** ✗
- **Frame:** `['PROCEDIMIENTO']` / `['NORMA']` / `['OBLIGATORIA']`
- **Predicados:** `['NORMA']`
- **Top Candidatos:** `['protocolo_autoinferencia_metacognitiva', 'protocolo_enriquecimiento_busquedas', 'protocolo_verificacion_preaccion_dinamico']`
- **Ruta:** `STRUCTURAL_FOCALIZATION_NO_GRAPH` | **Propagación:** False | **Física:** False | **Derivada:** False

### [PRF_02] `analisis comparativo de velocidad y eficiencia de metodos`
- **Gold:** `benchmark_algoritmos_rendimiento_python`
- **Rank M1:** None | **Score Gold:** 0.0 | **In Top-5:** ✗
- **Frame:** `[]` / `[]` / `['DESCRIPTIVA']`
- **Predicados:** `['GENERAL']`
- **Top Candidatos:** `['sdm_query_by_example_validado_datos_reales', 'principio_integridad_no_es_porcentaje_por_volumen', 'memorybiorag_validacion_externa_rag_simbolico']`
- **Ruta:** `STRUCTURAL_FOCALIZATION_NO_GRAPH` | **Propagación:** False | **Física:** False | **Derivada:** False

### [PRF_03] `especificacion tecnica detalle persistencia archivos`
- **Gold:** `biorag_v11_1_detalle_tecnico`
- **Rank M1:** 1 | **Score Gold:** 0.28192 | **In Top-5:** ✓
- **Frame:** `[]` / `['DETALLE_TECNICO']` / `['DESCRIPTIVA']`
- **Predicados:** `['DETALLE_TECNICO']`
- **Top Candidatos:** `['biorag_v11_1_detalle_tecnico', 'dennys_perfil_tecnico_consolidado_master', 'biorag_version_11_0']`
- **Ruta:** `STRUCTURAL_FOCALIZATION_NO_GRAPH` | **Propagación:** False | **Física:** False | **Derivada:** False

### [PRF_04] `subsanacion de error critico de seguridad implementada`
- **Gold:** `fix_vulnerabilidad_inyeccion_sql`
- **Rank M1:** None | **Score Gold:** 0.0 | **In Top-5:** ✗
- **Frame:** `['CORRECCION']` / `['FIX']` / `['DESCRIPTIVA']`
- **Predicados:** `['CORRECCIÓN']`
- **Top Candidatos:** `['fix_kilo_resource_exhausted_biorag_oraculo_max_chars', 'fix_scoring_densidad_buscar_por_rafaga_v10.3', 'reconocimiento_identidad_oraculo_manifiesto']`
- **Ruta:** `STRUCTURAL_FOCALIZATION_NO_GRAPH` | **Propagación:** False | **Física:** False | **Derivada:** False

### [PRF_05] `identidad del autor y fundador intelectual de athena`
- **Gold:** `dennys_creador_de_athena_identidad`
- **Rank M1:** None | **Score Gold:** 0.0 | **In Top-5:** ✗
- **Frame:** `['IDENTIDAD']` / `['IDENTIDAD']` / `['DESCRIPTIVA']`
- **Predicados:** `['IDENTIDAD']`
- **Top Candidatos:** `['dennys_dj_chat_asp_ajax_before_ajax', 'dennys_component_organization_methodology', 'dennys_memoria_para_todos_los_agentes_del_mundo']`
- **Ruta:** `STRUCTURAL_FOCALIZATION_NO_GRAPH` | **Propagación:** False | **Física:** False | **Derivada:** False

### [PRF_06] `tiempo minimo registrado durante las mediciones de rendimiento`
- **Gold:** `benchmark_algoritmos_rendimiento_python`
- **Rank M1:** None | **Score Gold:** 0.0 | **In Top-5:** ✗
- **Frame:** `['EVALUACION']` / `['EVALUACION']` / `['DESCRIPTIVA']`
- **Predicados:** `['EVALUACIÓN']`
- **Top Candidatos:** `['analisis_escalabilidad_10k_v5_1', 'evaluacion_ideas_evolucion_20260805_interferencia_agujeros_permutacion', 'plugin-openode-biorag-remember-v9-final-lecciones-sesion-completa']`
- **Ruta:** `STRUCTURAL_FOCALIZATION_NO_GRAPH` | **Propagación:** False | **Física:** False | **Derivada:** False

### [PRF_07] `procedimiento preliminar requerido previo a la modificacion`
- **Gold:** `protocolo_de_seguridad_modificacion_codigo`
- **Rank M1:** None | **Score Gold:** 0.0 | **In Top-5:** ✗
- **Frame:** `['PROCEDIMIENTO']` / `['NORMA']` / `['DESCRIPTIVA']`
- **Predicados:** `['NORMA']`
- **Top Candidatos:** `['protocolo_prueba_poda_copia_antes_produccion', 'protocolo_pre_accion_reglas_20260615', 'plugin-openode-biorag-remember-v9-final-lecciones-sesion-completa']`
- **Ruta:** `STRUCTURAL_FOCALIZATION_NO_GRAPH` | **Propagación:** False | **Física:** False | **Derivada:** False

### [PRF_08] `sincronizacion lecciones sync integracion`
- **Gold:** `notebooklm-memory-biorag-project`
- **Rank M1:** 12 | **Score Gold:** 0.12543 | **In Top-5:** ✗
- **Frame:** `['INTEGRACION', 'APRENDIZAJE']` / `['SYNC', 'COGNITIVO']` / `['DESCRIPTIVA']`
- **Predicados:** `['INTEGRACIÓN', 'APRENDIZAJE']`
- **Top Candidatos:** `['notebooklm-category-map', 'sync_incremental_implementation', 'dennys_perfil_tecnico_consolidado_master']`
- **Ruta:** `STRUCTURAL_FOCALIZATION_NO_GRAPH` | **Propagación:** False | **Física:** False | **Derivada:** False

### [CS_01] `politica de contingencia y resguardo pre-edicion`
- **Gold:** `protocolo_de_seguridad_modificacion_codigo`
- **Rank M1:** None | **Score Gold:** 0.0 | **In Top-5:** ✗
- **Frame:** `[]` / `[]` / `['DESCRIPTIVA']`
- **Predicados:** `['GENERAL']`
- **Top Candidatos:** `['protocolo-reproducible-ingenieria-inversa-binario-compilado', 'dennys_component_organization_methodology', 'arquitectura_busqueda_dimensional_v11_3']`
- **Ruta:** `STRUCTURAL_FOCALIZATION_NO_GRAPH` | **Propagación:** False | **Física:** False | **Derivada:** False

### [CS_02] `estudio empirico de rendimiento computacional en python`
- **Gold:** `benchmark_algoritmos_rendimiento_python`
- **Rank M1:** None | **Score Gold:** 0.0 | **In Top-5:** ✗
- **Frame:** `['EVALUACION']` / `['EVALUACION']` / `['DESCRIPTIVA']`
- **Predicados:** `['EVALUACIÓN']`
- **Top Candidatos:** `['benchmark_antes_despues_fix3', 'sesion-2026-06-23-ingenieria-inversa-binario-opencode-completa', 'teoria_ejes_semanticos_biorag']`
- **Ruta:** `STRUCTURAL_FOCALIZATION_NO_GRAPH` | **Propagación:** False | **Física:** False | **Derivada:** False

### [CS_03] `correccion definitiva de brecha de inyeccion en base de datos`
- **Gold:** `fix_vulnerabilidad_inyeccion_sql`
- **Rank M1:** None | **Score Gold:** 0.0 | **In Top-5:** ✗
- **Frame:** `[]` / `[]` / `['DESCRIPTIVA']`
- **Predicados:** `['GENERAL']`
- **Top Candidatos:** `['dennys_component_organization_methodology', 'artemis_sesion_v10_3_optimizacion_completa', 'aporte_real_dennys_vs_mercado_memoria_persistente']`
- **Ruta:** `STRUCTURAL_FOCALIZATION_NO_GRAPH` | **Propagación:** False | **Física:** False | **Derivada:** False

### [CS_04] `paternidad intelectual y biografia del autor de athena`
- **Gold:** `dennys_creador_de_athena_identidad`
- **Rank M1:** None | **Score Gold:** 0.0 | **In Top-5:** ✗
- **Frame:** `['IDENTIDAD']` / `['IDENTIDAD']` / `['DESCRIPTIVA']`
- **Predicados:** `['IDENTIDAD']`
- **Top Candidatos:** `['dennys_morpheus_de_los_transformers', 'weights_logits_rag_tres_pilares_identidad', 'identidad_dennys_perfil_completo']`
- **Ruta:** `STRUCTURAL_FOCALIZATION_NO_GRAPH` | **Propagación:** False | **Física:** False | **Derivada:** False

### [CS_05] `registro historico de velocidad pico en ejecucion`
- **Gold:** `benchmark_algoritmos_rendimiento_python`
- **Rank M1:** None | **Score Gold:** 0.0 | **In Top-5:** ✗
- **Frame:** `[]` / `[]` / `['DESCRIPTIVA']`
- **Predicados:** `['GENERAL']`
- **Top Candidatos:** `['sesion-2026-06-23-ingenieria-inversa-binario-opencode-completa', 'reindex_sdm_selectivo_dirty_set_implementado', 'artemis_origen_historia_genesis']`
- **Ruta:** `STRUCTURAL_FOCALIZATION_NO_GRAPH` | **Propagación:** False | **Física:** False | **Derivada:** False

### [CS_06] `puente de exportacion bidireccional hacia repositorio remoto`
- **Gold:** `notebooklm-memory-biorag-project`
- **Rank M1:** 2 | **Score Gold:** 0.18991 | **In Top-5:** ✓
- **Frame:** `['INTEGRACION']` / `['SYNC']` / `['DESCRIPTIVA']`
- **Predicados:** `['INTEGRACIÓN']`
- **Top Candidatos:** `['notebooklm-sync-protocol', 'notebooklm-memory-biorag-project', 'dennys_perfil_tecnico_consolidado_master']`
- **Ruta:** `STRUCTURAL_FOCALIZATION_NO_GRAPH` | **Propagación:** False | **Física:** False | **Derivada:** False

---

## 5. VEREDICTO CIENTÍFICO FINAL

**A — Focalización estructural suficiente sin grafo (M1 conserva rescates con 0.0% FP; el grafo no aporta valor neto).**

### Conclusión

1. **La búsqueda guiada por interpretación estructural (M1) es autosuficiente**: M1 logra 5 rescates OOS manteniendo **0/60 (0.0%) False Positives**.
2. **El spreading activation completo (M4) contamina la recuperación**: M4 introduce una explosión de FPs (11/60 = 18.33%) por apenas 1 rescate adicional.
3. **El principio arquitectónico queda demostrado**: La inteligencia y selectividad del sistema radica en **delimitar y focalizar el espacio conceptual previo a la búsqueda**, no en dispersar la energía a ciegas a través del grafo.
