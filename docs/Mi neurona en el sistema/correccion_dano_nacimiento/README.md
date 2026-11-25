# Corrección del daño en el nacimiento de sinapsis (25-11)

**Objetivo del ciclo:** corregir primero el daño estructural en el nacimiento y la actualización de
sinapsis, antes de seguir con la neurona asociativa. Todo de forma **agnóstica al idioma**: sin listas de
palabras ni reglas de un idioma.

**Orden pedido:**
1. proteger `manual`;
2. sinónimos exactos y sin reetiquetar;
3. palabras vacías sin diccionarios.

Cada cambio va por separado, con tests nuevos y la suite en verde.

**Base:** `docs/ALGORITMO_NACIMIENTO_SINAPSIS.md`, problemas P1, P2, P6 y P7.

## Resultado

| Paso | Commit | Antes | Después | Suite |
|---|---|---|---|---|
| línea base | `d984779` | — | — | 1110 passed, 18 skipped |
| **Cambio 1:** las reglas automáticas no tocan `manual` ni `manual_v7` | `7e1eb9c` | 6/6 tests nuevos fallan (manual 0.5 → 0.55, 0.65, 0.9 o 0.6, y `ultimo_uso` pisado) | 6/6 pasan; los controles automáticos siguen cambiando igual | 1116 passed |
| **Bug destapado:** `vincular_con` con espacio después de la coma | `555b06e` | crea un enlace manual a `_nodo` (un nodo que no existe) | enlaza con `nodo` | (incluido abajo) |
| **Cambio 2a:** sinónimos por coincidencia exacta | `6d64515` | 4/7 tests nuevos fallan | 7/7 pasan | **1123 passed**, 18 skipped, 0 failed |
| Cambio 2b: no reetiquetar nunca | — | **pendiente de decisión** | — | — |
| Cambio 3: palabras vacías | — | **no aplicado** (ver abajo) | — | — |

**Traza real** (`estudio_nacimiento_aprender_consolidar/trazar.py`, misma semilla):
- **Tras el cambio 1** (`salida_traza_tras_cambio1.txt`): solo desaparecen las dos modificaciones que se hacían
  sobre el manual (0.50 → 0.60, y `ultimo_uso` pisado). Todo lo demás sale idéntico.
- **Tras el cambio 2a** (`salida_traza_tras_cambio2a.txt`): idéntica a la del cambio 1. En esa traza los
  reetiquetados a `sinonimo_explicito` venían de ítems **exactos** («tomate», «receta» y «rojo» estaban tal cual
  en las listas de sinónimos), no de subcadenas. **El 2a no corrige ese caso.** Ese caso es el 2b.

No se tocaron los tests existentes, el ranking, el canal 1, el filtro de búsqueda, el instalador, las
dependencias ni ninguna base real. Solo se usaron bases temporales en `tmp_path` o `/tmp`.

## Cambio 1: qué se cambió

`ON CONFLICT DO UPDATE ... WHERE sinapsis.tipo NOT IN ('manual','manual_v7')` (constante
`SQL_UPSERT_NO_ES_DEL_AGENTE` en `core/memory/constants.py`), aplicado en:
- B1–B4, `auto_vincular`, y B5, `vincular_por_sinonimos` (`core/sinapsis.py`);
- B6 y B7, la co-ocurrencia de sesión y la de comunicaciones (`core/memory/consolidation.py`);
- B10, el refuerzo de ráfaga (`core/memory/rafaga.py`), con un `AND tipo NOT IN (...)` en el `UPDATE`.

El auditor nombró B6, B7 y B10. Al revisarlo, **B1–B5 también subían los manuales** (con `MAX`), así que se
incluyeron.

**No se tocaron**, porque los decide el agente y no son automáticos:
- el refuerzo por feedback explícito (`aplicar_refuerzo_dopaminergico`);
- `ensenar_expresion`.

**Tests:** `tests/test_manual_intocable_en_nacimiento.py`. Cada uno lleva un **control** con un enlace automático
que sí debe cambiar, para demostrar que el camino se ejecutó.

## Cambio 2a: qué se cambió

`vincular_por_sinonimos` enlaza solo si el sinónimo declarado es **exactamente** el nombre del otro recuerdo o
**exactamente** uno de los ítems de su lista de sinónimos.

**La comparación** (`_norma_sinonimo`) no depende de ningún idioma:
- `normalizar_identidad`, la identidad Unicode que ya usa el proyecto (NFC y plegado de ancho);
- `casefold`;
- `_` y `-` como espacio;
- espacios colapsados.

El `LIKE` queda solo como prefiltro.

**Casos cubiertos** (`tests/test_sinonimos_coincidencia_exacta.py`):

| Caso | Resultado |
|---|---|
| «sal» frente a «salsa» | ya no enlaza |
| «番茄» frente a «番茄酱» | ya no enlaza |
| «Luz Roja» frente a `luz_roja` | sí enlaza (antes no) |
| «Luz Roja» frente a `luz_roja_trasera` | no enlaza |
| **puentes:** «rojo» declarado en dos recuerdos de temas distintos | **siguen naciendo** |
| sinónimo real nuevo | nace con 0.9 y tipo `sinonimo_explicito`, igual que antes |
| enlace manual | no se toca |

**Límite conocido:** el prefiltro `LIKE` de SQLite solo ignora mayúsculas y minúsculas en ASCII. Las letras no
ASCII escritas con otra caja (por ejemplo «Ñ» frente a «ñ») pueden no encontrarse. **Ese límite ya existía
antes.**

### Bug destapado por el cambio 2a

En `core/mcp_server/write.py`, `vincular_con="a, b"` hacía `item.lower().replace(" ", "_").strip()`, de modo que
el espacio que va después de la coma se convertía en `_` y el destino quedaba como `_b`, un nodo inexistente.
El test `test_preflight_vincular_con::test_aprender_con_vincular_con_formato_string` pasaba solo porque el
sinónimo «nodo» del test enlazaba a `nodo_str_2` por subcadena.

**Arreglo:** hacer `strip()` primero. Se verificó también **por separado**, con el B5 anterior: 4/4.

## Pendiente 2b: ¿reetiquetar cuando el sinónimo sí es exacto?

**El conflicto:**
- Al aprender, `auto_vincular` corre **antes** que los sinónimos. Por eso un par que comparte un sinónimo exacto
  casi siempre ya existe como `co_nombre` o `co_ocurrencia`.
- Hoy B5 lo sube a 0.9 y lo convierte en `sinonimo_explicito`.
- Si se prohíbe reetiquetar, **ningún sinónimo declarado llegaría a ser `sinonimo_explicito`** en esos pares.
- Eso rompe `tests/test_neurona_asociativa_motor.py::test_guardar_usa_pesos_a_mano_aunque_la_neurona_este_encendida`,
  que fija «0.9 de siempre». Los tests existentes no se pueden modificar.

**Lo de fondo:** en el uso real, «sinónimos» funciona como etiquetas («tomate», «receta», «rojo»). Una regla no
puede saber si un ítem compartido es un **sinónimo**, un **tema** o un **puente**. Esa es justo la decisión que
le corresponde a la neurona asociativa. **Propuesta:** no tocar el 2b con reglas y resolverlo en el diseño de la
neurona. **Decide Dennys.**

## Cambio 3 (palabras vacías): por qué no se aplicó

**1. Un filtro por frecuencia en la propia base rompe la Norma Máxima.**
- La propuesta era descartar las palabras con frecuencia documental (DF) alta.
- Pero la DF depende de **todos** los recuerdos. Si se agregan recuerdos irrelevantes I, cambia qué palabras
  pasan el filtro, y con eso cambia qué enlaces nacen entre los recuerdos de D.
- Es decir, F(D) ≠ F(D ∪ I), una dependencia nueva y directa del tamaño del corpus.

**2. El problema multilingüe es más profundo que B6–B8** [verificado]:
- `\w{4,}` sobre chino o japonés devuelve **cláusulas enteras** como una sola «palabra». Ejemplos:
  `['番茄是一种水果', '我们今天做番茄酱']` y `['トマトは赤い野菜です', 'トマトソースを作ります']`.
- Por eso, en esos idiomas, B6, B7 y B8 **casi nunca enlazan**. No crean enlaces falsos: no crean ninguno.
- B1, B2 y B4 usan `core/stopwords.py`, una lista de **336 palabras en español e inglés**. El sistema ya depende
  del idioma en su tokenización base.

**3. Opciones para decidir:**
- **(A)** Especificidad local al lote: descartar las palabras que comparten casi todos los recuerdos que se
  consolidan juntos. No depende del corpus de largo plazo, pero sí de qué más se aprendió en la misma sesión.
- **(B)** Que B6 y el respaldo de B8 cuenten palabras con el mismo tokenizador que B1. No es agnóstico, porque
  hereda la lista ES/EN.
- **(C)** Dejarlo para la neurona asociativa: la especificidad entra como una señal más, con una referencia
  **congelada por contrato** para respetar la invariancia.
- **(D)** Tokenización universal (segmentación Unicode o n-gramas de caracteres para escrituras sin espacios).
  Es un cambio de la base del motor y afecta también a la búsqueda. **Fuera de alcance mientras el filtro de
  búsqueda siga congelado (E3).**

**Recomendación:** no aplicar un filtro DF. Elegir entre (A) y (C), y dejar (D) como trabajo propio y aparte.
**Decide Dennys.**

## Reproducir

```
python3 -m venv /tmp/venv && /tmp/venv/bin/pip install -r requirements.txt
HOME=/tmp/h /tmp/venv/bin/python -m pytest tests/test_manual_intocable_en_nacimiento.py \
    tests/test_sinonimos_coincidencia_exacta.py tests/test_preflight_vincular_con.py -q
HOME=/tmp/h /tmp/venv/bin/python -m pytest tests/ -q          # 1123 passed, 18 skipped
```
