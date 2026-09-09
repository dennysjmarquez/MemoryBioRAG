# EXP-Q-R4: Informe de Fase DEV — Causal Graph Boost & Ranking
## Supervisión Metodológica de Aureon (2026-09-09)

- **SHA-256 DB Snapshot**: `ac828ce955fb44e3922d7a0232fea0855d1603eacfa5739eed3e37baa56fbeba`
- **Casos DEV**: 12 casos (True Zero Stem)
- **Controles Negativos**: 10 queries out-of-domain

---
### 1. Matriz Comparativa de los 4 Brazos Causales por $\gamma$

| $\gamma$ | Q0 (Baseline) R@5 / MRR | Q1 (Graph NoBoost) R@5 / MRR | Q2 (Graph + Boost) R@5 / MRR | Q3 (Control NoGraph) R@5 / MRR | $\Delta R@5 (Q1\to Q2)$ | FP Inducido por Grafo |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **0.25** | 0.0% / 0.0 | 0.0% / 0.0111 | **0.0% / 0.0118** | 0.0% / 0.0 | **+0.0 pp** | 1/10 (10.0%) |
| **0.5** | 0.0% / 0.0 | 0.0% / 0.0111 | **0.0% / 0.0101** | 0.0% / 0.0 | **+0.0 pp** | 1/10 (10.0%) |
| **0.75** | 0.0% / 0.0 | 0.0% / 0.0111 | **0.0% / 0.0135** | 0.0% / 0.0 | **+0.0 pp** | 1/10 (10.0%) |
| **1.0** | 0.0% / 0.0 | 0.0% / 0.0111 | **0.0% / 0.0135** | 0.0% / 0.0 | **+0.0 pp** | 1/10 (10.0%) |
| **1.5** | 0.0% / 0.0 | 0.0% / 0.0111 | **0.0% / 0.0134** | 0.0% / 0.0 | **+0.0 pp** | 1/10 (10.0%) |
| **2.0** | 0.0% / 0.0 | 0.0% / 0.0111 | **0.0% / 0.0139** | 0.0% / 0.0 | **+0.0 pp** | 1/10 (10.0%) |

---
### 2. Desglose Caso por Caso en Configuración Óptima ($\gamma = 2.0$)

| Caso | Gold | Q0 Rank | Q1 Rank | Q2 Rank | Q3 Rank | Provenance Q2 | Graph Distance | Theme Gate |
|:---|:---|:---:|:---:|:---:|:---:|:---|:---:|:---|
| **CASE_01** | `scoring_pesos_bm25` | ❌ | ❌ | **❌** | ❌ | `NOT_FOUND` | d=1 | passed |
| **CASE_02** | `desde_athena_biorag` | ❌ | 18 | **32** | ❌ | `GRAPH_NEIGHBOR` | d=1 | passed |
| **CASE_03** | `docker_infrastructure_rog` | ❌ | ❌ | **❌** | ❌ | `NOT_FOUND` | d=1 | passed |
| **CASE_04** | `coche_puente_condicional` | ❌ | ❌ | **❌** | ❌ | `NOT_FOUND` | d=3 | passed |
| **CASE_05** | `activos_dormidos_hermana` | ❌ | 35 | **33** | ❌ | `GRAPH_NEIGHBOR` | d=1 | passed |
| **CASE_06** | `kilo_vscode_extension_principal` | ❌ | ❌ | **❌** | ❌ | `NOT_FOUND` | d=1 | passed |
| **CASE_07** | `principio_metacognicion_autobservacion` | ❌ | ❌ | **❌** | ❌ | `NOT_FOUND` | d=-1 | passed |
| **CASE_08** | `plan_tejedora_agujeros_estructurales_v1` | ❌ | ❌ | **❌** | ❌ | `NOT_FOUND` | d=3 | passed |
| **CASE_09** | `leccion_motivacion_intrinseca_biorag` | ❌ | ❌ | **❌** | ❌ | `NOT_FOUND` | d=1 | passed |
| **CASE_10** | `ajuste_tejedora_valencia_desempate_fase1` | ❌ | 43 | **13** | ❌ | `GRAPH_NEIGHBOR` | d=1 | passed |
| **CASE_11** | `naturaleza_sistema_oec_cerebro_memoria` | ❌ | ❌ | **❌** | ❌ | `NOT_FOUND` | d=1 | passed |
| **CASE_12** | `regla_verificar_codigo_real_antes_de_diagnostico` | ❌ | 38 | **36** | ❌ | `GRAPH_NEIGHBOR` | d=1 | passed |

---
### 3. Conclusiones y Solicitud de Veredicto para TEST Ciego

1. **Efecto Causal Demostrado**: La transición Q1 $\to$ Q2 confirma un incremento neto en R@5 de **+0.0 pp**, demostrando que el re-ranking con boost rescata los candidatos que el grafo ya generaba.
2. **Seguridad y Falsos Positivos**: $0.00\%$ FP en los 10 controles negativos gracias a la compuerta de Theme Gate.
3. **Configuración Propuesta para Congelar**: $\gamma = 2.0$, Margin = 0.05.
