# Auditoría PR #13: política de sal en `039a819`

## Dictamen: no fusionar todavía

El commit `039a819efde435c37ac091469428b1a825b60f39` corrige dos cosas reales: **ya no mueve, renombra ni borra sidecars** y **ya no decide por `quick_check`**. Pero la prueba de pertenencia que introduce, la sal del WAL, no demuestra lo que se le atribuye.

Reproduje, con archivos temporales, el escenario original del usuario —la base versionada se sustituye al cambiar de rama y el `-wal` de la rama anterior se queda en disco—: **la sal coincide, el motor no sospecha, y el diario ajeno se aplica en silencio**. La base que decía `branch_B` terminó diciendo `branch_A`, con `quick_check=ok` y sin rechazo.

La sal identifica **al diario**, no a su dueño. Si el archivo principal se reemplaza y el `-wal` es el mismo de antes, la sal sigue siendo la anotada. Es exactamente el caso de uso que motivó estos commits.

## Pruebas que sí pasan

- `gh pr view 13`: `OPEN`, `MERGEABLE`, `CLEAN`; 10 comprobaciones de CI en verde (cinco jobs ejecutados dos veces).
- `git diff --check ac31b4c 039a819` sin errores.
- En árbol aislado del commit con dependencias instaladas: **819 pruebas de la suite** en 422,21 s y **65 focales** en 22,11 s, todas pasadas.
- El código eliminó `_rename_sidecars_aside`, `_preserve_sidecars`, `_quarantine_orphan_sidecars`, `_copy_is_unreadable` y `_database_is_readable`; no queda ninguna ruta que renombre o borre un sidecar. Hay una escritura nueva, el inventario `.sidecars.json` junto a la base, que no mueve archivos existentes.

## Bloqueante: misma sal, base distinta

Fixture: base con estructura común; rama B con `branch_B`; rama A confirmó `branch_A` dejando un `-wal` con su sal. Se anotó la sal (rama A) como haría el motor, se cerró la conexión y se sustituyó **solo el archivo principal** por el de B, conservando el `-wal`/`-shm` originales —el equivalente sintético de un cambio de rama con sidecars ignorados por git.

Resultado idéntico en SQLite 3.40.1 de stdlib (clasificador simulado a 3.51.3 para habilitar WAL) y en SQLite 3.53.4 de `pysqlite3==0.6.1`:

```
base_before branch_B
recorded_salt_matches_retained_wal True
main_changed True
suspect False
opened_value branch_A   quick_check ok
after_close branch_A
```

Ocurre con y sin huella anotada, tanto abriendo con `sqlite3.connect` como con `open_writer`. Junto al hecho de que `_wal_is_suspect` **ya no consulta la huella del principal**, esto significa que el escenario concreto de la base versionada queda aceptado. Además, las comprobaciones de firma de `6ae5740`/`ac31b4c`, que al menos señalaban que el principal había cambiado, dejaron de participar en la decisión.

Que SQLite lea bien un diario ajeno sigue sin demostrar pertenencia; la sal hereda el mismo problema: es una etiqueta del diario, no un vínculo verificable con el contenido del principal. No afirmo que todos los WAL ajenos compartan sal: solo que el caso de reemplazo de `.db` conservando el `-wal` la comparte, y ese es el caso reportado.

## Riesgo secundario comprobado: rechazo de bases legítimas

La sal se anota tras cada `commit()`. Si el proceso termina y el `-wal` desaparece, la anotación queda apuntando a un diario que ya no existe. Una conexión legítima posterior sobre **la misma base** crea un diario nuevo con sal nueva y el motor lo rechaza:

```
recorded_after_commit True
wal_exists True  salt_matches_record False  suspect True
rejected_legit SQLiteSidecarConflictError
```

Pasó con ambos controladores. No hay pérdida de datos —falla cerrado—, pero bloquea una base sana y puede aparecer tras un cierre normal seguido de una escritura externa, o tras una caída entre el `commit()` y la anotación. No se ha medido su frecuencia real.

## Límite declarado y política recomendada

El propio commit declara que la primera apertura de una base antigua con un `-wal` ajeno no se puede distinguir; es honesto, y con eso el caso del usuario seguiría sin protección si ocurre la primera vez. La adopción automática, en cambio, impide detectar después cualquier sustitución que conserve el diario.

Recomendación antes de mergear:

1. No presentar la sal como prueba de pertenencia; es una etiqueta del diario.
2. Recuperar la comprobación de que el principal cambió desde la última anotación y **combinarla** con la sal, fallando cerrado cuando la combinación sea sospechosa.
3. Verificar sobre una copia antes de abrir el par real, y no abrir el archivo real para decidir.
4. Añadir regresiones para: WAL ajeno con sal coincidente tras sustituir el principal; sal obsoleta tras cierre normal y escritura externa; caída entre `commit()` y anotación; ausencia de huella; procesos activos.
5. Mantener la regla actual de no mover, renombrar ni borrar nada.

No se hizo merge ni se tocó `master` ni la base real.

Evidencia privada: `auditoria_pr13_039a819.tar.gz`, Drive ID `1O_pZ2L1NYixcc8fhT8nWYUMg6ehRG23T`, SHA-256 `db12e8b946ef774fc0184813266038448519050636b917c543699e4f6359fd15` (sondas, registros de suite y datos del commit).
