# Informe Oficial: Fase 3.2 — Experimento Controlado de Seed Focusing

**Fecha**: 2026-09-05  
**Snapshot auditado**: `snapshots/qa_escape_qcr_20260811.db` (Modo `READ-ONLY`)  
**Hash JSON de Datos Crudos**: `4c9fb37ffe3657cbcf96f47b81af9b27a7ed8a9deb4f4a9ced6c45b0be63e37c` (`docs/fase3_2_seed_focusing.json`)  
**Script de Extracción**: `scripts/proto_seed_focusing.py`  

---

## 1. Objetivo y Metodología Experimental

El objetivo de la **Fase 3.2** fue someter a prueba controlada la hipótesis propuesta al final de la Fase 3.1:
> *¿El Seed Focusing basado en corteza dimensional convierte las rutas existentes del grafo en recuperación efectiva, sin memorizar y sin disparar falsos positivos?*

Se compararon 4 condiciones experimentales bajo protocolo estricto:
- **S0 (Línea Base FTS)**: `Query $\rightarrow$ FTS / BM25` estándar.
- **S1 (Grafo Real No Focalizado)**: `Query $\rightarrow$ Todas las semillas FTS $\rightarrow$ Grafo Real Dirigido $\rightarrow$ Ranking`.
- **S2 (Seed Focusing Dimensional)**: `Query $\rightarrow$ Dimensiones semánticas (13 ejes) $\rightarrow$ Poda/Filtro de semillas $\rightarrow$ Grafo Real Dirigido $\rightarrow$ Ranking`.
- **S3 (Oracle Control)**: Control experimental que inyecta energía **exclusivamente desde la semilla óptima conectada al gold**, aislando el rendimiento intrínseco del grafo.

---

## 2. Tabla Comparativa Principal

| Método | Type-2 R@5 (8) | Type-2 R@1 (8) | Transfer R@5 (8) | Paraphrases R@5 (8) | Hard-Neg FP (60) | Corpus Shift R@5 (6) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **S0 (FTS Actual)** | 0/8 (0.0%) | 0/8 (0.0%) | 0/8 (0.0%) | 0/8 (0.0%) | **0/60 (0.0%)** | 0/6 (0.0%) |
| **S1 (Grafo No Focalizado)** | 0/8 (0.0%) | 0/8 (0.0%) | 0/8 (0.0%) | 0/8 (0.0%) | **0/60 (0.0%)** | 0/6 (0.0%) |
| **S2 (Seed Focusing Dimensional)** | **0/8 (0.0%)** | **0/8 (0.0%)** | **0/8 (0.0%)** | **0/8 (0.0%)** | **19/60 (31.7%)** | **0/6 (0.0%)** |
| **S3 (Oracle Control — Cota Superior)** | **2/8 (25.0%)** | **0/8 (0.0%)** | — *(Control)* | — *(Control)* | 0/60 *(Control)* | — *(Control)* |

---

## 3. Auditoría de Energía: Medición Matemática de la Relación Señal / Ruido

Se calculó de forma exacta la cantidad de energía inyectada en la semilla que conduce al `gold` frente a la energía total inyectada por las semillas competidoras:

| Caso | Query $\rightarrow$ Gold | Nº Semillas FTS | Energía Total Inyectada | Semilla Conectada al Gold | Energía de la Semilla Conectada | % Señal vs Ruido |
| :---: | :--- | :---: | :---: | :--- | :---: | :---: |
| **0497** | $\rightarrow$ `benchmark_antes_despues_fix3` | 131 | 39.50 | `leccion_scoring_peso_bm25...` | 0.3174 | **0.803%** |
| **0516** | $\rightarrow$ `dennys-identidad-profunda` | 344 | 141.64 | `instinto_primera_vez_agencia...` | 0.3705 | **0.262%** |
| **0534** | $\rightarrow$ `biorag_v11_1_detalle_tecnico` | 205 | 57.89 | `leccion_syn_obligatorio...` | 0.2836 | **0.490%** |
| **0583** | $\rightarrow$ `identificacion_obligatoria...` | 469 | 456.17 | `biorag_metricas_historial...` | 1.0000 | **0.219%** |
| **0640** | $\rightarrow$ `mentalidad_biorag_para_agentes` | 264 | 87.83 | `plan_mensajeria_leido...` | 0.4004 | **0.456%** |
| **0724** | $\rightarrow$ `protocolo_autoinferencia...` | 203 | 61.94 | *Ninguna semilla directa en 1 salto* | 0.0000 | **0.000%** |
| **0795** | $\rightarrow$ `fix_mensajeria_broadcast...` | 27 | 6.09 | *Ruta a 2 saltos sin arista directa* | 0.0000 | **0.000%** |
| **0801** | $\rightarrow$ `notebooklm-memory-biorag...` | 158 | 53.18 | `oracle_que_recordar_sobre...` | 0.4225 | **0.794%** |

### Conclusión Físico-Matemática:
- La semilla relevante representa en promedio **apenas el 0.38% de la energía inyectada** (con mínimos de $0.21\%$ en `0583`).
- El **$99.62\%$ restante de la energía** se dispersa en cientos de nodos no correlacionados, saturando los atractores densos (`research-pipeline-ownership-oec`, `installer_biorag_v1`) y cancelando cualquier posibilidad de rescate sin un filtrado estructural estricto.

---

## 4. Por qué Falló el Seed Focusing Dimensional Simple (S2)

1. **Granularidad Insuficiente de las Dimensiones**:
   Las dimensiones de corteza (`dominio_tecnico`, `accion_persistencia_computacion`) están asignadas a más de **300 nodos técnicos** en el corpus. Por tanto, filtrar por "dimensión técnica" solo redujo las semillas de 469 a 339 (poda de solo 20-30%), dejando intacto el $99\%$ del ruido.
2. **Generación de Falsos Positivos en Hard Negatives**:
   Al amplificar nodos por compartir dimensiones genéricas, S2 elevó el score de candidatos no relacionados ante consultas con colisión de palabras (`la persistencia de la memoria en el cuadro de salvador dali al detalle`), generando **19/60 falsos positivos (31.7%)**.
3. **Límite del Grafo No Tipado (S3 Oracle Control = 2/8)**:
   Incluso cuando el Oracle (S3) inyectó energía exclusivamente en la semilla óptima conectada, solo 2 casos (`0516` y `0801`) alcanzaron Top-5. En los otros 6 casos, las aristas salientes no tipadas de esa semilla dispersaron la energía hacia otros destinos sinónimos o de co-ocurrencia con mayor peso histórico.

---

## 5. Clasificación Semántica Definitiva de las Rutas

| Caso | Conectividad (`CONNECTED`) | Relevancia Semántica (`SEMANTICALLY_RELEVANT`) | Utilidad Recuperadora (`RETRIEVAL_USABLE`) | Diagnóstico |
| :---: | :---: | :---: | :---: | :--- |
| **0497** | SÍ (1 salto) | **ALTA** (`causa_raiz...` $\rightarrow$ `benchmark...`) | **NO** (0/8) | Ruta válida pero ahogada por 130 semillas ruidosas |
| **0516** | SÍ (1 salto) | **ALTA** (`dennys-metodo...` $\rightarrow$ `dennys-identidad...`) | **SÍ (solo en S3)** | Requiere aislamiento completo de la semilla |
| **0534** | SÍ (1 salto) | **ALTA** (`leccion_syn...` $\rightarrow$ `biorag_v11_1...`) | **NO** (0/8) | Ruta válida pero diluida en 205 semillas |
| **0583** | SÍ (1 salto) | **MEDIA** (`biorag_metricas...` $\rightarrow$ `identificacion...`) | **NO** (0/8) | 469 semillas por `biorag` destruyen la señal |
| **0640** | SÍ (1 salto) | **ALTA** (`ajuste_tejedora...` $\rightarrow$ `mentalidad...`) | **NO** (0/8) | 264 semillas diluyen la activación |
| **0724** | SÍ (1 salto) | **ALTA** (`leccion_guardar...` $\rightarrow$ `protocolo...`) | **NO** (0/8) | Ruta manual válida pero sumergida en 203 semillas |
| **0795** | SÍ (2 saltos) | **BAJA** (Cadena de versiones `v18` $\rightarrow$ `v17` $\rightarrow$ `fix`) | **NO** (0/8) | Conexión puramente histórica, no semántica |
| **0801** | SÍ (1 salto) | **ALTA** (`analisis_escalabilidad...` $\rightarrow$ `notebooklm...`) | **SÍ (solo en S3)** | Requiere aislamiento completo de la semilla |

---

## 6. Respuesta Concluyente a la Pregunta Fundamental

> **¿La focalización de semillas permite explotar las relaciones que ya existen en el grafo de forma generalizable, o simplemente selecciona retrospectivamente las rutas que sabemos que funcionan?**

### Veredicto Científico:
**La focalización dimensional simple NO permite explotar el grafo de forma generalizable.**
El experimento demuestra concluyentemente que:
1. Las dimensiones semánticas generales son demasiado amplias para discriminar semillas específicas dentro de un corpus técnico homogéneo.
2. El grafo asociativo actual (basado en `sinonimo_explicito` y `co_ocurrencia`) carece de **tipado funcional estricto** (`ES_UN`, `RESUELVE`, `REQUIERE`), por lo que la propagación de energía se desborda hacia nodos colaterales incluso desde semillas relevantes.

---

### Verificación Criptográfica de Artefactos de la Fase 3.2

- `docs/fase3_2_seed_focusing.json`: `4c9fb37ffe3657cbcf96f47b81af9b27a7ed8a9deb4f4a9ced6c45b0be63e37c`
- `scripts/proto_seed_focusing.py`: Verificado y ejecutable contra el snapshot canónico.
- `core/memory_store.py`: **100% intacto**.
- `snapshots/qa_escape_qcr_20260811.db`: **100% intacto**.
