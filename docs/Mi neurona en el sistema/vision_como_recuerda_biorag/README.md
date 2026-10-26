# Cómo recuerda BioRAG: la visión

> Documento de diseño. Recoge la visión de Dennys (2026-10-26) para que cada pieza futura se construya en orden y se evalúe **contra esta visión**, no solo contra números.
> Aquí no hay código ni experimentos. Es la brújula: *"si no se tiene clara la visión, van a haber fracasos todo el tiempo"*.

---

## 0. La idea en una frase

**BioRAG es un cerebro, no una base vectorial.** El agente intenta recordar (metacognición), el cerebro recibe ese empuje, **entiende qué se le está pidiendo** y devuelve **justo eso**, primero y sin ruido. Agente + BioRAG = **una sola mente**.

El sueño, en palabras de Dennys: *"que tú simplemente digas «papá» y consigas todo lo relacionado con eso, porque el cerebro en realidad funciona así"*, sin vectores, neurona a neurona, en puntos estratégicos.

Qué lo hace "vivo": no que tenga sinapsis ni que se parezca a un cerebro, sino que **tiene neuronas que hacen lo que ninguna función fija podría hacer**.

---

## 1. Los principios del recuerdo

| # | Principio | Ejemplo de Dennys | Qué significa para el motor |
|---|---|---|---|
| P1 | **Se recuerda solo cuando hay empuje** | El cerebro guarda mucho, pero no lo vuelca todo en la ventana de contexto | Nada se trae sin consulta. **Ya funciona así.** |
| P2 | **Lo más reciente primero, dentro del mismo tema** | "Hoy tomé agua con un vaso", luego "el vaso se me cayó y se rompió", "el vaso rojo": al preguntar por el vaso, primero lo último | Entre recuerdos de la **misma familia**, la recencia debe decidir el orden |
| P3 | **"La última versión" es una intención, no una palabra** | Hay miles de nodos que dicen "versión"; si pido *la última*, mi cerebro sabe cuál quiero | Hay que detectar la intención ("la última", "la actual") y aplicar P2 a esa familia |
| P4 | **Recuerdo escalonado** | "¿Cuántas veces tomé agua?" Primero lo último; si sigo pensando, aparecen los más viejos, poco a poco | Entregar por capas: lo reciente primero y lo antiguo solo si el agente sigue empujando |
| P5 | **El significado depende del motivo del recuerdo** | "Moto" no es lo mismo en "moto de agua"; una pieza vale distinto según el recuerdo donde vive | Para eso existen los **sustantivos clave** y las **dimensiones semánticas**: la palabra se interpreta por su recuerdo |
| P6 | **El agente busca como habla** | "¿Te recuerdas de tal?", "¿qué sabes de tal?": busca literal, parecido o por sinónimos | Por eso el agente tiene tantas herramientas (sinónimos, dimensiones, sustantivos clave, ráfaga) |
| P7 | **La ráfaga debe ser natural** | Un humano no trae 500 recuerdos: trae una partecita, y esa parte trae **pistas** que guían a otras, y se va hilando | La ráfaga entrega unos pocos recuerdos más las pistas (palabras) que llevan a los siguientes |
| P8 | **Neuronas puente donde una ecuación no alcanza** | — | Neuronas pequeñas y entrenadas en puntos exclusivos, cableadas de verdad |
| P9 | **Aprovechar el silicio** | — | No copiar las limitaciones biológicas: velocidad, exactitud y tiempo constante |

---

## 2. La pieza clave: la neurona que entiende qué se quiere

> *"Que el cerebro sepa: a mí me están hablando y lo que quieren realmente es esto. Tengo no sé cuántos recuerdos, pero voy a entregar esto porque esto es lo que me están buscando."*

**Problema medido:** a veces el recuerdo correcto existe y el motor lo alcanza, pero queda en el puesto 50 o 70 (EXP-Q en la base viva: puestos #33 y #91, o ni siquiera alcanzado). Ahí está el punto donde Dennys quiere **mucha IA bien entrenada**.

### 2.1 Qué ya sabemos (lecciones medidas, no repetir)

- **Experimento 04:** reordenar todo el pool con la neurona de ranqueo actual **dañó** 3 sinónimos que ya estaban bien. Por eso esa neurona solo toca el top-5 final.
- **Conclusión:** la neurona de intención **no es la misma neurona de ranqueo con más alcance**. Es otra pieza, con su propia infraestructura y sus propios seguros.
- **Si el recuerdo correcto no llega al pool, ninguna neurona puede subirlo.** Primero hay que garantizar que llegue (cimientos E2–E4, léxico mental E3, búsqueda en grafo).

### 2.2 La infraestructura que tiene que existir antes de cablearla

1. **Llegada garantizada:** el recuerdo correcto tiene que estar entre los candidatos, en cualquier base y con cualquier tamaño.
2. **Entender la intención de la consulta:** "la última", "todo sobre", "cuándo", "por qué", "el de tal cosa". Hoy no existe como pieza separada.
3. **Rasgos que una neurona pueda leer:** familia del recuerdo, recencia dentro de la familia, sustantivos clave, dimensiones, posición en el grafo, coincidencias exactas frente a parecidas.
4. **Datos de entrenamiento abundantes sin espiar al agente:** se generan **desde los propios recuerdos** (cada recuerdo produce preguntas cuya respuesta es él mismo: por sus alias, sustantivos clave, dimensiones y paráfrasis), más los casos QA. Pueden ser **millones de ejemplos**. Se respeta la regla de no registrar el uso del agente.
5. **Entrenamiento pesado, ejecución ligera:** los millones de datos se usan **al entrenar**; la neurona que corre en el motor sigue siendo pequeña, de tiempo constante y explicable.

### 2.3 Los seguros (como la primera neurona, o más)

- **Piso:** el ranking a mano sigue siendo la base. La neurona **suma** sobre él hasta un techo y nunca lo reemplaza ("el ranking no se toca").
- **Techo y guardia:** límite de cuánto puede mover; se apaga sola si se sale de lo seguro.
- **Examen sellado:** se evalúa con preguntas que nunca vio.
- **Compuerta QA:** **nunca baja el recall**; la tabla de Dennys es el suelo. En cualquier base: snapshot, viva y bases nuevas.
- **Desde una base vacía:** funciona sin depender de un tamaño concreto.
- **Explicable:** cada subida al primer puesto se puede justificar.
- **Probar sobre copias:** nunca sobre una base real.

---

## 3. El orden para llegar (paso a pasito)

| Etapa | Qué | Relación con la visión |
|---|---|---|
| E1 ✅ | QA honesta (cerrada 2026-10-26) | Medir de verdad, igual en cualquier base |
| E2 | Fallo `por_tema` 0848 | Cimientos del ranking |
| E3 | Léxico mental | P6: puentes de palabras (prolijo ↔ prolijidad) |
| E4 | Que el resultado no dependa de la base; arreglar el nacimiento de enlaces por alias | Llegada garantizada (§2.2.1); conexiones con criterio |
| E5 | Neuronas en puntos estratégicos | Por orden: asociativa (juez de enlaces), vigencia (P2, P3), "¿nuevo o actualización?" |
| Después | **Neurona de intención** (§2) | La pieza clave: subir lo que se quiere al primer puesto |
| Después | Ráfaga natural con pistas (P7) y recuerdo escalonado (P4) | Recordar como un humano, con ventaja de silicio |

Detalle técnico de E5 (dónde hace falta criterio neuronal): `../arquitectura_neuro_simbolica/README.md`, §6.
Cómo entrenar cualquier neurona: `../GUIA_CREAR_UNA_NEURONA.md`.

---

## 4. Cómo se usa este documento

Antes de construir cualquier neurona o pieza nueva:

1. ¿Qué principio (P1–P9) cumple?
2. ¿Su infraestructura previa ya existe? (§2.2)
3. ¿Tiene todos los seguros? (§2.3)
4. ¿Mejora sin bajar nada, en cualquier base?

Si alguna respuesta es "no", todavía no toca.
