# Estado de E3 al retomar la ruta — 2026-11-01

## Alcance

Cotejo documental y Git para retomar **B4a → resto de E3 → E4 → Fase 2 → v36 → examen de v37**. No es un cierre de fase ni una nueva medición de QA. No se cambiaron motor ni datos, no se ejecutó E1 y no se entrenó ninguna neurona.

## Qué se pudo verificar

- La visión y sus seis condiciones del examen v37 están en `docs/Mi neurona en el sistema/vision_como_recuerda_biorag/README.md`, guardadas en el commit `598c898` incorporado a la rama. El +10 % de p95 figura como **propuesta pendiente de confirmación**, no como decisión. La procedencia por agente también está pendiente de autorización.
- B4a tiene veredicto previo de auditoría en `c98c390`, con comparación de las cuatro QA; esto no implica que los falsos positivos ingleses del análisis multilingüe quedaran reparados ni prueba que la totalidad de E3 esté terminada.
- Cambio 1 y Cambio 2 de E3 cuentan con auditorías e informes previos, en `docs/e3_cambio1_resultados_20261029.md`, `docs/e3_cambio2_resultados_20261029.md` y `docs/auditoria_ci/auditoria_e3_cambio2_20261030.md`. En particular, la auditoría de Cambio 2 reporta 757 pruebas y compara con B3, pero esas corridas son históricas, no una ejecución de este turno. El gate de ruido devolvió código 1 tanto para la referencia como para el candidato; no ocultar ese resultado.
- GitHub confirma que el PR #12 fue fusionado en `master` el 2026-10-30 mediante `41e1793`, con cabecera `fb8cbea6c03d390413c64e9834fdf9e086e71ad0`. Se descargó su referencia de solo lectura y se compararon contra el HEAD de la rama actual los diez archivos de identidad Unicode y Cambio 2 inspeccionados: **sin diferencias de contenido**. La presencia de esos archivos no acredita que todo el resto del plan E3 esté completo.
- Esta copia Git es **shallow**. `git merge-base --is-ancestor` no logra atravesar su frontera para demostrar la ascendencia del head del PR, aunque el objeto del merge lista ese head como segundo padre y GitHub confirma la fusión. No se usa el fallo de ascendencia superficial como prueba de que no fue fusionado.
- `VERSION` contiene `v35.0`; no se encontró etiqueta v36 en el conjunto local. Falta verificar y cerrar E4 y la fase 2, documentar y auditar el resultado y gestionar la publicación. Una etiqueta local ausente no prueba por sí sola que no haya ninguna remota.

## Siguiente paso

Distinguir las obligaciones restantes de E3 de las ya incorporadas: controles multilingües, FP ingleses no resueltos y fusiones de etiquetas pospuestas, sin confundir investigación con correcciones aprobadas. Preparar baseline y diff de cualquier mejora de cimientos; no aplicar cambios de motor sin autorización. La prueba E1 asociativa y W son líneas de medición, no sustituyen esta ruta ni cierran automáticamente estas etapas. Después corresponde E4, modularización gradual y auditoría v36; el examen de v37 viene sobre esa base estable.
