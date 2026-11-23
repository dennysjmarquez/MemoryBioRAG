# Sonda MCP sintética: pista de hub y reformulación

## Propósito y alcance

Comprobar en una sesión MCP real y aislada si una pista de una palabra que coincide con un bridge permite recuperar su canónico y si una segunda consulta predefinida con dos palabras lo recupera. La expectativa era observar ambas llamadas sin filtrar resultados ni tocar el motor. Es una sonda de mecanismo, no una campaña E1, QA oficial, medición de recall general ni evaluación completa de agente + cerebro. La segunda consulta fue diseñada con conocimiento de la fixture; no demuestra que un agente pueda descubrirla autónomamente. La primera llamada aislada tampoco sigue todo el protocolo de descomposición y paráfrasis del prompt: se usó intencionalmente para probar el caso de una palabra.

## Método

- Código probado: `a93d3acc7ad8f74e8e4a4c26f508d06a13d4c3de`; Python 3.11 en entorno temporal con `requirements.txt`.
- Script exacto: `scripts/auditar_mcp_hub_sintetico.py`, SHA-256 `9d4a467f715535e2836be11a9d9485398eb47c56295c1f7375ea384f80f14343`. Ejecutar desde la raíz con `PYTHONPATH=.`, dependencias instaladas y carpeta `google_drive/auditoria_neuronas/` existente. La salida `mcp_hub_case.json` no debe existir: el script rehúsa sobrescribirla. Ante errores no garantiza persistir respuestas parciales; revisar también el log de ejecución. La prueba reportada completó todas las llamadas.
- Servidor stdio MCP real mediante `scripts/qa_stdio_server_intuicion.py`. Base nueva dentro de `TemporaryDirectory`, sin fuente real ni copia de datos vivos; reloj fijo, `PYTHONHASHSEED=0`, neurona de ranking, WordNet, PPMI, síntesis DMN y guardado heurístico apagados; auto-paráfrasis y auto-dimensiones MCP apagadas, `BIORAG_NO_LOG=1`, hub `escala`. No se entrenó ninguna neurona ni se modificó motor. La base temporal se eliminó al terminar.
- Una búsqueda previa vacía, `aprender` con un nodo inventado, cinco bridges y `consolidar`; después, las tres consultas que siguen, en la misma sesión y base. No son ensayos independientes; las lecturas pueden mutar la base. `asociaciones_max=0` solicita asociaciones completas; límite de resultados 10, sobre una fixture de un solo nodo. Sin `deep` en las consultas de recuperación.
- Pista escogida: `alborada`, presente en el bridge `semilla alborada` y ausente del nombre/contenido del canónico. Se consultó el hub y luego `recordar` con esa palabra; la reformulación predefinida fue `semilla alborada`. Ambas consultas `recordar` incluyen `sustantivos_clave` correspondientes.

## Resultado literal resumido

| Llamada | Resultado |
|---|---|
| `concept_hub_buscar(query="alborada")` | `match=true`; canónicos incluyen `nodo_demo` |
| `recordar(query="alborada")` | `total=0`, 0 resultados |
| `recordar(query="semilla alborada")` | `total=1`, 1 resultado, `nodo_demo` presente; `sinapsis_creadas=[]` |

Las seis llamadas terminaron sin error MCP; `aprender` y `consolidar` devolvieron `status=ok`. El resultado pone de manifiesto una diferencia observable entre la consulta directa al hub y `recordar` para esta fixture y esta configuración. La reformulación recuperó el nodo, pero **no prueba por qué**: podría entrar por más de una ruta. Tampoco establece que una consulta de hub y la de `recordar` usen idéntico camino interno, ni que se haya probado aislamiento causal del filtro. El control local anterior en `docs/auditoria_busqueda_hub_filtro_una_palabra_20261101.md` es evidencia separada de un posible filtro, no autorización para parchearlo ni prueba de impacto en una base real.

## Evidencia y siguiente decisión

Respuestas sintéticas completas y argumentos, incluidos errores de protocolo si los hubiera: `google_drive/auditoria_neuronas/mcp_hub_case.json`, SHA-256 `2a7b71ae76c7b329005f64ecb9ec64b46941975c492d050b214ee5153ab95c80`; copia privada Drive ID `1H4Ql8HBZvm10kO31DgWhvA3rGkxdO1D7`, checksum cotejado. Salida de proceso en `google_drive/auditoria_neuronas/sonda_mcp_hub.log`. Solo hay una ejecución; no se afirma repetibilidad ni ausencia de efectos fuera de lo observado.

Siguiente paso: investigar con controles adicionales el origen de la diferencia y la recuperación de pistas por el conjunto agente + cerebro, en bases sintéticas aisladas. Un cambio de motor sigue necesitando diff, autorización y medición de pérdidas. Esto no cierra B4a ni el resto de E3, no modifica B4b descartado y no habilita E1, E4, fase 2 o publicación v36 como si ya estuvieran completadas.
