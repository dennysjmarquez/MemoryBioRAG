# Auditoría PR #13: WAL de otra generación en `ac31b4c`

## Dictamen: no fusionar este commit

La verificación de legibilidad de la copia no demuestra que el WAL pertenezca al archivo principal. Reprodujimos **un WAL ajeno legible, con `quick_check=ok`, que fue aplicado al archivo principal de otra rama**: la fila que antes contenía `branch_B` terminó conteniendo `branch_A` en el archivo principal, sin alerta. Solo se utilizaron archivos temporales sintéticos. No se tocó la DB real; no se demuestra que esto haya sucedido históricamente en ella ni su frecuencia.

El usuario aceptó los límites previos del commit `6ae5740`; eso no equivale a aceptar esta nueva funcionalidad de mover archivos o a autorizar reparación/recreación de la base real. Además, **renombrar un WAL no es inocuo aunque se conserve una copia**: puede separar commits válidos de su base, y con otro proceso todavía abierto podría generar vistas divergentes. No realizar ese procedimiento sobre los originales sin autorización expresa y un protocolo que asegure preservación/coordinación.

## Pruebas positivas

PR #13 head `ac31b4c655dad19b9b72712a8b38a8b1596dc4a4`: GitHub informó `OPEN`, `CLEAN`, `MERGEABLE` y 10 checks exitosos (dos ejecuciones de cinco jobs); `git diff --check 6ae5740 ac31b4c` pasó. En Linux, archivo aislado del commit y entorno de dependencias: **66 pruebas focales** y **820 pruebas de suite completa** pasadas en 335,39 s. Esto no cubre el caso de contenido mezclado aunque estructura resulte válida. El usuario reportó su conteo con dependencias ausentes; nuestra instalación aislada contiene dependencias de la suite y no invalida ese reporte sobre su entorno.

## Prueba pareada: WAL ajeno pero copia legible

Se prepararon dos generaciones sintéticas a partir de la misma base con la misma estructura: el principal de la rama B contiene la fila `branch_B`; la rama A crea un WAL confirmado que cambia esa misma fila a `branch_A`. Se capturaron los bytes del WAL y SHM de A, se cerró la conexión de A y se restauraron esos sidecars junto al principal B, simulando un WAL quedado en disco tras una sustitución de generación. La copia/restauración de sidecars es artificial, no una reproducción de una caída real ni del caso histórico del usuario. Antes de colocar sidecars se abrió exclusivamente la fixture para confirmar `branch_B`.

Se probaron dos brazos, con y sin archivo de huella previo:

- **Con huella:** `_main_changed_since_record` fue `True`, pero `_copy_is_unreadable` fue `False`; `_wal_is_foreign` devolvió `False`.
- **Sin huella:** `_main_changed_since_record` y `_wal_is_foreign` devolvieron `False`; tampoco se rechazó la apertura.
- En ambos, `open_writer` leyó `branch_A`, `PRAGMA quick_check` devolvió `ok`, no se apartó ningún sidecar. Tras cerrar esa conexión, el WAL ya no estaba presente y una nueva conexión leyó `branch_A` en la DB principal.

Resultados iguales en stdlib Linux SQLite 3.40.1 forzando **solo el clasificador** a 3.51.3 para habilitar WAL en fixture y en SQLite 3.53.4 de `pysqlite3==0.6.1`, inyectado temporalmente como módulo `sqlite3` (también con clasificador simulado 3.51.3, versión de política ya corregida). La segunda prueba no valida compatibilidad general de pysqlite3 ni despliegue real. SQLite puede verificar consistencia estructural mientras las páginas provienen de otra generación: `quick_check=ok` no es prueba de pertenencia ni de corrección semántica. No inferir que todos los WAL ajenos sean legibles ni que todo `quick_check` fallido signifique WAL ajeno.

## Otros riesgos en el cambio

- Si falta, es inválida o no puede leerse la huella, `_main_changed_since_record` retorna `False` y se abre el par real. La ruta posterior `_database_is_readable` ejecuta su check después de abrir/configurar la conexión real y podría ser demasiado tarde para preservar la principal. También `_copy_is_unreadable` retorna `False` si `sqlite3.connect` falla: error de comprobación no es prueba de seguridad.
- Si la copia no pasa `quick_check`, el código asume procedencia ajena y renombra WAL/SHM sin establecer que el problema sea realmente el WAL, sin prueba de exclusividad frente a procesos antiguos, y sin verificar antes qué commits válidos contiene. Corrupción del principal, un fallo I/O o una copia inconsistente son otras posibilidades. `_preserve_sidecars` ignora errores de copia; `_rename_sidecars_aside` puede mover solo uno de los dos antes de fallar. Estas son observaciones de código, no una reproducción de pérdida en esos escenarios.
- Copiar principal, WAL y SHM por separado mientras haya escritores no constituye por sí solo un snapshot coherente. No usar `quick_check` sobre una copia inconsistente para decidir automáticamente sobre archivos vivos.

Proponer y revisar una política conservadora: ante combinación sospechosa o evidencia insuficiente, impedir el acceso potencialmente mutador y preservar original y sidecars, sin borrar ni apartarlos automáticamente. La disponibilidad con checkpoints legítimos, ausencia de huella, procesos antiguos y caídas requiere controles independientes; un sello o lock advisory aislado no prueba procedencia universal ni detiene procesos que lo ignoran. Cualquier recuperación real requiere autorización específica.

Evidencia sintética privada `auditoria_pr13_ac31b4c_v2.tar.gz`, Drive ID `1fp-QEDiXuniAU1vQ3l_-WlSpusqwzEf-`, SHA-256 `b3129db3e73c94be8e1c09aee2359eb07dc9b034619b32ce505d06f51f3f1727`; incluye sonda y logs. No se hizo merge ni se modificó `master` o la DB real.
