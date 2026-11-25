# Cómo nace, se queda o se poda una sinapsis en el cerebro, y cómo copiarlo en BioRAG

- **Fecha:** 2026-11-25. **Estado:** investigación y propuesta. No cambia el motor.
- **Pedido de Dennys:** la neurona asociativa nació para reemplazar a la hormiguita, que usaba Gemini para
  podar las sinapsis padre-hijo, sin APIs externas. Dennys quiere saber cómo lo hace un cerebro y tener un
  sistema más sofisticado.

## 1. El caso real (captura del Neuro-Visor, copia de la viva)

Recuerdo `regla_verificar_codigo_real_antes_de_diagnostico`: 152 sinapsis, de las cuales 91 son
`sinonimo_explicito`; 125 nunca se usaron.

| Peso hoy | Tipo | Fuerza según la neurona | Vecino |
|---|---|---|---|
| **1.00** | co_semantica | **.27** | un recuerdo sobre el nivel de inglés |
| **1.00** | co_semantica | .55 | una regla de no tocar cosas |
| **1.00** | co_semantica | **.27** | un parche técnico de ole32 |
| .50 | manual | **.93** | `regla_memoria_primero_buscar_regla_antes_de_actuar` |
| .17 | pmi_hebbiano | **.92** | una lección sobre el protocolo de feedback |

Por qué nace en 1.00 (`core/sinapsis.py`, `auto_vincular`, pasada 3):

- `solape = compartidos / min(sinónimos_A, sinónimos_B)` y `peso = 0.6·solape + 0.4·peso_vecino`.
- Si el vecino tiene **un solo** token de sinónimo y coincide (por ejemplo, un nombre propio), el solape da 1.0.
  Con un vecino de peso 1.0, la sinapsis nace en **1.00**.
- En la viva hay **224** `co_semantica` con peso 1.00.

En toda la viva, **30 048 de 34 597 sinapsis automáticas (87 %) nunca se usaron**, y existen 19 027 latentes.

## 2. Lo que hace el cerebro (fuentes)

| Mecanismo | Qué hace | Fuente |
|---|---|---|
| **Nacer mucho, débil y provisional** | La mayoría de las espinas nuevas son transitorias y pocas se estabilizan. Las que se quedan sostienen la memoria a largo plazo | Yang, Pan y Gan, *Nature* 2009; Holtmaat y Svoboda, *Nat Rev Neurosci* 2009 |
| **Sinapsis silenciosas** | Conexiones inmaduras que no transmiten hasta que se las recluta. Activarlas es más fácil que cambiar una madura, y no pisa lo ya aprendido | Vardalaki et al., MIT, *Nature* 2022 |
| **Etiqueta y captura** | Al activarse, la sinapsis queda **marcada**. Solo se vuelve duradera si, dentro de una ventana de tiempo, captura «proteínas de plasticidad» | Frey y Morris, *Nature* 1997; Redondo et al., *J Neurosci* 2010 |
| **Regla de tres factores** | Hebb (A y B juntos) deja una **traza de elegibilidad**. El cambio solo ocurre si llega un **tercer factor** (novedad, sorpresa o recompensa) mientras dura la traza | Gerstner et al., *Front Neural Circuits* 2018 |
| **Homeostasis en el sueño** | Despierto, las sinapsis se refuerzan en neto. El sueño las baja **en proporción** hasta que el total que recibe cada neurona vuelve a su base; las que caen bajo un umbral quedan silenciosas | Tononi y Cirelli, *Sleep Med Rev* 2006; *Neuron* 2014 |
| **Escalado multiplicativo** | Se multiplican todos los pesos de una neurona por el mismo factor: cambia el total, **se conserva el orden** | Turrigiano 2008 |
| **Poda por competencia** | El complemento (C1q/C3) marca **«cómeme»** a las sinapsis débiles o inactivas frente a sus vecinas fuertes, y la microglía se las come | Stevens et al. 2007; Schafer et al., *Neuron* 2012 |
| **«No me comas»** | CD47 protege a las sinapsis **activas**. Sin esa señal, la poda se excede | Lehrman et al., *Neuron* 2018 |
| **El sueño elige qué repasar** | Lo que se marcó despierto (ondas *sharp-wave ripple*) es lo que se repasa y consolida al dormir | Yang et al., *Science* 2024 |

La idea común: **el cerebro no decide en el momento de nacer.** Deja nacer mucho, débil y a prueba. Se queda
lo que junta evidencia en una ventana de tiempo, y la poda es **relativa** (competencia dentro de la misma
neurona), **marcada antes de ejecutarse** y con protección para lo activo.

## 3. BioRAG hoy frente al cerebro

| Cerebro | BioRAG hoy | Choque |
|---|---|---|
| nace débil y a prueba | nace **fuerte y para siempre** (0.9, a veces 1.00) | el ruido nace con más peso que lo bueno |
| lo hecho «a mano» se protege | `manual` nace en 0.5, **por debajo** de lo automático | al revés |
| etiqueta y ventana | no hay estado «a prueba» | nada distingue lo nuevo de lo confirmado |
| tercer factor | no existe; la hormiguita usaba el *significado* (Gemini) | el 39 % de sus cortes tuvo que volver (exp. 10) |
| homeostasis por neurona | LTD global ×0.95 solo si pasan 7 días sin uso | los nodos muy conectados no tienen freno: 759 vecinos; **las islas por sinapsis murieron por saturación** |
| poda relativa, marcada y con «no me comas» | Gemini decidía por pares, en absoluto | sin competencia ni protección por uso |
| silenciosas que se reclutan | 19 027 latentes; la confirmación dependía de la hormiguita | sin criterio propio |

## 4. Propuesta: el ciclo de vida de una sinapsis (la neurona asociativa v3)

La **neurona sigue cerrada**: su regla no aprende (decisión del 24-10). Lo que cambia son las **sinapsis**,
por evidencia, tiempo y uso, como en el cerebro. Así encaja con la nota de V2.15: *«lo que sigue cambiando son
las sinapsis del grafo (Hebb, sueño, desuso); la regla queda fija»*.

```
         nace (como hoy: el motor propone, no se corta nada al nacer — exp. 13)
           │  estado = A PRUEBA, etiqueta con fecha, fuerza = neurona
           ▼
   ┌── ventana de N sueños ──────────────────────────────────────────┐
   │  captura evidencia (tres factores, sin feedback del agente):    │
   │   1) fuerza de la neurona ≥ .80             (el par se parece)  │
   │   2) Hebb: A y B salieron juntos en un recordar o en la ráfaga  │
   │   3) tercer factor: la sinapsis estaba en el camino a la        │
   │      respuesta correcta en el AUTOEXAMEN (exp. 10, medición D)  │
   └─────────────────────────────────────────────────────────────────┘
           │ captura ≥ 2 de 3                       │ no captura
           ▼                                        ▼
       CONSOLIDADA                          DÉBIL (se atenúa)
           │                                        │ sigue sin evidencia
           │                                        ▼
           │                     marca «CÓMEME» si pierde la competencia
           │                     dentro de su nodo (relativa, no absoluta)
           │                                        │
           │                     «NO ME COMAS» si: manual · usada hace poco ·
           │                     útil en el autoexamen · el nodo quedaría
           │                     con < 5 pistas (Pilar 12)
           │                                        ▼
           │                         CUARENTENA (reversible, nunca borrar)
           ▼
   SUEÑO: homeostasis por nodo
   si la suma de pesos automáticos de un nodo pasa de su presupuesto (relativo a la
   mediana de ESTA memoria), se multiplican todos por el mismo factor:
   cambia el total, NO el orden. Los manuales no se escalan.

   LATENTES = silenciosas: pasan a activas solo con fuerza alta + Hebb (dos factores).
   COSTO FIJO: cada sueño revisa K nodos, primero los tocados desde el último sueño
   (como las ondas que marcan qué repasar).
```

**Qué reemplaza:**
- a la hormiguita (sin Gemini y sin APIs externas);
- al LTD global de sinapsis, por una homeostasis por nodo;
- a la confirmación de latentes.

**Qué no toca:**
- los recuerdos;
- los enlaces `manual`;
- el ranking ni el canal 1;
- nada en el momento de `recordar`, donde solo se **ordena** (Pilar 12).

### Reglas de la casa que respeta

| Regla | Cómo |
|---|---|
| Nunca borrar | cuarentena reversible |
| Manual intocable | «no me comas» permanente; no se escala |
| Sin feedback del agente | los tres factores son internos: neurona, coactivación y autoexamen |
| Tiempo constante | K nodos por sueño |
| Desde una DB vacía | sin datos no hay evidencia: todo queda a prueba y nada se poda |
| No filtrar al recordar | todo ocurre en el sueño |
| Homeostasis (Pilar 13) | presupuesto relativo a cada memoria |
| No cortar al nacer (exp. 13) | se nace igual que hoy |
| La poda por significado falló (exp. 10) | se poda por **utilidad y competencia**, no solo por fuerza |
| Grupo B del exp. 11: el 36 % de lo que soltaría era bueno | exige dos señales; la cuarentena es reversible; tope por ciclo |

## 5. Cómo se mediría (antes de tocar el motor)

1. **Simulación en copias** (snapshot y viva) de M sueños con estas reglas, en un script de laboratorio. Se mide:
   - el tamaño del grafo y los nodos con más de X vecinos;
   - las **islas por sinapsis** (LPA del motor): si la homeostasis funciona, deberían volver a aparecer;
   - el examen tapado y el canal 2 (exp. 14);
   - los recuerdos con menos de 5 pistas;
   - la QA oficial, que debe dar idéntica.
2. Después, modo **aprendiz**: en el motor solo anota estados, sin cambiar pesos. Luego modo **relevo**.
   Por último, el **retiro** de la hormiguita (exp. 10, §9.6).
3. Un paso a la vez, primero conversado y con interruptor.

## Fuentes

- Frey U, Morris RGM (1997). Synaptic tagging and long-term potentiation. *Nature* 385:533–536.
- Redondo RL et al. (2010). Synaptic tagging and capture… *J Neurosci* 30(14):4981. https://www.jneurosci.org/content/30/14/4981
- Tononi G, Cirelli C (2006). Sleep function and synaptic homeostasis. *Sleep Med Rev* 10:49–62.
- Tononi G, Cirelli C (2014). Sleep and the price of plasticity. *Neuron*. https://www.cell.com/neuron/fulltext/S0896-6273(13)01186-0
- Turrigiano G (2008). The self-tuning neuron: synaptic scaling of excitatory synapses. *Cell*.
- Schafer DP et al. (2012). Microglia sculpt postnatal neural circuits in an activity and complement-dependent manner. *Neuron* 74:691–705.
- Lehrman EK et al. (2018). CD47 protects synapses from excess microglia-mediated pruning during development. *Neuron*.
- Yang G, Pan F, Gan WB (2009). Stably maintained dendritic spines are associated with lifelong memories. *Nature* 462:920–924. https://www.nature.com/articles/nature08577
- Holtmaat A, Svoboda K (2009). Experience-dependent structural synaptic plasticity in the mammalian brain. *Nat Rev Neurosci*. https://www.nature.com/articles/nrn2699
- Gerstner W et al. (2018). Eligibility traces and plasticity on behavioral time scales. *Front Neural Circuits* 12:53.
- Vardalaki D et al. (2022). Filopodia are a structural substrate for silent synapses in adult neocortex. *Nature*. https://news.mit.edu/2022/silent-synapses-brain-1130
- Yang W et al. (2024). Selection of experience for memory by hippocampal sharp wave ripples. *Science* 383:1478. https://www.science.org/doi/10.1126/science.adk8261
