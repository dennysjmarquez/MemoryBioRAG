# Uso del MCP como agente, sobre una copia (2026-11-25)

## Qué se hizo

Se levantó el servidor MCP real (`mcp_server.py`, stdio) con:
- `BIORAG_PATH=/tmp/agente/cerebro.db`, una copia del snapshot público;
- `HOME=/tmp/agente/home`, para no tocar ningún `~/.biorag`.

Un cliente MCP llamó a las herramientas igual que lo haría un agente:
- `introspeccion` y `recordar`;
- `aprender` con `vincular_con`;
- `consolidar` tres veces, `desvincular` y `feedback`.

Después de cada paso, `estado.py` tomó una foto de la tabla `sinapsis` y la comparó con la anterior.

Garantías:
- No se tocó la DB viva (en esta sandbox ni siquiera existe), ni el motor, ni los tests.
- El snapshot quedó intacto: sha256 `104dd2902aaf…` antes y después.

## Archivos

| Archivo | Para qué |
|---|---|
| `cliente_mcp.py` | Una llamada por proceso: `python cliente_mcp.py <tool> '<json>'`, `list` o `schema <tool>` |
| `sesion.py` | Varias llamadas en **una** sesión (un solo servidor), como un agente real. `["_sleep", s]` hace una pausa |
| `estado.py` | Foto y diferencias de `sinapsis`: nuevas, borradas, pesos que suben o bajan, manuales tocados |
| `aprender1.json`, `p1–p3.json` | Los pasos exactos que se ejecutaron |

## Lo que se vio (verificado; cada línea es una salida real)

1. **Abrir el cerebro escribe sinapsis.** El constructor de `SQLiteMemoryBioRAG` llama a
   `sintetizar_sinapsis_dmn` (`core/memory_store.py`, L171–177).
   - Cada proceso que abre la memoria crea **8 `dmn_synthesized`** entre los 40 recuerdos de mayor
     peso. Pasa aunque la herramienta sea `introspeccion`, cuya descripción dice «No modifica nada».
   - En una misma sesión ocurre una sola vez. Con 35 s de pausa (cuando el `idle release` ya actuó)
     no se repitió.
   - Cada arranque de un agente, del CLI o de un script suma 8 más.
2. **`vincular_con` sobre un par que `auto_vincular` acaba de crear queda a medias.**
   - `aprender` creó primero `mapa→hormiguita_estado_real_50… pmi_hebbiano 0.63`. Después,
     `vincular_con` solo agregó el sentido inverso como `manual`.
   - En `recordar`, el canal 2 de ese recuerdo **muestra el vínculo explícito como `pmi_hebbiano
     0.63`, en tercer lugar, no como manual**. El otro vínculo explícito sí aparece como manual.
     La hipótesis del §3.2 del README queda confirmada en este caso.
3. **Ruido de la pasada 2 (`co_nombre`), con datos reales.**
   - En la primera consolidación, el recuerdo `reactivación_feedback_protocolo` (que estaba en corto
     plazo en el snapshot) nació enlazado con **26 recuerdos que solo comparten la palabra
     «protocolo» o «feedback»**.
   - La razón: una palabra de tres da overlap 0.33 ≥ 0.30.
4. **Pares sin relación desde las comunicaciones.**
   - En una consolidación con recuerdos de sesión nacieron 27 `co_ocurrencia` de peso 0.4 entre
     recuerdos que no tienen nada que ver con lo guardado. Por ejemplo,
     `tema_dark_2026_en_visor_de_markdown ↔ principio_liderazgo_accion`.
   - Vienen de mirar los últimos 50 mensajes contra 200 recuerdos activos sin orden.
5. **El uso no queda registrado.**
   - `recordar` con `asociados=true` muestra asociaciones pero **no marca `ultimo_uso`** en ninguna:
     0 estrenadas.
   - `feedback(util=true)` sube el peso del recuerdo pero **no refuerza ninguna sinapsis**, ni
     siquiera dentro de la misma sesión justo después de `recordar`. El refuerzo de aristas depende
     de `last_parent_map`, que solo se llena en la evocación por cadena.
   - Hoy casi no existe una señal de «esta sinapsis sirvió».
6. **Lo desvinculado no siempre renace.** En este flujo (`desvincular`, otro `aprender` del mismo
   concepto, `consolidar`), el par borrado **no** renació: el PMI se recalculó y el tope de 15 de la
   pasada 4 lo dejó afuera. En la prueba directa del README renacieron 15 de 40. El renacimiento
   depende de la situación; no es seguro.
7. **Una sola consolidación del snapshot dejó 851 → 506 recuerdos activos.** 240 recuerdos tenían
   peso ≤ 0.1, y una noche de LTD con el multiplicador 1.5 los baja de 0.05. Es el diseño
   (`dormido` no es borrado), pero alguien que pruebe el snapshot lo va a notar.
8. **El snapshot no pasa `core.lifecycle`.** Tiene 62 violaciones de clave foránea en
   `nodo_grupos_semanticos → largo_plazo`, así que la copia no puede marcarse como «al día». Por eso
   el MCP repite el aviso `BIORAG UPDATE AVAILABLE`. Afecta solo a la copia, no a la DB viva.
