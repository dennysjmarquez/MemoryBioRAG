# Auditoría E3 Cambio 2 — veredicto: APROBADO

- **Auditor:** sesión `arena/6459e2d0-memorybiorag`. **Operador:** `arena/33a8df67-memorybiorag` (PR #12, draft).
- **Commits auditados:** `4f3f8cc`, `1b62cd3`, `fb8cbea` (base `47f7f60`).
- **El merge es decisión de Dennys.** No se tocó ninguna base: todo corrió sobre copias en `/tmp`.

## 1. Código = v2 aprobado + docstring

Se aplicó `docs/e3_cambio2_propuesta_no_aplicar_20261029.patch` (sha `82fa4429…`) sobre un árbol limpio de `47f7f60` y se comparó archivo por archivo con la rama del operador:

```text
IGUAL core/mcp_server/search.py, core/mcp_server/write.py, core/memory/consolidation.py, core/memory/constants.py,
      core/memory/schema.py, core/memory_store.py, tests/test_sustantivos_clave_schema.py, tests/test_validacion_unicode_guardado_b2.py
DIFIERE core/memory/ingest.py  → solo el docstring (diff abajo)
Ningún otro archivo fuera de docs/ cambia.
```

```diff
@@ -39,10 +39,10 @@
     dimensiones: dict {tipo_nombre: [valores]} para indexación de 5 ejes.
     predicados: list[dict] con {sujeto, accion, objeto, contexto} para SRL v16.0.
     valencia_somatica: float [0.0, 1.0] para marcadores somáticos (v20.0).
-    sustantivos_clave: str (v25 spec 001) — centro de gravedad temático, ya normalizado por
-    la tool (aprender/guardar). Sobrescribe el valor previo (no merge): si el tema cambió,
-    los sustantivos se reemplazan (Decisión 2 del plan 001). Aditivo: default '' = nodos
-    legacy sin sustantivos, el comportamiento previo no cambia."""
+    sustantivos_clave plegados y sustantivos_clave_exactos se sustituyen como un par
+    cuando la percepción aporta sustantivos; no se fusionan etiquetas entre notas.
+    Si la percepción no aporta sustantivos, conserva las etiquetas plegadas y exactas
+    ya existentes en corto plazo; para un concepto nuevo, la etiqueta exacta queda NULL."""
     # Solo se transforman datos que entran en esta escritura; no filas antiguas.
     key_original = concepto.lower().strip()
     key_normalizada = normalizar_identidad(concepto).lower().strip()
```

## 2. Suite completa (mi corrida, sin `-k` y sin `BIORAG_NEURONA=0`)

```text
757 passed in 174.57s (0:02:54)
EXIT=0
```

## 3. QA snapshot (mis corridas; los logs del operador se perdieron)

Fuente: `snapshots/qa_escape_qcr_20260811.db`, sha `104dd2902aaf…`. Entorno: `PYTHONHASHSEED=0 BIORAG_NEURONA=0`, con requirements fijados.

```text
— normal —
GLOBAL SUMMARY (Retrieval) | 875    |  100.00% |   93.14% |  0.957 | 0         
GLOBAL SUMMARY (Noise/FP) | 40     | N/A       | N/A       | N/A      | 0          (0.00% FP sobre 40 válidos; 0 contaminados)
[GATE] OK — métricas dentro de los umbrales de la baseline oficial
EXIT=0
— ruido zzqx + censo —
GLOBAL SUMMARY (Retrieval) | 875    |   96.80% |   86.63% |  0.912 | 28        
GLOBAL SUMMARY (Noise/FP) | 40     | N/A       | N/A       | N/A      | 0          (0.00% FP sobre 40 válidos; 0 contaminados)
GATE DE REGRESIÓN: FALLADO
EXIT=1
```

Al comparar mis JSON con `docs/e3b3_snapshot_{normal,ruido}_20261028.json`, coinciden `global`, `categorias`, `qa_honesta` y `e2b`. La única diferencia es la ruta de origen (el mismo archivo, con el mismo sha).

- QA honesta normal: R@5 100,00 (865, 0 fallos); R@1 95,31; MRR 0,9718.
- QA honesta con ruido: R@5 97,34 (23 fallos); R@1 88,63; MRR 0,9281.
- El gate con ruido da código 1, igual que B3 (umbral histórico); no es una regresión.

## 4. QA viva

Copia restaurada desde el dump de Drive, sha `a61913ce074cd02323c13589040b7ab1e5e4f36b18bbe62c12f9c1d363324e9a` (no se sube al repo).

**Viva normal, repetida por el auditor:**

```text
GLOBAL SUMMARY (Retrieval) | 875    |   99.20% |   91.09% |  0.943 | 7         
GLOBAL SUMMARY (Noise/FP) | 40     | N/A       | N/A       | N/A      | 0          (0.00% FP sobre 40 válidos; 0 contaminados)
[GATE] OK — métricas dentro de los umbrales de la baseline oficial
EXIT=0
```

- Coincide con B3 y con el JSON publicado por el operador en `global`, `categorias`, `qa_honesta` y `e2b`.
- QA honesta: R@5 99,88 (1 fallo: 0848); R@1 93,53; MRR 0,9622.

**Viva con ruido:** no la repetí. Su JSON publicado (`docs/e3c2_viva_ruido_20261029.json`), pasado por `comprobar_escenario` contra B3, da **IGUAL**.

## 5. Multilingüe y guardados MCP (mis corridas)

```text
Idioma | R@5 | R@1 | MRR@5 | FP
zh     | 12/20 ( 60.00%) | 12/20 ( 60.00%) | 0.6000 | 0/2
ja     | 12/20 ( 60.00%) | 12/20 ( 60.00%) | 0.6000 | 0/2
ko     | 19/20 ( 95.00%) | 18/20 ( 90.00%) | 0.9250 | 0/2
ru     | 20/20 (100.00%) | 19/20 ( 95.00%) | 0.9750 | 0/2
en     | 20/20 (100.00%) | 20/20 (100.00%) | 1.0000 | 2/2
es     | 20/20 (100.00%) | 20/20 (100.00%) | 1.0000 | 0/2

```

- Contra `docs/e3b3_directa_20261028.json`: **0 casos peores, 10 mejores** (ja-06..10, zh-06..10) y **0 FP nuevos**.
- Guardados MCP: zh 18, ja 15, ko 16, ru 20 = **69/80**, idéntico a `docs/e3b3_guardado_nativo_20261028.log`.

## 6. Observaciones (no bloquean)

1. Las salidas crudas de las QA snapshot del operador se perdieron. Las sustituyen las corridas de este informe.
2. El primer bloque de `e3c2_comprobar_igualdad_qa_b3_20261029.log` compara **B2 contra B3** (archivos previos), no la candidata. La evidencia de la candidata es la comparación directa del segundo bloque, más estas corridas.
3. La §5 del informe del operador cita mediciones previas a añadir el docstring. Las repetí y dan lo mismo.

## Veredicto

**APROBADO.**

- El código es exactamente v2 + docstring.
- Pasan los 757 tests.
- Snapshot y viva coinciden con B3, con FP 0/40.
- Multilingüe: mejora en zh/ja, sin pérdidas.
- Guardados MCP: 69/80, sin cambio.

La PR #12 sigue en draft. Pasarla a lista y hacer el merge le corresponde solo a Dennys.
