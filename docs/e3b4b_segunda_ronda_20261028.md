# B4b — apoyo real por candidato: diagnóstico en copia

**Veredicto: diagnosticado, sin cambio seguro.** No se modifica el motor ni se aplica el prototipo. La prueba sintética conserva todas las posiciones y elimina los dos falsos positivos ingleses. Sin embargo, una comprobación posterior muestra que el prototipo no interpreta de forma segura todos los apoyos solapados. Se detiene la ronda; no se afirma que la idea general sea imposible.

**Aclaración del auditor:** «si algo baja» se refería a posiciones, R@5/R@1 y falsos positivos por categoría, no a una puntuación que cambia sin mover posiciones. La variación de puntuación de `en-15` no es una regresión bajo ese criterio. La decisión de detenerse se mantiene por el defecto de seguridad en apoyos solapados. **No se ejecutaron MCP ni las cuatro QA oficiales**; sus resultados no se conocen para este prototipo.

## 1. Qué se probó

- Fuente de referencia: `ab8ce2323b4a06886d1ea76d755012f85288fffe`, con motor B4a `94c372d`. Prototipo inyectado solo en memoria; nunca escrito en `core/`.
- Para cada candidato FTS se usan marcas `highlight()` antes del orden y límite. La intención era descartar solo si todos los apoyos eran cortos, internos y sin inicio válido; no se exige una palabra concreta. La prueba de solapamiento de la sección 4 muestra por qué este prototipo **no garantiza** esa intención.
- El cuerpo exacto de `PALABRA_INICIO_ANCHO` B4a se extrajo mediante AST. Coincidió con la función registrada en SQLite en 16 sondas. Diez pruebas unitarias iniciales pasaron, pero no cubrían el solapamiento de la sección 4.
- 120 recuerdos sintéticos y 132 consultas: 20 positivos y 2 negativos por idioma. Misma base fuente para ambos brazos, copia y estado propio por consulta; reloj fijo, `PYTHONHASHSEED=0`, neurona desactivada y WordNet habilitado desde el inicio sin alternar la bandera. Directa: `profundidad=activos`, `limite=5`, `ignore_peso_sinaptico=True`.
- Se alternó el orden de los brazos. La base sintética no cambió durante las búsquedas. SHA de esa base: `49e55c8803c494661210b8a5899a614e303c23c5315b79864220d873b6f6a30e`.

## 2. Prueba directa multilingüe

R@5 y R@1 son cantidades de aciertos sobre 20; FP sobre 2 negativos por idioma.

| Idioma | B4a R@5/R@1/FP | Prototipo R@5/R@1/FP |
|---|---:|---:|
| Chino | 12/12/0 | 12/12/0 |
| Japonés | 12/12/0 | 12/12/0 |
| Coreano | 19/18/0 | 19/18/0 |
| Ruso | 20/19/0 | 20/19/0 |
| Inglés | 20/20/2 | 20/20/0 |
| Español | 20/20/0 | 20/20/0 |
| **Total** | **103/101/2** | **103/101/0** |

- `en-n01`: el falso positivo desaparece; el apoyo resaltado era `play` dentro de `displayed`.
- `en-n02`: el falso positivo desaparece; el apoyo era `lay` dentro de `displayed`.
- `ru-17`: `кодовый замок` conserva posición **2** y puntuación **0,0786**; `число` era un apoyo largo válido. No se exigió `для`.
- `ko-08`: conserva posición **1** y puntuación **0,0782**.
- En los 120 positivos no empeoró ninguna posición. Entre las listas finales de las 132 consultas solo hubo tres diferencias: los dos negativos ingleses anteriores y la puntuación de `en-15` explicada debajo.

## 3. Puntuación que cambió, sin pérdida de posición

Para `en-15`, la respuesta correcta `birthday tart` permanece primera, mientras su puntuación cambia de **0,3121 a 0,2862** (−0,0259; aproximadamente −8,3 %). Se reprodujo tres veces con copias independientes del mismo corpus sintético. Según la aclaración del auditor, este cambio sin pérdida de posición **no cuenta como regresión**.

La traza muestra lo siguiente:

1. B4a construye un conjunto con `birthday tart` y `flute lesson`; el segundo entra por `day` dentro de `Mondays` y no aparece en la lista final.
2. El prototipo retira `flute lesson` por ese apoyo interno y conserva `birthday tart` por sus apoyos largos.
3. Como los dos recuerdos sintéticos comparten el mismo bloque temporal, la señal de afinidad temporal del correcto pasa de **1 a 0** al quedar solo. Las demás señales observadas de ese candidato son iguales. El score híbrido baja de **0,2838 a 0,2579**, y el score final de **0,3121 a 0,2862**.

La causa observada es la composición del conjunto de candidatos y la señal temporal existente (`core/memory/search.py:1644-1649`, `core/memory/episodes.py:94-100`). **No se han cambiado pesos ni ecuaciones.** Los recuerdos sintéticos se crean con reloj fijo; esta observación no establece la frecuencia ni la magnitud del efecto en la memoria viva.

## 4. Apoyos solapados: defecto del prototipo

`highlight()` puede fusionar varios apoyos. Sonda SQLite trigram, con datos sintéticos:

```text
texto:       x漢漢漢漢
MATCH:       "漢漢漢" OR "漢漢漢漢"
resaltado:   x[漢漢漢漢]
B4a("漢漢漢", texto):   1  ← apoyo real válido
B4a("漢漢漢漢", texto): 0  ← tramo fusionado
prototipo:   descarta       ← incorrecto
```

El tramo resaltado por sí solo no demuestra cuáles términos reales aportaron. Este caso debería **conservarse**, pero el prototipo lo descarta. Por ello, la tabla anterior describe lo que hizo el prototipo medido; **no demuestra seguridad para todos los textos ni valida una implementación fiel a la regla pedida**. Esta sonda no demuestra una pérdida final en el motor completo: demuestra que el filtro experimental puede tomar una decisión insegura.

No se intentó otra variante ni se tocó B4a para corregirlo.

### Pendientes acordados

- `en-n02`: revisarlo al reemplazar WordNet; no se cambia WordNet en esta ronda.
- `en-n01`: retomarlo más adelante con un prototipo que resuelva correctamente los solapamientos; no se aplica ese prototipo ahora.

## 5. Coste orientativo

Tiempo de la llamada de búsqueda en los 132 pares, en un solo proceso y sin concurrencia. Excluye la construcción y copia de la base, inicialización de la conexión y compilación del arnés. Valores orientativos para este corpus sintético, no para la viva ni para carga concurrente.

| Medida | B4a | Prototipo |
|---|---:|---:|
| Media | 22,68 ms | 23,60 ms |
| Mediana | 18,53 ms | 19,70 ms |
| Percentil 95 | 55,66 ms | 54,97 ms |

La media subió aproximadamente **0,92 ms por búsqueda**, un **4,0 %** en esta medición; el p95 no demuestra una mejora por sí solo.

## 6. Resguardo e integridad

Evidencias sintéticas bajo `/home/user/MemoryBioRAG_evidencias/e3b4b_apoyo_20261028/`:

- `directa_comparacion.json`: resultados, tiempos, comparaciones y trazas de los 132 casos. SHA `16c21006a9eb26243ca6f9fc31d6894c8daf6af227d81fcf7a36afc844c760a8`.
- `confirmacion_en15.json`: tres repeticiones de la caída. SHA `2b5a8c3db1ecbebdd868e1ea9750b8de20257f2b368a646e4716436e6a8027b1`.
- `traza_score_en15.json`: señales antes/después; observador controlado frente a búsquedas sin observador. SHA `cdfb84c7696b739a88465e1261485198ed380af2672322dad1a1993516120a13`.
- `solapamiento.json`: contraejemplo de marcas fusionadas. SHA `381ad2e9d147c58647a8674f145f7e51b4a73ffa40588455314923da35bd44e3`.
- `b4b_apoyo.py`, `probar_multilingue.py`, `confirmar_en15.py`, `trazar_score_en15.py` y `sonda_solapamiento.py`: arneses de investigación.
- `diff_fts_en_memoria_no_aplicar.patch`: **solo la inserción SQL experimental**, no contiene el arnés ni es un parche completo; no aplicar. SHA `ef2d966b98636a11c6a065b6c9955c7bb6a3a8d994a9cd38ea3aac546fbf0c5d`.

Las huellas del motor después de la investigación siguen siendo `f4479e7d…` para `core/memory/search.py` y `b7e7219c…` para `core/memory_store.py`; el snapshot mantiene `104dd290…`. No se reconstruyó ni abrió la base viva, y no se publica ninguna base ni resultado privado. Este informe es el único archivo de la ronda destinado a la PR #12. La PR continúa en borrador, sin merge; antes de esta publicación su cabeza era `ab8ce23`.
