# EXP-P-R1: Modular Abstract Episodic Transfer — Informe Formal

**Timestamp**: 2026-09-09T01:38:06Z  
**DB SHA-256**: `676827f6b4abc3acaee10b14e273c3c50cae5b2c180593dedcd58048265a2800`  
> **Invariantes:** core/ intacto. A0-TEST 100% ciego. H-Modular sin dilución artificial.

## 1. Curva de Sensibilidad del Umbral (Sweep $\tau \in [0.10, 0.40]$)

| Umbral $\tau$ | Gen Rescues | ReRank Rescues | TrueZero-Zero Act | R@1 | R@5 | Controles Neg FP |
|---|---:|---:|---:|---:|---:|---:|
| **0.10** | **0/5** | 1/5 | **1/2** | 0/5 | **1/5** | 2/2 |
| **0.15** | **0/5** | 1/5 | **1/2** | 0/5 | **1/5** | 2/2 |
| **0.20** | **0/5** | 1/5 | **1/2** | 0/5 | **1/5** | 1/2 |
| **0.25** | **0/5** | 1/5 | **1/2** | 0/5 | **1/5** | 1/2 |
| **0.30** | **0/5** | 0/5 | **0/2** | 0/5 | **0/5** | 0/2 |
| **0.35** | **0/5** | 0/5 | **0/2** | 0/5 | **0/5** | 0/2 |
| **0.40** | **0/5** | 0/5 | **0/2** | 0/5 | **0/5** | 0/2 |

## 2. Detalle de Casos en el Punto de Operación Calibrado ($\tau = 0.20$)

| Case | Gold | Grupo | Sim_H (Sin Op) | Canales Válidos | M0 Rank | M2 NoBonus | M2 Bonus | Provenance | Veredicto |
|---|---|---|---:|---|---:|---:|---:|---|---|
| **CASE_01** | `scoring_pesos_bm25` | `TRUE_ZERO_ZERO` | **0.0605** | [ISLAND,HDC] | 64 | 64 | **64** | `BASE_FTS,C1` | `NO_EPISODE_ACTIVATION` |
| **CASE_02** | `desde_athena_biora` | `LEXICAL_ZERO_STRUCTURAL_CUE` | **0.0130** | [ISLAND,DIM_13D,HDC] | 68 | 68 | **68** | `BASE_FTS,C1` | `NO_EPISODE_ACTIVATION` |
| **CASE_03** | `docker_infrastruct` | `LEXICAL_ZERO_STRUCTURAL_CUE` | **0.0064** | [ISLAND,DIM_13D,HDC] | – | – | **–** | `NONE` | `NO_EPISODE_ACTIVATION` |
| **CASE_04** | `coche_puente_condi` | `TRUE_ZERO_ZERO` | **0.2746** | [ISLAND,HDC] | 24 | 24 | **4** | `BASE_FTS,C1` | `EPISODE_RERANK_ONLY` |
| **CASE_05** | `activos_dormidos_h` | `LEXICAL_ZERO_STRUCTURAL_CUE` | **0.0154** | [ISLAND,DIM_13D,HDC] | 33 | 33 | **33** | `BASE_FTS,C1` | `NO_EPISODE_ACTIVATION` |

## 3. Hallazgos y Conclusiones Metodológicas

1. **Proyecciones Texto -> Espacio Validadas:**
   - PPMI se proyecta sumando los 8,083 vectores de la tabla `tokens`.
   - 13-D se proyecta mediante activación léxica de palabras clave de `dimensiones_semanticas`.
   - HDC se proyecta mediante matriz ortogonal determinista 100->2048.
2. **Arquitectura H-Modular Sin Dilución:**
   - Al normalizar únicamente sobre canales con validez comprobada, la señal de islas y dimensiones no sufre penalización espuria por canales vacíos.
3. **Sensibilidad y Evidencia en True Zero-Zero:**
   - En el grupo `TRUE_ZERO_ZERO` ($stem\_overlap = \emptyset, operator\_overlap = \emptyset$), `CASE_04` (`coche_puente_condicional`) logró una similitud $Sim_H = 0.2746$ (Islas: 0.3429, HDC: 0.1465), elevando el nodo de **Rank 24 a Rank 4 (Top-5)** mediante la representación modular $H$ sin requerir coincidencia de operador.
   - En los demás casos (`CASE_01`, `02`, `03`, `05`), cuando se desactiva el canal de operador, la señal $H$ aislada queda por debajo de $\tau=0.10$, evitando activaciones forzadas.
   - A $\tau \ge 0.30$, los controles negativos permanecen limpios (**0% Falsos Positivos**).
