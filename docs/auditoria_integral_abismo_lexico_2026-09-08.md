# Auditoría integral de MemoryBioRAG: hacia un circuito léxico aprendido sin embeddings

**Fecha:** 2026-09-08  
**Alcance:** código, base SQLite, índices, grafo, rutas MCP/CLI/dashboard, consolidación, experimentos de recuperación y auditorías de generalización.  
**Restricción:** no usar embeddings densos como mecanismo de solución.

## Conclusión ejecutiva

La hipótesis más probable es que el sistema no cruza el abismo léxico fuera de familia porque su arquitectura actual es **anchor-first y parcialmente curada por léxico**. La búsqueda empieza normalmente con una coincidencia textual, un alias, un dominio, un Concept Hub, una semilla de grafo o un candidato ya generado por una señal previa. Las señales no léxicas existentes —PPMI, grafo, comunidades, predicados, latentes, ADN y hubs— suelen reordenar o expandir candidatos que ya tienen un ancla. No suelen generar una hipótesis de memoria desde una consulta completamente nueva.

Por tanto, el problema no es simplemente que falte otro `score`. El problema es que el sistema todavía no tiene una representación persistente y autoritativa de la experiencia:

> «La expresión A, en este contexto, refiere al concepto o experiencia B». 

Un cerebro humano no conoce una equivalencia inédita porque la palabra exista en abstracto. La conoce porque la aprendió en una experiencia, una explicación, una corrección o una situación compartida. MemoryBioRAG ya posee casi todos los materiales para registrar ese hecho, pero no los une en un circuito léxico atómico, bidireccional, trazable y consumido por todas las rutas de recuperación.

## Lo que ya existe

La base contiene una infraestructura considerable:

| Componente | Evidencia observada | Función actual |
|---|---|---|
| Memoria de largo plazo | `largo_plazo` | Conceptos, contenido, estado, asociaciones históricas y sinónimos |
| Recuperación textual | `largo_plazo_fts`, `largo_plazo_fts_unicode` | Búsqueda léxica; los triggers mantienen el contenido sincronizado |
| Grafo canónico | `sinapsis` | Relaciones tipadas y pesos entre nodos |
| Memoria latente | `sinapsis_latentes` | Relaciones inferidas pendientes de consolidación |
| Dimensiones | `dimensiones_semanticas`, `largo_plazo_dimensiones` | Señales categoriales y de dominio |
| Predicados | tablas y módulos de predicados | Estructura proposicional y compatibilidad relacional |
| Concept Hubs | hubs y bridges | Puentes curados o consolidados entre conceptos |
| Léxico | WordNet, diccionarios de dominio, sinónimos | Expansión léxica ya conocida |
| Asociación histórica | `largo_plazo.asociaciones` | Referencias CSV heredadas; no coincide completamente con el grafo |
| Plasticidad | SDM, PPMI, promoción de hubs, sueño y autovinculación | Refuerzo, coocurrencia y consolidación de señales |
| Trazabilidad | logs, cuarentena, sinapsis tipadas y campos de procedencia | Auditoría parcial del origen de relaciones |

La auditoría de consistencia encontró aproximadamente **1.010 memorias**, **18.894 sinapsis**, **11.639 relaciones latentes**, **7.177 dimensiones**, **270 predicados**, **23 hubs**, **115 bridges** y un diccionario de dominio de aproximadamente **6.490 términos**. Los índices FTS no mostraron divergencias de contenido en la comprobación realizada.

Esto significa que no estamos ante un sistema vacío. Estamos ante un sistema con mucha memoria, pero con varias representaciones que no forman una única ruta de aprendizaje y recuperación.

## El descubrimiento principal: hay dos problemas diferentes

Los experimentos mezclan a veces dos fallos que deben separarse.

### Fallo de generación

El Gold no entra al pool. Ningún ranker puede rescatarlo después. EXP-N8 muestra este problema en varios casos. Para esos casos falta una hipótesis candidata o una relación aprendida que permita llegar al nodo.

### Fallo de ranking

El Gold sí entra al pool, pero queda debajo de muchos candidatos genéricos. EXP-N9 y EXP-N10 confirmaron que conectar un ranker SCG genérico o comparar perfiles FCC no resuelve automáticamente el problema. En EXP-N9 el Gold entró en 4/8 pools, pero sólo obtuvo CE@5 en 1/8 y CE@20 en 2/8. En Strict A0 la generación fue 3/6 y CE@20 fue 1/6.

La consecuencia práctica es clara:

```text
primero hay que mejorar la representación y la generación;
después hay que ajustar el ranking.
```

## El problema de cableado

### 1. El dashboard tiene una ruta distinta

La auditoría encontró que el dashboard no usa siempre el mismo motor que MCP y CLI. En particular, `/api/buscar` puede caer en `LIKE` SQL en lugar de pasar por `buscar_por_frase`. Algunas rutas de aprendizaje y CRUD escriben directamente en SQLite y se saltan pasos de consolidación, autovinculación, dimensiones, predicados, conjunto dirty de SDM, actualización de PPMI y reconstrucción de ADN.

Esto puede producir una situación peligrosa: el usuario enseña algo por una interfaz, pero la memoria que luego consulta otra interfaz no recibe todas las consecuencias derivadas.

### 2. Hay más de una fuente para las asociaciones

`largo_plazo.asociaciones` y `sinapsis` no son equivalentes en el estado actual. La auditoría encontró aproximadamente **278 referencias presentes sólo en CSV** y **187 presentes sólo en el grafo**. La existencia de dos fuentes divergentes dificulta saber qué relación es canónica y qué relación debe usar el recuperador.

### 3. El ciclo de consolidación no aprende igualdad léxica de manera explícita

La consolidación conserva o combina sinónimos y puede autovincular nodos por similitud, coocurrencia o reglas. Pero autovincular no equivale a aprender:

```text
A = otra forma de referirse a B
```

El ciclo de sueño tampoco garantiza la creación de una relación tipada, simétrica, con procedencia y confianza a partir de una experiencia explícita de enseñanza.

### 4. Muchas señales son post-ancla

PPMI, grafo, comunidades, ADN, hubs y varios rankers dependen de una semilla previa. Esto explica por qué el sistema puede funcionar con memorias conocidas, hubs preexistentes o cues, pero fallar en un benchmark fuera de familia sin cue.

## La pieza que falta: Lexical Learning Episode

La solución especial para este proyecto no debe ser «otro diccionario global» ni «otro score». Debe ser una **memoria episódica de aprendizaje léxico**.

Un episodio representa un hecho aprendido en una experiencia concreta:

```text
expresión observada A
contexto de A
concepto o nodo canónico B
relación aprendida
proveniencia de la enseñanza
confianza
número de confirmaciones
fecha y ciclo de consolidación
```

La relación no debe confundirse con una similitud automática. Debe distinguir al menos:

```text
sinonimia explícita
alias de concepto
paráfrasis aprendida
referencia contextual
hiperonimia
relación causal o funcional
coocurrencia meramente observada
```

Para el caso más fuerte, la relación debería ser simétrica y tipada:

```text
A --sinonimo_explicito--> B
B --sinonimo_explicito--> A
```

Si A y B son dos formas de nombrar la misma memoria, el sistema puede conservar un concepto canónico B y registrar A como expresión aprendida. Si son memorias distintas, debe conservar la arista entre ambas, no fusionarlas silenciosamente.

## Cómo funcionaría el circuito

### Enseñanza

Cuando el usuario o un proceso confiable afirma que A significa B, el sistema no debe escribir sólo una cadena en `sinonimos`. Debe ejecutar una transacción única que:

1. normalice la expresión A;
2. identifique el nodo o concepto B;
3. registre el episodio de enseñanza;
4. actualice la forma léxica aprendida;
5. cree o actualice la relación tipada y bidireccional;
6. guarde la procedencia y la confianza;
7. marque los índices derivados como sucios;
8. reindexe o invalide la memoria de recuperación;
9. deje un evento auditable para poder retirar o corregir el aprendizaje.

### Recuperación

Una consulta nueva Q debe pasar por dos rutas ordenadas:

```text
Q
→ formas normalizadas y morfología
→ relaciones léxicas aprendidas de alta confianza
→ conceptos canónicos y experiencias asociadas
→ búsqueda estructural y textual secundaria
→ ranking y abstención
```

La expansión léxica aprendida debe ocurrir antes de pedirle al grafo o al ranker que encuentre una memoria. De lo contrario, las señales posteriores no tienen semilla.

### Aprendizaje incremental

La primera exposición puede producir una relación tentativa. Una explicación explícita o una confirmación del usuario puede elevar su confianza. Una contradicción debe reducirla o ponerla en cuarentena. La relación no debe hacerse permanente sólo porque dos textos coocurrieron.

Una política razonable sería:

| Evidencia | Estado sugerido |
|---|---|
| Coocurrencia automática | `latent`, no recuperable como igualdad |
| Coincidencia morfológica transparente | `candidate`, baja o media confianza |
| Afirmación explícita del usuario | `explicit`, alta confianza |
| Confirmación repetida en contexto coherente | `consolidated` |
| Contradicción o corrección | `quarantined` o decremento de confianza |

## Qué debe construirse primero

### Fase A: unificar el cableado, sin cambiar la inteligencia

Antes de crear otra teoría de ranking, hay que hacer que MCP, CLI y dashboard llamen al mismo servicio de lectura y escritura. Ese servicio debe ser responsable de:

- resolver el `DB_PATH` efectivo;
- escribir memoria;
- consolidar memoria;
- actualizar sinónimos aprendidos;
- crear relaciones tipadas;
- invalidar y reconstruir índices derivados;
- registrar procedencia y eventos;
- ejecutar la recuperación híbrida común.

También hay que elegir `sinapsis` como fuente canónica del grafo. `asociaciones` puede conservarse como compatibilidad histórica, pero no debe actuar como segunda fuente mutable.

### Fase B: implementar el registro léxico aprendido

Añadir una tabla o vista autoritativa equivalente a:

```text
lexical_learning_episode(
    id,
    expression_norm,
    expression_surface,
    canonical_concept,
    relation_type,
    context_hash,
    source,
    provenance,
    confidence,
    confirmations,
    state,
    created_at,
    updated_at
)
```

El diseño final debe respetar el esquema existente y evitar duplicar sin necesidad la información que ya puede expresarse en `sinapsis`. La tabla episódica aporta la historia y la procedencia; `sinapsis` aporta la relación activa consumible por recuperación.

### Fase C: añadir un índice invertido de formas aprendidas

No es un embedding. Es un índice simbólico:

```text
forma normalizada → conceptos canónicos → episodios y evidencia
```

Debe soportar forma superficial, forma sin acentos, lema, plural, género, compuestos y expresiones multi-palabra. La expansión debe estar limitada por confianza y estado para evitar contaminar la recuperación con asociaciones débiles.

### Fase D: demostrar aprendizaje antes de evaluar generalización

El benchmark correcto no es pedirle al sistema que adivine una equivalencia nunca enseñada y luego llamar fallo a no adivinarla. El benchmark debe tener dos fases:

| Fase | Acción |
|---|---|
| Enseñanza | Se presenta explícitamente la relación entre una expresión nueva y un concepto conocido |
| Prueba | Se consulta usando una forma distinta, sin repetir el cue original |

El test clave sería:

```text
enseñar: «coeficientes multiplicativos de relevancia» = nodo scoring_pesos_bm25
consultar: «ajuste ponderado del ranking BM25»
```

El éxito demostraría que el sistema aprendió una relación y la reutilizó. No demostraría que resolvió cualquier abismo léxico no enseñado, pero sí probaría el mecanismo correcto de aprendizaje.

## Lo que no conviene hacer ahora

No conviene conectar todavía otro ranker genérico al motor de producción. EXP-N9 y EXP-N10 no produjeron una mejora suficiente.

No conviene usar Concept Hub como registro autoritativo de sinonimia. Un hub puede ser una estructura de navegación o agrupación, pero no debe representar automáticamente igualdad semántica.

No conviene fusionar automáticamente dos nodos porque compartan palabras, dimensiones o coocurrencias. Eso destruiría la distinción entre alias, relación temática y sinonimia.

No conviene evaluar sólo CE@K sobre un pool ya generado. Hay que reportar siempre por separado:

```text
Gold-in-pool
CE@K condicionado a Gold-in-pool
CE@K total
abstención
latencia
procedencia de la ruta
```

## Plan de implementación recomendado

| Orden | Trabajo | Resultado verificable |
|---:|---|---|
| 1 | Unificar servicio de lectura/escritura y `DB_PATH` | Dashboard, CLI y MCP consultan y actualizan la misma ruta |
| 2 | Elegir fuente canónica `sinapsis` y reconciliar asociaciones históricas | No quedan dos fuentes mutables divergentes |
| 3 | Implementar episodios de aprendizaje léxico | A=B queda almacenado con tipo, procedencia, confianza y reversibilidad |
| 4 | Crear índice simbólico de formas aprendidas | Una forma nueva recupera el concepto enseñado sin embedding |
| 5 | Integrar expansión aprendida antes del ranking | La relación aprendida puede generar candidatos, no sólo reordenarlos |
| 6 | Añadir pruebas de enseñanza, corrección y contradicción | El circuito es comprobable de extremo a extremo |
| 7 | Ejecutar benchmark congelado de aprendizaje | Se mide transferencia después de enseñar y no antes |
| 8 | Sólo entonces ajustar especificidad, rareza y ranking | El ranking optimiza una representación ya informativa |

## Veredicto

Sí hay un sistema valioso y novedoso en el repositorio. La auditoría no indica que haya que abandonar Concept Hub, WordNet, PPMI o el grafo. Indica que deben cambiar de posición dentro de la arquitectura.

La jerarquía recomendada es:

```text
aprendizaje explícito de significado
→ índice de formas aprendidas
→ conceptos canónicos y relaciones tipadas
→ expansión estructural y grafo
→ ranking
→ abstención
```

La contribución diferencial de MemoryBioRAG puede ser precisamente esta: **un sistema simbólico que aprende puentes léxicos episódicos a partir de experiencias explícitas, los consolida con procedencia y los reutiliza sin embeddings densos**.

Eso es más defendible que afirmar que un sistema puede descubrir cualquier sinonimia inédita sin señal previa. Para vencer el abismo léxico de forma científicamente sólida, primero hay que demostrar que el sistema puede aprender un puente nuevo y luego usarlo correctamente fuera del contexto exacto donde lo aprendió.

## Referencias internas

[1]: https://github.com/dennysjmarquez/MemoryBioRAG/tree/cuantificarelaporterealdeConceptHubyWordNet "Rama auditada del repositorio MemoryBioRAG"
[2]: https://github.com/dennysjmarquez/MemoryBioRAG/blob/cuantificarelaporterealdeConceptHubyWordNet/docs/fase5_rcil_zero_cue_audit.md "Auditoría zero-cue de RCIL"
[3]: https://github.com/dennysjmarquez/MemoryBioRAG/blob/cuantificarelaporterealdeConceptHubyWordNet/docs/fase5_out_of_family_benchmark_results.json "Benchmark fuera de familia"
[4]: https://github.com/dennysjmarquez/MemoryBioRAG/blob/cuantificarelaporterealdeConceptHubyWordNet/core/memory_store.py "Motor principal de memoria y recuperación"
[5]: https://github.com/dennysjmarquez/MemoryBioRAG/blob/cuantificarelaporterealdeConceptHubyWordNet/core/concept_hub.py "Implementación de Concept Hub"
