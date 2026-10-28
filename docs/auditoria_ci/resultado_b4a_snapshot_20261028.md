# Resultado: QA del snapshot en GitHub Actions (B3 frente a B4a), 2026-10-28

**Corrida:** https://github.com/dennysjmarquez/MemoryBioRAG/actions/runs/40753126307 (flujo `auditoria_qa_snapshot.yml`, commit `c454d0b`).
**Código medido:** rama del operador fijada en `4d8306155246e6f4bea4d28e9151cbd6630bad7f`; B4a = ese código + `docs/e3b4a_diff_aplicado_20261028.patch`.
**Huellas verificadas en cada trabajo, al inicio y al final:** `search.py` `f4479e7d…`, `memory_store.py` `b7e7219c…`, test `68f89c4c…`, snapshot `104dd290…`.
**Entorno:** contenedor Debian 12 (Python 3.11.2 / SQLite 3.40.1), dependencias de `requirements.txt`.
**Duración:** normal 12–15 min; con ruido 27–35 min. Todo en verde.

El cuadro de resumen lo transcribió el auditor de la captura que envió Dennys (la máquina del auditor no puede descargar los registros de GitHub).

| Escenario | B3 en GitHub (R@5 / R@1 / FP) | B4a en GitHub (R@5 / R@1 / FP) | B3 vs B4a (mismo entorno) | B3 Arena vs B3 GitHub |
|---|---|---|---|---|
| snapshot sin ruido | 100,0 / 95,31 / 0 de 40 | 100,0 / 95,31 / 0 de 40 | **IGUALES** | **IGUALES** |
| snapshot con ruido `zzqx` | 97,34 / 88,63 / 0 de 40 | 97,34 / 88,63 / 0 de 40 | **IGUALES** | **IGUALES** |

MRR: sin ruido 0,9718; con ruido 0,9281 (iguales en B3 y B4a). "IGUALES" significa que `comprobar_escenario` (de `scripts/comprobar_igualdad_qa_b3.py`) no encontró diferencias en: fuente, corpus, cada categoría, R@5 y R@1 honestos, métricas globales, FP 0/40 y censo temático.

**Conclusiones:**
1. En el snapshot, B4a no cambia nada respecto de B3: piso respetado.
2. **Reproducibilidad:** B3 medido en GitHub es idéntico, categoría por categoría, a B3 medido en Arena por el operador. El resultado se repite en otra máquina.
3. Pendiente para cerrar B4a: las 2 QA de la base viva (no se sube a GitHub; se corren en las máquinas de trabajo).

**Límites de esta evidencia (señalados por el operador, aceptados por el auditor):**
1. **La huella final del test no se registró.** El flujo verificó `tests/test_prefijo_ancho_b4a.py` al inicio, pero al final solo midió `search.py`, `memory_store.py` y el snapshot. Impacto: ninguno sobre la QA, porque `evaluar_qa.py` no ejecuta ese test; las dos piezas del motor sí se verificaron al final. Se corregirá en la próxima versión del flujo.
2. **El verde no prueba "B3 Arena = B3 GitHub".** El paso solo falla si B3 ≠ B4a; la comparación con Arena se informa en el resumen sin detener el flujo. La evidencia de esa igualdad es el **texto del resumen** de la corrida ("IGUALES" en los dos escenarios), que cualquiera puede leer en el enlace de arriba; no el color verde. En la próxima versión, esa diferencia también hará fallar el paso.

## Base viva, medida por el auditor en su máquina (Arena)

Fuente: copia reconstruida del volcado de Drive del 26-10-2026 (MD5 `34650056…`), SHA-256 `a61913ce…`, abierta en solo lectura; la QA trabaja en su copia. Código: `4d83061` + parche B4a (huellas `f4479e7d…` / `b7e7219c…`, verificadas al inicio y al final). Python 3.11.2 / SQLite 3.40.1. Comparación con `docs/e3b3_viva_*_20261028.json` mediante `comprobar_escenario`.

| Escenario | B3 (operador) R@5 / R@1 / FP | B4a (auditor) R@5 / R@1 / FP | Diferencias |
|---|---|---|---|
| viva sin ruido | 99,88 / 93,53 / 0 de 40 | 99,88 / 93,53 / 0 de 40 | **NINGUNA (iguales en cada categoría)** |
| viva con ruido `zzqx` | 96,63 / 88,12 / 0 de 40 | 96,63 / 88,12 / 0 de 40 | **NINGUNA (iguales en cada categoría)** |

SHA-256 de los JSON de métricas del auditor: con ruido `b6e07ab4768a6e390738a4b6020c9c29edf75343048ce4e5aca85c6a39750c9a` (código de salida 1 por la compuerta clásica, igual que en B3); sin ruido: `7a7fc51d5da7db08968d26c4bd58933b8cb5984e5f5e54736919d6f64a29ab5e`. No se sube el JSON ni los fallos porque contienen títulos de recuerdos de la base viva.

## Veredicto del auditor sobre B4a: **APROBADO** (2026-10-28)

Las **4 QA oficiales** son iguales a B3 en cada categoría, con FP 0/40: snapshot sin ruido y con ruido (GitHub Actions), viva sin ruido y con ruido (máquina del auditor). Pruebas: 721/721. Condición para el commit del motor: debe ser **idéntico al parche** `b622ddb` (mismas huellas de `search.py`, `memory_store.py` y el test). Sin merge: el OK final es de Dennys.

**Lección operativa:** la máquina de trabajo de Arena **se congela cuando el agente termina su turno**; los procesos en segundo plano solo avanzan mientras el agente sigue trabajando (comprobado: `etime` de las QA avanzó ~2 min en ~18 min de reloj entre turnos, y normal durante las esperas dentro del turno). Para QA largas, el agente debe **quedarse esperando dentro de su turno** (esperas de hasta 30 min seguidas) hasta que terminen.
