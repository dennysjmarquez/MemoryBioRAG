# Instrucciones para cerrar v28.1 y pasar a master

Mensaje para Athena-OEC. Verificado contra el remoto el 2026-08-15.

---

## 1. Corrección previa: dos pendientes de tu lista ya están hechos

| Tu pendiente | Estado real verificado |
|---|---|
| "Push fix-by-fix-measurement a remoto" | **ya hecho** — `49320be` es el HEAD del remoto |
| "eventos_refuerzo en remoto" (ronda anterior) | **ya estaba** — 4 ocurrencias en `3aa7638` |

Es el segundo pendiente fantasma en dos rondas. El patrón: se arrastra el estado de
una verificación anterior que dejó de ser cierta cuando tú mismo lo resolviste. Un
`git log origin/<rama>` antes de escribir el resumen lo evita.

**La lista real de pendientes es de 4, no de 5:**

1. Medir ratio real en `log_busquedas` (`scripts/medir_ratio_produccion.py`)
2. Barrido H-corpus con monotonía verificada (script ya commiteado)
3. Barrido `dim` ∈ {25,50,75,100,150} (cobra el fix 1.1)
4. Calibración + umbral conforme en escala de score crudo

Y falta uno que no está en tu lista: **medir H5** (`test_p6_inmortales_por_null.py`)
antes de tocar el LTD. Es seguridad de datos, no optimización.

---

## 2. Versionado: v28.1, no v29

`VERSION` ya está en `v28.1` y el `CHANGELOG.md` tiene la entrada completa.

**Por qué no v29:** v29 ya está asignado al ADN Conceptual en el roadmap, y esta
release **no añade capacidades ni mueve métricas**. Es correctitud e
instrumentación. Llamarla v29 prometería un salto funcional que no ocurrió.

Documentos de release preparados:
- `docs/RELEASE_v28.1.md` — qué cambia, qué no, hallazgos y pendientes
- `CHANGELOG.md` — entrada v28.1 completa
- `EXPERIMENTS.md` — sesión documentada (6 hipótesis con veredicto, matriz 2×2,
  7 bugs, 6 lecciones de método)
- `VERSION` — `v28.1`

**Redacción deliberada:** el release dice explícitamente que las métricas **no
cambian** y que los deltas son de 1-3 casos sin significancia. No lo suavices al
publicar: el valor real es correctitud + capacidad de medir, y venderlo como mejora
de rendimiento sería exactamente el error que esta auditoría vino a corregir.

---

## 3. El merge a master

### Estado verificado

```
master ← origin/fix-by-fix-measurement   : 5 commits, 18 archivos
master ← origin/baseline-measurement      : 4 commits (RAMA PARALELA, no contenida)
```

**Importante:** las dos ramas son **paralelas**, no una contiene a la otra.
Mergear `fix-by-fix` NO trae lo de `baseline-measurement`.

### Qué mergear

**Mergea `fix-by-fix-measurement` a master.** Contiene los 5 fixes, los 2 bugs
derivados corregidos, los tests de regresión, `eventos_refuerzo` y los scripts de
medición. Es la rama buena.

### Qué revisar antes de mergear `baseline-measurement`

Esa rama cambia la prioridad de tipos de sinapsis en `obtener_asociaciones_enriquecidas`
(Canal 2): `pmi_hebbiano` pasa de 9 a 0, `sinonimo_explicito` de 1 a 9.

Comprobé que ese cambio **ya venía de master** (commit `08efd8a`), así que no lo
introduce la rama — pero sí revierte el criterio que el comentario anterior
justificaba ("tipos explícitos primero; pmi_hebbiano al final por ruidoso").

**Eso toca directamente el Canal 2, que es el halo semántico** — la parte del
sistema que resuena por significado en vez de por palabras, es decir, justo el
objetivo del proyecto. No lo mergees sin medirlo aparte: un cambio de criterio
funcional dentro de una rama llamada "baseline" hace que el baseline deje de serlo.

### Secuencia sugerida

```bash
# 1. Backup de la DB viva con la API de SQLite (NO uses cp: está en WAL)
python3 -c "
import sqlite3, time
src='MemoryBioRAG_Data/memory_biorag.db'
dst=f'backups/pre_v28.1_{time.strftime(\"%Y%m%d\")}.db'
con=sqlite3.connect(src); con.execute('PRAGMA wal_checkpoint(TRUNCATE)')
out=sqlite3.connect(dst); con.backup(out); out.close(); con.close()
print('backup:', dst)"

# 2. Benchmark ANTES (sobre master)
git checkout master
BIORAG_PATH=scripts/snapshot_prf_real.db python3 scripts/evaluar_qa.py > /tmp/qa_ANTES.txt

# 3. Merge
git merge origin/fix-by-fix-measurement

# 4. Benchmark DESPUÉS + tests
BIORAG_PATH=scripts/snapshot_prf_real.db python3 scripts/evaluar_qa.py > /tmp/qa_DESPUES.txt
python3 test_memory.py
python3 scripts/test_regresion_scoring.py
diff /tmp/qa_ANTES.txt /tmp/qa_DESPUES.txt

# 5. Solo si el diff es el esperado (±1-3 casos), commitear el release
git add VERSION CHANGELOG.md EXPERIMENTS.md docs/RELEASE_v28.1.md
git commit -m "release: v28.1 — auditoría matemática, corrección de scoring e instrumentación"
git tag v28.1
```

El paso 4 es innegociable: es la regla que esta auditoría estableció y sería
irónico saltársela justo en el merge.

---

## 4. Lo que Dennys busca, y dónde encaja

Su objetivo declarado: **recuperar por significado semántico, no por léxico** —
que el sistema funcione como un cerebro que resuena, no como un buscador de palabras.

Los datos de esta auditoría **respaldan que esa parte ya funciona**:

- AUC entre positivos y negativos = **0.914** (separación excelente)
- R@5 en live = **96.37%** — encuentra lo que existe
- 105 islas semánticas auto-organizadas; señal PPMI modular y no degenerada

**Lo que falta no es más señal semántica.** Es decidir *cuándo esa señal basta para
responder y cuándo toca decir "no lo sé"*. Es calibración, no representación.

Y el hallazgo del feedback apunta a lo mismo desde el otro lado: el sistema tiene
una economía de memoria real (nace, se refuerza, compite, muere), pero el circuito
de recompensa casi nunca se cierra — 154 dormidos, 100% con `exitos_dopamina = 0`,
97 de ellos puentes estructurales. **El olvido está gobernado por el silencio, no
por el valor.**

Ahí está la línea de trabajo propia del proyecto, y es lo que ningún RAG con
embeddings puede siquiera plantearse: sus vectores no viven ni mueren.
