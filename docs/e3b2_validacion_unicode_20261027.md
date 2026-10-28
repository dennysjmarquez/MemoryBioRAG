# E3B2 — validación Unicode al guardar y actualizar

**Estado: B2 CUMPLE LAS MEDICIONES.** Las cuatro QA oficiales, la comparación multilingüe y las pruebas completas no muestran regresiones frente a B1.

## Cambio autorizado

- `aprender` y su alias `guardar`, y `agregar_sustantivos`, usan el mismo `_sustantivo_valido` que `recordar` en B1.
- Se valida con NFC para contar de 2 a 15 caracteres, de las categorías Unicode letras, marcas o números, y `_`. El helper no cambia el valor ya normalizado por el flujo existente.
- `agregar_sustantivos` **reemplaza** el campo; no se cambió para fusionar.
- Solo cambian las dos llamadas de validación, el comentario asociado y el import `re` que ya no se necesita: [diff productivo](e3b2_diff_candidato_20261027.patch).
- El normalizador previo y la identidad de escrituras se reservan para B3: por ejemplo, `ガラス` y `カラス` siguen colisionando. No se amplía el alcance a neuronas ni a dimensiones.
- El texto previo de los mensajes de error se conserva: habla de alfanuméricos y `_`, pero no enumera las marcas Unicode que admite la validación.

## Medición multilingüe

La QA directa B2 reproduce **los 132 casos y todas las métricas** de B1, sin diferencias también al invertir el orden de consultas. Búsqueda: activos, límite 5, `ignore_peso_sinaptico=True`, neurona apagada. Es gold sintético, sin revisión independiente.

| Idioma | R@5 B1 → B2 | R@1 B1 → B2 | MRR@5 B1 → B2 | FP B1 → B2 |
|---|---:|---:|---:|---:|
| zh | 7/20 → 7/20 | 7/20 → 7/20 | 0,3500 → 0,3500 | 0/2 → 0/2 |
| ja | 7/20 → 7/20 | 7/20 → 7/20 | 0,3500 → 0,3500 | 0/2 → 0/2 |
| ko | 19/20 → 19/20 | 18/20 → 18/20 | 0,9250 → 0,9250 | 0/2 → 0/2 |
| ru | 20/20 → 20/20 | 19/20 → 19/20 | 0,9750 → 0,9750 | 0/2 → 0/2 |
| en | 20/20 → 20/20 | 20/20 → 20/20 | 1,0000 → 1,0000 | 2/2 → 2/2 |
| es | 20/20 → 20/20 | 20/20 → 20/20 | 1,0000 → 1,0000 | 0/2 → 0/2 |

El brazo MCP de recordar también reproduce **los 132 resultados de B1**: 118 búsquedas ejecutadas y 14 rechazos etiquetados **«pendiente hueco 1»**. Esos rechazos no son búsquedas ni abstenciones. Sus parámetros difieren de la QA directa: MCP usa un pool interno de 15 y el peso sináptico predeterminado. No se presentan como ensayos emparejados con la directa.

Comparación y datos completos: [`e3b2_comparacion_multilingue_20261027.json`](e3b2_comparacion_multilingue_20261027.json), [`e3b2_directa_20261027.json`](e3b2_directa_20261027.json) y [`e3b2_mcp_brazo_a_20261027.json`](e3b2_mcp_brazo_a_20261027.json).

## 80 intentos de guardado nativo

Se usó FastMCP en proceso, con validación de esquema, sin transporte ni agente real. Cada versión tuvo una base temporal inicialmente vacía; para cada caso se realizó realmente `recordar` antes de intentar `aprender`. Se emplearon los mismos 80 recuerdos, sustantivos y cinco puentes sintéticos por idioma, sin espacios artificiales en chino o japonés y sin reintentos. Las frases no tienen revisión por hablantes. La referencia carga una copia exacta del `write.py` de B1; el árbol B2 no se modifica. Las entradas están fijadas por SHA-256 `fed44d525fe037a4ffd596a5b5bda24129ca22727474518b5425dd805954c35c`.

| Idioma | Intentos con búsqueda previa B1/B2 | Guardados B1 → B2 | Primer rechazo en B2 |
|---|---:|---:|---|
| zh | 20/20 | 0 → 0 | 20 puentes |
| ja | 20/20 | 0 → 0 | 20 puentes |
| ko | 20/20 | 0 → 16 | 3 puentes; 1 sustantivo de un carácter |
| ru | 20/20 | 0 → 20 | Ninguno |

Cada guardado B2 está confirmado por la respuesta MCP, el registro de sustantivos en la base, cinco puentes y la consolidación a largo plazo. De las búsquedas previas, ninguna devolvió resultados en B1 y dos devolvieron resultados en B2; ninguna señaló un duplicado exacto. No hubo excepciones ni incoherencias en los 80 intentos. El caso `ko-12` rechaza `물`, una sola sílaba tras NFC. Los tres rechazos coreanos por puentes son `ko-05`, `ko-07` y `ko-20`.

Los puentes se validan antes que los sustantivos: los rechazos zh/ja no demuestran que sus sustantivos pasen o fallen. La escritura y actualización nativas de los cuatro idiomas se prueban además de forma controlada con otros puentes en las pruebas MCP. El primer bloqueo de **cada uno de los 80 intentos** está en [`e3b2_primer_rechazo_80_20261027.md`](e3b2_primer_rechazo_80_20261027.md); las respuestas íntegras están en los JSON de referencia y candidato.

Estas son entradas emparejadas, pero las historias de las bases difieren después del primer guardado exitoso: B1 continúa sin recuerdos y B2 acumula los suyos. La comparación es de guardados, no de recall, ni equivale a la QA directa o al brazo MCP de recordar. La búsqueda previa usa otras etiquetas; por eso puede ejecutarse en casos cuyo término de consulta de B1 sigue en «pendiente hueco 1».

## QA oficiales y pruebas

Las cuatro corridas usan los 921 casos oficiales, copia del snapshot o de la viva, neurona apagada y las mismas opciones de B1. Cada proceso tiene su propio archivo auxiliar temporal. Las primeras corridas se detuvieron antes de obtener métricas al detectarse estado auxiliar compartido; se descartaron y repitieron aisladas. Detalle: [`e3b2_medicion_descartada_20261027.txt`](e3b2_medicion_descartada_20261027.txt). El snapshot y la fuente viva conservaron sus huellas; ver [`e3b2_integridad_final_20261027.txt`](e3b2_integridad_final_20261027.txt).

| Condición | Snapshot R@5 / R@1 / FP, B1 → B2 | Viva R@5 / R@1 / FP, B1 → B2 |
|---|---|---|
| Normal | 100,00 % / 95,31 % / 0 de 40 → iguales | 99,88 % / 93,53 % / 0 de 40 → iguales |
| Ruido `zzqx` | 97,34 % / 88,63 % / 0 de 40 → iguales | 96,63 % / 88,12 % / 0 de 40 → iguales |

No hubo cambios en R@5, R@1, MRR, FP ni en ninguna categoría. Tampoco cambiaron las tablas clásicas, la clasificación honesta, los fallos honestos o el censo temático. Detalle lado a lado: [`e3b2_categorias_oficial_20261027.md`](e3b2_categorias_oficial_20261027.md); datos y problemas comprobados: [`e3b2_comparacion_oficial_20261027.json`](e3b2_comparacion_oficial_20261027.json).

Las corridas normales devolvieron código 0; las dos con ruido, código 1 por el mismo gate clásico de umbral fijo que ya fallaba en B1. No se desactivó el gate. La comparación emparejada con B1 **cumple**. La autoprueba del comparador aceptó una copia idéntica a B1 y detectó una caída artificial por categoría: [`e3b2_autoprueba_comparador_oficial_20261027.log`](e3b2_autoprueba_comparador_oficial_20261027.log).

La [suite completa](e3b2_pytest_final_20261027.log) obtuvo **648 pruebas aprobadas** en 466,16 s; incluye las pruebas MCP con validación de esquema y las del comparador. Las [22 pruebas focalizadas](e3b2_pruebas_mcp_esquema_20261027.log) también aprobaron. Después se corrigió un salto de línea sobrante en el generador de la tabla: el comparador se reprodujo y sus [5 pruebas](e3b2_pruebas_comparadores_20261027.log) aprobaron. Pytest se ejecutó sin fijar `BIORAG_NEURONA=0`, para no apagar las pruebas neuronales.

### Reproducción del guardado nativo

La referencia B1 puede reconstruirse sin modificar el árbol B2. Se necesita Python 3.11 y las dependencias del proyecto:

```bash
D=$(mktemp -d)
git show c0ef030e336f963b7cd913e3693adda311750ea5:core/mcp_server/write.py > "$D/write_b1.py"
PYTHONHASHSEED=0 BIORAG_NEURONA=0 python scripts/evaluar_qa_guardado_nativo_b2.py \
  --write-source "$D/write_b1.py" --sha-write 6b9a997f1ee3edab5c571724059a37bf0aed52ac508bc07e328e8b46adcf202a \
  --salida "$D/referencia.json"
PYTHONHASHSEED=0 BIORAG_NEURONA=0 python scripts/evaluar_qa_guardado_nativo_b2.py \
  --sha-write b188d7430e8e37dcbcde1dcb949cc5255c7d205c1b7c1cc9de3ef726e4545218 \
  --salida "$D/candidato.json"
```

Ambos comandos crean sus propias bases y estados temporales y los destruyen al finalizar; los JSON conservan las respuestas y verificaciones.

## Pendientes sin cambios en esta entrega

1. Los 14 casos de una sola letra o sílaba siguen como **«pendiente hueco 1»**; no se agregan excepciones de anchura.
2. Los puentes zh/ja sin espacios quedan pendientes para otra entrega; el mismo límite también bloqueó tres plantillas coreanas.
3. `core/memory/neurona_examen.py:197`: regex ASCII, reservado para la etapa de neuronas.
4. Los valores de dimensiones puramente no latinos pueden descartarse con aviso; revisar en la etapa correspondiente, sin cambios aquí. La calidad del autovinculado no se evalúa en esta entrega y su tokenizador sigue limitado para escrituras no latinas.
5. B3: identidad y tildes solamente latinas, en entregas separadas para la función MCP y el match exacto del motor. B4: límite de palabra sin perder los fragmentos zh/ja.

No se modifican `VERSION`, `README`, `CHANGELOG` ni se hace merge. Los códigos y resultados crudos se conservan en los archivos `e3b2_*`; sus huellas están en [`e3b2_sha256_20261027.txt`](e3b2_sha256_20261027.txt).
