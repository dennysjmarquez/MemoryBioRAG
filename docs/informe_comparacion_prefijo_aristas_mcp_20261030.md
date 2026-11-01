# Resultado: comparación controlada del prefijo común en nombres MCP

**Fecha:** 2026-10-30

**Estado:** ambos brazos completados; sin errores MCP o de transporte.

**Autorización:** recibida explícitamente de Dennys.

## Diseño y control de variables

Se usaron dos DB temporales nuevas e independientes, con la misma versión de código (`730c8c9`), el mismo transporte MCP stdio, reloj fijo, cuatro recuerdos, contenidos, `sustantivos_clave`, dimensiones, categorías, argumentos de búsqueda, orden y secuencia de 12 llamadas. Antes de cada `aprender` se hizo una llamada MCP real `recordar`; hubo cuatro búsquedas previas por brazo, todas con `total=0`.

- **Sin prefijo:** `reintento_objetivo`, `reintento_idempotencia`, `reintento_backoff`, `color_favorito`.
- **Con prefijo:** los mismos identificadores con `smoke_mcp_` antepuesto.
- Las cuatro llamadas de `recordar` por brazo usaron `deep=False` y `forzar_rafaga=False`; no se envió `rafaga_palabras`.
- Los textos de `recordar` se fijaron sin incluir los nombres, por lo que son idénticos entre brazos.
- `concepto` en cada `aprender` y los endpoints `a`/`b` en `vincular` cambian necesariamente para apuntar a los nombres de su brazo. Son referencias a los mismos cuatro IDs semánticos, no recuerdos diferentes.
- El helper habitual de bridges depende del nombre. Para no introducir una segunda variable, se calculó una sola vez por recuerdo usando el nombre base sin prefijo y se reutilizó el mismo payload exacto en ambos brazos. `contenido`, `sustantivos_clave`, dimensiones, categoría `General`, `syn` omitido y `busqueda_previa=True` permanecieron iguales.
- Solo cambian por aislamiento las rutas `BIORAG_PATH`, `BIORAG_QA_TEMP_ROOT` y el archivo DMN derivado de la ruta DB; cada brazo tiene su propio temporal nuevo.

## Secuencia por brazo

Cuatro pares de llamadas (`recordar` previa, `aprender`), `consolidar`, dos `vincular`, y `recordar` final: 12 llamadas MCP por brazo, 24 en total. Se tomó un snapshot de solo lectura inmediatamente antes y después de cada llamada. El JSON registra dirección, tipo, peso, timestamps, respuesta cruda/parseada, errores y diff dirigido.

| Brazo | Estado final DB | Filas dirigidas al final | Filas nuevas en `consolidar` | Filas nuevas en cada `vincular` | Errores |
|---|---|---:|---:|---:|---:|
| Sin prefijo | integridad `ok` | 9 | 9 | 0, 0 | 0 |
| Con `smoke_mcp_` | integridad `ok` | 12 | 12 | 0, 0 | 0 |

No había aristas antes de `consolidar` en ninguno de los brazos. `recordar` final tampoco añadió ni modificó aristas.

## Filas dirigidas observadas al terminar `consolidar`

### Sin prefijo

| Origen | Destino | Tipo | Peso |
|---|---|---|---:|
| `color_favorito` | `reintento_backoff` | `dmn_synthesized` | 0.30 |
| `color_favorito` | `reintento_idempotencia` | `dmn_synthesized` | 0.30 |
| `color_favorito` | `reintento_objetivo` | `dmn_synthesized` | 0.30 |
| `reintento_backoff` | `reintento_idempotencia` | `co_nombre` | 0.65 |
| `reintento_backoff` | `reintento_objetivo` | `co_nombre` | 0.65 |
| `reintento_idempotencia` | `reintento_backoff` | `co_nombre` | 0.75 |
| `reintento_idempotencia` | `reintento_objetivo` | `co_nombre` | 0.65 |
| `reintento_objetivo` | `reintento_backoff` | `co_nombre` | 0.75 |
| `reintento_objetivo` | `reintento_idempotencia` | `co_nombre` | 0.75 |

### Con prefijo `smoke_mcp_`

| Origen | Destino | Tipo | Peso |
|---|---|---|---:|
| `smoke_mcp_color_favorito` | `smoke_mcp_reintento_backoff` | `co_nombre` | 0.53 |
| `smoke_mcp_color_favorito` | `smoke_mcp_reintento_idempotencia` | `co_nombre` | 0.53 |
| `smoke_mcp_color_favorito` | `smoke_mcp_reintento_objetivo` | `co_nombre` | 0.53 |
| `smoke_mcp_reintento_backoff` | `smoke_mcp_color_favorito` | `co_nombre` | 0.53 |
| `smoke_mcp_reintento_backoff` | `smoke_mcp_reintento_idempotencia` | `co_nombre` | 0.77 |
| `smoke_mcp_reintento_backoff` | `smoke_mcp_reintento_objetivo` | `co_nombre` | 0.77 |
| `smoke_mcp_reintento_idempotencia` | `smoke_mcp_color_favorito` | `co_nombre` | 0.53 |
| `smoke_mcp_reintento_idempotencia` | `smoke_mcp_reintento_backoff` | `co_nombre` | 0.87 |
| `smoke_mcp_reintento_idempotencia` | `smoke_mcp_reintento_objetivo` | `co_nombre` | 0.77 |
| `smoke_mcp_reintento_objetivo` | `smoke_mcp_color_favorito` | `co_nombre` | 0.53 |
| `smoke_mcp_reintento_objetivo` | `smoke_mcp_reintento_backoff` | `co_nombre` | 0.87 |
| `smoke_mcp_reintento_objetivo` | `smoke_mcp_reintento_idempotencia` | `co_nombre` | 0.87 |

## Diferencias entre brazos

Al normalizar los endpoints quitando solamente el prefijo para comparar los mismos IDs:

- **Tres filas dirigidas adicionales solo en el brazo con prefijo:** `reintento_backoff → color_favorito`, `reintento_idempotencia → color_favorito` y `reintento_objetivo → color_favorito`; cada una quedó como `co_nombre`, peso `0.53`.
- No hubo filas dirigidas exclusivas del brazo sin prefijo.
- Las otras nueve direcciones estaban en ambos estados finales, pero el tipo/peso observado difirió: en el brazo sin prefijo, las tres direcciones `color_favorito → reintento_*` quedaron como `dmn_synthesized/0.30`; en el brazo con prefijo, esas mismas parejas quedaron como `co_nombre/0.53`. Las seis direcciones entre los tres recuerdos `reintento_*` quedaron como `co_nombre` en ambos brazos, con pesos `0.65/0.75` sin prefijo y `0.77/0.87` con prefijo según dirección.
- En los dos brazos, las parejas objetivo↔idempotencia y objetivo↔backoff ya existían antes de llamar `vincular`; ambas llamadas devolvieron `status=ok` y no insertaron ni cambiaron filas.

## Límite de inferencia

La diferencia observada está asociada a estos dos brazos controlados, que difieren en el prefijo de los nombres salvo los campos de referencia y rutas de aislamiento documentados. Las filas aparecieron dentro del intervalo de la llamada MCP completa `consolidar`; estos snapshots no identifican qué subfunción interna escribió cada fila, ni prueban un efecto general más allá de esta fixture y configuración. Los tipos y pesos consignados son los que quedaron observados al terminar cada llamada, no una atribución causal interna.

## Evidencia y restricciones

`docs/resultados_comparacion_prefijo_aristas_mcp_20261030.json` contiene los argumentos, respuestas crudas y parseadas, snapshots previos/posteriores completos, diffs, errores (vacíos), rutas temporales y estado final de ambos brazos. Ambas DB temporales pasaron `integrity_check=ok` y se eliminaron tras guardar la evidencia.

No se accedió a bases originales ni snapshots. No se modificó motor ni ranking. No se ejecutó la QA completa ni se evaluaron sus umbrales.
