# Auditoría de corrección del arnés E3 CJK — `8cf0c01`

## Veredicto

**Correcciones verificadas para los controles sintéticos declarados; no se aprueba aplicar los parches.** La reproducción independiente recuperó ambos insumos exactos de Drive privado y repitió los 15 controles, tres brazos y tres repeticiones. Se confirman las coincidencias y la discrepancia de scores notificadas, con los límites que siguen. Esto no cierra E3, no es prueba de producción ni de un agente completo, y no autoriza entrenamiento o cambios de motor.

## Integridad y preparación

Se verificó que el remoto apunta a `8cf0c01c3e59516cb1bfe7aca68bf15ab4b1ebc0`; el commit modifica únicamente informe y arnés, no `core/memory/search.py`. Sus SHA-256 coinciden con lo anunciado: informe `20fc3ac5290772a2796eef66388335a6a5bfe7f3f7424548b9f34ff414c8da1d`, script `d2dca6457a207a3eb8b1dba99565008ed825411c4d29e71e2029b20d40628769`.

La carpeta Drive indicada por Dennys mostró una sola autorización, de propietario. Se descargaron insumos y cinco JSON a `google_drive/` ignorado, sin publicarlos en Git; los seis SHA-256 locales coincidieron con el listado Drive. El hash del archivo de insumos es `c7416de1d010257125592ebf19468c9748761ab56c0d2f318f30e0b9aa2cd02b`.

El operador ejecutó sobre `2438aba`; la reproducción independiente usó `a40b7e9760de37ebebeca0bdf262793a2b133fa8`: no hay diferencias entre esas referencias en `core/`, `middleware/`, `config/`, `biorag.py`, evaluador E3A y gold. Los parches exactos y el arnés se tomaron de `8cf0c01`; se aplicaron e instrumentaron únicamente en árboles temporales. Ambas consultas japonesas se leyeron del archivo privado, no se incluyen en este informe ni en el repositorio. No se tocó una base original ni se entrenó.

## Reproducción y comparación

El arnés usa un proceso por brazo y una fuente SQLite sintética por ejecución, copiándola para cada primaria y cada expansión. Se verificaron los hashes de los insumos y el estado de la fuente; esta nueva ejecución recreó su fuente con SHA `f857e58904adb7f8500b6cea4bfc0adc5637b12f4e1a17ef0b6213aa2a773150`, no el mismo archivo que el operador. Sus conteos observados fueron **123 nodos activos, 5 filas sinápticas y 4 manuales**. El resultado pareado de cada ejecución se interpreta dentro de su propia fuente; no se pretende igualdad byte a byte entre fuentes recreadas.

Comparando por ID y repetición con los JSON archivados del operador, hubo **0 diferencias** en 135 registros de resultados primarios, primarios de la copia de contexto, primarios expandidos, vecinos registrados, totales, candidatos y errores instrumentados. También coincidieron los campos estructurales del sondeo FTS y las comparaciones persistidas entre brazos. Se excluyeron tiempos, picos de memoria y hashes de fuente, que pueden variar; los JSON completos no son byte idénticos.

En esta repetición, las 15 listas de primarios fueron estables entre las tres repeticiones de cada brazo; no hubo diferencias entre primarios de las dos copias limpias. Los errores instrumentados del parche registrados fueron cero en los tres brazos. Esto demuestra el resultado observado, **no que el detector funcione cuando se inyecta un error**, ni que se hayan probado todas las rutas de error.

Se confirma la única discrepancia en OR, control japonés A: en las tres repeticiones la expansión conservó nombres y orden de los dos primarios, cambió sus scores y devolvió cero vecinos nuevos. La fixture enlaza manualmente ambos primarios; el código BFS de `core/memory/synapses.py` puede reforzar un nodo ya visitado, incluidos primarios, y después ordenar por score. El enlace observado y esa ruta son **compatibles** con lo sucedido; no se hizo una ablación pareada del enlace ni se afirma causa exclusiva. No se propone cortar esa asociación.

## Comprobación de las observaciones anteriores

1. Las consultas primaria y de contexto parten ahora de copias independientes, y la segunda usa expansión explícita. Se preservan resultados y comparaciones, incluida la discrepancia, en vez de tratarla como un vecino añadido.
2. Las comparaciones por caso están escritas en los JSON de OR y umbral 2; las tres repeticiones conservan resultados y tiempos individuales. La fixture completa, sus añadidos y conteos finales están documentados.
3. El reloj fijo cubre la construcción de la fixture y sus enlaces. Los insumos japoneses y su receta se conservan en Drive privado. El catch del parche se instrumenta solo en las copias temporales.
4. Límite residual: `_result_rows` corta a cinco también la lista de vecinos antes de registrar y comparar. En esta fixture se observó como máximo un vecino registrado por caso, pero el arnés **no demuestra conservación de todos los vecinos** cuando hubiera más de cinco. Debe medirse una fixture apropiada sin ese recorte de observación; no convertir el límite experimental en pérdida aceptada ni modificar datos o motor por ello.
5. Las mediciones usan `tracemalloc`, fixture pequeña y orden fijo de brazos; no representan p95, toda la memoria nativa de SQLite, carga concurrente o corpus grande. La sonda de error no fue validada mediante una inyección controlada de fallo. La batería es directa, no una evaluación MCP stdio ni de agente independiente.

## Decisión y retorno al plan

Se cierra la revisión de **estas correcciones de arnés**, no E3. OR sigue produciendo candidatos en el negativo japonés; el umbral 2 pierde dos recuperaciones frente a OR en la batería anterior. No filtrar `を指す` ni aplicar automáticamente cualquiera de los parches. Solicitar control de vecinos completo y fallo FTS sintético; en paralelo volver al resto de E3, incluidos los FP ingleses y las obligaciones de etiquetas, manteniendo baseline, diff aislado y pistas. Tras evidencia y autorización específica vendrían cambios de motor, E4, fase 2 y v36; neuronas nuevas después de cimientos.

Evidencia privada de esta reproducción: `google_drive/auditoria_neuronas/auditoria_post_8cf0c01.tar.gz`, SHA-256 `da962e19626a3c67d55f59925b6ad37ce844480a19006afe299a283edbe71ab4`, copia Drive `1osXbEwlIsgjrayOKXxC_5NxZxHBK0Rle`. Incluye JSON sintéticos y log, sin SQLite ni los insumos privados. El resumen de la nueva ejecución tiene SHA `06c6be3cc3bebe6f039b28e03a6eba3aa53dea3abccc6aecb977ed75bb3af97a`. Las salidas completas originales del operador permanecen en su carpeta privada.
