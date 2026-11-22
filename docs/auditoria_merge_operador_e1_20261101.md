# Auditoría limitada del merge del operador y utilidades E1 — 2026-11-01

## Referencias y seguridad del checkout

- Rama remota de esta sesión: `arena/6459e2d0-memorybiorag`, punta `69a1768984554cf08411cb7487601549a80245f9` al efectuar la comprobación.
- Rama del operador: `arena/9a54babb-memorybiorag`, punta `60722742daa7c7f77b9dbc5a3c2a2dd26ffd646b`. `git merge-base --is-ancestor` confirmó que ese commit está incluido en la punta remota propia. El merge tiene dos padres y el segundo es ese commit del operador.
- El HEAD local seguía en `f8c2b166b6f13cd7bbbdffb13135d3d68354b8e0`, con numerosas modificaciones y archivos no rastreados. **El merge remoto no sincronizó ese checkout local.** No se hizo reset, stash, push ni sobrescritura de dichos archivos; para los controles siguientes se extrajeron archivos versionados de `69a1768` a una carpeta temporal independiente. Esa extracción no altera el checkout ni constituye una rama de trabajo adicional.
- Los cinco artefactos principales de paquete E1, generador, fixture, manifiesto y estado de revisión son idénticos entre `6072274` y `69a1768` según `git diff --stat` sobre esas rutas. Esto no examina todos los cambios del merge ni aprueba el producto entero.

## Regeneración aislada

En la copia temporal se ejecutó `scripts/preparar_paquete_ciego_e1.py` con su salida privada por defecto bajo la raíz temporal, no en el checkout. El paquete y el manifiesto generados conservaron exactamente los SHA-256 de los archivos publicados de `69a1768`. Se generaron 33 casos y 156 presentaciones; el crosswalk nuevo tuvo modo `0600` y su hash coincidió con el que devolvió el generador. Un segundo intento sobre la misma ruta privada falló con `FileExistsError`, sin reemplazar la evidencia. No se publicó el contenido ni el digest privado aquí.

## Pruebas limitadas en copia aislada

Python 3.11.2, pytest instalado en un entorno temporal, `PYTHONHASHSEED=0`. Se ejecutaron los archivos:

- `tests/test_qa_intuicion_asociaciones_e1.py`;
- `tests/test_linea_base_segura.py`;
- `tests/test_authorizer_supervisor_subprocess_synthetic.py`;
- `tests/test_sqlite_authorizer_diagnostic_synthetic.py`.

**Resultado final literal:** `67 passed, 2 subtests passed in 1.15s`.

Los primeros intentos no fueron limpios: la primera colección falló con dos errores de importación porque no se configuró `PYTHONPATH` para la copia. Tras corregirlo, tres pruebas fallaron porque la extracción parcial omitía un módulo y un informe de fixture; después de añadirlos, quedó un fallo por otro módulo omitido. Con todos esos archivos extraídos del mismo commit se obtuvo el resultado final anterior. Las pruebas son unitarias/sintéticas y algunas usan SQLite `:memory:` o temporales; no equivalen a ejecutar la campaña E1, medir MCP ni validar rendimiento sobre el cerebro completo. No se abrió una base original.

## Límites

Los 28 desacuerdos siguen pendientes y las pasadas siguen siendo exploratorias/no independientes. La verificación mecánica de originales y transformaciones no equivale a revisión semántica humana de las 156 presentaciones. El gold sigue abierto, W pendiente y no se autorizó ni ejecutó la campaña E1. No se entrenaron neuronas ni se modificaron motor o bases en esta auditoría. No se inspeccionó el plugin OpenCode.

Los resultados aquí no prueban que el merge completo sea funcional.

## Sincronización posterior del checkout

Después de los controles anteriores, Dennys autorizó expresamente actualizar el checkout preservando el trabajo local. Se archivaron y verificaron 384 archivos modificados/no rastreados, se conservó además un stash y se adelantó la misma rama por fast-forward a `69a1768984554cf08411cb7487601549a80245f9`. Del respaldo, 380 archivos ya coincidían exactamente con la versión sincronizada y tres informes que no existían en ella se restauraron; `.gitignore` conserva todo el contenido anterior y añade la protección publicada de `.private_evidence/`. Los 384 quedaron preservados según verificación por SHA-256, salvo `.gitignore`, comprobado como prefijo íntegro más la adición. El archivo local de respaldo estaba fuera del repositorio, con SHA-256 `57c73a84aebd67a018ccd84e8c9f948bae9ef2d589c7fcefdff06c90ef930027`; su manifiesto detallaba los hashes. No se incluyeron archivos ignorados ni bases en el respaldo, ni se tocaron las bases originales. Se conservó un stash como resguardo adicional.

## Restauración posterior del entorno

En un turno posterior el entorno volvió a mostrar el HEAD local anterior `f8c2b16`, aunque el remoto de la rama conservaba `776b1d4` y el contenido de trabajo reconstituido contenía numerosos archivos superpuestos. El respaldo local y stash del entorno anterior no estaban disponibles, por lo que no se presume su persistencia. Se verificó un nuevo respaldo de 599 archivos modificados/no rastreados, sin archivos ignorados ni bases: SHA-256 `b73a8a1494092010e2e95c9599c979805e534c6d6aad73ac1d3af007d5e25009`. Se subió el archivo y su manifiesto a la carpeta privada de revisión de Drive; el SHA-256 devuelto por Drive coincide. No compartir este resguardo con revisores ciegos: puede contener material ajeno a su paquete.

Se conservó un nuevo stash y se adelantó esta misma rama local por fast-forward a `776b1d4`. De los 599 archivos respaldados, 598 ya coincidían byte a byte y uno, el informe privado/sanitizado que no estaba versionado, se restauró con su hash intacto. Se comprobaron los 599 archivos contra el manifiesto. Esto no modifica ni abre una base original. La ubicación en Drive es el resguardo duradero de esta segunda sincronización; el estado de archivos temporales y stash puede variar si el entorno se reinicia.
