# E3 — controles CJK sintéticos extendidos (corrida corregida, 2 nov 2026)

**Estado:** evidencia diagnóstica; E3 continúa abierto. No aplicar. No avanzar a E4 ni entrenar.

## Alcance y método

Comparación pareada de tres brazos (`baseline`, propuesta CJK OR y umbral 2) en 15 controles sintéticos: mezcla de alfabetos, conectores, control japonés investigado, paráfrasis/pista alineada y cinco longitudes de consulta. La base SQLite se construyó como fixture sintética independiente a partir del arnés E3A, con tres recuerdos y dos asociaciones manuales sintéticas; cada búsqueda usó una copia. Los parches se aplicaron exclusivamente a árboles temporales extraídos con `git archive`. El corpus NLTK se enlazó en modo lectura; no se abrió ni modificó una base original. `integrity_check=ok` y el hash de la fuente sintética permaneció igual tras las corridas.

Cada caso tuvo tres repeticiones. La búsqueda primaria se ejecutó con ventana contextual cero; en un segundo llamado se midió la expansión de contexto por separado. Así se evita contar vecinos como resultados primarios o alterar artificialmente el top-k. Los puntajes de vecinos se reportan aparte y no se interpretan como reordenamiento de resultados primarios.

La corrida corregida se ejecutó el 2 nov 2026 sobre HEAD `41e1793abb9e346f01e619c17611dc158ff27f4a`. El JSON completo de la primera corrida ya no estaba disponible en `/tmp`; los valores y artefactos detallados que se conservan son de esta nueva corrida corregida, no una reconstrucción byte a byte de los archivos temporales anteriores.

## Hallazgos

### Observación del control japonés

El sondeo FTS encontró dos candidatos sintéticos y **el único trigrama compartido con cada contenido candidato fue `を指す`**. Con OR aparecieron ambos como resultados primarios (puntajes 0,0417 y 0,0145); baseline y umbral 2 no devolvieron resultados. Al sustituir la frase predicativa final por otra forma común, los tres brazos quedaron sin candidatos ni resultados.

Esto apunta a una coincidencia léxica corta y general como explicación inmediata de las recuperaciones observadas, pero no demuestra que el trigrama o la asociación sean siempre irrelevantes. Se conserva solo como pista diagnóstica: no se convierte en regla de filtrado ni se eliminan pistas o asociaciones.

### Mezcla de alfabetos, conectores y límites de extracción

En esta fixture, OR recuperó el recuerdo sintético `灯台警告記録` en los controles con letras latinas sin espacio, con el conector inglés `and`, con puntuación y con la partícula japonesa `の`; el recuerdo asociado `霧夜観測手掛かり` apareció como contexto expandido. Baseline no recuperó resultados primarios en esos controles. Umbral 2 reprodujo las recuperaciones de latín, puntuación y Han suplementario, pero no el control con `の`. La variante Hangul mixta no produjo resultados en ningún brazo.

El carácter Han suplementario U+20000 quedó fuera de los rangos incluidos por estos parches, aunque el sufijo Han restante pudo generar recuperación. Esto evidencia el comportamiento de compactación/segmentación de esta propuesta concreta, no una recomendación para descartar alfabetos ni para filtrar resultados.

### Pistas, paráfrasis y ranking

La consulta alineada recuperó el mismo recuerdo primario en los tres brazos; el recuerdo asociado se mantuvo en el contexto expandido en los tres. La paráfrasis libre no devolvió primarios con baseline, pero OR y umbral 2 recuperaron el recuerdo de pista como primario y conservaron el asociado como contexto. En este ejemplo, el score del vecino contextual supera al del primario; el motor lo presenta en un campo/posición de contexto aparte. Por ello no debe describirse como inversión del ranking primario.

### Coste local y consultas largas

Mediana de búsqueda primaria sobre los 15 casos (tres repeticiones por caso):

| Brazo | Mediana (ms) |
|---|---:|
| Baseline | 146,245 |
| OR | 146,874 |
| Umbral 2 | 153,306 |

En el brazo OR, los cinco controles largos (68, 132, 260, 504 y 1004 caracteres totales) generaron 66, 130, 258, 502 y 1002 trigramas únicos; las expresiones FTS OR ocuparon 986, 1.946, 3.866, 7.526 y 15.026 bytes. No hubo error FTS, incluido el control de 1004 caracteres. Las medianas de búsqueda primaria fueron 143,3; 153,6; 192,9; 258,3 y 363,1 ms, con máximos de asignaciones Python observados por `tracemalloc` de 437,2; 463,9; 505,4; 609,0 y 773,1 KiB.

Los controles de 504 y 1004 caracteres superan el límite MCP de 500; el de 1004 es solo una sonda directa del motor. Todas estas latencias y asignaciones corresponden a esta máquina y a esta fixture minúscula; no son SLO ni evidencia de rendimiento de producción. El umbral 2 no mostró una ventaja de coste global en esta ejecución.

## Límites y decisión

La evidencia es una fixture pareada, pequeña y artificial. No permite concluir generalización, calidad semántica, impacto con corpus grandes ni conveniencia de activar cualquiera de los parches. Se conservan los controles que muestran diferencias con el umbral 2 y la observación del control japonés permanece como pista diagnóstica, no como motivo para excluir caracteres, asociaciones o pistas.

**Decisión:** mantener los dos parches NO APLICAR; no modificar `core/memory/search.py`; no usar bases originales; no entrenar; E3 sigue abierto y no se inicia E4.

## Artefactos reproducibles y hashes

- Script sanitizado: `scripts/evaluar_controles_extendidos_cjk_e3.py`.
- Parches diagnósticos: `docs/e3_cjk_trigram_propuesta_NO_APLICAR_20261101.patch` y `docs/e3_cjk_trigram_umbral2_DIAGNOSTICO_NO_APLICAR_20261101.patch`; solo se aplican en árboles temporales.
- JSON detallados corregidos: `baseline.json`, `or.json`, `umbral2.json`, `resumen.json` y `fuente_sintetica_metadata.json`. Se conservan en Drive privado junto con un manifiesto SHA-256; no se incluyen en el commit.
- El script obtiene las dos consultas japonesas mediante `BIORAG_E3_JP_QUERY_A` y `BIORAG_E3_JP_QUERY_B`, suministradas localmente y no almacenadas por el script en el repo. Los resultados no contienen el texto de consulta ni el mapeo a las etiquetas originales.
- HEAD evaluado: `41e1793abb9e346f01e619c17611dc158ff27f4a`. SHA-256 del motor sin cambios: `7193ee7f9e4fdcc52787d8dc107d7456cbaedecac687e084d4e15f450a4ba8e6`.
