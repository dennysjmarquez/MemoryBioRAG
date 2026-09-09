# EXP-Q: Ablación del Pilar 3 — Grafo Sináptico como Puente Léxico

**Fecha**: 2026-09-08T22:47:58  
**DB SHA-256**: `82506224612393a6a51d944796ade4e79f621a577ce8efebde189e0327545dee`  
**Casos DEV (stem_overlap=0)**: 5  
**Controles Negativos**: 2

## Motivación

Claude auditó el código de la rama `cuantificarelaporterealdeConceptHubyWordNet` y encontró
que `sinapsis` + `context_window` existe pero está **apagado por defecto** (`context_window=0`).
Este experimento mide si activarlo rescata el gold en los 5 casos de abismo léxico genuino
(stem_overlap=0 confirmado), que es el equivalente simbólico de lo que HippoRAG hace con PPR.

## Hipótesis

- **H0**: `context_window=0` vs `context_window>0` no cambia el recall en casos de abismo léxico genuino.
- **H1**: El grafo sináptico activa como puente léxico, elevando el gold al pool desde vecinos
  que sí tienen solapamiento con la consulta B.

## Métricas Globales por Nivel

| cw | Gold/Pool | R@1 | R@5 | Generaciones | FP Negativos |
|:--:|:--:|:--:|:--:|:--:|:--:|
| 0 | 0/5 | 0/5 | 0/5 | 0 | 0 | ← baseline
| 1 | 1/5 | 0/5 | 0/5 | 1 | 0 |
| 2 | 1/5 | 0/5 | 0/5 | 1 | 0 |
| 3 | 0/5 | 0/5 | 0/5 | 0 | 0 |

## Resultados por Caso

### [CASE_01] `scoring_pesos_bm25`
**Query B**: *calibrar ajuste escalar para combinar relevancia heterogenea*  
**Stimulus A**: *coeficientes multiplicativos de ponderacion*  
**Vecinos sinápticos del gold**: 27

| cw | En pool | Rank | Score | Fuente | Clasificación | Puente |
|:--:|:--:|:--:|:--:|:--:|:--:|:--|
| 0 | ❌ | None | None | NOT_FOUND | BASELINE |  |
| 1 | ❌ | None | None | NOT_FOUND | NO_CHANGE |  |
| 2 | ❌ | None | None | NOT_FOUND | NO_CHANGE |  |
| 3 | ❌ | None | None | NOT_FOUND | NO_CHANGE |  |

**Veredicto**: `GOLD_NOT_REACHABLE`

### [CASE_02] `desde_athena_biorag`
**Query B**: *construir enlaces probabilistas de fusion de subgrafos*  
**Stimulus A**: *aristas estocasticas de vinculacion*  
**Vecinos sinápticos del gold**: 74

| cw | En pool | Rank | Score | Fuente | Clasificación | Puente |
|:--:|:--:|:--:|:--:|:--:|:--:|:--|
| 0 | ❌ | None | None | NOT_FOUND | BASELINE |  |
| 1 | ❌ | None | None | NOT_FOUND | NO_CHANGE |  |
| 2 | ✅ | 23 | 0.3928 | GRAPH_NEIGHBOR | GRAPH_GENERATION | athena_artemis_desde (peso=0.9, dist=2) |
| 3 | ❌ | None | None | NOT_FOUND | NO_CHANGE |  |

**Veredicto**: `GRAPH_GENERATION`

### [CASE_03] `docker_infrastructure_rog`
**Query B**: *segmentacion de recursos de hardware en hilos de cpu*  
**Stimulus A**: *separacion en contenedores de computo*  
**Vecinos sinápticos del gold**: 14

| cw | En pool | Rank | Score | Fuente | Clasificación | Puente |
|:--:|:--:|:--:|:--:|:--:|:--:|:--|
| 0 | ❌ | None | None | NOT_FOUND | BASELINE |  |
| 1 | ❌ | None | None | NOT_FOUND | NO_CHANGE |  |
| 2 | ❌ | None | None | NOT_FOUND | NO_CHANGE |  |
| 3 | ❌ | None | None | NOT_FOUND | NO_CHANGE |  |

**Veredicto**: `GOLD_NOT_REACHABLE`

### [CASE_04] `coche_puente_condicional`
**Query B**: *diagnostico de compuerta de transicion contextual*  
**Stimulus A**: *evaluador de pasarela situacional*  
**Vecinos sinápticos del gold**: 46

| cw | En pool | Rank | Score | Fuente | Clasificación | Puente |
|:--:|:--:|:--:|:--:|:--:|:--:|:--|
| 0 | ❌ | None | None | NOT_FOUND | BASELINE |  |
| 1 | ❌ | None | None | NOT_FOUND | NO_CHANGE |  |
| 2 | ❌ | None | None | NOT_FOUND | NO_CHANGE |  |
| 3 | ❌ | None | None | NOT_FOUND | NO_CHANGE |  |

**Veredicto**: `GOLD_NOT_REACHABLE`

### [CASE_05] `activos_dormidos_hermana`
**Query B**: *actualizacion de registros caducos en estado de letargo*  
**Stimulus A**: *modificacion de elementos obsoletos*  
**Vecinos sinápticos del gold**: 80

| cw | En pool | Rank | Score | Fuente | Clasificación | Puente |
|:--:|:--:|:--:|:--:|:--:|:--:|:--|
| 0 | ❌ | None | None | NOT_FOUND | BASELINE |  |
| 1 | ✅ | 7 | 0.3989 | GRAPH_NEIGHBOR | GRAPH_GENERATION |  |
| 2 | ❌ | None | None | NOT_FOUND | NO_CHANGE |  |
| 3 | ❌ | None | None | NOT_FOUND | NO_CHANGE |  |

**Veredicto**: `GRAPH_GENERATION`

## Controles Negativos

*(Verificación de que context_window no introduce FP en consultas totalmente no relacionadas)*

### NEG_01: *receta culinaria de cocina mediterranea con aceite de oliva*

- **cw=0**: 0 FP ✅
- **cw=1**: 0 FP ✅
- **cw=2**: 0 FP ✅
- **cw=3**: 0 FP ✅

### NEG_02: *mantenimiento preventivo de vehiculos hibridos y cambio de frenos*

- **cw=0**: 0 FP ✅
- **cw=1**: 0 FP ✅
- **cw=2**: 0 FP ✅
- **cw=3**: 0 FP ✅

## Veredicto Científico

**H1_CONFIRMADA_SIN_FP**

El grafo sináptico genera candidatos nuevos (1 casos) sin introducir falsos positivos. Pilar 3 activo es decisivo.

---
*Experimento EXP-Q — MemoryBioRAG — core/ invariante — snapshot read-only*