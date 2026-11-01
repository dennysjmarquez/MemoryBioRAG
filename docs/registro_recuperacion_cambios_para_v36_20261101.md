# Registro recuperado de cambios para la futura v36 — 2026-11-01

## Objetivo y estado

Dennys pidió que ninguna mejora de los trabajos llamados informalmente 35.1, 35.2 y 35.3 se pierda al preparar la documentación de v36. Este registro preserva la pista del plan `docs/plan_publicacion_v36.md` y la contrasta con GitHub. Es **un inventario inicial, no el changelog definitivo ni evidencia de que v36 esté lista**. No modifica README, VERSION, CHANGELOG, motor ni bases.

La decisión vigente es **no publicar ni etiquetar v35.1–v35.3**: sus cambios se explicarán juntos dentro de la sección de v36, sin fingir que hubo releases intermedios. La consulta `git ls-remote --tags origin 'refs/tags/v35*' 'refs/tags/v36*'` devolvió `refs/tags/v35.0` y ninguna etiqueta v35.1–v35.3 o v36 en el remoto consultado. Es una comprobación puntual del repositorio remoto, no una declaración sobre otros posibles repositorios.

## Cambios históricos a recuperar en el relato de v36

Los títulos y hashes fueron cotejados mediante la API de commits de GitHub; por tratarse de commits históricos en una copia Git superficial, esta consulta **no demuestra por sí sola que cada efecto siga intacto ni su rendimiento actual**. Antes de publicar se contrastará cada afirmación con el código final y las pruebas correspondientes. Los nombres v35.1–v35.3 de la primera columna son referencias de trabajo, no versiones publicadas.

| Referencia histórica | Cambio que debe conservarse y verificarse | Commit fuente |
|---|---|---|
| 35.1 | Escala: cambios para reducir dependencia del tamaño de la memoria, con `BIORAG_ESCALA=1`; documentar sus condiciones y límites, sin prometer invariancia universal. | [`f317a9a`](https://github.com/dennysjmarquez/MemoryBioRAG/commit/f317a9afd6cc00c2896bea8f85fcf993c1f05a07) |
| 35.2 | Concept Hub a escala: índice y competencia entre hubs/recuerdos; explicar también configuración de fábrica y mediciones realmente realizadas. | [`3cce403`](https://github.com/dennysjmarquez/MemoryBioRAG/commit/3cce40308344f73adcd1ec3a71030af38af15756) |
| 35.3 | Consideración acotada de palabras de función en el Concept Hub, sin descartar por principio conectores que puedan contener información. | [`ff571fb`](https://github.com/dennysjmarquez/MemoryBioRAG/commit/ff571fb310d88388fdb79d517f8dac13ed904662) |
| 35.3 | Ajuste del multiplicador del puente de ángulo ingenuo en el hub a escala. | [`d776a49`](https://github.com/dennysjmarquez/MemoryBioRAG/commit/d776a49074c82d904a0eff58d3bf62ec15fb0b74) |
| QA | Mostrar información de la neurona de ranking y comparar sus resultados con la fórmula. | [`daffa6f`](https://github.com/dennysjmarquez/MemoryBioRAG/commit/daffa6fdf49202ecf9e505856871d8f804c10dc4) |
| QA | `--con-neurona`: preguntar antes de entrenar cuando corresponde y usar la existente cuando ya está disponible. No implica autorización actual para entrenar. | [`e70daaf`](https://github.com/dennysjmarquez/MemoryBioRAG/commit/e70daaf0002a97d3a2c39861412afe9db8ce4255) |
| Diagnóstico | Herramienta para investigar fallos de QA sobre copia; actualización para señalar posible contaminación. | [`eab3f68`](https://github.com/dennysjmarquez/MemoryBioRAG/commit/eab3f68f3d45f2d4b13bb93d79e0851c204b7284), [`6a2662f`](https://github.com/dennysjmarquez/MemoryBioRAG/commit/6a2662fe43e7534f9fb20248910e23d074dd4ad4) |
| Diagnóstico | Herramienta de inspección del hub y su competencia, con reporte del tipo de puente. | [`c2a8681`](https://github.com/dennysjmarquez/MemoryBioRAG/commit/c2a86812d7cb01db9592bfb80f1e5d13db3ffdfc), [`0cc1fed`](https://github.com/dennysjmarquez/MemoryBioRAG/commit/0cc1fedc1ef4d36405a0584f19748695cbccee94) |

La tabla recupera los elementos ya identificados en el plan, **no afirma que agoten todos los commits**. Antes de publicar habrá que revisar el rango completo entre la etiqueta v35.0 y el commit final aprobado para incorporar cualquier cambio omitido, documentación y compatibilidad MCP. No incluir candidatos revertidos como mejoras activas: por ejemplo E2c/E2e se investigaron y rechazaron.

## Otros elementos para la publicación

- **E1/E2/E3 históricos:** QA honesta, diagnósticos de ruido y temática e identidad multilingüe, diferenciando evidencia histórica, investigación rechazada y código efectivamente incorporado. El PR #12 se fusionó, pero E3 completo aún no está acreditado como cerrado: ver `docs/estado_e3_retorno_plan_20261101.md`.
- **E4 y modularización fase 2:** pendientes de verificación y cierre antes de redactar la entrada final. Mantener puentes de compatibilidad, cambiar un paquete por vez y comparar con línea base, conforme al plan.
- **Versionado y compatibilidad:** `VERSION` sigue en v35.0 y `pyproject.toml` conserva 34.0.0. Python ≥3.11 consta actualmente en `pyproject.toml`, clasificador, instalador y matriz CI; se deben comprobar los cuatro en el momento de publicar, sin asumir que el documento histórico todavía describe el estado actual.
- **Evidencia final:** reportar las cuatro QA y categorías, con/ sin ruido y neurona según el protocolo correspondiente; identificar cada base, tamaño, configuración y pérdidas. No mezclar QA históricas con la campaña asociativa E1, no dar 95 % como recall actual ni atribuir a la neurona diferencias entre bases distintas. No acortar el README; el documento maestro completo se hará al final del proyecto, no como condición para este inventario.
- **Seguridad:** no subir datos privados ni pesos; no alterar originales. Las modificaciones de motor, el entrenamiento y la campaña E1 requieren autorización específica. PR desde la rama de esta sesión; merge final solo con OK explícito.

## Control focal al recuperar el estado

En el HEAD anterior a este registro (`57dcf71`), se ejecutaron sobre bases temporales sintéticas las pruebas `tests/test_sustantivos_clave_schema.py`, `tests/test_normalizar_sustantivos_clave.py` y `tests/test_validacion_bridges_unicode_b3.py`: **43 passed**. Python 3.11.2, NumPy 2.4.6, pytest 8.4.2, neurona de ranking apagada, síntesis DMN y PPMI desactivados. Es un control parcial de esquema/normalización/validación; no es una de las cuatro QA, no mide el sistema completo ni reemplaza el entorno fijado para la auditoría final. No hubo entrenamiento ni acceso a bases reales.
