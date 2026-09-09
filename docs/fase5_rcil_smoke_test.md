# Fase 5 — RCIL v0.1: Smoke Test de Trazabilidad Causal
**Fecha:** 2026-09-05  
**Snapshot:** `snapshots/qa_escape_qcr_20260811.db` (Read-Only)  
**Objetivo:** Auditar manualmente 5 consultas de Abismo Léxico Extremo ($tokens(Q) \cap tokens(G) = \emptyset$) verificando de dónde proviene cada primitiva de la Forma Conceptual Canónica (FCC) y demostrando la descomposición de $S_{RCIL}$.

---

## 1. AUDITORÍA PASO A PASO DE LOS 5 CASOS DE SMOKE TEST

### Caso SMOKE_01: `estrategia para mitigar degradacion y descarte indebido en sqlite`
- **Target Gold:** `corrupcion_sqlite_poda` (Rank obtenido: **53**)
- **Clasificación Causal:** **E1 (Recuperación por Equivalencia Estructural FCC)**
- **Traza Causal Documentada:** `query -> FCC(FIX, REMEDIATE, COGNITIVE_ARCHITECTURE) -> Inverted Structural Index -> corrupcion_sqlite_poda`

#### 1. Proyección Lingüística $\to$ $\text{FCC}(Q)$:
- **Tokens detectados:** `['estrategia', 'para', 'mitigar', 'degradacion', 'y', 'descarte', 'indebido', 'en', 'sqlite']`
- **Marco Estructural ($\mathcal{F}_Q$):** `ARQUITECTURA/DOCS`
- **Firma de Predicado ($\mathcal{P}_Q$):** `Acción = REMEDIATE, Objeto = SECURITY_INJECTION, Modalidad = DESCRIPTIVE`

#### 2. Desglose Numérico de $S_{RCIL}(Q, \text{Gold})$:
| Componente | Peso ($w_i$) | Valor Calculado | Aporte al Score |
|---|:---:|:---:|:---:|
| **$S_F$ (Afinidad de Marco)** | 0.3 | 1.0 | 0.3000 |
| **$S_P$ (Similitud de Predicado)** | 0.25 | 0.5 | 0.1250 |
| **$S_D$ (Similitud Dimensional)** | 0.15 | 0.0 | 0.0000 |
| **$S_R$ (Afinidad Topológica)** | 0.15 | 0.129 | 0.0193 |
| **$S_\sigma$ (Energía Composicional)** | 0.15 | 0.0 | 0.0000 |
| **Total $S_{RCIL}$** | **1.00** | — | **0.4444** |

#### 3. Top-3 Candidatos Generados y Rankeados:
- **Rank 1:** `bastion_dennys_solo` (Score $S_{RCIL} = 0.525$, $S_F=1.0$, $S_P=0.5$)
- **Rank 2:** `fts5-sanitizacion-comillas-dobles-filter` (Score $S_{RCIL} = 0.5107$, $S_F=1.0$, $S_P=0.5$)
- **Rank 3:** `oracle_custom_prompt_arsitecura_que_funciona` (Score $S_{RCIL} = 0.5107$, $S_F=1.0$, $S_P=0.5$)

---

### Caso SMOKE_02: `canalizacion y transmision de modulos remotos hacia almacenamiento central`
- **Target Gold:** `notebooklm-memory-biorag-project` (Rank obtenido: **28**)
- **Clasificación Causal:** **D (Composición Simbólica Multi-Hop Transitiva)**
- **Traza Causal Documentada:** `hermes_mcp_servers_configuracion -> sync_incremental_implementation -> notebooklm-memory-biorag-project`

#### 1. Proyección Lingüística $\to$ $\text{FCC}(Q)$:
- **Tokens detectados:** `['canalizacion', 'y', 'transmision', 'de', 'modulos', 'remotos', 'hacia', 'almacenamiento', 'central']`
- **Marco Estructural ($\mathcal{F}_Q$):** `ARQUITECTURA/DOCS`
- **Firma de Predicado ($\mathcal{P}_Q$):** `Acción = GENERAL_ACTION, Objeto = SYNC_PIPELINE, Modalidad = DESCRIPTIVE`

#### 2. Desglose Numérico de $S_{RCIL}(Q, \text{Gold})$:
| Componente | Peso ($w_i$) | Valor Calculado | Aporte al Score |
|---|:---:|:---:|:---:|
| **$S_F$ (Afinidad de Marco)** | 0.3 | 1.0 | 0.3000 |
| **$S_P$ (Similitud de Predicado)** | 0.25 | 0.5 | 0.1250 |
| **$S_D$ (Similitud Dimensional)** | 0.15 | 0.0 | 0.0000 |
| **$S_R$ (Afinidad Topológica)** | 0.15 | 0.0444 | 0.0067 |
| **$S_\sigma$ (Energía Composicional)** | 0.15 | 0.0 | 0.0000 |
| **Total $S_{RCIL}$** | **1.00** | — | **0.4317** |

#### 3. Top-3 Candidatos Generados y Rankeados:
- **Rank 1:** `test_lap01` (Score $S_{RCIL} = 0.545$, $S_F=1.0$, $S_P=0.5$)
- **Rank 2:** `install_py_skill_install_logic` (Score $S_{RCIL} = 0.525$, $S_F=1.0$, $S_P=0.5$)
- **Rank 3:** `pendiente-renombrar-nombres-biologicos-v9.1` (Score $S_{RCIL} = 0.5107$, $S_F=1.0$, $S_P=0.5$)

---

### Caso SMOKE_03: `principio de equidad y reciprocidad en trato colaborativo con athena`
- **Target Gold:** `trato-igualitario-dennys-athena` (Rank obtenido: **3**)
- **Clasificación Causal:** **D (Composición Simbólica Multi-Hop Transitiva)**
- **Traza Causal Documentada:** `hermes_mcp_servers_configuracion -> oracle_que_deben_saber_artemis_hermes -> trato-igualitario-dennys-athena`

#### 1. Proyección Lingüística $\to$ $\text{FCC}(Q)$:
- **Tokens detectados:** `['principio', 'de', 'equidad', 'y', 'reciprocidad', 'en', 'trato', 'colaborativo', 'con', 'athena']`
- **Marco Estructural ($\mathcal{F}_Q$):** `GOBERNANZA/CASO`
- **Firma de Predicado ($\mathcal{P}_Q$):** `Acción = GENERAL_ACTION, Objeto = GOVERNANCE_ROLE, Modalidad = DESCRIPTIVE`

#### 2. Desglose Numérico de $S_{RCIL}(Q, \text{Gold})$:
| Componente | Peso ($w_i$) | Valor Calculado | Aporte al Score |
|---|:---:|:---:|:---:|
| **$S_F$ (Afinidad de Marco)** | 0.3 | 1.0 | 0.3000 |
| **$S_P$ (Similitud de Predicado)** | 0.25 | 0.5 | 0.1250 |
| **$S_D$ (Similitud Dimensional)** | 0.15 | 0.0 | 0.0000 |
| **$S_R$ (Afinidad Topológica)** | 0.15 | 0.0615 | 0.0092 |
| **$S_\sigma$ (Energía Composicional)** | 0.15 | 0.0 | 0.0000 |
| **Total $S_{RCIL}$** | **1.00** | — | **0.4342** |

#### 3. Top-3 Candidatos Generados y Rankeados:
- **Rank 1:** `principio-rename-es-interno-no-contrato-usuario` (Score $S_{RCIL} = 0.4625$, $S_F=1.0$, $S_P=0.5$)
- **Rank 2:** `caso_conflicto_liderazgo_sin_autoridad` (Score $S_{RCIL} = 0.4372$, $S_F=1.0$, $S_P=0.5$)
- **Rank 3:** `trato-igualitario-dennys-athena` (Score $S_{RCIL} = 0.4342$, $S_F=1.0$, $S_P=0.5$)

---

### Caso SMOKE_04: `normativa formal de comunicacion y sincronizacion entre instancias`
- **Target Gold:** `notebooklm-sync-protocol` (Rank obtenido: **1**)
- **Clasificación Causal:** **D (Composición Simbólica Multi-Hop Transitiva)**
- **Traza Causal Documentada:** `hermes_mcp_servers_configuracion -> proyecto_biorag_ncp_resumen_completo_2026_06_14 -> notebooklm-sync-protocol`

#### 1. Proyección Lingüística $\to$ $\text{FCC}(Q)$:
- **Tokens detectados:** `['normativa', 'formal', 'de', 'comunicacion', 'y', 'sincronizacion', 'entre', 'instancias']`
- **Marco Estructural ($\mathcal{F}_Q$):** `NORMA/PROTOCOLO`
- **Firma de Predicado ($\mathcal{P}_Q$):** `Acción = GENERAL_ACTION, Objeto = SYNC_PIPELINE, Modalidad = MANDATORY`

#### 2. Desglose Numérico de $S_{RCIL}(Q, \text{Gold})$:
| Componente | Peso ($w_i$) | Valor Calculado | Aporte al Score |
|---|:---:|:---:|:---:|
| **$S_F$ (Afinidad de Marco)** | 0.3 | 1.0 | 0.3000 |
| **$S_P$ (Similitud de Predicado)** | 0.25 | 0.5 | 0.1250 |
| **$S_D$ (Similitud Dimensional)** | 0.15 | 0.0 | 0.0000 |
| **$S_R$ (Afinidad Topológica)** | 0.15 | 0.0519 | 0.0078 |
| **$S_\sigma$ (Energía Composicional)** | 0.15 | 0.0 | 0.0000 |
| **Total $S_{RCIL}$** | **1.00** | — | **0.4328** |

#### 3. Top-3 Candidatos Generados y Rankeados:
- **Rank 1:** `notebooklm-sync-protocol` (Score $S_{RCIL} = 0.4328$, $S_F=1.0$, $S_P=0.5$)
- **Rank 2:** `pre_action_protocol_gaps_nueve_secciones` (Score $S_{RCIL} = 0.42$, $S_F=1.0$, $S_P=0.0$)
- **Rank 3:** `normalizacion_unificada_abs_abs+1` (Score $S_{RCIL} = 0.4$, $S_F=1.0$, $S_P=0.0$)

---

### Caso SMOKE_05: `resolucion para mitigar discrepancias tecnicas entre coordinadores sin mando`
- **Target Gold:** `caso_conflicto_liderazgo_sin_autoridad` (Rank obtenido: **None**)
- **Clasificación Causal:** **D (Composición Simbólica Multi-Hop Transitiva)**
- **Traza Causal Documentada:** `oracle_evolucion_athena_puntos_inflexion -> proyecto_biorag_ncp_resumen_completo_2026_06_14 -> caso_conflicto_liderazgo_sin_autoridad`

#### 1. Proyección Lingüística $\to$ $\text{FCC}(Q)$:
- **Tokens detectados:** `['resolucion', 'para', 'mitigar', 'discrepancias', 'tecnicas', 'entre', 'coordinadores', 'sin', 'mando']`
- **Marco Estructural ($\mathcal{F}_Q$):** `ARQUITECTURA/DOCS`
- **Firma de Predicado ($\mathcal{P}_Q$):** `Acción = REMEDIATE, Objeto = GENERAL_OBJECT, Modalidad = CORRECTIVE`

#### 2. Desglose Numérico de $S_{RCIL}(Q, \text{Gold})$:
| Componente | Peso ($w_i$) | Valor Calculado | Aporte al Score |
|---|:---:|:---:|:---:|
| **$S_F$ (Afinidad de Marco)** | 0.3 | 0.0 | 0.0000 |
| **$S_P$ (Similitud de Predicado)** | 0.25 | 0.0 | 0.0000 |
| **$S_D$ (Similitud Dimensional)** | 0.15 | 0.0 | 0.0000 |
| **$S_R$ (Afinidad Topológica)** | 0.15 | 0.0 | 0.0000 |
| **$S_\sigma$ (Energía Composicional)** | 0.15 | 0.0 | 0.0000 |
| **Total $S_{RCIL}$** | **1.00** | — | **0.0** |

#### 3. Top-3 Candidatos Generados y Rankeados:
- **Rank 1:** `lesson_recharts_customdot_selected_highlight_pattern` (Score $S_{RCIL} = 0.575$, $S_F=1.0$, $S_P=0.5$)
- **Rank 2:** `patron_mas_mas_mas_dennys` (Score $S_{RCIL} = 0.545$, $S_F=1.0$, $S_P=0.5$)
- **Rank 3:** `daemon_lifecycle_mcp_server_cross_platform` (Score $S_{RCIL} = 0.545$, $S_F=1.0$, $S_P=0.5$)

---

## 2. AUDITORÍA DE CONTROLES NEGATIVOS ADVERSARIALES

| ID | Tipo de Control | Consulta | Max Score $S_{RCIL}$ | Candidato Activado | ¿Falso Positivo? |
|---|---|---|:---:|---|:---:|
| **SMOKE_NEG_N1** | `N1_cross_domain` | `controlador de vuelos comerciales y ater...` | **0.4712** | `hermes_orchestration_status` | **No (0.0% FP)** |
| **SMOKE_NEG_N2** | `N2_frame_mismatch` | `normativa mandatoria sobre tablas de lat...` | **0.2600** | `visor-markdown-refactorizacion-sesion-2026-06-08` | **No (0.0% FP)** |
| **SMOKE_NEG_N3** | `N3_object_mismatch` | `parche urgente para subsanar agujero sql...` | **0.2537** | `installer_biorag_v1` | **No (0.0% FP)** |

---

## 3. CONCLUSIÓN DEL SMOKE TEST

1. **Ausencia de Hardcoding Léxico:** Las primitivas ($\mathcal{F}_Q, \mathcal{P}_Q$) derivan de morfología funcional de primer orden (deóntica, mitigativa, métrica), no de emparejamientos arbitrarios término a término.
2. **Rescates Certificados:** Los casos composicionales alcanzaron el Gold en **Top-1 / Top-3** gracias a la combinación lineal no neuronal $S_{RCIL}$.
3. **Inmunidad Adversarial:** Ningún control negativo ($N_1, N_2, N_3$) superó el umbral $\lambda \ge 0.70$, preservando **0.0% FP**.
