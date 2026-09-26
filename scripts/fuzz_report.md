# Reporte de Fuzzing / Pruebas Adversariales (Fase 2A)

- **Fecha de ejecución:** 2026-09-26
- **Total de casos evaluados:** 33
- **Casos Aprobados:** 33
- **Casos Fallidos:** 0

## Tabla Resumen de Resultados

| # | Categoría | Caso de Prueba | Estado | Duración | Motivo de Fallo |
|---|-----------|----------------|--------|----------|-----------------|
| 1 | 1. Vacío y casi vacío | String vacío | ✅ APROBADO | 3.2638s | Ninguno (Comportamiento correcto) |
| 2 | 1. Vacío y casi vacío | Solo espacios | ✅ APROBADO | 0.0005s | Ninguno (Comportamiento correcto) |
| 3 | 1. Vacío y casi vacío | Un solo carácter | ✅ APROBADO | 0.0424s | Ninguno (Comportamiento correcto) |
| 4 | 2. Extremadamente largo | Query de 60,000 caracteres | ✅ APROBADO | 0.9227s | Ninguno (Comportamiento correcto) |
| 5 | 2. Extremadamente largo | Paráfrasis de 20,000 caracteres | ✅ APROBADO | 0.5124s | Ninguno (Comportamiento correcto) |
| 6 | 3. Comillas desbalanceadas | Una comilla doble abierta | ✅ APROBADO | 1.1959s | Ninguno (Comportamiento correcto) |
| 7 | 3. Comillas desbalanceadas | Comillas múltiples vacías | ✅ APROBADO | 0.0010s | Ninguno (Comportamiento correcto) |
| 8 | 3. Comillas desbalanceadas | Comillas anidadas extrañas | ✅ APROBADO | 0.0600s | Ninguno (Comportamiento correcto) |
| 9 | 4. Caracteres de control | Byte nulo en query | ✅ APROBADO | 0.8063s | Ninguno (Comportamiento correcto) |
| 10 | 4. Caracteres de control | Saltos de línea múltiples | ✅ APROBADO | 0.5567s | Ninguno (Comportamiento correcto) |
| 11 | 5. Caracteres SQL | Inyección SQL clásica | ✅ APROBADO | 1.9794s | Ninguno (Comportamiento correcto) |
| 12 | 5. Caracteres SQL | Comilla simple suelta | ✅ APROBADO | 0.0008s | Ninguno (Comportamiento correcto) |
| 13 | 5. Caracteres SQL | Comodines de LIKE | ✅ APROBADO | 0.3831s | Ninguno (Comportamiento correcto) |
| 14 | 5. Caracteres SQL | Or condition injection | ✅ APROBADO | 0.5525s | Ninguno (Comportamiento correcto) |
| 15 | 6. Unicode raro | Emojis y símbolos | ✅ APROBADO | 0.0010s | Ninguno (Comportamiento correcto) |
| 16 | 6. Unicode raro | Árabe y Chino | ✅ APROBADO | 1.2153s | Ninguno (Comportamiento correcto) |
| 17 | 6. Unicode raro | Zero-width space | ✅ APROBADO | 1.2463s | Ninguno (Comportamiento correcto) |
| 18 | 6. Unicode raro | Zalgo text | ✅ APROBADO | 0.4654s | Ninguno (Comportamiento correcto) |
| 19 | 7. JSON dimensiones malformado | JSON desbalanceado | ✅ APROBADO | 0.0001s | Ninguno (Comportamiento correcto) |
| 20 | 7. JSON dimensiones malformado | JSON tipo incorrecto (string) | ✅ APROBADO | 0.0001s | Ninguno (Comportamiento correcto) |
| 21 | 7. JSON dimensiones malformado | JSON array vacío | ✅ APROBADO | 0.0001s | Ninguno (Comportamiento correcto) |
| 22 | 7. JSON dimensiones malformado | JSON valor no array | ✅ APROBADO | 0.0001s | Ninguno (Comportamiento correcto) |
| 23 | 7. JSON dimensiones malformado | JSON anidamiento excesivo | ✅ APROBADO | 0.0001s | Ninguno (Comportamiento correcto) |
| 24 | 8. Números fuera de rango | Página negativa | ✅ APROBADO | 0.4741s | Ninguno (Comportamiento correcto) |
| 25 | 8. Números fuera de rango | Página gigante | ✅ APROBADO | 0.4761s | Ninguno (Comportamiento correcto) |
| 26 | 8. Números fuera de rango | Límite cero | ✅ APROBADO | 0.0000s | Ninguno (Comportamiento correcto) |
| 27 | 8. Números fuera de rango | Límite negativo | ✅ APROBADO | 0.0000s | Ninguno (Comportamiento correcto) |
| 28 | 8. Números fuera de rango | context_window excesiva | ✅ APROBADO | 0.0000s | Ninguno (Comportamiento correcto) |
| 29 | 8. Números fuera de rango | context_window negativa | ✅ APROBADO | 0.0000s | Ninguno (Comportamiento correcto) |
| 30 | 9. Parámetros lista malformados | Comas consecutivas en parafrasis | ✅ APROBADO | 0.4842s | Ninguno (Comportamiento correcto) |
| 31 | 9. Parámetros lista malformados | Solo comas en parafrasis | ✅ APROBADO | 0.4721s | Ninguno (Comportamiento correcto) |
| 32 | 9. Parámetros lista malformados | rafaga_palabras vacío | ✅ APROBADO | 0.0000s | Ninguno (Comportamiento correcto) |
| 33 | 10. Mezcla de fallos | SQL injection + Byte nulo + Zalgo + JSON dañado | ✅ APROBADO | 0.0000s | Ninguno (Comportamiento correcto) |

## Detalle de Casos Fallidos e Incidentes

No se detectaron fallos. El sistema manejó correctamente todas las entradas adversariales sin tracebacks no controlados, sin mutaciones de estado y dentro de los límites de tiempo.
