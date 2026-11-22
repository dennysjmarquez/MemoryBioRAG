# Auditoría PR #13: WAL reutilizado `68e4151`

## Dictamen

**No recomendar merge todavía.** La corrección reproduce el rechazo del caso anterior simple, pero una variante sintética con WAL preexistente y checkpoint PASSIVE dejó pasar una escritura raw posterior a una coordinada, sin alerta, con la misma firma WAL. No se demostró corrupción ni se usaron bases originales. El hallazgo contradice la afirmación de que el tamaño más las muestras de cabecera y cola detectan cada commit WAL.

## Validación positiva

PR #13 head `68e415143f2bbe377a2e0a83a80b2b8b8237f95c`: GitHub informa `CLEAN`, dos ejecuciones de 5 jobs exitosos (suites Ubuntu 3.11/3.12 y SQLite Ubuntu/macOS/Windows), con las omisiones propias de Windows documentadas en el workflow. `git diff --check 9b39f4b 68e4151` pasa. Reproducción en Linux de 56 pruebas focalizadas pasa. Se repitió el control y contraste del informe anterior: sin checkpoint previo ambos ahora lanzan `SQLiteDatabaseIdentityChangedError`, tanto con SQLite estándar simulado como con `pysqlite3` 3.53.4 inyectado en proceso temporal. La suite completa de 810 solo está reportada por operador/CI; no se ejecutó completa localmente aquí.

## Contraste adicional: WAL de tamaño reutilizado

Dos DB sintéticas distintas, cada una con el motor abierto, tabla de prueba, y WAL de 1.689.232 bytes. Se ejecutó un checkpoint PASSIVE mediante `open_writer`, resultado SQLite `(0, 410, 410)`, y se tomó una lectura inicial del cursor protegido. Después:

| Brazo | Escrituras | Firma WAL antes/después del raw | Lectura protegida |
|---|---|---|---|
| Control | cliente raw confirma | diferente | `SQLiteDatabaseIdentityChangedError` |
| Contraste | `open_writer` confirma; cliente raw confirma; lector aún no había vuelto a verificar | **idéntica**, tamaño 1.689.232 | retorna las dos filas, sin alerta |

Los resultados se repitieron con el SQLite estándar 3.40.1 del sandbox forzando **solo el clasificador** a 3.51.3 para permitir WAL en la fixture, y con SQLite 3.53.4 de `pysqlite3==0.6.1` inyectado como módulo `sqlite3` en un proceso de prueba. La inyección no es la configuración de producción del candidato ni valida compatibilidad API. La diferencia entre brazos es la presencia del commit coordinado antes del raw. La firma examina solo tamaño, 64 bytes iniciales y 4096 finales; los resultados son compatibles con reutilización de espacio WAL sin cambiar esas muestras. No se ha identificado qué frame concreto cambió. No se afirma que el contenido raw fuera dañino: se demuestra que **la alerta esperada para una escritura no coordinada no apareció** en este caso.

La seguridad del diseño no puede depender de asumir que todos los commits siempre aumentan el tamaño físico o modifican la cabecera/cola; SQLite puede conservar espacio tras checkpoint. Un digest completo u otro protocolo no debe recomendarse automáticamente: medir coste, checkpoints, frames válidos/generaciones, consistencia de lectura concurrente, caídas, y acceso legacy/external que no acata locks. No alterar DB original ni quitar la detección. La coordinación advisory no impide a escritores que no la acatan.

## Checkpoints y alcance

Con la misma fixture, un checkpoint PASSIVE o TRUNCATE **coordinado** permitió la lectura posterior; un checkpoint ejecutado por una conexión raw bloqueó la lectura protegida tanto en SQLite estándar simulado como en pysqlite3 experimental. La política elegida prevé fallar cerrado ante cambios no coordinados: esto es un límite operativo que debe quedar claro, no por sí solo un bug. No demuestra que todos los checkpoints legítimos y carreras de producción funcionen.

Evidencia privada sintética: `auditoria_pr13_68e4151.tar.gz`, Drive ID `1ePEzH-gKxSrdAVOM5_zrn0OQI4_LZQzs`, SHA-256 `53ebb6fbd5f52a32aae8b54a7ff14a542104faf673d8e47858e0b9938c4b7642`, con sondas pareadas y logs. No se hizo merge ni se modificó `master`.
