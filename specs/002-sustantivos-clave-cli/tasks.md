# Tareas — Spec 002: Sustantivos Clave en CLI (biorag.py)

## T1: Parser de Flags y Capa de Sanitización OWASP en CLI
- **RF cubiertos**: RF-1, RF-2, RF-21, RF-22, RF-23, RF-24, CL-1, CL-2, CL-4
- **Descripción**: Implementar en `biorag.py` las funciones auxiliares `_sanitizar_entrada_cli(texto, max_len)` y `_extraer_flag_valor(args, flags)` para limpieza de bytes nulos, control chars, límites de longitud, regex alfanumérico y extracción de flags `--sustantivos-clave`/`--sustantivos` tolerante a su posición en la línea de comandos.
- **Hecho cuando**:
  - [x] `_sanitizar_entrada_cli` rechaza o limpia bytes nulos, control chars y trunca/rechaza si excede límites de tamaño.
  - [x] `_extraer_flag_valor` extrae `--sustantivos-clave` tanto si se pasa antes, entre o después de argumentos posicionales, o reporta error si falta el argumento.
  - [x] `pytest tests/test_biorag_cli.py -k "sanitizacion or flags"` pasa en verde.
- [x] **Estado**: hecha

---

## T2: Comando `guardar` con Validación Pedagógica y Confirmación Visual
- **RF cubiertos**: RF-3, RF-4, RF-5
- **Descripción**: Actualizar `cmd_guardar` en `biorag.py` para requerir obligatoriamente `--sustantivos-clave` (o alias `--sustantivos`), validar mediante `normalizar_sustantivos_clave`, mostrar salida pedagógica guiada en caso de omisión o formato inválido (exit code `1`) y confirmar visualmente los sustantivos almacenados con conteo (exit code `0`).
- **Hecho cuando**:
  - [x] Ejecutar `guardar` sin `--sustantivos-clave` retorna exit code `1` y muestra la guía pedagógica de núcleo temático.
  - [x] Ejecutar `guardar` con sustantivos inválidos (<1, >5, o <2 / >15 chars) retorna exit code `1` con mensaje descriptivo.
  - [x] Ejecutar `guardar` con sustantivos válidos almacena el recuerdo en corto plazo y muestra confirmación enriquecida `Sustantivos clave: [s1, s2] (2/5)`.
  - [x] `pytest tests/test_biorag_cli.py -k "guardar"` pasa en verde.
- [x] **Estado**: hecha

---

## T3: Subcomandos `sustantivos` y `agregar_sustantivos` con Alias
- **RF cubiertos**: RF-6, RF-7, RF-8, RF-9, RF-10, RF-11, RF-12, RF-13, CL-3
- **Descripción**: Implementar los subcomandos `cmd_sustantivos` y `cmd_agregar_sustantivos` en `biorag.py` con queries SQL parametrizadas, gestión de nodos legados, normalización y registro de alias (`sustantivo`, `agregar-sustantivos`, `asignar_sustantivos`) en el enrutador `main()`.
- **Hecho cuando**:
  - [x] `biorag.py sustantivos <concepto>` muestra los sustantivos del nodo o mensaje informativo si es legado (exit code `0`), o error si no existe (exit code `1`).
  - [x] `biorag.py agregar_sustantivos <concepto> "s1,s2"` valida y actualiza el nodo en base de datos, sincronizando FTS5 (exit code `0`).
  - [x] Los alias `sustantivo`, `agregar-sustantivos` y `asignar_sustantivos` funcionan de forma idéntica.
  - [x] `pytest tests/test_biorag_cli.py -k "sustantivos_cmd"` pasa en verde.
- [x] **Estado**: hecha

---

## T4: Comando `buscar` con Sesgo Temático, Salida Detallada y Familiaridad
- **RF cubiertos**: RF-14, RF-15, RF-16
- **Descripción**: Actualizar `cmd_buscar` en `biorag.py` para aceptar `--sustantivos-clave` (alias `--sustantivos`), pasar los términos a `cerebro.buscar_por_frase`, mostrar la línea de núcleo temático en `--completo`/`--asociados`, sugerir el flag si no hay resultados, y enriquecer `cmd_familiaridad` para escanear `sustantivos_clave`.
- **Hecho cuando**:
  - [x] `biorag.py buscar "query" --sustantivos-clave "s1,s2"` ejecuta la búsqueda filtrando/sesgando por núcleo temático.
  - [x] `biorag.py buscar ... --completo` imprime los sustantivos clave de cada resultado devuelto.
  - [x] Búsquedas sin resultados muestran el tip pedagógico de refinamiento con `--sustantivos-clave`.
  - [x] `cmd_familiaridad` detecta coincidencias sobre `sustantivos_clave`.
  - [x] `pytest tests/test_biorag_cli.py -k "buscar"` pasa en verde.
- [x] **Estado**: hecha

---

## T5: Visibilidad Transversal (`corteza`, `listar`, `estado`) y Ayuda Pedagógica
- **RF cubiertos**: RF-17, RF-18, RF-19, RF-25
- **Descripción**: Actualizar `cmd_corteza` y `cmd_listar` para visualizar los sustantivos clave por nodo. Actualizar `cmd_estado` para calcular y reportar `Nodos con sustantivos clave: X/Y (Z%)`. Actualizar el docstring principal `__doc__` de `biorag.py` con la guía de núcleo temático, seguridad y ejemplos.
- **Hecho cuando**:
  - [ ] `biorag.py corteza` y `biorag.py listar` muestran los sustantivos clave de cada concepto.
  - [ ] `biorag.py estado` muestra la métrica de cobertura de sustantivos clave.
  - [ ] `biorag.py help` / `--help` imprime la documentación pedagógica completa.
  - [ ] `pytest tests/test_biorag_cli.py -k "visibilidad or help"` pasa en verde.
- [ ] **Estado**: pendiente

---

## T6: Suite Integral de Integración CLI y Verificación de Cero Regresiones
- **RF cubiertos**: RF-1 a RF-25, RND-1 a RND-3, CL-1 a CL-4
- **Descripción**: Ejecutar la suite completa de integración `tests/test_biorag_cli.py` y verificar la suite global de tests unitarios y benchmarks oficiales para garantizar cero regresiones.
- **Hecho cuando**:
  - [ ] `pytest tests/test_biorag_cli.py` pasa al 100% con todos los casos de prueba de integración CLI.
  - [ ] `pytest tests/ -v` pasa al 100% (221 tests existentes + nuevos tests CLI).
- [ ] **Estado**: pendiente

---

## Cobertura de requisitos

| RF | Cubierto por |
|---|---|
| RF-1 | T1, T2, T4 |
| RF-2 | T1, T2, T4 |
| RF-3 | T2 |
| RF-4 | T2 |
| RF-5 | T2 |
| RF-6 | T3 |
| RF-7 | T3 |
| RF-8 | T3 |
| RF-9 | T3 |
| RF-10 | T3 |
| RF-11 | T3 |
| RF-12 | T3 |
| RF-13 | T3 |
| RF-14 | T4 |
| RF-15 | T4 |
| RF-16 | T4 |
| RF-17 | T5 |
| RF-18 | T5 |
| RF-19 | T5 |
| RF-21 | T1, T6 |
| RF-22 | T1, T6 |
| RF-23 | T1, T6 |
| RF-24 | T1, T3, T6 |
| RF-25 | T5 |
| CL-1 | T1, T2, T6 |
| CL-2 | T1, T6 |
| CL-3 | T3, T6 |
| CL-4 | T1, T2, T6 |
| RND-1 a RND-3 | T1, T2, T3, T4, T5, T6 |

**Cobertura: 100% (25/25 RFs + Casos Límite + RNDs cubiertos).**
