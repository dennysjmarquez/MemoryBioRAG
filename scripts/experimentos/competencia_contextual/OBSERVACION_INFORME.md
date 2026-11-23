# Primera interacción en observación — resultado

## Estado
**Puente experimental construido, sin integración ni aplicación productiva.** Se mantiene el ledger/selector anteriores sin modificaciones en esta fase. No hay una nueva neurona ni entrenamiento, ni interpretación libre de conversaciones.

Se añade:
- `correction_language.py`: adaptador español de gramática composicional limitada, con offsets de evidencia original y abstención explícita.
- `observation.py`: registro SQLite lateral idempotente con actor/rol, texto, instantes y propuesta. Distingue observación de fecha efectiva. No tiene método de aplicar ni confirmar correcciones al ledger real.
- `demo_observation.py`: demostración ejecutable y verificación del snapshot por backup temporal.
- `test_observation.py`: 17 pruebas nuevas, además de las 23 anteriores intactas.
- `resultados_observacion.json`: salida reproducible de mensajes sintéticos, sin contenido privado de recuerdos.

## Interacción observada

Mensaje de fixture en lenguaje natural:

> Corrijo: el puerto del servicio alfa en producción es 8443, no 8080.

Se extrajo:

```text
entity: servicio alfa
attribute: puerto
scope: producción
old: 8080
new: 8443
status: pending_confirmation
confirmed: false
production_action: none
```

Cada campo incluye offsets exactos dentro del mensaje recibido. El antecedente `8080` debe existir, estar confirmado y ser único en ese contexto. No se elige por similitud. Si no existe o hay ambigüedad/conflicto, se pide revisión.

Resultado de observación:

```text
actual: port-old
would_if_confirmed: port-new
ledger_unchanged: True
production_ranking_unchanged: True
```

`actual` es la decisión del selector con el ledger de fixture ANTES de la corrección, no una nueva salida de BM25. `would_if_confirmed` ejecuta el mismo selector sobre un backup en RAM donde se supone la confirmación, exclusivamente para comparar. La propuesta real permanece sin confirmar. Los mismos candidatos y scores se conservan; el ranking productivo no se escribe.

## Copia aislada del caso diagnosticado

Mensaje sintético de actualización:

> Actualizo: la versión del proyecto en DEV pasa de 32.4 a 36.1.

```text
proposal: pending_confirmation
confirmed: False
actual: version_actual_biorag_v32_4_20261007
would_if_confirmed: version_actual_biorag
ledger_unchanged: True
production_ranking_unchanged: True
source_unchanged: True
```

Se abrió en solo lectura el snapshot suministrado y se usó `sqlite3.backup()` a una DB temporal. Quick check OK; se verificó la presencia de los nodos del caso y el hash SHA-256 idéntico antes/después:

`07a77c801eaa56750627e1c831de91a65e6448da25e4803b86d3ae4e2446c55e`

La demo usa los cinco candidatos de la búsqueda real registrada en la fase previa (`resultados_motor.json`), **no ejecuta una búsqueda nueva**. El antecedente confirmado se carga al ledger de fixture; la propuesta nueva sí se extrae del mensaje. Los mensajes y los instantes lógicos 1/2/3 son datos de ensayo, no declaraciones reales del usuario ni fechas inferidas del corpus. No se considera que esto haya confirmado la versión instalada o el release Stable.

## Validación ejecutada

```text
python -m unittest discover -s scripts/experimentos/competencia_contextual -p 'test_*.py' -v
Ran 40 tests in 0.223s
OK
```

Se mantienen las 23 pruebas originales y se añaden 17. Las nuevas comprueban:
- extracción de corrección y actualización, offsets y cinco dominios sin vocabularios de dominio en el parser;
- abstención ante preguntas, citas, discurso reportado, incertidumbre, estructura ambigua o contexto faltante;
- propuesta sin autoridad para roles assistant/tool/system; rol declarado NO equivale a autenticación de transporte;
- fecha efectiva no supuesta desde la fecha del mensaje, y actualización futura no aplicada antes;
- antecedentes ausentes, ambiguos o contradictorios sin vinculación adivinada;
- evento idempotente; reutilizar el mismo ID con otro contenido produce error;
- reconstruir el observador conserva la propuesta registrada;
- repetir simulaciones no cambia ledger ni registro ni confirma nada;
- consultas históricas sin reordenamiento y candidato ausente como retrieval_gap;
- igualdad exacta con 10.000 afirmaciones ajenas y 30 eventos ajenos;
- rechazo a conexiones de memoria/ledger como registro de interacciones, tiempos no finitos y texto excesivo;
- rechazo temprano de estructura adversarial con muchos delimitadores.

No se ejecutó la suite oficial QA 921 en esta fase: el mecanismo NO está conectado al pipeline y no se afirma cero regresiones de una integración. Ese gate permanece obligatorio y pendiente. No se tocaron ni relajaron tests, umbrales o reglas del motor productivo.

## Alcance real y limitaciones

1. Reconoce dos familias de enunciados completos de español. Es un parser conservador, no comprensión semántica abierta. Expresiones fuera de la gramática o con partículas ambiguas se abstienen aunque una persona pudiera entenderlas.
2. La intención/contexto de la consulta posterior sigue siendo estructurada. No se añadió un router por palabras “hoy”/“actual”.
3. No hay aprendizaje por exposición. La declaración de una corrección registra una hipótesis con evidencia textual; no acredita su veracidad.
4. Se exige fecha efectiva explícita para simular; el sistema no interpreta todavía “desde ayer”, husos horarios ni anáforas (“eso”, “lo de antes”).
5. No se autentican identidades ni se verifican fuentes externas: eso corresponde al transporte/política futura. No usar la cadena role='user' como seguridad productiva.
6. Un contexto no encontrado no se resuelve con aliases aproximados. Es preferible revisión a corregir otra entidad por error.
7. Parser O(L) con tamaño acotado y presupuesto estructural; grounding usa índice por contexto. El backup de simulación cuesta O(N) y es SOLO de laboratorio, no un diseño aprobado para consultas productivas.
8. Propuestas pendientes pueden quedar desactualizadas: no existe un flujo de aprobación productivo; antes de implementarlo habrá que revalidar antecedentes, autoridad, vigencia y concurrencia transaccionalmente.

## Reproducción

```bash
python -m unittest discover -s scripts/experimentos/competencia_contextual -p 'test_*.py' -v
python scripts/experimentos/competencia_contextual/demo_observation.py
# Solo snapshot de backup, jamás DB viva:
python scripts/experimentos/competencia_contextual/demo_observation.py \
  --snapshot /ruta/snapshot.db --output /tmp/observacion.json
```

## Próximo hito
Ampliar con un conjunto de mensajes humanos anotado independientemente (incluidos casos que deben abstenerse), medir errores de vinculación y cobertura del adaptador. Después diseñar confirmación/revalidación y el adaptador de interacción MCP. No conectar escritura ni ranking productivo mientras estos pasos y los gates de regresión estén pendientes.
