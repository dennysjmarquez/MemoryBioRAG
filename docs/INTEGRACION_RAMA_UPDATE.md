# Integración del actualizador con el historial remoto de la misma rama

Se integran los padres locales `3ebac2a` y remotos
`1a41428fa7d69e576a1fcf6772af3b527bdda8f8` en
`arena/6459e2d0-memorybiorag`, con base común
`f8c2b166b6f13cd7bbbdffb13135d3d68354b8e0`.
No se cambia de rama, no se reescribe el historial remoto ni se publica Stable.

## Resolución de diferencias

- Se conservan lifecycle, updater, backup, mantenimiento, recovery, esquema contextual
  independiente de flags y MCP estructurado de la revisión local probada.
- Se preservan las mejoras remotas de rutas del daemon/estado/PID/logs, guardas de
  importación fcntl, validación de existencia de nodos en vincular y sus pruebas.
- Instalador combinado: conserva preparación lifecycle, dependencias fijadas,
  rechazo de fallos/cambios locales y protección de skills ajenas; incorpora la
  ruta configurable de backups y migración del estado legacy remotas.
- Se conserva el pipeline remoto de publicación, plantillas, exclusiones y versión
  Stable independiente de DEV. No se ejecuta ninguna publicación. Se conserva su
  protocolo en AGENTS, aclarando que pedir push DEV no autoriza release Stable.
- Defaults vigentes: correcciones locales 1 y contrato temporal 1; explícito 0
  desactiva la conducta correspondiente. El parser legado no vuelve al MCP nuevo.
- Las eliminaciones remotas de archivos DB versionados se conservan; no se abre
  ni modifica memoria viva. El corpus y resultado bruto grandes ya presentes en
  el historial remoto se conservan al integrar, no se generan ni cargan de nuevo.

## Evidencia de la versión combinada

Código y snapshot copiados a `/tmp/biorag-merged-validation`, HOME temporal,
NLTK local, daemon y chequeo de updates desactivados, BLAS con un hilo.

- `pytest tests/ -q`: **987 passed, 18 skipped, 11 subtests passed**, 331.88 s.
  BIORAG_TEMPORAL_PROTOTYPE=0 por compatibilidad de la suite antigua; no es
  certificación global con contrato obligatorio por defecto.
- Correcciones/perspectivas/esquema/backup/mantenimiento/recovery:
  **80 passed, 7 subtests**, contrato temporal explícitamente 1.
- Updater/instalación/dependencias/packaging/rutas/avisador/vincular:
  **64 passed, 2 subtests**.
- `pytest scripts/test_stable_packaging.py -q`: **19 passed, 9 subtests**.
  Primer intento: faltaba wheel en el venv temporal. Se instalaron setuptools y
  wheel solo allí y se repitió; no se cambió el código para ocultar el fallo.
- E2E MCP stdio estructurado real: aprobado sobre DB sintética con mensaje japonés,
  los seis modos y confirmación idempotente.
- Verificación de sintaxis de Python integrado y ausencia de conflictos pendientes.

Las selecciones se solapan: no sumar conteos como pruebas únicas. La QA oficial de
921 aprobada anteriormente no se repitió tras este merge; su evidencia anterior
sigue separada. No se certifica Windows, update completo real Git+pip+datos ni
rollback global atómico. Esta entrega permite prueba local supervisada, no prueba
que cualquier instalación ya esté migrada ni que los servicios estén activados.
