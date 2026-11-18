# Constitución del Proyecto MemoryBioRAG

> **Versión:** 1.0 | **Fecha:** 2026-09-16
> **Propósito:** Principios innegociables que rigen todo desarrollo en este proyecto.

---

## 0. La Actitud del Inventor (principio rector)

> **Nada es "imposible", solo "todavía no medido". Y si algo falla, se busca otro camino; no se rinde.**

Es la actitud con la que se trabaja en este proyecto, por encima de cualquier técnica. Dennys Marquez lo resume así: un inventor no dice "no se puede"; si lo hiciera, nada de lo que hoy existe existiría.

- **Prohibido cerrar una idea con "imposible" o "no se puede".** Lo honesto es decir qué falta: un dato, una medida, una pieza ("aguja") que todavía no existe.
- **Un intento fallido se revierte, la meta no.** El Pilar 1 sigue mandando: si un cambio baja una métrica, se revierte. Pero eso cierra *ese camino*, no el objetivo. Se anota por qué falló y se busca otro.
- **La ambición se apoya en evidencia.** No se discute la meta; se prueba cada paso con resultados verificables (Pilar 4).

## 1. Identidad del Proyecto

**MemoryBioRAG** es una arquitectura de memoria cognitiva biomimética y simbólica para agentes de IA.

- **Paradigma:** Python puro + SQLite FTS5. Cero embeddings densos, cero GPU, cero llamadas a APIs externas en el path de búsqueda.
- **Motor:** SQLite FTS5 WAL + Factorización PPMI-SVD (100 dims) + Espacio Semántico de 13 Ejes + Grafo Sináptico Hebbiano + Sparse Distributed Memory (SDM 2048-bit) + Calibración Conforme.
- **Idiomas:** Español + Inglés (stemming bilingüe ES/EN + expansión simbólica vía WordNet + Domain Dict automático).

- **Enfoque:** *un sistema con comportamiento vivo, que se adapta y evoluciona.* BioRAG ya mostró conductas que nadie le dictó: recuerdos que se agrupan solos en islas, que se duermen y despiertan, conexiones que nacen y se debilitan con el uso. Todo lo que se construya debe **fomentar** que esas conductas nazcan solas, de forma adaptativa y evolutiva, en vez de imponerlas a mano (Pilar 13).
- **Inclinación:** *"MemoryBioRAG se inclina hacia la inteligencia distribuida y asociativa, no hacia la inteligencia monolítica."* (Dennys Marquez, 2026-10-28). Criterio repartido en un motor rápido y neuronas pequeñas en puntos precisos; recuerdos que se hilan por asociación (ver Pilares 9–11 y la visión §0).

## 2. El Inverso Fundamental

> **BioRAG no piensa. El agente piensa.**

BioRAG es la **memoria externa** del agente — no su cognición. El trabajo cognitivo (entender la pregunta, diseñar la estrategia de búsqueda, interpretar los resultados) lo hace el agente. BioRAG aporta la memoria. El agente aporta la inteligencia.

**Consecuencia directa:** Cuando el usuario habla en lenguaje natural, el agente **no puede** reenviar las palabras literales a la memoria. Debe descomponer, reformular y traducir al vocabulario del dominio.

## 3. Pilares Inmutables

### Pilar 1: Cero Regresiones
- Antes de cualquier cambio, medir métricas baseline.
- Después del cambio, verificar que NINGUNA métrica empeoró.
- Si hay regresión: **REVERSIÓN INMEDIATA**. No se negocia.

### Pilar 2: Un Cambio a la Vez
- Nunca probar múltiples hipótesis o cambios simultáneamente.
- Aislar cada cambio, medir Antes vs Después, registrar métricas exactas.
- Si cualquier métrica regresa: revertir inmediatamente.

### Pilar 3: Fallos Visibles
- Datos faltantes, tokens no indexados, discrepancias de DB deben fallar de forma visible (excepciones, logs descriptivos).
- **NUNCA** devolver defaults silenciosos (como `0.0`, arrays vacíos, o fallback null) que puedan confundirse con resultados válidos.

### Pilar 4: Sin Prosas sin Resultados Concretos
- Nunca reportar números asumidos, simulados o esperados como hechos verificados.
- Cada afirmación de éxito, mejora o regresión debe probarse con outputs de comandos verbatim (diffs, resúmenes de benchmark, corridas de pytest).

### Pilar 5: Verificación Dual
- Verificar contra el snapshot congelado **NO** es suficiente.
- **Dual Verification:** Snapshot (regresión matemática) + Copia de DB activa (resolución en mundo real).
- Si un fix pasa en el snapshot pero falla en la copia activa: **NO está resuelto**.

### Pilar 6: Diseño Universal UX-First
- Antes de construir, justificar: ¿Quién lo usa? ¿Existe otra ruta natural? ¿Vale la pena el peso técnico?
- **PROHIBICIÓN ESTRICTA:** Nunca hardcodear vocabularios de dominio, diccionarios o términos internos del proyecto en el motor. El sistema debe permanecer 100% agnóstico al dominio.

### Pilar 7: Validación Fail-Fast
- Toda validación de parámetros ocurre ANTES de escribir en la base de datos.
- Si un parámetro es inválido, retornar error accionable INMEDIATAMENTE.
- Nunca dejar estado parcial en la DB.

### Pilar 8: Sin Features Fantasma
- Campos opcionales sin consecuencias reales se convierten en campos fantasma (97% de nodos sin bridges lo demuestran).
- Si un campo es importante, debe ser obligatorio o tener nudge visible que fuerce su uso.

### Pilar 9: Modular, Desacoplado y Hexagonal (regla de oro)
> *"Si dañas una cosa, se daña todo lo demás cuando hay harto acoplamiento."* — Dennys Marquez
- **Nada monolítico.** Cada pieza (capa del motor, neurona, validador, adaptador de idioma) vive en su propio módulo, con una responsabilidad clara.
- **Evitar el acoplamiento.** Una pieza se comunica con otra por una interfaz pequeña y explícita, nunca leyendo su interior. Quitar o cambiar una pieza no debe romper las demás.
- **Mentalidad hexagonal:** la lógica del cerebro (el dominio) en el centro; la base de datos, el MCP, los diccionarios, los idiomas y las neuronas, como **puertos y adaptadores** enchufables. Un adaptador se desconecta sin tocar el centro.
- Si se encuentra código acoplado o monolítico, se anota y se desacopla en un cambio propio, medido como cualquier otro (Pilar 1 y Pilar 2).

### Pilar 10: Todo Documentado: Por Qué se Creó, Por Qué Ahí, Por Qué se Quitó (regla de oro)
- Cada pieza nueva lleva escrito **qué problema resuelve, por qué en ese punto** del sistema y **con qué medida se aprobó**.
- Cada pieza que se quita o se apaga lleva escrito **por qué se quitó**, con la evidencia, para que nadie la reinvente sin saberlo.
- Escrito para que lo entienda **cualquier humano sin mucho conocimiento técnico y cualquier IA futura**. Lenguaje simple; el detalle técnico, aparte.
- El conocimiento no puede quedar solo en la cabeza de alguien ni en una sesión de chat: si no está en el repo, se pierde.

### Pilar 11: Toda Neurona con Piso, Techo y Guardianes
- Ninguna neurona entra al motor sin: **piso** (la fórmula a mano sigue siendo el mínimo garantizado), **techo** (cuánto puede mover como máximo), **guardianes** (comprobaciones que la apagan si algo no cuadra) y **examen propio**.
- Funciona con la base vacía, en tiempo constante, y solo **suma** encima del ranking; nunca lo reemplaza.
- El modelo es la primera neurona del motor: cualquier neurona nueva se construye y calibra igual.

### Pilar 12: El Ruido Útil No se Mata (regla de oro)
> *"Si quitamos el ruido, nos quedamos con un sistema ciego, típico, normal y común como cualquier buscador. Y esto no lo es."* — Dennys Marquez (2026-10-29)

**La regla:**
- **Las neuronas (re-ranking, razonamiento) solo ORDENAN.** Nunca quitan, filtran ni vacían la lista.
- **Ningún cambio** del motor ni del MCP puede dejar al agente sin los recuerdos parecidos o relacionados que acompañan al mejor, aunque suba una métrica de una sola consulta. Si un cambio recorta la lista, tiene que demostrar con medición que **no se pierden las pistas** (además del Pilar 1).
- **Un "no sé" no vacía la lista.** Si el cerebro no está seguro, **lo dice** (`nivel_certeza`, aviso de brecha) y **sigue mostrando lo parecido**. No lo esconde.
- El orden importa: lo que mejor encaja va arriba (la brújula es el top-1 / top-5); el ruido útil va debajo, a la vista, pero sin tapar al bueno.

**Por qué:**
- **BioRAG no es un buscador; es un cerebro.** El agente y el cerebro forman **una sola mente**: el agente intenta recordar, el cerebro le "tira" lo parecido, y lo parecido trae **palabras pista** con las que el agente vuelve a buscar ("gatito" → "gato" → el recuerdo). Así recuerda una persona: casi nunca a la primera; va tirando del hilo hasta dar con el recuerdo, porque el recuerdo está ahí.
- **Ese ruido ES el hilo.** En el ejercicio n.º 2 (visión §2u), el recuerdo buscado llegó gracias a un vecino que no era la respuesta: fue la pista. Sin ese "ruido", el agente no lo habría encontrado.
- **La completación de patrones** (traer lo incompleto y lo cercano) es la capacidad más poderosa del sistema, y nace justamente de lo que parece ruido. Un filtro que solo deja "lo exacto" la apaga.
- **Si se mata el ruido:** sube un número en una prueba de una sola consulta, pero el sistema queda **ciego**: solo encuentra lo que ya se sabe nombrar. Eso es un buscador común, y eso destruye el proyecto.

**Cómo se aplica (sin romper lo demás):**
- Proteger el ruido útil **no** significa tapar la respuesta con basura: los falsos positivos siguen midiéndose (FP 0/40) y el mejor recuerdo debe estar arriba. Se resuelve **ordenando y diciendo qué tan cerca está cada cosa**, no borrando.
- Todo filtro existente que hoy recorte la lista (por ejemplo, el filtro de cobertura de palabras, QCR; visión §2u, ejercicio n.º 3) se registra y se conversa con Dennys antes de tocarlo, con medición de pistas conservadas. El OK es siempre suyo.
- Detalle y ejemplos: `docs/Mi neurona en el sistema/vision_como_recuerda_biorag/README.md` (P10, P11 y §2u).

### Pilar 13: Un Sistema Vivo: Fomentar lo que Nace Solo (enfoque rector)
> *"Ya demostró síntomas de ser un sistema vivo. Eso nadie lo programó, ni siquiera una neurona. Hay que cablear y dejar que ese tipo de conductas nazcan de forma natural, adaptativa, evolutiva."* — Dennys Marquez (2026-10-29)

**El enfoque:** BioRAG se construye como un **organismo**, no como una máquina de reglas. Se pone algo en su sitio y se deja que todo lo que lo rodea (el uso, el agente, el sueño, el tiempo) influya y construya lo demás. El objetivo es un sistema vivo, natural y completo, que **se adapta y evoluciona**.

**La evidencia de que ya pasa (medida, no supuesta):**
- **Islas de recuerdos.** El código solo trae un detector genérico de grupos (LPA, v16.0). **Qué islas se forman, cuántas y con qué recuerdos nadie lo escribió:** salió del uso. Aparecieron solas, se parecían a lo que hace una base vectorial y, cuando la memoria creció, **se apagaron solas** por saturación del grafo. Las islas por significado siguen sanas (125 en la viva). Detalle: `docs/Mi neurona en el sistema/islas_de_recuerdos/README.md`.
- **Sueño y despertar.** Recuerdos que se duermen por desuso (162 de 1.357) y despiertan al recordarlos (visión §2u, ejercicio 3).
- **Conexiones que nacen del uso** (hebbianas, de co-ocurrencia, del sueño) y se debilitan si no se usan.

**Reglas para fomentarlo (aplican a todo cambio):**
1. **Reglas locales simples antes que órdenes globales.** Se prefieren mecanismos pequeños que actúan "en el vecindario" (reforzar lo que se usa junto, debilitar lo que no se usa, consolidar de noche) y de los que el orden **emerge**. No se imponen listas, taxonomías ni categorías escritas a mano para cada base (Política A: no inventar ejes).
2. **Dejar espacio para crecer.** Catálogos abiertos (dimensiones de mundo abierto), estructuras que se crean solas. Lo que el sistema crea tiene que ser **legible** para humanos y agentes, y no hacerse pasar por algo "de fábrica" (lección del 2026-10-07: prefijo `tema_`).
3. **Homeostasis: que lo vivo no se ahogue al crecer.** Todo mecanismo emergente necesita su equilibrio (poda, escalado, umbrales relativos al tamaño de la memoria) para seguir funcionando con 10 veces más recuerdos. Las islas del sueño murieron justo por falta de esto.
4. **Nacer de los datos, en cualquier base.** Lo que emerge tiene que salir del propio uso de cada memoria, desde la base vacía, sin sembrarlo a mano. Así da el mismo comportamiento en cualquier base.
5. **Observar antes de usar, y nunca borrar por no entender** (visión P12 y §2w). Lo que nace solo se mide y se documenta. Recién entonces se decide si se usa, se mejora o se deja.
6. **Primero para asociar, después para ordenar.** Una señal emergente entra primero como pista o asociación (Pilar 12). Al ranking solo entra con medición y el OK de Dennys (Pilares 1 y 11). Las islas ya enseñaron esto: sanas para asociar, negativas para reordenar (agosto de 2026).

**La pregunta obligatoria antes de cada cambio:** *¿esto deja que el comportamiento nazca solo, o lo impone a mano? ¿Y sigue vivo cuando la memoria crezca 10 veces?*

**Límites (para que lo vivo no rompa lo demás):** fomentar la emergencia **no** suspende los otros pilares. Cero regresiones (1), un cambio a la vez (2), modular y hexagonal (9), documentado (10) y neuronas con piso, techo y guardianes (11) siguen mandando. Lo vivo se cultiva con medición, no con fe.

## 4. Stack Técnico

| Componente | Tecnología |
|---|---|
| Lenguaje | Python 3.x puro |
| Base de datos | SQLite 3 + FTS5 (WAL mode) |
| Motor semántico | PPMI + SVD (100 dims) + Retrofitting Hebbiano |
| Grafo | Sinapsis Hebbianas (tabla `sinapsis`) |
| Memoria hiperdimensional | SDM 2048-bit (Kanerva 1988) |
| Calibración | Conforme (Vovk 2005, α=0.10) |
| Servidor | MCP (Model Context Protocol) via FastAPI/Stdio |
| Tests | pytest |
| Snapshot congelado | `snapshots/qa_escape_qcr_20260811.db` |

## 5. Comandos de Verificación (Obligatorios antes de cualquier release)

```bash
# 1. Suite de tests unitarios
python3 -m pytest tests/ -v

# 2. Benchmark QA completo (921 casos, snapshot congelado)
BIORAG_PATH=snapshots/qa_escape_qcr_20260811.db python3 scripts/evaluar_qa.py

# 3. Abismo Léxico (cero solapamiento léxico)
BIORAG_PATH=snapshots/qa_escape_qcr_20260811.db python3 scripts/test_abismo_lexico.py

# 4. Fuzzing adversarial (33 casos)
python3 scripts/fuzz_qa.py

# 5. Concurrencia (20 hilos + 20 clientes HTTP)
python3 scripts/concurrencia_qa.py
```

## 6. Métricas Oficiales de Referencia (v31.3)

| Métrica | Valor | Gate |
|---|---|---|
| Recall@5 Global | 98.06% | ≥ 97.0% |
| Recall@1 (Top-1) | 90.74% | ≥ 88.0% |
| MRR | 0.9355 | ≥ 0.90 |
| Tasa de FP | 0.0% (0/40) | = 0.0% |
| Tests Unitarios | 168/168 PASSED | 100% |

## 7. Flujo de Desarrollo Obligatorio

1. **Leer** AGENTS.md y esta constitución antes de tocar código.
2. **Medir** baseline: `pytest tests/ -v` + `evaluar_qa.py` + `test_abismo_lexico.py`.
3. **Planear** el cambio (spec → plan → tasks).
4. **Implementar** un cambio a la vez.
5. **Verificar** post-cambio: mismos comandos que el paso 2.
6. **Comparar** métricas Antes vs Después.
7. **Si hay regresión:** revertir inmediatamente.
8. **Si no hay regresión:** documentar el cambio con evidencia concreta.

## 8. Fuera de Alcance Permanente

- Dependencias de hardware pesado (GPU, TPU).
- Llamadas a APIs externas en el path de búsqueda.
- Hardcoding de vocabularios de dominio.
- Modificación de pesos BM25 sin verificación completa de regresión.
- Campos opcionales sin consecuencias (anti-patrón "campo fantasma").
