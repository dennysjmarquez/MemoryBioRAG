# Convergencia de evidencia para el ranking de BioRAG

## Objetivo y estado

El caso de aceptación es la búsqueda que, después de la transformación del modelo,
se ejecutó como `biorag version actual ultima` con cuatro paráfrasis. El candidato
`reindex_selectivo_dirty` quedó arriba de `version_actual_biorag` porque una mención
incidental en el cuerpo podía competir con la evidencia estructurada del recuerdo
que sí respondía la pregunta.

La hipótesis evaluada es que evidencia pertinente distribuida entre `concepto`,
`sinonimos`, `sustantivos_clave` y `contenido` es más fiable que una mención aislada.
No se codifica ningún ID ni categoría como excepción. La implementación es una
alternativa experimental a Spec 006/007, no una afirmación de que el caso histórico
quedó validado contra la DB original: esa inversión no se reproduce en la copia de
DB disponible en este checkout.

## Señal

`core/memory/evidence_convergence.py` calcula cobertura [0, 1] por campo. Compara
la consulta normalizada y cada paráfrasis por separado; toma la mejor coincidencia
de cada canal, para no diluir una paráfrasis al unir todos sus tokens. Usa igualdad,
stemming y similitud difusa (umbral 0.75). Repetir un token dentro del mismo campo
no aumenta su cobertura.

La cobertura se pondera con los pesos de campos ya usados por BM25:

| Campo | Peso |
|---|---:|
| `concepto` | 5 |
| `sinonimos` | 2 |
| `sustantivos_clave` | 4 |
| `contenido` | 1 |

El bono combina cobertura ponderada y distribución entre campos. Es positivo,
acotado por defecto a 0.06 (máximo configurable 0.12), y se reduce en consultas de
uno o dos tokens. Los campos vacíos no restan puntos. El peso pequeño de `contenido`
permite una coincidencia real en ese campo, pero una mención corporal aislada no
recibe el mismo apoyo que evidencia repartida en campos más específicos.

No se presupone que “4/4 siempre gana”: la señal ayuda a desempatar según fuerza,
cobertura y distribución; el score híbrido original sigue participando. Una frase
completa y exacta en el contenido puede ser evidencia valiosa por sí misma.

## Ubicación y protección del pipeline

- Primero se completa el ranking base y se fija la página con el top-k visible.
- Si el llamador sobreconsulta (MCP usa un pool interno 3x), el bono solo reordena
  el prefijo top-k público. El overfetch no incorpora candidatos nuevos al top-k ni
  cambia el conjunto de semillas que alimenta la expansión sináptica.
- Se conserva la puntuación base en mapas internos. MCP usa esa base para abstención,
  calibración y gates de ráfaga; el score ajustado se informa por separado como
  `score_hibrido` y se adjuntan `score_hibrido_base` y
  `bonus_convergencia_multicampo` para trazabilidad.
- El delta posterior de activación profunda o expansión por grafo se mantiene
  separado del bono. El cambio no toca el esquema ni entrena/escribe la DB canónica.

Spec 006 se deja como NO-GO tal como está: su multiplicador puede atenuar candidatos
que entraron por señales no léxicas y degradar recuperación válida. Spec 007 evita
esa penalización con un bono aditivo, pero su conteo binario igualitario no distingue
la fuerza de los matches, y su contrato de `r[4]` intacto debe contrastarse con los
consumidores que vuelven a ordenar por score. Por eso la implementación presente
usa cobertura gradual, limita el reordenamiento al top-k público y mantiene canales
paralelos de score; no es una copia literal de Spec 007.

## Flags

- `BIORAG_CONVERGENCIA_ACTIVA=0|1`: flag público compatible con las Specs 006/007.
  Tiene precedencia sobre el alias `BIORAG_CONVERGENCIA_EVIDENCIA`.
- `BIORAG_CONVERGENCIA_BONUS_MAX`: máximo del bono, limitado en esta implementación
a `[0, 0.12]`; el alias anterior es `BIORAG_CONVERGENCIA_EVIDENCIA_MAX_BONUS`.
- El valor por defecto del máximo es 0.06. El flag permite A/B sin editar el código.

## Verificación local segura

El smoke A/B clona la DB con `sqlite3.backup()` en una carpeta temporal para cada
variante, abre la fuente en solo lectura, imprime el top-5, las posiciones de ambos
conceptos, la cobertura directa de los cuatro campos y comprueba que el hash de la
fuente no cambie. `evaluar_qa.py` también clona desde una conexión de solo lectura;
las mutaciones de profundidad ocurren únicamente en la copia temporal:

```bash
PATH="$PWD/.venv/bin:$PATH" \
  python scripts/smoke_convergencia_multicampo.py \
  --db MemoryBioRAG_Data/memory_biorag.db --strict
```

Si `reindex_selectivo_dirty` aparece como `null` en `pos_incidental_off`, la DB usada
no reproduce el caso original; que el objetivo salga primero en esa DB no demuestra
que se haya corregido la inversión histórica. El smoke informa ambas cosas.

Para el gate global de 921 casos, ejecutar OFF y ON contra **el mismo snapshot
congelado**; las salidas se dirigen a `/tmp` para no pisar artefactos del repo:

```bash
PATH="$PWD/.venv/bin:$PATH" \
BIORAG_PATH="$PWD/snapshots/qa_escape_qcr_20260811.db" \
BIORAG_CONVERGENCIA_ACTIVA=0 \
BIORAG_QA_METRICS=/tmp/biorag-qa-off.json \
BIORAG_QA_FAILED_CASES=/tmp/biorag-qa-off-fallos.jsonl \
python scripts/evaluar_qa.py

PATH="$PWD/.venv/bin:$PATH" \
BIORAG_PATH="$PWD/snapshots/qa_escape_qcr_20260811.db" \
BIORAG_CONVERGENCIA_ACTIVA=1 \
BIORAG_QA_METRICS=/tmp/biorag-qa-on.json \
BIORAG_QA_FAILED_CASES=/tmp/biorag-qa-on-fallos.jsonl \
python scripts/evaluar_qa.py
```

El smoke de la DB local y el benchmark congelado son comprobaciones distintas: el
segundo mide regresión general; solo la DB que contiene el estado histórico del
problema puede confirmar el cambio de orden reportado.
