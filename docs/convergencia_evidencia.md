# Convergencia de evidencia para el ranking de BioRAG

## Objetivo y estado

El caso de aceptación es la búsqueda que, después de la transformación del modelo,
se ejecutó como `biorag version actual ultima` con cuatro paráfrasis. El candidato
`reindex_selectivo_dirty` quedó arriba de `version_actual_biorag` porque una mención
incidental en el cuerpo podía competir con la evidencia estructurada del recuerdo
que sí respondía la pregunta.

La hipótesis evaluada es que evidencia pertinente distribuida entre `concepto`,
`sinonimos`, `sustantivos_clave` y `contenido` es más fiable que una mención aislada.
No se codifica ningún ID ni categoría como excepción. El caso histórico quedó confirmado
en la DB local del usuario (SHA-256
`0e5b063810b79be56b076bba7d33a662e9afc259607e5f80e3049192c5cfdbd5`): el objetivo
pasó de la posición 2 a la 1 frente a una mención incidental. El smoke usó una copia
aislada y la fuente permaneció sin cambios. Esa DB no está versionada en este checkout,
por lo que el hash identifica el artefacto validado sin distribuirlo.

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
acotado por defecto a 0.085 (máximo configurable 0.12), y se reduce en consultas de
uno o dos tokens. En el smoke local, la brecha base era 0.0671: cap 0.06 daba 0.05
de diferencial y no invertía el orden; cap 0.085 produjo bonos `0.0779` para el
objetivo y `0.0071` para la mención incidental, invirtiendo el orden por `0.0037`.
Una corrida de 921 casos con cap 0.09 perdió un caso typo (R@5 99.89%). La suite
integral del usuario con cap efectivo 0.085 reportó R@5 100%, R@1 91.77%, MRR 0.950
(redondeado), 0 falsos positivos y gate OK. Los campos vacíos no restan puntos. El
peso pequeño de `contenido` permite una coincidencia real en ese campo, pero una
mención corporal aislada no recibe el mismo apoyo que evidencia repartida en campos
más específicos.

No se presupone que “4/4 siempre gana”: la señal ayuda a desempatar según fuerza,
cobertura y distribución; el score híbrido original sigue participando. Una frase
completa y exacta en el contenido puede ser evidencia valiosa por sí misma.

La inspiración biológica es limitada: la convergencia de varios campos funciona como
analogía de integración de señales, no como simulación de neuronas, sinapsis corticales
o cognición humana. La evidencia global solo permite afirmar no-regresión y una mejora
pequeña en el benchmark evaluado; no garantiza ganar en toda consulta o dominio.

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

- `BIORAG_CONVERGENCIA_ACTIVA=0|1`: flag público del reranker aditivo; tiene
  precedencia sobre el alias `BIORAG_CONVERGENCIA_EVIDENCIA`.
- El experimento multiplicativo legado de Spec 006 queda aislado bajo
  `BIORAG_CONVERGENCIA_006_ACTIVA=1` (default OFF), para que la bandera pública no
  active dos algoritmos incompatibles a la vez.
- `BIORAG_CONVERGENCIA_BONUS_MAX`: máximo del bono, limitado en esta implementación
a `[0, 0.12]`; el alias anterior es `BIORAG_CONVERGENCIA_EVIDENCIA_MAX_BONUS`.
- El valor por defecto del máximo es 0.085. El flag permite A/B sin editar el código.

## Verificación local segura

El smoke A/B clona la DB con `sqlite3.backup()` en una carpeta temporal para cada
variante, abre la fuente en solo lectura, imprime el top-5, las posiciones de ambos
conceptos, la cobertura de los cuatro campos y comprueba que el hash de la fuente no
cambie. `evaluar_qa.py` también clona desde una conexión de solo lectura; las
mutaciones de profundidad ocurren únicamente en la copia temporal.

```bash
BIORAG_CONVERGENCIA_006_ACTIVA=0 BIORAG_CONVERGENCIA_ACTIVA=1 BIORAG_CONVERGENCIA_BONUS_MAX=0.085 python3 scripts/smoke_convergencia_multicampo.py --db "$PWD/MemoryBioRAG_Data/memory_biorag.db" --strict
```

El smoke confirmó el orden histórico en el artefacto local del usuario (SHA-256
`0e5b063810b79be56b076bba7d33a662e9afc259607e5f80e3049192c5cfdbd5`), que no está
versionado ni distribuido. Una DB distinta puede no reproducir la inversión original.

Para comparar OFF/ON en el gate global de 921 casos, usar el mismo snapshot congelado
y un intérprete que tenga instalados los requisitos (`numpy`, etc.). Las salidas se
dirigen a `/tmp` para no pisar artefactos del repositorio:

```bash
BIORAG_PATH="$PWD/snapshots/qa_escape_qcr_20260811.db" BIORAG_CONVERGENCIA_006_ACTIVA=0 BIORAG_CONVERGENCIA_ACTIVA=0 BIORAG_QA_METRICS=/tmp/biorag-qa-off.json BIORAG_QA_FAILED_CASES=/tmp/biorag-qa-off-fallos.jsonl python3 scripts/evaluar_qa.py

BIORAG_PATH="$PWD/snapshots/qa_escape_qcr_20260811.db" BIORAG_CONVERGENCIA_006_ACTIVA=0 BIORAG_CONVERGENCIA_ACTIVA=1 BIORAG_CONVERGENCIA_BONUS_MAX=0.085 BIORAG_QA_METRICS=/tmp/biorag-qa-on.json BIORAG_QA_FAILED_CASES=/tmp/biorag-qa-on-fallos.jsonl python3 scripts/evaluar_qa.py
```

El smoke de la DB local y el benchmark congelado son comprobaciones distintas: el
segundo mide regresión general; solo la DB con el estado histórico confirma la
inversión reportada. La convergencia no garantiza mejorar todas las consultas y
solo reordena candidatos que ya pasaron al top-k/pool correspondiente.
