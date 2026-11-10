# Auditoría PR #13: `6ae5740`

## Dictamen y límites

La corrección del caso de instantánea del informe `41a98a3` se reproduce y no encontramos en estas pruebas otra regresión que impida por sí sola una decisión de integración. **La ventana previamente documentada entre commit SQLite y publicación de la firma sigue abierta**: un commit de una conexión sin protocolo, intercalado ahí, puede quedar atestiguado. Es una limitación demostrada en prueba forzada, no una frecuencia de producción ni una prueba de corrupción. El usuario debe conocerla antes de aceptar el merge; no es válido prometer detección de toda escritura antigua. Firmas y metadata tampoco garantizan integridad completa ni prevención de alteraciones.

Este informe no instala SQLite corregido ni comprueba el estado del sistema de Dennys. Integrar código en Git no actualiza su Python ni repara una DB. Aún se requiere revisar el runtime efectivo de cada escritor y un plan de actualización local. Respetar cierres ordenados, preservar DB/WAL/SHM y no ejecutar migración ni reparación de la DB real automáticamente.

## CI y ejecución

PR #13 head `6ae5740e4bfd9ab873c47e59a45f6e6a6c180f9a`: GitHub informó `OPEN`, `MERGEABLE`, `CLEAN`, 10 checks exitosos (dos ejecuciones × cinco jobs). `git diff --check 41a98a3 6ae5740` pasó. En archivo aislado de `6ae5740`, Linux, entorno virtual de dependencias: **817 pruebas pasadas en 622,06 s**, más **63 focales pasadas en 28,35 s**. La cifra local es 817, no 816. Los resultados de CI no garantizan que cada prueba se haya ejecutado en todas las plataformas.

## Sonda de instantánea y rendimiento

Se repitieron los brazos anteriores con alteración directa de un byte de WAL sintético mediante hook, ya sea después de la firma pero antes de guardar la instantánea o después de completar esta. Ambos lanzaron `SQLiteDatabaseIdentityChangedError` en el candidato y el hook intercalado confirmó que el digest había cambiado. Es una prueba artificial, no un commit SQL válido ni prueba de corrupción real. También pasaron 6 regresiones focales de `tests/test_sqlite_generation.py` con SQLite 3.53.4 vía `pysqlite3==0.6.1` inyectado como `sqlite3`; la inyección es experimental y no demuestra compatibilidad completa ni despliegue real.

Una microprueba de 200 INSERT+commit coordinados secuenciales y count final dio 200 filas en **1,292 s** con stdlib SQLite 3.40.1 y **1,246 s** con pysqlite3 SQLite 3.53.4. El primer caso fuerza el clasificador a 3.51.3 solo para probar WAL en una DB sintética; no hacerlo en producción. Son cifras acotadas con caché y almacenamiento locales, no una comparación A/B ni prueba de «sin coste» en cualquier carga.

## Procesos coordinados

Sonda adicional: motor lector retenido, 10 rondas de dos procesos `open_writer` con INSERT+commit, lectura entre rondas. En SQLite 3.53.4 de pysqlite3 inyectado tanto en padre como hijos (clasificador de versión simulado a 3.51.3, aunque el binario 3.53.4 ya está corregido), cuatro ejecuciones completaron con 20 filas visibles; no equivale a una prueba exhaustiva de WAL, multiproceso ni equivalencia con stdlib. Con stdlib 3.40.1 en modo DELETE, 20 filas visibles.

Con ese mismo stdlib **forzado artificialmente a WAL**, en una ejecución el lector rechazó al desaparecer WAL/SHM tras terminar los dos escritores; se registró para investigación, no como fallo demostrado del camino soportado ni de SQLite 3.53.4. La política del PR no permite normalmente este WAL con SQLite 3.40.1. No se determinó causa ni se observó corrupción; no ignorar el resultado ni forzar esa configuración en uso real.

Evidencia sintética privada: `auditoria_pr13_6ae5740.tar.gz`, Drive ID `17edk7bZMm7alLBafijDTmxhH9Lryu_Gj`, SHA-256 `af8d81301101c5bdec9273d4fbee99f080c4e72de567da630ab65bc0768d550a`. Incluye sondas, resultados y logs completos. No se hizo merge ni se tocó `master` ni una base real.
