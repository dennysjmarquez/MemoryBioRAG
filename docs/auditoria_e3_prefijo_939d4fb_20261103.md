# Auditoría E3: matriz de prefijo `939d4fb`

Se revisó el commit `939d4fb5aef9c70d997c2832776a59cca594df93`, hijo de `6369951`; añade solo un informe y un runner, sin cambiar `core/`. Se reprodujo el mismo runner del operador en checkout aislado y fixture sintética, con `PYTHONHASHSEED=0` y QCR desactivado por el propio arnés. `py_compile` pasó. Sin embargo, `git diff --check 939d4fb^ 939d4fb` **falló** por espacios finales en las líneas 3 y 4 del informe; el operador reportó que pasaba. Es una corrección documental menor, no fallo de motor.

## Reproducción

Cinco casos, baseline e instrumentado: 20 llamadas MCP contando aperturas, cero flags de error de búsqueda, las cinco comprobaciones automáticas pasaron. Por comprobación adicional, los JSON parseados completos coincidieron en los cinco pares; no hubo cambios en los snapshots observados en apertura/búsqueda. La igualdad se limita a estos casos y snapshots. No se ejecutó suite completa ni se accedió a la evidencia privada del operador.

Los datos reproducidos muestran que el guardia recibió y eliminó las dos coincidencias internas de subcadena, conservó `react` → `reactive`, y eliminó la pista de paráfrasis en el caso de consulta de un token. En la consulta de dos tokens, con QCR desactivado, el objetivo se devolvió y el guardia no recibió al objetivo. La traza registra que la rama de paráfrasis también encontró el objetivo. Esos dos casos **cambian la consulta**, no aíslan únicamente el guardia, y no hay brazo correspondiente sin paráfrasis; no prueban que la variante fuera la causa exclusiva del resultado multitémino. El caso `culo`/`artículos` se verificó leyendo la evidencia, pero no tiene una aserción propia en `checks`; `all_checks_pass` no lo garantiza automáticamente.

El checksum de nuestra salida íntegra fue `e9bb67120a271d0e1756f3f36137ee88e93f986c78d5e05bd322da94e6b9bd3d`, distinto al reportado para `run04` (`0a74b457a17a862d7bf7a62e18ba90e7a723a2f20f36ef8779831a1329e33f58`). Sin acceso a aquel archivo no se conoce el motivo, no se afirma equivalencia byte a byte. Evidencia de la réplica en Drive privado ID `1MX6hlMr1vKlkK-zVtHK6AlDe_UIJUU4Y`, archivo `auditoria_e3_939d4fb_20261103.tar.gz`, SHA-256 `5f4dbb77b4315cfec567fb745cb7b466f2169b760e6af6b43b1c2707fc69eb02`.

## Historia y límites

Inspección de `57e232e` confirmó incorporación de la función `PALABRA_COMPLETA` y comentarios sobre límites de palabra y `culo`/`artículos`, conservando rutas semánticas exentas. `d310ae9` cambió el filtro final anterior de palabra completa a prefijo. Se verificó también el diff de `b373946`: cambió la selección literal de una igualdad a exclusión de una lista de orígenes no literales. No se revisaron exhaustivamente todos los hitos. No concluir que cualquier substring rechazado sea irrelevante para una necesidad real; el fixture controla un ejemplo, no mide utilidad humana ni frecuencia real.

El reporte del agente local sobre sus propios scripts sintéticos no fue reproducido aquí. Su explicación posterior de que un resultado ausente fue por top-k tiene carácter de hipótesis mientras no muestre trazas de esa etapa y origen. En una sonda independiente de la función SQLite actual, `react`/`reactor` y `todo`/`todopoderoso` devolvieron 1; es resultado del predicado aislado, no garantía de resultados de la búsqueda completa. E3 sigue abierto y no se autoriza cambio del motor ni E4.
