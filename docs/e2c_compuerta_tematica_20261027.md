# E2c — retirar la compuerta de sinónimos del temático

**Estado: RECHAZADO Y REVERTIDO.** En el snapshot sin ruido, la categoría
`por_tema` bajó de **100,00 % a 98,46 %** de R@5 honesta: el caso 0634 salió
del top-5. Eso incumple el criterio de Dennys. La línea del motor ya fue
restaurada, sin ajustes adicionales; el archivo coincide con `2dff937`.

Las otras tres QA comenzaron antes de revertir, con el candidato ya cargado en
memoria. Las cuatro terminaron; el resultado completo confirma el rechazo.

## Cambio candidato

Un único cambio en el motor. Diff exacto, también guardado en
[`e2c_diff_candidato_20261027.patch`](e2c_diff_candidato_20261027.patch):

```diff
diff --git a/core/memory/search.py b/core/memory/search.py
index dabb618..54a22f8 100644
--- a/core/memory/search.py
+++ b/core/memory/search.py
@@ -1746,7 +1746,7 @@ def buscar_por_frase(self, frase, profundidad="activos", pagina=1, limite=None,
         # (bm25 > 0.001 o concepto_ratio > 0.001) Y no hay señal fuerte de sinónimo
         tematico_score = 0.0
         bm25_val = bm25_norm_map.get(concepto, 0.0)
-        if _perfiles_tematicos and _todas_dims and (bm25_val > 0.001 or concepto_ratio > 0.001) and sinonimos_ratio < 0.5:
+        if _perfiles_tematicos and _todas_dims and (bm25_val > 0.001 or concepto_ratio > 0.001):
             sims = []
             for _, (other_concepto, _, _, _, _, _) in enumerate(todos[:15]):
                 if other_concepto != concepto and concepto and other_concepto:
```

El comentario de la línea anterior queda desactualizado por el candidato; no se
editó porque la instrucción fue cambiar solo la condición.

## Condiciones de la medición

- QA oficial de 921 casos, `BIORAG_NEURONA=0`, `profundidad="activos"` y
  `limite=5` donde corresponde; no se modifica el examen. Los casos de dormido
  y los negativos conservan su tratamiento propio del arnés.
- Snapshot: SHA-256 `104dd2902aaf24c3ce93624492ea95a719acbdcca50f4f6bc123ac8317749796`.
- «Viva»: copia reconstruida del volcado de Drive del 26-10-2026, 1.357 nodos,
  SHA-256 `a61913ce074cd02323c13589040b7ab1e5e4f36b18bbe62c12f9c1d363324e9a`.
  Es la misma copia medida en E2b, no una conexión a una base mutable actual.
- El arnés abre las fuentes en lectura inmutable y trabaja sobre copias propias.
  Se mide cada base sin ruido y con `zzqx` añadido a cada consulta. Para que la
  comparación sea con las mismas condiciones de E2b, las dos corridas con ruido
  llevan el censo activado; las dos sin ruido no lo llevan.
- Baselines: `e1c_qa_honesta_{snapshot,viva}_20261026.json` sin ruido y
  `e2b_qa_ruido_{snapshot,viva}_20261026.json` con ruido. Se comprueban también
  los denominadores y las marcas de casos apartados antes de comparar.
- Criterio de Dennys: no bajar R@5 honesta en ninguna categoría de ninguna
  corrida; no bajar R@1 honesta global; FP 0/40; pytest en verde. Los negativos
  deben estar sin contaminar para que el 0/40 sea válido.

## Caso 0848: consulta exacta de la QA

La consulta es `semánticas 849 embedding`; con ruido se añade al final `zzqx`.
Se llamó a la API pública sobre una copia independiente para cada consulta,
con `BIORAG_NEURONA=0`, `profundidad="activos"` e
`ignore_peso_sinaptico=True`. Igual que la QA, se activó únicamente el esperado
antes de cada búsqueda; en la viva parte dormido. Eso solo se hizo en la copia.

### Salida original antes del cambio

```text
snapshot 0848_sin_ruido    limite= 5 puesto=   4 score=0.3861 candidatos=129
snapshot 0848_sin_ruido    limite=50 puesto=   4 score=0.3861 candidatos=129
snapshot 0848_con_zzqx     limite= 5 puesto=   1 score=0.4388 candidatos=129
snapshot 0848_con_zzqx     limite=50 puesto=   1 score=0.4388 candidatos=129
viva     0848_sin_ruido    limite= 5 puesto=None score=  None candidatos=683
viva     0848_sin_ruido    limite=50 puesto=   6 score=0.3732 candidatos=683
viva     0848_con_zzqx     limite= 5 puesto=None score=  None candidatos=683
viva     0848_con_zzqx     limite=50 puesto=   5 score=0.4272 candidatos=683
```

### Salida original con el candidato

```text
snapshot 0848_sin_ruido    limite= 5 puesto=   1 score=0.4322 candidatos=129
snapshot 0848_sin_ruido    limite=50 puesto=   1 score=0.4322 candidatos=129
snapshot 0848_con_zzqx     limite= 5 puesto=   1 score=0.4388 candidatos=129
snapshot 0848_con_zzqx     limite=50 puesto=   1 score=0.4388 candidatos=129
viva     0848_sin_ruido    limite= 5 puesto=   2 score=0.4193 candidatos=683
viva     0848_sin_ruido    limite=50 puesto=   2 score=0.4193 candidatos=683
viva     0848_con_zzqx     limite= 5 puesto=None score=  None candidatos=683
viva     0848_con_zzqx     limite=50 puesto=   5 score=0.4272 candidatos=683
```

`None` significa **fuera del top-5 servido**, no puesto cero. La consulta con
`limite=50` es solo un diagnóstico complementario: en la viva con ruido, el
puesto 5 obtenido con ese límite **no aparece** en la búsqueda con `limite=5`.
No se debe sustituir el resultado de la QA por el de 50. Las salidas completas
están en [`antes`](e2c_0848_antes_20261027.json) y
[`candidato`](e2c_0848_despues_20261027.json).

## Pytest

Sobre una copia aislada del código candidato, con las dependencias fijadas y sin
activar `BIORAG_NEURONA=0` para pytest:

```text
........................................................................ [ 13%]
........................................................................ [ 26%]
........................................................................ [ 39%]
........................................................................ [ 53%]
........................................................................ [ 66%]
........................................................................ [ 79%]
........................................................................ [ 92%]
......................................                                   [100%]
542 passed in 363.31s (0:06:03)
```

[Salida completa](e2c_pytest_candidato_20261027.log).

## QA antes / candidato

### Las cuatro corridas: resultados globales honestos

| Base | R@5 antes → candidato | R@1 antes → candidato | Fallos R@5 antes → candidato | FP candidato |
|---|---:|---:|---:|---:|
| snapshot sin ruido | **100,00 → 99,88 %** | 95,31 → 95,90 % | **0 → 1** | 0/40 |
| snapshot con `zzqx` | 97,34 → 97,69 % | 88,63 → 89,45 % | 23 → 20 | 0/40 |
| viva sin ruido | **99,88 → 99,54 %** | 93,53 → 94,47 % | **1 → 4** | 0/40 |
| viva con `zzqx` | 96,63 → 97,10 % | 88,12 → 88,71 % | 29 → 25 | 0/40 |

La R@1 global subió y los 40 negativos fueron válidos, sin FP, en las cuatro
corridas. Eso no compensa las caídas de R@5 por categoría, que eran prohibidas.

### R@5 honesta por categoría

| Categoría | Snapshot sin ruido | Viva sin ruido | Snapshot con `zzqx` | Viva con `zzqx` |
|---|---:|---:|---:|---:|
| cruce_idioma | 100 → 100 | 100 → 100 | 62,50 → 62,50 | 62,50 → 62,50 |
| dormido | 100 → 100 | 100 → 100 | 98,46 → 98,46 | 98,46 → 98,46 |
| literal | 100 → 100 | 100 → 100 | 99,38 → 99,38 | 98,56 → 99,18 |
| **por_tema** | **100 → 98,46** | **98,46 → 96,92** | 95,38 → 95,38 | 92,31 → 92,31 |
| pregunta_natural | 100 → 100 | 100 → 100 | 98,46 → 98,46 | 100 → 100 |
| sinonimo | 100 → 100 | 100 → 100 | 88,89 → 95,56 | 85,37 → 87,80 |
| **typo** | 100 → 100 | **100 → 98,46** | 93,85 → 93,85 | 96,92 → 96,92 |
| **variante_gramatical** | 100 → 100 | **100 → 98,46** | 95,38 → 95,38 | 92,31 → 92,31 |

Son porcentajes antes → candidato. Los denominadores y las marcas de los casos
apartados coinciden; la [comparación completa](e2c_comparacion_20261027.txt)
incluye aciertos y totales. El monitor dejó un motivo genérico en su JSON, pero
la comparación **sí es evaluable** y enumera las cuatro bajadas concretas.

### Snapshot sin ruido: regresión que obliga a revertir

| Medida | Antes | Candidato |
|---|---:|---:|
| R@5 honesta global | 100,00 % (865) | 99,88 % (865) |
| R@5 honesta `por_tema` | **100,00 % (65)** | **98,46 % (65)** |
| R@1 honesta global | 95,31 % (853) | 95,90 % (853) |
| FP negativos | 0/40 | 0/40 |

Salida literal del caso que bajó:

```text
[Category: por_tema] (1 total failures)
----------------------------------------
  #1 [ID 0634] Query: "paráfrasis vectores búsqueda"
      Expected:  arquitectura_dos_niveles_biorag
      Returned:  ['principio_paráfrasis_nivel_dios', 'v13_1_parafrasis_expansion_semantica', 'sin_vectores_sin_ml_sin_dependencias'] (scores: [0.516, 0.515, 0.482])
      Reason:    Expected concept not found in top 5 results
```

[Salida completa](e2c_qa_snapshot_normal_20261027.log) ·
[métricas](e2c_qa_snapshot_normal_20261027.json) ·
[fallos](e2c_qa_snapshot_normal_fallos_20261027.jsonl).

El gate clásico del arnés imprime `[GATE] OK`, pero usa otros umbrales. No
sustituye el criterio más estricto de E2c: esta bajada obliga a rechazar.

### Viva sin ruido

| Medida | Antes | Candidato |
|---|---:|---:|
| R@5 honesta global | 99,88 % (861) | 99,54 % (861) |
| R@5 honesta `por_tema` | **98,46 % (65)** | **96,92 % (65)** |
| R@5 honesta `typo` | **100,00 % (65)** | **98,46 % (65)** |
| R@5 honesta `variante_gramatical` | **100,00 % (65)** | **98,46 % (65)** |
| R@1 honesta global | 93,53 % (850) | 94,47 % (850) |
| FP negativos | 0/40 | 0/40 |

El 0848 dejó de fallar, pero entraron dos fallos de `por_tema` (0516 y 0634),
uno de `typo` (0513) y uno de `variante_gramatical` (0518). La mejora puntual
no compensa ninguna de esas bajadas bajo el criterio acordado.

[Salida completa](e2c_qa_viva_normal_20261027.log) ·
[métricas](e2c_qa_viva_normal_20261027.json) ·
[fallos](e2c_qa_viva_normal_fallos_20261027.jsonl).

### Snapshot con `zzqx`

| Medida | Antes | Candidato |
|---|---:|---:|
| R@5 honesta global | 97,34 % (865) | 97,69 % (865) |
| R@5 honesta `sinonimo` | 88,89 % (45) | 95,56 % (45) |
| R@1 honesta global | 88,63 % (853) | 89,45 % (853) |
| FP negativos | 0/40 | 0/40 |

Las otras siete categorías de R@5 honesta no bajaron. El gate clásico terminó en
rojo tanto en la baseline con ruido como con el candidato: compara contra otros
umbrales fijos, no contra la baseline con ruido de E2c.

[Salida completa](e2c_qa_snapshot_ruido_20261027.log) ·
[métricas](e2c_qa_snapshot_ruido_20261027.json) ·
[fallos](e2c_qa_snapshot_ruido_fallos_20261027.jsonl).

### Viva con `zzqx`

| Medida | Antes | Candidato |
|---|---:|---:|
| R@5 honesta global | 96,63 % (861) | 97,10 % (861) |
| R@5 honesta `literal` | 98,56 % (487) | 99,18 % (487) |
| R@5 honesta `sinonimo` | 85,37 % (41) | 87,80 % (41) |
| R@1 honesta global | 88,12 % (850) | 88,71 % (850) |
| FP negativos | 0/40 | 0/40 |

Las otras seis categorías de R@5 honesta no bajaron. El 0848 permaneció fuera
del top-5 con `limite=5`. El gate clásico terminó en rojo tanto antes como con
el candidato, por sus umbrales fijos.

[Salida completa](e2c_qa_viva_ruido_20261027.log) ·
[métricas](e2c_qa_viva_ruido_20261027.json) ·
[fallos](e2c_qa_viva_ruido_fallos_20261027.jsonl).

## Cierre

**Rechazado y revertido** por las caídas de R@5 honesta sin ruido. El candidato
mejoró varias cifras y pasó pytest, pero no cumplió la condición de no perder en
ninguna categoría. El motor vuelve al estado anterior; no se hizo ningún ajuste
adicional. El snapshot y la copia de la viva conservaron sus SHA-256 y no
quedaron `-wal`/`-shm` junto a las fuentes.
