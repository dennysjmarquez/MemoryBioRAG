# Mapa verificado: cómo nacen las sinapsis en BioRAG (2026-11-25)

Dennys pegó un «mapa completo y exacto» del nacimiento de sinapsis que escribió otro agente. Lo revisé
**contra el código actual** (rama `arena/da3df5df-memorybiorag`, commit `798ac34`) y medí en el
snapshot público (`snapshots/qa_escape_qcr_20260811.db`, sha256 `104dd2902aaf…`, que sigue intacto).

- Todas las cifras de este documento salen de `verificar.py` (lee el snapshot en solo lectura y hace
  dos pruebas sobre una copia temporal). Para repetirlo:
  `python3 "docs/Mi neurona en el sistema/mapa_nacimiento_sinapsis/verificar.py" snapshots/qa_escape_qcr_20260811.db`
- **No se cambió nada del motor, ni de los tests, ni de la DB viva.** La DB viva no estaba en esta
  sandbox; las cifras de la viva que se citan vienen de mediciones anteriores ya publicadas
  (`islas_de_recuerdos/README.md`, experimentos 14 y 15).
- Distinción: **verificado** = leído en el código o medido; **hipótesis** = deducido, sin medir.

---

## 1. Lo que el mapa dice bien

En general la estructura es correcta:
- las cuatro pasadas de `auto_vincular`;
- `ON CONFLICT … MAX(peso)` (el peso solo sube cuando el par se vuelve a encontrar);
- DMN con `DO NOTHING`;
- `hipotesis_sueno` con peso 0.08;
- ráfaga con 0.6 y refuerzo +0.1;
- LTD de 0.95 por noche después de 7 días;
- poda de lo que queda por debajo de 0.05;
- los manuales excluidos por `SQL_NO_ES_DEL_AGENTE`.

## 2. Lo que el mapa dice mal (verificado en el código)

| Lo que dice el mapa | Lo que dice el código | Dónde |
|---|---|---|
| `auto_vincular` en L1150–1450 | `core/sinapsis.py` tiene 576 líneas. `auto_vincular` ocupa L104–384 y `vincular_por_sinonimos`, L440–488 | `core/sinapsis.py` |
| «fanout ≤ 30 salida total por nodo» | 30 es el tope **de la pasada 1 en una llamada**. Cada pasada tiene su propio tope: 30, 30, **30** y 15, o sea hasta ~105 enlaces por llamada. **No hay tope por nodo**: se acumula en cada guardado y en cada sueño, y la entrada no tiene ningún límite. En el snapshot, `version_actual_biorag` tiene **241** salidas automáticas | L140, L216, L272, L336 |
| Pasadas 2–4: `peso = overlap·k + w_old·k'` («peso viejo») | `peso_exist` es el `peso_sinaptico` **del recuerdo destino** (su importancia), no el peso anterior de la sinapsis. El enlace nace más fuerte cuanto más importante es el destino, aunque la relación sea la misma: «el rico se hace más rico» | L222, L283, L346 |
| co_semantica: `overlap / max(...)`, `> 0`, fanout 15 | `overlap = intersección / **min**(...)`, con umbral **≥ 0.4** y tope 30. Si el otro recuerdo tiene 1 o 2 sinónimos, **una sola palabra en común da overlap 1.0**, y el peso queda en 0.6 + 0.4·importancia. Es la causa de los «co_semantica 1.00 con fuerza .27» del experimento 14. En el snapshot hay 46 con peso ≥ .99 | L272–283 |
| sinonimo_explicito: peso **0.8**, «creación explícita por el usuario» | El peso por defecto es **0.9**. El usuario declara **palabras**, no pares. El motor enlaza con **todo** recuerdo cuyo nombre o sinónimos **contengan esa cadena** (`LIKE '%término%'`). También nacen `sinonimo_explicito` desde `lexical_learning` (con peso = confianza, en los dos sentidos) | L440–457; `core/lexical_learning.py` L26 y L309–325 |
| Cierre triádico «opcional», que crea sinapsis `triadica` | **Viene activado** (`BIORAG_CIERRE_TRIADICO=1`) y es un **filtro**: rechaza el enlace si los dos no comparten vecino ni dimensión y el nuevo ya tiene más de 5 sinapsis. No existe ningún tipo `triadica`. Se aplica solo en la pasada 1 y en la co-ocurrencia de sesión; no en las pasadas 2–4 ni en los sinónimos | L99–101, L158–166; `consolidation.py` L105–116 |
| co-ocurrencia de sesión o comunicaciones: «+0.05/+0.1 en conflicto» | Es cierto, pero el `UPDATE` **no mira el tipo**: si el par ya era `manual`, le sube el peso. Además `MIN(0.9, …)` **baja** a 0.9 cualquier enlace que tuviera más. En las comunicaciones solo se miran 200 recuerdos activos sin orden (`LIMIT 200`) y los últimos 50 mensajes | `consolidation.py` L119–128, L138, L145, L179–185 |
| ráfaga: refuerzo +0.1 | Es cierto, pero tampoco mira el tipo: el `UPDATE` sube los `manual` (hasta 0.95). Además, solo nace si la palabra de la consulta es **el nombre de un recuerdo** que existe | `core/memory/rafaga.py` L313–345 |
| DMN | Elige pares **solo entre los 40 recuerdos de mayor `peso_sinaptico`**, como máximo 8 por sueño, y viene activado. Otra vez refuerza a los que ya son centrales | `core/dmn_engine.py` L33–140 |
| `hipotesis_sueno` | Lee la cola `vacios_cognitivos` de `estado_hormiga.json`: **depende de la hormiguita**. Es el **único** tipo que nace con `ultimo_uso = ahora`, así que es el único que se olvida solo si no se usa (como las espinas transitorias). Hay 0 en el snapshot | `core/sueno_vacios.py` L1–30, L276–292 |
| `latente_confirmada`: «promoción por refuerzo real» | Solo nace cuando una persona la confirma en el dashboard. No hay promoción automática | `dashboard-neuro-visor/backend/server.py` L745–758 |
| Latentes: tope 50 por nodo, PMI 0.1/0.4, CTE 0.15 | `MAX_LATENTES_POR_NODO = 20`, `UMBRAL_PMI_LATENTE = 0.02`, `UMBRAL_PMI_ALTO = 0.05`, `UMBRAL_SINAPSIS_CTE = 0.25` | `core/inferencia_transitiva.py` L36–51 |
| `establecer_asociacion(…, peso=0.5, tipo='manual')` | No recibe ni peso ni tipo. Inserta `manual` 0.5 **solo en los sentidos que no existían**: no convierte un enlace automático que ya estaba (ver §3.2) | `core/memory/synapses.py` L172–185 |
| «neurona_asociativa (v35) decide qué asociaciones ve el agente» | **Falso.** Está cerrada y **el motor no la llama**. El canal 2 hoy ordena por prioridad de tipo y por peso. Su lugar en el canal 2 es una propuesta (experimento 14), no algo implementado | `core/neurona_asociativa.py` L7–12 |
| «Solo LTD o `recalcular_similitud` bajan pesos» | El LTD **solo toca las sinapsis con `ultimo_uso` lleno**. Todo lo que nace por `auto_vincular`, sinónimos o DMN nace con `ultimo_uso` NULL, así que el LTD **nunca le llega** (§3.4). `recalcular_similitud_sinapsis` solo lo usa un script manual (`scripts/prune_stale_synapses.py`) | `consolidation.py` L482–487 |
| Faltan tipos | También existen `legacy_csv` (25 en el snapshot), `test` (1), `tejida_estructural` (`scripts/tejedora_sweep.py`) y las restauradas desde la cuarentena (`core/dmn_reflexion.py` L940–950) | — |

## 3. Cuatro hallazgos nuevos (verificados y medidos)

### 3.1 Lo que se poda vuelve a nacer: el sistema no recuerda lo que rechazó

Ningún camino de nacimiento consulta `sinapsis_cuarentena` (donde la hormiguita deja lo que poda) ni
`sinapsis_bloqueadas` (lo que una persona rechaza en el dashboard). Lo verifiqué con `grep`: ninguna
de esas dos tablas se lee al crear un enlace.

- **En el snapshot:** de 3245 sinapsis en cuarentena sin restaurar, **432 (13 %) ya habían
  renacido**. Del mismo tipo, en promedio **2,4 días** después (398 `co_ocurrencia`, 21
  `sinonimo_explicito`, 6 `co_semantica`…).
- **Prueba en una copia:** a 40 enlaces automáticos al azar les apliqué `desvincular` (la «plasticidad
  negativa» del agente) y después volví a guardar el recuerdo con `auto_vincular`. **15 de 40
  renacieron al instante**, con el mismo tipo y casi el mismo peso.
- El docstring de `desvincular` promete «para que no vuelva a traerse»; **en código no se cumple**
  cuando el par sigue cumpliendo la regla de nacimiento.

### 3.2 Cuando el agente vincula un par que ya tenía enlace automático, queda protegido a medias

En `aprender`, primero corre `auto_vincular`, después los sinónimos y al final `vincular_con`
(`core/mcp_server/write.py` L316–347). Si el enlace automático ya existía, `establecer_asociacion`
no lo convierte: solo crea el sentido que faltaba.

- **Prueba en una copia:** quedó `A→B co_ocurrencia 0.677` y `B→A manual 0.5`, y el mensaje
  respondió «Sinapsis establecida».
- **En el snapshot:** **142 pares** tienen `manual` en un sentido y un enlace automático en el otro
  (116 `sinonimo_explicito`, 14 `pmi_hebbiano`, 7 `co_nombre`, 5 `co_ocurrencia`). El sentido
  automático lo pueden tocar el LTD, la poda y la hormiguita.
- **Hipótesis (sin medir):** el canal 2 puede mostrar ese par como automático y no como «manual
  primero».

### 3.3 Hay procesos automáticos que cambian el peso de los enlaces manuales

**Verificado en el código:** la co-ocurrencia de sesión (+0.1), la de comunicaciones (+0.05) y el
refuerzo de ráfaga (+0.1) hacen `UPDATE` sin filtrar por tipo. El refuerzo dopaminérgico también
sube las aristas del camino sin mirar el tipo, pero ese depende de feedback explícito.

- **En el snapshot:** 36 enlaces manuales no pesan 0.5.
- **No se puede saber cuál proceso causó cada uno** (no hay historial), así que la atribución queda
  como hipótesis.
- Las reglas dicen que «los `manual` no los toca nada automático».

### 3.4 Lo que nunca se usó es inmune al olvido

Este hallazgo ya estaba en `islas_de_recuerdos/README.md`; aquí se confirma contra el código actual.
El `INSERT` de `auto_vincular`, de los sinónimos y del DMN no llena `ultimo_uso`, y el LTD exige
`ultimo_uso IS NOT NULL`.

- **En el snapshot:** 5152 de 5863 `sinonimo_explicito`, 1215 de 1226 `co_semantica` y las 56
  `dmn_synthesized` tienen `ultimo_uso` NULL.
- **En la viva** (medición anterior): el 87 %.

**Extra: el cierre triádico ya no filtra.** El grafo está tan conectado que **el 54 % de los pares de
recuerdos tomados al azar ya comparten un vecino**, y el 89 % de los recuerdos activos tiene más de 5
sinapsis. El filtro contra «puentes espurios» deja pasar a más de la mitad de los pares sin relación.

## 4. Qué significa para la «neurona gobernadora» que propone el mapa

El mapa propone una neurona que decida el **peso al nacer**, con **veto**, y que rompa `MAX(peso)`.
Con la evidencia que ya hay:

- **Poner el peso al nacer ya se probó** (experimento 12, commit `dd85fcf`): la QA salió idéntica y se
  revirtió (`76fe11c`).
- **El veto al nacer baja el recall** (experimento 13).
- **Bajar pesos roba lugares del canal 2** mientras el umbral sea absoluto (experimento 15, S1).

Lo medido hoy apunta a otra causa. El problema no es tanto **con qué peso** nace un enlace, sino que el
sistema:

1. **no recuerda lo que ya se rechazó**, así que lo podado y lo desvinculado renace (§3.1);
2. **no respeta del todo la decisión del agente** (§3.2 y §3.3);
3. **no olvida lo que nunca se usó** (§3.4);
4. **nace con reglas que premian al que ya es central**: el peso depende de la importancia del
   destino, el DMN elige entre los 40 más pesados, el `min` de la pasada 3 y no hay tope por nodo.

En la biología del documento anterior (`biologia_ciclo_de_vida_sinapsis.md`), lo que falta es justo:
- la **marca que persiste** (C1q/C3: lo marcado para comerse no se reconstruye igual);
- el **«no me comas»** de lo que se usa (CD47);
- el **recambio de las espinas transitorias**.

`hipotesis_sueno` ya funciona así (nace con 0.08 y se olvida si no se usa). Los demás tipos no.

## 5. Propuesta (no implementada; cada paso necesita el OK de Dennys)

**Primero, cuatro correcciones de reglas.** Son pequeñas y cada una se mide sola, en una copia, con la
QA y la suite antes y después:

1. **Memoria de rechazo.** Antes de crear un enlace automático, mirar `sinapsis_cuarentena`, las
   bloqueadas y un registro de `desvincular`. Si el par está ahí, no renace (o renace solo con
   evidencia nueva y más fuerte). Es lo que más se parece a lo que hacía la hormiguita, pero sin
   API: **la decisión ya tomada se respeta**.
2. **`vincular` convierte en `manual` los dos sentidos** de un par que ya existía como automático.
3. **Ningún proceso automático cambia el peso de un `manual`** (agregar el filtro de tipo a los tres
   `UPDATE`).
4. **Nacer con `ultimo_uso = creado_en`**, como `hipotesis_sueno`, para que el olvido por desuso
   funcione. **Ojo:** esto haría decaer miles de enlaces de golpe. Antes de proponerlo hay que
   simularlo en copia (con cuántos sueños bajan del umbral del canal 2) y, probablemente, aplicarlo
   solo a lo que nace de aquí en adelante.

**Después, la neurona del canal 2** (experimento 14). **Y al final, la neurona de nacimiento.** Esta
no debería decidir solo el peso: debería decidir **si un par vuelve a nacer después de haber sido
rechazado**, y en eso puede aprender de las 5446 decisiones históricas de cuarentena
(3245 + 2201 restauradas) **como banco de entrenamiento con examen sellado**, sin Gemini.

Nada de esto se ha implementado.
