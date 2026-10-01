# Plan técnico — Spec 004: Pre-flight Search (Busca Antes de Aprender)

## Estructura de módulos

| Archivo | Responsabilidad | RFs cubiertos |
|---|---|---|
| `core/memory_store.py` | Métodos centrales de ingestión y actualización (`aprender`, `guardar`, `actualizar`), validación de `busqueda_previa`, orquestación de `vincular_con`. | RF-1, RF-2, RF-3, RF-4, RF-5, RF-6, RF-7 |
| `core/mcp_server/write.py` | Tools MCP de escritura (`biorag_aprender`, `biorag_guardar`, `biorag_actualizar`), esquemas JSON y validaciones de transporte. | RF-1, RF-3, RF-4, RF-5, RF-7 |
| `AGENTS.md` | Documentación operativa obligatoria: Sección 10 con diagrama de flujo, tabla de decisiones y protocolo pre-flight. | RF-8 |
| `tests/test_preflight_busqueda_previa.py` | Suite de tests para validar obligatoriedad de `busqueda_previa=True` y código de error. | RF-1, RF-2 |
| `tests/test_actualizar_sin_restriccion_temporal.py` | Suite de tests para validar actualización sin restricción temporal y modo `sobrescribir=True`. | RF-3, RF-4 |
| `tests/test_preflight_vincular_con.py` | Suite de tests para verificar linking sináptico atómico al aprender. | RF-5, RF-6 |
| `tests/test_preflight_guardar_alias.py` | Suite de tests para verificar paridad del alias `guardar` y MCP con `aprender`. | RF-7 |

---

## Diseño técnico y cambios por módulo

### 1. `aprender` y `guardar` en `core/memory_store.py`
- **Firma**:
  ```python
  def aprender(
      self,
      concepto: str,
      contenido: str,
      sustantivos_clave: str | None = None,
      dimensiones: str | None = None,
      sinonimos: str | list[str] | None = None,
      bridges: list[str] | None = None,
      busqueda_previa: bool = False,
      vincular_con: list[str] | str | None = None,
      **kwargs
  )
  ```
- **Validación Primera (Fail-Fast)**:
  ```python
  if busqueda_previa is not True:
      raise ValueError("BUSQUEDA_PREVIA_REQUERIDA: Debes realizar una búsqueda previa...")
  ```
- **Procesamiento de `vincular_con`**:
  Tras insertar el nuevo nodo, iterar sobre los conceptos dados y llamar a `self.establecer_asociacion(concepto, destino)` capturando silenciosamente nodos no encontrados.

### 2. `actualizar` en `core/memory_store.py` y `core/mcp_server/write.py`
- **Eliminación de restricción temporal**: Remover cualquier cálculo que valide `now - creado_en <= MAX_AGE`.
- **Soporte de `sobrescribir: bool = False`**:
  - Si `sobrescribir is False`: Enriquecer o concatenar contenido según comportamiento por defecto.
  - Si `sobrescribir is True`: Ejecutar `UPDATE` directo sobre `contenido`, recalculando dimensiones y actualizando FTS5.

### 3. Capa MCP (`core/mcp_server/write.py`)
- Exponer los nuevos parámetros en `biorag_aprender`, `biorag_guardar` y `biorag_actualizar` con sus respectivas descripciones.
- Retornar diccionarios de error estructurados `{"status": "error", "codigo": "BUSQUEDA_PREVIA_REQUERIDA", ...}` cuando la validación falle.

---

## Estrategia de testing y verificación

1. `tests/test_preflight_busqueda_previa.py`:
   - Verificar rechazo con `busqueda_previa=False` (o ausente).
   - Verificar éxito con `busqueda_previa=True`.
2. `tests/test_actualizar_sin_restriccion_temporal.py`:
   - Crear nodo con fecha antigua y verificar actualización exitosa.
   - Verificar reemplazo completo de contenido con `sobrescribir=True`.
3. `tests/test_preflight_vincular_con.py`:
   - Crear nodo pasando `vincular_con=["nodo_existente"]` y verificar existencia de arista en `sinapsis`.
   - Verificar robustez cuando se pasa un nodo inexistente.
4. `tests/test_preflight_guardar_alias.py`:
   - Probar idéntico comportamiento en `guardar()` y las funciones wrapper de MCP.
5. Ejecutar suite completa `pytest tests/ -q` garantizando 0 regresiones.
