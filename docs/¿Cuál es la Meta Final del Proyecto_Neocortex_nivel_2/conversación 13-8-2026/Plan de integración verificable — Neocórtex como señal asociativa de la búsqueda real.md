# Plan de integración verificable — Neocórtex como señal asociativa de la búsqueda real

**Destinatario:** agente local que mantiene el repositorio.  
**Objetivo:** instalar los archivos hoy guardados en `docs/¿Cuál es la Meta Final del Proyecto_Neocortex_nivel_2/`, integrarlos sin reemplazos ciegos y convertir el ADN Conceptual en una señal adicional de recuperación y asociación para la ruta de búsqueda que ya utiliza el sistema.

---

## 0. Decisión de producto que debe gobernar toda la implementación

> **El sistema no debe responder con silencio cuando exista memoria relacionada.** Debe distinguir entre evidencia directa y asociaciones tentativas, no convertir una falta de certeza en un `return []`.

La política aprobada es la alternativa **A**: degradación asociativa etiquetada. El motor puede tener baja confianza, pero la respuesta debe incluir lo mejor disponible dentro de la memoria, explicado y marcado de manera inequívoca.

| Situación | Resultado correcto | Resultado prohibido |
|---|---|---|
| Hay coincidencia directa sólida | Resultado principal con `estado_epistemico: "directo"`. | Ocultar evidencia disponible. |
| Hay relación semántica/ADN, pero no evidencia directa | Resultados de asociación con `estado_epistemico: "asociativo_baja_confianza"`, afinidad y explicación. | Presentar la asociación como hecho confirmado. |
| Ningún mecanismo encuentra un ancla local | Respuesta estructurada: `sin_evidencia_local`, con explicación y sugerencia para guardar/consultar nueva memoria. | Lista vacía sin metadatos, excepción, o inventar una respuesta. |

### Caso guía: la pregunta de la cebra

Para una pregunta como «¿alguna vez me monté en una cebra?», la memoria **no puede afirmar “no”** salvo que tenga un recuerdo explícito que lo contradiga. Una ausencia de registro no es prueba de ausencia. La respuesta correcta es:

```json
{
  "estado_epistemico": "sin_evidencia_directa",
  "confianza_epistemica": 0.18,
  "respuesta": "No encuentro un recuerdo directo que confirme esa experiencia.",
  "asociaciones": ["cebra", "zoológico", "animal", "equitación"],
  "nota": "Estas asociaciones describen memoria relacionada; no prueban que el evento haya ocurrido o no."
}
```

El equivalente interno de esto **no** es `return []`.

---

## 1. Regla de instalación: primero inventario, luego copia, después parches

Los archivos de `docs/¿Cuál es la Meta Final del Proyecto_Neocortex_nivel_2/` deben tratarse como **artefactos fuente pendientes de integración**, no como archivos que se copian todos indiscriminadamente sobre el repositorio.

### 1.1 Inventario obligatorio

Antes de modificar código, el agente local debe generar un manifiesto con ruta, SHA-256 y destino esperado:

```bash
cd <RAIZ_DEL_REPO>
find 'docs/¿Cuál es la Meta Final del Proyecto_Neocortex_nivel_2' -type f -print0 \
  | sort -z | xargs -0 sha256sum > /tmp/neocortex_origen.sha256
```

Debe comprobar que no hay diferencias de nombres o versiones entre los archivos de `docs/` y la tabla siguiente. Si hay archivos con el mismo nombre pero contenido distinto, debe detenerse y abrir una decisión de merge; no reemplazar automáticamente.

### 1.2 Mapa de destinos

| Fuente bajo `docs/...` | Destino operativo | Acción permitida |
|---|---|---|
| `adn_conceptual.py` | `core/adn_conceptual.py` | Instalar como módulo nuevo; revisar importaciones y pruebas. |
| `neocortex_teleologico.py` | `core/neocortex_teleologico.py` | Instalar como módulo nuevo; reemplazar el gate vacío por política asociativa antes de conectar. |
| `hipotesis_teleologica.py` | `core/hipotesis_teleologica.py` | Instalar después de adaptar a cromosomas dinámicos; no debe importar catálogos fijos eliminados. |
| Cambios de `memory_store.py` | `core/memory_store.py` | Aplicar como parche por funciones; no copiar el archivo completo. |
| Cambios de `dmn_engine.py` | `core/dmn_engine.py` | Aplicar como parche dentro del ciclo de sueño; no reescribir el DMN. |
| Cambios de `auto_clustering.py` | `core/auto_clustering.py` | Aplicar el parche mínimo y comprobar dependencias/importaciones. |
| `reentrenar_ppmi.py` | `scripts/reentrenar_ppmi.py` | Parche de inicialización para snapshots sin `tokens` o `nodos`. |
| `reconstruir_indice_adn_v29.py` | `scripts/reconstruir_indice_adn_v29.py` | Instalar como comando de reconstrucción controlada. |
| `validar_indice_adn_v29.py` | `scripts/validar_indice_adn_v29.py` | Instalar como prueba de no-recorrido global en caliente. |
| `diagnosticar_redes_neuronales.py` | `scripts/diagnosticar_redes_neuronales.py` | Instalar como diagnóstico; no como parte del servicio. |
| `benchmark_921_*.json` y comparador | `artifacts/benchmarks/` o `scripts/` | Conservar como evidencia; no usar como lógica de producción. |

**No mover informes Markdown ni presentaciones al directorio `core/`.** Son documentación, no dependencias de ejecución.

---

## 2. Arquitectura destino: sumar señales, no sustituir la búsqueda existente

La búsqueda actual ya combina memoria, PPMI/SVD, FTS, sinapsis, Ráfaga y demás capas. El ADN Conceptual debe añadirse como **señal complementaria**, no sustituir esas señales ni crear una segunda ruta inconexa.

### 2.1 Flujo único de búsqueda

Todas las entradas —búsqueda por palabra, búsqueda de frase, Ráfaga, búsqueda total y herramientas MCP— deben converger en un punto de integración común situado dentro o inmediatamente después de `SQLiteMemoryBioRAG.buscar_por_frase()`.

```text
consulta
  -> normalización y recuperación existente
      (FTS / PPMI / sinapsis / Ráfaga / filtros actuales)
  -> candidatos base y sus puntuaciones
  -> evaluación epistémica C_e
  -> expansión ADN con índice nocturno precalculado
  -> fusión de señales + etiquetado de certeza
  -> respuesta uniforme para CLI, API, MCP y UI
```

No añadir llamadas independientes a `buscar_por_esencia()` a cada handler MCP. El MCP debe recibir el resultado enriquecido porque llama a la misma API central. El agente debe localizar los handlers MCP que llamen directamente a un motor alternativo y redirigirlos al adaptador común, sin cambiar sus contratos públicos sin pruebas.

### 2.2 Índices que se generan solo durante sueño

`ADNConceptualEngine.reconstruir_indice_nocturno()` es el único lugar autorizado para:

1. detectar comunidades mediante `detectar_comunidades()`;
2. calcular centroides de cromosomas desde vectores PPMI/SVD reales;
3. construir firmas ADN de nodos;
4. precalcular `adn_vecinos_v29`;
5. precalcular `neocortex_token_candidatos_v29`.

El ciclo DMN debe reconstruirlos **después** de una reindexación PPMI/SVD o cuando haya memoria consolidada pendiente. Se debe persistir una revisión de índice, hash de snapshot, fecha y cantidad de nodos. Si la revisión no coincide con PPMI, el índice debe considerarse obsoleto y reconstruirse en el próximo sueño, nunca recalcualarse desde una consulta.

### 2.3 Prohibición de recorridos globales en caliente

En producción, estas funciones no pueden hacer `for ... in self.indices.vecs.items()` ni construir una matriz con todo el corpus por cada consulta:

| Función | Fuente de candidatos permitida |
|---|---|
| `evaluar_episteme()` | `neocortex_token_candidatos_v29` y pool acotado por token. |
| `razonar_por_significado()` | Pool persistido token→concepto, luego expansión sináptica acotada. |
| `buscar_por_esencia()` | `adn_vecinos_v29` si el nodo existe; para consulta nueva, membresías de sus cromosomas dominantes. |
| Búsqueda principal | Candidatos de la recuperación actual más candidatos ADN acotados. |

Instrumentar en pruebas un contador `n_candidatos_adn_consultados`. Para el snapshot de 487 nodos, el contador debe ser menor que 487. En una base grande, deberá respetar los límites configurados (`TOP_CANDIDATOS_TOKEN`, `TOP_VECINOS` y máximo de expansión).

---

## 3. Reemplazo obligatorio del `return []` de baja confianza

El siguiente patrón debe eliminarse de la ruta que construye una respuesta para un usuario o un agente:

```python
if confianza < 0.2 or not pool_candidatos:
    return []
```

Se debe sustituir por un adaptador de salida, por ejemplo `resolver_asociaciones_degradadas()`. No es necesario usar este nombre exacto; sí se deben preservar sus reglas.

### 3.1 Algoritmo de degradación asociativa

1. Ejecutar recuperación actual y guardar los `k` resultados base, aunque sean débiles.
2. Si hay candidatos token→nodo, expandir con `adn_vecinos_v29` de los mejores anclajes.
3. Si no hay candidatos token→nodo, usar los mejores resultados de la recuperación existente como **anclajes**, nunca un barrido total del corpus.
4. Fusionar candidatos, eliminar duplicados y limitar a `k` resultados principales más `m` asociaciones.
5. Marcar todo resultado no directo con `tipo_relacion: "asociacion"`; nunca usarlo como respuesta factual no cualificada.
6. Si ni la recuperación existente ni ADN encuentra un ancla, devolver un objeto con `sin_evidencia_local` y explicación; la lista interna puede estar vacía, pero la respuesta pública no puede ser silenciosa ni ambigua.

### 3.2 Contrato mínimo de resultado

Sin romper los campos que consumidores actuales ya esperan, añadir metadatos opcionales:

```json
{
  "concepto": "...",
  "score_final": 0.42,
  "score_base": 0.37,
  "score_adn": 0.62,
  "confianza_epistemica": 0.18,
  "estado_epistemico": "asociativo_baja_confianza",
  "tipo_relacion": "asociacion",
  "genes_compartidos": ["auto_..."],
  "explicacion": "Relacionado por memoria vectorial y vecindad conceptual precalculada; no es evidencia directa."
}
```

Los resultados directos conservan `tipo_relacion: "evidencia_directa"`. El consumidor MCP o UI debe mostrar primero evidencia directa y después el bloque **«Asociaciones relacionadas, confianza baja»**.

---

## 4. Fusión de ranking: propuesta conservadora y medible

No sumar cosenos sin normalización. Cada señal se debe escalar a `[0, 1]` dentro del pool de candidatos antes de combinarla.

### 4.1 Señales

| Símbolo | Fuente | Papel |
|---|---|---|
| `S_base` | Puntuación ya calculada por `buscar_por_frase()` | Señal principal y estable. |
| `S_adn` | Afinidad de `adn_vecinos_v29` o firma ADN | Señal complementaria de asociación. |
| `S_epi` | Confianza epistémica `C_e` | Calibración y etiqueta, no interruptor de silencio. |
| `S_directa` | Evidencia lexical/FTS/identidad de concepto | Protección contra que una asociación supere una coincidencia directa. |

### 4.2 Primera configuración segura

Usar una bandera de función desactivada por defecto:

```text
BIORAG_ADN_RANKING_ENABLED=false
BIORAG_ADN_PESO=0.15
BIORAG_ADN_MAX_EXPANSION=24
BIORAG_ADN_UMBRAL_ASOCIACION=0.35
```

Con la bandera activa, calcular:

```text
S_final_directo = 0.85 * S_base + 0.15 * S_adn
S_final_asociativo = min(0.49, 0.70 * S_base + 0.30 * S_adn)
```

La cota `0.49` es deliberada: una asociación de baja confianza no debe adelantar a una coincidencia directa que el motor considera fiable. `C_e` regula visibilidad y presentación:

```text
C_e >= 0.60       -> directo / confianza alta
0.20 <= C_e < .60 -> relacionado / confianza media
C_e < 0.20        -> asociativo / confianza baja, nunca vacío
```

El agente puede ajustar estos valores **solo después de ablación**, no por intuición.

### 4.3 Integración concreta en código

1. En `memory_store.py`, identificar el último punto donde la lista de resultados ya tiene su score híbrido actual.
2. Crear una función privada, por ejemplo `_enriquecer_con_adn(query, resultados_base, limite)`, que no consulte el corpus completo.
3. Esta función usa una instancia de `ADNConceptualEngine` ya cargada desde la base persistida y el `NeocortexTeleologico` para metadatos, no para devolver vacío.
4. Enriquecer los candidatos base y, si procede, añadir vecinos ADN de los dos mejores anclajes. Mantener la procedencia por candidato.
5. Ordenar con fórmula versionada y retornar la estructura compatible actual más los campos nuevos.
6. Confirmar que los endpoints MCP, Ráfaga y búsquedas simples terminan llamando al mismo método. Si alguno no lo hace, introducir un adaptador central sin duplicar el ranking.

---

## 5. Viabilidad: pruebas que el agente debe ejecutar antes de declarar éxito

### 5.1 Preparación reproducible

```bash
cd <RAIZ_DEL_REPO>
python3 scripts/generar_snapshot.py
python3 scripts/reentrenar_ppmi.py scripts/snapshot_prf_real.db
python3 scripts/reconstruir_indice_adn_v29.py
```

Registrar en cada JSON: commit SHA, checksum SHA-256 del snapshot, versión de índice ADN, número de nodos y número de cromosomas.

### 5.2 Pruebas funcionales obligatorias

| Prueba | Aserción |
|---|---|
| Coincidencia literal | El concepto esperado sigue en top-1 o top-5 según baseline. |
| Typo conocido | La recuperación actual no empeora frente al baseline. |
| Consulta semántica con asociación | Devuelve resultados y todos indican si son directos o asociativos. |
| Consulta fuera de distribución | No crashea ni devuelve silencio público; retorna `sin_evidencia_local` o asociaciones de baja confianza. |
| Pregunta de experiencia personal no registrada | Declara ausencia de evidencia directa; no responde afirmando o negando el evento. |
| Cebra / zoológico / animal | Expone asociaciones separadas de evidencia. |
| Ráfaga y MCP | Devuelven el mismo esquema de certeza/procedencia que la búsqueda principal. |
| Latencia | Ninguna consulta usa una iteración global de nodos. |

### 5.3 Prueba estructural de rendimiento

Ejecutar `scripts/validar_indice_adn_v29.py` y extenderla para fallar si:

```text
candidatos_precalculados >= nodos_totales
```

También instrumentar un contador de accesos a `indices.vecs` durante la consulta. El acceso por clave está permitido; una iteración sobre todos los valores no lo está.

### 5.4 Benchmark antes/después

La suite `casos_qa_baseline_v1.jsonl` tiene **921 casos**: 881 positivos y 40 negativos. Debe ejecutarse dos veces con el mismo snapshot congelado:

1. `BIORAG_ADN_RANKING_ENABLED=false`;
2. `BIORAG_ADN_RANKING_ENABLED=true`.

Métricas mínimas:

| Métrica | Criterio inicial |
|---|---|
| Recall@5 global | No degradar más de 0.5 puntos porcentuales. |
| Recall@1 global | No degradar más de 0.5 puntos porcentuales. |
| MRR | No degradar más de 0.005. |
| Falsos positivos en 40 negativos | No aumentar sin revisión manual explícita. |
| Tiempo p50/p95 por consulta | Medir y comparar; no aceptar recorridos globales. |
| Cobertura asociativa | Crear un set separado y curado de al menos 50 consultas de asociación; 921 QA mide recuperación, no calidad de asociación. |

El benchmark anterior v26.4 vs v29 fue estable —Recall@5 87.8547%, Recall@1 85.9251%, MRR 0.8675, 0 falsos positivos— precisamente porque ADN todavía no intervenía en el ranking real. Esa igualdad **es control de regresión**, no evidencia de mejora semántica.

### 5.5 Diferencias menores en casos fallidos

Si aparecen diferencias como IDs 0649 y 0746 sin cambio en los agregados, el agente debe guardar para cada consulta:

```json
{
  "id": "...",
  "ranking_base": ["..."],
  "ranking_adn_off": ["..."],
  "ranking_adn_on": ["..."],
  "semilla_aleatoria": 42,
  "version_indice": "..."
}
```

Primero comprobar orden SQL sin `ORDER BY`, timestamps de índice, estado dormido/activo mutado entre casos y cualquier aleatoriedad de propagación. No descartar la diferencia solo porque ambas ejecuciones fallan.

---

## 6. Criterios de aceptación

El trabajo es **viable** si y solo si el agente puede demostrar todos estos puntos:

1. No existen categorías ni ejemplos semánticos fijos en el ADN; los cromosomas provienen del clustering del corpus real.
2. La construcción de centroides, firmas y vecinos se ejecuta en sueño y queda persistida con revisión verificable.
3. Las consultas no recorren todo el corpus para ADN o evaluación epistémica.
4. Una consulta de baja confianza no produce silencio: retorna evidencia directa, asociaciones marcadas o un objeto explícito de falta de evidencia local.
5. `buscar_por_frase()` incorpora ADN bajo feature flag, sin desconectar Ráfaga, FTS, PPMI ni sinapsis.
6. MCP y los otros puntos de entrada consumen el mismo resultado enriquecido o el mismo adaptador central.
7. Los 921 casos se ejecutan antes/después y se entrega JSON con métricas, fallos y metadatos reproducibles.
8. La mejora asociativa se mide en un benchmark específico; no se declara éxito solo porque los 921 casos no empeoran.

## 7. Secuencia de ejecución recomendada para el agente local

1. Crear rama de trabajo y manifestar los archivos de `docs/`.
2. Instalar los módulos nuevos y aplicar los parches mínimos.
3. Resolver el contrato de degradación asociativa **antes** de cablear ranking.
4. Reconstruir el snapshot, PPMI/SVD y el índice ADN durante sueño controlado.
5. Ejecutar pruebas estructurales y casos dirigidos.
6. Ejecutar benchmark ADN apagado y guardar JSON.
7. Activar feature flag con peso 0.15, repetir benchmark y guardar JSON.
8. Revisar regresiones, falsos positivos, las diferencias por caso y p95.
9. Solo entonces aumentar o reducir el peso ADN, con nueva ejecución completa.
10. Entregar PR con código, manifest, dos JSON, comparación y decisión explícita de habilitar o mantener apagada la bandera.

---

## Resultado esperado

El resultado no es un “buscador que siempre se inventa algo”, ni un “gate que se calla”. Es una memoria con tres niveles de honestidad:

1. **recuerdo directo**, cuando hay evidencia local;
2. **asociación relacionada**, cuando el cerebro encuentra puentes pero no puede afirmar un hecho;
3. **sin evidencia local**, cuando no existe un ancla suficiente.

Eso conserva el comportamiento asociativo que describió el usuario —cebra, zoológico, rayas, equitación y experiencia personal— sin confundir asociaciones con recuerdos confirmados.
