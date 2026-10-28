# B4a — resguardo del diff y medición parcial

**Corte: 2026-10-28 11:24:07 -04.** Este commit guarda solo el diff y este resumen; todavía no incorpora el cambio del motor.

El [diff aplicado y sus pruebas](e3b4a_diff_aplicado_20261028.patch) tiene SHA-256 `bfd480fb5177236c63104bd7a4194cad1e20a42110c6b8015f0c1b7e93b4a198`. Se comprobó en una copia limpia: reproduce exactamente los dos archivos del motor y la prueba nueva.
La base Git incorpora `7c7abb9` (documentación); la referencia de métricas sigue siendo B3 `e58b7c5`. El prefijo se acepta al inicio normal de palabra o después de un carácter Unicode de ancho W/F. No se cambiaron FTS, WordNet, pesos ni umbrales.

## Pruebas ya terminadas

- Suite completa: **721 pruebas pasaron**. Sin pérdidas en multilingüe, puentes, guardados ni búsquedas MCP respecto a B3.
- **Snapshot normal = B3**, también por categoría: R@5 100,00 %, R@1 95,31 %, MRR 0,9718 y FP 0/40.
- Los 30 puentes conservaron rango 1 y scores. FastMCP conservó 69/80 guardados y no hubo pérdidas R@1/R@5 en 414 búsquedas posteriores.

### Multilingüe, B3 → B4a

Aciertos R@5 / R@1 sobre 20 positivos; FP sobre 2 negativos por idioma. Son dos brazos distintos, no comparaciones entre sí.

| Idioma | Directa: R@5 / R@1 / FP | MCP: R@5 / R@1 / FP |
|---|---|---|
| zh | 7/7/0 → 12/12/0 | 7/7/0 → 12/12/0 |
| ja | 7/7/0 → 12/12/0 | 6/6/0 → 8/8/0 |
| ko | 19/18/0 → 19/18/0 | 16/16/0 → 16/16/0 |
| ru | 20/19/0 → 20/19/0 | 20/19/0 → 20/19/0 |
| en | 20/20/2 → 20/20/2 | 20/20/2 → 20/20/2 |
| es | 20/20/0 → 20/20/0 | 20/20/0 → 20/20/0 |

Directa: `activos`, límite 5 y peso ignorado. MCP: límite público 5, pool interno 15 y peso predeterminado. Ambos brazos tienen 132 casos y verificación inversa. Persisten los dos FP ingleses y 14 rechazos MCP «pendiente hueco 1».

De lista vacía a posición 1: directa `zh-06`–`zh-10` y `ja-06`–`ja-10`; MCP `zh-06`–`zh-10`, `ja-07` y `ja-09`.

## QA oficiales al corte

| QA | Estado | Inicio registrado, hora de Venezuela |
|---|---|---|
| Snapshot normal | Terminó: igual a B3 | 10:24:59 |
| Viva normal | En curso | 10:24:59 |
| Snapshot con ruido | En curso | 10:24:59 |
| Viva con ruido | En curso | 10:24:59 |

Las horas son las registradas al crear los procesos; `ps` mostró un `btime` variable, no una diferencia entre lanzador e hijo.

## Integridad y decisión

- `core/memory/search.py`: `f4479e7db7673c264176a48d467ab7c32411ea67a8cb39ad8daf4a4089677286`.
- `core/memory_store.py`: `b7e7219caf0f801ce60a9531dc7dca982fe57142dd20450e85e124a048db5168`.
- `tests/test_prefijo_ancho_b4a.py`: `68f89c4cf8b54a141da95cf373672fe610b52222036f4334caf570aac03c4181`.
- Las huellas coinciden con las registradas al inicio y después de integrar `7c7abb9`.
- El commit real del motor se hará solo si las cuatro QA coinciden con B3. Si hay una baja, se revierte el candidato y se conserva este diff como registro de lo probado y del motivo.
