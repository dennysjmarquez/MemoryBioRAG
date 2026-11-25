# Experimento 18 — Decisiones por consenso (13 opiniones), contrastadas con el código y con E0

**Fecha:** 2026-11-25 · **Base:** `590c2da`

## 0. Lo que quiere Dennys (con sus palabras)

> «Se quiere hacer lo que hace la hormiguita: le das un nodo y los que están enlazados, y dices "esto tiene que
> ver con esto", "no", y lo corta, porque por detrás se hacen sinapsis malas. Se quiere corregir eso con una
> neurona hiperentrenada, que no memorice sino que aprenda. Y llevar este sistema al siguiente nivel, que ningún
> otro lo tenga.»

Traducido a especificación:
- **Entrada:** un nodo y sus sinapsis automáticas.
- **Salida:** para cada sinapsis, `consolidar` · `seguir a prueba` · `debilitar` · `cuarentena` (reversible).
- **Quién decide:** una neurona pequeña que **generaliza**: se evalúa en temas que nunca vio.
- **Sin** Gemini, APIs ni embeddings.

## 1. Regla con la que se resolvió el consenso

Se **adopta** lo que cumple las tres condiciones:
1. tiene consenso, o una mayoría clara sin objeciones de fondo;
2. es compatible con las normas vigentes de Dennys;
3. no quedó refutado por una medición.

Lo que choca con una norma de Dennys **no se adopta**: queda en §4 para su palabra, con una recomendación.

Las opiniones 1 (Gemini 4) y 5 (DeepSeek) son **el mismo texto**: cuentan como una sola opinión.

## 2. Tabla de consenso

| Tema | Postura | Quiénes | Veredicto |
|---|---|---|---|
| Ciclo A | no ejecutarlo | las 13 | ✅ **Adoptado** (ya estaba descartado) |
| Dónde va la inteligencia | en la **consolidación en el sueño**, no en el nacimiento | las 13 | ✅ **Adoptado** |
| Nacimiento | nace como hoy, pero **débil y a prueba**, con fecha y ventana protegida; no se corta al nacer | las 13 (Claude: «no cortar al nacer») | ✅ **Adoptado** como diseño. En el motor necesita el OK de §4.3 |
| Piso mecánico primero | regla fija «≥ 2 de 3»; el MLP solo entra si **supera de forma medible** al piso; si no, se queda el piso | Gemini 4, Claude, Kimi, Google, Gemini-argon, Qwen, Manus, ChatGPT | ✅ **Adoptado** |
| Modo sombra | primero anota qué haría, sin cambiar pesos | Kimi, ChatGPT, Manus | ✅ **Adoptado** (ya estaba como «modo aprendiz» en la biología §5) |
| Una pieza a la vez | etapas pequeñas, cada una con criterio fijado antes | Claude, Manus, ChatGPT, Kimi | ✅ **Adoptado** |
| Contar episodios, no repeticiones | la evidencia se cuenta por episodio distinto (días, sesiones o sueños), no por cuántas veces salió | ChatGPT, Manus, GPT-luna, Kimi | ✅ **Adoptado:** se cuentan sueños distintos |
| Medir falsos positivos | la precisión de lo consolidado pesa tanto como el recall | mimo | ✅ **Adoptado** |
| **Co-salida en un resultado = señal para consolidar** | **sí**, es actividad del motor | Qwen, Google, Gemini 4 (como «U2 interna»), Gemini-argon (**solo si es resonancia independiente**) | ⚠️ **Minoría**, y **refutada en su forma bruta por el código**: el ranking lee las sinapsis (`AUDITORIA_RANKING_LEE_SINAPSIS.md`), así que la co-salida bruta forma el bucle |
| | **no**: es exposición, a lo sumo candidata; nunca consolida sola | ChatGPT, Claude, Kimi, GPT-luna, Manus, mimo, Grok | ✅ **Adoptado** |
| Coactivación válida | solo si A y B se activan **por vías que no leen la sinapsis** que se juzga | Gemini-argon; Claude («demostrar que no genera el bucle») | ✅ **Adoptado:** repaso en el sueño con `ignorar_sinapsis` |
| **Registrar el «uso real» del agente** (`co_used`, citado o seguido) | hace falta para consolidar | ChatGPT, GPT-luna, Manus, mimo, Kimi, Claude, Grok | ⛔ **Choca con la norma 4** («sin feedback, sin registrar qué usó, sin trabajo extra para el agente»). Además hay evidencia de que no funciona: `log_busquedas.util` quedó **vacía, 0 de 2157 filas**, cuando dependía del agente (`core/feedback_implicito.py`). → §4.1 |
| **Examen real ocultando `manual`** | obligatorio | Gemini 4, Kimi, Claude, mimo, Manus, Grok, Google, Qwen, GPT-luna | ⛔ **Choca con la decisión 3** (no abrir la DB viva ni el snapshot). Claude advierte además que los `manual` pueden ser pocos o sesgados. → §4.2 |
| Agujas del par: n-gramas de caracteres y NCD | entradas de la neurona | Gemini 4, Gemini web, Google | ❌ **Refutado por E0:** AUC 0,54–0,70 y orden distinto en cada idioma (`RESULTADOS_E0.md`). Esas opiniones se escribieron antes de E0 |
| Arreglar el «broadcast difuso» de L3023/L3148 | primero | Gemini 4, mimo, Claude, Gemini-argon, Google | ⚠️ **Matizado por el código:** no está en el camino del MCP. Prioridad baja. → §4.4 |
| Ventana fija o adaptativa (pregunta de Qwen) | — | — | **Fija, en sueños (N = 3), no en días.** Lo adaptativo sería una variante aparte, medida después |

## 3. Lo que queda decidido (diseño, sin tocar el motor)

1. **Nacer:** como hoy, pero automático = `a_prueba`, con fecha. Sin el 0,9 fijo y eterno.
   - Esto resuelve el pendiente 2b sin reetiquetar a ciegas.
   - `manual` sigue intocable (ya garantizado por `7e1eb9c`).
2. **Evidencia del sueño**, toda sin idioma, sin telemetría y sin el agente:
   - (a) **estructura que declaró el agente al aprender:** dimensiones, sustantivos clave, sinónimos y
     categoría, comparados por igualdad exacta normalizada;
   - (b) **resonancia independiente en el repaso:** activación conjunta en ≥ 2 sueños distintos, con
     `ignorar_sinapsis`;
   - (c) **competencia dentro del nodo:** queda entre las 5 automáticas más fuertes de A o de B.
3. **Piso:** «≥ 2 de 3». **Encima:** un MLP mínimo, que **solo entra si supera al piso** con la tolerancia
   fijada. Después, modo sombra; después, relevo.
4. **Pruebas obligatorias:**
   - invariancia (D frente a D∪I);
   - orden de guardado;
   - mundo espejo en **español, inglés, chino y japonés**;
   - el bucle (subir el peso de una sinapsis no fabrica su evidencia);
   - precisión **y** recall;
   - QA idéntica.

## 4. Lo que necesita la palabra de Dennys (con recomendación)

### 4.1 Norma 4: ¿se registra el uso real del agente?

**Recomendación: no.** La norma 4 queda como está.
- La mayoría pide «uso real», pero eso obliga al agente a reportar qué recuerdos usó: trabajo extra y
  telemetría.
- Además, las señales que dependen de la disciplina del agente mueren: `util` quedó en 0 de 2157.
- La resonancia independiente da una señal por par **sin el agente y sin el bucle**.

### 4.2 Examen con datos reales

Choca con la decisión 3. Opciones:
- **A. Solo sintético sin filtración + mundo espejo.** Cumple la norma, pero no prueba el valor real.
- **B. Copia de solo lectura, solo para evaluar, nunca para entrenar.** Se ocultan `manual` al azar y además
  Dennys revisa una muestra **al azar** de pares automáticos, sí o no. Por la decisión 4, esa revisión humana sí
  es etiqueta. Antes se cuenta cuántos `manual` hay y de qué tipo, por el sesgo que advierte Claude.
- **Recomendación: B**, porque sin ella no se puede afirmar que la neurona supere a la hormiguita.

### 4.3 Dos cambios pequeños en el motor, para E1 y E2

- El parámetro `ignorar_sinapsis` en `buscar_por_frase`: por defecto apagado, ranking intacto.
- La columna de estado (`a_prueba` / `consolidada` y fecha) en `sinapsis`.

**Recomendación: sí, pero después de E1 en laboratorio.** E1 se puede correr parcheando en memoria una copia en
`/tmp`, sin tocar el repo.

### 4.4 Broadcast difuso de la línea de comandos

**Recomendación: arreglarlo en su propio ciclo**, con una prueba nueva. No es urgente: no afecta al agente.

## 5. ¿De dónde «aprende» la neurona? (la pregunta de fondo, sin adornos)

La hormiguita sabía si dos recuerdos tenían que ver porque Gemini **sabe cosas del mundo**. Un MLP pequeño, sin
embeddings, **no puede saberlo**: E0 lo midió, porque la forma del texto casi no lleva esa información. Por eso
su inteligencia tiene que venir de otro lado, y ahí está lo que nadie más tiene:
- **Juzgar con evidencia acumulada en el tiempo, no de una vez.** A-MEM (NeurIPS 2025) y la hormiguita deciden
  al crear el enlace, con un LLM. Aquí cada sinapsis se juzga en varios sueños, con lo declarado por el agente,
  con la resonancia independiente y con la competencia local.
- **Lo que aprende el MLP** es a **combinar** esas evidencias mejor que la regla fija. Por ejemplo, cuánto vale
  una dimensión compartida en un nodo muy conectado frente a uno aislado. Se evalúa en temas sellados que nunca
  vio: eso es aprender y no memorizar.
- **Etiquetas:** mundos sintéticos **sin filtración** para entrenar, y la revisión humana al azar (§4.2 B) como
  examen final.

**Confianza [D]:** ~0,75 en que el piso mecánico mejore el 11–18 % actual. ~0,5 en que el MLP supere al piso.
**Si no lo supera, se queda el piso**: eso es un resultado válido, no un fracaso.
