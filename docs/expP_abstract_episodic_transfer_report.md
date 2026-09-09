# EXP-P / FASE 2.2: Abstract Episodic Transfer — Informe Formal

**Timestamp**: 2026-09-09T01:33:42Z  
**DB SHA-256**: `676827f6b4abc3acaee10b14e273c3c50cae5b2c180593dedcd58048265a2800`  
> **Invariantes:** core/ intacto. A0-TEST 100% ciego. Evaluación de 8 ablaciones abstractas sin operador.

## 1. Matriz Comparativa de las 8 Ablaciones

| Cod | Ablación | Gen Rescue | ReRank | True Zero-Cue | R@1 | R@5 | R@10 | Neg FP |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| **A** | `OP_ONLY` | **1/5** | 2/5 | **0/5** | 3/5 | **3/5** | 3/5 | 0/2 |
| **B** | `DIM_13D_ONLY` | **0/5** | 0/5 | **0/5** | 0/5 | **0/5** | 0/5 | 0/2 |
| **C** | `HDC_ONLY` | **0/5** | 0/5 | **0/5** | 0/5 | **0/5** | 0/5 | 0/2 |
| **D** | `ISLAND_ONLY` | **1/5** | 1/5 | **0/5** | 1/5 | **2/5** | 2/5 | 2/2 |
| **E** | `DIM_13D_PLUS_HDC` | **0/5** | 0/5 | **0/5** | 0/5 | **0/5** | 0/5 | 0/2 |
| **F** | `DIM_13D_PLUS_ISLAND` | **0/5** | 1/5 | **0/5** | 1/5 | **1/5** | 1/5 | 2/2 |
| **G** | `HDC_PLUS_ISLAND` | **0/5** | 1/5 | **0/5** | 1/5 | **1/5** | 1/5 | 2/2 |
| **H** | `DIM_HDC_ISLAND` | **0/5** | 0/5 | **0/5** | 0/5 | **0/5** | 0/5 | 0/2 |

## 2. Detalle por Caso en la Mejor Configuración Híbrida (DIM_HDC_ISLAND)

| Case | Gold | Sim_H | Stem Ov | Op Ov | Transfer Type | M0 Rank | M2 Rank | Veredicto |
|---|---|---:|---|---|---|---:|---:|---|
| **CASE_01** | `scoring_pesos_bm25` | **0.0** | `∅` | `∅` | `NOT_TRANSFERRED` | 64 | **64** | `NO_EPISODE_ACTIVATION` |
| **CASE_02** | `desde_athena_biorag` | **0.0** | `∅` | `['LINK']` | `NOT_TRANSFERRED` | 68 | **68** | `NO_EPISODE_ACTIVATION` |
| **CASE_03** | `docker_infrastructur` | **0.1591** | `∅` | `['SEPARATE']` | `NOT_TRANSFERRED` | – | **–** | `NO_EPISODE_ACTIVATION` |
| **CASE_04** | `coche_puente_condici` | **0.0** | `∅` | `∅` | `NOT_TRANSFERRED` | 24 | **24** | `NO_EPISODE_ACTIVATION` |
| **CASE_05** | `activos_dormidos_her` | **0.1901** | `∅` | `['MODIFY']` | `NOT_TRANSFERRED` | 33 | **33** | `NO_EPISODE_ACTIVATION` |

## 3. Conclusiones Metodológicas (Aureon Protocol)

1. **Rendimiento de Canales Aislados:**
   - **`OP_ONLY` (Canal A):** Logra 1 rescate de generación (`CASE_03`), 2 de re-ranking (`CASE_02`, `CASE_05`) y **0/2 Falsos Positivos**, pero depende de la coincidencia del operador canónico.
   - **`ISLAND_ONLY` (Canal D):** Logra activar episodios mediante la topología emergente de comunidades PPMI ($Sim_H=0.477$ en `CASE_03` alcanzando Rank 2, $Sim_H=0.570$ en `CASE_05` alcanzando Rank 1), pero introduce **2/2 Falsos Positivos** en controles negativos si no está acotado por gating estructural.
   - **`DIM_13D` y `HDC` (Canales B y C):** Resultan inoperantes ($Sim_H=0.0$) a nivel de sintagmas libres arbitrarios porque las tablas de dimensiones y HDC están ancladas a nivel de nodo conceptual, no de vocabulario abierto no indexado.
2. **Dilución en Combinaciones Híbridas (Canal H):**
   - Promediar 13-D y HDC (con valor 0.0) con la señal de Isla ($0.48$) diluye el score total ($0.16 < 0.25$), desactivando el episodio.
3. **Hallazgo Central:** La señal topológica de **Islas Semánticas (PPMI+SVD)** es el único canal continuo capaz de tender un puente entre expresiones distintas sin compartir operador, pero requiere el **gating de especificidad de operador/rol** para neutralizar falsos positivos.
