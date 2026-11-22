# Herramientas MCP de corrección — laboratorio exclusivo

Implementación: `lab_mcp.py` (servidor FastMCP stdio separado) y `approval.py` (servicio transaccional). No se registran herramientas en core/mcp_server. No hay bump de versión ni release.

## Flujo real

1. `registrar_correccion(id, mensaje, observado_en, efectivo_desde)` usa el reconocedor limitado existente y registra propuesta pendiente con evidencia. La identidad proviene de la delegación explícita del anfitrión del proceso.
2. `revisar_correccion(id, nodo_sucesor)` devuelve evidencia, contexto y digest. El nodo sucesor se vincula explícitamente; el prototipo no deduce el contenido correcto solo por nombre de nodo.
3. `confirmar_correccion(id, nodo_sucesor, digest, request_id)` revalida bajo BEGIN IMMEDIATE, inserta claim confirmado, revisión, recibo y arista tipada en una transacción. Cambios de contexto o contenido de nodos desde la revisión producen stale_proposal.
4. `buscar_contextual(consulta, entidad, atributo, alcance, instante, intencion)` ejecuta motor BioRAG real sobre graph.db y conecta el selector. No interpreta automáticamente intención/contexto de cualquier lenguaje natural.

La delegación es por `(entity,attribute,scope)` exacto; el principal NO es parámetro de ninguna tool. Seguridad real limitada al host local que lanza el proceso stdio. No existe autenticación remota de usuarios, pantalla de consentimiento humana ni gestión dinámica de expiración de delegaciones. Cualquier proceso con ese acceso delegado puede aprobar. No desplegar como MCP productivo hasta resolver esa política.

## Atomicidad local, no distribuida

Archivos locales en disco `ledger.db` y `graph.db`, mismo directorio temporal marcado `LAB_ONLY`. SQLite ATTACH, ambos journal_mode=DELETE y synchronous=FULL. El commit usa las garantías multiarchivo de rollback/super-journal de SQLite; no soporta WAL ni filesystem remoto ni se promete atomicidad entre servicios. Observer conserva su propio registro de entrada; el recibo de aprobación es la autoridad, no el campo pending original del observador.

Se prueban rollback por excepción después de escribir ledger y después de escribir grafo, muerte real del subproceso antes de commit y recuperación, repetición del recibo y dos aprobadores concurrentes. No se simula un corte físico de energía ni se acredita durabilidad bajo cualquier filesystem.

## Por qué no sobrescribir sinapsis

El snapshot tiene `PRIMARY KEY(origen,destino)` en `sinapsis` y ya existe una arista manual del par auditado. Cambiar su tipo a sustituye borraría su significado anterior, y una arista sin alcance podría contaminar propagación asociativa.

La copia del grafo recibe **`sinapsis_sustitucion`** con tipo='sustituye', IDs de claims, contexto, fecha y procedencia. La asociación previa queda intacta. Ledger y esta proyección se escriben en el mismo commit; no se usa outbox aquí porque ambos archivos están bajo una única transacción local soportada.

El core actual no consume esta tabla para BFS ni modifica su ranking por ella; el adaptador experimental aplica la evidencia del ledger. Esto es un puente de laboratorio funcional, NO una migración terminada del conectoma productivo. Para integrar se requiere decidir API/esquema de aristas contextualizadas y evaluar la interacción con propagación, índices, backups y múltiples procesos.

## Ejecutar E2E con cliente MCP real

En un entorno con requirements del proyecto instalados:

```bash
python scripts/experimentos/competencia_contextual/e2e_approval_mcp.py \
  --snapshot /ruta/backup-suministrado.db \
  --code /tmp/copia-codigo-sin-env \
  --corpus /ruta/nltk_data \
  --output /tmp/e2e-aprobacion.json
```

El fixture requiere los dos nodos del caso auditado. Crea backup temporal del snapshot, ledger y registro lateral, inicia servidor por stdio, inicializa cliente MCP, lista tools y llama las cuatro herramientas por protocolo. La declaración y el antecedente son fixtures, no una aprobación real del usuario sobre su corpus.

Variables de lanzamiento del servidor: LAB_ROOT, LAB_PRINCIPAL, LAB_GRANTS (JSON de contextos delegados) y LAB_CODE. Todas las bases deben estar en /tmp; se rechaza un directorio sin LAB_ONLY y symlinks de archivos DB. La marca es una protección contra error de operación, NO una frontera de seguridad contra un host malicioso.

## Límites para cierre de v36.2

QA vacía no demuestra eficacia de aprobaciones sobre 921 contextos; E2E dirigido no demuestra comprensión abierta. Falta autenticación/delegación productiva, multivalor, retirada/revocación, migración de grafo tipado e integración con intención/contexto, además de resolver el gate de suite global y doble verificación con copia actual. No declarar release listo solo porque la tool del laboratorio responde correctamente.
