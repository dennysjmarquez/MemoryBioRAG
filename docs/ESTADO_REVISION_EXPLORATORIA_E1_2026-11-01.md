# Estado de las pasadas exploratorias E1 — 2026-11-01

## Estado y alcance

Se completaron dos pasadas del paquete ciego por ChatGPT y Gemini. Las dos se registran estrictamente como **EXPLORATORIAS, NO INDEPENDIENTES**: no se pudo verificar el aislamiento de las sesiones, por lo que no son anotaciones independientes, no demuestran acuerdo entre revisores independientes y no determinan la corrección de ninguna etiqueta gold.

Gemini indicó que no podía verificar por sí mismo el SHA-256 del paquete. Dennys comprobó en su equipo que la copia descargada coincidía con el hash esperado. La respuesta de ChatGPT dice que su sesión usó herramientas locales para leer/verificar el paquete; dado que no se pudo verificar el aislamiento ni el cumplimiento literal de las restricciones de herramientas, esta circunstancia también se conserva como limitación, no como evidencia de independencia.

**E1 sigue abierto.** No se modificó ni cerró el gold; no se ejecutó la campaña, no se entrenaron neuronas y no se modificaron motor o bases.

## Integridad y controles reproducidos

Los dos archivos se descargaron desde la carpeta privada de Drive `BioRAG - Revisión ciega E1`; no se asumió que su filesystem fuera compartido. Se calcularon localmente los SHA-256 sobre los bytes descargados y coinciden exactamente con los hashes congelados comunicados:

| Archivo privado | SHA-256 verificado | Tamaño |
|---|---|---:|
| `revision_1.txt` | `a6d51434c15c6507d6028b2a747239b213d7afa4973a15fc490a0493b415454a` | 48.465 bytes |
| `revision_2.txt` | `efc8bf399fe7ea4f95d026c3188bfbec9e7fe27b55972ed7541d5fce31e668e8` | 61.336 bytes |

El paquete local también se verificó: SHA-256 `c6445643cf8750cd85f841c4f3c8b6211c9ecb2a7e5777a43c56764c98112a90`, igual al hash esperado. Las copias temporales descargadas se eliminaron después de la comprobación. Las respuestas completas permanecen en Drive privado y **no se incorporan a este repositorio ni a este informe**.

Comprobación automática local, sin exponer el contenido de las respuestas: cada archivo contiene 33 códigos de caso y 156 códigos de elemento; los 156 códigos de elemento son únicos en cada archivo y ambos conjuntos coinciden. Se extrajeron 156 categorías en cada pasada y se reprodujo la comparación: 128 categorías coinciden y 28 difieren. De esas diferencias, 26 son `pista indirecta` en una respuesta frente a `respuesta directa` en la otra; las dos restantes son una inversión de esas categorías y una diferencia `neutral`/`pista indirecta`. Estos resultados describen exclusivamente las salidas: **no prueban independencia, no son un voto y no dicen qué categoría es correcta**.

La carpeta de Drive contiene además `vista_adjudicacion_sin_gold.md`. Se comprobó que la vista incluye los 33 códigos de caso y los 156 códigos de elemento, y que presenta texto original y presentado. La vista no debe considerarse una garantía de cegamiento semántico: algunos encabezados de los originales sugieren roles. Esos encabezados son parte del texto fuente y un riesgo de sesgo, **no una etiqueta verdadera ni evidencia para asignar automáticamente un rol**.

## Criterio humano provisional y cuestión de rúbrica

Dennys aportó dos observaciones provisionales para la consulta “¿Cómo espaciar los reintentos?”:

1. El recuerdo que menciona timeout y reintento, pero no la espera, tiene relación y puede servir como pista para continuar buscando; por sí solo no explica cómo espaciar intentos. No descartarlo por no ser respuesta directa.
2. El recuerdo que menciona `backoff` puede ser respuesta directa para quien conoce la técnica, pero no explica tiempos ni configuración. La explicación del término se dio al auditor antes de recibir este criterio, así que pudo influir. Se conserva como **pregunta abierta de rúbrica**, no como etiqueta humana definitiva: ¿cuánto conocimiento técnico externo puede usar quien clasifica, frente a lo que el texto permite inferir por sí solo?

Hasta que Dennys resuelva esa regla, no se debe convertir ninguna de estas observaciones en gold ni usar la mera familiaridad del evaluador con una técnica para ocultar la diferencia entre “nombra un concepto relacionado” y “da información suficiente para contestar”.

## Siguiente paso propuesto: adjudicación acotada, no cuestionario de 156 preguntas

1. **Congelar el registro exploratorio.** Mantener por separado ambas respuestas originales, sus hashes y sus categorías; no fusionarlas ni calcularlas como acuerdo independiente.
2. **Construir una cola privada de discrepancias** a partir de los 28 códigos que difieren, conservando pregunta, dos textos presentados, justificaciones y dudas. Empezar por las 26 diferencias pista/respuesta directa; tratar aparte la inversión restante y la diferencia neutral/pista. No adjuntar etiquetas gold.
3. **Revisar los 156 elementos una sola vez para el efecto de transformación**, como ya exige el procedimiento. Para cada elemento, el adjudicador registra primero su lectura de la pregunta y el texto presentado; después coteja el original y registra si el cambio altera materialmente la lectura. Marca explícitamente si el encabezado original sugiere un rol y evita tomarlo como verdad automática. Los 4 elementos sin transformación también se cotejan y se registran como iguales; no se presumen revisados por omisión.
4. **Pedir criterio a Dennys de uno en uno y solo cuando haga falta.** Se le presenta un caso concreto con pregunta, texto presentado y original, categorías y razones de las dos pasadas, y el punto exacto de decisión; se ocultan los roles gold y se evita revelar el encabezado original antes de guardar la primera lectura del adjudicador. Se registra su respuesta como criterio provisional para esa regla, no como decisión masiva ni cierre de gold. Si el caso no requiere aclaración humana, se anota la justificación y se sigue sin interrumpirlo.
5. **Llevar un log de adjudicación** con código opaco, desacuerdo, evaluación de transformación, riesgo de encabezado, regla aplicada, consulta/respuesta de Dennys si la hubo, estado abierto/resuelto y justificación. La adjudicación queda separada de los juicios exploratorios y del gold.
6. **Dejar explícito el umbral de conocimiento externo** antes de resolver los casos donde el término técnico (`backoff`) cambia la categoría. Hasta entonces, conservarlos como discrepancia abierta; no elevar una explicación aportada después de la pasada a evidencia de aislamiento o independencia.

Este flujo no requiere que Dennys responda 156 preguntas: la revisión de originales se completa sistemáticamente, pero su intervención se reserva para los desacuerdos o reglas ambiguas que realmente necesiten una decisión de criterio.

## Comprobaciones y límites de esta actualización

- Drive: localizados y descargados los dos archivos congelados desde la carpeta privada; ambos SHA-256 coinciden byte por byte con los valores registrados arriba.
- Paquete: SHA-256 local coincide con el hash esperado.
- Estructura y comparación: 33 casos/156 elementos por pasada; códigos completos, únicos y coincidentes; 128 coincidencias, 28 diferencias, con desglose descrito arriba.
- Vista de adjudicación: 33 casos/156 códigos, con original y presentado; se mantiene la advertencia de sesgo por encabezados de rol en los originales.
- No se leyó ni publicó contenido de `.private_evidence/`; no se añadieron respuestas completas a Git.
- No se modificaron fixture ni gold; no se ejecutó E1, no se entrenaron neuronas, y no se tocaron motor o bases.
- Las pasadas se mantienen como exploratorias/no independientes; aislamiento no verificado.
