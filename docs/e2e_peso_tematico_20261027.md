# E2e — Anulación del aporte temático

**Estado: RECHAZADO y revertido según los criterios E2e.**

## 1. Cambio autorizado

Se ensayó un único cambio en el numerador de `_calcular_score_hibrido`, en `core/memory/scoring.py`. Ya fue revertido; solo continúa en el árbol aislado que termina las mediciones:

```diff
-            0.08 * tematico_score_gated +      # Similitud temática (gate per-candidate)
+            0.00 * tematico_score_gated +      # Similitud temática (gate per-candidate)
```

El `0.08` del denominador **no** se cambió: así no se reajustan los demás pesos. El diff completo está en [`e2e_diff_candidato_20261027.patch`](e2e_diff_candidato_20261027.patch).

La [prueba directa](e2e_prueba_peso_20261027.txt) comprueba que el aporte temático pasa a cero con y sin evidencia léxica. No sustituye las cuatro QA.

## 2. Protocolo y criterios

- Cuatro parejas: snapshot y copia de la viva; cada una sin ruido y con la palabra `zzqx`.
- Examen oficial de 921 casos, el mismo arnés y los mismos datos en ambas versiones. Se fija `PYTHONHASHSEED=0` desde el inicio y `BIORAG_NEURONA=0`; se usa el censo nativo del arnés solo en ambas mediciones con ruido.
- La QA usa copias independientes y restaura los estados de los nodos entre casos. La búsqueda ordinaria se hace como el examen, con `limite=5` e `ignore_peso_sinaptico=True`; el arnés conserva sus excepciones preexistentes para casos dormidos y negativos.
- Aceptar solo si en **cada pareja** ninguna categoría baja en R@5 honesta, R@1 honesta global no baja, FP es 0/40 con 40 controles válidos y el pytest completo pasa. Si no, se revierte el cambio. No se corrige ningún otro peso.
- El gate clásico con ruido puede fallar por sus umbrales absolutos aun en la referencia: la decisión E2e es la comparación emparejada indicada arriba. Se conservarán sus salidas tal cual.

La «viva» es una copia del backup de Drive del **26-10-2026**, no una conexión a la base actual en vivo. Se confirmó que ese seguía siendo el último archivo `backup_memory_biorag.sql` disponible. SHA-256 de la copia: `a61913ce074cd02323c13589040b7ab1e5e4f36b18bbe62c12f9c1d363324e9a`; MD5 del backup en Drive: `34650056ebcc04427ba3f9b494150026`. SHA-256 del snapshot: `104dd2902aaf24c3ce93624492ea95a719acbdcca50f4f6bc123ac8317749796`. Ambos se consultaron con `mode=ro&immutable=1` sin WAL y se verificaron intactos.

El arnés y el examen de referencia y candidato son idénticos por SHA-256. Las versiones del motor se ejecutan desde dos árboles aislados; solo difieren en la línea del patch. Entorno: Python 3.11.2, SQLite 3.40.1, NumPy 2.4.6 y pytest 9.1.1.

## 3. QA completa

### Global honesta — antes → candidato (%)

| Escenario | R@5 | R@1 | FP válidos |
|---|---:|---:|---:|
| Snapshot, sin ruido | 100.00 → 99.77 | 95.31 → 95.78 | 0/40 → 0/40 |
| Copia viva, sin ruido | 99.88 → 99.54 | 93.53 → 94.24 | 0/40 → 0/40 |
| Snapshot, `zzqx` | 97.34 → 97.69 | 88.63 → 89.45 | 0/40 → 0/40 |
| Copia viva, `zzqx` | 96.63 → 97.10 | 88.12 → 88.71 | 0/40 → 0/40 |

### Sin ruido — R@5 honesta por categoría, antes → candidato

| Categoría | Snapshot % (aciertos/total) | Copia viva % (aciertos/total) |
|---|---:|---:|
| cruce_idioma | 100.00 → 100.00 (8→8/8) | 100.00 → 100.00 (8→8/8) |
| dormido | 100.00 → 100.00 (65→65/65) | 100.00 → 100.00 (65→65/65) |
| literal | 100.00 → 100.00 (487→487/487) | 100.00 → 100.00 (487→487/487) |
| por_tema | 100.00 → 98.46 (65→64/65) | 98.46 → 96.92 (64→63/65) |
| pregunta_natural | 100.00 → 100.00 (65→65/65) | 100.00 → 100.00 (65→65/65) |
| sinonimo | 100.00 → 100.00 (45→45/45) | 100.00 → 100.00 (41→41/41) |
| typo | 100.00 → 100.00 (65→65/65) | 100.00 → 98.46 (65→64/65) |
| variante_gramatical | 100.00 → 98.46 (65→64/65) | 100.00 → 98.46 (65→64/65) |

### Con `zzqx` — R@5 honesta por categoría, antes → candidato

| Categoría | Snapshot % (aciertos/total) | Copia viva % (aciertos/total) |
|---|---:|---:|
| cruce_idioma | 62.50 → 62.50 (5→5/8) | 62.50 → 62.50 (5→5/8) |
| dormido | 98.46 → 98.46 (64→64/65) | 98.46 → 98.46 (64→64/65) |
| literal | 99.38 → 99.38 (484→484/487) | 98.56 → 99.18 (480→483/487) |
| por_tema | 95.38 → 95.38 (62→62/65) | 92.31 → 92.31 (60→60/65) |
| pregunta_natural | 98.46 → 98.46 (64→64/65) | 100.00 → 100.00 (65→65/65) |
| sinonimo | 88.89 → 95.56 (40→43/45) | 85.37 → 87.80 (35→36/41) |
| typo | 93.85 → 93.85 (61→61/65) | 96.92 → 96.92 (63→63/65) |
| variante_gramatical | 95.38 → 95.38 (62→62/65) | 92.31 → 92.31 (60→60/65) |

### Casos honestos nuevos y recuperados

Se muestran los identificadores que cambiaron de acierto a fallo, o al revés. No son los casos apartados de la QA honesta.

| Escenario | Fallos nuevos | Fallos recuperados |
|---|---|---|
| Snapshot, sin ruido | 0518 (variante_gramatical), 0634 (por_tema) | ninguno |
| Copia viva, sin ruido | 0513 (typo), 0516 (por_tema), 0518 (variante_gramatical), 0634 (por_tema) | 0848 (por_tema) |
| Snapshot, `zzqx` | ninguno | 0638 (sinonimo), 0650 (sinonimo), 0781 (sinonimo) |
| Copia viva, `zzqx` | 0258 (literal) | 0043 (literal), 0090 (literal), 0212 (literal), 0214 (literal), 0587 (sinonimo) |

Comparación íntegra, con denominadores y razones: [salida](e2e_comparacion_20261027.txt), [JSON](e2e_comparacion_veredicto_20261027.json) y [comparador](e2e_comparar_20261027.py). [Prueba del comparador](e2e_prueba_comparador_20261027.txt).
Los JSON, fallos y logs originales llevan prefijos `e2e_base_*` y `e2e_candidato_*`.

## 4. Caso 0848, límite 5

El esperado se activa únicamente en la copia temporal, como hace la QA, y se realiza cada búsqueda sobre una copia nueva. Valores `fuera` significan que el esperado no apareció en los cinco resultados servidos.

| Consulta | Snapshot antes → candidato | Copia viva antes → candidato |
|---|---:|---:|
| `semánticas 849 embedding` | 4 → 1 | fuera → 2 |
| `semánticas 849 embedding zzqx` | 1 → 1 | fuera → fuera |

Al haberse revertido el candidato, el motor queda como en la columna «antes»: en la copia viva, 0848 permanece fuera del top 5 con y sin ruido. Fuentes: [antes](e2e_0848_base_20261027.json), [candidato](e2e_0848_candidato_20261027.json), [código de medición](e2e_medicion_0848_20261027.py). Los mismos archivos también muestran `limite=50` como diagnóstico independiente: **no es equivalente** a la búsqueda oficial de límite 5 y no sustituye la tabla.

## 5. Caso de la versión: solo diagnóstico parcial

No fue posible reconstruir la llamada MCP real: la documentación conserva la consulta, los sustantivos y `forzar_rafaga=true`, pero no los textos de las 11 palabras de ráfaga ni de las cuatro paráfrasis. El registro del backup tampoco contiene esa consulta exacta. No se inventaron esos parámetros.

Se midió aparte la consulta documentada y los sustantivos documentados, **sin** ráfaga ni paráfrasis, con neurona apagada, semilla 0 y límite 5, por `_recordar_impl` del MCP sobre copias nuevas. Esa interfaz no expone `ignore_peso_sinaptico`; por tanto, esta medición no es la QA ni reproduce la llamada real.

| Copia viva, llamada parcial | Antes | Candidato |
|---|---:|---:|
| Puesto de `version_actual_biorag` | 3 | 2 |
| Primer resultado | v32.3 | v32.3 |

No se debe comparar este puesto 3 directamente con el puesto 4 de la llamada real histórica. Fuentes: [antes](e2e_version_base_parcial_20261027.json), [candidato](e2e_version_candidato_parcial_20261027.json), [código](e2e_medicion_version_parcial_20261027.py).

## 6. Pruebas

- **Pytest completo del candidato, copia aislada:** `550 passed in 421.46s`. `PYTHONHASHSEED=0`, sin exportar `BIORAG_NEURONA=0`, para no inutilizar las pruebas neuronales. [Salida completa](e2e_pytest_candidato_20261027.log).
- **Script autónomo previo:** `tests/test_tematico_score_regression.py` exige aporte positivo con evidencia léxica. Pasa con el original, falla con el candidato y vuelve a pasar después de revertir. Pytest recoge cero pruebas de ese archivo. No se modificó ni se presenta su fallo como fallo de pytest. [Original](e2e_prueba_tematico_original_20261027.log) / [candidato](e2e_prueba_tematico_candidato_20261027.log) / [revertido](e2e_prueba_tematico_revertido_20261027.log).

## 7. Veredicto

El candidato queda rechazado y el motor fue **revertido byte a byte** a la fórmula de referencia. Se cierra E2 sin más ajustes; el 0848 en la copia viva queda conocido según §4.

Razones de rechazo:
- snapshot normal: baja R@5 honesta por_tema (65→64/65)
- snapshot normal: baja R@5 honesta variante_gramatical (65→64/65)
- viva normal: baja R@5 honesta por_tema (64→63/65)
- viva normal: baja R@5 honesta typo (65→64/65)
- viva normal: baja R@5 honesta variante_gramatical (65→64/65)

[Veredicto verificable](e2e_veredicto_20261027.json). No se hizo merge.
