# Paso 2: el examen de rescate, en el laboratorio (protocolo fijado ANTES de medir, 2026-11-25)

Plan: `../PLAN_NEURONA_SINAPTICA_ESTRELLA.md` §3 y §9. **No toca el motor. No entrena ninguna neurona.**
Solo construye el examen que será la «verdad gratuita» de la neurona sináptica y mide si sirve.

## 1. Para quien llega sin contexto
La neurona 1 del motor aprende sola porque cada recuerdo se hace preguntas a sí mismo y la respuesta correcta es
él mismo. Para las sinapsis buscamos algo igual de gratuito:
1. El recuerdo **B** se hace una pregunta con pocas piezas de su propio texto.
2. La búsqueda **ciega** (una copia sin sinapsis) **no** encuentra a B, pero sí encuentra a **A**.
3. A tiene vecinos sinápticos (el «canal 2»). Si B está entre ellos, el grafo puede **rescatar** a B.
4. La pregunta del examen: **¿en qué puesto queda B entre los vecinos de A?** La respuesta es B, porque la pregunta
   salió de B. Nadie tiene que etiquetar nada.

Una neurona futura aprenderá a ordenar los vecinos de A para que B suba. Hoy solo medimos el **piso**: el orden a
mano del motor (`obtener_asociaciones_enriquecidas`: peso ≥ 0,50, nodo activo, prioridad del tipo y peso
descendente, tope de 2 `sinonimo_explicito`, 5 visibles).

## 2. Mundo
- Textos y estructura del experimento 18 E1 (`mundos_espejo.py`, `e1_mundo.py`, semilla 18), en es, en, zh, ja:
  24 recuerdos D (8 temas × 3) + 8 irrelevantes I. Construido con el motor real (`e1_medir.py construir`), igual
  que en E1 (la DMN encendida durante la construcción, como crece el motor normalmente; aquí queda declarado).
- **Mundo principal: «ruidoso»** = D + las 20 sinapsis falsas de E1 (pares de temas distintos, semilla 18) + un
  sueño. Razón, conocida antes de medir el examen: el grafo limpio D tiene solo 16–18 filas de sinapsis por idioma
  (`e1_a4.json`), y las bases reales son ruidosas (exp. 16: 11–18 % de acierto de las sinapsis automáticas).
- **Diagnóstico:** el mundo limpio D (sin puertas) e invariancia con DI ruidoso (D + I + las mismas 20 falsas + sueño).
- Las etiquetas del mundo (mismo tema / puente / distinto) **nunca entran en el examen**; solo se usan para auditar
  si el examen premia relaciones reales (P5).

## 3. Las pistas (sin idioma)
- Unidades Unicode de `e1_repaso.unidades`: palabras entre espacios; bigramas en escritura sin espacios.
- Se quitan las unidades contenidas en el nombre del recuerdo («sin el nombre»).
- **Muestras dispersas**, no ventanas seguidas: posiciones elegidas con un azar fijo por `sha256(B|sueño|nivel)`.
- **Dificultad en escalera:** nivel 3 = 3 unidades, nivel 2 = 2, nivel 1 = 1. Sueños 1–5. Hasta 15 pistas por B.
- Sin listas de palabras, sin plantillas, sin diccionarios.

## 4. Búsqueda ciega y casos
- Copia limpia A4 (`e1_repaso`): sin `sinapsis`, sin `sinapsis_latentes`, sin `asociaciones`, sin dimensiones
  `auto_generada = 1`; `buscar_por_frase(pista, limite=6, profundidad="profundo", usar_inferencia=False,
  context_window=0, ignore_peso_sinaptico=True)`, entorno limpio (DMN, PPMI, SDM y multihop apagados).
- **Caso de rescate:** B no está en el top-5 ciego, y algún A del top-5 ciego tiene a B entre sus vecinos del canal 2
  (lista completa, sin cortar a 5). Se toma el primer A así. Respuesta: el puesto de B en la lista de A.
- **Guardia:** 20 % de los B por `sha256(B) % 5 == 0`. Hoy solo se cuenta; servirá en el paso 4.

## 5. Puertas (en el mundo ruidoso; deben cumplirse en los 4 idiomas)
| id | qué | umbral |
|---|---|---|
| P1 | Casos suficientes | ≥ 30 casos y ≥ 8 recuerdos B distintos por idioma; ≥ 2 B distintos en la guardia |
| P2 | Invariancia de la pregunta | top-5 ciego idéntico entre D y DI en ≥ 98 % de las pistas |
| P2b | Invariancia de la respuesta | en los casos comunes, el mismo A y el mismo puesto del piso en ≥ 98 % (D ruidoso frente a DI ruidoso) |
| P3 | Control de hubs | ningún A aporta más del 25 % de los casos; los 3 A más frecuentes, ≤ 50 % |
| P4 | Margen para aprender | el piso NO pone a B primero en ≥ 20 % de los casos (si no, no hay nada que aprender aquí) |
| P5 | Validez: el examen premia relaciones reales | (a) la fracción de casos con A y B del mismo tema o puente supera la fracción de esas relaciones entre todas las aristas del grafo ruidoso; (b) MRR del orden «oráculo» (mismo tema primero) > MRR del piso > MRR del «anti-oráculo» (distinto tema primero) |
| P6 | Limpieza y reproducibilidad | dos repasos idénticos; sha256 de las bases sin cambio; 0 sinapsis, 0 asociaciones y 0 emergentes en la copia ciega al terminar; la consulta de vecinos no cambia el número de sinapsis |

Referencia, sin puerta: MRR esperado de un orden al azar, piso en el mundo limpio D, distribución por nivel.

## 6. Qué significa cada resultado
- **Todas pasan:** el examen sirve como verdad gratuita; se pasa al paso 3 (agujas, mundo a ciegas).
- **Falla P1 o P3:** el mundo es pequeño o el grafo demasiado ralo; el paso 3 necesita un mundo más grande.
- **Falla P5:** el examen premia coincidencias de superficie y no relaciones; hay que rediseñarlo antes de entrenar.
- **Falla P4:** el piso ya acierta aquí; la neurona no tendría qué aprender en este mundo.
Ningún umbral se cambia después de ver los datos. Si algo falla, se informa tal cual.
