# Propuesta si no está disponible el runner temporal original

Fecha: 2026-11-01. Estado: para revisión del auditor. Sin ejecución de búsquedas reales y sin cambios al motor o a las bases.

## Resultado de la búsqueda del original

No encontré `/tmp/biorag_fk_smallcheck_runner.py` ni otro archivo con ese nombre en `/tmp` o en el árbol de trabajo buscado. Tampoco aparece como archivo versionado en el historial Git disponible. Por tanto, **no recuperé el runner y no puedo proporcionar ni afirmar un SHA-256 de su contenido**: sin los bytes originales no existe un hash verificable. No abrí ni inspeccioné `.private_evidence/`.

No debe tratarse `tests/test_authorizer_supervisor_subprocess_synthetic.py` como si fuera el runner original: es una fixture sintética, ahora con un flujo parent/worker y SQLite `:memory:`.

## Alternativas

### Recomendada: reconstruir un reemplazo mínimo y versionado

No intentar inferir el script original completo desde la evidencia de una corrida. Crear, bajo nombre nuevo y con una versión/hash propios, un runner aislado que implemente solo el contrato revisado:

1. **Asignación privada por ejecución:** raíz modo `0700`, subdirectorio nuevo por `run_id`, `worker_id` nuevo por hijo y rutas exclusivas para evento local, evento primario, respaldo y resultado.
2. **Arranque del hijo:** un `Popen` por worker, descriptor IPC heredado y rutas/identificadores pasados explícitamente. Cerrar en el padre la copia de escritura del pipe.
3. **Registro de guardia:** conservar el primer evento sanitizado; no incluir SQL, parámetros, valores, filas ni locales. En fallo de IPC, preservar localmente antes del envío y abortar.
4. **Supervisión de salida:** procesar cualquier evento recibido; si `select` no marca datos y `poll` ve la salida, drenar el pipe antes de clasificar. Rechazar EOF parcial, eventos pendientes, salida no cero y cualquier fallo de persistencia sin respaldo.
5. **Resultado vinculado:** el hijo escribe exclusivamente un sobre privado JSON (`status`, `run_id`, `worker_id`) mediante `O_EXCL`, modo `0600` y `fsync`. El supervisor acepta `ok` solo con EOF limpio, canal vacío, sin evento local y coincidencia exacta de ambos identificadores. El padre no avanza a otro worker tras cualquier estado no limpio.
6. **Separación del motor:** el runner no copia ni modifica código de `core/`, no toca las bases durante el desarrollo y no se ejecuta contra consultas o recuerdos reales en esta fase.

El contrato de path/result y supervisor está implementado como helper en `scripts/authorizer_supervisor.py`; el flujo integrado sintético está en `tests/test_authorizer_supervisor_subprocess_synthetic.py`. El siguiente paso sería crear el runner nuevo a partir de ese contrato, con su interfaz y supuestos claramente documentados, no afirmar que es el original.

### Alternativa más sencilla: mantener solo el adaptador revisado

Si el auditor no requiere reproducir exactamente el controlador antiguo, conservar el helper y las pruebas subprocess sintéticas como artefacto auditado y posponer la integración real hasta disponer de la invocación exacta, formato de entrada/salida y supuestos del runner. Esta opción reduce riesgo de adivinar rutas o aceptar resultados ajenos, pero **no equivale a integración con el arnés real**.

## Datos mínimos necesarios para reconstrucción fiel

Si se requiere equivalencia con el runner perdido, obtenerlo desde una copia confiable o pedir al usuario que lo aporte junto con su hash previo a cualquier edición. Si no existe copia, solicitar confirmación para escribir un reemplazo nuevo y registrar explícitamente sus diferencias. Antes de una integración real también se necesitan:

- cómo se construye el comando y su entorno;
- formato y canal de entrada del worker;
- esquema del resultado privado exitoso y condiciones actuales de `status=ok`;
- rutas/sandbox de evidencia, timeouts y política de reintento;
- cómo se hace la comprobación de estado antes/después sin alterar las bases.

No se deben inferir ni rellenar esos detalles con datos de una ejecución real.

## Verificación sintética ya ejecutada

Con Python 3.11.2 y SQLite `:memory:`: las **5 pruebas diagnósticas** pasaron y las **8 pruebas subprocess integradas** pasaron en cinco ejecuciones consecutivas. Incluyen carrera `select`/`poll`, cierre normal, mensaje parcial, IPC, fallback de guardado, resultado inválido, resultado antiguo de otro `run_id` y resultado de otro `worker_id`. No son prueba del runner original ni del arnés real.

No ejecutar búsquedas reales hasta que el auditor revise la propuesta y exista autorización explícita. E1 sigue abierto; W pendiente.
