# MemoryBioRAG — Evaluación Contrafactual de Desempate SDM en Discovery (Informe Final Cerrado)
**Destinatario:** Aureon (Dirección Científica) & Dennys Márquez  
**Fecha:** 2026-10-13  
**Fase:** Evaluación Contrafactual Exploratoria (Discovery)  
**Estado del Motor `core/`:** 100% Intacto (Cero modificaciones)  
**Snapshot de Referencia:** `snapshots/qa_escape_qcr_20260811.db` (SHA-256: `104dd2902aaf24c3ce93624492ea95a719acbdcca50f4f6bc123ac8317749796`)  
**Dataset Oficial:** `scripts/casos_qa_baseline_v1.jsonl` (SHA-256: `c76a71465f7a9be647094d79f00ffcebd742b00a6c12fa4ae90cf2c3d0654f4c`)  
**Población Evaluada:** Split Discovery (442 casos) + Controles Negativos Dev (20 casos)  
**Script Ejecutor:** `scripts/fase4_desempate_sdm_discovery_aureon.py`  
**Artefacto JSON:** `docs/fase4_desempate_sdm_discovery_reporte.json`  

---

## 1. Precisiones Metodológicas y Matices Requeridos por Aureon

Antes de emitir el veredicto definitivo, se dejan documentados formalmente los tres matices metodológicos requeridos por la Dirección Científica:

### A. El Top-5 se conserva por construcción (No es prueba independiente de seguridad)
El mecanismo probado interviene únicamente intercambiando las posiciones relativas de los dos primeros candidatos devueltos ($c_1 \leftrightarrow c_2$) cuando se cumple la condición de desempate.
- Por definición algorítmica, este intercambio reordena pero no añade ni elimina elementos del conjunto $\{c_1, c_2, c_3, c_4, c_5\}$.
- Por tanto, que el Top-5 se mantenga en 442/442 (100.0%) es una propiedad garantizada por la implementación y **no constituye una prueba empírica independiente de seguridad de recuperación**.
- La métrica verdaderamente informativa de seguridad en este experimento es el **Top-1**.

### B. Asimetría de Representación en la Consulta SDM y Alcance de la Señal
En la función de generación:
```python
q_vec = generar_vector_sdm(concepto=query, contenido=query)
```
- La consulta **no proporciona dimensiones semánticas ni vecinos sinápticos**. Como consecuencia, los segmentos de dimensiones Hebbianas (bits 768..1792) y de vecinos (bits 1920..2048) se encuentran completamente apagados en el vector de consulta.
- Adicionalmente, el argumento predeterminado `categoria=""` activa las proyecciones correspondientes a la cadena vacía.
- Por tanto, la ventaja del 69.4% observada en el diagnóstico exploratorio inicial **no demuestra que las dimensiones semánticas Hebbianas estén identificando a Gold**. La señal proviene de las coincidencias textuales (concepto/contenido) y de la densidad/distribución de bits de los candidatos (donde dimensiones no compartidas engordan el denominador de Jaccard reduciendo la similitud del competidor).
- Medir la contribución aislada de cada segmento requeriría un experimento específico con control de asimetría, el cual no procede realizar para rescatar esta regla.

### C. Auditoría Exhaustiva de Controles Negativos con Criterio Calibrado Oficial
Se auditó formalmente el comportamiento de los 20 controles negativos de desarrollo bajo la definición oficial del arnés:
$$\text{Falso Positivo} \iff \text{len(results)} > 0 \land results[0][4] \ge \text{umbral\_conforme} (0.6212)$$
- **Resultado empírico verificado:** Las **20 consultas de control negativo devolvieron listas estrictamente vacías (0 candidatos recuperados)** en la fase de generación léxica FTS5 BM25.
- Por lo tanto, bajo ambas métricas ($\text{len} > 0$ y criterio calibrado $\ge 0.6212$), la tasa de falsos positivos es idéntica: **0 / 20 (0.0% FP)**. Queda acreditado que la regla de desempate no alteró ni pudo introducir falsos positivos.

---

## 2. Resultados de la Evaluación en Discovery (442 Casos)

| Métrica | Baseline Original | SDM Condicionado | Delta |
|---|---|---|---|
| **Top-1 Hits** | **405 / 442 (91.63%)** | **405 / 442 (91.63%)** | **+0** |
| **Top-5 Hits** | **442 / 442 (100.0%)** | **442 / 442 (100.0%)** | **+0** *(Por construcción)* |
| **MRR** | **0.9483** | **0.9483** | **+0.0000** |
| **Desempates Activados** | — | **2 casos** | — |
| **Ganancias Top-1 (+1)** | — | **1 caso (Caso 0273)** | — |
| **Pérdidas Top-1 (-1)** | — | **1 caso (Caso 0804)** | — |
| **Falsos Positivos (Neg Dev)** | **0 / 20 (0.0%)** | **0 / 20 (0.0%)** | **0** |

### Registro de las 2 Transiciones:
1. **Caso 0273 (`literal`)** — Ganancia Top-1:
   - Query: `"mcp-primitiva-externa-definicion"`
   - Gold: `mcp-primitiva-externa-definicion`
   - Ganador Baseline: `mcp-primitiva-externa-definicion-2` (Gold en Rank 2).
   - SDM: $\Delta_{sdm} = +0.0176$ $\rightarrow$ **Gold promovido a Rank 1**.
2. **Caso 0804 (`typo`)** — Pérdida Top-1 (Regresión):
   - Query: `"cv secion d tets vinculacion"`
   - Gold: `cv_seccion_d_test_vinculacion`
   - Ganador Baseline: `cv_seccion_d_test_vinculacion` (**Gold ya era Rank 1**, score 0.4077; competidor `cv_seccion_d_test_vinculacion2` score 0.4067, margen 0.0010).
   - SDM: $\Delta_{sdm} = +0.0047$ a favor de `cv_seccion_d_test_vinculacion2` $\rightarrow$ **Gold degradado a Rank 2**.

---

## 3. Tratamiento Especial del Caso 0516
Se ratifica formalmente la separación del caso `0516`:
- En dicho caso, el ganador `biorag_v20_rpe_dopamina` fue inyectado directamente en Top-1 por el post-procesador de Concept Hub con score 0.5193, mientras Gold obtuvo 0.3785 en scoring híbrido estándar.
- Esta discrepancia pertenece a la interacción entre el Concept Hub y la lista ordenada, por lo que su diferencia de $-0.1408$ se mantiene documentada pero **separada de la distribución de márgenes homogéneos del ranking híbrido**.

---

## 4. Veredicto Final y Cierre de la Línea de Investigación

### Veredicto: `NO-GO (RECHAZADO)`
1. La política de desempate concreta ensayada (margen $\le 0.010$, detección de alias/versión y $\Delta_{sdm} > 0.003$) **no demostró mejora neta (balance +0)** y **violó el criterio de salvaguarda de cero regresiones** al degradar el caso `0804`.
2. No se modifican umbrales a posteriori para maquillar el resultado ni para eliminar el caso adverso.
3. **El motor `core/` permanece 100% intacto.**
4. Se cierra este informe como evidencia científica reproducible de un resultado negativo útil que delimita con precisión los riesgos y fronteras de la intervención.
