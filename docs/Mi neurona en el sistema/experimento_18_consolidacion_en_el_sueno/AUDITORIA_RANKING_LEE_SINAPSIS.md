# Experimento 18 — Auditoría: ¿la búsqueda del agente depende de las sinapsis? (el riesgo del bucle)

**Fecha:** 2026-11-25 · **Base:** `590c2da`

Solo lectura de código: no se modificó nada. **[V]** = verificado, con archivo y línea.

## Por qué importa

Varios asesores (ChatGPT, Claude, Kimi, GPT-luna, Gemini-argon) advierten un riesgo: si «salir juntos en un
resultado» refuerza la sinapsis, aparece un bucle.
1. La sinapsis hace que A y B salgan juntos.
2. Salir juntos refuerza la sinapsis.
3. Y así vuelven a salir juntos.

El sistema aprendería **sus propios hábitos**, no las relaciones reales. Para saber si eso pasaría aquí hay que
ver si el orden del canal 1 **lee la tabla `sinapsis`**.

## Respuesta: sí, en toda consulta normal [V]

`buscar_por_frase` (`core/memory/search.py`, L58) es la búsqueda que usan `recordar` y `buscar` del MCP
(`core/mcp_server/search.py` L550). Estos son los puntos donde lee sinapsis:

| Punto | Línea | ¿Cuándo actúa? | Efecto en el orden |
|---|---|---|---|
| **Activación en cadena desde las 5 semillas FTS** (`cadena_scores_map`) | L2072–2081 | **en toda consulta no estricta** con resultados FTS | `score_cadena` entra en la fórmula: `0.10 · max(score_latente, score_cadena)` (`scoring.py` L338). La neurona de re-ranqueo también lo lee (`neurona.py` L249) |
| **Inferencia transitiva** (`sinapsis_latentes`) | L2152–2161 | en toda consulta con `usar_inferencia=True`, que es el valor por defecto | sube `score_latente`, en el mismo término del 10 % |
| Fallback 1.8: similitud latente (grafo de sinapsis) | L894–905 | solo si hay menos de 3 resultados | agrega candidatos |
| Fallback 1.9: evocación en cadena (`last_parent_map`) | L1067–1098 | solo si hay menos de 3 resultados | agrega candidatos |
| Fallback 2.2: expansión sináptica | L1255–1270 | solo si hay menos de 3 resultados | agrega candidatos |
| Multihop | L1548–1551 | **apagado** por defecto (`BIORAG_MULTIHOP_EXPANSION=0`, `constants.py` L99) | — |
| `context_window` | L2798–2810 | solo si se pide. El MCP lo pasa como 0 a `buscar_por_frase` (L553) y expande aparte (L725) | agrega vecinos después del orden |

**La ráfaga (B10)** escribe sinapsis **durante** el recordar (`rafaga.py` L342). Es nacimiento dentro de la
búsqueda, no una lectura.

### Conclusión [V + D]

- **[V]** Hasta el 10 % del puntaje de cada resultado del canal 1 viene de las sinapsis existentes.
- **[D]** Por eso, contar la co-salida en `buscar_por_frase` como evidencia **sí** formaría el bucle: la sinapsis
  A–B empuja a B en las consultas de A, y eso se leería como prueba de que A–B es buena.
- Esto **descarta** medir la coactivación en el camino del agente (`buscar_por_frase` o ráfaga), aunque se
  hiciera sin telemetría.

## ⚠️ Corrección del mismo día (antes de medir nada): hay dos entradas más del bucle [V]

Al revisar la propuesta de Gemini se comprobó que la tabla anterior estaba **incompleta**. Las sinapsis también
entran en el orden de forma **indirecta**, a través de dos índices que se construyen a partir de ellas:

| Punto | Línea | ¿Cuándo actúa? | Cómo entran las sinapsis |
|---|---|---|---|
| **Señal #13, PPMI+SVD** (`score_candidato`) | `search.py` L2236–2250; peso 0,15 (`constants.py` L208) | **en toda consulta** | los vectores de nodo se **reajustan con las sinapsis** (*retrofitting*, `ppmi_vectorizer.py` L164 y L339–345) |
| Analogía y campo potencial (PPMI) | `search.py` L2105–2135 | solo con su opción o peso activado (por defecto, 0) | los mismos vectores reajustados |
| **Fallback 2.5, SDM** | `search.py` L1289–1321 | si hay menos de 3 resultados (`SDM_FALLBACK_ACTIVO=1`) | los bits 1920–2047 de cada vector SDM codifican los **vecinos por sinapsis** (`sdm.py` L42, L224 y L344) |

**Consecuencias:**
1. La influencia de las sinapsis en el canal 1 es **mayor** que «hasta el 10 %». Al término directo del 10 %
   se suma la parte reajustada de una señal que pesa 0,15.
2. **Error mío corregido:** la versión anterior de esta sección ponía el **SDM** entre las vías «que no leen
   la tabla `sinapsis`». Es falso.
3. Además, PPMI y SDM usan el lematizador español y PPMI la lista de palabras vacías: no son neutrales al
   idioma. PPMI, SVD e IDF son estadísticas de **todo** el corpus, así que tampoco son invariantes ante D∪I.

**Definición corregida:** `ignorar_sinapsis=True` debe saltarse también la señal #13 de PPMI, la analogía, el
campo potencial y el fallback SDM. El repaso usa **solo** FTS (contenido, nombre, sinónimos y sustantivos
clave), las dimensiones y la estructura declarada por igualdad exacta. La prueba del bucle (C1.2 del protocolo
v2) habría detectado esto. Ahora queda escrito antes de medir.

## Lo que sí sirve: «resonancia independiente» en el repaso del sueño

Es la regla que propuso Gemini-argon, ajustada a lo verificado:

> El par A–B cuenta como coactivado **solo si** A y B se activan con una consulta construida desde los campos de
> A, por **vías que no leen la tabla `sinapsis`**: FTS sobre el contenido, el nombre, los sinónimos y los
> sustantivos clave, más las dimensiones (**sin SDM ni PPMI**: ver la corrección de arriba). Así la sinapsis que se está juzgando no puede fabricar su
> propia evidencia.

**Cómo se implementaría (requiere OK, es un cambio en el motor):**
1. Un parámetro nuevo de `buscar_por_frase`, `ignorar_sinapsis=False`. Con `True` se saltan L2072–2081,
   L2152–2161, los fallbacks 1.8, 1.9 y 2.2, el multihop y `context_window`.
   - Con el valor por defecto **no cambia nada**: el ranking del agente queda intacto, como pide la regla de
     Dennys.
   - Lo usa **solo** el repaso del sueño, y siempre en silencio (`neurona.silencio`, L102): no escribe accesos
     ni `log_busquedas`.
2. Test de regresión: con `ignorar_sinapsis=False`, la QA da idéntica caso por caso.
3. Test del bucle: subir de forma artificial el peso de A–B **no cambia** la coactivación medida con
   `ignorar_sinapsis=True`.

## El «broadcast difuso» de L3023/L3148

Ya está en `INFORME_VERIFICACION.md` §1: ese código no está en el camino del MCP. Arreglarlo es poco
prioritario y cambia el olvido de quien usa la línea de comandos, porque `ultimo_uso` alimenta el LTD ×0,95.

**Propuesta, si Dennys lo autoriza:** quitar `ultimo_uso` masivo de `buscar_recuerdo_microsegundos`,
`buscar_recuerdo_profundo` y `buscar_vecinos`, y dejar el +0,15 del propio recuerdo. Una prueba nueva
comprobaría que ninguna sinapsis cambia de `ultimo_uso` al evocar.
