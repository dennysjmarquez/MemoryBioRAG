# Auditoría de controles CJK del operador `2438aba` — 2 nov 2026

## Veredicto

**Evidencia útil y acotada; auditoría parcial, sin aprobación para aplicar los parches.** La reproducción independiente confirmó varios resultados del informe sobre una fixture sintética, pero la segunda consulta japonesa no estaba disponible para verificarla exactamente. Detecté además límites del arnés que deben corregirse antes de usar sus campos como prueba de estabilidad o de conservación de contexto. No se propone filtrar `を指す`, ni borrar pistas o asociaciones. E3 sigue abierto.

## Integridad y procedencia

- El commit remoto `2438aba890b70e775edc3fb685c5bf5cd684b60b` agrega solo el informe y el script; no modifica motor. Hashes del informe `c7e6c7046999eba1631836d2b2849332905a21a9bb7135d693fb3e400a59a1e7` y script `7839c53e1af55e9c9e8e04621a0285e9433a753a8f4ca68e26bf5a3f7bbd4a56`, cotejados con Git. El motor indicado coincide con el de la auditoría anterior.
- El listado de Drive de la carpeta indicada muestra los cinco archivos y checksums declarados, y el manifiesto enlaza el commit. Solo se leyeron metadatos/manifiesto: **no se cotejó aquí el contenido completo de los JSON originales**. El propio manifiesto aclara que la corrida temporal anterior se perdió y que lo archivado es una repetición corregida, no bytes recuperados de aquella.
- El código crea la base E3A completa de **120 recuerdos y una sinapsis reportada antes de añadir datos**, y luego agrega tres recuerdos y dos enlaces. Por tanto no debe describirse como una base de solo tres recuerdos. Los metadatos `nodos=120` y `sinapsis=1` provienen de antes de los añadidos; `extras_synthetic=3` y `manual_links_synthetic=2` son valores asignados por el script, no un conteo final verificado mediante consultas. No inferir el número final exacto de aristas de esas cifras.

## Reproducción independiente parcial

Se ejecutó el script exacto del operador en un árbol aislado, usando motor `6fd27702a7d212fc46e1c315a273c7497e52b5fe`; las rutas de motor, dependencias locales, evaluador y gold cotejadas no difieren de `41e1793`, HEAD informado por el operador. Parches extraídos del commit `2438aba` y aplicados exclusivamente a copias temporales. Base sintética pareada, una copia por consulta/repetición; tres brazos, tres repeticiones, neurona de ranking apagada. No se usaron bases de usuario ni se entrenó.

El primer intento abortó antes de crear la base porque el script copiado tenía otro nombre y su lanzador esperaba el original. Se corrigió el nombre y se ejecutó en un directorio nuevo, exit 0; no se atribuye el primer error al motor.

De los dos textos japoneses requeridos como variables de entorno, se obtuvo el primero desde el gold sintético público por su ID comunicado. El segundo **no está en el script ni en el manifiesto**: se sustituyó por otro texto de prueba para poder ejecutar el arnés, y ese resultado se excluye de toda comparación con el informe. Por ello esto no es una reproducción íntegra de los 15 controles del operador ni una reproducción bit a bit de sus JSON; tampoco valida su control japonés modificado.

En los 14 casos comparables de esta repetición:

- Control japonés original: baseline y umbral 2 sin resultados primarios; OR devolvió dos. La sonda FTS cruda encontró dos candidatos con un único trigrama compartido `を指す` en ambos. Es observación de esta fixture, no regla para eliminar un conector.
- Los casos de mezcla latina, conector inglés, puntuación, partícula japonesa y Han suplementario mostraron el mismo patrón de presencia primaria informado por el operador; hangul mixto no dio primarios en ningún brazo. Esto no demuestra soporte general de esos alfabetos. En Han suplementario, una coincidencia del resto de la consulta no prueba cobertura del carácter excluido.
- Los controles de pista libre y alineada mostraron el mismo patrón de presencia primaria informado. Los nombres esperados aparecieron en el campo que el arnés llama `expanded_context`; el alcance de esa etiqueta requiere la comprobación indicada abajo. No se evaluó un agente independiente ni MCP stdio en esta reproducción.
- Los cinco controles largos produjeron en la sonda FTS cruda las mismas cantidades de trigramas y bytes informadas, sin excepción en **esa sonda**. Esto no prueba que el FTS interno del parche no haya fallado: el parche captura `OperationalError` silenciosamente. La medición fue local, con `tracemalloc` activo, y no es una prueba de coste o p95 en producción ni mide toda la memoria nativa de SQLite.

## Observaciones del arnés a corregir

1. `worker_search` realiza primero la búsqueda primaria y luego otra búsqueda con `context_window=1` **en la misma conexión/copia ya leída**. Calcula contexto como la diferencia de nombres entre ambas listas. Como las lecturas pueden mutar estado y la segunda búsqueda puede cambiar sus primarios, esa diferencia no demuestra por sí sola que todo elemento nuevo sea vecino. Para acreditarlo, usar copias limpias separadas, comprobar igualdad de primarios y contrastar los vecinos con la expansión explícita o el campo MCP `contexto_expandido`; registrar discrepancias, no descartarlas.
2. El script calcula `baseline_top5_missing`, `baseline_context_missing`, `top1_changed` y `score_deltas_for_shared` **en memoria después de cargar los JSON**, pero no vuelve a escribir los archivos ni los incluye en `resumen.json`. No están preservadas esas comparaciones por caso en el artefacto de salida. Los resultados primarios crudos sí están en cada archivo y permiten recalcularlas; esta auditoría no afirma haberlas auditado todas.
3. De las tres repeticiones se guardan medianas de tiempo y del pico de asignación Python, pero los resultados, contexto y sondeo FTS son solo los de la última repetición. No hay comparación registrada de listas y scores entre las tres, ni tiempos individuales; tres ejecuciones no prueban por sí solas repetibilidad de resultados. La estadística de memoria es la **mediana de tres picos observados** bajo `tracemalloc`, no un máximo absoluto de memoria del proceso.
4. El reloj fijo se aplica al constructor inicial y a las búsquedas; la adición de los tres recuerdos y enlaces se hace fuera de ese parche de reloj. Puede dejar fechas distintas; no se ha demostrado que esto altere el resultado. Fijar reloj durante toda la construcción o medir el efecto.
5. El arnés recibe dos consultas por variables y no preserva su texto ni una receta inequívoca de la segunda. Para reproducibilidad completa, conservar ambos insumos o su receta recuperable **en Drive privado**, más hashes, sin publicar consultas ni crosswalk privados. La segunda fue sustituida en esta auditoría y queda sin verificar.

Ninguna observación anterior invalida automáticamente todas las cifras del operador; sí limita lo que se puede afirmar. No se evaluaron aquí las cuatro QA oficiales, escala real, p95, supervivencia de pistas en otras bases o causa exhaustiva de los resultados.

## Siguiente trabajo

Solicitar al operador que corrija el arnés y publique solo script/informe sanitizados; conservar entradas y resultados detallados privadamente, y mostrar pruebas de que errores no se cuentan como listas vacías. Volver a comparar sobre una fuente pareada con las tres repeticiones registradas, contexto separado y comprobado, y reloj uniforme. Mantener los dos parches NO APLICAR, sin avanzar a E4, entrenar ni ejecutar campaña E1 sin autorización.

Evidencia de la reproducción parcial y del primer intento fallido: `google_drive/auditoria_neuronas/auditoria_e3_controles_2438aba.tar.gz`, SHA-256 `62c5c3ae0962d7df2db6d8a865a9a4567c2b2eb6e70ff541074e61dca62fabbd`; copia privada Drive `1_8BcnW2MZtMihG2T2JnNALfq5efpDlrC`, checksum cotejado. Contiene salidas sintéticas, incluido el control sustituido, y la instrumentación privada de esta auditoría; no contiene SQLite ni datos vivos.
