# E1 — QA honesta (segunda entrega, reglas estrictas)

**Fecha:** 2026-10-26 · **Rama:** `arena/33a8df67-memorybiorag` · **Alcance:** solo
`scripts/evaluar_qa.py` y sus pruebas. Cero código del motor.

## Las tres reglas, aplicadas

**1. OBSOLETA = "YA NO declara".**
El recuerdo esperado declaraba la palabra en el **snapshot de origen** (alias
completo o palabra entera del nombre) y **ya no la declara** en la base medida.
Sin la referencia no se puede afirmar «ya no», así que sin ella `obsoleta` queda
en `False`: no se inventa. Midiendo el propio snapshot son 0 por construcción.

**2. AMBIGUA sin «contiene».**
Solo dos formas cuentan: **alias completo** (`filtro-arquitecto-prolijo` ==
`filtro-arquitecto-prolijo`) o **palabra entera dentro del nombre** (`perfil`
dentro de `dennys_perfil_gustos`). Con substring, `agente` reclamaba 119 nodos
siendo 32 los exactos, porque entraba en `agentes`, `agencia`…, y
`oracle identification` salía ambigua con un solo reclamante real.

**3. Umbral POR MÉTRICA** (decisión de Dennys):
- **R@5**: se aparta solo con **más de 5** reclamantes. Con 5 o menos, todos
  caben en el top-5.
- **R@1**: se aparta desde **2**.

Una misma pregunta puede contar para el R@5 y no para el R@1. **Este umbral se
decidió DESPUÉS de ver la primera medición de E1.** Es una decisión consciente,
no una regla previa, y el informe lo dice en su cabecera.

## Comprobación de las cifras de referencia

| base | obsoletas | ambiguas | ambiguas para R@5 |
|---|---:|---:|---:|
| snapshot | **0** | **28** | **14** |
| viva | **1** (`0674`) | **30** | **17** |

Coinciden exactamente con las del auditor. La viva tiene una obsoleta y es la que
él predijo: `compuerta-pre-validacion` declaraba `filtro-arquitecto-prolijo` como
alias completo en el snapshot, y en la base viva ese alias fue sustituido por
`filtro-de-impacto`.

## Las dos tablas

### SNAPSHOT (866 nodos, `BIORAG_NEURONA=0`, 921 casos)

```
Categoría            |            CLÁSICA |          HONESTA R@5 |          HONESTA R@1
                     |      n   R@5   R@1 |      n    R@5   ap. |      n    R@1   ap.
sinonimo             |     55 100.0% 56.4% |     45 100.0%    14 |     33  87.9%    28
GLOBAL (recuperación)|    875 100.0% 93.1% |    865 100.0%    14 |    853  95.3%    28
fallos (fuera top-5) |      0             |      0              |
no llegó al 1º puesto|     60             |                     |     40
MRR                  |                    |                     |        0.9718
```

### BASE VIVA (1357 nodos, `BIORAG_NEURONA=0`, 921 casos)

```
Categoría            |            CLÁSICA |          HONESTA R@5 |          HONESTA R@1
                     |      n   R@5   R@1 |      n    R@5   ap. |      n    R@1   ap.
sinonimo             |     55  89.1% 52.7% |     41 100.0%    18 |     30  90.0%    31
por_tema             |     65  98.5% 63.1% |     65  98.5%     0 |     65  63.1%     0
GLOBAL (recuperación)|    875  99.2% 91.1% |    861  99.9%    18 |    850  93.5%    31
fallos (fuera top-5) |      7             |      1              |
no llegó al 1º puesto|     78             |                     |     55
MRR                  |                    |                     |        0.9622
```

Resto de categorías: idénticas en las tres columnas (el cambio solo toca
`sinonimo`).

## Lectura

- El **único fallo honesto** de la base viva sigue siendo `por_tema` **0848**.
  Ese es el objetivo de E2.
- `sinonimo` queda al **100 % de R@5** en las dos bases, y en R@1 al 87,9 %
  (snapshot) y 90,0 % (viva) entre los casos que se conservan.
- La viva **sube** al apartar: su R@1 honesto de `sinonimo` (90,0 %) es mayor que
  el del snapshot (87,9 %), porque sus 30 ambiguas restantes pesan menos.

## Nota sobre 61 y 55

`sinonimo` tiene **61** casos en el JSONL, pero la fila de la tabla muestra **55**
porque la QA ya reubica 6 con etiqueta contradictoria en la categoría `ambiguo`.
Los «apartados» se cuentan sobre los 61; el informe lo aclara en la misma línea
para que no parezca un descuadre.

## Artefactos

- `docs/e1b_qa_honesta_snapshot_20261026.log` / `.json`
- `docs/e1b_qa_honesta_viva_20261026.log` / `.json`
- `tests/test_qa_honesta.py` — 13 pruebas: regla 1 (3), regla 2 (4), regla 3 (3),
  tabla por métrica (2) y el aviso del umbral (1).

## Fallo propio, corregido

La primera versión de la prueba de la regla 1 abría el snapshot **directo**, y el
motor lo pasaba a modo WAL: le cambió el sha256. Se detectó antes de entregar,
se restauró el archivo (vuelve a `104dd2902aaf`) y la prueba ahora trabaja sobre
una copia y verifica ella misma que el original no cambió.
