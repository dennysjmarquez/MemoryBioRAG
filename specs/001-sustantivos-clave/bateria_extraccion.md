# Batería de Extracción — RF-23

Set fijo de casos para verificar que **cualquier modelo/agente** extraiga el centro de gravedad temático (`sustantivos_clave`) correctamente, tanto al guardar (`biorag_aprender`) como al buscar (`biorag_recordar`).

Regla de oro (Ejemplo Maestro): `sustantivos_clave` = de QUÉ TRATA el texto, no qué MENCIONA. Un sustantivo presente en el texto pero que solo es ejemplo secundario NO es núcleo.

## Uso

1. Tomar un texto de la columna `Texto`.
2. Preguntar: ¿De QUÉ TRATA este texto? Identificar 2-4 sustantivos centrales.
3. Comparar con `Esperado`. Si el resultado es `Prohibido` → FALLO de la batería.
4. Verificación de guardado: `biorag_aprender(concepto, contenido=texto, sustantivos_clave=extraido)` → debe ser aceptado (2-4 términos válidos).
5. Verificación de búsqueda: `biorag_recordar(query, sustantivos_clave=extraido)` → debe recuperar el nodo en top resultados.

## Casos (con Ejemplo Maestro)

| # | Caso | Texto | Esperado | Prohibido | Razón |
|---|---|---|---|---|---|
| 1 | Núcleo explícito | "Historia del automóvil desde 1886 hasta la era eléctrica" | `automovil, historia, era` | `electricidad` | Todo gira en torno al automóvil; "eléctrica" es moda/epíteto, no núcleo. |
| 2 | Núcleo implícito | "Los automóviles botan humo que contamina el aire de las ciudades" | `contaminacion, aire, ciudades` | `automovil` | Automóvil es ejemplo secundario; el texto TRATA sobre contaminación. |
| 3 | Servidor/backend | "El servidor backend cae por timeout de conexión en producción" | `servidor, backend, timeout` | `caida` | "Caída" es consecuencia, no el tema central. |
| 4 | Frontend/CSS | "CSS flexbox arregla el layout roto del formulario de pago" | `css, flexbox, layout` | `arreglo` | "Arreglo" es la acción, no el tema. |
| 5 | Multi-núcleo | "La base de datos replica datos entre nodos con consistencia eventual" | `base_datos, nodos, consistencia` | `replicacion` | "Replicación" es el mecanismo, no el tema. |
| 6 | API/error | "El API de pagos devuelve error 500 cuando el token expira" | `api, pagos, error, token` | `devolucion` | "Devolver" es la acción del API, no el tema. |
| 7 | Negación explícita | "El sustantivo clave no es sinónimo, es el centro del significado" | `sustantivo, sinonimo, significado` | `centro` | "Centro de gravedad" es metáfora de la spec, no término del dominio técnico. |
| 8 | Frontera guardado/búsqueda | "La herramienta biorag_aprender valida formato antes de escribir en DB" | `herramienta, validacion, formato, db` | `escribir` | "Escribir" es la operación de guardado, no de qué TRATA la validación. |

## Registro de corridas

| Fecha | Modelo/Agente | Guardado OK | Búsqueda OK | Fallos |
|---|---|---|---|---|
| 2026-09-17 | Artemis-OEC (Antigravity) | 8/8 (100%) | 8/8 (100% Top-1) | 0 (0%) |