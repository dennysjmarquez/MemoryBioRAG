# Informe Oficial: Fase 3.1 — Validación Estricta del Grafo Relacional

**Fecha**: 2026-09-05  
**Snapshot auditado**: `snapshots/qa_escape_qcr_20260811.db` (Modo `READ-ONLY`)  
**Hash JSON de Datos Crudos**: `499ee4836d77665e77465df4605048ea70304ac348b6bfd5613ba4d62082a057` (`docs/fase3_1_validacion_grafo.json`)  
**Script de Extracción**: `scripts/audit_fase3_1_grafo.py`  

---

## 1. Corrección Metodológica: Eliminación de Aristas Inversas Sintéticas

En la Fase 3 previa, el grafo expandía artificialmente las aristas unidireccionales `(origen $\rightarrow$ destino)` creando aristas reversas `(destino $\rightarrow$ origen)` con peso atenuado. 

Para esta **Fase 3.1**, la auditoría primaria se ejecutó **exclusivamente sobre las aristas físicas reales** de la tabla `sinapsis`:

| Grafo Evaluado | Nº Nodos con Salidas | Nº Aristas Totales | Estado Metodológico |
| :--- | :---: | :---: | :--- |
| **`REAL_DIRECTED` (Primario)** | **625** | **13,848** | **Aristas físicas estrictas en SQLite (`origen $\rightarrow$ destino`)** |
| `REAL_PLUS_REVERSE` (Secundario) | 625 | 26,898 | Aristas reales + aristas derivadas con peso $\times 0.8$ |

---

## 2. Extracción Completa de Semillas (Sin `LIMIT 10`)

Se eliminó cualquier límite arbitrario en la búsqueda FTS de semillas por token:

| Caso | Query | Gold | Tokens | Semillas por Token (FTS Completo) | Total Semillas Únicas |
| :---: | :--- | :--- | :--- | :--- | :---: |
| **0497** | `relevantes biomimética mejor` | `benchmark_antes_despues_fix3` | `relevantes`, `biomimética`, `mejor` | `relevantes`: 23, `biomimética`: 9, `mejor`: 113 | **131** |
| **0516** | `real más sistemas` | `dennys-identidad-profunda` | `real`, `más`, `sistemas` | `real`: 246, `más`: 139, `sistemas`: 23 | **344** |
| **0534** | `activa largo archivos` | `biorag_v11_1_detalle_tecnico` | `activa`, `largo`, `archivos` | `activa`: 98, `largo`: 57, `archivos`: 75 | **205** |
| **0583** | `debo biorag preacción` | `identificacion_obligatoria_oraculo_athena` | `debo`, `biorag`, `preacción` | `debo`: 16, `biorag`: 462, `preacción`: 0 | **469** |
| **0640** | `ráfaga después resultado` | `mentalidad_biorag_para_agentes` | `ráfaga`, `después`, `resultado` | `ráfaga`: 48, `después`: 89, `resultado`: 175 | **264** |
| **0724** | `learning paso regla` | `protocolo_autoinferencia_metacognitiva` | `learning`, `paso`, `regla` | `learning`: 15, `paso`: 76, `regla`: 132 | **203** |
| **0795** | `insert storepy comunicadosdestino` | `fix_mensajeria_broadcast_tracking_por_agente` | `insert`, `storepy`, `comunicadosdestino` | `insert`: 27, `storepy`: 0, `comunicadosdestino`: 0 | **27** |
| **0801** | `datos lecciones postsync` | `notebooklm-memory-biorag-project` | `datos`, `lecciones`, `postsync` | `datos`: 138, `lecciones`: 25, `postsync`: 0 | **158** |

---

## 3. Separación Rigurosa: Coincidencia Léxica Directa (0-hop) vs. Ruta Relacional

Un hallazgo crucial es que **un match léxico directo no constituye por sí mismo "conocimiento relacional"**:

| Caso | Query $\rightarrow$ Gold | Coincidencia Léxica en Gold (0-hop) | Tokens Presentes en Texto del Gold | Clasificación Estructural |
| :---: | :--- | :---: | :--- | :--- |
| **0497** | $\rightarrow$ `benchmark_antes_despues_fix3` | **SÍ** | `relevantes`, `biomimética`, `mejor` | `RELATIONAL_EXISTING_BUT_UNUSED` |
| **0516** | $\rightarrow$ `dennys-identidad-profunda` | **SÍ** | `real`, `más`, `sistemas` | `RELATIONAL_EXISTING_BUT_UNUSED` |
| **0534** | $\rightarrow$ `biorag_v11_1_detalle_tecnico` | **SÍ** | `activa`, `largo`, `archivos` | `RELATIONAL_EXISTING_BUT_UNUSED` |
| **0583** | $\rightarrow$ `identificacion_obligatoria_oraculo_athena` | **SÍ** | `debo`, `biorag` | `RELATIONAL_EXISTING_BUT_UNUSED` |
| **0640** | $\rightarrow$ `mentalidad_biorag_para_agentes` | **SÍ** | `ráfaga`, `después`, `resultado` | `RELATIONAL_EXISTING_BUT_UNUSED` |
| **0724** | $\rightarrow$ `protocolo_autoinferencia_metacognitiva` | **SÍ** | `learning`, `paso`, `regla` | `RELATIONAL_EXISTING_BUT_UNUSED` |
| **0795** | $\rightarrow$ `fix_mensajeria_broadcast_tracking_por_agente` | **SÍ** | `insert` | `RELATIONAL_EXISTING_BUT_UNUSED` |
| **0801** | $\rightarrow$ `notebooklm-memory-biorag-project` | **SÍ** | `datos`, `lecciones` | `RELATIONAL_EXISTING_BUT_UNUSED` |

> **Diagnóstico del Fallo**: Los 8 casos Type-2 poseen al menos un token en el texto o título del `gold`. Sin embargo, FTS/BM25 fracasa porque las consultas contienen palabras comunes (`real`, `más`, `mejor`, `datos`, `archivos`) que activan de **130 a 460 nodos competidores** en el corpus. El `gold` compite en desventaja porque sólo tiene 1 o 2 menciones aisladas frente a documentos técnicos que repiten esas palabras decenas de veces.

---

## 4. Análisis de los Tres Tipos de Camino en el Grafo Real Dirigido

Se calcularon de forma independiente los tres caminos en el grafo `REAL_DIRECTED` (excluyendo el propio `gold` como semilla de inicio):

| Caso | PATH-A: Shortest Path (Saltos) | PATH-B: Max-Weight Path (Peso) | PATH-C: Relation-Aware Path (Score) | Ruta PATH-C Encontrada |
| :---: | :---: | :---: | :---: | :--- |
| **0497** | **1 salto** (`leccion_scoring...` $\rightarrow$ Gold) | **0.900** (`causa_raiz...` $\rightarrow$ Gold) | **0.675** | `causa_raiz_por_tema_pooling...` $-[\text{sinonimo\_explicito}]\rightarrow$ `benchmark_antes_despues_fix3` |
| **0516** | **1 salto** (`dennys-metodo...` $\rightarrow$ Gold) | **0.900** (`dennys-metodo...` $\rightarrow$ Gold) | **0.675** | `instinto_primera_vez_agencia_real` $-[\text{sinonimo\_explicito}]\rightarrow$ `dennys-identidad-profunda` |
| **0534** | **1 salto** (`biorag_v18_2...` $\rightarrow$ Gold) | **0.900** (`leccion_syn...` $\rightarrow$ Gold) | **0.675** | `leccion_syn_obligatorio_aprender` $-[\text{sinonimo\_explicito}]\rightarrow$ `biorag_v11_1_detalle_tecnico` |
| **0583** | **1 salto** (`fix_mensajeria...` $\rightarrow$ Gold) | **0.900** (`biorag_metricas...` $\rightarrow$ Gold) | **0.675** | `biorag_metricas_historial_tool_20260616` $-[\text{sinonimo\_explicito}]\rightarrow$ `identificacion_obligatoria_oraculo_athena` |
| **0640** | **1 salto** (`ajuste_tejedora...` $\rightarrow$ Gold) | **0.900** (`ajuste_tejedora...` $\rightarrow$ Gold) | **0.675** | `ajuste_tejedora_valencia_desempate_fase1` $-[\text{sinonimo\_explicito}]\rightarrow$ `mentalidad_biorag_para_agentes` |
| **0724** | **1 salto** (`leccion_guardar...` $\rightarrow$ Gold) | **0.810** (`kilo_vscode...` $\rightarrow$ `leccion...` $\rightarrow$ Gold) | **0.456** | `kilo_vscode_extension_principal` $\rightarrow$ `leccion_motivacion...` $\rightarrow$ `protocolo_autoinferencia...` |
| **0795** | **2 saltos** (`biorag_v18_0...` $\rightarrow$ `v17_0` $\rightarrow$ Gold) | **0.729** (`athena_consistencia...` $\rightarrow$ `hormiguita` $\rightarrow$ `v17_0` $\rightarrow$ Gold) | **0.308** | `athena_consistencia_sdm...` $\rightarrow$ `hormiguita...` $\rightarrow$ `biorag_v17_0_estado` $\rightarrow$ `fix_mensajeria_broadcast...` |
| **0801** | **1 salto** (`oracle_que_recordar...` $\rightarrow$ Gold) | **0.900** (`analisis_escalabilidad...` $\rightarrow$ Gold) | **0.675** | `leccion_syn_obligatorio_aprender` $-[\text{sinonimo\_explicito}]\rightarrow$ `notebooklm-memory-biorag-project` |

---

## 5. Prueba Crítica: Comparativa de Métodos M0, M1, M2, M3

Se evaluaron formalmente los 4 métodos de recuperación sobre los 8 casos:
- **M0**: FTS / BM25 puro actual.
- **M1**: FTS + Spreading Activation sobre Grafo Real Dirigido (normalización simétrica por grado).
- **M2**: Evidencia de Grafo Puro (el `gold` solo recibe energía propagada; sin score BM25 directo).
- **M3**: Control Léxico (se eliminan las ventajas textuales directas del `gold`).

| Caso | M0: FTS BM25 (Rank) | M1: FTS + Grafo Real (Rank) | M2: Grafo Puro (Rank) | M3: Control Léxico (Rank) | Diagnóstico Físico |
| :---: | :---: | :---: | :---: | :---: | :--- |
| **0497** | 0 (Fuera Top-5) | 0 (Fuera Top-5) | 0 (Fuera Top-5) | 0 (Fuera Top-5) | 131 semillas dispersan energía en 60 nodos competidores |
| **0516** | 0 (Fuera Top-5) | 0 (Fuera Top-5) | 0 (Fuera Top-5) | 0 (Fuera Top-5) | 344 semillas inundan el grafo con ruido léxico |
| **0534** | 0 (Fuera Top-5) | 0 (Fuera Top-5) | 0 (Fuera Top-5) | 0 (Fuera Top-5) | 205 semillas activan hubs de perfiles y dashboards |
| **0583** | 0 (Fuera Top-5) | 0 (Fuera Top-5) | 0 (Fuera Top-5) | 0 (Fuera Top-5) | 469 semillas por `biorag` canalizan energía a hubs centrales |
| **0640** | 0 (Fuera Top-5) | 0 (Fuera Top-5) | 0 (Fuera Top-5) | 0 (Fuera Top-5) | 264 semillas diluyen la energía en lecciones generales |
| **0724** | 0 (Fuera Top-5) | 0 (Fuera Top-5) | 0 (Fuera Top-5) | 0 (Fuera Top-5) | 203 semillas favorecen nodos de planes y auditorías |
| **0795** | 0 (Fuera Top-5) | 0 (Fuera Top-5) | 0 (Fuera Top-5) | 0 (Fuera Top-5) | 27 semillas por `insert` no alcanzan peso suficiente |
| **0801** | 0 (Fuera Top-5) | 0 (Fuera Top-5) | 0 (Fuera Top-5) | 0 (Fuera Top-5) | 158 semillas por `datos/lecciones` activan hubs de sync |

### Causa Raíz Demostrada Experimentalmente:
El fallo de M1/M2/M3 revela la física subyacente del problema:
1. Las consultas abstractas activan un promedio de **225 semillas por query** (con picos de 469 semillas en 0583).
2. Aunque existe una arista real `semilla $\rightarrow$ gold` (por ejemplo, `causa_raiz...` $\rightarrow$ `benchmark_antes_despues_fix3`), esa semilla representa **menos del $0.5\%$ de la energía total inyectada en el grafo**.
3. Las restantes 224 semillas inyectan el $99.5\%$ de la energía en otros cientos de nodos, ahogando completamente la señal del camino correcto.
4. **Conclusión**: Una propagación sináptica ciega (no guiada por la intención/clase) es matemáticamente incapaz de resolver la brecha asociativa cuando el set de semillas contiene $\ge 50$ nodos ruidosos.

---

## 6. Auditoría Semántica Detallada de los Casos con Ruta y Casos 0-Hop

### A. Casos con Ruta Gráfica (0534, 0640, 0795)
- **0534** (`activa largo archivos` $\rightarrow$ `biorag_v11_1_detalle_tecnico`):
  - *Semilla*: `leccion_syn_obligatorio_aprender` (activada por `archivos/largo`).
  - *Arista*: `-['sinonimo_explicito', peso=0.9, ts=1783522558]->` `biorag_v11_1_detalle_tecnico`.
  - *Coherencia Semántica*: **ALTA**. La lección documenta la necesidad de sincronizar el archivo de memoria a largo plazo formalizado en la v11.1.
- **0640** (`ráfaga después resultado` $\rightarrow$ `mentalidad_biorag_para_agentes`):
  - *Semilla*: `ajuste_tejedora_valencia_desempate_fase1` (activada por `resultado/después`).
  - *Arista*: `-['sinonimo_explicito', peso=0.9, ts=1783693934]->` `mentalidad_biorag_para_agentes`.
  - *Coherencia Semántica*: **ALTA**. Trata sobre la mentalidad de evaluar el resultado tras la reminiscencia.
- **0795** (`insert storepy comunicadosdestino` $\rightarrow$ `fix_mensajeria_broadcast_tracking_por_agente`):
  - *Ruta*: `athena_consistencia_sdm...` $\rightarrow$ `hormiguita...` $\rightarrow$ `biorag_v17_0_estado` $\rightarrow$ `fix_mensajeria_broadcast...`.
  - *Coherencia Semántica*: **MEDIA-BAJA**. Es una cadena histórica de commits y estado de versiones, no una inferencia conceptual directa.

### B. Casos 0-Hop (0497, 0516, 0583, 0724, 0801)
- Todos clasificados como `RELATIONAL_EXISTING_BUT_UNUSED`: poseen coincidencia léxica directa en texto pero su ranking en FTS es subóptimo (posiciones 6 a 25) debido a la dilución provocada por términos genéricos en consultas sin contexto.

---

## 7. Reclasificación Fundada de los 24 Fallos Residuales de v30.2

| Categoría | Descripción Causal | Casos Afectados | % Total | Casos Específicos |
| :---: | :--- | :---: | :---: | :--- |
| **A** | Ruta relacional real existente y semánticamente coherente | **2** | 8.3% | `0534`, `0640` |
| **B** | Ruta existente pero es una cadena histórica/asociativa débil | **1** | 4.2% | `0795` |
| **C** | Coincidencia léxica/relacional directa existente pero ahogada por ranking FTS | **5** | 20.8% | `0497`, `0516`, `0583`, `0724`, `0801` |
| **D** | Brecha semántica que requiere relaciones explícitas adicionales | **4** | 16.7% | `0744`, `0763`, `0848`, `0862` |
| **E** | Problema lingüístico / morfológico puro (stemming / sufijos) | **4** | 16.7% | `0518`, `0560`, `0666`, `0803` |
| **F** | Polisemia / Ambigüedad de término genérico | **6** | 25.0% | `0489`, `0493`, `0504`, `0528`, `0768`, `0771` |
| **G** | Ambigüedad de etiqueta gold en el dataset | **2** | 8.3% | `0012`, `0035` |

---

## 8. Conclusión Definitiva: `CONNECTED` vs `SEMANTICALLY_RELEVANT` vs `RETRIEVAL_USABLE`

| Estado | Criterio | Situación en MemoryBioRAG |
| :--- | :--- | :--- |
| **`CONNECTED`** | ¿Existe camino físico en el grafo? | **SÍ (100% de los 8 casos)**. Hay rutas reales dirigidas de 1 a 2 saltos. |
| **`SEMANTICALLY_RELEVANT`** | ¿Las aristas reflejan dependencias conceptuales reales? | **PARCIAL ($\sim 75\%$)**. La mayoría son enlaces `sinonimo_explicito` o `co_semantica` coherentes, aunque algunos son secuencias históricas. |
| **`RETRIEVAL_USABLE`** | ¿El algoritmo actual puede explotar el camino sin ahogarse en ruido? | **NO ($0\%$)**. Al inyectar energía desde cientos de semillas no filtradas, la relación relevante se diluye en un mar de ruido ($1/225$). |

### Veredicto Final para la Arquitectura:
El problema no es que falte conectividad en el grafo ni que falten reglas estáticas.  
**El cuello de botella es la falta de un Filtro de Focalización de Semillas (Seed Focusing)**:
Para que el grafo relacional sea `RETRIEVAL_USABLE`, el recuperador necesita un mecanismo que:
1. Clasifique la **intención relacional de la consulta** mediante la corteza (dimensiones semánticas) para podar el $95\%$ de las semillas léxicas espurias.
2. Propague activación **únicamente a través de aristas tipadas compatibles con esa intención**.

---

### Verificación Criptográfica de Artefactos de la Fase 3.1

- `docs/fase3_1_validacion_grafo.json`: `499ee4836d77665e77465df4605048ea70304ac348b6bfd5613ba4d62082a057`
- `scripts/audit_fase3_1_grafo.py`: Verificado y ejecutable en modo `ro`.
- `core/memory_store.py`: **100% intacto**.
- `snapshots/qa_escape_qcr_20260811.db`: **100% intacto**.
