# Auditoría de creación MCP y densidad E3 — `4013677`

## Veredicto

**Reproducido este bloque sintético de 48 sesiones y 24 pares.** No es cierre de E3 ni evaluación de agente autónomo; no se elige una política de etiquetas ni se autoriza cambiar motor o avanzar a E4. Se identificó un defecto de registro de excepciones del arnés que debe corregirse sin descartar la evidencia exitosa.

El remoto del operador apuntaba a `401367748d628363286cd8bb1e519238c5352fcc`; frente a `24287a4` se añadieron el runner, informe y una actualización del inventario. `core`, middleware, configuración, `biorag.py` y launcher stdio inspeccionados coinciden con la rama auditora `bc2fac5`. SHA-256 runner `f582092e241c3d06dbdc9015f3e1d2ff31441ecc0f3269df9300d097db474bd4`; informe `9d017d6525bdcaf0ca3f7bbfd18e0c3faf4367f21f2ced2bdd0610ff7bd00a54`.

## Reproducción

Ejecutamos el arnés exacto desde árbol temporal, entorno aislado, recursos NLTK locales y `PYTHONHASHSEED=0`, mediante el servidor MCP stdio de QA y copias SQLite sintéticas independientes. Salida 0. No se tocaron bases reales, no se aplicó parche ni se fusionaron recuerdos.

- **48/48 brazos** válidos, **24/24 pares**, 432 snapshots y cero errores registrados de grafo o almacenamiento. Los estados de creación, lectura y consolidación fueron `ok` en las 48 sesiones; las búsquedas no registraron errores MCP. Previa sin objetivo en 48/48.
- Las columnas exacta y plegada coincidieron con sus esperados en corto y largo en 48/48; todos los ejemplos son ASCII, sin probar diferencias de normalización. Los campos capturados de concepto, contenido y sinónimos del objetivo coincidieron en 24/24 pares.
- En las nueve etapas comparables, las filas observadas del grafo coincidieron en 24/24 pares. **Alcance exacto:** nueve tablas concretas y la proyección `largo_plazo(concepto, asociaciones)`; no es el grafo completo en todos los posibles almacenamientos ni toda la base SQLite. El metadata `graph_snapshot_scope.full_row_tables` del runner incluye también el alias de esa proyección: debe describirse como proyección, no como décima tabla completa.
- En cada ruta y cuatro densidades se reprodujeron los agregados del informe: historia útil, primario 4/4 activo y 0/4 neutral; contradicha, 4/4 en ambos; vecino, primario 4/4 activo y 0/4 neutral, con neutral en contexto 2/4. Esos conteos son descriptivos de la fixture, no una regla de vigencia ni evidencia de causalidad general.
- Los conteos de filas DMN en el intervalo de primera llamada y de filas manuales tras creación coinciden con el informe. No se deduce que las aristas por sí solas causen el resultado, y no se eliminaron asociaciones. Se realizó un solo orden de consulta por brazo; no se transfiere automáticamente el control de orden de otra fixture.

`guardar` es un alias de la ruta de creación y esta batería no aísla todas las funciones internas ni otras entradas, idiomas o bases. No se cotejaron las trazas privadas originales del operador, que no están disponibles aquí; la reproducción y la evidencia son propias.

## Defecto de registro de excepción

En `execute()`, cuando `run_arm` lanza una excepción, el registro incompleto usa la clave `family`, pero `summarize()` exige `history_family`. Un control local con un registro de ese formato reproduce `KeyError`: en ese fallo el runner puede terminar sin guardar el informe de brazos inconclusos. **No ocurrió en nuestra ejecución exitosa**; no convierte una excepción en éxito, pero sí impide conservar adecuadamente la evidencia del fallo. Corregir la clave y probar la ruta de excepción inyectada en sintético, conservando las corridas originales. No requiere modificación de motor.

## Continuación

Aceptar la medición sintética dentro de sus límites y seguir con el resto del inventario E3. Corregir en paralelo el manejo de excepción y la etiqueta del alcance de snapshot, sin convertir este detalle del arnés en una barrera automática para investigaciones independientes. Mantener pistas y asociaciones; cualquier propuesta de motor requiere baseline, diff aislado, evidencia y autorización específica. E4 y entrenamiento siguen fuera de alcance.

Evidencia privada auditora: `auditoria_e3_densidad_4013677.tar.gz`, SHA-256 `bd154ea71c70d2a434d6f98c039a652b7c9316268bc63635ed7ed36c46f16643`, Drive `1DQX2r4BTH7oEYGxxw9MdNguCtM1Z779e`. Contiene resultados sintéticos y logs de la reproducción, sin SQLite ni datos vivos.
