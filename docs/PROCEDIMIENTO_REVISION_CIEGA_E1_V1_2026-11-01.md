# Procedimiento de revisión ciega E1 — paquete v1

**Estado de este documento: instantánea histórica de preparación (2026-11-01).** Al redactarse, el paquete aún no se había enviado y no se había iniciado ninguna pasada; ese estado no describe la situación posterior. El informe [Estado de las pasadas exploratorias E1](ESTADO_REVISION_EXPLORATORIA_E1_2026-11-01.md) registra las dos pasadas posteriores como **EXPLORATORIAS, NO INDEPENDIENTES**, los controles realizados y las limitaciones vigentes. Este procedimiento no modifica/cierra el gold ni autoriza E1.

## Artefactos

- Paquete para revisor: `docs/paquete_ciego_revision_semantica_e1_v1.jsonl`
- Manifiesto técnico: `docs/manifiesto_paquete_ciego_revision_semantica_e1_v1.json`
- Generador reproducible: `scripts/preparar_paquete_ciego_e1.py`
- Crosswalk operativo con etiquetas e **textos originales**: `.private_evidence/e1_blind_review_v1/crosswalk_private_r10.jsonl` (directorio `0700`, archivo `0600`; no entregar a revisores ni añadir al control de versiones). El generador crea el archivo en modo exclusivo y falla si ya existe; cada regeneración debe usar una ruta privada nueva para no sobrescribir evidencia. **No es una barrera de cegamiento contra quien tenga el repositorio:** se reconstruye desde el gold público, el generador y la semilla pública.

Hash SHA-256 del paquete: `c6445643cf8750cd85f841c4f3c8b6211c9ecb2a7e5777a43c56764c98112a90`.

## Composición y mezcla

- 33 consultas/casos; se mantienen las 90 asignaciones bajo revisión: 33 de objetivo y 57 de pista.
- 66 presentaciones adicionales: exactamente 2 por caso, muestreadas sin reemplazo entre los otros nodos del mismo episodio, sin filtrar por su rol gold. Total: 156 presentaciones. El mismo nodo de fuente puede aparecer en casos distintos.
- Semilla de mezcla: `20261101`. El generador ordena las entradas de origen, toma las 2 adicionales, mezcla los candidatos dentro de cada caso, mezcla los casos y asigna códigos opacos mediante el mismo PRNG.
- Campos visibles: `case_code`, `question`, `items[].item_code`, `items[].text`. No se suministran IDs de fuente, roles, justificaciones, fragmentos de evidencia ya anotados, respuesta gold, tipo de consulta, expectativa de abstención, estrato ni respuestas de otros revisores.

## Transformaciones exactas del texto presentado

La consulta se copia verbatim. Para cada texto de recuerdo se aplican, en este orden, solo las reglas listadas abajo; el crosswalk privado retiene la cadena original, la presentada y las reglas aplicadas:

1. Regex `^.{1,90}?\b[0-9]{1,3}\s*:\s*`: quitar el título inicial numerado completo y preservar el cuerpo a partir del primer carácter posterior al match. Se aplicó en 147 presentaciones.
2. Regex `\s*This is the primary decision\.\s*$`: quitar esa oración final exacta si está presente. Se aplicó en 4 presentaciones.
3. Regex `\bacción primaria es\b` (sin distinción de mayúsculas): reemplazar el match por `acción es`, preservando el texto de la acción. Se aplicó en 5 presentaciones.

No se traduce, parafrasea, normaliza el caso ni se reescribe el contenido restante. Los códigos de caso/artículo sustituyen los identificadores originales. La selección de adicionales y las transformaciones no alteran el JSONL gold.

## Verificación de fuga

El generador falló cerrado si no hallaba 33 casos, 33/57 asignaciones, 66 adicionales o 90 asignaciones únicas; si no podía elegir dos candidatos adicionales en un caso; o si detectaba IDs `qa_pos_*`, claves/metadatos gold, títulos numerados o frases de rol revisadas en el paquete. Se comprobaron los esquemas visibles (solo las cuatro claves previstas), la unicidad de códigos y los totales 33/156. El manifiesto registra el hash del crosswalk para integridad, no como secreto. El gold, el generador y la semilla `20261101` son públicos; cualquier persona con ellos puede reconstruir el crosswalk. Excluir el archivo privado del paquete/commit reduce exposición accidental, pero **no garantiza el cegamiento** si un agente puede leer el repositorio.

Los títulos numerados se quitan porque varios contienen palabras que declaran el rol de origen. Para las dos pasadas, entregar exactamente estos dos archivos y nada más: el JSONL del paquete y `docs/INSTRUCCIONES_REVISOR_CIEGO_E1_V1.md` (que incluye el hash esperado del paquete). No entregar el manifest, gold, generador, crosswalk, este procedimiento ni esta conversación.

## Plan original de entrega aislada (histórico)

Este apartado registra la propuesta de preparación, no certifica que se haya cumplido. Se propuso preparar **dos entornos frescos fuera del checkout/repositorio** (A y B), sin herramientas de navegación o archivos del proyecto, conectores, historial de conversación, memoria compartida ni acceso al crosswalk. A cada uno se le cargaría únicamente el paquete JSONL y el archivo de instrucciones; las instrucciones verificarían el SHA-256 esperado. El custodio conservaría el manifiesto/crosswalk y las respuestas; cada sesión devolvería su respuesta sin ver la de la otra. Se congelarían/hashéarían ambas salidas antes de cualquier comparación. El informe posterior enlazado arriba registra lo que sí ocurrió y sus límites.

Antes de ejecutar, el custodio debe registrar el identificador de sesión de cada entorno, comprobar que no ve el repo/historial ni la otra salida, y guardar hashes de los dos archivos entregados, prompt y respuesta. Si la plataforma no permite inspeccionar o demostrar esas barreras, no declarar independencia. Si aun así se hicieran pasadas, etiquetarlas **exploratorias, no independientes**, sin calcular acuerdo como si fueran independientes ni usarlas para aprobar/cerrar gold.

**Registro histórico de preparación:** en el turno en que se redactó este procedimiento solo era identificable la sesión actual de Arena Agent Mode, que ya había tenido acceso al gold/etiquetas; no se exponía el ID de una segunda sesión fresca y aislada. En ese momento no se asignó ni inició ninguna pasada. Posteriormente se recibieron dos pasadas; el informe enlazado arriba las identifica como exploratorias/no independientes y deja constancia de que el aislamiento no pudo verificarse.

## Adjudicación y revisión de originales

Después de congelar ambas respuestas, un adjudicador humano bilingüe, elegido por Dennys y preferentemente ajeno a las dos revisiones, conserva primero las opiniones ciegas. El manifiesto informa 147 aplicaciones de eliminación de título, 4 de eliminación de sufijo y 5 reemplazos del marcador de acción: 156 aplicaciones de reglas en total. Algunas presentaciones recibieron más de una regla; en términos de presentaciones únicas, 152 de las 156 fueron transformadas y 4 quedaron iguales. Como esos cambios pueden quitar contexto de encabezado o matiz de rol, el adjudicador deberá cotejar la pregunta, el texto presentado y el original mediante el crosswalk para las 156 presentaciones, registrar cuáles transformaciones son materialmente relevantes y si la lectura cambia al recuperar el original. Para evitar anclaje, la vista de adjudicación debe omitir la etiqueta gold; solo se revela después si hace falta resolver el crosswalk y el razonamiento semántico quedó registrado.

Cada agente devolvería por artículo una categoría provisional (`respuesta principal`, `pista útil`, `neutral`, `irrelevante/perjudicial` o `evidencia insuficiente`), fragmento textual, vínculo con la consulta, duda y confianza. La revisión de agentes no sustituye automáticamente a revisores humanos ni constituye aprobación del gold.

**Estado al cerrar la preparación (histórico, 2026-11-01): pasadas iniciadas: 0; gold modificado: no; campaña E1 ejecutada: no; motor/bases modificados: no.** Las dos pasadas posteriores y su clasificación exploratoria/no independiente se documentan en el [informe de estado posterior](ESTADO_REVISION_EXPLORATORIA_E1_2026-11-01.md). W sigue pendiente.
