# Plan definitivo — Stemming bilingüe (español + inglés) en query, parafrasis y ráfaga

Este documento reemplaza `plan_stemming_definitivo.md` (la versión solo-español). Mismo diseño de
fondo, misma ubicación de los cambios, pero el helper de stemming ahora corre **dos idiomas por
palabra** en vez de uno. Verificado contra la misma versión de `core/memory_store.py` ya revisada —
si el archivo cambió desde entonces, buscar por el texto citado, no por el número de línea.

## Por qué bilingüe desde ahora

El sistema guarda contenido mezclado — texto en español con términos técnicos en inglés
("backend", "commit", "deploy"), y es razonable esperar que agentes angloparlantes lo usen
directamente en inglés más adelante. Un stemmer de un solo idioma no ayuda con el otro: aplicarle
reglas de sufijos en español a una palabra en inglés (o viceversa) no rompe nada, pero tampoco agrupa
bien sus variantes. La solución no es "detectar el idioma de cada palabra" (frágil, ambiguo con
palabras cortas) — es correr el stemmer de **los dos idiomas sobre cada palabra** y agregar ambas
raíces como variantes. Es el mismo patrón de "agregar variantes al OR" que ya usa todo el sistema
hoy (paráfrasis, ráfaga), aplicado dos veces en vez de una.

**Nota aparte, para no perderla de vista:** cuando se necesite soportar chino, NO es una extensión de
este mismo mecanismo — el chino no se "stemiza" (no tiene inflexión gramatical de ese tipo) y además
no separa palabras con espacios, así que hace falta segmentación (herramienta distinta, ej. `jieba`),
no Snowball. Queda fuera de este plan, como tarea separada para el futuro.

## Decisión de arquitectura (ya evaluada, no reabrir)

- ❌ Tabla FTS espejo nueva — descartada, duplica almacenamiento innecesariamente.
- ❌ Escaneo completo de `largo_plazo` en cada búsqueda — descartada, no escala.
- ✅ Stemizar solo las tres entradas de búsqueda (`query`, `parafrasis`, `rafaga_palabras`), en los
  dos idiomas, reinsertando las raíces como variantes adicionales del mecanismo de paráfrasis/ráfaga
  que ya existe. Cero tablas nuevas, cero triggers, cero escaneo completo.

---

## Paso 0 — Dependencia

```bash
pip install PyStemmer --break-system-packages
```

`PyStemmer` trae Snowball para ~20 idiomas bajo la misma API — no hace falta una librería por idioma:
```python
import Stemmer
Stemmer.Stemmer('spanish').stemWord('implementacion')
Stemmer.Stemmer('english').stemWord('implementation')
```

Alternativa si `PyStemmer` no está disponible: `nltk.stem.snowball.SnowballStemmer`, que también
soporta ambos idiomas (`SnowballStemmer("spanish")` / `SnowballStemmer("english")`) con la misma
lógica de diccionario de abajo.

## Paso 1 — Helper de stemming bilingüe (una sola vez, en `__init__`)

Ubicación: `core/memory_store.py`, dentro de `__init__` de `SQLiteMemoryBioRAG` (línea 52), justo
después del registro de `PALABRA_COMPLETA` (línea 72:
`self.conn.create_function("PALABRA_COMPLETA", 2, palabra_completa)`). Agregar:

```python
        # Stemming bilingüe (español + inglés): normaliza variantes gramaticales de una
        # misma palabra en cualquiera de los dos idiomas. Diccionario de stemmers para
        # poder agregar más idiomas después sin reescribir la lógica.
        # Se usa SOLO del lado de la BUSQUEDA (query/parafrasis/rafaga) — nunca sobre
        # el contenido guardado.
        try:
            import Stemmer as _PyStemmer
            _stemmers_idiomas = {
                'es': _PyStemmer.Stemmer('spanish'),
                'en': _PyStemmer.Stemmer('english'),
            }
            def _stem_variantes_palabra(w):
                w = (w or "").lower()
                if len(w) <= 4:
                    return {w}
                return {stemmer.stemWord(w) for stemmer in _stemmers_idiomas.values()}
        except ImportError:
            from nltk.stem.snowball import SnowballStemmer as _SnowballStemmer
            _stemmers_idiomas = {
                'es': _SnowballStemmer("spanish"),
                'en': _SnowballStemmer("english"),
            }
            def _stem_variantes_palabra(w):
                w = (w or "").lower()
                if len(w) <= 4:
                    return {w}
                return {stemmer.stem(w) for stemmer in _stemmers_idiomas.values()}
        self._stem_variantes_palabra = _stem_variantes_palabra

        def _stem_variantes_frase(texto):
            """Devuelve un set de raices unicas (es+en) de todas las palabras de una frase."""
            if not texto:
                return set()
            variantes = set()
            for w in re.findall(r'\w+', texto):
                variantes |= self._stem_variantes_palabra(w)
            return variantes
        self._stem_variantes_frase = _stem_variantes_frase
```

**Diferencia clave con la versión solo-español:** ahora `_stem_variantes_palabra` devuelve un
**conjunto** (puede tener 1 o 2 elementos: la raíz en español y la raíz en inglés, que a veces
coinciden y a veces no), en vez de un solo string. Esto es intencional — para una palabra como
"implementación" las dos raíces pueden ser distintas ("implement" en ambos casos, de hecho, pero
para otras palabras sí van a diferir), y queremos las dos como variantes de búsqueda posibles, sin
tener que adivinar cuál idioma es la palabra.

**Por qué el umbral `len(w) <= 4`:** stemizar palabras cortas las corta demasiado y genera ruido en
cualquiera de los dos idiomas.

**Verificar antes de pegar:** confirmar que `re` ya está importado globalmente en el archivo (se usa
en todo `memory_store.py` — no duplicar el import si ya existe).

## Paso 2 — Reinsertar en `parafrasis_list` dentro de `buscar_por_frase`

Ubicación: función `buscar_por_frase` (empieza en línea 1833). Insertar el bloque nuevo justo antes
de la línea 1893 (`# ponytail: no semantic expansion table...`), después de:

```python
        clause = (" AND " + " AND ".join(filtros)) if filtros else ""
```

Insertar:

```python
        # ─── Reinsertar variantes por raiz (stemming es+en) como parafrasis adicional ───
        # Mismo mecanismo que ya usa parafrasis_list (OR + PARAFRASIS_PENALTY) — no se
        # inventa un camino de scoring nuevo, solo se agregan mas variantes a la lista.
        # Aplica sobre frase_limpia (sin los terminos protegidos entre comillas, que ya
        # tienen su propio bypass de trigram).
        _variantes_stem = set()
        _variantes_stem |= self._stem_variantes_frase(frase_limpia)
        if parafrasis_list:
            for _p in parafrasis_list:
                _variantes_stem |= self._stem_variantes_frase(_p)
        # Sacar variantes que ya son iguales a la frase original (no aportan nada nuevo)
        _variantes_stem = {v for v in _variantes_stem if v and v != frase_limpia.lower()}
        if _variantes_stem:
            parafrasis_list = (parafrasis_list or []) + list(_variantes_stem)
```

**Por qué acá y no antes:** este punto ya tiene `frase_limpia` (sin los términos protegidos entre
comillas) y `parafrasis_list` recibido, pero es ANTES de que se arme `fts_match` (líneas 1894-1907),
que es lo que consume `parafrasis_list`. El resto del bloque `if modo_estricto: / elif parafrasis_list:
/ ...` no necesita ningún cambio — ya sabe qué hacer con una lista más larga.

## Paso 3 — Mismo tratamiento en `buscar_por_rafaga`

Ubicación: función `buscar_por_rafaga` (empieza en línea 2638). Insertar después de
`if not rafaga_palabras: return [], 0, []` (línea 2654-2655) y antes de la "Fase 0" (línea 2657):

```python
        if not rafaga_palabras:
            return [], 0, []

        # ─── Reinsertar variantes por raiz (stemming es+en) en la lista de rafaga ───
        _variantes_rafaga = set()
        for _w in rafaga_palabras:
            _variantes_rafaga |= self._stem_variantes_palabra(_w)
        _variantes_rafaga = {v for v in _variantes_rafaga if v}
        rafaga_palabras_lower = {w.lower() for w in rafaga_palabras}
        _variantes_nuevas = [v for v in _variantes_rafaga if v not in rafaga_palabras_lower]
        if _variantes_nuevas:
            rafaga_palabras = list(rafaga_palabras) + _variantes_nuevas

        # Fase 0: Verificar errores previos de interpretación
```

## Paso 4 — `mcp_server.py`

**No se toca.** Sigue pasando `query`, `parafrasis`, `rafaga_palabras` como strings crudos, igual que
hoy. Todo el trabajo de stemming vive dentro de `core/memory_store.py`.

---

## Qué NO hacer

- No crear tablas FTS nuevas ni triggers nuevos.
- No registrar el stemmer como función SQL — todo el trabajo es en Python, antes de tocar la base.
- No tocar `largo_plazo_fts`, `largo_plazo_fts_unicode`, `grupos_semanticos`, `nodo_grupos_semanticos`.
- No stemizar el contenido guardado (`percibir_corto_plazo`, `consolidar_concepto`) — solo del lado
  de la búsqueda.
- No tocar `buscar_por_tokens` (línea 787) — función huérfana preexistente, no conectada a nada, no
  forma parte de este plan.
- No intentar meter soporte de chino en este mismo mecanismo — es un problema distinto (segmentación,
  no stemming) y queda fuera de este plan a propósito.
- No intentar detectar automáticamente el idioma de cada palabra antes de stemizar — se corren los
  dos stemmers siempre, sin adivinar, para evitar errores de clasificación de idioma en palabras
  ambiguas o cortas.

## Cómo validar (en orden)

1. **Compilación:** `python3 -m py_compile core/memory_store.py` — debe pasar sin errores.
2. **Caso español:**
   ```python
   aprender(concepto='test_stem_es', contenido='Implementamos la memoria persistente hoy', syn='prueba')
   consolidar()
   recordar(query='implementacion memoria', parafrasis='prueba de memoria,memoria guardada')
   ```
   `test_stem_es` debe aparecer.
3. **Caso inglés:**
   ```python
   aprender(concepto='test_stem_en', contenido='We implemented persistent memory today', syn='test')
   consolidar()
   recordar(query='implementation memory', parafrasis='memory test,persistent storage')
   ```
   `test_stem_en` debe aparecer.
4. **Confirmar que la precisión no se rompió:** buscar con la forma EXACTA en que quedó guardado cada
   nodo de prueba y comparar `score_hibrido` contra el de las búsquedas de los pasos 2 y 3 — el match
   literal debe seguir rankeando igual o más alto que el que solo coincide por raíz.
5. **Regresión completa:** correr `test_memory.py` de punta a punta, confirmar que nada se rompió.
6. Reportar los 4 resultados (compilación, caso español, caso inglés, comparación de score, regresión)
   como evidencia de cierre — no un simple "listo".