# Spec 007 — Convergencia Multi-Campo (Bonus Aditivo Post-QCR)

> **Contexto de evolución**:
> Esta especificación sustituye el enfoque multiplicativo original (Spec 006) por un
> **bonus aditivo post-QCR** tras el análisis forense A/B que identificó las causas raíz
> de regresión (bypass asimétrico, penalización por variante morfológica y efecto
> monotónico negativo sobre scores).

---

## Contexto y objetivo

El motor de scoring actual puede posicionar un nodo incorrecto en el primer lugar cuando
una palabra buscada aparece muchas veces dentro de su campo `contenido`, aunque ese nodo
no trate realmente del tema buscado. Un texto largo con múltiples menciones casuales de una
palabra supera en ranking a un nodo cuyo título, sinónimos y sustantivos clave son exactamente
esa palabra.

El objetivo es corregir esto: la relevancia real de un nodo se mide por en cuántos campos
estructurales independientes resuena la búsqueda (resonancia estructural), no por cuántas
veces se repite en uno solo de ellos.

---

## Usuarios / actores

- **Motor de búsqueda interno** (`buscar_por_frase`): calcula el ranking de candidatos.
- **Cualquier usuario o agente** que llame a `buscar`, `recordar` o `buscar_por_frase` —
  no hay cambios en la interfaz pública ni en el formato de respuesta.

---

## Historias de usuario

- **H1:** Como usuario que busca un tema, quiero que el nodo más relevante (el que trata
  exactamente de ese tema a nivel conceptual y estructural) aparezca primero, aunque su
  texto sea corto y otro nodo más largo mencione las mismas palabras de pasada.
- **H2:** Como agente que guarda memorias con concepto, sinónimos y sustantivos bien
  definidos, quiero que esa estructura bien completada sea premiada en el ranking frente a
  nodos con solo contenido largo pero mal estructurados.

---

## Requisitos funcionales (criterios de aceptación en EARS)

- **RF-1:** CUANDO el motor calcula el score de un candidato, EL SISTEMA debe evaluar en
  cuántos de los cuatro campos estructurados (`concepto`, `sinonimos`, `sustantivos_clave`,
  `contenido`) aparece al menos un **token normalizado** de la búsqueda (sin stopwords,
  sin acentos, aplicando la misma normalización que `concepto_ratio` y `sinonimos_ratio`).
  Un campo se considera activo si contiene **al menos uno** de los tokens.
  Los cuatro canales tienen **igual peso** (conteo igualitario).

- **RF-2:** EL SISTEMA debe tratar cada campo como un canal binario: activo (1) si
  contiene al menos un token de la búsqueda, inactivo (0) si no contiene ninguno.
  La repetición de tokens dentro del mismo campo NO incrementa el valor del canal.

- **RF-3:** EL SISTEMA debe calcular `canales_activos` como la suma de los cuatro canales
  binarios (entero entre 0 y 4 inclusive).

- **RF-4:** EL SISTEMA debe aplicar la convergencia como un **bonus aditivo** sobre el
  score base, exclusivamente para determinar el **orden del sort final post-QCR**.
  El `score_base` (valor en `r[4]` de la tupla retornada) **NO debe modificarse**:
  ```
  bonus_conv(n) = CONVERGENCIA_BONUS_MAX × max(0, canales(n) − 1) / 3
  score_ranking(n) = min(1.0, score_base(n) + bonus_conv(n))
  ```
  donde `CONVERGENCIA_BONUS_MAX` ∈ (0.0, 1.0], default **0.05**.

  Valores resultantes con `BONUS_MAX = 0.05`:
  - `canales = 0` → `bonus = 0.000` (neutral)
  - `canales = 1` → `bonus = 0.000` (neutral — caso base)
  - `canales = 2` → `bonus = 0.017`
  - `canales = 3` → `bonus = 0.033`
  - `canales = 4` → `bonus = 0.050` (máximo)

- **RF-5:** CUANDO `canales = 4` (los 4 campos activos), EL SISTEMA aplica el bonus
  máximo (`CONVERGENCIA_BONUS_MAX`). CUANDO `canales ≤ 1`, el bonus es 0 y el
  `score_ranking` es idéntico al `score_base` — ningún nodo es penalizado.

- **RF-6:** EL SISTEMA debe ordenar los resultados finales post-QCR por `score_ranking`
  descendente, preservando el `score_base` original en la posición `r[4]` de cada resultado.

- **RF-7:** EL SISTEMA debe poder desactivar este mecanismo mediante la variable de
  entorno `BIORAG_CONVERGENCIA_ACTIVA=0` sin necesidad de modificar código, restaurando
  el comportamiento anterior exacto (sort únicamente por `score_base`).

- **RF-7b:** CUANDO `BIORAG_CONVERGENCIA_ACTIVA=0`, EL SISTEMA debe usar `bonus = 0`
  para todos los candidatos, produciendo el mismo orden que el baseline sin convergencia.

- **RF-8:** EL SISTEMA debe exponer `BIORAG_CONVERGENCIA_BONUS_MAX` (float en `(0.0, 1.0]`,
  default `0.05`) para controlar el bonus máximo aplicable.
  SI `BONUS_MAX ≤ 0.0` o `> 1.0`, EL SISTEMA debe clampear (`0.001` si ≤ 0, `1.0` si > 1.0)
  y registrar un **warning** en el log con el valor recibido y el valor usado.

- **RF-9:** EL SISTEMA debe mantener `BIORAG_CONVERGENCIA_ALPHA` en `constants.py` únicamente
  por compatibilidad retrospectiva, sin utilizarlo en el cálculo del nuevo bonus aditivo.

- **RF-10:** El bonus de convergencia debe calcularse usando los **tokens normalizados**
  de la búsqueda (sin stopwords, sin acentos), reutilizando la tokenización `q_set` ya
  calculada para el scoring simbólico.

- **RF-11 (Contrato de score retornado):** EL SISTEMA debe retornar en `r[4]` de cada
  tupla el `score_base` (valor de `_calcular_score_hibrido`, sin el bonus de convergencia).
  El `score_ranking` es únicamente un criterio de ordenamiento interno. Ningún consumidor
  externo (MCP, CLI, `evaluar_qa.py`, test suites) debe recibir scores inflados por el bonus.

- **RF-12 (Posición en pipeline):** El bonus de convergencia DEBE aplicarse **después**
  de todos los pasos que consumen `score_base`:
  ```
  (a) _calcular_score_hibrido       → produce score_base  [sin cambios]
  (b) Filtro QCR                    → usa score_base       [sin cambios]
  (c) Promoción GABA/Hub/lexico     → usan score_base      [sin cambios]
  (d) ← APLICACIÓN DEL BONUS ADITIVO → (sort final por score_ranking)
  ```
  Las semillas del BFS y la expansión de contexto sináptico se calculan con `score_base`,
  antes del bonus.

- **RF-13 (Paridad con evaluador oficial):** Cualquier verificación o smoke test que
  pretenda ser comparable con el benchmark oficial debe llamar a `buscar_por_frase` con
  `ignore_peso_sinaptico=True`.

---

## Requisitos no funcionales

- **RNF-1:** El cálculo de convergencia no debe requerir consultas SQL individuales por
  candidato. Se reutiliza la consulta batch única previa al loop de scoring para obtener
  `sustantivos_clave` de todos los candidatos simultáneamente.
- **RNF-2:** El tiempo de cómputo del factor de convergencia debe ser O(T×4) donde T es
  el número de tokens de la búsqueda — computacionalmente despreciable.
- **RNF-3:** El valor de `score_ranking` debe ser un float en [0.0, 1.0].
  El `score_base` retornado en `r[4]` preserva su rango calibrado original.
- **RNF-4:** El mecanismo es invariante al tamaño del corpus — no depende de N ni de la
  distribución del corpus.
- **RNF-5:** El benchmark completo de 921 casos (`evaluar_qa.py` con
  `ignore_peso_sinaptico=True`) es el **gate bloqueante obligatorio**:
  Recall@5 ≥ 97.0%, Recall@1 ≥ 88.76%, MRR ≥ 0.916, FPR = 0.0%.

---

## Casos límite

- **CL-1:** Nodo sin `sustantivos_clave` (campo vacío o NULL): el canal de sustantivos
  se marca como inactivo (0). El bonus máximo para ese nodo es `BONUS_MAX × 2/3`.
- **CL-2:** Nodo sin `sinonimos`: canal inactivo, bonus máximo `BONUS_MAX × 2/3`.
- **CL-3:** Query de tokens que quedan vacíos tras normalización (ej: solo stopwords):
  `q_set` vacío → no se aplica bonus (`score_ranking == score_base`).
- **CL-4:** Token que aparece solo en `contenido` con 500 repeticiones: canal de contenido
  vale 1. Sin bonificación por frecuencia interna.
- **CL-5:** Candidato con `match_exacto=True`: recibe el mismo cálculo de bonus sin bypass
  especial (al no haber penalizaciones, no se requieren inmunizaciones).
- **CL-6:** Todos los canales inactivos (0/4): `bonus = 0`. El `score_ranking` es idéntico
  al `score_base`.
- **CL-7:** Candidatos recuperados por capas no léxicas (`sdm`, `dimensional_fallback`, etc.):
  reciben el mismo cálculo uniforme de bonus sin bypass asimétrico.
- **CL-8:** Query multipalabra con tokens distribuidos entre distintos campos: cada campo
  con al menos un token se marca como activo (1).
- **CL-9:** `BIORAG_CONVERGENCIA_BONUS_MAX` fuera de `(0.0, 1.0]`: clampeo defensivo a
  `0.001` (si ≤ 0) o `1.0` (si > 1.0) con log warning.
- **CL-10:** Consumidor externo que reordene manualmente por `r[4]`: observará `score_base`
  calibrado sin distorsión.

---

## Fuera de alcance

- Cambiar los pesos de señales en `_calcular_score_hibrido`.
- Añadir nuevas señales aditivas permanentes al `score_base`.
- Modificar la generación de candidatos (capas FTS, fallbacks, sinapsis).
- Modificar el esquema de base de datos SQLite.
- Modificar la firma o contratos públicos de `buscar_por_frase` o MCP tools.
- Ponderación heterogénea de canales (conteo no igualitario entre campos).
- Corrección de promociones post-scoring ejecutadas por el Concept Hub.

---

## Criterios de finalización

1. **Gate Benchmark Oficial:** Ejecución de `evaluar_qa.py` con `ignore_peso_sinaptico=True`
   contra el snapshot congelado con `[GATE] OK`, Recall@5 ≥ 97.0%, Recall@1 ≥ 88.76%,
   MRR ≥ 0.916 y FPR = 0.0%.
2. **Test Unitario Resonancia:** Nodo con 4/4 campos activos supera a nodo con 1/4 campos,
   a igualdad de `score_base`.
3. **Test Unitario Frecuencia Binaria:** 500 repeticiones en `contenido` producen el mismo
   bonus que 1 repetición.
4. **Test Unitario Desactivación:** `BIORAG_CONVERGENCIA_ACTIVA=0` restaura el orden exacto
   del baseline.
5. **Test Unitario Integridad de Score:** El valor `r[4]` retornado es idéntico a `score_base`.
6. **Test Unitario Clamping:** Validación de límites inferior y superior para `BONUS_MAX`.
7. **Smoke Test Producción (No destructivo):** En copia temporal de la DB viva, verificar que
   `version_actual_biorag` mejora ranking frente a `reindex_selectivo_dirty` para
   `"cual es la ultima version de biorag"`.

---

## Dudas abiertas

- [RESUELTO] El cálculo opera exclusivamente sobre el sort final post-QCR.
- [RESUELTO] El score en `r[4]` se mantiene como `score_base` sin alteraciones.
- [RESUELTO] La variable de control es `CONVERGENCIA_BONUS_MAX` (default 0.05).
