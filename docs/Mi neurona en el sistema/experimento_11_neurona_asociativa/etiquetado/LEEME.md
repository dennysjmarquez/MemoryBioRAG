# Hoja para marcar 100 pares a mano (opcional)

Para saber la **precisión real** de la neurona hace falta una muestra marcada por ti. La neurona
**no aprende** de tus respuestas: la hoja es un examen.

## 1. Generar la hoja (en tu máquina, una vez)

La hoja **no está en git** porque muestra trozos de tus recuerdos y el repo es público. Se genera en
un segundo desde la raíz del repo:

```bash
cd "docs/Mi neurona en el sistema/experimento_11_neurona_asociativa/etiquetado"
python preparar_hoja.py
```

- Sin argumentos usa el snapshot del repo (`snapshots/qa_escape_qcr_20260811.db`).
- Nunca lee la DB original: primero la copia a un archivo temporal y trabaja sobre la copia.
- La semilla es fija, así que siempre sale la misma hoja.

Crea tres archivos en esta carpeta:

| Archivo | Para qué |
|---|---|
| `hoja_para_dennys.html` | **La forma fácil.** Ábrela con doble clic en el navegador |
| `hoja_para_dennys.csv` | La misma hoja, para Excel, LibreOffice o Google Sheets |
| `clave_no_mirar.json` | De dónde salió cada par y qué opina la neurona. **No lo abras antes de terminar** |

## 2. Marcar

En cada par hay dos recuerdos tuyos con un resumen. Para cada par eliges una respuesta:

- **sí**: tienen que ver; deberían estar conectados.
- **no**: no tienen que ver.
- **mismo momento**: no hablan de lo mismo, pero son del mismo momento o proyecto (cuenta como sí).
- **se contradicen**: dicen cosas opuestas.
- **no sé**: no estás seguro.

**En el HTML:**
- Pulsas un botón por par. Tus respuestas se guardan solas en el navegador, así que puedes cerrarlo y
  seguir otro día.
- Arriba ves cuántos pares llevas.
- Al terminar, pulsas **Descargar respuestas**. Te baja `hoja_para_dennys.csv`; ponlo en esta carpeta
  en lugar del que está.

**En el CSV:** escribe `si`, `no`, `momento`, `contradicen` o `nose` en la columna `tu_respuesta` y
guarda como CSV con el mismo nombre.

## 3. Ver el resultado

```bash
python medir_hoja.py
```

## Qué decide cada grupo

Los 100 pares salen de 4 grupos mezclados:

| Grupo | Pares | Qué son | Qué decide |
|---|---|---|---|
| A | 40 | Conexiones que la neurona conserva | La precisión real |
| B | 30 | Conexiones que soltaría | Si cada recuerdo se queda con 10 o con 20 socios |
| C | 15 | Desacuerdos con Gemini | Si la neurona puede reemplazar a la hormiguita |
| D | 15 | Conexiones nuevas que propondría | Si la neurona propone o solo juzga |
