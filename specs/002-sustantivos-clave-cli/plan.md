# Plan Técnico — Spec 002: Sustantivos Clave en CLI (biorag.py)

## Estructura de módulos

- `biorag.py` → Interfaz CLI de terminal. Responsable de:
  - Extracción y normalización de flags (`--sustantivos-clave`, `--sustantivos`, `--syn`, `--cat`).
  - Validación *fail-fast* con salida pedagógica descriptiva y exit code `1`.
  - Implementación de subcomandos `guardar`, `buscar`, `sustantivos`, `agregar_sustantivos`, `corteza`, `listar`, `estado`.
  - Mapeo de alias amigables (`sustantivo`, `agregar-sustantivos`, `asignar_sustantivos`).
  - Actualización del docstring de ayuda interactiva (`help` / `--help`).
  *(Cubre: RF-1 a RF-20)*

- `tests/test_biorag_cli.py` → Suite de tests de integración para la interfaz CLI. Responsable de:
  - Verificar exit codes (`0` para éxito, `1` para errores).
  - Verificar captura de stdout/stderr de cada comando.
  - Verificar robustez frente a orden de argumentos y casos límite.
  *(Cubre: RF-1 a RF-20, RND-1 a RND-3, CL-1 a CL-4)*

---

## Modelo de datos interno

No requiere cambios en el esquema SQLite de la base de datos (el esquema de 4 columnas en `largo_plazo` y `largo_plazo_fts` ya fue completado en Spec 001).

### Estructuras auxiliares en memoria (`biorag.py`)
```python
# Resultado de parseo de argumentos
ParsedGuardarArgs = {
    "clave": str,
    "contenido": str,
    "sinonimos": str,
    "categoria": str,
    "sustantivos_clave": str
}

# Constantes de mensajes pedagógicos
MSG_AYUDA_SUSTANTIVOS = """..."""
```

---

## Algoritmos y lógica interna

### 1. Capa de Sanitización y Seguridad OWASP (`_sanitizar_entrada_cli`)
- **Objetivo:** Prevenir inyecciones (SQL/FTS5/Command), ataques de control chars y desbordamiento de memoria (OWASP A03:2021).
- **Mecanismos:**
  1. **Limpieza de Caracteres Peligrosos:** Eliminar bytes nulos (`\x00`), caracteres de control ASCII (`[\x01-\x1f\x7f]`), y normalizar espacios redundantes.
  2. **Validación de Límites de Tamaño:** Longitud de concepto ≤ 200 chars, sustantivo ≤ 15 chars (mínimo 2), contenido ≤ 100,000 chars. Si se excede, fail-fast con exit code `1` y mensaje claro.
  3. **Whitelisting Alfanumérico para Sustantivos:** Aplicar regex estricto `^[a-zA-Z0-9_]+$` por término tras normalización y remoción de tildes.
  4. **Parametrización SQL y Escapado FTS5:** Prohibición absoluta de f-strings en queries SQLite (`cursor.execute(..., (param1, param2))`) y sanitización de operadores booleanos FTS5 conflictivos en búsquedas.
  *(Cubre: RF-21, RF-22, RF-23, RF-24)*

### 2. Extractor Robusto de Flags Desordenados (`_extraer_flag_valor`)
- **Problema:** En terminal, el usuario puede invocar `guardar --sustantivos-clave "a,b" clave contenido` o `guardar clave contenido --sustantivos-clave "a,b"`.
- **Algoritmo:**
  1. Escanear la lista de tokens `args`.
  2. Identificar pares `[flag, valor]` para `--sustantivos-clave`, `--sustantivos`, `--syn`, `--cat`.
  3. Sanitizar los valores extraídos a través de `_sanitizar_entrada_cli`.
  4. Si un flag no tiene valor siguiente o el valor es otro flag que inicia con `--`, reportar error de sintaxis descriptivo (*fail-fast* con exit code `1`).
  5. Retirar los pares `[flag, valor]` y consolidar los tokens restantes como argumentos posicionales (`clave` y `contenido`).
  *(Cubre: RF-1, RF-2, CL-2, CL-4)*

### 3. Flujo de Validación y Almacenamiento en `cmd_guardar`
1. Extraer y sanitizar flags con `_extraer_flag_valor`.
2. Verificar presencia de `--sustantivos-clave` (o `--sustantivos`).
   - Si falta: Imprimir bloque pedagógico (Definición de núcleo temático + regla 1-5 sustantivos + ejemplo concreto) y retornar exit code `1`.
3. Validar y normalizar sustantivos usando `normalizar_sustantivos_clave(raw_sustantivos)` importada desde `core.memory_store`.
   - Si falla validación: Capturar `ValueError`, imprimir mensaje guiado y retornar exit code `1`.
4. Invocar `cerebro.percibir_corto_plazo(concepto=clave, contenido=contenido, sinonimos=sinonimos, categoria=categoria, sustantivos_clave=sustantivos_norm)`.
5. Imprimir resumen visual enriquecido con lista de sustantivos y conteo. Retornar exit code `0`.
*(Cubre: RF-3, RF-4, RF-5)*

### 4. Flujo en `cmd_sustantivos` y `cmd_agregar_sustantivos`
- **`cmd_sustantivos`:**
  1. Sanitizar y normalizar concepto recibido a minúsculas.
  2. Consultar con sentencia parametrizada `SELECT sustantivos_clave FROM largo_plazo WHERE concepto = ?`.
  3. Si no existe registro: Imprimir error y retornar exit code `1`.
  4. Si existe y está vacío: Imprimir mensaje de nodo legado con sugerencia y retornar exit code `0`.
  5. Si tiene sustantivos: Imprimir lista formateada y retornar exit code `0`.
- **`cmd_agregar_sustantivos`:**
  1. Sanitizar concepto y validar sustantivos con `normalizar_sustantivos_clave`.
  2. Verificar existencia del concepto en `largo_plazo` con query parametrizada. Si no existe, retornar exit code `1`.
  3. Ejecutar `UPDATE largo_plazo SET sustantivos_clave = ? WHERE concepto = ?` con query parametrizada.
  4. Imprimir confirmación y retornar exit code `0`.
*(Cubre: RF-6 a RF-13)*

### 5. Enriquecimiento de `cmd_corteza`, `cmd_listar`, `cmd_buscar` y `cmd_estado`
- **`cmd_corteza` / `cmd_listar`:** Incluir la columna `sustantivos_clave` en la consulta `SELECT` y formatearla en la salida visual (`[sust1, sust2]`).
- **`cmd_buscar`:** Sanitizar la frase de búsqueda, enviar `sustantivos_clave` a `cerebro.buscar_por_frase(..., sustantivos_clave=...)` e incluir en salida `--completo` la línea de núcleo temático. Si no hay resultados, mostrar tip de búsqueda.
- **`cmd_estado`:** Ejecutar consulta parametrizada de conteo y reportar porcentaje de cobertura.
*(Cubre: RF-14 a RF-19)*

---

## Decisiones técnicas y arquitectura

- **Decisión 1**: Reutilizar directamente la función central `normalizar_sustantivos_clave` de `core.memory_store` en el CLI en lugar de implementar una lógica de parseo separada.
  - **Alternativa descartada**: Validar con expresiones regulares ad-hoc en `biorag.py`.
  - **Por qué**: Garantiza paridad estricta y única fuente de verdad entre el Core, el MCP y el CLI.
  - **Restricción de constitución**: Pilar 7 (Validación Fail-Fast) y Regla Invariante de Memoria.

- **Decisión 2**: Salida pedagógica explicativa en stdout con exit code `1` ante omisión o error de formato.
  - **Alternativa descartada**: Lanzar un traceback de excepción de Python sin capturar.
  - **Por qué**: Los usuarios y agentes de terminal necesitan mensajes legibles de inmediato para saber cómo formular el comando sin leer trazas de error internas.
  - **Restricción de constitución**: Pilar 3 (Fallos Visibles) y Pilar 6 (UX-First).

- **Decisión 3**: No requerir reinicio de base de datos ni scripts de migración adicionales para el CLI.
  - **Alternativa descartada**: Crear un script intermediario de migración para el CLI.
  - **Por qué**: El core ya maneja la coexistencia y los triggers SQLite actualizan el índice FTS5 automáticamente en cada `UPDATE`.
  - **Restricción de constitución**: Pilar 1 (Cero Regresiones).

---

## Contrato de interfaces externas

### Comandos de Línea de Comandos (CLI)

```bash
# 1. Guardar nuevo recuerdo (Obligatorio --sustantivos-clave)
python3 biorag.py guardar <clave> <contenido> --sustantivos-clave "termino1,termino2" [--syn "sin1,sin2"] [--cat categoria]
# Exit code: 0 (éxito) | 1 (error de validación con guía pedagógica)

# 2. Consultar sustantivos clave
python3 biorag.py sustantivos <concepto>
# Exit code: 0 (encontrado o legado) | 1 (no encontrado)

# 3. Asignar o actualizar sustantivos clave
python3 biorag.py agregar_sustantivos <concepto> "termino1,termino2"
# Exit code: 0 (actualizado) | 1 (error de validación o concepto inexistente)

# 4. Buscar recuerdos con sesgo temático
python3 biorag.py buscar <texto> [--sustantivos-clave "termino1,termino2"] [--completo] [--asociados]
# Exit code: 0

# 5. Ayuda pedagógica
python3 biorag.py help
```

---

## Estrategia de tests

### Suite: `tests/test_biorag_cli.py`
Se implementarán pruebas automatizadas ejecutando los métodos de `biorag.py` con captura de `sys.argv`, `stdout` y códigos de salida:

1. **Test `test_cli_guardar_exito`**: Verifica almacenamiento con `--sustantivos-clave` y `--sustantivos`, confirmando exit code `0` y salida formateada (RF-1, RF-2, RF-3).
2. **Test `test_cli_guardar_sin_sustantivos_muestra_guia`**: Verifica que al omitir el flag se retorne exit code `1` y el mensaje contenga la explicación pedagógica del núcleo temático (RF-4).
3. **Test `test_cli_guardar_sustantivos_invalidos`**: Verifica que sustantivos con caracteres inválidos, menos de 1 o más de 5 fallen con exit code `1` (RF-5).
4. **Test `test_cli_sustantivos_consulta_y_legado`**: Verifica consulta de nodo con sustantivos, nodo sin sustantivos y nodo inexistente (RF-6, RF-7, RF-8, RF-9).
5. **Test `test_cli_agregar_sustantivos`**: Verifica actualización exitosa, concepto inexistente y términos inválidos (RF-10, RF-11, RF-12, RF-13).
6. **Test `test_cli_buscar_con_sustantivos_y_completo`**: Verifica que `buscar --sustantivos-clave` ejecute y que `--completo` imprima sustantivos (RF-14, RF-15, RF-16).
7. **Test `test_cli_corteza_listar_estado_visibilidad`**: Verifica que `corteza`, `listar` y `estado` incluyan los sustantivos y el porcentaje de cobertura (RF-17, RF-18, RF-19).
8. **Test `test_cli_seguridad_owasp_sanitizacion`**: Verifica rechazo de bytes nulos `\x00`, caracteres de control, conceptos > 200 chars, sustantivos > 15 chars, contenido > 100,000 chars, e inyecciones SQL/FTS5 (RF-21, RF-22, RF-23, RF-24).
9. **Test `test_cli_help_pedagogico`**: Verifica que `biorag.py help` contenga la explicación del núcleo temático, sintaxis y reglas de seguridad (RF-25).
10. **Test `test_cli_casos_limite`**: Cobertura de espacios en comas, flags desordenados, mayúsculas y ausencia de comillas (CL-1 a CL-4).

### Matriz de Cobertura de Requisitos
- **RF-1, RF-2**: Algoritmo 2, Test 1, Test 10
- **RF-3, RF-4, RF-5**: Algoritmo 3, Test 1, Test 2, Test 3
- **RF-6, RF-7, RF-8, RF-9**: Algoritmo 4, Test 4
- **RF-10, RF-11, RF-12, RF-13**: Algoritmo 4, Test 5
- **RF-14, RF-15, RF-16**: Algoritmo 5, Test 6
- **RF-17, RF-18, RF-19**: Algoritmo 5, Test 7
- **RF-21, RF-22, RF-23, RF-24**: Algoritmo 1, Test 8
- **RF-25**: Docstring `biorag.py`, Test 9
- **CL-1 a CL-4**: Algoritmo 2, Test 10
- **RND-1 a RND-3**: Suite completa de tests

**Cobertura: 100% (25/25 RFs cubiertos).**
