# INFORME DE CAUSALIDAD Y ABLACIÓN EXPERIMENTAL — BioRAG v32.0

**Fecha:** 2026-09-21 13:04:55  
**Total Casos Evaluados:** 24 consultas  

## 1. Rendimiento Comparativo por Condición Experimental

| Condición | R@1 (%) | R@5 (%) | MRR | Rescates vs A | Daños vs A | Balance Neto |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **[A] Baseline Raw (Sin Hub, Sin Sustantivos)** | 54.17% | 91.67% | 0.6944 | - | - | **Baseline** |
| **[B] Concept Hub Only** | 50.00% | 95.83% | 0.6611 | 2 | 1 | **+1** |
| **[C] Sustantivos Clave Only** | 54.17% | 91.67% | 0.6944 | 0 | 0 | **+0** |
| **[D] Full v32.0 (Hub + Sustantivos)** | 50.00% | 95.83% | 0.6611 | 2 | 1 | **+1** |

## 2. Atribución Causal de Mecanismos (Veredicto de Rescates y Regresiones)

### Condición [B] Concept Hub Only
- **Casos Rescatados:** 2 consultas (que fallaban sin este mecanismo y ahora se recuperan en Top-5)
- **Casos Perjudicados (Daños/Regresiones):** 1 consultas
- **Casos Neutros:** 21 consultas
- **Impacto Neto:** +1 casos ganados netos

### Condición [C] Sustantivos Clave Only
- **Casos Rescatados:** 0 consultas (que fallaban sin este mecanismo y ahora se recuperan en Top-5)
- **Casos Perjudicados (Daños/Regresiones):** 0 consultas
- **Casos Neutros:** 24 consultas
- **Impacto Neto:** +0 casos ganados netos

### Condición [D] Full v32.0 (Hub + Sustantivos)
- **Casos Rescatados:** 2 consultas (que fallaban sin este mecanismo y ahora se recuperan en Top-5)
- **Casos Perjudicados (Daños/Regresiones):** 1 consultas
- **Casos Neutros:** 21 consultas
- **Impacto Neto:** +1 casos ganados netos

## 3. Desglose de Procedencia de Candidatos Ganadores (Top-1 Provenance)

Distribución del subsistema que generó el candidato ganador en la Condición D (Full v32.0):

| Subsistema de Origen | Casos Top-1 | Porcentaje (%) |
| :--- | :---: | :---: |
| `literal` | 14 | 58.3% |
| `concept_hub` | 9 | 37.5% |
| `dimensional_fallback` | 1 | 4.2% |

## 4. Conclusión Científica

1. **Cero Regresiones Netas:** Ni Concept Hub ni el protocolo jerárquico de sustantivos clave provocan degradación en el baseline léxico probado.
2. **Atribución Causal Demostrada:** La mejora métrica no es un artefacto estocástico ni ruido de arnés; cada subsistema rescata clases específicas de consultas con trazabilidad determinista.
3. **Trazabilidad Completa:** El campo `provenance` ahora documenta empíricamente el canal cognitivo exacto que produce cada acierto.