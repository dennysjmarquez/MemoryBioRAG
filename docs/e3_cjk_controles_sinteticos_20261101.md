# E3 — controles CJK sintéticos extendidos (arnés corregido tras auditoría, 2 nov 2026)

**Estado:** evidencia diagnóstica; E3 sigue abierto. Los parches continúan NO APLICAR. No avanzar a E4 ni entrenar.

## Auditoría atendida

Leí `docs/auditoria_controles_cjk_operador_2438aba_20261102.md`, commit `a40b7e9760de37ebebeca0bdf262793a2b133fa8`. Corrí el arnés corregido sobre el checkout del commit `2438aba890b70e775edc3fb685c5bf5cd684b60b`; el código del arnés probado se identifica además por SHA-256 en `fuente_sintetica_metadata.json` y en el manifiesto privado.

Correcciones implementadas:

1. Cada repetición crea dos copias SQLite limpias desde el mismo hash: una para la búsqueda primaria y otra para repetir la búsqueda primaria y llamar directamente a `expandir_contexto_vecinos`. Se comparan resultados/scores de ambas búsquedas, los primarios devueltos por la expansión explícita y sus vecinos; se registran discrepancias en vez de clasificarlas automáticamente como contexto.
2. Las comparaciones por caso (`baseline_top5_missing`, `baseline_context_missing`, `top1_changed` y diferencias de score) se escriben de vuelta a los JSON de OR y umbral 2.
3. Los tres resultados, vecinos, sondeos FTS, errores, tiempos y picos de `tracemalloc` se conservan por repetición. Los JSON señalan estabilidad de primarios/vecinos/sondeo entre repeticiones; informan medianas y máximos de asignaciones observadas, no llaman “máximo” a una mediana.
4. El reloj fijo cubre la creación de la fixture, los tres recuerdos añadidos y las dos asociaciones manuales.
5. Los dos textos japoneses se preservan en Drive privado con hashes UTF-8 y receta de derivación inequívoca. El script permite leer el JSON local de Drive mediante `--japanese-inputs`; no escribe los textos en el repo ni en sus JSON de resultados.

Para comprobar los errores antes ocultados por el parche, los árboles experimentales temporales instrumentan únicamente el `except sqlite3.OperationalError` añadido por el patch para registrar el error antes de conservar el comportamiento de recuperación. No se alteraron los parches almacenados ni el motor del checkout. El sondeo FTS independiente también informa sus propios errores.

## Fuente pareada y conteos

La fuente parte de la fixture E3A sintética completa: 120 recuerdos y 1 fila sináptica antes de añadir datos. Después se añadieron tres recuerdos y dos pares manuales bidireccionales. El JSON de metadatos verifica el estado final: **123 recuerdos activos, 5 filas sinápticas, 4 filas manuales**, `integrity_check=ok`. El hash SQLite se mantuvo idéntico en las tres condiciones y durante las búsquedas. Cada consulta y repetición se ejecutó en copias nuevas; el corpus NLTK fue el único enlace de solo lectura. No se usó una base original.

## Resultados observados

- En el control japonés A, la sonda FTS encontró dos recuerdos sintéticos; con cada contenido el único trigrama compartido fue **`を指す`**. OR produjo dos resultados primarios (scores 0,0705 y 0,0433); baseline y umbral 2 no devolvieron primarios. El control japonés B no produjo candidatos ni primarios en ninguno de los tres brazos. Es una observación de esta fixture; **`を指す` no se convierte en filtro**.
- Los primarios y sus scores fueron idénticos entre las tres repeticiones en todos los casos y brazos. Las búsquedas primarias sobre las dos copias independientes coincidieron en todos los casos. La lista de vecinos explícitos también fue idéntica entre repeticiones.
- Hallazgo importante de la expansión explícita: solo en OR/control japonés A, los primarios conservaron nombres y orden, pero sus scores cambiaron de **0,0705/0,0433 a 0,0894/0,0646** al llamar a la expansión; esa expansión no devolvió vecinos. La discrepancia apareció en las tres repeticiones. Por eso el arnés preserva primarios antes y después de expandir y marca este cambio, en vez de atribuirlo a un vecino añadido. No se propone filtrar ni borrar la asociación.
- En mezcla de alfabetos, OR recuperó el recuerdo sintético `灯台警告記録` para Latin sin espacio, el conector inglés `and`, puntuación, partícula `の` y Han suplementario U+20000; el asociado `霧夜観測手掛かり` se registró como vecino explícito. Umbral 2 reprodujo las recuperaciones de Latin, puntuación y Han suplementario, pero no la partícula `の`. Hangul mixto no produjo primarios. Baseline no produjo primarios en esos controles. Son resultados sintéticos de esta segmentación, no evidencia general de soporte ni base para filtrar.
- La pista alineada conservó el primario y el vecino explícito en los tres brazos. La paráfrasis libre produjo primario y vecino con OR y umbral 2; baseline no produjo resultados.
- **No se registraron errores** ni en el FTS crudo ni en el punto `OperationalError` del parche instrumentado, en ninguna repetición de los tres brazos. Los JSON guardan el detalle por brazo/caso/repetición, no solo este total.

## Ranking, comparación y coste local

Los JSON de OR y umbral 2 ahora contienen las comparaciones por caso frente al baseline. En el resumen agregado, casos con resultados primarios inestables entre repeticiones: **0** en los tres brazos; casos con discrepancia entre primarios de copias independientes: **0** en los tres; discrepancias de scores de primarios tras expansión explícita: **0 baseline, 1 OR (control japonés A), 0 umbral 2**; casos con errores CJK instrumentados: **0** en los tres.

Mediana de búsqueda primaria sobre 15 casos, tres repeticiones:

| Brazo | Mediana (ms) |
|---|---:|
| Baseline | 143,796 |
| OR | 150,312 |
| Umbral 2 | 149,875 |

En OR, las consultas de 68, 132, 260, 504 y 1004 caracteres generaron 66, 130, 258, 502 y 1002 trigramas; las expresiones OR ocuparon 986, 1.946, 3.866, 7.526 y 15.026 bytes. Las medianas de búsqueda fueron 147,1; 158,0; 195,3; 252,8 y 367,5 ms. La mediana de los tres picos por `tracemalloc` fue 437,2; 464,2; 505,4; 609,1 y 772,7 KiB; los máximos observados entre las tres repeticiones fueron 441,0; 469,7; 515,6; 629,8 y 813,0 KiB. No hubo error FTS en esos sondeos. Las consultas de 504 y 1004 caracteres superan el límite MCP de 500; la de 1004 es una sonda directa del motor. Estas cifras son locales a una fixture pequeña, con `tracemalloc` activo; no son SLO, p95 ni estimaciones de toda la memoria nativa de SQLite.

## Alcance y decisión

La corrección mejora la trazabilidad de repetibilidad, contexto, scores, errores FTS y diferencias entre brazos; no vuelve esta fixture una evaluación de producción. No se evaluaron escala real, p95, agente independiente ni generalización. Mantener ambos parches NO APLICAR; no modificar `core/memory/search.py`, no usar bases originales, no entrenar. **E3 sigue abierto; no avanzar a E4.**

## Artefactos y datos privados

- Script sanitizado: `scripts/evaluar_controles_extendidos_cjk_e3.py`.
- Los dos parches diagnósticos permanecen en `docs/e3_cjk_trigram_propuesta_NO_APLICAR_20261101.patch` y `docs/e3_cjk_trigram_umbral2_DIAGNOSTICO_NO_APLICAR_20261101.patch`; solo se aplican en árboles temporales.
- JSON completos de salida y manifiesto SHA-256: carpeta privada de Drive **“E3 CJK correcciones post-auditoría 2026-11-02”**; contiene los dos insumos japoneses exactos y su receta/hash. No se incluye SQLite, texto de consulta ni crosswalk en el commit.
- Hash SHA-256 del motor sin modificar: `7193ee7f9e4fdcc52787d8dc107d7456cbaedecac687e084d4e15f450a4ba8e6`.
