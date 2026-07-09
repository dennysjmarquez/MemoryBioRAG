# Plan definitivo — Stemming en query, parafrasis y ráfaga

Este documento reemplaza cualquier versión anterior de "instrucciones de stemming" que se haya
compartido antes. Está verificado línea por línea contra la versión ACTUAL de `core/memory_store.py`
(la que confirmó que el stemming todavía NO está implementado). Si el archivo cambió desde esta
verificación, revisar los números de línea antes de aplicar los parches — buscar por el texto citado,
no confiar ciegamente en el número.

## Por qué esto sigue haciendo falta (contexto para el agente, sin ambigüedad)

BioRAG ya tiene:
- Búsqueda léxica FTS5 (trigram + unicode61).
- Paráfrasis obligatoria (`parafrasis_list`), combinada con OR y penalización de score.
- Clasificación semántica por WordNet (`grupo_score`), que agrupa palabras DISTINTAS por categoría conceptual.
- `modo_estricto` para exigir AND en vez de OR.

Ninguno de esos mecanismos resuelve esto: la MISMA palabra escrita con terminaciones distintas
("implementar", "implementación", "implementamos", "implementando") no se reconoce como la misma
palabra. Se confirmó con una prueba directa contra SQLite FTS5: buscar "implementacion" no encuentra
un texto que dice "implementamos", aunque hablen exactamente de lo mismo. WordNet tampoco lo resuelve,
porque WordNet espera la forma de diccionario (lema) de la palabra, no una conjugación — "implementamos"
probablemente ni siquiera es reconocida por WordNet como palabra válida.

**Stemming resuelve exactamente esto: reduce cualquier variante a su raíz común antes de comparar.**

## Decisión de arquitectura (ya evaluada y descartada dos alternativas más pesadas — no volver a proponerlas)

- ❌ Tabla FTS espejo nueva con triggers — descartada por duplicar almacenamiento de texto innecesariamente.
- ❌ Escaneo completo de `largo_plazo` en Python en cada búsqueda — descartada por constar O(n) en cada
  consulta a medida que la base crece.
- ✅ **Aprobada:** stemizar SOLO las palabras de las tres entradas de búsqueda (`query`, `parafrasis`,
  `rafaga_palabras`) — nunca el contenido guardado — y reinsertar esas raíces como variantes adicionales
  dentro del mismo mecanismo de paráfrasis/ráfaga que YA EXISTE. Cero tablas nuevas, cero triggers, cero
  escaneo completo. Se confirmó empíricamente que buscar una raíz corta (ej. "implement") directo contra
  la tabla trigram principal YA existente encuentra todas las variantes por sí sola, sin wildcard ni
  tabla adicional.

---

## Paso 0 — Dependencia

```bash
pip install PyStemmer --break-system-packages
```
Alternativa si no está disponible en el entorno: `pip install nltk --break-system-packages` y usar
`nltk.stem.snowball.SnowballStemmer("spanish")`.

## Paso 1 — Helper de stemming (una sola vez, en `__init__`)

Ubicación: `core/memory_store.py`, dentro de `__init__` de `SQLiteMemoryBioRAG` (empieza en línea 52),
después del bloque que registra `PALABRA_COMPLETA` (línea 72: `self.conn.create_function("PALABRA_COMPLETA", 2, palabra_completa)`).
Agregar inmediatamente después:

```python
        # Stemming en español: normaliza variantes gramaticales de una misma palabra
        # (implementar/implementacion/implementamos comparten raiz). Solo se usa del
        # lado de la BUSQUEDA (query/parafrasis/rafaga) — nunca sobre el contenido guardado.
        try:
            import Stemmer as _PyStemmer
            _stemmer_es = _PyStemmer.Stemmer('spanish')
            def _stem_palabra(w):
                w = (w or "").lower()
                return _stemmer_es.stemWord(w) if len(w) > 4 else w
        except ImportError:
            from nltk.stem.snowball import SnowballStemmer as _SnowballStemmer
            _stemmer_es_nltk = _SnowballStemmer("spanish")
            def _stem_palabra(w):
                w = (w or "").lower()
                return _stemmer_es_nltk.stem(w) if len(w) > 4 else w
        self._stem_palabra = _stem_palabra

        def _stem_frase(texto):
            """Version stemizada de una frase completa, palabra por palabra."""
            if not texto:
                return ""
            return " ".join(self._stem_palabra(w) for w in re.findall(r'\w+', texto))
        self._stem_frase = _stem_frase
```

**Por qué el umbral `len(w) > 4`:** stemizar palabras cortas (ej. "voy", "muy", "casa") las corta
demasiado y genera ruido — el stemmer necesita suficiente material para identificar una raíz real.

**Verificar antes de pegar:** confirmar que `re` ya está importado al inicio del archivo (es casi
seguro que sí, se usa en todo el archivo) — no volver a importarlo si ya existe un `import re` global.

## Paso 2 — Reinsertar en `parafrasis_list` dentro de `buscar_por_frase`

Ubicación exacta: función `buscar_por_frase`, que empieza en la línea 1833. Insertar el bloque nuevo
**justo antes** de la línea 1893 (`# ponytail: no semantic expansion table...`), es decir, después de
que se calculan `query`, `frase_limpia`, `pesos_tokens`, y ANTES del `if modo_estricto:`. El código
existente alrededor de ese punto es:

```python
        query = frase_limpia if not solo_protegidos else ""

        # Calcular pesos diferenciales de tokens por centralidad en la red
        pesos_tokens = self._pesar_tokens_query(frase)

        # Build filter clauses
        ...
        clause = (" AND " + " AND ".join(filtros)) if filtros else ""

        # ponytail: no semantic expansion table — agent passes synonyms as parafrasis_list directly
        if modo_estricto:
```

Insertar el bloque nuevo INMEDIATAMENTE ANTES de la línea `if modo_estricto:` (línea 1894 actual),
después de `clause = (...)`:

```python
        # ─── Reinsertar variantes por raiz (stemming) como parafrasis adicional ───
        # Mismo mecanismo que ya usa parafrasis_list (OR + PARAFRASIS_PENALTY) — no se
        # inventa un camino de scoring nuevo, solo se le agregan mas variantes a la lista.
        # Se aplica solo sobre frase_limpia (sin los terminos protegidos entre comillas,
        # que ya tienen su propio bypass de trigram).
        _variantes_stem = []
        _frase_stem = self._stem_frase(frase_limpia)
        if _frase_stem and _frase_stem != frase_limpia.lower():
            _variantes_stem.append(_frase_stem)
        if parafrasis_list:
            for _p in parafrasis_list:
                _p_stem = self._stem_frase(_p)
                if _p_stem and _p_stem != _p.lower():
                    _variantes_stem.append(_p_stem)
        if _variantes_stem:
            parafrasis_list = (parafrasis_list or []) + _variantes_stem
```

**Por qué acá y no antes:** este punto ya tiene `frase_limpia` calculada (sin los términos
protegidos entre comillas) y `parafrasis_list` ya recibido como parámetro, pero es ANTES de que se
arme `fts_match` (líneas 1894-1907), que es donde `parafrasis_list` se consume. Insertando acá, el
`parafrasis_list` ya extendido con las raíces fluye automáticamente al resto de la función sin tocar
ninguna otra línea del `if modo_estricto: / elif parafrasis_list: / ...` — ese bloque ya sabe qué
hacer con una `parafrasis_list` más larga, no hace falta modificarlo.

## Paso 3 — Mismo tratamiento en `buscar_por_rafaga`

Ubicación exacta: función `buscar_por_rafaga`, que empieza en la línea 2638. Insertar el bloque nuevo
después de la línea `if not rafaga_palabras: return [], 0, []` (línea 2654-2655) y antes de la
"Fase 0" (línea 2657: `# Fase 0: Verificar errores previos de interpretación`):

```python
        if not rafaga_palabras:
            return [], 0, []

        # ─── Reinsertar variantes por raiz (stemming) en la propia lista de rafaga ───
        _variantes_rafaga = []
        for _w in rafaga_palabras:
            _w_stem = self._stem_palabra(_w)
            if _w_stem and _w_stem != _w.lower():
                _variantes_rafaga.append(_w_stem)
        if _variantes_rafaga:
            rafaga_palabras = list(rafaga_palabras) + _variantes_rafaga

        # Fase 0: Verificar errores previos de interpretación
```

## Paso 4 — `mcp_server.py`

**No se toca.** Ningún cambio necesario ahí — sigue pasando `query`, `parafrasis`, `rafaga_palabras`
como strings crudos, exactamente igual que hoy. Todo el trabajo de stemming vive dentro de
`core/memory_store.py`.

---

## Qué NO hacer

- No crear ninguna tabla FTS nueva ni triggers nuevos.
- No registrar el stemmer como función SQL (`create_function`) — acá no hace falta, todo el trabajo
  es en Python puro, antes de tocar la base de datos.
- No tocar `largo_plazo_fts`, `largo_plazo_fts_unicode`, `grupos_semanticos`, `nodo_grupos_semanticos`.
- No stemizar el contenido que se guarda (`percibir_corto_plazo`, `consolidar_concepto`) — el stemming
  es solo del lado de la búsqueda, nunca de lo que se almacena o se muestra al usuario.
- No conectar esto con `buscar_por_tokens` (línea 787) — esa función existe desde antes, no está
  conectada a nada (no la llama ningún otro método del archivo), y no forma parte de este plan. Si el
  agente la encuentra y le parece relacionada, que la deje intacta y sin tocar — no es parte de esta
  tarea, y mezclarla puede introducir un camino de búsqueda paralelo no deseado.

## Cómo validar (en orden)

1. **Compilación:** `python3 -m py_compile core/memory_store.py` — debe pasar sin errores antes de
   probar nada más.
2. **Caso mínimo:** guardar un nodo de prueba:
   ```python
   aprender(concepto='test_stem', contenido='Implementamos la memoria persistente hoy', syn='prueba')
   consolidar()
   ```
3. **Buscar variante distinta:**
   ```python
   recordar(query='implementacion memoria', parafrasis='prueba de memoria,memoria guardada')
   ```
   `test_stem` debe aparecer en los resultados — antes de este cambio, no aparecía.
4. **Confirmar que la precisión no se rompió:** buscar `query='implementamos memoria'` (la forma
   EXACTA en que está guardado) y comparar su `score_hibrido` contra el de la búsqueda del paso 3 —
   el match literal debe seguir rankeando igual o más alto que el que solo coincide por raíz (esto lo
   garantiza el mecanismo de `PARAFRASIS_PENALTY` ya existente, que no se tocó).
5. **Regresión completa:** correr `test_memory.py` de punta a punta y confirmar que nada que ya
   funcionaba se rompió.
6. Reportar los 4 resultados (compilación, caso mínimo, comparación de score, regresión) para que se
   pueda confirmar el cierre de esta tarea con evidencia, no solo con "ya quedó".