# Auditoría en GitHub Actions (QA del snapshot)

**Por qué existe.** Las máquinas de trabajo de Arena se reinician cada ~50 minutos y las QA oficiales tardan más. Los servidores de GitHub no se reinician. Dennys autorizó (2026-10-28) correr allí las 2 QA del **snapshot** (que ya está en el repo). La base viva **nunca** se sube: sus 2 QA se corren en las máquinas de trabajo.

**Por qué el archivo está aquí y no en `.github/workflows/`.** La app de GitHub que usan los agentes no tiene permiso para crear flujos de trabajo (`workflows`). Un humano con permiso debe copiarlo a `.github/workflows/auditoria_qa_snapshot.yml` en la rama `arena/6459e2d0-memorybiorag`. Al hacerlo, el flujo arranca solo.

**Qué hace.** Ver el encabezado de [`auditoria_qa_snapshot.yml`](auditoria_qa_snapshot.yml):
- toma el código del operador fijado por SHA y le aplica (o no) el parche B4a, verificando las huellas;
- corre las 2 QA del snapshot para B3 y para B4a en el mismo entorno (Debian 12: Python 3.11.2 / SQLite 3.40.1);
- compara B3 contra B4a y B3 de GitHub contra B3 de Arena.

**Qué no hace.** No toca el motor, ni `ci.yml`, ni ninguna base. Es una herramienta temporal de la auditoría E3: se retira antes del tag v36.0 si no se decide conservarla.
