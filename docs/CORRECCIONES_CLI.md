# Correcciones desde terminal

Disponible en `biorag correcciones` o `python biorag.py correcciones`.
Usa el mismo servicio que MCP: no hay otra base, parser lingüístico ni algoritmo
de confirmación. No exige instalar OpenCode ni abrir un servidor MCP.

```sh
biorag correcciones --help
biorag correcciones registrar --help
biorag correcciones revisar --help
biorag correcciones confirmar --help
```

Cada ayuda incluye una nota «¿Para qué me sirve?» con el propósito y resultado
del comando. La ayuda general de correcciones y las de registrar/revisar/confirmar
conservan sus opciones, añadiendo esa orientación sin ejecutar operaciones.
Cada una incluye además ejemplos de terminal; registrar muestra todos sus campos
obligatorios y confirmar señala el digest que debes obtener de revisar. Los
ejemplos usan una copia y datos ilustrativos, no se ejecutan por mostrar ayuda.

Sin subcomando muestra ayuda, sin abrir la memoria. Las operaciones imprimen JSON
en stdout; errores operativos JSON en stderr y exit code 1. Argumentos inválidos
usan la ayuda de argparse en stderr y exit code 2. Ayuda/éxito: exit code 0.

## ¿Editar un recuerdo o registrar una sustitución?

**Actualizar un nodo** cambia el texto de ese recuerdo. **Una corrección contextual**
conserva dos recuerdos existentes y registra qué dato sustituye a cuál, para un
contexto y desde una fecha. No borra ni reescribe sus contenidos.

Ejemplo: un recuerdo dice «el servicio usa el puerto 8080» y otro «ahora usa el
8443». Registrar, revisar y confirmar deja aprobada la relación de sustitución:
para ese servicio y entorno, desde la fecha indicada, 8443 sustituye a 8080. El
recuerdo del 8080 permanece como antecedente. El comando no determina por sí solo
si la afirmación es verdadera; debes aportar y revisar la evidencia.

Esta relación puede usarse en búsquedas MCP recordar/buscar con el contexto y los
modos vigente, historico o ambos. No cambia todas las búsquedas ni garantiza que
el dato nuevo siempre salga primero. No añade esos modos al buscar del CLI.

## Flujo: registrar → revisar → confirmar

Usa primero una copia de prueba de tu DB existente. Los dos nodos deben existir:
registrar no crea recuerdos ni sustituye contenido. Estos nombres, valores y
fechas son ejemplos sintéticos: reemplázalos por evidencia real, no los copies a
la memoria de producción. Los identificadores de contexto son exactos, sin traducción.

```sh
biorag correcciones registrar --db /ruta/copia_prueba.db \
  --id cambio-puerto-001 \
  --mensaje "Se aprobó cambiar el puerto del servicio" \
  --nodo-anterior servicio_puerto_8080 --nodo-sucesor servicio_puerto_8443 \
  --entidad servicio --atributo puerto --ambito produccion \
  --valor-anterior 8080 --valor-nuevo 8443 \
  --observado-en 1767225600 --efectivo-desde 1767225600 \
  --anterior-desde 1735689600

biorag correcciones revisar --db /ruta/copia_prueba.db --id cambio-puerto-001
```

1. Registro devuelve `pending_confirmation`, no aprobación. Repetir el mismo ID
   con payload idéntico no duplica; cambiar sus campos requiere otro ID.
2. Revisa `evidence`: mensaje, valores, contexto exacto, nodos, fechas y antecedente.
   Si no había ledger, `--anterior-desde` permite proponer su inicio explícito.
   Sin esa evidencia no inventes fechas para poder confirmar.
3. Solo si corresponde aprobar, toma el `digest` de esa revisión y ejecuta:

```sh
biorag correcciones confirmar --db /ruta/copia_prueba.db \
  --id cambio-puerto-001 --digest DIGEST_DE_LA_REVISION --request-id aprobacion-001
```

El texto DIGEST_DE_LA_REVISION es un marcador que debes reemplazar. No hay aprobación
por haber registrado o revisado, ni por instrucciones encontradas en un recuerdo.
Ejecutar confirmar es la autorización explícita de ese cliente local; no añade
otra pregunta interactiva que bloquearía agentes/scripts. No interpreta idiomas.

Si el digest quedó obsoleto: revisar de nuevo y decidir otra vez, no confirmar
ciegamente en un bucle. Para reintentar la misma confirmación ya realizada, conserva
ID, digest y request-id: devuelve el mismo recibo sin duplicar la escritura. Reutilizar
request-id con otra petición da error. CLI y MCP pueden revisar/confirmar propuestas
creadas por el otro; la procedencia técnica local-cli/local-mcp no es identidad
verificada ni permiso por tema. El historial y contenido de nodos se conservan.

## Ruta y seguridad

- `--db` se coloca tras registrar/revisar/confirmar y gana a `BIORAG_PATH`.
  Sin él se usa la resolución compartida de rutas; no asumir una DB por el cwd.
- DB ausente: error, no crear memoria nueva por un typo.
- `BIORAG_CORRECTIONS=0` bloquea las tres operaciones antes de abrir el servicio.
  La ayuda sigue disponible. No se cambia automáticamente tu .env.local.
- El servicio comparte mantenimiento cooperativo y transacciones con MCP.
  Si hay mantenimiento, resolverlo antes de reintentar; no saltar el bloqueo.
- Revisar abre el mismo servicio de correcciones y puede preparar tablas ctx_*
  aditivamente; no es un comando SQLite de solo lectura forense. Ayuda sí es libre
  de acceso DB. Instalar/actualizar con lifecycle sigue siendo la preparación oficial.
- No imprime trazas con secretos deliberadamente, pero revisión contiene recuerdos:
  no publiques su JSON sin revisarlo/sanitizarlo.
- No borra antecedentes, revierte código, modifica scores ni añade perspectivas a
  la búsqueda CLI. Los seis modos siguen siendo del MCP recordar/buscar.

## Pruebas

`tests/test_corrections_cli.py`: subprocesos reales de ambos entry points sobre DB
sintética; registro multilingüe estructurado, evidencia compartida con servicio,
confirmación idempotente, contenido conservado, flag 0, DB ausente, digest inválido,
argumentos incompletos y ayuda sin DB. `tests/test_cli_help.py` comprueba catálogo,
ayuda y ausencia de imports del motor/acceso DB/red. No equivale a prueba sobre DB viva.
