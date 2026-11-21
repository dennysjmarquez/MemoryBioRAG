# Estado de ejecución — fase aprobación/búsqueda/QA

## Hecho
- Diseño del contrato MCP documentado en PLAN_APROBACION_QA.md. Todavía no hay herramienta de aprobación publicada ni escritura aprobada a grafo/core.
- Adaptador search_adapter.py implementado fuera de core. Soporta shadow/apply experimental, conserva tuplas y scores; fallback visible ante error. Necesita puerto explícito de resolución contextual.
- Test del adaptador: shadow, promoción estable, passthrough y fallback. Suite experimental total 41/41 PASS.
- Código efectivo de core/config/middleware y scripts oficiales copiados a /tmp/biorag-phase3/code, sin .env.local ni DB viva.
- Snapshot oficial snapshots/qa_escape_qcr_20260811.db copiado por backup SQLite. Quick check OK. Casos oficiales contados: 921.
- QA oficial lanzada en proceso background (baseline primero, selector después); seed/configuración constantes. No se cambiaron gates ni casos. Logs, trazas y métricas en /tmp/biorag-phase3/results.

## Pendiente: no declarar resultado todavía
La baseline seguía en ejecución en el último control, con 662 llamadas de búsqueda trazadas. No equivalen necesariamente a 216 casos completados. No se conoce aún el gate ni el recall final. La variante selector se ejecutará después de la baseline, incluso si el gate devuelve fallo, para poder comparar honestamente.

Proceso Arena: qa-aislada-de-921-casos-baseline-410e19d4

El worker ejecuta scripts/evaluar_qa.py mediante runpy, envolviendo buscar_por_frase solo en su proceso. Baseline registra sin alterar; variante conecta adaptador apply con ledger vacío y resolución contextual ausente. Esto mide conexión sin interferencia, NO generalización de correcciones aprobadas. Ambas condiciones deben exponerse en el informe final.

## Reanudación
1. Consultar proceso background con get_process_output wait_for=exit; evitar lanzar duplicados.
2. Revisar baseline/selector-exit.txt, *-metrics.json, *-failed.jsonl y trazas. Si hay error de ejecución, diagnosticar antes de medir.
3. Comparar orden, scores y membresía de cada llamada, fallos y recalls global/por categoría. Separar gate absoluto de diferencia emparejada. Informar cualquier baseline que ya falle sin relajar umbrales.
4. Persistir informe resumido y manifest de entradas; no incluir DB, trazas privadas ni logs con recuerdos.
5. Ejecutar caso dirigido con contexto confirmado por el adaptador y comparación contra snapshot suministrado. Probar invariancia del adaptador con crecimiento antes de aprobarlo (la invariancia del selector anterior ya tiene tests; no sustituye medición de esta fase).
6. Diseñar e implementar unidad transaccional experimental para aprobación y outbox con tests de concurrencia/fallos antes de exponer MCP.

Estos archivos de estado, contrato y adaptador se incluyen para revisión en el mismo commit de la biblioteca de investigación. No hay cambios a master/core por estas acciones. Los temporales y procesos pueden no sobrevivir a otra sesión; si faltan, no asumir que acabaron exitosamente. Los archivos nuevos del laboratorio sí quedan en el workspace.
