# Auditoría — Calibración conforme v28.1 (`FIX_FP_80%_EN_LIVE`, `423868c`)

Respuesta a las cinco preguntas planteadas. Revisado leyendo el código de la rama,
no el reporte.

**Veredicto corto:** la matemática es correcta y la idea del percentil es acertada.
Pero **el número que justifica el cambio (`FP 6%`) es tautológico**, y **el coste en
recall no se midió**. No mergear a master hasta cerrar esos dos puntos.

---

## P1. ¿La matemática conforme es correcta y suficiente para FP ≤ α?

**La fórmula, sí. La evidencia que la respalda, no.**

El cuantil `k = ceil((n+1)(1−α))` es la predicción conforme split estándar (Vovk
2005) y está bien implementado. La garantía es real **bajo intercambiabilidad**.

**Problema: `FP 6% (2/32)` no es una medición.**

`calibrar_umbral_conforme` recoge los scores de los 32 negativos, fija el umbral con
ellos y **no reserva ninguno para validar**. El FP se reporta sobre los mismos datos.
Aritmética:

```
n=32, α=0.10  ->  k = ceil(33 × 0.90) = 30
umbral = 30º valor de 32  ->  quedan 2 por encima  ->  2/32 = 6.25%
```

El reporte dice 6% (2/32). **Coincide exactamente con el cálculo puramente
aritmético.** Ese número saldría igual con datos aleatorios: es la definición del
cuantil, no una propiedad del sistema.

> Es el mismo fallo que ya se detectó y corrigió en `test_h_corpus_umbral.py`
> (partición calibración/validación). Aquí volvió a aparecer en el código de
> producción.

**Qué hace falta:** partir los negativos (16 calibración / 16 validación) y reportar
el FP sobre los que el umbral nunca vio. Solo entonces el número significa algo.

**Segundo problema — el tamaño de muestra.** Con n=32 y α=0.10, `k=30`: el umbral
lo determina el 30º de 32 valores, es decir la cola de la muestra. El α mínimo
detectable es `1/(n+1) = 0.030`. Partir a la mitad deja 16, y ahí `k = ceil(17×0.9)
= 16` — el **máximo** de la submuestra, el estadístico más inestable que existe.

**Con 32 negativos, la garantía es formalmente válida pero estadísticamente frágil.**
Generar negativos es barato (son consultas sin respuesta): subir a 200-300 convierte
el umbral en algo defendible.

---

## P2. ¿Los 40 negativos del QA baseline son representativos?

**Hay tres sesgos, y uno es grave.**

**a) Sesgo de construcción (grave).** Los negativos del QA fueron escritos a mano
para ser *claramente* ajenos al corpus. Las consultas negativas reales de un agente
son mucho más sutiles: preguntas sobre temas vecinos, matices que la memoria no
tiene. Esas puntúan **más alto** que un negativo sintético.

Consecuencia: el umbral calibrado con negativos "fáciles" queda **demasiado bajo**
para los negativos reales, y la garantía FP ≤ α no se traslada a producción.

**b) Sesgo de distribución.** La garantía conforme exige que la muestra de
calibración venga de **la misma distribución** que las consultas de producción. El
propio docstring lo asume, pero nadie lo verificó. Es la hipótesis central del
método y está sin comprobar.

**c) n=32 es el 4.3% del benchmark.** Wilson 95% para 2/32: **[1.7%, 20.1%]**. El
intervalo real de ese "6%" llega hasta el 21%.

**Recomendación concreta:** extraer negativos reales de `log_busquedas` (consultas
que el agente hizo y no tuvieron respuesta útil). Eso resuelve (a) y (b) a la vez,
y es la misma tabla que ya hace falta para medir el ratio.

---

## P3. ¿El umbral de drift >20% es razonable?

**El mecanismo sí; el disparador es incompleto.**

Persistir el umbral con `n_nodos_corpus` y recalcular al detectar cambio es la
decisión correcta, y resuelve el problema real ("el umbral no escala"). Bien
diseñado.

Pero **el tamaño del corpus no es la única causa de deriva.** El piso de ruido
también se mueve con:

- un **reindexado PPMI+SVD completo** (cambia todos los vectores de golpe, sin
  cambiar el número de nodos)
- el **retrofitting hebbiano** tras un ciclo de sueño
- cambios en pesos del scoring (como el fix 1.2 de esta misma release, que
  multiplicó todos los scores por ~0.746 sin tocar un solo nodo)

Con la lógica actual, cualquiera de esos deja el umbral obsoleto y **el sistema no
se entera**, porque `n_nodos` no cambió.

**Fix sugerido:** invalidar la calibración también cuando cambie
`ppmi_ultima_reindexacion` (ya está en la tabla `data`) o la versión del scoring.
Es una condición más en el mismo `if`.

Sobre el 20% en sí: es arbitrario pero razonable como punto de partida. Lo que lo
justificaría es medir cuánto se mueve el umbral en función del crecimiento —
convertirlo en dato en vez de constante.

---

## P4. ¿Los 3 niveles son la forma correcta de "nunca silencio"?

**Sí, y es la mejor decisión de diseño de esta release.**

Exponer `evidencia_directa` / `relacionado_confianza_media` / `sin_evidencia_directa`
en vez de un corte binario es exactamente lo que corresponde con AUC=0.914: hay
señal de sobra para graduar. Y encaja con el "filtro de honestidad epistémica" que
el proyecto ya declaraba pero no implementaba.

Que **no toque el ranking** (`buscar_con_calibracion` es una función aparte;
`buscar_por_frase` queda intacta) es la decisión correcta: preserva el baseline y
hace el cambio reversible.

**Dos observaciones:**

1. Los **cortes entre niveles** no están calibrados: el umbral conforme define uno
   solo (responder/no). El límite entre "directa" y "media" es una constante
   elegida a mano. Con la misma maquinaria se podrían derivar dos cuantiles
   (α=0.10 y α=0.30) en vez de uno.

2. El fallback `return score > 0.65` cuando no hay calibración es un umbral fijo
   —justo lo que la release viene a eliminar—. Debería avisar ruidosamente de que
   está operando sin calibrar, en vez de degradar en silencio a la práctica anterior.

---

## P5. ¿Rompe algo del ranking o del baseline?

**No, y está bien aislado.** Verificado en el código:

- `buscar_con_calibracion` es una vía **separada**; `buscar_por_frase` no cambia
- `nivel_certeza` y `confianza_calibrada` son **campos añadidos**, no reordenan
- 22 tests pasan (16 previos + 6 nuevos)

**Pero hay un coste que no se midió, y es el punto más importante de esta auditoría.**

Los tests nuevos verifican percentiles, monotonía de Platt y persistencia. **Ninguno
mide cuántas respuestas correctas se pierden.** Del barrido H-corpus previo sobre la
live DB, un umbral en la zona 0.78–0.80 da recall 78–82%. Aplicado a los 881 casos:

| escenario | responde bien |
|---|---|
| hoy, sin abstención | **849 casos** |
| con umbral ~0.80 | ~722 casos |
| con umbral ~0.78 | ~687 casos |

**Pérdida estimada: 127–162 respuestas correctas**, para evitar ~30 falsos positivos
de 40 negativos.

Y con los tamaños del propio benchmark (881 positivos : 40 negativos), asumiendo que
un FP y un FN cuestan lo mismo:

```
sin abstención        : 881×0.9637 + 40×0.00 = 849 aciertos netos
conforme (α=0.10)     : 881×0.8200 + 40×0.94 = 760 aciertos netos
```

**El balance neto empeora.** No porque la calibración esté mal hecha, sino porque
**α=0.10 fue elegido sin conocer el coste relativo de cada tipo de error** — y ese
coste depende del ratio real de consultas con y sin respuesta, que sigue sin medirse.

---

## Qué haría antes de mergear

| # | Acción | Coste | Por qué |
|---|---|---|---|
| 1 | Partir negativos en calibración/validación y reportar FP held-out | 10 líneas | el `6%` actual es aritmética, no evidencia |
| 2 | Correr `evaluar_qa.py` con `buscar_con_calibracion` activa | 1 corrida | mide la pérdida real de recall, hoy desconocida |
| 3 | Medir ratio real en `log_busquedas` | 1 consulta | sin él, α=0.10 es una preferencia, no una decisión |
| 4 | Extraer negativos reales de `log_busquedas` | 1 tarde | resuelve el sesgo de construcción (P2a) |
| 5 | Añadir `ppmi_ultima_reindexacion` al disparador de drift | 1 línea | P3: el corpus no es la única causa de deriva |
| 6 | Hacer ruidoso el fallback `score > 0.65` | 2 líneas | no degradar en silencio al comportamiento viejo |

Los pasos 1–3 son media hora y deciden si α=0.10 es el valor correcto o hay que
moverlo.

---

## Lo que está bien y hay que reconocer

- **La idea del percentil es correcta y es de Dennys.** La analogía con `width:50%`
  es exacta: el umbral deja de ser un valor absoluto y pasa a ser una posición
  relativa en la distribución de ruido. Es la solución adecuada al problema
  diagnosticado.
- **La persistencia con `n_nodos_corpus`** convierte una calibración estática en un
  sistema que se mantiene solo. Es el paso de "arreglo puntual" a "mecanismo".
- **Los 3 niveles** aprovechan la señal disponible (AUC 0.914) mucho mejor que un
  corte binario.
- **El aislamiento respecto al ranking** preserva el baseline y hace el cambio
  reversible.
- **El comentario en el código** documenta explícitamente que RRF no resuelve el FP,
  con el razonamiento. Eso evita que alguien lo reintroduzca en seis meses.

La arquitectura es la correcta. Lo que falta es la evidencia que la valide: hoy el
cambio se apoya en un número tautológico y no conoce su propio coste.
