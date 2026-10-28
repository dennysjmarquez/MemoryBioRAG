# E3B2 — primer resultado de los 80 intentos

Se hizo una búsqueda previa MCP real por caso, en dos bases temporales inicialmente vacías.
La referencia carga la versión B1; el candidato usa B2. No hay reintentos.
Los puentes son plantillas sintéticas en la lengua respectiva, no revisadas por hablantes.
Un primer rechazo por puentes ocurre antes de validar los sustantivos y no prueba si estos pasarían.
Las respuestas completas, el detalle de los puentes y la persistencia están en los archivos JSON y log de cada brazo.

Leyenda: **guardado** = confirmado por MCP, persistido, 5 puentes y consolidado;
**BRIDGES_INVALIDOS** = primer bloqueo en puentes; **FORMATO_INVALIDO** = primer bloqueo en sustantivos.

## Chino

| Intento | Referencia B1 | Candidato B2 |
|---|---|---|
| zh-01 | BRIDGES_INVALIDOS | BRIDGES_INVALIDOS |
| zh-02 | BRIDGES_INVALIDOS | BRIDGES_INVALIDOS |
| zh-03 | BRIDGES_INVALIDOS | BRIDGES_INVALIDOS |
| zh-04 | BRIDGES_INVALIDOS | BRIDGES_INVALIDOS |
| zh-05 | BRIDGES_INVALIDOS | BRIDGES_INVALIDOS |
| zh-06 | BRIDGES_INVALIDOS | BRIDGES_INVALIDOS |
| zh-07 | BRIDGES_INVALIDOS | BRIDGES_INVALIDOS |
| zh-08 | BRIDGES_INVALIDOS | BRIDGES_INVALIDOS |
| zh-09 | BRIDGES_INVALIDOS | BRIDGES_INVALIDOS |
| zh-10 | BRIDGES_INVALIDOS | BRIDGES_INVALIDOS |
| zh-11 | BRIDGES_INVALIDOS | BRIDGES_INVALIDOS |
| zh-12 | BRIDGES_INVALIDOS | BRIDGES_INVALIDOS |
| zh-13 | BRIDGES_INVALIDOS | BRIDGES_INVALIDOS |
| zh-14 | BRIDGES_INVALIDOS | BRIDGES_INVALIDOS |
| zh-15 | BRIDGES_INVALIDOS | BRIDGES_INVALIDOS |
| zh-16 | BRIDGES_INVALIDOS | BRIDGES_INVALIDOS |
| zh-17 | BRIDGES_INVALIDOS | BRIDGES_INVALIDOS |
| zh-18 | BRIDGES_INVALIDOS | BRIDGES_INVALIDOS |
| zh-19 | BRIDGES_INVALIDOS | BRIDGES_INVALIDOS |
| zh-20 | BRIDGES_INVALIDOS | BRIDGES_INVALIDOS |

## Japonés

| Intento | Referencia B1 | Candidato B2 |
|---|---|---|
| ja-01 | BRIDGES_INVALIDOS | BRIDGES_INVALIDOS |
| ja-02 | BRIDGES_INVALIDOS | BRIDGES_INVALIDOS |
| ja-03 | BRIDGES_INVALIDOS | BRIDGES_INVALIDOS |
| ja-04 | BRIDGES_INVALIDOS | BRIDGES_INVALIDOS |
| ja-05 | BRIDGES_INVALIDOS | BRIDGES_INVALIDOS |
| ja-06 | BRIDGES_INVALIDOS | BRIDGES_INVALIDOS |
| ja-07 | BRIDGES_INVALIDOS | BRIDGES_INVALIDOS |
| ja-08 | BRIDGES_INVALIDOS | BRIDGES_INVALIDOS |
| ja-09 | BRIDGES_INVALIDOS | BRIDGES_INVALIDOS |
| ja-10 | BRIDGES_INVALIDOS | BRIDGES_INVALIDOS |
| ja-11 | BRIDGES_INVALIDOS | BRIDGES_INVALIDOS |
| ja-12 | BRIDGES_INVALIDOS | BRIDGES_INVALIDOS |
| ja-13 | BRIDGES_INVALIDOS | BRIDGES_INVALIDOS |
| ja-14 | BRIDGES_INVALIDOS | BRIDGES_INVALIDOS |
| ja-15 | BRIDGES_INVALIDOS | BRIDGES_INVALIDOS |
| ja-16 | BRIDGES_INVALIDOS | BRIDGES_INVALIDOS |
| ja-17 | BRIDGES_INVALIDOS | BRIDGES_INVALIDOS |
| ja-18 | BRIDGES_INVALIDOS | BRIDGES_INVALIDOS |
| ja-19 | BRIDGES_INVALIDOS | BRIDGES_INVALIDOS |
| ja-20 | BRIDGES_INVALIDOS | BRIDGES_INVALIDOS |

## Coreano

| Intento | Referencia B1 | Candidato B2 |
|---|---|---|
| ko-01 | FORMATO_INVALIDO | Guardado |
| ko-02 | FORMATO_INVALIDO | Guardado |
| ko-03 | FORMATO_INVALIDO | Guardado |
| ko-04 | FORMATO_INVALIDO | Guardado |
| ko-05 | BRIDGES_INVALIDOS | BRIDGES_INVALIDOS |
| ko-06 | FORMATO_INVALIDO | Guardado |
| ko-07 | BRIDGES_INVALIDOS | BRIDGES_INVALIDOS |
| ko-08 | FORMATO_INVALIDO | Guardado |
| ko-09 | FORMATO_INVALIDO | Guardado |
| ko-10 | FORMATO_INVALIDO | Guardado |
| ko-11 | FORMATO_INVALIDO | Guardado |
| ko-12 | FORMATO_INVALIDO | FORMATO_INVALIDO |
| ko-13 | FORMATO_INVALIDO | Guardado |
| ko-14 | FORMATO_INVALIDO | Guardado |
| ko-15 | FORMATO_INVALIDO | Guardado |
| ko-16 | FORMATO_INVALIDO | Guardado |
| ko-17 | FORMATO_INVALIDO | Guardado |
| ko-18 | FORMATO_INVALIDO | Guardado |
| ko-19 | FORMATO_INVALIDO | Guardado |
| ko-20 | BRIDGES_INVALIDOS | BRIDGES_INVALIDOS |

## Ruso

| Intento | Referencia B1 | Candidato B2 |
|---|---|---|
| ru-01 | FORMATO_INVALIDO | Guardado |
| ru-02 | FORMATO_INVALIDO | Guardado |
| ru-03 | FORMATO_INVALIDO | Guardado |
| ru-04 | FORMATO_INVALIDO | Guardado |
| ru-05 | FORMATO_INVALIDO | Guardado |
| ru-06 | FORMATO_INVALIDO | Guardado |
| ru-07 | FORMATO_INVALIDO | Guardado |
| ru-08 | FORMATO_INVALIDO | Guardado |
| ru-09 | FORMATO_INVALIDO | Guardado |
| ru-10 | FORMATO_INVALIDO | Guardado |
| ru-11 | FORMATO_INVALIDO | Guardado |
| ru-12 | FORMATO_INVALIDO | Guardado |
| ru-13 | FORMATO_INVALIDO | Guardado |
| ru-14 | FORMATO_INVALIDO | Guardado |
| ru-15 | FORMATO_INVALIDO | Guardado |
| ru-16 | FORMATO_INVALIDO | Guardado |
| ru-17 | FORMATO_INVALIDO | Guardado |
| ru-18 | FORMATO_INVALIDO | Guardado |
| ru-19 | FORMATO_INVALIDO | Guardado |
| ru-20 | FORMATO_INVALIDO | Guardado |

En `ko-12`, el sustantivo `물` tiene un solo carácter tras NFC; por eso conserva el rechazo de B1.

Ver: [`e3b2_guardado_nativo_20261027.json`](e3b2_guardado_nativo_20261027.json) y
[`e3b2_guardado_referencia_b1_20261027.json`](e3b2_guardado_referencia_b1_20261027.json).
