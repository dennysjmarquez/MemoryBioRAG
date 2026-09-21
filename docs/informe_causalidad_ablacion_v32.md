# INFORME DE CAUSALIDAD Y ABLACIÓN EXPERIMENTAL — BioRAG v32.0

**Fecha:** 2026-09-21 14:49:51  
**Total Casos Evaluados:** 24 consultas  

## 1. Rendimiento Comparativo por Condición Experimental

| Condición | R@1 (%) | R@5 (%) | MRR | Rescates vs A | Daños vs A | Balance Neto |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **[A] Motor base sin Hub ni boost de sustantivos** | 54.17% | 91.67% | 0.6944 | - | - | **Línea Base** |
| **[B] Motor base + Concept Hub** | 50.00% | 95.83% | 0.6611 | 2 | 1 | **+1** |
| **[C] Motor base + Sustantivos Clave** | 54.17% | 91.67% | 0.6944 | 0 | 0 | **+0** |
| **[D] Motor base + Hub + Sustantivos (v32.0)** | 50.00% | 95.83% | 0.6611 | 2 | 1 | **+1** |

## 2. Atribución Causal de Mecanismos (Veredicto de Rescates y Regresiones)

### Condición [B] Motor base + Concept Hub
- **Casos Rescatados:** 2 consultas (que fallaban sin este mecanismo y ahora se recuperan en Top-5)
- **Casos Perjudicados (Daños/Regresiones):** 1 consultas
- **Casos Neutros:** 21 consultas
- **Impacto Neto:** +1 casos ganados netos

### Condición [C] Motor base + Sustantivos Clave
- **Casos Rescatados:** 0 consultas (que fallaban sin este mecanismo y ahora se recuperan en Top-5)
- **Casos Perjudicados (Daños/Regresiones):** 0 consultas
- **Casos Neutros:** 24 consultas
- **Impacto Neto:** +0 casos ganados netos

### Condición [D] Motor base + Hub + Sustantivos (v32.0)
- **Casos Rescatados:** 2 consultas (que fallaban sin este mecanismo y ahora se recuperan en Top-5)
- **Casos Perjudicados (Daños/Regresiones):** 1 consultas
- **Casos Neutros:** 21 consultas
- **Impacto Neto:** +1 casos ganados netos

## 3. Desglose de Procedencia de Candidatos Ganadores (Top-1 Provenance)

Distribución del subsistema que generó el candidato ganador en la Condición D (v32.0):

| Subsistema de Origen | Casos Top-1 | Porcentaje (%) |
| :--- | :---: | :---: |
| `literal` | 14 | 58.3% |
| `concept_hub` | 9 | 37.5% |
| `dimensional_fallback` | 1 | 4.2% |

## 4. Conclusión Científica y Delimitación Metodológica

1. **Balance Causal Cuantificado:** En la condición integrada [D], se registraron 2 rescates y 1 regresión(es) frente a la condición base [A], resultando en un balance neto de +1 casos ganados sobre la muestra evaluada (n=24).
   - Casos con regresión identificados: 0499. La telemetría de procedencia permite aislar el factor (p. ej. inyección de términos con solapamiento parcial / vocabulary drift) para guiar la optimización de guards.
2. **Diferenciación Epistemológica:** Se distingue formalmente entre Candidate Provenance (subsistema que integró el candidato al pool) y Contribución Causal (demostrada mediante la diferencia experimental entre condiciones con el mecanismo activo vs inactivo).
3. **Fundamentación vs. Calibración:** La jerarquía cualitativa de los 5 ángulos se apoya en la teoría de prototipos (Rosch, 1975) y redes semánticas (Collins & Quillian, 1969), mientras que sus multiplicadores escalares exactos corresponden a una calibración empírica en el corpus que debe validarse en pruebas de generalización continua.