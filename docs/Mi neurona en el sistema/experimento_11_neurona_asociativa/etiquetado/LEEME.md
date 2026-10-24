# Hoja para marcar 100 pares a mano (opcional)

Para saber la **precisión real** de la neurona hace falta una muestra marcada por ti.

1. Abre `hoja_para_dennys.csv` (Excel, LibreOffice o Google Sheets).
2. En cada fila hay dos recuerdos tuyos con un resumen corto. En la columna `tu_respuesta` escribe:
   - `si`: tienen que ver; deberían estar conectados.
   - `no`: no tienen que ver.
   - `momento`: no hablan de lo mismo, pero son del mismo momento o proyecto (cuenta como sí).
   - `contradicen`: dicen cosas opuestas.
   - `nose`: no estás seguro.
3. Guarda el archivo como CSV con el mismo nombre y corre `python medir_hoja.py`.

La hoja **no** muestra qué opina la neurona ni de dónde salió cada par, para no influirte. Eso está
en `clave_no_mirar.json`; no lo abras antes de terminar.

Los 100 pares salen de 4 grupos mezclados (ver `preparar_hoja.py`): 40 que la neurona conserva,
30 que soltaría, 15 donde no está de acuerdo con Gemini y 15 conexiones nuevas que propondría.

**Privacidad:** la hoja muestra trozos de tus recuerdos. Por eso **no se sube a git** (hay un
`.gitignore` en esta carpeta). Si no la tienes, se genera con
`python preparar_hoja.py <ruta a una COPIA de la db>`.
