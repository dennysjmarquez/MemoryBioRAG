# Experimento 18 — La neurona en el sueño: las sinapsis nacen a prueba y se consolidan por evidencia

**Protocolo fijado y subido ANTES de medir** (2026-11-25, rama `arena/da3df5df-memorybiorag`).
- Ningún umbral de este archivo se cambia después de ver resultados.
- Si hiciera falta cambiar algo, se escribe un protocolo nuevo con fecha, y lo medido con este queda tal cual.
- La verificación previa está en `INFORME_VERIFICACION.md`.

## 0. La idea en una frase

**La inteligencia no va en el nacimiento, va en la consolidación.**

Como en el cerebro:
1. Las sinapsis **nacen como hoy**: el motor propone, no se corta nada al nacer y el recall queda intacto
   (exp. 13).
2. Nacen **a prueba**, con fecha.
3. En cada **sueño**, una neurona pequeña y cerrada decide cuáles **se consolidan**, cuáles **se debilitan** y
   cuáles pasan a **cuarentena** (reversible).
4. Para decidir usa evidencia que se acumula con el tiempo, no una foto del momento del nacimiento.

| Cerebro (fuentes en la biología §2) | BioRAG en este diseño |
|---|---|
| Nace mucho, débil y a prueba (espinas transitorias; sinapsis silenciosas) | nace como hoy, con estado `a_prueba` y fecha |
| Se estabiliza lo que se **reactiva**: en el sueño se repite lo marcado en la vigilia (Yang y col., 2024) | **repaso interno** en el sueño: el motor se pregunta a sí mismo por K recuerdos tocados desde el último sueño, en silencio y sin observar al agente |
| Cuenta el **patrón**, no la magnitud | lo que cuenta es haber sido capturada en **varios** sueños distintos, no un solo pico |
| Las vecinas coordinadas se protegen (Niculescu, 2018) | competencia **dentro del nodo**: se compara con sus hermanas, no con un umbral absoluto |
| Etiqueta + ventana + tercer factor (Frey y Morris; Gerstner) | ventana de N sueños; consolidar exige ≥ 2 de 3 evidencias |
| Homeostasis por neurona (Turrigiano) | presupuesto de peso automático por nodo; se escala sin cambiar el orden |
| Poda marcada con «no me comas» (complemento; CD47) | cuarentena reversible; `manual` es «no me comas» permanente |

## 1. Límites (decisiones de Dennys vigentes)

| Norma | Cómo se cumple aquí |
|---|---|
| Norma Máxima (invariancia) | Todas las entradas de la neurona son **del par** (sus dos textos), del **repaso con la búsqueda real** (que debe ser invariante por la propia norma) o de **su propio nodo**. Ninguna frecuencia del corpus. Se prueba en E0 y E2 |
| Norma 4 / U0 (sin feedback, sin registrar uso, sin telemetría, sin señal nueva por sinapsis) | No se lee `log_busquedas`, `feedback`, `ultimo_uso` ni el canal 2. La coactivación sale **solo** del repaso interno. El estado `a_prueba` es de ciclo de vida, no de uso, **pero agrega una columna**: requiere OK (§7) |
| Decisión 3 (sin DB viva, privada ni snapshot; `manual` no es etiqueta) | E0–E2 solo con datos escritos o generados para el experimento. El examen real (E3) queda **bloqueado** |
| Neurona cerrada; F1–F6 no autorizados; no implementar en el motor sin OK; E3 del plan anterior abierto | Este experimento **no modifica el motor ni los tests**. E0–E2 son scripts de laboratorio en esta carpeta |
| Multilingüe: sin listas de palabras ni `\w{4,}` | Las agujas trabajan sobre **caracteres Unicode** por categoría (letra/número frente al resto), sin tokenizador ni listas. El mismo código para todos los idiomas |
| Nunca borrar; `manual` intocable; recall nunca baja; ranking intacto | cuarentena reversible; `manual` excluido de toda decisión; nada ocurre en `recordar` |
| Tiempo constante | K nodos por sueño; cada aguja es O(largo de los dos textos) |
| Desde una DB vacía | sin evidencia, todo queda a prueba y nada se poda |

## 2. Entradas de la neurona (todas sin idioma)

| Entrada | Qué mide | ¿Depende del corpus? |
|---|---|---|
| **N1. n-gramas de caracteres** | Jaccard entre los conjuntos de bigramas y trigramas de caracteres de los dos textos, tras normalizar | No: solo los dos textos |
| **N2. compresión (NCD)** | cuánto comprime el texto de A cuando ya se vio el de B: `1 − NCD` con zlib, simétrica | No: solo los dos textos |
| **R. coactivación por repaso** | en cuántos sueños distintos A y B se activaron juntos en el repaso interno | No por frecuencias, pero sí por la búsqueda real. Hereda su invariancia |
| **K. competencia en el nodo** | posición del par entre las sinapsis automáticas de A y de B | Solo del nodo |
| **V. vías de nacimiento** | cuántas vías distintas (B1–B12) propusieron el par | Del nacimiento. Por el exp. 16 se sabe que **no** es invariante: entra solo como desempate y se audita en E2 |

**Normalización común (N1, N2):**
1. NFKC + casefold.
2. Cada carácter que no sea letra ni número (categoría Unicode `L*`/`N*`) pasa a un espacio.
3. Los espacios se colapsan.

Es puramente estructural: sirve igual para el español, el inglés, el chino y el japonés.

## 3. Etapas

| Etapa | Qué | Estado |
|---|---|---|
| **E0** | ¿Las agujas N1 y N2 funcionan **igual en cuatro idiomas** y son invariantes por construcción? | **Autorizada ahora**: es laboratorio puro, sin motor ni DB |
| E1 | ¿El repaso interno es **invariante** (D frente a D∪I) y reproducible, con la búsqueda real sobre bases sintéticas en `/tmp`? | Requiere OK de Dennys para C1 |
| E2 | Simulación del ciclo de vida (nacer → a prueba → sueños → consolidar o cuarentena) en mundos sintéticos **sin filtración léxica** y en cuatro idiomas | Requiere el OK de E1 |
| E3 | Examen real muestreado al azar (no por la fuerza de la neurona) | **Bloqueada** por la decisión 3 |
| E4 | Motor: modo aprendiz (solo anota estados), luego relevo | **Bloqueada**. Requiere el OK explícito de Dennys |

## 4. E0 — las agujas del par en cuatro idiomas (fijado antes de medir)

**Corpus (`mundos_espejo.py`):**
- 8 temas × 3 recuerdos, escritos **a mano** en español, inglés, chino y japonés, con el mismo contenido.
- Los tres recuerdos de un tema tratan **facetas distintas** y comparten pocas palabras, a propósito: así se
  evita la filtración léxica del exp. 16.
- Más 3 pares **puente**: rasgo compartido entre temas distintos, como «rojo». Se reportan aparte y no cuentan
  para los criterios.
- `I`: 8 recuerdos irrelevantes de otro dominio, en los cuatro idiomas, para la prueba de invariancia.

**Pares:**
- 24 recuerdos dan 276 pares por idioma.
- Positivos: los 24 pares del mismo tema.
- Negativos: los pares de temas distintos que no son puente (249).

**Agujas medidas:**
- N1 y N2.
- **Referencia, sin criterio:** Jaccard de tokens `\w{4,}`, que es lo que usa hoy el motor en B6/B7. Sirve para
  ver cuánto falla en chino y japonés.

**Criterios (por aguja). Pasa E0 solo si cumple todos:**

| # | Criterio | Umbral |
|---|---|---|
| C0.1 | AUC (positivos frente a negativos) en **cada** idioma | ≥ 0,70 |
| C0.2 | Diferencia entre la mayor y la menor AUC de los cuatro idiomas | ≤ 0,10 |
| C0.3 | Spearman de las 276 puntuaciones del español frente a cada uno de los otros tres idiomas | ≥ 0,50 en los tres |
| C0.4 | Invariancia: la puntuación de cada par en D es **idéntica, bit a bit,** a la de D∪I | 276/276 en cada idioma |
| C0.5 | Reproducibilidad: dos corridas dan resultados idénticos | idéntico |

**Lectura fijada antes:**
- Una aguja que pasa queda como **entrada candidata** para E2.
- Una aguja que no pasa **no se usa como entrada**. Se documenta el motivo y no se ajusta para que pase.
- Con 24 positivos, el error estándar de la AUC ronda ±0,05. E0 es **una prueba de humo** de la condición
  necesaria (que la aguja funcione igual en cualquier idioma). **No prueba que la aguja sea valiosa en
  datos reales.**

**Predicción escrita antes de medir [D]:**
- N1 pasa en español e inglés y es dudosa en chino y japonés.
- N2 queda por debajo de N1, porque los textos son cortos.
- La referencia `\w{4,}` se hunde en chino y japonés.

## 5. La neurona (para E2, fijado ahora y sin entrenar)

1. **Piso a mano:** la regla «≥ 2 de 3» de la biología §4. Las tres evidencias son:
   - (a) N1 ≥ el percentil 75 de los pares a prueba **de su propio nodo**, sin umbral global;
   - (b) coactivación en el repaso en ≥ 2 sueños distintos;
   - (c) gana la competencia del nodo: queda entre las 5 automáticas más fuertes de A o de B.
2. **Red pequeña encima:** un MLP de 1 capa oculta, de 8 unidades, sobre las entradas de §2.
   - Etiquetas solo sintéticas, con la verdad por construcción.
   - El **20 % por tema** queda sellado y nunca se estudia.
   - Campeón, guardia y techo, como en las demás neuronas.
   - **Nunca queda por debajo del piso.**
3. **Salidas:** `consolidar` · `seguir a prueba` · `debilitar` · `cuarentena` (reversible).
   - Nunca toca `manual`.
   - Nunca deja un nodo con menos de 5 pistas (Pilar 12).
   - Tiene un tope de cambios por sueño.

## 6. Criterios de E2 (fijados ahora; se miden solo si se autoriza)

| # | Criterio | Umbral |
|---|---|---|
| C2.1 | Precisión de las consolidadas (fracción que une recuerdos relacionados) | ≥ piso + 0,15 y ≥ 0,50 (hoy: 0,11–0,18, exp. 16) |
| C2.2 | Recall de las relacionadas que nacieron: no pasan a cuarentena | ≥ 0,90 |
| C2.3 | **Aporte único:** relacionadas consolidadas que el canal 1 **no** trae solo (fuera del top-5 de las consultas del propio recuerdo) | > 0 y ≥ las del piso |
| C2.4 | Invariancia D frente a D∪I: el estado final de los pares de D es igual | ≥ 98 % idéntico; el resto explicado |
| C2.5 | Orden de guardado: estado final con otro orden | ≥ 95 % idéntico (hoy cambia el 73–78 % de las puntuaciones) |
| C2.6 | Cuatro idiomas: |C2.1(idioma) − C2.1(español)| | ≤ 0,05 en los tres |
| C2.7 | `manual` | 0 cambios |
| C2.8 | QA y recall | idénticos |

## 7. Lo que necesita decidir Dennys (nada de esto se hace sin su OK)

1. **C1:** ¿la coactivación sale del repaso interno (sin telemetría, recomendado) o del uso real
   (`log_busquedas`, que requiere una excepción a U0 y a la norma 4)?
2. Una **columna nueva** de estado (`a_prueba` / `consolidada` + fecha) en `sinapsis`. No es una señal de uso,
   pero es una señal nueva por sinapsis. ¿Entra en U0 o no?
3. **E3:** ¿se autoriza algún examen con datos reales, y cuál? Por ejemplo, una copia con revisión humana de
   pares muestreados al azar.
4. **Neurona «de fábrica» o aprendizaje por memoria:** se recomienda empezar con la de fábrica, congelada y
   versionada.
