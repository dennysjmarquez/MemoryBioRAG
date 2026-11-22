# E3 · Cambio 1: propuesta de identidad Unicode para auditoría

**DOCUMENTOS, NO APLICAR AL MOTOR.** El auditor y Dennys aún no han dado el OK. Este documento y el [diff propuesto](e3_cambio1_identidad_diff_NO_APLICAR_20261029.patch) no ejecutan ni instalan el cambio.

- Base del diff: `b4fef27b5d84c8827ca140c4d6e14bffae93b65c`.
- SHA-256 del diff: `98254a8611aa6d744c2433c83d2ba02601aa199531c444d65565dc6460f0747c`.
- Tras un reinicio desapareció la copia temporal anterior. El diff se reconstruyó y **coincide byte por byte con la huella anunciada**. Se comprobó su aplicación limpia en una copia de la base y se compararon sus 12 archivos con la candidata probada. En el árbol real no se aplicó.
- Las cuatro QA oficiales se reservan para **después del OK**. Aquí hay pruebas unitarias y experimentos sintéticos en copias, no esas QA.

## 1. Qué conecta el cambio propuesto

La función única `normalizar_identidad` aplica NFC, el mapeo directo `<wide>`/`<narrow>` del bloque U+FF00–FFEF y U+3000 → espacio. No aplica NFKC general; U+309B queda para después. Se conecta con consulta, escrituras nuevas, sustantivos, puentes y nombres. La validación de puentes sigue devolviendo el texto original; la escritura de puentes nuevos sí lo pliega. El test B3 cambia explícitamente `１２３４` de aceptado a rechazado, igual que `1234`.

No migra ni reindexa automáticamente los datos existentes. Para las herramientas MCP de sustantivos se consulta primero la clave exacta y luego la normalizada. En ciertos conflictos de clave antigua se detiene la escritura o consolidación, pero no se escanea todo el corpus: aún pueden existir otras formas equivalentes o duplicados. No hay garantía general de recuperación de registros antiguos.

**No se adelanta el Cambio 2:** el normalizador histórico de sustantivos sigue aplicando `_quitar_acentos`/NFKD. Así, `ガラス,カラス` todavía colapsa a `カラス`; también colapsa `①①,11` y `ﬁﬁ,fifi`. La ingestión directa mantiene su contrato actual de recibir sustantivos ya normalizados; no cubre clientes directos que envíen ese campo crudo.

## 2. Contenido nuevo: motivo y pérdida del original

**Motivo de la propuesta:** si la consulta se pliega pero el contenido recién escrito se deja ancho, los índices FTS pueden distinguir ambos. Por eso el diff pliega también el contenido y los sinónimos nuevos, para que la entrada al índice y la consulta compartan forma. Es una decisión de diseño de esta propuesta, **no una demostración de que sobrescribir el texto original sea la única solución**.

**Sí, se pierde la representación exacta en ese flujo.** Ejemplo: si el usuario entrega `Marcador ｚｑｘｈｎ en el archivo nuevo.`, la propuesta guarda `Marcador zqxhn en el archivo nuevo.`. En el campo de contenido de ese recuerdo no queda la forma de ancho original y el diff no guarda otra copia recuperable del texto original. NFC también puede recomponer caracteres. Los registros antiguos no se reescriben por instalar el cambio. Esto afecta a contenido y sinónimos nuevos, no solo a sus claves de búsqueda; necesita revisión explícita antes del OK.

## 3. Medición: base mixta de dos recuerdos sintéticos

No se abrió la viva ni se escribió el snapshot. Se creó el primer recuerdo con la base `b4fef27` y el segundo con la propuesta, ambos en una **base sintética**. Antes de cada escritura hubo búsqueda previa; para construir este caso de ensayo se mantuvieron separados aunque el segundo preflight encontró el primero.

| Recuerdo | Entrada entregada | Contenido realmente guardado |
|---|---|---|
| `recuerdo_antiguo` | `Marcador ｚｑｘｈｎ en el archivo antiguo.` | `Marcador ｚｑｘｈｎ en el archivo antiguo.` |
| `recuerdo_nuevo` | `Marcador ｚｑｘｈｎ en el archivo nuevo.` | `Marcador zqxhn en el archivo nuevo.` |

Una consulta literal a cada índice FTS (`trigram` y `unicode61`) dio lo mismo en ambos índices:

| Término consultado directamente al índice | Fila encontrada |
|---|---|
| `ｚｑｘｈｎ` | `recuerdo_antiguo` |
| `zqxhn` | `recuerdo_nuevo` |

Esa prueba es **solo el índice literal**, no toda la búsqueda. Para el motor completo se usó la **misma base fuente byte a byte** en ambos brazos, una copia y un proceso nuevo por consulta, `profundidad="activos"`, `limite=5`, `ignore_peso_sinaptico=True`, neurona apagada, WordNet encendido, reloj y hash fijados. La propuesta convierte la consulta ancha `ｚｑｘｈｎ` en `zqxhn`:

| Consulta | Motor base: posición y score | Propuesta: posición y score |
|---|---|---|
| `ｚｑｘｈｎ` | 1. nuevo `0.1786`; 2. antiguo `0.0488` | 1. antiguo `0.1781`; 2. nuevo `0.0454` |
| `zqxhn` | 1. antiguo `0.1781`; 2. nuevo `0.0454` | 1. antiguo `0.1781`; 2. nuevo `0.0454` |

El caso de consulta ancha se repitió **3/3 con el mismo orden y scores** por brazo. SHA-256 de la fuente sintética, igual antes y después de las consultas: `5d02f4821f8856970dba1dbe20bb30c143e96a2aae68c6595526876ee40ad782`.

**Lectura sin ocultar el riesgo:** el índice literal plegado encuentra solo el nuevo, aunque la búsqueda completa devuelve también el antiguo. En este ejemplo no hay pérdida de ambas filas, pero **sí cambia el orden**: el nuevo baja de 1 a 2 y el antiguo sube de 2 a 1. Los dos contienen el mismo marcador y no se definió un gold para elegir cuál era el correcto: no es una regresión oficial demostrada. Si el esperado fuera el nuevo, sería una pérdida de rango, no una diferencia de score aislada. Una sola base artificial no permite afirmar compatibilidad ni ausencia de regresiones; este resultado debe revisarse antes del OK.

## 4. Lista exacta de llamadas a `normalizar_identidad`

Estas son las **21 llamadas directas en código de producción**; las líneas corresponden a los archivos **propuestos**, no a la base sin el patch. La lista se obtuvo inspeccionando el AST de todos los `.py` de la copia reconstruida.

| Archivo y línea | Función / dato que se normaliza |
|---|---|
| `core/concept_hub.py:112` | `validar_bridges`: nombre del concepto. |
| `core/concept_hub.py:131` | `validar_bridges`: texto del puente para contar y comparar. |
| `core/concept_hub.py:346` | `agregar_bridges`: texto del puente nuevo al guardar. |
| `core/mcp_server/_shared.py:95` | `_sustantivo_valido`: término para validar. |
| `core/mcp_server/search.py:154` | `_recordar_impl._sanitizar_string`: consulta y partes sanitizadas. |
| `core/mcp_server/search.py:169` | `_recordar_impl`: paráfrasis antes de separar por comas. |
| `core/mcp_server/search.py:179` | `_recordar_impl`: palabras de ráfaga antes de separar. |
| `core/mcp_server/write.py:43` | `_buscar_registro_sustantivos`: nombre alternativo normalizado. |
| `core/mcp_server/write.py:105` | `_aprender_impl`: nombre del concepto. |
| `core/mcp_server/write.py:132` | `_aprender_impl`: contenido nuevo. |
| `core/mcp_server/write.py:134` | `_aprender_impl`: sinónimos nuevos. |
| `core/mcp_server/write.py:900` | `biorag_agregar_sustantivos`: nombre del concepto. |
| `core/memory/constants.py:301` | `normalizar_sustantivos_clave`: entrada antes de separar términos. |
| `core/memory/ingest.py:51` | `percibir_corto_plazo`: nombre del concepto. |
| `core/memory/ingest.py:53` | `percibir_corto_plazo`: contenido nuevo. |
| `core/memory/ingest.py:54` | `percibir_corto_plazo`: sinónimos nuevos. |
| `core/memory/ingest.py:157` | `consolidar_concepto`: nombre normalizado alternativo. |
| `core/memory/search.py:78` | `buscar_por_frase`: consulta. |
| `core/memory/search.py:80` | `buscar_por_frase`: cada paráfrasis. |
| `core/memory/search.py:82` | `buscar_por_frase`: impulso por sustantivos. |
| `core/memory_service.py:83` | `aprender`: nombre que se usará al consolidar. |

En pruebas hay **11 llamadas directas** en `tests/test_identidad_unicode_cambio1.py`: líneas `31`, `32`, `36` (dos), `37` (dos), `38`, `39`, `44`, `45` y `46`. Además, en las líneas `187–191`, la prueba del límite conserva una referencia a la función y la llama indirectamente como `real(texto)`. La definición está en `core/identidad_unicode.py:17`; no es una llamada.

## 5. SHA-256 de los archivos que cambiaría el diff

`Antes` corresponde a `b4fef27`; `Propuesto` es el contenido tras aplicar el diff **solo en copia**. `NUEVO` indica que el archivo no existía en esa base.

| Archivo | SHA-256 antes | SHA-256 propuesto |
|---|---|---|
| `core/README.md` | `0f5d12b01cf00b9f4f6579e850117379398c09eb842d33c57f841badfbff0992` | `2bb3ee4b49ff2df79e9e827bd5c428c4d30f17a9259def1157aa62eb4b709aba` |
| `core/concept_hub.py` | `50cdced5342eb255abcd1ea9ab0781ab677ec518b173bc3855a32c0be9b618cf` | `c02ca5191f61d5d578a66bad6a2a21eefc49151cf1925c02477a32091c8243c7` |
| `core/identidad_unicode.py` | `NUEVO` | `09423e0cf8e1debda1bcbec9d04beaa5507cd63bc6226c818fe50d45db75c20b` |
| `core/mcp_server/_shared.py` | `eaf26c15feafe47c574a381ad6e7f1118439c825e893a95db6cbce94d2ef7e36` | `31f9f6ec5befdc98ca492b55646763b7eac0503d328c7ea27364d2b3f543589c` |
| `core/mcp_server/search.py` | `797d2b254d7b9b215537ab6c3fe40d8e0c492f7e64bbc0a55d5a773f185663fc` | `432ee33c499bd9326010a6172e6208b8879e25a767343d7e78bc70a0db7fb32a` |
| `core/mcp_server/write.py` | `b188d7430e8e37dcbcde1dcb949cc5255c7d205c1b7c1cc9de3ef726e4545218` | `714b5219805bf49cebffe2cb98c14628006b28f0928ca1a973a46b844073afcc` |
| `core/memory/constants.py` | `de8397eefa632d18eb06d61a3907286b17ba9c022b2e3924389d082041439c35` | `8f748fe21e4aa524ca84df71cb021a2c9e81ca2ba2cdc33f3d23e1f135ca13e8` |
| `core/memory/ingest.py` | `25f72f24e60723008cece6792583f39c64927ad4dcae73e90118357ef87c7951` | `8e0627073f5a3e553d459c0c2f82b05021cf5c255c65f2883abf68c222a0a193` |
| `core/memory/search.py` | `f4479e7db7673c264176a48d467ab7c32411ea67a8cb39ad8daf4a4089677286` | `7193ee7f9e4fdcc52787d8dc107d7456cbaedecac687e084d4e15f450a4ba8e6` |
| `core/memory_service.py` | `51ec9b5181c5e92410c31cf80e8bc68e86b82908ed0b1542639827c72e137f7b` | `b5783729ae25a6100d1a8cd24204d47ae56ce3224fec252540c30ad4b22c9a65` |
| `tests/test_identidad_unicode_cambio1.py` | `NUEVO` | `21213fbcbbe277227d2a5c09b40900dac9562229b642d937a6f835496181291d` |
| `tests/test_validacion_bridges_unicode_b3.py` | `9b4d70a224b974d28441628b0e3acb37951dd1920140542bfb962157bfae0c88` | `fc6ad1d4a0a75009f11af6e6ee6f4f5ebdd89a50daf156834e298232f0192bc1` |

## 6. Pruebas en copias, no QA oficiales

Después del reinicio se rehicieron las pruebas sobre la candidata cuyo diff tiene la huella indicada arriba, con Python 3.11.2, SQLite 3.40.1, Unicode 14.0.0, NumPy 2.4.6, NLTK 3.9.4, Pydantic 2.13.5, MCP 1.30.0 y pytest 9.1.1:

```text
151 passed in 7.20s
746 passed in 178.55s (0:02:58)
```

Las 151 incluyen identidad, B1/B2/B3/B4a y búsqueda previa. La suite de 746 usó una **copia independiente** del snapshot y no forzó la neurona apagada. El snapshot original conservó SHA-256 `104dd2902aaf24c3ce93624492ea95a719acbdcca50f4f6bc123ac8317749796`.

También se repitieron 132 búsquedas sintéticas multilingües: cada brazo creó su propia base con los mismos 120 contenidos del gold, luego usó una copia limpia por consulta. Las 132 listas, órdenes, scores y rangos coincidieron entre base y propuesta. Los dos archivos SQLite fueron creados por separado y **sus bytes no eran idénticos**; ambos pasaron la validación de contenidos y de integridad. WordNet encendido, neurona apagada y parámetros de búsqueda iguales a los indicados arriba.

| Idioma | R@5 base/propuesta | R@1 base/propuesta | FP base/propuesta |
|---|---:|---:|---:|
| zh | 12/20 · 12/20 | 12/20 · 12/20 | 0/2 · 0/2 |
| ja | 12/20 · 12/20 | 12/20 · 12/20 | 0/2 · 0/2 |
| ko | 19/20 · 19/20 | 18/20 · 18/20 | 0/2 · 0/2 |
| ru | 20/20 · 20/20 | 19/20 · 19/20 | 0/2 · 0/2 |
| en | 20/20 · 20/20 | 20/20 · 20/20 | 2/2 · 2/2 |
| es | 20/20 · 20/20 | 20/20 · 20/20 | 0/2 · 0/2 |
| **Total** | **103/120 · 103/120** | **101/120 · 101/120** | **2/12 · 2/12** |

El evaluador informó `commit_motor=null` porque las copias no son repositorios Git; la base se identifica por `b4fef27` y la candidata por el SHA del diff. Las salidas JSON de esta repetición fueron temporales: base SHA-256 `4cd2436f147885ad91f7b0961a5d1f2a77c00644c1c5d0a39468d75a897bded6`, propuesta `e1932933ecfb25e2830afbc80e9363a4b3ae827ac0b3eaba45d293a26dacf357`. Estos resultados no invalidan la observación de cambio de orden de la base mixta ni sustituyen las QA.

No se ejecutaron las cuatro QA oficiales ni el circuito completo de 80 guardados y búsquedas MCP para este diff. Los dos archivos de esta entrega son documentos; no se incluye base de datos, volcado ni aplicación al motor.

La comprobación de espacios del **código propuesto** pasó. Al revisar el archivo `.patch` como documento agregado, `git diff --check` marca espacios de las líneas de contexto propias del formato diff; se conservan para no alterar sus bytes ni la huella anunciada.

## 7. Reproducir la medición mixta

<details>
<summary>Preparación, comandos y sonda completa para el auditor</summary>

La sonda siguiente es autónoma y usa únicamente registros artificiales. Guardar el bloque Python como `sonda_mixta.py`. Los comandos aplican el patch **solo en una copia desechable**, jamás en el checkout de trabajo. El SHA del archivo de sonda usado en la medición fue `84ee46c95053c2c9332f94e80ba999015c786a319e1ea5108a1eafcb5f4cf13f`. La huella de una base creada de nuevo puede variar; lo importante es que cada brazo consulte copias de **la misma** fuente, sin WAL/SHM pendientes.

```bash
# En la raíz del repositorio, con el bloque siguiente guardado en otra ruta:
PATCH="$PWD/docs/e3_cambio1_identidad_diff_NO_APLICAR_20261029.patch"
SONDA=/ruta/al/archivo/sonda_mixta.py
BASE_COMMIT=b4fef27b5d84c8827ca140c4d6e14bffae93b65c
D=$(mktemp -d); B="$D/base"; C="$D/propuesta"; mkdir -p "$B" "$C" "$D/resultados"
git archive "$BASE_COMMIT" | tar -x -C "$B"
git archive "$BASE_COMMIT" | tar -x -C "$C"
(cd "$C" && git apply --check "$PATCH" && git apply "$PATCH")  # solo copia
python3 -m venv "$D/venv"
PY="$D/venv/bin/python"
"$PY" -m pip install -r "$B/requirements.txt"
export PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 BIORAG_NEURONA=0 BIORAG_WORDNET_ENABLED=1
unset BIORAG_PATH
DB="$D/resultados/mezcla.db"
export BIORAG_DMN_ESTADO_PATH="$D/resultados/dmn-antiguo.json"
"$PY" "$SONDA" --raiz "$B" --base "$DB" --modo antiguo --salida "$D/resultados/antiguo.json"
export BIORAG_DMN_ESTADO_PATH="$D/resultados/dmn-nuevo.json"
"$PY" "$SONDA" --raiz "$C" --base "$DB" --modo nuevo --salida "$D/resultados/nuevo.json"
"$PY" "$SONDA" --raiz "$C" --base "$DB" --modo fts --salida "$D/resultados/fts.json"
for brazo in base propuesta; do
  if [ "$brazo" = base ]; then R="$B"; else R="$C"; fi
  for caso in ancho normal; do
    if [ "$caso" = ancho ]; then Q='ｚｑｘｈｎ'; else Q='zqxhn'; fi
    export BIORAG_DMN_ESTADO_PATH="$D/resultados/dmn-${brazo}-${caso}.json"
    "$PY" "$SONDA" --raiz "$R" --base "$DB" --modo buscar --query "$Q" --salida "$D/resultados/${brazo}_${caso}.json"
  done
done
sha256sum "$DB"
```

Sonda utilizada:

```python
#!/usr/bin/env python3
"""Sonda sintética de contenido mixto; los motores y las DB son copias aisladas."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
from unittest.mock import patch

p = argparse.ArgumentParser()
p.add_argument('--raiz', required=True)
p.add_argument('--base', required=True)
p.add_argument('--modo', required=True, choices=['antiguo', 'nuevo', 'buscar', 'fts'])
p.add_argument('--query')
p.add_argument('--salida', required=True)
a = p.parse_args()
root = Path(a.raiz).resolve()
os.chdir(root)
sys.path.insert(0, str(root))
source = Path(a.base)
out = Path(a.salida)
if out.exists():
    raise FileExistsError(out)

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def check_no_wal():
    for suf in ('-wal', '-shm'):
        if Path(str(source) + suf).exists():
            raise RuntimeError(f'Fuente con {suf}: no copiar')

if a.modo == 'fts':
    check_no_wal()
    antes = sha(source)
    con = sqlite3.connect(f'file:{source}?mode=ro&immutable=1', uri=True)
    rows = con.execute('SELECT concepto, contenido FROM largo_plazo ORDER BY concepto').fetchall()
    matches = {}
    for tabla in ('largo_plazo_fts', 'largo_plazo_fts_unicode'):
        for q in ('ｚｑｘｈｎ', 'zqxhn'):
            # Consulta de diagnóstico FTS directa; no representa todo el motor.
            matches[f'{tabla}:{q}'] = con.execute(
                f'SELECT concepto FROM {tabla} WHERE {tabla} MATCH ? ORDER BY concepto', (q,)
            ).fetchall()
    con.close()
    assert sha(source) == antes
    result = {'sha_fuente': antes, 'filas': rows, 'fts_literal': matches}
else:
    from core.memory_store import SQLiteMemoryBioRAG
    from core.memory_service import aprender
    with patch('time.time', return_value=1793059200.0):
        if a.modo == 'antiguo':
            if source.exists():
                raise FileExistsError(source)
            cerebro = SQLiteMemoryBioRAG(str(source))
            try:
                # Antes de la escritura, búsqueda previa sobre la base sintética.
                previa, _ = cerebro.buscar_por_frase('ｚｑｘｈｎ', profundidad='activos',
                    limite=5, ignore_peso_sinaptico=True)
                entrada = 'Marcador ｚｑｘｈｎ en el archivo antiguo.'
                aprender(cerebro, 'recuerdo_antiguo', entrada)
                cerebro.conn.commit()
                filas = cerebro.conn.execute('SELECT concepto,contenido FROM largo_plazo ORDER BY concepto').fetchall()
                wal = cerebro.conn.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()
                assert wal[0] == 0
            finally:
                cerebro.cerrar_sistema()
            check_no_wal()
            result = {'sha_fuente': sha(source), 'entrada': entrada,
                      'previa': [r[0] for r in previa], 'filas': filas}
        elif a.modo == 'nuevo':
            check_no_wal()
            cerebro = SQLiteMemoryBioRAG(str(source))
            try:
                previa, _ = cerebro.buscar_por_frase('ｚｑｘｈｎ', profundidad='activos',
                    limite=5, ignore_peso_sinaptico=True)
                entrada = 'Marcador ｚｑｘｈｎ en el archivo nuevo.'
                aprender(cerebro, 'recuerdo_nuevo', entrada)
                cerebro.conn.commit()
                filas = cerebro.conn.execute('SELECT concepto,contenido FROM largo_plazo ORDER BY concepto').fetchall()
                wal = cerebro.conn.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()
                assert wal[0] == 0
            finally:
                cerebro.cerrar_sistema()
            check_no_wal()
            result = {'sha_fuente': sha(source), 'entrada': entrada,
                      'previa': [r[0] for r in previa], 'filas': filas}
        else:
            if not a.query:
                raise ValueError('Falta --query')
            check_no_wal()
            antes = sha(source)
            with tempfile.TemporaryDirectory(prefix='e3-mezcla-') as d:
                copy = Path(d) / 'copia.db'
                shutil.copyfile(source, copy)
                assert sha(copy) == antes
                cerebro = SQLiteMemoryBioRAG(str(copy))
                try:
                    hits, total = cerebro.buscar_por_frase(a.query, profundidad='activos',
                        limite=5, ignore_peso_sinaptico=True)
                    filas = cerebro.conn.execute('SELECT concepto,contenido FROM largo_plazo ORDER BY concepto').fetchall()
                    result = {'sha_fuente': antes, 'query': a.query,
                              'total': total, 'hits': [{'concepto': r[0], 'score': r[4]} for r in hits],
                              'filas': filas}
                finally:
                    cerebro.cerrar_sistema()
            assert sha(source) == antes
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print('RESULTADO_JSON ' + json.dumps(result, ensure_ascii=False))
```
</details>

**Siguiente paso:** revisión del auditor y decisión de Dennys. No aplicar el diff ni iniciar las cuatro QA oficiales antes del OK.
