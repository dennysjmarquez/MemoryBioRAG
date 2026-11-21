# Fichas críticas — fuentes primarias, lectura parcial

Las cifras siguientes son **reportadas por los autores** y no reproducidas por BioRAG. No se comparan en un ranking común: cambian modelos, datasets, presupuestos y jueces. Los enlaces versionados y el alcance exacto están en fuentes.json. “No acreditado en lo leído” NO significa “el sistema no lo hace”. Las propuestas para BioRAG son nuestras hipótesis, no resultados del artículo.

## 1. TEM — arXiv:2610.21900v1

Fuente: https://arxiv.org/html/2610.21900v1 — consultados resumen, §§1–5 (chunks 0–3; 4/7).

- **Mecanismo/esquema:** hechos `(subject, relation, object, source_session, source_index)`. Agrupa sujeto normalizado y relación. Mantiene versiones; el máximo índice de sesión determina el estado no histórico. Extrae con modelo congelado y usa memoria de eventos/texto original como complemento.
- **Actualización:** append; etiquetas calculadas sobre grupo completo ANTES de recuperar top-k. Ordena evidencia seleccionada por fuente y etiqueta versiones históricas. No penaliza antigüedad en selección.
- **Conflictos:** valores de la última sesión pueden coexistir sin resolución. Supone actualizaciones monovaloradas ordenadas; índice de fuente no acredita tiempo efectivo del evento. No resuelve preferencias simultáneamente válidas ni informes tardíos con esa regla.
- **Resultados:** 420 preguntas / 600 sesiones / 60 personas. Key-entity hit 75.71–97.62% según modelo; ablar etiquetas sobre iguales hechos/orden da +17.14–55.95 pp. Residencia histórica: 96.67–100% en 60 preguntas. Evidencia 94.05–117.55 tokens de media, sin costo de construcción/embeddings. Experimento con A100 40GB.
- **Límite esencial:** en 1.540 preguntas LoCoMo, etiquetas y no-etiquetas tienen resultados globales similares. TEM-Hybrid vs session-aware RAG da diferencias conservadoras de 7.92/10.58 pp, pero no es una ablación que atribuya esas ganancias solo a etiquetas. Referencia long-context puntúa más alto con mayor presupuesto. Las cotas de puntuación no son intervalos de confianza.
- **Adoptar/adaptar:** estado temporal y procedencia visibles al modelo; evaluar etiquetas independientemente del orden. **No copiar:** “último mensaje = vigente”. Nuestro alcance y tiempo efectivo deben permanecer explícitos. No equivale exactamente a la promoción de selector.py.

## 2. Zep / Graphiti — arXiv:2501.13956v1

Fuente: https://arxiv.org/html/2501.13956v1 — resumen y §2, chunks 0–1 (2/6).

- **Mecanismo/esquema:** subgrafos episódico, entidades semánticas y comunidades. Episodios guardan entrada original; entidades y relaciones derivadas enlazan con fuentes. Extracción y resolución usan LLM, búsqueda de texto y embeddings.
- **Actualización:** deduplicación por entidades y relaciones; aristas con tiempo de creación/expiración de sistema y validez/invalidez en el mundo. Distingue tiempo transaccional y de evento.
- **Conflictos:** un LLM compara nuevas aristas con relacionadas y puede invalidar intervalos solapados; el paper describe prioridad de información nueva para invalidar. Esa política necesita evaluación de autoridad e informes tardíos en nuestro caso.
- **Resultados reportados en resumen:** DMR 94.8% frente a MemGPT 93.4%; LongMemEval mejoras de hasta 18.5% y reducción de latencia frente a sus baselines. No se reanalizaron tablas completas, unidades ni todos los controles: no trasladar esas cifras a BioRAG.
- **Adoptar/adaptar:** dos tiempos y navegación hecho→fuente; índices contextuales para limitar búsqueda de contradicciones. **No copiar:** que la recencia o una extracción LLM autoricen una sustitución.
- **Pregunta para superar en medición, no en marketing:** ¿aprobación auditada + outbox resisten concurrencia/crashes sin perder acceso histórico? Nuestro ledger actual aún no es plenamente bitemporal.

## 3. HippoRAG — arXiv:2405.14831v3

Fuente: https://arxiv.org/html/2405.14831v3 — resumen y §2, chunks 0–1 (2/17).

- **Mecanismo/esquema:** índice de grafo OpenIE extraído por LLM; nodos de frases nominales, relaciones y enlaces de sinonimia por encoder; matriz nodos↔pasajes.
- **Actualización/recuperación:** indexación offline de pasajes; extrae entidades de consulta, enlaza semillas y usa Personalized PageRank para propagación y agregación a pasajes. Imita funcionalmente separación/completado de patrones, no tejido neural.
- **Conflictos/tiempo:** las secciones leídas no establecen aprobación de correcciones ni protocolo transaccional temporal. No asumir que PPR resuelve validez.
- **Métricas:** compara multi-hop QA en MuSiQue/2WikiMultiHopQA, recuperación y costo/latencia frente a iteración como IRCoT. El HTML duplica algunas cifras tipográficas (“2020”, “1010”); NO transcribimos esos números como resultados válidos sin verificar tabla/PDF.
- **Adoptar/adaptar:** probar expansión asociativa para rescatar vigente fuera del pool. Mantener procedencia por pasaje.
- **Riesgo de escala:** PPR global puede variar por enlaces/grado de nodos ajenos; no cumple automáticamente nuestra invariancia. Cualquier experimento necesita subgrafo y presupuesto explícitos, más controles de hubs. Recuperación asociativa y verdad deben seguir separadas.

## 4. MemOS — arXiv:2507.03724v4

Fuente: https://arxiv.org/html/2507.03724v4 — resumen y fragmentos §§1–2, chunks 0,2,4 (3/20).

- **Mecanismo/esquema:** MemCube encapsula contenido y metadatos (procedencia/versionado); propone unificar memoria textual, activaciones/KV y parámetros. Reader/Scheduler/Lifecycle/Operator gobiernan operaciones.
- **Actualización:** ciclo de generación, activación, fusión, archivo y expiración; ámbitos y controles de acceso, con transformaciones entre tipos.
- **Conflictos:** lo leído describe control/gobernanza; no acredita para nuestra implementación atomicidad ledger+grafo+vector ni una política de confirmación humana.
- **Evaluación:** el texto identifica LoCoMo, LongMemEval, PersonaMem y PreFEval. Tablas experimentales completas no revisadas aquí; se dejan cifras sin extraer antes que inventarlas.
- **Adoptar/adaptar:** puertos por responsabilidad y metadatos de permisos/ciclo de vida. **No copiar todo:** acceso a activaciones y pesos no es necesario para el problema de sustitución y reduce portabilidad. No añadir infraestructura pesada sin medición local.
- **Límite de revisión:** falta revisar secciones operativas y evaluaciones completas antes de decidir una dependencia.

## 5. Mem0 — arXiv:2504.19413v1

Fuente: https://arxiv.org/html/2504.19413v1 — resumen y §2, chunks 0–2 (3/10).

- **Mecanismo/esquema:** extracción incremental de hechos desde par de mensajes, resumen e historial reciente; recuperación de memorias similares para decidir operaciones por tool call LLM. Variante grafo con entidades, tipos, tripletas, embeddings y timestamps.
- **Actualización:** en ESTA versión, ADD/UPDATE/DELETE/NOOP. Configuración leída usa 10 mensajes previos y 10 memorias similares; GPT-4o-mini. No extrapolar a versiones actuales del producto.
- **Conflictos:** Mem0g usa resolver LLM para marcar relaciones inválidas en lugar de borrarlas físicamente. No describir todas las variantes como destructivas.
- **Resultados de resumen:** +26% relativo en LLM-as-a-Judge frente a OpenAI; p95 −91% y tokens >90% menos frente a full context. Son comparaciones distintas con denominadores distintos, no +26 puntos de recall.
- **Adoptar/adaptar:** separación extracción/operación y medir latencia/costo de ingesta además de lectura. **No copiar:** dejar que tool call semántico conceda permiso para borrar o confirmar. El agente propone; una política autenticada autoriza.

## 6. A-Mem — arXiv:2502.12110v11

Fuente: https://arxiv.org/html/2502.12110v11 — resumen y §3.1, chunks 0–1 (2/13).

- **Mecanismo/esquema:** nota `m={contenido, timestamp, keywords, tags, contexto, embedding, links}`; Zettelkasten, enlaces entre notas y evolución contextual.
- **Actualización:** un LLM genera atributos y contextualización; nuevas notas disparan búsqueda de vecinas y propuestas de enlaces/evolución. Recuperación usa encoder y conexiones.
- **Conflictos:** los fragmentos leídos no establecen una política suficiente de sustitución confirmada por alcance y tiempo. Similitud/enlace no equivale a contradicción.
- **Métricas:** resumen declara comparación con seis modelos y varias métricas; tablas no inspeccionadas en esta lectura. No se registra cifra de superioridad sin su protocolo.
- **Adoptar/adaptar:** enlaces como pistas, atributos derivados versionados y reconstruibles. Conservar contenido original separado de las interpretaciones del agente.
- **No copiar:** reescribir descripciones previas sin evento de auditoría o dejar que mayor conectividad se convierta en autoridad.

## 7. MemMachine — arXiv:2604.04853v1

Fuente: https://arxiv.org/html/2604.04853v1 — resumen e introducción/tipos, chunks 0–1 (2/11).

- **Mecanismo/esquema:** memoria corta, episodios crudos persistentes y perfil derivado; recuperación contextual expande núcleos con turnos vecinos. Minimiza extracción rutinaria por LLM.
- **Actualización:** fuente episódica preservada, abstracción/perfil en capa distinta. Hay tensiones explícitas compresión↔preservación y recuperación↔contexto siempre presente.
- **Conflictos:** conservar fuente garantiza lo registrado, no verdad objetiva. No se auditó en esta lectura su transacción multi-almacén ni confirmación MCP.
- **Resultados reportados:** LoCoMo 0.9169 con gpt-4.1-mini; LongMemEvalS 93.0% con otra configuración; mejoras de ablations de profundidad/formato/prompts. No comparables directamente con el strict judge de TEM ni R@5 de BioRAG.
- **Adoptar/adaptar:** episodio original como evidencia y vecinos de conversación como pistas; medir costo de preservar detalles. **No copiar:** asumir que expandir siempre mejora, sin presupuesto y trazabilidad.
- **Prueba propuesta:** corrección de frase fragmentada entre turnos con fuente intacta y referencias ambiguas que exijan revisión.

## 8. MemStrata — arXiv:2606.26511v1

Fuente: https://arxiv.org/html/2606.26511v1 — resumen, §4, §§5–7 parcialmente, chunks 0,2,3 (3/11).

- **Mecanismo/esquema:** tripleta estructurada con clave sujeto/relación y objeto mutable; valid_from/valid_to/superseded_by. Texto original para evidencia, detección exacta de duplicados; fallback de sorpresa/LLM para prosa.
- **Actualización:** valor diferente para la misma clave monovalorada sustituye el anterior; mismo valor refuerza; preserva hechos distintos en lugar de fusionarlos indiscriminadamente.
- **Lectura:** recupera activos y **filtra sustituidos**. Es una diferencia real con la invariante BioRAG de no eliminar pistas: no copiar ese filtro general.
- **Resultados:** seis benchmarks pequeños (dos estáticos y cuatro evolutivos con 20–30 escenarios pareados), 7B local. Reporta 0.95–1.00 accuracy evolutiva. Tabla estática domain muestra 0.82 frente a 0.86 de RAG aunque el texto diga “ties”; no convertirlo en igualdad exacta ni cero regresiones. Tabla stale error contiene 0.03 en code_mutation, no cero universal.
- **Limitaciones reconocidas:** extracción ~97% en plantillas estructuradas, ~44% en benchmark de contradicciones de lenguaje más desordenado que los autores ponen en cuarentena. Retención histórica disponible en diseño, pero consultas as-of no evaluadas allí. Verificar bitemporalidad efectiva antes de asumirla por el nombre del ledger.
- **Adoptar/adaptar:** prueba marker-free, tasa de respuesta obsoleta y no confundir similitud con sustitución. **No adoptar como teorema universal:** un AUROC bajo en una muestra concreta no demuestra que cualquier sistema RAG o clasificador sea incapaz. Conservar acceso histórico y anotar, no borrar de la lista.

## 9. Human-Inspired Memory Architecture — arXiv:2605.08538v1

Fuente: https://arxiv.org/html/2605.08538v1 — resumen, §§3–7 y §9/limitaciones parcialmente, chunks 0,1,3 (3/6).

- **Mecanismo/esquema:** hot/warm/semantic tiers, episodios + grafo, sueño por lotes, olvido por interferencia, maduración, reconsolidación y recuperación híbrida. Una capa de datos común facilita gobernanza.
- **Actualización:** consolidación periódica, importancia, TTL, trazas episódicas/semánticas separadas; reducción progresiva de fidelidad y reconsolidación configurable. No todos son compatibles con nuestra preservación.
- **Conflictos:** validación temporal y cuarentena; controles de autoridad. Maduración temporal o frecuencia no acreditan verdad. Leer muchas veces no debe verificar.
- **Resultados:** VSCode retention precision 97.2% con reducción 58%; LongMemEval M-tier 70.1% frente a 71.2% raw RAG a presupuesto 200K, con intervalos solapados. Eso NO prueba equivalencia formal ni no inferioridad por sí solo. S-tier consolidación agresiva baja de 78.4% a 48.4%; presupuestos muy bajos dañan recall.
- **Limitación destacada:** maduración y reconsolidación no quedan empíricamente discriminadas como capacidades por los benchmarks disponibles. No vender seis mecanismos como seis beneficios demostrados.
- **Adoptar/adaptar:** ablations y calibración separada del test; sueño como productor de hipótesis/revisiones. **No copiar:** poda por percentiles globales, TTL o maduración como confirmación; pueden romper historia e invariancia frente a crecimiento.

## 10. CH-HNN — Nature Communications, DOI 10.1038/s41467-025-56405-9

Fuente: https://www.nature.com/articles/s41467-025-56405-9 — resumen, introducción y descripción del método, chunks 0–1 (2/15).

- **Título verificado:** Hybrid neural networks for continual learning inspired by corticohippocampal circuits. No es el paper original de Complementary Learning Systems ni una evaluación de agentes conversacionales.
- **Mecanismo/esquema:** ANN para regularidades y SNN para episodios/conceptos específicos, con metaplasticidad para modular cambios de pesos consolidados.
- **Actualización:** entrenamiento incremental y bucles entre representaciones específicas/generalizadas. El “esquema” es neural, no ledger de afirmaciones SQL.
- **Conflictos:** busca mitigar olvido catastrófico en clasificación incremental, no aprobar hechos contradictorios con procedencia.
- **Métricas/tareas:** task-/class-incremental en variantes MNIST/CIFAR/Tiny-ImageNet/DVS; no extraídas tablas numéricas. No extrapolar ahorro energético neuromórfico a nuestro proceso CPU sin medir.
- **Adoptar/adaptar:** estabilidad-plasticidad y memoria rápida vs generalización lenta como hipótesis para futuros modelos locales. Antes de otra neurona, examen propio, piso/techo y guardianes.
- **No copiar ahora:** nueva pila ANN/SNN ni migración del motor. Un resultado visual incremental no demuestra vigencia correcta en recuperación textual.

## Conclusión transversal

Lo defendible hoy es una arquitectura que separa fuente, interpretación, aprobación, validez, recuperación y presentación. Nada de esta revisión acredita que BioRAG sea superior, universal, consciente o biológicamente equivalente. Para sostener mejoras habrá que medir contra baselines emparejadas, con datos independientes y fallos adversariales, no sumar los mejores porcentajes de papers incompatibles.
