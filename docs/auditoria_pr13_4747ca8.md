# Auditoría PR #13: `4747ca8`

## Resultado y decisión recomendada

No fusionar todavía con la afirmación de que solo resta la ventana commit-publicación. La corrección cubre las dos regresiones reportadas en `d5c3834`, la suite completa pasa y la optimización medida es efectiva, pero existe **otra pérdida de cobertura comparada con `2818e72`**: una alteración directa del archivo WAL que no cambie el archivo principal puede pasar sin que el guard calcule la firma del WAL.

El experimento es deliberadamente adversarial sobre una DB desechable: modifica un byte directamente en WAL por fuera de SQLite. No es un commit SQLite válido, ni demuestra que un cliente antiguo ejecutando SQL cause ese resultado, ni que la base real esté corrupta, ni que SQLite no tenga otras comprobaciones. Tampoco demuestra que el defecto suceda normalmente. Sí demuestra que la optimización reduce la detección de modificaciones del WAL que se comprobaba en `2818e72`, y que los comentarios del código que atribuyen el fast path únicamente a que nada cambió son demasiado fuertes. Es una cuestión de alcance de protección a resolver explícitamente antes de presentar el diseño como equivalente.

## Comprobaciones

GitHub PR #13: head `4747ca838624105d1649539d43f185d2067eaa32`, abierto, `CLEAN`, `MERGEABLE`, 10 jobs verdes en dos ejecuciones. `git diff --check d5c3834 4747ca8` pasa. En Linux, árbol aislado del commit, **61 pruebas focales pasaron**; ejecutamos la **suite completa 815 pasadas en 459,61 s**. Entre las focales pasan las pruebas agregadas para alteración in-place de tamaño constante y checkpoint raw sin cambio de tamaño; son los dos controles del informe `d5c3834`.

Comparación de rendimiento aislada en SQLite estándar Linux con clasificador simulado a 3.51.3, WAL físico sintético 18.589.472 bytes, 30 lecturas protegidas repetidas con caché caliente: `2818e72` **1,723 s**, `4747ca8` **0,010 s** en corrida archivada. No extrapolar a uso normal, disco frío u otros sistemas; el anterior es más lento pero no se presenta como una solución segura universal.

## Sonda comparada: alteración directa de WAL

Por cada commit y runtime se creó una DB WAL temporal, tabla y fila sintéticas mediante el motor y se hizo una lectura protegida inicial. Desde un descriptor de archivo se cambió un byte, con XOR, cerca del final del WAL, sin sustituirlo ni cambiar su tamaño. Esto puede invalidar checksums del WAL y es **exclusivamente para probar una modificación directa artificial**. Se comprobó que el digest WAL cambió y que inode WAL y tamaño/mtime/ctime del archivo principal no cambiaron. El guard efectuó otra lectura `COUNT(*)`:

| Commit | SQLite estándar 3.40.1* | SQLite 3.53.4 experimental** |
|---|---|---|
| `2818e72` | `SQLiteDatabaseIdentityChangedError` | `SQLiteDatabaseIdentityChangedError` |
| `4747ca8` | lectura retorna 1 sin alerta | lectura retorna 1 sin alerta |

\* Se fuerza solo el clasificador de versión para habilitar WAL en fixture. ** `pysqlite3==0.6.1` inyectado como módulo `sqlite3` antes de importar el candidato; no es la configuración real ni valida compatibilidad global. El script es de prueba y no debe ejecutarse contra bases reales.

El fast path compara data_version, época y metadata **del archivo principal**; ninguna de estas condiciones implica que el WAL mantenga su contenido. El cambio en WAL no hace que SQLite avance data_version porque no se ejecutó commit SQL. `_remember_connection_snapshot` tiene un fast path semejante. El hecho de que el digest completo esté disponible cuando se llama no significa que se invoque en este caso. Aun añadir metadata del WAL no demuestra protección absoluta frente a carreras, tiempos de archivo o errores de almacenamiento; requiere pruebas propias y contrato claro, sin asumir que el fallo es equivalente a la ventana de commit-publicación.

La ventana commit-publicación previa sigue identificada en el informe `auditoria_pr13_2818e72.md`: este diff no cambia `core/sqlite_runtime.py`. No se volvió a ejecutar esa sonda aquí. Evitar afirmar que la criptografía es la única solución; no se investigaron exhaustivamente las alternativas.

Evidencia sintética privada: `auditoria_pr13_4747ca8.tar.gz`, Drive ID `1rD2pj9_FcskUM7lflIMpW01Fd-Djg71w`, SHA-256 `8ce1a030f7ac777401ae698a3c2b91ba826cdd4d047cf0e951ac8a938d4fa1e7`. Incluye sondas y logs de suite/focal/performance. No se hizo merge, no se tocó `master` ni la base real.
