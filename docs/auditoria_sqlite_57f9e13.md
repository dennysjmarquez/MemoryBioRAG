# Revisión del candidato SQLite `57f9e13`

## Dictamen

**No recomendar integración o despliegue todavía.** El candidato incorpora defensas valiosas, pero la prueba Windows de CI no ejecutó los tests, existen límites de identidad reproducidos y falta un camino probado para el runtime/base WAL de la instalación del usuario. Esto no es una evaluación exhaustiva ni una certificación de seguridad. Ninguna base original fue abierta ni modificada.

## Alcance revisado

Se revisó `57f9e1318bdc409c2dded05e4fc2b6d451b40760`, padre `555f3bcb3df7c7ad9606e26f9170c96b932e8b77` (que coincidía con `master` remoto al consultar). El diff modifica 32 archivos: política y aperturas SQLite, conexiones por hilo y estado de request, identidad principal/sidecars, rutas y lifecycle del daemon, varios consumidores, tests y CI; no modifica instalador ni dependencias. `git diff --check` pasó. El código y las pruebas se extrajeron en una copia con snapshot de QA versionado, entorno Python aislado con dependencias del proyecto y `pytest-subtests`; no se usaron datos vivos.

Se reprodujeron **797 passed** en `python -m pytest tests/ -q` (275,99 s); subconjunto de rutas, runtime, generaciones, daemon, conexiones por hilo y singleton: **43 passed**. Estos resultados validan la suite bajo el entorno probado, no todos los escenarios de concurrencia ni todas las plataformas. No se ejecutaron separadamente los scripts adicionales de invariantes de CI.

## CI consultada para el commit

En la ejecución 42526947166: Ubuntu y macOS del job focalizado SQLite/locks completaron con `success`; Windows terminó con **failure en `Checkout Code`**, por lo que instalación y prueba SQLite fueron **skipped**. No se ha confirmado la causa del fallo de checkout: los logs detallados no estuvieron disponibles en este entorno. La suite Ubuntu Python 3.11 y 3.12 aparece como `success` en la API de checks. Un fallo antes de los tests no demuestra un defecto de Windows, pero tampoco permite considerarlo validado.

## Identidad de archivos: límite reproducido

En una fixture temporal con journal no-WAL, se sobrescribió el archivo principal **in-place** con otro SQLite preservando su inode. `_assert_database_identity()` lo aceptó: observa `(st_dev, st_ino)`, no el contenido ni la generación lógica. Esta limitación ya se documenta en `specs/008-sqlite-engine/plan.md` y `tasks.md`; no concluir que cualquier modificación del archivo indica anomalía, pues SQLite y procesos autorizados también escriben. Se necesita una política coordinada y pruebas de casos legítimos y adversos antes de afirmar protección contra reemplazos in-place.

Otra fixture retuvo un cursor público antes de renombrar el archivo principal y crear otro en su ruta. La lectura mediante ese cursor siguió viendo la base anterior; obtener nuevamente `m.cursor` sí lanzó `SQLiteDatabaseIdentityChangedError`. Un intento de escritura usando cursor retenido en una prueba adicional falló con `sqlite3.OperationalError: attempt to write a readonly database`; **no se ha demostrado que esa escritura se haya producido**. El código revisa identidad al acceder a la propiedad o al primer acceso de una operación, no intercepta automáticamente todos los usos posteriores de objetos DB-API retenidos; esto también aparece en el plan. Hay ventanas de concurrencia y consumidores independientes que requieren evaluación separada. No extrapolar estas sondas a todos los modos de journal/OS.

## Bloqueos antes de una decisión informada

1. Resolver o reejecutar la matriz Windows y comprobar que realmente se ejecuten las pruebas; preservar el diagnóstico de checkout.
2. Diseñar y medir una estrategia para cambios in-place, acceso por objetos retenidos y sidecars antes de primera observación, o aceptar expresamente límites operativos con restricciones verificables. Evaluar no solo protección sino no interrumpir cambios SQLite legítimos.
3. Probar en copias un camino operativo para una DB WAL existente con SQLite vulnerable, sin detener procesos ni borrar/cambiar originales. El candidato falla cerrado por defecto; no instala automáticamente SQLite corregido ni incluye una CLI de transición. El 3.45.1 que el usuario informó previamente puede ser rechazado por la clasificación basada en versión; verificar el runtime efectivo y posibles backports por proceso, no asumir la versión actual de la laptop ni la causa de la corrupción.
4. Revisar transacciones multipaso, escrituras por consumidores externos y lifecycle bajo múltiples procesos; auditoría del propio candidato los enumera como pendientes. Examinar impacto en rutas de escritura/lectura, asociaciones y recall con baseline reproducible antes de integrar. CI verde no sustituye estas pruebas.
5. Alinear el diff exacto con las otras ramas y `master` vigentes, preservar cambios ajenos y obtener aprobación explícita antes de PR/merge. No se autorizó reparar, reemplazar ni migrar la DB del usuario.

Evidencia privada sintética `auditoria_sqlite_57f9e13.tar.gz`, Drive ID `1J-b4U_wwEFDLfmwaNM7CHal4gZOlhTOG`, SHA-256 `6ec1d24cab884e74805db922ebd30c02965cb520141cd835f5e7492305122150`. Incluye logs y sonda; no contiene DB de usuario. La captura de CI corresponde al momento de esta revisión.
