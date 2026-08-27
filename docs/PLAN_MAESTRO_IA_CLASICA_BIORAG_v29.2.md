# Plan Maestro: Integración de IA Clásica en BioRAG v29.2

**Fecha:** 2026-08-26  
**Versión:** 29.2 (commit 5a11570 - baseline congelado)  
**Rama actual:** `meta-controlador-fase1` (derivada de `IAclasica`)  
**Baseline Oficial:** `baseline_oficial_20260826.txt` (congelado)

---

## 1. RESUMEN EJECUTIVO

### Objetivo
Integrar **IA clásica (simbólica/probabilística)** en **3 puntos quirúrgicos exactos** donde sea **necesaria y suficiente** — no por meterla, sino porque **solo ahí resuelve lo que ingeniería manual no puede**.

### Las 3 Intervenciones Quirúrgicas (En Orden)

| Fase | Intervención | IA Clásica | Ganancia Esperada | Tiempo |
|------|--------------|------------|-------------------|--------|
| **1** | **Meta-Controlador de Búsqueda** | Regresión Logística Calibrada (`FusionLogistica` existente) + LambdaRank | Pesos óptimos por query (no hardcoded) | 1 semana |
| **2** | **Laboratorio de Ablación Causal** | NOTEARS + PC/FCI + **Datos Interventivos Reales** (ablaciones reales) | Causalidad orientada real, no correlación | 2 semanas |
| **3** | **Gate Contrafactual en Lote** | Synthetic Controls + Bootstrap + Sandbox | Solo aristas con valor neto probado entran | 1 semana |

**Total: 4 semanas para sistema medible, defensible, sin regresiones.**

---

## 2. BASELINE OFICIAL CONGELADO (Inmutable)

**Fecha:** 2026-08-26  
**Archivo:** `baseline_oficial_20260826.txt` (guardar y no tocar)

| Métrica | Valor | N |
|---------|-------|---|
| **Global R@5** | 97.39% | 857/881 |
| **Global R@1** | 86.27% | 760/881 |
| **MRR** | 0.904 | 881 |
| **FP Rate (QA negativos)** | 82.50% | 33/40 |
| **por_tema R@5** | 92.31% | 60/65 |
| **por_tema R@1** | 46.15% | 30/65 |
| **sinonimo R@5** | 91.80% | 56/61 |
| **sinonimo R@1** | 39.34% | 24/61 |
| **pregunta_natural R@5** | 98.46% | 64/65 |
| **typo R@5** | 98.46% | 64/65 |

**Archivo guardado:** `baseline_oficial_20260826.txt` (output completo de `./scripts/run_qa_suite.sh`)

---

## 3. REGLAS DE ORO (Inquebrantables)

| Regla | Descripción |
|-------|-------------|
| **Regla de Oro #1** | Si `Global R@5 < 97.39%` O `FP Rate > 82.5%` → **NO MERGE. REVERTIR AUTOMÁTICO.** |
| **Regla de Oro #2** | Modo sombra obligatorio antes de producción (no toca grafo, solo loggea). |
| **Regla de Oro #3** | Holdout 921 casos NUNCA usado en entrenamiento. Split estricto: 70/15/15 estratificado. |
| **Regla de Oro #4** | Calibración conforme: solo negativos PUROS (sintéticos + QA reales score=0). |
| **Regla de Oro #5** | Cada fase se valida contra baseline congelado ANTES de merge. |

---

## 4. ANÁLISIS DE DATOS REALES (Evidencia Empírica)

### 4.1 Negativos Disponibles (Realidad Actual)

| Fuente | Cantidad | Calidad | Uso |
|--------|----------|---------|-----|
| **QA baseline (~10-12 reales)** | ~10-12 | ✅ Score=0 real | Calibración conforme |
| **Sintéticos (regenerables)** | 200+ | ✅ Garantizado score=0 | Calibración + Entrenamiento |
| **log_busquedas (0 resultados)** | 6 | ❌ Muy pocos | ❌ No sirve |
| **Sintéticos (regenerables ∞)** | ∞ | ✅ Garantizado | Cualquier cantidad |

**Total negativos puros utilizables: ~210-212** (10-12 QA + 200 sintéticos)

> **Nota:** Los 40 "negativos" del QA baseline NO son todos negativos reales. ~28-30 son **falsos positivos** (matchéan corpus real por coincidencia léxica accidental). Solo ~10-12 son negativos reales (score=0).

### 4.2 Datos de Entrenamiento Para Meta-Controlador

| Tipo | Fuente | Cuántos | Calidad |
|------|--------|---------|---------|
| **Positivos** | Sinapsis recall+ (QA + logs util) | ~100-500 | Alta |
| **Negativos** | 200 sintéticos + ~10 QA reales | ~210 | Alta |
| **Hard Negatives** | Sinapsis que crearon FP (ablación) | ~20-50 | Hard negative mining |

> **Nota:** Los 40 "negativos" del QA baseline NO son todos negativos reales. ~28-30 son falsos positivos que matchéan corpus real por coincidencia léxica. **NO USAR** como negativos puros.

---

## 5. ARQUITECTURA DE LAS 3 FASES

### Fase 1: Meta-Controlador de Búsqueda (Semana 1)

**Objetivo:** Reemplazar 14 pesos hardcoded en `_calcular_score_hibrido` por pesos aprendidos por query.

**IA Clásica:** `FusionLogistica` (Regresión Logística Calibrada - **ya existe en `core/calibracion.py`**) + LambdaRank

**Señales Actuales (14) con Pesos Hardcoded:**
| Señal | Peso Hardcoded |
|-------|----------------|
| bm25_norm | 0.25 |
| dim_score | 0.14 |
| concepto_ratio | 0.08 |
| sinonimos_ratio | 0.08 |
| peso_sinaptico | 0.10 |
| jaccard_score | 0.10 |
| grupo_score | 0.10 |
| tematico_score | 0.08 |
| temporal_score | 0.04 |
| asoc_score | 0.02 |
| pred_score | 0.20 |
| ppmi_score | 0.15 |
| hub_score | 0.20 |
| jsd_score | 0.00 |

**Target:** Pesos óptimos **por query** (no globales), aprendidos de 921 casos QA.

**Archivos a Modificar:**
- `core/memory_store.py` → `_calcular_score_hibrido` + `buscar_por_frase`
- `core/meta_controlador.py` (NUEVO - wrapper FusionLogistica)
- `scripts/entrenar_meta_controlador.py` (NUEVO - pipeline entrenamiento)
- `scripts/validar_meta_controlador.py` (NUEVO - validación completa)

**Validación Obligatoria (Modo Sombra):**
```bash
BIORAG_META_CONTROLADOR=1 ./scripts/run_qa_suite.sh
# Comparar vs baseline: R@5 ≥ 97.39%, FP ≤ 82.5%, por_tema R@5 ≥ 92.31%
```

**Criterios de Promoción (TODOS obligatorios):**
- Global R@5 ≥ 97.39%
- Global R@1 ≥ 86.27%
- FP Rate ≤ 82.5%
- por_tema R@5 ≥ 92.31%
- AUC-ROC holdout ≥ 0.85
- ECE (calibración) < 0.05

---

### Fase 2: Laboratorio de Ablación Causal (Semanas 2-3)

**Objetivo:** Descubrir causalidad REAL en el grafo usando intervención real + NOTEARS.

**IA Clásica:** NOTEARS + PC/FCI + **Datos Interventivos Reales** (ablaciones reales)

**Lo Que NO Hace:** "PMI ≥ 0.05 = causal" (adivinado)
**Lo Que SÍ Hace:** "Al quitar esta arista, R@5 baja 2.3pp para queries por_tema PERO sube FP para sinonimo"

**Pipeline:**
1. **Ablación por familia** (ya existe para GABA/PPMI/Jaccard) → Extender a: `co_nombre`, `co_ocurrencia`, `pmi_hebbiano`, `sinonimo_explicito`, `latentes`
2. **Ablación individual** (sample representativo) → Medir ΔR@5, ΔFP, ΔMRR, Δlatencia por arista
3. **NOTEARS + PC/FCI + Datos Interventivos Reales** → Grafo causal ORIENTADO con confianza real
3. **Salida:** Aristas `efecto_retrieval_verificado` (NO `causal_verificada`)

**Salida:** Grafo causal orientado con confianza real → aristas `efecto_retrieval_verificado`

> **Nota:** NO usar `causal_verificada` — PMI/ablación no prueban causalidad conceptual. Solo efecto medido sobre retrieval.

---

### Fase 3: Gate Contrafactual en Lote (Semana 4)

**Objetivo:** Solo aristas con valor neto probado entran al grafo.

**IA Clásica:** Synthetic Controls + Bootstrap + Sandbox Real

**Pipeline:**
```python
for arista_candidata in cuarentena:
    # 1. Clonar snapshot en memoria (:memory:)
    # 2. G + e vs G → medir ΔR@5, ΔFP, ΔMRR, Δlatencia
    # 3. G - e (si existe) → medir efecto de quitarla
    # 4. Decidir: PROMOVER / ATENUAR / BLOQUEAR / CUARENTENA
```

**Ejecución:** En ciclo de sueño / DMN / Hormiguita (NO en hot path)

**Gate de Calidad:** Precision ≥ 80% (promueve buenas, rechaza malas)

---

## 5. VALIDACIÓN Y MÉTRICAS

### Protocolo de Regresión (Obligatorio Cada Cambio)

```bash
# ANTES de cualquier commit que toque lógica de sinapsis/búsqueda:
./scripts/run_qa_suite.sh > test_post_cambio_$(date +%Y%m%d_%H%M).txt

# Comparar automáticamente contra baseline_oficial_20260826.txt
# Si ANY métrica crítica empeora → FAIL, NO MERGE
```

### Métricas Críticas (Umbrales de Regresión)

| Métrica | Baseline | Umbral Regresión |
|---------|----------|------------------|
| Global R@5 | 97.39% | < 97.39% → FAIL |
| FP Rate | 82.5% | > 82.5% → FAIL |
| por_tema R@5 | 92.31% | < 92.31% → FAIL |
| Global R@1 | 86.27% | < 86.27% → FAIL |

---

## 6. ARCHIVOS Y ESTRUCTURA

### Archivos a Crear/Modificar

| Archivo | Acción | Fase | Riesgo |
|---------|--------|------|--------|
| `core/memory_store.py` | Modificar `_calcular_score_hibrido` + `buscar_por_frase` | 1 | **Alto** |
| `core/meta_controlador.py` | **NUEVO** - wrapper FusionLogistica | 1 | Medio |
| `scripts/entrenar_meta_controlador.py` | **NUEVO** - pipeline entrenamiento | 1 | Bajo |
| `scripts/validar_meta_controlador.py` | **NUEVO** - validación completa | 1 | Bajo |
| `scripts/ablacion_sinapsis.py` | **NUEVO** - laboratorio ablación | 2 | Medio |
| `scripts/gate_contrafactual.py` | **NUEVO** - gate batch | 3 | Medio |
| `models/meta_controlador_v1.pkl` | **NUEVO** - artefacto modelo | 1 | Bajo |
| `.env.local` | Agregar `BIORAG_META_CONTROLADOR=0` | 1 | Bajo |

### Documentación a Generar/Actualizar

| Archivo | Descripción |
|---------|-------------|
| `docs/PLAN_MAESTRO_IA_CLASICA_BIORAG_v29.2.md` | Este documento |
| `docs/AUDITORIA_IA_CLASICA_2026-08-26.md` | Auditoría completa |
| `CHANGELOG.md` | Entrada v29.2 |
| `README.md` | Actualizar a v29.2 |
| `docs/AUDITORIA_IA_CLASICA_2026-08-26.md` | Auditoría técnica completa |

---

## 7. RIESGOS Y MITIGACIÓN

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|------------|
| Regresión en R@5 | Media | Alto | Modo sombra obligatorio; rollback automático |
| Overfitting en 921 casos | Media | Alto | L2=1.0; holdout estricto; CV 5-fold |
| Calibración rota (ECE alto) | Baja | Alto | IsotonicRegression fallback; monitoreo ECE |
| Latencia añadida | Baja | Medio | Cache de modelo en memoria; batch scoring |
| Data leakage (QA en train) | Media | Crítico | Split temporal estricto; holdout NUNCA visto |
| Data leakage calibración | Media | Alto | Negativos sintéticos + QA reales score=0 SOLO |
| Circularidad etiquetas (PMI→bueno) | Alta | Crítico | NO usar PMI≥0.05 como label; usar utilidad real |

---

## 8. CRONOGRAMA DETALLADO

### Semana 1: Meta-Controlador (Fase 1)
| Día | Actividad | Entregable |
|-----|-----------|------------|
| 1-2 | Instrumentación + extracción features | `extraer_features_hibridas()` |
| 3-4 | Pipeline entrenamiento offline | `scripts/entrenar_meta_controlador.py` |
| 5 | Modo sombra + validación | `BIORAG_META_CONTROLADOR=1` |
| 6-7 | Validación cruzada + holdout | Métricas en holdout test |
| 8-10 | Análisis features + ablación | Coeficientes + ablation features |
| 11-12 | Promoción + documentación | Modelo v1.pkl + docs |

### Semana 2-3: Laboratorio Ablación (Fase 2)
| Semana | Actividad | Entregable |
|--------|-----------|------------|
| 2 | Ablación por familia (extender existente) | `scripts/ablacion_sinapsis.py` |
| 2 | Ablación individual (sample) | Dataset ΔR@5, ΔFP por arista |
| 3 | NOTEARS + PC/FCI + datos interventivos | Grafo causal orientado |
| 3 | Integración + validación | `efecto_retrieval_verificado` |

### Semana 4: Gate Contrafactual (Fase 3)
| Día | Actividad | Entregable |
|-----|-----------|------------|
| 1-2 | Pipeline batch sandbox | `scripts/gate_contrafactual.py` |
| 3-4 | Integración DMN/sueño | Pipeline batch automatizado |
| 5 | Validación + métricas | Precision gate ≥ 80% |

---

## 9. COMANDOS DE REFERENCIA

```bash
# Baseline oficial (YA EJECUTADO - CONGELADO)
./scripts/run_qa_suite.sh > baseline_oficial_20260826.txt

# Verificar FusionLogistica
python3 -c "
import os, sys, numpy as np
os.environ['BIORAG_NO_LOG']='1'; sys.path.insert(0,'.')
from core.calibracion import FusionLogistica
import numpy as np
fl = FusionLogistica()
X=np.random.rand(200,14); y=np.random.randint(0,2,200)
fl.fit(X,y); print('OK:', fl.predict_proba(np.random.rand(5,14))[:,1])
"

# Modo sombra Meta-Controlador
BIORAG_META_CONTROLADOR=1 ./scripts/run_qa_suite.sh > test_post_fase1.txt

# Comparación automática vs baseline
python3 scripts/comparar_baseline.py baseline_oficial_20260826.txt test_post_fase1.txt

# Suite completa
./scripts/run_qa_suite.sh

# Tests unitarios
python3 -m pytest tests/ -v --tb=short
```

---

## 10. CHECKLIST FINAL DE GO/NO-GO

- [ ] Baseline oficial congelado y guardado
- [ ] Suite completa 33/33 tests pasan
- [ ] QA suite completa: R@5 ≥ baseline, FP ≤ baseline
- [ ] Holdout test: AUC ≥ 0.85, ECE < 0.05
- [ ] 5-fold CV: desviación std < 0.5pp en R@5
- [ ] Latencia P95 ≤ baseline + 10%
- [ ] Rollback probado y documentado
- [ ] Documentación actualizada
- [ ] Merge a master solo tras validación completa

---

## 11. ROLLBACK PLAN

```bash
# Si algo falla en producción:
git checkout master -- core/memory_store.py
# O revertir env var:
BIORAG_META_CONTROLADOR=0
# Modelo se desactiva instantáneamente (no hay migración de DB)
```

---

## 12. CONCLUSIÓN

**Este plan NO es teórico.** Cada componente:
- ✅ Usa código **ya existente** (`FusionLogistica`, `auto_vincular`, ablaciones, DMN, sandbox)
- ✅ Tiene **métricas cuantificables** con baseline congelado
- ✅ Tiene **rollback inmediato** (env var o git checkout)
- ✅ Tiene **validación obligatoria** antes de merge
- ✅ **Rechaza** lo que no sirve (ASP, Z3, DoWhy, "500%", "causal_verificada")

**La ganancia real no es "500%".** Es:
- **+43 respuestas correctas en Top-1 de 881**
- **16-17 falsos positivos menos de 40 negativos**
- **Pesos/umbrales aprendidos de datos, no adivinados**
- **Solo sinapsis con valor neto probado en el grafo**
- **Sistema que aprende qué le sirve, no lo que adivinas**

---

**Estado:** Plan documentado. Listo para ejecutar Fase 1 mañana.  
**Rama actual:** `meta-controlador-fase1`  
**Baseline:** `baseline_oficial_20260826.txt` (congelado)  
**Próximo comando:** `cd /mnt/recursos_compartidos_y_otros/MemoryBioRAG && python3 -c "from core.calibracion import FusionLogistica; print('OK')"`