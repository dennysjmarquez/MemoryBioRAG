# Auditoría del seguimiento SQLite `faa0dd3`

## Dictamen

**No recomendar integrar todavía:** se confirmó una regresión de disponibilidad ante una escritura de esquema legítima desde otro proceso, usando el propio `open_writer` del candidato. Se requiere corregir o establecer y probar un protocolo explícito para ese caso antes de adoptar la protección. No se demostró corrupción de datos. La evaluación es acotada y no certifica seguridad integral.

## Validaciones confirmadas

El commit revisado es `faa0dd385f2bee0df8ef6e0154c4401d0cb326de`, descendiente de `57f9e13`; el diff de seguimiento cambia wrappers SQLite, firmas de archivo, pruebas/CI, documentación y renombra seis rutas incompatibles con Windows. `git diff --check 57f9e13 faa0dd3` pasó. La API de GitHub confirma que el run `42610281654` corresponde al commit exacto y concluyó `success` en las suites Ubuntu Python 3.11/3.12 y la matriz focalizada Ubuntu/macOS/Windows. En Windows checkout sí pasó; los pasos específicos de reemplazo in-place con handles retenidos y locks entre procesos quedaron **skipped**, por lo que no están validados allí.

En copia aislada, Python 3.11, dependencias del candidato, snapshot QA versionado y `PYTHONHASHSEED=0`: `pytest tests/ -q` = **800 passed** (200,47 s); el subconjunto de runtime, rutas, generación, daemon, conexiones por hilo y singleton = **46 passed**. Incluye las pruebas sintéticas nuevas de reemplazo in-place en Linux. No se ejecutaron aparte los scripts de scoring y Concept Hub de CI. No se abrió, migró ni reparó ninguna DB original. Esto valida los escenarios ensayados, no toda concurrencia ni todas las modificaciones externas.

## Regresión reproducida: segundo escritor permitido

En una DB temporal nueva en modo DELETE, se abrió `SQLiteMemoryBioRAG` y se conservó un cursor. Un segundo proceso Python abrió la **misma ruta** mediante `core.sqlite_runtime.open_writer`, ejecutó `CREATE TABLE` y un `INSERT` sintéticos y confirmó correctamente (`exit 0`). El proceso principal intentó consultar esa tabla:

| Versión | Escritor secundario | Dos lecturas posteriores del principal |
|---|---|---|
| `57f9e13` | commit exitoso | `1`, `1` |
| `faa0dd3` | commit exitoso | `SQLiteDatabaseIdentityChangedError`, repetido |

El candidato correlaciona `note_database_commit` en memoria por proceso; ese contador no se comparte con un escritor de otro proceso. `_check_in_place_change` además no reconoce como commit verificable el cambio si cambió la cookie de esquema. En la fixture, un `CREATE TABLE` real y confirmado fue tratado como posible sustitución in-place y las lecturas posteriores quedaron bloqueadas en la instancia. Es razonable fallar cerrado ante ambigüedad, pero este escenario muestra un **cambio funcional real** frente al baseline, incluso entre procesos que usan la fábrica del proyecto. No prueba que alguna rutina concreta de producción lo active; hay que comprobar los ciclos reales (inicialización, migración, ADN, MCP, dashboard y daemons) en copias, y definir una coordinación que no acepte reemplazos inseguros ni bloquee cambios autorizados inadvertidamente. No solventar quitando el guardia sin pruebas ni cambiar la DB original.

## Otros límites relevantes

- Las firmas, `data_version` y proxies mejoran los casos verificados; el candidato reconoce límites con cambios durante transacciones, mutaciones que preserven observables, escritores externos/raw y las pruebas omitidas en Windows. No presentar el verde de CI como cobertura de esos supuestos.
- El runbook WAL→DELETE solo describe un opt-in API y pruebas con fixtures; no se ejecutó una migración de usuario. Se siguen necesitando backup consistente, coordinación de todos los consumidores y autorización expresa para cualquier DB real. El cambio no instala automáticamente un SQLite corregido.
- No se ha medido exhaustivamente el impacto de abrir/leer encabezados y ejecutar `PRAGMA data_version` por acceso ni compatibilidad de todos los consumidores de objetos DB-API proxy.
- La comparación previa 57f se reproduce solo para la sonda indicada, no para una suite completa comparativa en este entorno. Mantener baseline, logs completos y pruebas contra falsos positivos de seguridad y pérdida de disponibilidad.

Evidencia privada sintética: `auditoria_sqlite_faa0dd3.tar.gz`, Drive ID `1gwdWkz30ouFbjjAWoc-SFogyxt-J1VJb`, SHA-256 `b6f77a2548fcfb0a7c2e1fb3ebdfeafa51da914cfd312654a682e4aecc90a4ce`. Incluye logs y sonda A/B de dos procesos; no hay datos reales. No se hizo PR ni merge.
