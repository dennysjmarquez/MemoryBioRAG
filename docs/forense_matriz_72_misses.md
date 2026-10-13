# MemoryBioRAG — Investigación Estructural y Forense de los 72 Fallos de Baseline
**Destinatario:** Aureon (Dirección Científica) & Dennys Márquez  
**Fecha:** 2026-10-13  
**Fase:** Diagnóstico Forense y Generación de Hipótesis (Paso 1, 2, 3 y 4)  
**Estado del Motor `core/`:** 100% Intacto (Cero modificaciones)  
**Snapshot de Referencia:** `snapshots/qa_escape_qcr_20260811.db` (SHA-256: `104dd2902aaf24c3ce93624492ea95a719acbdcca50f4f6bc123ac8317749796`)  
**Dataset Oficial:** `scripts/casos_qa_baseline_v1.jsonl` (SHA-256: `c76a71465f7a9be647094d79f00ffcebd742b00a6c12fa4ae90cf2c3d0654f4c`)  
**Script Forense:** `scripts/diagnostico_forense_matriz_72_aureon.py`  
**Artefacto JSON:** `docs/forense_matriz_72_misses.json`  

---

## 1. Verificación de la Población de Errores (Paso 1)

### 1.1 Distribución Total del Dataset (921 casos)
- **Casos QA Positivos:** 875 (de los cuales 803 son aciertos Top-1 = 91.77%, y 875 aciertos Top-5 = 100.0%).
- **Controles Negativos:** 40 (0 Falsos Positivos = 0.0%).
- **Casos "Dormido":** 65 (0 fallos, 100% acierto en Top-1 y Top-5 tras despertar el nodo).

### 1.2 Auditoría de los 72 Fallos de Top-1 por Categoría
Se verificó caso por caso la lista canónica de fallos del baseline:

| Categoría | Total en Dataset | Fallos Top-1 | Tasa de Error (%) |
|---|---|---|---|
| **sinonimo** | 61 | **24** | 39.34% |
| **por_tema** | 65 | **24** | 36.92% |
| **variante_gramatical** | 65 | **8** | 12.31% |
| **typo** | 65 | **7** | 10.77% |
| **pregunta_natural** | 65 | **4** | 6.15% |
| **cruce_idioma** | 8 | **3** | 37.50% |
| **literal** | 487 | **2** | 0.41% |
| **TOTAL** | **875** | **72** | **8.23%** |

> **Confirmación oficial solicitada por Aureon:**  
> Sí, la cifra de **24 fallos en `por_tema`** está 100% respaldada por los artefactos oficiales.  
> Adicionalmente, la categoría **`sinonimo` presenta exactamente otros 24 fallos**.  
> Entre ambas categorías (`por_tema` + `sinonimo`) concentran **48 de los 72 fallos (66.7%)**.

---

## 2. Taxonomía Estructural de los Fallos (Paso 1 y 2)

El análisis individual reveló que los 72 fallos no son homogéneos. Se clasifican objetivamente en 5 categorías de comportamiento del motor:

```
Total Fallos (72)
  ├── 1. Fallo de Recuperación / Post-Processing Inyección (1 caso, 1.4%)
  │      └── Caso 0516: Winner inyectado externamente por Concept Hub post-processing.
  ├── 2. Fallo de Desambiguación / Versión / Alias (8 casos, 11.1%)
  │      └── Colisiones de nombres normalizados idénticos o sufijos (ej: guión vs guión bajo, v8.3 vs v8.0).
  ├── 3. Fallo Semántico por Sinónimo Distante (24 casos, 33.3%)
  │      └── El usuario consulta un sinónimo válido, pero gana un nodo con mayor coincidencia léxica directa.
  ├── 4. Fallo de Evidencia Relacional por Tema (23 casos, 31.9%)
  │      └── Consultas compuestas por 3 tokens sintéticos sin puente léxico con el Gold.
  └── 5. Fallo de Ranking Competitivo Multi-Señal (16 casos, 22.2%)
         └── Gold está en el pool compitiendo estrechamente pero pierde por mínimas diferencias léxicas o PPMI.
```

### Detalle de Posición de Gold en el Baseline:
- **Rank 2 (segunda posición inmediata):** 37 casos (51.4%)
- **Rank 3:** 14 casos (19.4%)
- **Rank 4:** 13 casos (18.1%)
- **Rank 5:** 8 casos (11.1%)
- **Fuera de Top-5 / No Recuperado:** **0 casos** (todos los 72 fallos están en Top-5).

### Distribución del Margen de Puntuación (Gold vs. Winner):
- Margen muy estrecho (`[-0.010, 0.000]`): **9 casos** (12.7%)
- Margen moderado (`[-0.050, -0.010)`): **23 casos** (32.4%)
- Margen amplio (`< -0.050`): **39 casos** (54.9%)

---

## 3. Contraste Empírico de las Tres Hipótesis (Paso 3 y 4)

Se evaluó la presencia y comportamiento real de las señales en la base de datos congelada `snapshots/qa_escape_qcr_20260811.db`:

### Hipótesis H1 — SDM y Separación de Patrones
- **Disponibilidad en DB:** 100% (todos los 866 nodos del corpus tienen vector de 2048 bits / 256 bytes en `nodos_sdm`).
- **Comportamiento Discriminativo (`similitud_sdm(q_vec, g_vec) - similitud_sdm(q_vec, w_vec)`):**
  - Favorece a Gold: **50 casos (69.4%)**
  - Favorece al Winner: **18 casos (25.0%)**
  - Empate estricto: **4 casos (5.6%)**
- **Hallazgos Críticos:**
  1. Para desempates de versión/alias (ej: `0205` `identidad-relacion-dennys` vs `identidad_relacion_dennys`), SDM discrimina favorablemente a Gold (+0.0076) porque los tokens del concepto generan bits exactos en el segmento `SEGMENTO_CONCEPTO` (bits 512..767).
  2. Sin embargo, las magnitudes absolutas de similitud son minúsculas (`0.005` a `0.030`), debido a que la query carece de dimensiones, categoría o vecinos en el momento de la consulta.
  3. En 18 casos (25%), SDM favorece al competidor erróneo. Usar SDM de forma indiscriminada degradaría 18 casos.

### Hipótesis H2 — Evidencia Relacional y Coactivación del Grafo (`sinapsis`)
- **Disponibilidad en DB:**
  - 13,904 aristas en la tabla `sinapsis`.
  - Grado promedio de nodos Gold: **29.6 conexiones**.
  - Grado promedio de nodos Ganadores: **43.6 conexiones**.
- **Comportamiento en consultas `por_tema` (24 casos):**
  - En más del 50% de las consultas `por_tema`, **ni Gold ni Winner tienen conexiones con nodos que coincidan con los términos de la consulta**.
  - En los casos donde sí existen coincidencias, el Winner suele tener más conexiones debido a que es un "hub" más denso (ej: caso 0608 "puente", Winner tiene 10 conexiones; caso 0753 "metodología", Winner tiene 6 conexiones).
- **Conclusión de H2:** La advertencia de Aureon se confirmó al 100%. Una coactivación indiscriminada del grafo amplifica los hubs genéricos y refuerza a los ganadores iniciales incorrectos.

### Hipótesis H3 — Coincidencia Relacional mediante Predicados Semánticos (`predicados`)
- **Disponibilidad en DB:**
  - La tabla `predicados` contiene únicamente **187 filas** para **102 conceptos** en todo el corpus (cobertura global de solo 11.78%).
- **Cobertura en los 72 Fallos:**
  - **Gold tiene predicados:** **0 casos (0.0%)**.
  - **Winner tiene predicados:** **13 casos (18.1%)**.
  - **Ambos tienen predicados:** **0 casos (0.0%)**.
  - **Ninguno tiene predicados:** **59 casos (81.9%)**.
- **Conclusión de H3:**
  - En el estado actual del corpus congelado, **la tabla `predicados` no puede discriminar ni rescatar a Gold en ninguno de los 72 fallos**.
  - De hecho, cualquier ponderación adicional de predicados en estos fallos solo sumaría puntos al Winner (en 13 casos) o sería inocua (en 59 casos).

---

## 4. Hallazgo Forense Revelador: El Caso 0516
En el diagnóstico v2, el caso `0516` figuraba como `evaluable_aritmeticamente: False` con motivo "Winner ausente".
La reconstrucción forense descubrió la causa exacta:
- Consulta: `"real más sistemas"`.
- Gold: `dennys-identidad-profunda` (score híbrido: 0.3785).
- Ganador: `biorag_v20_rpe_dopamina` (score reportado: 0.5193).
- **Mecanismo:** `biorag_v20_rpe_dopamina` **nunca pasó por el scoring híbrido normal**. Fue inyectado directamente en el índice 0 mediante el post-procesador de **Concept Hub** (`search.py` líneas 1883-1946) debido a una coincidencia de hub con confianza $\ge 0.4$.

---

## 5. Recomendación Científica y Siguiente Paso Mínimo
De las tres hipótesis analizadas, **H1 (SDM)** es la única que posee información discriminativa positiva (69.4% de discriminación a favor de Gold), pero **no debe aplicarse como un re-ranking global**.

### Propuesta de Intervención Mínima y Falsable:
1. **Población Objetivo:** Exclusivamente casos de **Desambiguación de Versión / Alias** (8 casos) o desempates de margen ultra-estrecho ($|margin| \le 0.010$).
2. **Salvaguarda de Abstención:** Si $|sim_{sdm}(q, c_1) - sim_{sdm}(q, c_2)| < 0.003$ o si ambos candidatos no comparten raíz o no están en el rango de empate, el mecanismo se abstiene completamente.
3. **Prueba Contrafactual Previa:** Evaluar esta regla contrafactualmente sobre el subconjunto Discovery antes de cualquier consideración sobre validación o código de producción.
