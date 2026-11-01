# Auditoría mecánica de la vista de revisión E1 — 2026-11-01

## Alcance

Verificación de integridad y correspondencia de los artefactos sintéticos; **no es revisión semántica humana, adjudicación ni evaluación de BioRAG**. La fuente reproducida fue el commit publicado del operador `60722742daa7c7f77b9dbc5a3c2a2dd26ffd646b`, en una copia temporal aislada con el generador, la fixture E1 y las instrucciones. Se usaron copias privadas descargadas de Drive de la vista, el paquete y la cola. Los originales, respuestas, crosswalk y resultados individuales no se incluyen en este documento.

La rama de trabajo propia todavía apunta a `f8c2b166b6f13cd7bbbdffb13135d3d68354b8e0`; el commit del operador se obtuvo mediante fetch y es descendiente de ese commit, pero no se integró al checkout: hay modificaciones locales y archivos no rastreados superpuestos. En el cálculo de hash de blobs, 18 de 21 archivos modificados coinciden con la versión del operador y tres difieren; 348 de 349 archivos no rastreados superpuestos coinciden y uno difiere. Las cuatro diferencias están en `.gitignore`, `AGENTS.md`, `CONSTITUTION.md` y `docs/Mi neurona en el sistema/vision_como_recuerda_biorag/README.md`. La copia local contiene ampliaciones en los tres últimos; la versión publicada tiene tres líneas adicionales en `.gitignore`. No se sobrescribieron ni descartaron esos cambios. Además, al consultar el remoto de la propia rama `arena/6459e2d0-memorybiorag`, su punta era `368415062abe7e8a94b3cd76b0bdf566e8ec3b95`, 158 commits por delante del HEAD local. No se hizo commit, push, reset ni sincronización que pudiera sobrescribir cambios. El análisis usa el commit identificado, no supone que el árbol de trabajo sea idéntico al del operador.

## Controles reproducidos

- Paquete generado en la copia aislada y copia descargada de Drive: SHA-256 coincidente `c6445643cf8750cd85f841c4f3c8b6211c9ecb2a7e5777a43c56764c98112a90`.
- Vista privada descargada: SHA-256 `eaf0a27d8eedb63b179d69f971ab2ddee90edee6041f097c7ec01e3158a5d10c`.
- Cola privada descargada: SHA-256 `54dcc7f1b40aa69d5a06c890160d1834d7c284b2bd5a92dcac725cbe1489cff0`.
- La reproducción contiene 156 pares de códigos únicos; coincide exactamente con los 156 pares del paquete. Las 28 claves de la cola están dentro del conjunto del paquete. Las preguntas y textos presentados reproducidos coinciden con el paquete para los 156 pares.
- Se verificó mediante extracción programática que los textos presentado y original de la vista corresponden al crosswalk regenerado para los 156 pares. Esto comprueba correspondencia textual, **no** si la vista altera la lectura semántica, ni si los encabezados inducen sesgo, ni que un humano los haya revisado.
- 152 presentaciones cambiaron y 4 quedaron iguales. Aplicaciones por regla, con solapamiento: 147 títulos, 5 marcadores de acción primaria y 4 sufijos. De los 28 desacuerdos, 27 presentaciones cambiaron; de los otros 128 pares, 125 cambiaron. Una comparación mecánica no evalúa materialidad.

## Control mecánico por elemento — continuación

Se reconstruyó cada transformación con una implementación separada que vuelve a aplicar las tres regex registradas, en el orden previsto. Los 156 resultados y las reglas aplicadas coinciden con el crosswalk regenerado. Se guardó un registro privado por par de códigos, sin textos fuente ni campos de gold: `google_drive/e1_revision_control.jsonl`, SHA-256 `583946c1b26283b02b815f43ef11c2c8f2374872ad411178dc55329161fadaaf`, permiso local `0600`. Una copia fue cargada a la carpeta privada de revisión en Drive y su SHA-256 devuelto por Drive coincide. No se alteraron los registros de las pasadas ni la cola.

El control clasifica automáticamente los 147 títulos eliminados según palabras del propio encabezado: 54 con palabras que pueden sugerir un rol de respuesta o pista, 61 con palabras que pueden sugerir una clasificación negativa y 32 con otros encabezados. Es una clasificación literal para localizar posibles anclajes, **no un juicio de relevancia ni una etiqueta de los recuerdos**. Otras reglas también pueden aportar señales de rol. Las 156 entradas del registro figuran explícitamente con impacto semántico no evaluado y revisión humana pendiente. La coincidencia de una regla o un título no prueba por sí misma que cambiaría una respuesta ni autoriza descartar una pista.

## Estado y límites

Las dos pasadas son exploratorias/no independientes. Los 28 desacuerdos tienen lecturas preliminares de agente; siguen pendientes. El orden reportado de lectura inicial y cotejo no está demostrado independientemente por sus hashes. Las 128 coincidencias tampoco son automáticamente correctas, ni una garantía de que no cambie el significado al recuperar el original.

El cotejo semántico humano de los 156 pares y las reglas sobre conocimiento externo y preguntas vagas siguen abiertos. Los textos originales pueden contener encabezados que sugieren roles; su presencia constituye riesgo de anclaje, no una etiqueta verdadera. La inspección de un agente con acceso a la fuente y al repositorio no es una revisión ciega ni reemplaza automáticamente al adjudicador humano previsto.

No se cambió el gold, no se ejecutó la campaña E1 y no se modificaron motor ni bases en esta comprobación. No se entrenó ninguna neurona. W permanece pendiente.

## Sincronización posterior

Después de esta auditoría, Dennys autorizó actualizar el checkout. La rama local avanzó por fast-forward a `69a1768984554cf08411cb7487601549a80245f9`, coincidiendo con su punta remota en ese momento. Se preservaron los 384 archivos locales en un respaldo verificado y un stash; se restauraron los informes que no existían en el merge. La conciliación y sus límites constan en `docs/auditoria_merge_operador_e1_20261101.md`. Las referencias anteriores al checkout anterior son históricas, no el estado actual.

## Advertencia preexistente del checkout

`git diff --check` sobre todos los cambios locales señala un marcador residual `>>>>>>> Stashed changes` en `core/concept_hub.py:1008`. El mismo texto aparece en la versión publicada del operador `6072274`, dentro de un docstring; no se ha verificado que tenga efecto funcional. No se ha reparado ni se han ejecutado pruebas del motor en esta comprobación. El informe nuevo pasó su propia comprobación de espacios; el resultado global no puede reportarse como limpio.
