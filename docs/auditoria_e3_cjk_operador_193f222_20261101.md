# Auditoría E3: propuesta CJK del operador `193f222`

## Veredicto

**Investigación útil, no aprobada para aplicación.** La comparación pareada propia confirma la mejora sintética informada y el nuevo resultado en un negativo japonés. La adición de candidatos puede aportar pistas; un resultado irrelevante en este control no autoriza a borrar pistas ni demuestra daño general. A la vez, todavía no hay evidencia suficiente de seguridad de ranking, coste y comportamiento agente + cerebro en corpus y consultas variados. El segundo parche, de umbral dos, es diagnóstico y pierde dos recuperaciones frente al OR amplio; no se recomienda convertirlo en filtro. E3 sigue abierto.

El commit del operador `193f2226f5aef19f602d6cd8a2455c9b6dc55c89` contiene informes, dos parches marcados NO APLICAR, scripts y resultados; **no cambia `core/memory/search.py`**. La auditoría se hizo desde `5fcdac24a6cc7ab59d6987563cb62de7e95c92d4`; las rutas `core/`, `middleware/`, `config/`, evaluador y gold no difieren entre ambos commits. No se aplicó nada al árbol de trabajo ni a una base de usuario, no se ejecutó campaña E1 ni se entrenó.

## Lectura del diff

El candidato OR agrega al pool resultados FTS en base a trigramas extraídos de rangos chino, kana y hangul; agrega su nuevo origen a `_ORIGENES_NO_LITERALES`. Se aplicó exclusivamente sobre una **copia temporal** para los ensayos. El SHA-256 del diff exacto es `104b7aa0a74e3fa3441f84102756529b5a7c0c2597e518e013341d9536486bb2`; el del umbral de diagnóstico es `dc1a1d1a337a39d6af8c08ee628081915180f604c4f1e0c1fac292a4aa1cbd3b`.

Puntos que requieren resolución y medición antes de proponer aplicación:

1. **Adición no garantiza conservación de salida ni ranking.** Los candidatos adicionales alteran el pool y los valores BM25 usados para normalización; etapas posteriores como QCR, ranking y paginación pueden cambiar lo devuelto. El nuevo origen evita el filtro final de prefijo, pero también entra en otras decisiones basadas en `_ORIGENES_NO_LITERALES`, incluida la convergencia. No afirmar que agregar al pool garantiza conservar todos los vecinos o pistas en la salida. En esta muestra sí se conservaron los top-5 previos, no es prueba general.
2. El código extrae solo caracteres dentro de esos rangos y los concatena antes de formar trigramas: puede formar fragmentos artificiales atravesando espacios, puntuación, texto latino o cambios de escritura. También incluye hangul, no solo chino/japonés. Deben probarse mezclas, conectores y límites Unicode sin descartar expresiones significativas; no imponer normalización global.
3. La consulta OR y `fetchall()` pueden crecer con la longitud de la consulta y la cantidad de coincidencias; no se midieron costo, memoria, p95, tamaño de corpus o consultas largas/adversariales. No hay datos para afirmar complejidad segura ni tiempo constante.
4. `sqlite3.OperationalError` se captura silenciosamente: un error de FTS puede desactivar el rescate sin quedar visible. Debe caracterizarse y hacerse observable en cualquier diseño futuro, sin convertir error en éxito.
5. El runner del operador copia `core` pero usa enlaces a `config`, `middleware` y `MemoryBioRAG_Data`, hereda variables de entorno y no fija explícitamente el estado DMN. No lo ejecuté sobre archivos de usuario. La comparación siguiente usa otra herramienta, entorno limpio, copias Git y estado temporal para evitar depender de esos enlaces. Esto **no prueba** que su corrida haya modificado datos reales.

## Comparación pareada independiente

`scripts/auditar_cjk_pareado_sintetico.py` (SHA `bb85a34c7f7646a0fe04a2ca4f854ac79120f92eea796409f1996a4a477b3c39`) creó **una sola** base E3A sintética de 120 recuerdos, integridad comprobada y WAL evacuado. SHA de la fuente `2c24e12136e6d761dc474abe2674406cc48ec641b2ba03d42ae114bb3bbae3a5`. Cada brazo se ejecutó en proceso separado: motor base, OR y umbral 2; cada una de las 132 consultas abrió su propia copia limpia de esa fuente y estado DMN independiente. El SHA de la fuente no cambió. Reloj fijo, Python 3.11.2, SQLite 3.40.1, NumPy 2.4.6, NLTK 3.9.4, `PYTHONHASHSEED=0`, `BIORAG_NEURONA=0`, `BIORAG_NO_LOG=1`; búsqueda directa activos, límite 5 y peso sináptico ignorado. Gold SHA `d3665a8e895ba061354ddd7d9c4fe44614956ad79d663433c6ef70e59aa78a6a`. No se repitió el orden inverso en esta auditoría; el operador sí lo reporta por separado.

| Idioma | Base R@5 / R@1 / FP | OR R@5 / R@1 / FP | Umbral 2 R@5 / R@1 / FP |
|---|---:|---:|---:|
| zh | 12/20 / 12/20 / 0/2 | 19/20 / 19/20 / 0/2 | 17/20 / 17/20 / 0/2 |
| ja | 12/20 / 12/20 / 0/2 | 19/20 / 19/20 / 1/2 | 19/20 / 19/20 / 0/2 |
| ko | 19/20 / 18/20 / 0/2 | igual | igual |
| ru | 20/20 / 19/20 / 0/2 | igual | igual |
| en | 20/20 / 20/20 / 2/2 | igual | igual |
| es | 20/20 / 20/20 / 0/2 | igual | igual |

OR: 14 positivos mejoran de rango, ninguno baja frente a base; **un negativo nuevo con resultado, `ja-n01`**. En 15/132 consultas cambia la lista o score. En esta batería no se encontró ningún resultado del top-5 base ausente del top-5 del OR; esto no comprende resultados fuera del top-5 ni otras bases. `zh-18` y `ja-17` siguen sin recuperar. Los dos FP ingleses persisten.

Umbral 2: 12 positivos mejoran frente a base, ninguno baja frente a base, ningún FP nuevo en esos 12 negativos; comparado con el OR amplio **pierde `zh-11` y `zh-14`**. No presentar la ausencia de FP en cuatro negativos CJK como seguridad general ni tomar el umbral como regla de descarte.

El control es una sola fixture sintética, sin traducción validada por hablantes independientes; no son las cuatro QA oficiales ni una prueba MCP o de un agente real. No cuantifica el impacto de las pistas indirectas, recall en corpus reales, latencia o comportamiento en bases grandes. R@5 y FP se entienden bajo el gold de esta fixture.

## Prueba de pista del operador

Se reprodujo su script de handlers MCP directamente en base temporal: exit 0, integridad `ok`; consulta libre sin seed, consulta alineada con seed y destino en contexto expandido. Confirma ese trayecto construido con una arista manual, no stdio, no un agente independiente ni una medida general de seguimiento. El script original incluye en su salida datos de aristas sintéticas; la salida detallada quedó privada, sin publicar pesos en el informe.

## Próximo trabajo para el operador

- Mantener ambos parches sin aplicar y conservar el OR como línea de investigación, no como filtro de pistas. La cifra de FP es una señal para examinar relevancia y conducta del conjunto agente + BioRAG; no borrar el candidato automáticamente para mejorar el marcador.
- Preparar controles sintéticos adicionales, **pareados sobre la misma base**, para mezclas de alfabetos, conectores, textos largos, colisiones, seguridad de error FTS, retención de candidatos/vecinos y cambios en el ranking. Medir costo y escala sin exponer bases originales. Incluir caracteres CJK fuera de los rangos y hangul para delimitar cobertura, sin prometer que un parche limitado resuelva todos los idiomas.
- Si emerge una mejora concreta, proponer diff exacto y baseline; medir cuatro QA oficiales pertinentes en copias y pruebas MCP/agente + cerebro cuando estén autorizadas, manteniendo resultados negativos y pistas útiles. No cambiar motor, entrenar neurona ni ejecutar campaña E1 sin autorización específica.

## Reproducción y evidencia

Con dependencias instaladas, fetch del commit del operador y nombres de salida nuevos:

```bash
git fetch origin refs/heads/arena/9a54babb-memorybiorag:refs/remotes/origin/arena/9a54babb-memorybiorag
env -i HOME="$HOME" PATH="$PATH" python scripts/auditar_cjk_pareado_sintetico.py \
  --salida google_drive/auditoria_neuronas/e3_cjk_pareado_nuevo
```

El script usa `git archive` de HEAD y valida igualdad de `search.py` y gold con el commit del operador antes de aplicar parches solo en directorios temporales; usa NLTK local y elimina las bases temporales. Las dependencias restantes deben cotejarse si HEAD cambia. El script no limita el resultado a un resumen: guarda los 132 casos y scores sintéticos por brazo en la ruta indicada. La evidencia de esta corrida, incluyendo logs privados, está en `google_drive/auditoria_neuronas/auditoria_cjk_193f222_pareada.tar.gz`, SHA `d5bfa45b11f99fa8066e2f17cb294680b6392b2593bef7e297f3e8b666ddec26`, copia privada Drive `16REj5WF9aGfkn6XEKvbl1vXd5btSv4L_` con checksum cotejado. El resumen pareado tiene SHA `0c74fb2a267446710a9449840bb2ab0f15ac63fd6e40282aeaa7a7a97008e99e`.
