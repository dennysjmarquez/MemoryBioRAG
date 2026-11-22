# Auditoría PR #13, commit `2818e72`

## Dictamen

La corrección **sí cierra los dos experimentos anteriores** (WAL simple y reutilizado) en los entornos sintéticos probados. Sin embargo, no recomiendo aún fusionar: se reprodujo otra ventana en la que un commit raw posterior al commit coordinado queda incluido en su atestación. Además, hashear el WAL completo en cada comprobación introduce un coste proporcional a su tamaño y una regresión importante en una microprueba. Ninguna prueba demuestra corrupción; todas usaron DB temporales.

## Validación

PR #13 head `2818e72700a05ac85429ef82d1dee520a94b5270`; GitHub informó `OPEN`, `CLEAN`, `MERGEABLE` y 10 jobs verdes (dos ejecuciones de cinco jobs). `git diff --check 68e4151 2818e72` pasó. Sobre archivo aislado del commit en Linux: **58 pruebas focales pasadas** y **suite completa 812 pasadas en 476,02 s**. El operador informó lo mismo para la suite y CI. No se abrió la DB real.

Las sondas independientes repitieron cuatro brazos: raw solo y coordinado seguido de raw, tanto con WAL simple como tras checkpoint PASSIVE y reutilización. Los cuatro lanzaron `SQLiteDatabaseIdentityChangedError`. Se repitió con SQLite estándar Linux 3.40.1, forzando solo el clasificador de versión a 3.51.3 para permitir WAL de prueba, y con `pysqlite3==0.6.1` SQLite 3.53.4 inyectado temporalmente como `sqlite3`. Esta inyección no representa la ruta de producción ni establece compatibilidad completa de APIs.

## Ventana commit–atestación

La sonda usa un hook de prueba en `_publish_state_locked`, **no modifica el código del candidato**. Intercala determinísticamente un cliente SQLite sin protocolo justo al inicio de la publicación de firma: el commit coordinado ya terminó y `_assert_no_foreign_commit` ya se ejecutó. El hook verifica desde otra conexión que la fila coordinada ya es visible, y luego hace commit raw antes de calcular la firma. Ambos commits se confirman sin error; la lectura protegida posterior acepta ambas filas `[(1,), (2,)]`, sin `SQLiteDatabaseIdentityChangedError`. Resultado idéntico en los dos runtimes sintéticos indicados.

El lock de época coordina a los clientes compatibles, no al raw. El commit SQLite coordinado termina antes de `publish()`; este experimento demuestra que el raw puede hacer commit en esa ventana y que la firma completa entonces atestigua el estado que ya incluye ambos commits. Es una intercalación deliberada y posible, no una frecuencia estimada ni evidencia de explotación en producción. La sonda es en un solo proceso con conexiones separadas y un hook que fija el orden; no se ha medido probabilidad de que ocurra naturalmente en múltiples procesos. Repetir el control sin raw, con raw tras publicación, y ensayos multiproceso/caídas antes de aprobar. No presentar locks advisory como bloqueo para clientes que los ignoran.

## Coste de la firma completa

Microprueba aislada secuencial, misma máquina, Python SQLite 3.40.1 con clasificador simulado, fixture de tabla sintética, WAL físico de 18.589.472 bytes, 30 `SELECT count(*)` protegidos repetidos, caché caliente. `68e4151` con muestra: **0,010 s**; `2818e72` con hash completo: **1,428 s**. Es una medición acotada, no un benchmark de consultas reales, latencias de disco frío ni predicción de impacto en producción. El código lee todo el archivo WAL para la firma, por tanto el coste de cada comprobación crece con su tamaño; validar carga, concurrencia y presupuestos sin sacrificar seguridad. El valor 68 sirve de comparación de rendimiento, no es una alternativa segura: ese commit falla la prueba de reutilización.

Evidencia privada: `auditoria_pr13_2818e72_v2.tar.gz`, Drive ID `1YLcAeZzMqT03Y6tXMyBhDoHWcDA3nzsg`, SHA-256 `006b1fdc8babfbd0c9a28fbeb86cb4325c7776f590b337503935445f23d5e102` (sondas, logs y suite). No se fusionó PR #13 ni se modificó `master`.
