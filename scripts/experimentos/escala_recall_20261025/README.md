# Experimento: invariancia de escala del recall base (fórmula, sin neurona) — 2026-10-25

**Pregunta:** ¿el recall de la fórmula depende del tamaño o del contenido de la memoria?
**Respuesta:** sí dependía. Se encontraron 4 mecanismos y se repararon. Con los arreglos
(`BIORAG_ESCALA=1`, el valor por defecto) el recall deja de caer al crecer, salvo en
empates de preguntas de una sola palabra y en una debilidad del ranking principal que ya
existía (ver «Lo que queda»).

## Cómo se midió
- QA oficial `scripts/evaluar_qa.py` (921 casos, `limite=5`), `BIORAG_NEURONA=0`,
  `PYTHONHASHSEED=1`. Siempre sobre COPIAS: el snapshot y la base viva no se tocaron
  (sha256 del snapshot `104dd2902aaf…` antes y después).
- Copias crecidas (`crecer.py`, `LIMPIO=1` = sin párrafos que citen preguntas de la QA;
  `dims_nn.py` = cada relleno recibe las dimensiones de su recuerdo real más parecido):
  - **S0**: snapshot original, 866 recuerdos.
  - **A640**: + 640 documentos ajenos (1506).
  - **T1000r**: + 1000 apuntes del mismo tema (1866).
  - **T3000r**: + 3000 apuntes del mismo tema (~3866).
- `_off` = `BIORAG_ESCALA=0` (motor anterior); `_fin` = con los 4 arreglos.
- Directorio de trabajo de los scripts: `/tmp/v` (las bases no se guardan en git).

## Resultado (R@1 y R@5 por categoría; ver `tabla_final.txt`)

| Copia | Recuerdos | R@5 antes | R@5 después | R@1 antes | R@1 después | FP |
|---|---|---|---|---|---|---|
| S0 | 866 | 100 | **100** | 91.89 | **92.57** | 0/40 |
| A640 | 1506 | 99.66 | **99.77** | 92.46 | **93.03** | 0/40 |
| T1000r | 1866 | 99.31 | **99.89** | 92.00 | **92.80** | 0/40 |
| T3000r | ~3866 | 99.20 | **99.54** | 91.77 | **92.57** | 0/40 |

Ninguna categoría baja respecto de su propia copia sin arreglo.

## Los 4 mecanismos y sus arreglos (`core/memory/search.py` + `core/memory/escala.py`)
1. **Compuerta del rescate de typos** — se apagaba si OTRO recuerdo cubría la pregunta
   (basta una nota que la cite). Arreglo: si la pregunta trae palabras que la memoria no
   conoce (aparecen en ≤ 1 recuerdo), el rescate corre.
2. **Ventanas por antigüedad** — el rescate simbólico (1000 filas) y el fallback 1.7
   (200 filas) miraban los recuerdos MÁS VIEJOS. Arreglo: miran los más parecidos
   (bm25 sobre trigramas). Solo actúa cuando hay más recuerdos que la ventana.
3. **Dimensiones prestadas** — cuando el agente no da dimensiones, se infieren de los 5
   primeros resultados; al crecer, esos 5 son rellenos y recuerdos genéricos sin ninguna
   palabra de la pregunta se saltaban el filtro QCR. Arreglo: con dimensiones inferidas
   (no dadas por el agente) no hay escape de QCR.
4. **Palabra real tratada como typo** — al ver los candidatos correctos, el parecido
   difuso empataba «rector» con «vector». Arreglo: el parecido difuso es solo para
   palabras que la memoria no conoce; una palabra conocida solo empata con sus
   flexiones (mismo comienzo de 3 letras).

## Lo que queda (honesto)
- `0805` «cv» y `0734` «regla»: empates. ~30 y 132 recuerdos contienen la palabra; la
  respuesta ya estaba 5.ª en S0 y la separan 0.0001–0.003 de su vecino.
- `0516`, `0681` (solo en T3000r): la respuesta ya estaba 4.ª en S0; al crecer, recuerdos
  que repiten UNA palabra muchas veces le ganan a la única que tiene TODAS. Es el
  ranking principal (cobertura de palabras poco premiada); no se tocó sin acuerdo.

## Pruebas
- `tests/test_escala.py` (17) y `tests/test_escala_motor.py` (7): reproducen cada
  mecanismo dentro del motor real y verifican el arreglo.
- `tests/test_qcr_typo_d4.py`: dos tests fijan `BIORAG_ESCALA=0` para aislar QCR-typo;
  uno nuevo verifica que con escala el rescate trae la respuesta correcta y nunca el control.
- Suite completa: 489 passed.

## Nota de entorno
Sin `MemoryBioRAG_Data/nltk_data` (WordNet) el motor no falla: degrada en silencio
(4 casos cambian). Una copia del código sin esa carpeta mide otra cosa.
