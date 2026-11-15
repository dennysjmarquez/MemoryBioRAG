# Informe reproducible: guardia final de prefijo y pistas de paráfrasis (E3)

**Fecha de ejecución:** 2026-11-03
**Alcance:** fixture sintética única; siete casos (incluidos controles sin paráfrasis); comparación MCP baseline/instrumentado.
**No se modificó el motor ni se abrió ninguna base de usuario.** No se propone aquí un cambio de política ni del motor.

## Conclusión breve

La revisión histórica identifica dos objetivos relacionados, pero distintos: el filtro anterior `PALABRA_COMPLETA` restringía matches a límites de palabra para evitar falsos positivos de subcadena; el filtro final `PALABRA_PREFIJO`, introducido después, permite además coincidencias morfológicas por prefijo, por ejemplo `react` → `reactive`. La ejecución sintética confirma que el guardia actual elimina los dos candidatos de una palabra con subcadena interna y conserva el prefijo válido. Los controles sin paráfrasis no encuentran el candidato; al añadir `quartz`, FTS sí lo encuentra por la rama de paráfrasis. Para la consulta de una palabra, el filtro luego descarta ese candidato; en el caso multiword, lo conserva y el guardia no se ejecuta.

Esto demuestra el mecanismo en estas fixtures, no su frecuencia ni impacto sobre datos reales. No se consultó ninguna base original.

## Evolución histórica relevante

- **`57e232e44206411d636b827f6639c510d1cc5bed` (2026-06-18):** introduce `PALABRA_COMPLETA` como UDF SQLite basada en un límite de palabra (`re.search(r'\\b' + re.escape(token) + r'\\b', texto.lower())`). El código documenta el falso positivo de FTS5 trigram: `culo` no debe coincidir con `artículos`. Se aplicó como condición adicional de búsqueda literal en contenido, concepto y sinónimos, y en fallbacks/semi-llas pertinentes. La intención era precisión, no aceptar extensiones morfológicas.
- **`d310ae985647874791226d297f2a8490395e2e76` (2026-06-23):** cambia el filtro final de palabra completa a `PALABRA_PREFIJO`, para que una consulta como `react` recupere `reactive` y siga rechazando una aparición interna como `culo` dentro de `artículos`. También incorpora una tabla FTS5 `unicode61` con comodines de prefijo. El cambio del filtro final no equivale a eliminar toda condición `PALABRA_COMPLETA` del motor: siguen existiendo usos en otros caminos/fallbacks.
- **`b373946ca45724498bc2468838728c93756508a2` (2026-07-11):** cambia la preservación del filtro según una lista de orígenes no literales excluidos. Un origen no enumerado se trata como literal; por ello, una rama `paraphrase` no reconocida puede acabar sujeta al token de la consulta original. Es una explicación de una ruta posible, no una afirmación de que todas las paráfrasis se atribuyan así.
- **`2e94312f4b80562f650de01fd5ea51e47e1fbf1a` (2026-09-17):** amplía el criterio para abarcar `sustantivos_clave`.
- **`94c372d645955fac203cd356954006c76821adbb` (2026-10-28):** extiende el límite de palabra con la semántica `PALABRA_INICIO_ANCHO` para caracteres Unicode de ancho W/F; las pruebas asociadas comprueban el predicado Unicode aislado. El commit posterior `c695310` integra identidad Unicode validada.

Estos hitos se pueden inspeccionar con `git show <hash> -- core/memory_store.py tests/test_memory.py` para los commits previos a la extracción, y con `git show <hash> -- core/memory/search.py tests/test_memory.py` para los posteriores. En particular, antes de `d310ae9`, la búsqueda final con token único requería palabra completa; la motivación explícita y el ejemplo `culo`/`artículos` ya estaban documentados en `57e232e`.

## Protocolo de reproducción

Desde la raíz del repositorio, usando Python compatible con las dependencias del proyecto:

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m py_compile scripts/diagnosticar_filtro_prefijo_parafrasis_e3.py
.venv/bin/python scripts/diagnosticar_filtro_prefijo_parafrasis_e3.py \
  --evidence-dir .private_evidence/e3_prefix_guard_paraphrase_YYYYMMDD_runNN
```

`runNN` debe ser un directorio nuevo; el runner se niega a reutilizar un directorio existente y solo acepta una ruta dentro de `.private_evidence/`. La ejecución escribe el JSON íntegro y `SHA256SUMS.json` allí. Esos archivos son evidencia de operador y no se publican en Git; el runner y este informe sí son reproducibles desde el repositorio. La fixture se crea en un temporal y se elimina al terminar.

El runner reutiliza `scripts/diagnosticar_traza_interna_parafrasis_e3.py`, clona una fixture sintética para cada brazo MCP, desactiva QCR para aislar el comportamiento en el caso multiword y empareja llamadas baseline/instrumentadas. No modifica `core/` ni recibe una ruta a una base original. `helium,vector` satisface el parámetro obligatorio `sustantivos_clave` sin coincidir con la fixture.

## Separación instrumental del filtro final

El launcher ahora registra toda sentencia SQL que mencione `PALABRA_INICIO_ANCHO` y asigna un `query_role` a partir de la forma SQL observada. Solo clasifica como `final_single_word_prefix_guard` la forma del SELECT final que valida los candidatos ya reunidos mediante `concepto IN (...)` y consulta concepto, contenido, sinónimos y `sustantivos_clave`. Las demás sentencias se mantienen visibles como `content_match_scoring` u `other_prefix_function_query`; no se interpretan como el filtro final. Se conserva además la ubicación de llamada y un SHA-256 del SQL para auditar la clasificación. La atribución es pasiva; no altera consultas, parámetros ni resultados.

La corrida muestra por separado el SELECT final para los casos de una palabra y una sentencia `content_match_scoring` en la consulta multiword. Esta última no entra en la lista de entradas/salidas del filtro final. Una sentencia no final puede usar la función en una expresión de conteo/puntuación; su mera presencia no prueba que el filtro haya eliminado un candidato.

## Resultado guardado

Corrida de referencia actualizada: `.private_evidence/e3_prefix_guard_paraphrase_20261103_run08/`

- `synthetic_prefix_guard_results.json` — resultados íntegros sintéticos.
- `SHA256SUMS.json` — SHA-256 del JSON: `dc39e0de24bdf033133ff76b7b51ce333e856d29f4d9f3d78c3f9c29748a116e`.
- Siete casos, veintiocho llamadas, cero errores MCP; las parejas baseline/instrumentado fueron equivalentes y las nueve comprobaciones pasaron.
- `articulos_substring_removed_by_guard` comprueba automáticamente y por separado que el candidato de `culo` / `artículos` entra al pool, es descartado por el guardia y no llega a MCP.
- Los dos controles sin paráfrasis (`qzxnovelquery` y `qzxnovelquery sentinel`) no tienen el candidato en el pool ni en MCP. Al agregar la paráfrasis `quartz`, FTS atribuye el candidato a `paraphrase_1` en ambos casos. En la consulta de una palabra el guardia final recibe el candidato y lo elimina; en la consulta multiword el candidato llega a MCP y el guardia final no se ejecuta.
- Los casos de protección también se conservan: `probeanchor` dentro de `xxprobeanchorzz` y `culo` dentro de `artículos` se descartan; `react` conserva el prefijo válido `reactive`.

Los intentos anteriores `run01` y `run02` se preservaron; fallaron antes de escribir resultados íntegros. `run03` fue una corrida válida con una etiqueta de rol imprecisa; `run04` fue la referencia corregida de cinco casos, `run05` añadió la comprobación propia de `culo` / `artículos`, y `run07` agregó controles de paráfrasis. Todos se conservan sin cambios. `run06` falló una aserción porque la consulta control multiword incluía `archive`, presente en el texto sintético; luego se corrigió a `sentinel`. `run08` repite esa matriz con la clasificación instrumental afinada. No se deben interpretar los directorios fallidos como evidencia de resultado.

## Compatibilidad de los dos runners con la etiqueta nueva

`diagnosticar_traza_interna_parafrasis_e3.py` ahora espera `final_single_word_prefix_guard` y nombra su comprobación `target_excluded_by_final_single_word_prefix_guard`, en línea con la clasificación del launcher. Ejecuté tanto ese runner como `diagnosticar_filtro_prefijo_parafrasis_e3.py` después del ajuste:

- `.private_evidence/e3_internal_paraphrase_trace_20261103_run09/`: 24 llamadas MCP, cero errores, `far_query_exclusion_path_confirmed=true` e instrumentación equivalente en todos los pares. Checksum manifestados en `SHA256SUMS.json`: `stdio_cases_full.json` `21286622affaacea7f69e1d139ea0fcc7bf17dd6f470da6ffd83d77573194d19`; `synthetic_manifest.json` `e642cada4b5752304cdb9318646c3baad3b246c8654362ecabc5681c961f06f4`.
- `.private_evidence/e3_prefix_guard_paraphrase_20261103_run10/`: siete casos, 28 llamadas, cero errores y las nueve comprobaciones pasaron. SHA-256 del JSON íntegro: `48cb7fba2633adf238da61bb259f589945cf5e7f663e282342cea2fd6559d0f1`.

Ambas corridas son sintéticas; las trazas y manifiestos completos se conservan en esos directorios privados y no se incluyen en Git.

## Límites de inferencia

- Las consultas y los documentos son sintéticos; no se abrieron ni modificaron bases originales.
- La atribución de rama y la salida MCP observadas aplican a esta fixture y configuración. No miden prevalencia en producción.
- El control multiword confirma que, en esta ruta y con QCR desactivado, el guardia no corre cuando la consulta tiene dos tokens extraídos; no generaliza a otras capas o configuraciones.
- El hallazgo de la historia (`paraphrase` puede ser evaluado como literal si no se reconoce como origen no literal) explica la susceptibilidad; la fixture confirma un caso observable, no que toda ruta de paráfrasis se comporte igual.
- Este informe presenta evidencia y límites; no recomienda cambiar el motor, borrar etiquetas/pistas ni adoptar una política de retención.
