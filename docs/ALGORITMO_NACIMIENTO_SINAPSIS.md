# El algoritmo base: cómo BioRAG crea, cambia y borra sinapsis

> **Para quién es este documento:** para cualquiera que llegue sin contexto y necesite entender qué pasa
> por detrás cuando el sistema aprende o consolida. Describe el código tal como está (rama
> `arena/da3df5df-memorybiorag`, 25-11-2026).
>
> **Cómo verificarlo:** cada afirmación lleva el archivo y la línea. Todo lo marcado **[visto]** se
> reprodujo con el motor real en `docs/Mi neurona en el sistema/estudio_nacimiento_aprender_consolidar/trazar.py`.
> Ese script trabaja sobre una base nueva en `/tmp`, sin datos privados. Lo marcado **[código]** se
> verificó leyendo el código. Lo marcado **[deducido]** es una inferencia todavía sin medir.
>
> **Qué no es:** no es una propuesta implementada. La sección 8 propone mejoras, y ninguna está
> aplicada. Cada una necesita el OK de Dennys.

---

## 1. Vocabulario mínimo

| Término | Qué es en BioRAG | Dónde vive |
|---|---|---|
| **Recuerdo / nodo / concepto** | Una unidad de memoria con nombre (`concepto`), texto (`contenido`), `sinonimos`, dimensiones y `peso_sinaptico` (la importancia del recuerdo, no del enlace) | `corto_plazo` y `largo_plazo` |
| **Corto plazo** | La «sala de espera» donde entra lo que se aprende y todavía no se consolidó | tabla `corto_plazo` |
| **Largo plazo** | La memoria consolidada. Solo aquí se crean enlaces | tabla `largo_plazo` |
| **Sinapsis directa** | Un enlace real y guardado entre dos recuerdos | tabla **`sinapsis`** |
| **Sinapsis latente** | Un enlace **inferido**: A y C no están unidos, pero hay un camino A→B→C. Es un cálculo, no un enlace | tabla **`sinapsis_latentes`** |
| **Dimensiones** | Etiquetas semánticas del recuerdo (entidad, intención, tema…). Dos recuerdos con una dimensión en común «se parecen» para varias reglas | `largo_plazo_dimensiones` |
| **`asociaciones`** | Una columna de texto en `largo_plazo` con la lista de vecinos. Es un **espejo** de `sinapsis` y no la fuente | `_sincronizar_asociaciones`, `core/sinapsis.py:491` |

### 1.1 Sinapsis directa (`sinapsis`)

Las columnas están en `core/sinapsis.py:31`:

```
origen TEXT, destino TEXT, peso REAL (0–1), tipo TEXT, creado_en REAL, ultimo_uso REAL
PRIMARY KEY (origen, destino)
```

- **Es dirigida.** `A→B` y `B→A` son dos filas distintas, con pesos que pueden diferir. Casi todas las
  reglas automáticas crean **un solo sentido** (del nuevo al viejo). Solo `vincular_con` (manual) y el
  aprendizaje léxico crean los dos. Al leer, casi todo el sistema la trata como no dirigida
  (`origen = X OR destino = X`).
- **`tipo`** dice qué regla la creó: `co_ocurrencia`, `co_nombre`, `co_semantica`, `pmi_hebbiano`,
  `sinonimo_explicito`, `manual`, `dmn_synthesized`, `rafaga_rememb`, `hipotesis_sueno` y otros. **Solo
  guarda un tipo.** Si dos reglas crean el mismo par, sobrevive el último tipo, salvo que el anterior esté
  protegido (ver §4).
- **`ultimo_uso`** debería decir cuándo se usó por última vez. En la práctica **nace vacío (NULL)** y solo se
  llena cuando otra regla vuelve a tocar el par (ver §5). **No mide uso real.** Que un enlace aparezca en el
  canal 2 o en la búsqueda no lo actualiza.
- **Quién la lee:**
  - el **canal 2** (vecinos que se muestran junto a los resultados, `core/memory/synapses.py:462`);
  - la propagación por cadena (`_evocacion_por_cadena`, `synapses.py:197`);
  - la expansión de contexto (BFS);
  - el cálculo de latentes;
  - el DMN.

### 1.2 Sinapsis latente (`sinapsis_latentes`)

Las columnas están en `core/memory/schema.py:228`:

```
origen, destino, peso_atenuado, saltos, calculado_en, pmi_score, tiene_dim_comun
```

- **Es un caché que se recalcula entero en cada sueño.** `calcular_sinapsis_latentes` hace `DELETE` de
  toda la tabla y la vuelve a llenar (`core/inferencia_transitiva.py:85`). **Una latente nunca se
  convierte sola en directa.** Antes la hormiguita (Gemini) las «confirmaba», pero hoy está fuera de uso.
- **Qué la usa:**
  - **Ranking.** Para cada candidato, el ranking lee `MAX(peso_atenuado)` de cualquier latente que lo
    toque (`core/memory/search.py:2153`) y la suma a la fórmula con peso 0.10
    (`core/memory/scoring.py:338`). **Ese máximo no depende de la consulta** [código]: un recuerdo con una
    latente fuerte recibe el mismo empujón en cualquier búsqueda.
  - **Respaldo para pocas coincidencias.** Cuando hay menos de 3 resultados, entra
    `buscar_por_similitud_latente` (`search.py:1255`).
- Se explica en detalle en el §6.

---

## 2. Cuándo corre cada cosa (línea de tiempo)

```
 aprender (MCP)                          consolidar / sueno (MCP)                fin de sesión (MCP)
 core/mcp_server/write.py               core/memory/consolidation.py:325         core/mcp_server/session.py:68
 ─────────────────────────              ──────────────────────────────           ─────────────────────────
 1 percibir_corto_plazo                  1 fusionar cada recuerdo de corto→largo  1 autoguarda el resumen
   (no crea sinapsis)                    2 auto_vincular(cada uno)       [B1–B4]  2 consolidar_concepto(resumen)
 2 auto_vincular(clave)  L316  [B1–B4]   3 WordNet (clasifica, no enlaza)           → auto_vincular   [B1–B4]
   *solo contra largo_plazo*             4 co-ocurrencia de «sesión»     [B6,B7]  3 si queda algo en corto plazo:
 3 vincular_por_sinonimos L320 [B5]      5 DMN                           [B8]       ciclo de sueño completo
 4 vincular_con → manual  L347 [B9]      6 latentes (recalcula todo)     [§6]
 5 hub + bridges (otra tabla)            7 LTD de recuerdos
                                         8 LTD de sinapsis (×0.95)       [§5]
                                         9 poda de sinapsis < 0.05       [§5]
                                        10 duerme recuerdos ≤ 0.05
                                        11 auto-clustering, PPMI, neurona.practicar

 Además: abrir el cerebro (memory_store.py:172) → DMN [B8] · buscar → ráfaga [B10]
         ensenar_expresion → léxico [B11] · script sleep_cycle.py → hipotesis_sueno [B12]
```

**Consecuencia importante [visto]:** al aprender, `auto_vincular` solo compara contra `largo_plazo`. Por eso
**dos recuerdos aprendidos en la misma sesión no se enlazan hasta consolidar**. En la traza, la sesión 1 no
creó ningún enlace al aprender: todo nació al consolidar.

---

## 3. Las vías de nacimiento (directas)

| # | Vía (tipo) | Dónde | Cuándo nace | Peso al nacer | Sentido | Tope |
|---|---|---|---|---|---|---|
| B1 | `co_ocurrencia` (texto) | `sinapsis.py:104–186` | Jaccard de palabras entre los dos textos ≥ 0.4 **y** cierre triádico | = Jaccard | nuevo→viejo | 30 en total |
| B2 | `co_nombre` | `sinapsis.py:190–244` | Palabras del nombre (≥ 4 letras, sin palabras vacías, al menos 2): la fracción de esas palabras presente en el nombre del otro ≥ 0.3 | 0.7·fracción + 0.3·importancia del destino | nuevo→viejo | 30 |
| B3 | `co_semantica` | `sinapsis.py:246–304` | Solapamiento de **sinónimos** (intersección / el menor) ≥ 0.4. Lee los sinónimos desde `largo_plazo`, así que **al aprender no corre** (el recuerdo está en corto plazo) [código] | 0.6·solapamiento + 0.4·importancia del destino | nuevo→viejo | 30 |
| B4 | `pmi_hebbiano` | `sinapsis.py:306–380` | Palabras que suelen salir juntas en la memoria (NPMI ≥ 0.35, con un mínimo de 3 apariciones; `core/pmi_semantico.py`). Une con recuerdos que contienen la palabra **asociada**, no la propia | 0.75·NPMI medio + 0.25·importancia del destino, si ≥ 0.35 | nuevo→viejo | 15 |
| B5 | `sinonimo_explicito` | `sinapsis.py:440–488` | **Cada** sinónimo declarado se busca con `LIKE '%término%'` en el **nombre** o en los **sinónimos** de cualquier recuerdo activo | **0.9 fijo** | nuevo→viejo | **sin tope** |
| B6 | `co_ocurrencia` (sesión) | `consolidation.py:89–131` | Dos recuerdos consolidados en el mismo sueño que comparten ≥ 2 palabras `\w{4,}` | min(0.9; 0.3 + 0.1·compartidas) | solo c1→c2 | sin tope |
| B7 | `co_ocurrencia` (mensajes) | `consolidation.py:134–190` | Los últimos 50 mensajes de `comunicaciones` × 200 recuerdos activos sin orden: los que comparten ≥ 2 palabras con un mismo mensaje (los 10 primeros) | 0.4 | c1→c2 | 10 por mensaje |
| B8 | `dmn_synthesized` | `dmn_engine.py:33` | Pares de los 40 recuerdos más pesados que comparten una dimensión o, si faltan, ≥ 2 palabras `\w{4,}`, sin enlace previo | **0.30** | c1→c2 | 8 por llamada |
| B9 | `manual` | `synapses.py:172` (`vincular_con`) | Lo decide el agente | 0.5 | **los dos** | — |
| B10 | `rafaga_rememb` | `rafaga.py:313–345` (al **buscar**) | Una palabra de la consulta es **el nombre** de un recuerdo activo y aparece completa en otro resultado con puntaje ≥ 0.5 | 0.6 | palabra→nodo | — |
| B11 | `sinonimo_explicito` (léxico) | `lexical_learning.py:311` | `ensenar_expresion` (lo enseña el agente) | según la confianza | los dos | — |
| B12 | `hipotesis_sueno` | `sueno_vacios.py:186` (solo el script `sleep_cycle.py`) | Búsquedas que no encontraron nada, cerradas por afinidad | **0.08 con `ultimo_uso` = ahora** | — | 50 |

**El cierre triádico** (B1, B6 y B7; `sinapsis.py:99–101`, `_vecinos_comunes` y `_dimensiones_comunes`):
- acepta el par si comparten un vecino, **o** una dimensión, **o** si el nuevo tiene ≤ 5 sinapsis;
- en una memoria grande casi todos los pares pasan (en el snapshot, el 54 % de los pares al azar ya comparten
  un vecino, `mapa_nacimiento_sinapsis/README.md` §3.4), así que **ya no filtra**.

**Una sola transacción:** `auto_vincular` corre B1→B4 en orden. Cada pasada salta los recuerdos que ya enlazó una
pasada anterior (`ya_vinculados`) y al final sincroniza `asociaciones` y marca el SDM como sucio.

---

## 4. Qué pasa cuando el par ya existe (`ON CONFLICT`)

Esta es la parte que más pesa en el resultado final:

| Vía | Peso | Tipo | `ultimo_uso` |
|---|---|---|---|
| B1–B5, B11 | `MAX(viejo, nuevo)` | conserva `manual`, `manual_v7`, `sinonimo_explicito` o `test`; si no, **gana el nuevo** | `COALESCE(viejo, ahora)`: **se llena** |
| B6 | `MIN(0.9, viejo + 0.1)` | no lo cambia | `= ahora` |
| B7 | `MIN(0.9, viejo + 0.05)` | no lo cambia | `= ahora` |
| B8 | `DO NOTHING` / `NOT EXISTS` | — | — |
| B9 | si ya existe, no lo toca (no lo convierte en `manual`) | — | — |
| B10 | `MIN(0.95, viejo + 0.1)` | no lo cambia | `= ahora` |

**B6, B7 y B10 no miran el tipo**, así que **suben también los `manual`** [visto en B6].

---

## 5. La vida después de nacer: refuerzo, olvido y poda

**Lo que sube un peso o llena `ultimo_uso`:**
- los conflictos del §4;
- el refuerzo por feedback (`aplicar_refuerzo_dopaminergico`, `synapses.py:59`, solo con feedback explícito);
- los comandos CLI de recordar por clave (`search.py:2958` y `3075`), que llenan `ultimo_uso` de **todas** las
  sinapsis del recuerdo.

El `recordar` del MCP **no** marca uso en las sinapsis [código].

**Olvido de sinapsis (LTD)** (`consolidation.py:484`):
- `peso ×= 0.95^fracción_de_noche`, solo si `ultimo_uso IS NOT NULL` **y** tiene más de 7 días **y** el tipo no
  es `manual`;
- después, **se borran** las sinapsis con peso < 0.05 (salvo las `manual`).

**Consecuencia [visto + código]:**
- lo que **nunca** se tocó (`ultimo_uso` NULL) **no se olvida jamás**;
- lo que se tocó una vez y quedó quieto, sí;
- **el olvido castiga a lo que alguna vez se confirmó y protege a lo que nunca se confirmó.**

**El tipo protegido es para siempre:**
- `sinonimo_explicito` y `manual` no se pueden reetiquetar;
- `manual` además no decae ni se poda.

---

## 6. El algoritmo de las sinapsis latentes (`core/inferencia_transitiva.py:85`)

1. Recalcula el PMI si el corpus creció más de un 10 %.
2. Hace `DELETE FROM sinapsis_latentes`.
3. **CTE recursiva** sobre `sinapsis` con peso ≥ 0.25 y hasta **2 saltos** (el sueño llama con `max_saltos=2`):
   - `peso_camino = Π(pesos) × 0.7^saltos`;
   - el segundo salto solo se permite si alguno de los dos tramos es `manual`, `manual_v7`,
     `sinonimo_explicito` o `test`, o si ambos son `co_nombre` o `co_semantica`;
   - se descartan los pares que ya tienen enlace directo.
4. **Madurez:**

| Caso | Factor |
|---|---|
| NPMI ≥ 0.05 | 1.0 (madura) |
| dimensión común y NPMI ≥ 0.02 | 1.0 (joven) |
| solo dimensión común | **0.15 (inmadura: existe, pero casi invisible)** |
| nada | se descarta |

5. `peso_final = peso_camino × (1 + 0.5·NPMI + 0.1·dim) × factor`.
6. **Inhibición lateral:** se quedan las 20 mejores por origen.

**[visto]** En la traza:

| Camino | Peso final |
|---|---|
| `sistema_backup` →(sinónimo 0.9)→ `configuracion_servidor` →(DMN 0.3)→ recetas | **0.022** (inmadura) |
| `sangre_donacion` →(«rojo», 0.9)→ salsa → pasta | 0.063 |

---

## 7. Problemas verificados del algoritmo actual

> **Estado al 25-11 (después del ciclo de corrección; ver `docs/Mi neurona en el sistema/correccion_dano_nacimiento/README.md`):**
> - **P6 corregido** en `7e1eb9c`: ninguna regla automática de nacimiento o refuerzo (B1–B7, B10) toca `manual` ni
>   `manual_v7`.
> - **P2 corregido** en `6d64515`: B5 compara por coincidencia exacta, sin subcadenas y sin depender del idioma.
> - **P1 sigue abierto** (2b, pendiente de decisión): reetiquetar cuando el ítem compartido es exacto.
> - **P7 sigue abierto** (cambio 3, pendiente de decisión): un filtro DF rompería la invariancia.
> - **Bug aparte corregido** en `555b06e`: `vincular_con` con espacio después de la coma.
>
> Las secciones 3 y 4 describen las reglas tal como eran **antes** de estos commits. Las diferencias:
> - B5 ahora exige nombre exacto o ítem exacto;
> - B1–B7 y B10 no actualizan un par `manual`.

| # | Problema | Evidencia |
|---|---|---|
| P1 | **B5 reetiqueta enlaces de tema como «sinónimo».** Un sinónimo como «tomate» o «receta» convierte `co_nombre 0.75` y `co_ocurrencia 0.40` en `sinonimo_explicito 0.90`, un tipo protegido para siempre | [visto] traza, sesión 3. Explica la precisión del 9–13 % de `sinonimo_explicito` en el exp. 16 |
| P2 | **B5 compara subcadenas.** `LIKE '%sal%'` también encuentra «salsa» y «salud». No tiene tope | [código] `sinapsis.py:452` |
| P3 | **Los puentes nacen igual que los sinónimos.** «rojo» une sangre ↔ salsa de tomate ↔ semáforo a 0.9, protegido e inmune al olvido. El sistema no distingue entre puente, sinónimo y tema | [visto] traza, sesión 2 |
| P4 | **`MAX` y un solo tipo.** Cuando dos reglas confirman el mismo par, la evidencia **no se suma**: queda el máximo y se pierde de dónde vino | [código] §4 |
| P5 | **El olvido está invertido** (§5): lo nunca tocado es eterno y lo tocado decae | [código] + [visto] |
| P6 | **Los automáticos tocan `manual`** (B6, B7 y B10). Además B6 lo sube en un solo sentido: `manual` A→B 0.60 y B→A 0.50 | [visto] |
| P7 | **Las palabras vacías cuentan** en B6, B7 y el respaldo de B8: `\w{4,}` sin filtro, así que «para», «como», «este» o «desde» valen como palabras compartidas | [código] `consolidation.py:93,148,151`, `dmn_engine.py:89` |
| P8 | **«Sesión» no es sesión:** B6 junta todo lo que había en corto plazo desde el último sueño, aunque sean temas no relacionados | [código] |
| P9 | **El DMN premia a los centrales:** elige entre los 40 más pesados, une por **cualquier** dimensión compartida y además corre cada vez que se abre el cerebro | [código]; [visto] recetas ↔ servidores (exagerado en la traza porque todos comparten dimensiones) |
| P10 | **Aprender no ve la sesión:** los enlaces entre los recuerdos del mismo día solo nacen al consolidar | [visto] |
| P11 | **Varias reglas premian la importancia del destino** (B2, B3 y B4): el rico se hace más rico | [código] |
| P12 | **El cierre triádico ya no filtra** en memorias grandes | mapa §3.4 (snapshot) |
| P13 | **Las latentes dan un empujón que no depende de la consulta** en el ranking | [código] `search.py:2153` |
| P14 | **No hay memoria de rechazo:** lo podado o desvinculado vuelve a nacer en el siguiente sueño | mapa §3.1; exp. 16: renacieron 6–14 de 30 |

---

## 8. Cómo lo hace un cerebro y qué cambiaría (propuesta, **no implementada**)

La biología detallada con sus fuentes está en
`docs/Mi neurona en el sistema/experimento_14_neurona_ordena_canal2/biologia_ciclo_de_vida_sinapsis.md`.
Resumen:

| Cerebro | BioRAG hoy | Cambio propuesto |
|---|---|---|
| **Nace mucho, débil y a prueba.** La mayoría de las espinas nuevas desaparecen (Yang, Pan y Gan 2009) | Nace fuerte (hasta 0.9) y para siempre (P1, P3, P5) | Todo enlace automático nace **a prueba**, débil y con fecha (etiqueta) |
| **La evidencia converge.** Varias entradas que coinciden suman (Hebb, regla de tres factores) | `MAX` y un solo tipo (P4) | Guardar **la procedencia** aparte del tipo y **sumar evidencias independientes** con saturación. No reetiquetar |
| **Etiqueta y captura** (Frey y Morris 1997). Se queda lo que se reactiva dentro de una ventana | No existe | En el sueño, lo que está a prueba se **consolida** si juntó evidencia nueva en N sueños; si no, se atenúa |
| **El sueño baja en proporción** (Tononi y Cirelli) y **por neurona** (Turrigiano) | ×0.95 global solo para lo «usado» (P5) | Homeostasis **por nodo** y multiplicativa (conserva el orden). Se aplica a todos los automáticos, no solo a los que tienen `ultimo_uso` |
| **Poda marcada y con «no me comas»** (complemento y CD47) | Se borra < 0.05 y vuelve a nacer (P14) | Marca persistente: lo rechazado no renace sin evidencia nueva más fuerte. `manual` es intocable (P6) |
| **Sinapsis silenciosas.** Existen sin transmitir y se reclutan cuando el contexto las necesita | Latentes recalculadas de cero, con un empujón fijo (P13) | **Los puentes («rojo», «papa») como silenciosas que se activan por contexto**: experimento 17, neurona asociativa |
| **Lo que se aprende junto se enlaza** (codificación conjunta en el hipocampo) | Solo al consolidar (P10); «sesión» = todo el corto plazo (P8) | Coactivación **en el momento de aprender**, dentro de una ventana real de tiempo |

**Límites que ya decidió Dennys y que esta propuesta respeta (25-11):**
- **U0:** ninguna señal nueva de uso por sinapsis y sin telemetría. Por eso «evidencia» aquí significa
  evidencia **interna**: textos, sinónimos, dimensiones, coaprendizaje y repaso en el sueño. No significa clics
  ni apariciones en el canal 2.
- Nunca borrar recuerdos. Nada automático toca `manual`. El ranking no se toca. Tiempo constante. Funciona desde
  una base vacía.
- F1–F6 (cambiar nacimiento, pesos o poda) **no están autorizados todavía**. Antes de tocar el motor: línea base
  → un solo cambio → medir en copias con criterios fijados de antemano.

**Orden sugerido**, de lo más pequeño y seguro a lo más grande. Cada paso se mide por separado:
1. **Correcciones de higiene:**
   - B5 sin subcadenas y sin reetiquetar (P1, P2);
   - filtrar palabras vacías en B6, B7 y B8 (P7);
   - B6, B7 y B10 no tocan `manual` (P6).
2. **Procedencia aparte del tipo** y suma de evidencias (P4). Es solo un registro: no cambia pesos todavía.
3. **Nacer a prueba + homeostasis por nodo** en el sueño (P5, P3). Requiere simularlo antes en copias.
4. **Memoria de rechazo** (P14). Ya está escrita como regla aparte en
   `experimento_16_protocolo_ns1_sintetico/REGLA_NO_RENACER_TRAS_DESVINCULAR.md`.
5. **Neurona asociativa para los puentes** (experimento 17). Es la única parte donde hace falta «inteligencia»
   que no sale de un algoritmo fijo: decidir, según el contexto, cuándo un rasgo compartido merece el salto.

---

## 9. Reproducir

```
python3 -m venv /tmp/venv && /tmp/venv/bin/pip install -r requirements.txt
PYTHONHASHSEED=1 HOME=/tmp/traza_home /tmp/venv/bin/python \
  "docs/Mi neurona en el sistema/estudio_nacimiento_aprender_consolidar/trazar.py"
```

La salida esperada está en `.../estudio_nacimiento_aprender_consolidar/salida_traza.txt`.

## Documentos relacionados

- `docs/Mi neurona en el sistema/mapa_nacimiento_sinapsis/README.md`: mapa anterior, con mediciones sobre el
  snapshot (§3.1–3.4).
- `docs/Mi neurona en el sistema/experimento_16_protocolo_ns1_sintetico/RESULTADOS.md`: la neurona ordena el
  canal 2 hasta el techo; el límite está en el nacimiento.
- `docs/Mi neurona en el sistema/experimento_17_puentes_y_salto/DISENO.md`: puentes y salto según el contexto.
