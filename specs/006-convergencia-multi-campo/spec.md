# Spec 006 — Convergencia Multi-Campo (Resonancia Estructural)

## Contexto y objetivo

El motor de scoring actual puede posicionar un nodo incorrecto en el primer lugar cuando
una palabra buscada aparece muchas veces dentro de su campo `contenido`, aunque ese nodo
no trate realmente del tema buscado. Un texto largo con 20 menciones casuales de una
palabra supera en ranking a un nodo cuyo título, sinónimos y sustantivos son exactamente
esa palabra.

El objetivo es corregir esto: la relevancia real de un nodo se mide por en cuántos campos
estructurales independientes resuena la búsqueda, no por cuántas veces se repite en uno
solo de ellos.

---

## Usuarios / actores

- **Motor de búsqueda interno** (`buscar_por_frase`): calcula el ranking de candidatos.
- **Cualquier usuario o agente** que llame a `buscar`, `recordar` o `buscar_por_frase` —
  no hay cambios en la interfaz pública.

---

## Historias de usuario

- H1: Como usuario que busca un tema, quiero que el nodo más relevante (el que trata
  exactamente de ese tema) aparezca primero, aunque su texto sea corto y otro nodo más
  largo mencione las mismas palabras de pasada.
- H2: Como agente que guarda memorias con concepto, sinónimos y sustantivos bien
  definidos, quiero que esa estructura bien completada sea premiada en el ranking frente a
  nodos con solo contenido largo pero mal estructurados.

---

## Requisitos funcionales (criterios de aceptación en EARS)

- **RF-1:** CUANDO el motor calcula el score de un candidato, EL SISTEMA debe evaluar en
  cuántos de los cuatro campos estructurados (`concepto`, `sinonimos`, `sustantivos_clave`,
  `contenido`) aparece al menos un **token normalizado** de la búsqueda (sin stopwords,
  sin acentos, mismo proceso que `concepto_ratio` y `sinonimos_ratio`). Un campo se
  considera activo si contiene **al menos uno** de los tokens — no se requiere que los
  contenga todos.

- **RF-2:** EL SISTEMA debe tratar cada campo como un canal binario: activo (1) si
  contiene al menos un token de la búsqueda, inactivo (0) si no contiene ninguno.
  **La repetición de tokens dentro del mismo campo NO incrementa el valor del canal** —
  50 menciones en `contenido` cuentan igual que 1 mención.

- **RF-3:** EL SISTEMA debe calcular el factor de convergencia como:
  ```
  convergencia = canales_activos / 4.0
  ```
  donde `canales_activos` es la suma de los cuatro canales binarios (valor entre 0.0 y 1.0).

- **RF-4:** EL SISTEMA debe aplicar el factor de convergencia como **multiplicador** sobre
  el score híbrido ya calculado, no como una señal aditiva nueva:
  ```
  score_final = score_hibrido × (alpha + (1 - alpha) × convergencia)
  ```
  donde `alpha` es un parámetro configurable con valor por defecto 0.5, que garantiza
  que un nodo con convergencia 0 no quede en score 0 absoluto.

- **RF-5:** CUANDO la convergencia es 1.0 (los 4 campos activos), EL SISTEMA no debe
  modificar el score híbrido base (multiplicador = 1.0).

- **RF-6:** CUANDO la convergencia es 0.25 (solo 1 campo activo, típicamente solo
  `contenido`), EL SISTEMA debe reducir el score híbrido base a máximo 62.5% de su valor
  (con alpha=0.5: `0.5 + 0.5×0.25 = 0.625`).

- **RF-7:** EL SISTEMA debe poder desactivar este mecanismo mediante la variable de
  entorno `BIORAG_CONVERGENCIA_ACTIVA=0` sin necesidad de modificar código, restaurando
  el comportamiento anterior.

- **RF-7b:** CUANDO `BIORAG_CONVERGENCIA_ACTIVA=0`, EL SISTEMA debe aplicar multiplicador
  = 1.0 a todos los candidatos (equivalente a no tener convergencia).

- **RF-8:** EL SISTEMA debe poder ajustar el peso del alpha mediante la variable de
  entorno `BIORAG_CONVERGENCIA_ALPHA` (float en el rango **(0.0, 1.0) exclusivo**, default 0.5).
  SI el valor recibido está fuera de ese rango (≤ 0.0 o ≥ 1.0), EL SISTEMA debe clampear
  al valor más cercano válido (`0.01` si ≤ 0.0, `0.99` si ≥ 1.0) y registrar un warning
  en el log con el valor recibido y el valor usado.
  **Nota**: `alpha = 0.0` llevaría a score × 0 cuando convergencia = 0 (elimina el nodo);
  `alpha = 1.0` desactiva el efecto silenciosamente (multiplicador = 1.0 siempre).

- **RF-9:** CUANDO `match_exacto=True` para un candidato (la query coincide exactamente
  con el nombre del nodo), EL SISTEMA no debe aplicar el factor de convergencia — el bono
  de match exacto es suficiente y la convergencia sería redundante.

- **RF-10:** El factor de convergencia debe calcularse usando los **tokens normalizados**
  de la búsqueda (sin stopwords, sin acentos), aplicando la misma normalización que el
  sistema usa actualmente para `concepto_ratio` y `sinonimos_ratio`.

---

## Requisitos no funcionales

- **RNF-1:** El cálculo de convergencia no debe requerir consultas individuales por
  candidato. Se permite una única consulta batch previa al loop de scoring para obtener
  `sustantivos_clave` de todos los candidatos a la vez (el mismo patrón que ya existe
  para `concepto_sinonimos_map`). `concepto` y `contenido` ya están disponibles en el
  array de candidatos. `sinonimos` ya se obtiene en el batch existente.
- **RNF-2:** El tiempo de cómputo del factor de convergencia debe ser O(T×4) donde T es
  el número de tokens de la búsqueda — despreciable frente al resto del scoring.
- **RNF-3:** El resultado del score final debe seguir siendo un float en [0.0, 1.0].
- **RNF-4:** El mecanismo es invariante al tamaño del corpus — no depende de N ni de la
  distribución del corpus.
- **RNF-5:** El benchmark de 921 casos congelados (`qa_escape_qcr_20260811.db`) debe
  mantener o mejorar Recall@5 ≥ 97.0% y Recall@1 ≥ 88.76%.

---

## Casos límite

- **CL-1:** Nodo sin `sustantivos_clave` (campo vacío o NULL): el canal de sustantivos
  se marca como inactivo (0). La convergencia máxima para ese nodo es 3/4 = 0.75.
- **CL-2:** Nodo sin `sinonimos`: canal inactivo, convergencia máxima 0.75.
- **CL-3:** Query de tokens que quedan todos vacíos tras normalización (ej: solo
  stopwords): no se aplica el factor (se usa multiplicador = 1.0, sin penalización).
- **CL-4:** Token que aparece solo en `contenido` con 500 repeticiones: el canal de
  contenido vale 1. Sin bonificación por frecuencia.
- **CL-5:** Candidato con `match_exacto=True`: el factor de convergencia no se aplica
  (RF-9).
- **CL-6:** Todos los canales inactivos (convergencia = 0.0): el score final es
  `score_hibrido × alpha`. Con alpha=0.5, el nodo se atenúa pero no desaparece.
- **CL-7:** Candidatos recuperados por capas **no léxicas** (origen = `semantica`,
  `dimensional_fallback`, `sdm`, `expansion`, `cadena`, `typo`, `simbolico`,
  `lexico_aprendido`): el factor de convergencia NO se aplica (multiplicador = 1.0).
  Estos nodos entran al pool precisamente porque no hay overlap léxico con la query —
  penalizarlos por no tener tokens en los campos sería contradictorio con su función.
- **CL-8:** Query multipalabra cuyos tokens se distribuyen entre campos distintos
  (ej: `concepto` tiene token A, `sinonimos` tiene token B): ambos canales se marcan
  como activos (1). La regla es "al menos un token" por campo, no "todos los tokens".
- **CL-9:** `BIORAG_CONVERGENCIA_ALPHA` con valor fuera de **(0.0, 1.0)** (ej: 0.0, 1.0, 2.5, -0.1):
  se clampea al valor válido más cercano (`0.01` o `0.99`) y se registra un warning en el
  log. Los valores extremos (0 y 1) se rechazan porque producen comportamientos degenerados
  (ver RF-8).

---

## Fuera de alcance

- Cambiar los pesos existentes en `_calcular_score_hibrido`.
- Añadir nuevas señales aditivas al sistema de scoring.
- Modificar cómo se generan los candidatos (capas FTS, fallbacks, sináptica).
- Cambiar el comportamiento del QCR, re-ranking Jaccard o inhibición GABA.
- Modificar el esquema de la base de datos.
- Cambiar la interfaz pública de `buscar_por_frase` o las herramientas MCP.
- Implementar convergencia sobre campos adicionales (`asociaciones`, `bridges`, `dimensiones`).
- **Corrección del efecto del Concept Hub**: cuando un candidato es promovido por el
  Concept Hub, esa promoción ocurre **después** del scoring y del multiplicador de
  convergencia. Por tanto, una query como `"version actual biorag"` cuyo resultado top-1
  es promovido por el Hub no será corregida por este cambio. Ese comportamiento es
  atribuible al Hub y queda fuera del alcance de Spec-006.

---

## Resultado esperado

**Cuantitativo — benchmark 921 casos congelados:**
- Recall@5 ≥ 97.0% (igual o mayor que `baseline_oficial_20260826.txt`)
- Recall@1 ≥ 88.76% (igual o mayor)
- MRR ≥ 0.916 (igual o mayor)
- Falsos positivos: 0.0%
- Gate: `[GATE] OK` en `evaluar_qa.py` — si aparece cualquier otra salida, es regresión.

**Cualitativo — smoke test con DB de producción:**
- `version_actual_biorag` pasa de TOP-2 a TOP-1 para la query
  `"cual es la ultima version de biorag"`.
- `reindex_selectivo_dirty` baja de posición (era TOP-1 incorrectamente).
- El top-5 completo sigue siendo temáticamente coherente con el tema
  "versión de biorag" — no aparecen nodos irrelevantes como daño colateral.

**Comportamiento estructural garantizado:**
- Un nodo con match en 4/4 campos SIEMPRE supera a un nodo con match en
  1/4 campos, dado el mismo score híbrido base de entrada.
- Un nodo con la palabra buscada repetida 500 veces en `contenido` obtiene
  el mismo multiplicador que uno con 1 sola mención (canal binario).

---

## Criterios de finalización

1. **ANTES de implementar:** ejecutar `evaluar_qa.py` contra el snapshot congelado y
   verificar que los resultados coinciden con `scripts/baseline_oficial_20260826.txt`.
   Si no coinciden, se detiene todo — el entorno no está limpio y no se puede medir
   el impacto del cambio de forma confiable.

2. **DESPUÉS de implementar:** ejecutar `evaluar_qa.py` contra el mismo snapshot. Los
   resultados deben ser iguales o mejores que `scripts/baseline_oficial_20260826.txt`.
   Cualquier métrica que baje (Recall@1, Recall@5, MRR) es una regresión que bloquea
   el cambio — se revierte inmediatamente.
3. Test unitario: nodo con match en 4 campos supera a nodo con match solo en `contenido`,
   dado el mismo score híbrido base.
4. Test unitario: 500 repeticiones de un token en `contenido` producen el mismo
   multiplicador que 1 repetición (canal binario, RF-2).
5. Test: `BIORAG_CONVERGENCIA_ACTIVA=0` restaura el comportamiento anterior exacto.
6. Test: `match_exacto=True` no aplica el multiplicador (RF-9).
7. **Test de humo con la DB de producción real (sin modificarla) — Top-5 completo:**
   Query: `"cual es la ultima version de biorag"` (y paráfrasis: `"ultima version biorag"`,
   `"version actual biorag"`).

   **Paso 7a — Capturar top-5 ANTES del cambio** (línea base de humo):
   Ejecutar la búsqueda y registrar los 5 nodos con sus scores. Comportamiento conocido:
   TOP-1 = `reindex_selectivo_dirty` (~0.82), TOP-2 = `version_actual_biorag` (~0.78).

   **Paso 7b — Capturar top-5 DESPUÉS del cambio** y verificar:
   - `version_actual_biorag` debe aparecer en el TOP-1 o TOP-2 con score igual o mayor al actual.
   - `reindex_selectivo_dirty` debe haber bajado de posición (su match es solo en `contenido`).
   - Los demás nodos del top-5 deben seguir siendo relevantes al tema "versión de biorag"
     (no deben aparecer nodos completamente irrelevantes como resultado del cambio).

   **Nota sobre `"version actual biorag"`**: según análisis previo, en esta paráfrasis el
   candidato top-1 puede ser promovido por el **Concept Hub** (origen `concept_hub`), que
   actúa post-scoring. El multiplicador de convergencia NO puede corregir una promoción
   que ocurre después de aplicarse. Si `reindex_selectivo_dirty` sigue top-1 en esta
   paráfrasis tras el cambio, **no es una regresión** — es el comportamiento esperado
   documentado como fuera de alcance (ver sección "Fuera de alcance"). El criterio de
   éxito aplica a la **query principal** (`"cual es la ultima version de biorag"`).

   La DB de producción no se modifica en ningún paso. Solo se comparan rankings.

---

## Dudas abiertas

- [RESUELTO] El `contenido` para el canal binario usa el texto **completo** (no truncado).
  Dado que el resultado es binario, un texto largo no suma más puntos por ser largo.
  El rendimiento no es un problema porque el `contenido` ya está cargado en memoria
  como parte del array de candidatos — no se genera ninguna consulta adicional a la
  base de datos. La verificación es una operación Python pura en RAM: O(T × 4 × K)
  donde T = tokens de la query, 4 = campos, K = candidatos en el pool (típicamente ≤ 50).
