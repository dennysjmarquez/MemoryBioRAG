# Auditoría de la corrección del arnés E3 — `6d47725`

## Veredicto

**Corrección parcial verificada; permanecen abiertos los cuatro puntos de `docs/auditoria_replica_etiquetas_3f796c4_20261102.md`.** La réplica sintética y los controles de directorio nuevo se reproducen. No se modifica ni aprueba cambiar el motor, no se escoge política de etiquetas y E3 permanece abierto.

El commit `6d477258ce56e90e5dc466087411492ec7243cc2` es la cabeza remota del operador cotejada. Frente a `3f796c4` solo modifica el informe y el runner; no cambia motor, middleware ni configuración. SHA-256 del runner: `08d193c4ee8cedc771827320ef1474095f9196bb909c012bc7de2149fe9d2657`; del informe: `ff0c9699dd35bed7c4bea11314be4db9fa2a05c9de7c9a9d25cbb3c6eabf31f0`.

## Lo que sí se corrigió y reprodujo

- El informe describe acertadamente el alcance: **nueve tablas de grafo completas más una proyección de asociaciones**, no todas las tablas ni todos los campos de SQLite. El intervalo en que aparece una fila DMN se presenta como observación, sin adjudicar un subpaso interno.
- Desde un árbol y entorno temporales ejecutamos el runner exacto por MCP stdio: salida 0, **32 brazos marcados exitosos, 176 snapshots, cero errores en consultas de snapshot, 16 comparaciones de grafo iguales y ocho controles de orden iguales**. Se mantuvieron las filas manuales en la salida registrada. El control de estado MCP del propio runner tiene el límite indicado abajo.
- La salida detallada se escribió en un directorio nuevo bajo `.private_evidence/` de la copia temporal. Una segunda invocación con el mismo destino fue rechazada; también fue rechazada una ruta externa. Los SHA-256 de archivos del manifiesto de nuestra corrida coinciden con los bytes guardados. No se usaron bases reales ni se aplicaron parches.
- El operador reporta que su evidencia original y copia son byte a byte iguales. No tuvimos acceso a esas dos carpetas privadas del operador y **no verificamos esa igualdad independientemente**; no confundirla con nuestra propia comprobación de checksums ni con la prueba de no sobrescritura.

## Puntos pendientes de la auditoría anterior

1. **Denominador:** el informe sigue atribuyendo las consultas históricas a «cuatro modos». Solo tres de los cuatro modos ejecutan la consulta histórica; `single_current` no la ejecuta. En nuestra salida hubo 24 consultas históricas en total: tres modos × cuatro familias × dos brazos. El denominador correcto no invalida los resultados observados en esas consultas.
2. **Columna exacta:** `stored_pair_matches_expected` aún deriva el exacto a partir de la respuesta plegada en lugar de leer directamente la columna exacta. Por separado cotejamos las dos columnas del snapshot de nuestra corrida: 32/32 coinciden en estos ejemplos ASCII. Eso no valida diferencias entre formas exactas y plegadas.
3. **Errores de `recordar`:** el parser registra `_mcp_is_error`, pero esa bandera aún se descarta al construir el resumen de la consulta antes de comprobar el estado del brazo. El control independiente de la auditoría `5f1a29f` encontró cero indicadores MCP de error en su propia repetición; el runner actual todavía no garantiza detectar el caso de indicador de error sin `status=error`.
4. **Hash del manifiesto:** `SHA256SUMS.json` coincide con el archivo, pero `cue_manifest_sha256` y `private_manifest_sha256` se calculan sin el salto final que sí se escribe. Confirmamos que ese campo no coincide con el SHA-256 del archivo completo. Conviene nombrar por separado hash de contenido canónico y hash de archivo, o usar un único formato de bytes y verificarlo antes y después.

El arnés ahora preserva conjuntos de salida en directorios distintos, lo que es una mejora; no transforma el manifiesto en inmutable durante la ejecución. Los resultados siguen siendo una prueba sintética acotada: ninguna etiqueta histórica se considera automáticamente ruido o falsa, y la prueba no decide vigencia ni comportamiento de un agente autónomo.

## Continuación

Pedir al operador que corrija los cuatro puntos anteriores, manteniendo intactas y separadas las evidencias ya generadas. Estas son correcciones de reporte/arnés, no cambios al motor ni autorización para E4. No hace falta destruir ni reemplazar datos para arreglarlas.

Evidencia privada de nuestra ejecución: `auditoria_e3_replica_6d47725.tar.gz`, SHA-256 `35db0d70cd22b5a1c78f595ae9bc212dbc6235d2184c717ee75a151bf1355cd0`, Drive `1Exxwt9VAJN4ZLxu9cp6pP7Y97ycRXA_c`. Contiene el detalle sintético de nuestra corrida y log, sin bases SQLite ni datos vivos.
