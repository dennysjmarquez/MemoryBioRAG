# Experimento 18 — Protocolo v2 (E1 y E2): piso mecánico frente a MLP, con resonancia independiente

**Fijado y subido ANTES de medir** (2026-11-25, rama `arena/da3df5df-memorybiorag`).

- Sustituye las §2, §5 y §6 de `PROTOCOLO.md` (v1). La v1 queda tal cual, porque **E0 se midió con ella**.
- Los motivos del cambio están en `RESULTADOS_E0.md`, `AUDITORIA_RANKING_LEE_SINAPSIS.md` y
  `DECISIONES_CONSENSO.md`.
- No se cambia ningún umbral después de ver resultados.

> **Enmienda del 2026-11-25, antes de cualquier medición:** `ignorar_sinapsis` también excluye la señal #13
> de PPMI, la analogía, el campo potencial y el fallback SDM, porque sus índices se construyen con las
> sinapsis. Ver «Corrección» en `AUDITORIA_RANKING_LEE_SINAPSIS.md`. Ningún umbral cambia.

## 1. Qué cambia frente a la v1 y por qué

| v1 | v2 | Motivo |
|---|---|---|
| Entradas N1 (n-gramas) y N2 (NCD) | **Fuera** | E0: no pasan (AUC 0,54–0,70; Spearman ≤ 0,32) |
| Coactivación por repaso con la búsqueda real | **Resonancia independiente:** repaso con `ignorar_sinapsis` | El ranking lee las sinapsis (hasta el 10 % del puntaje): sin esto se forma el bucle |
| Evidencia (a) del piso: N1 ≥ percentil 75 del nodo | (a) = **estructura declarada por el agente**, compartida por igualdad exacta normalizada | N1 no pasó E0 |
| — | **Prueba del bucle** y **puerta MLP frente al piso** | Consenso de las 13 opiniones |

## 2. Entradas (todas sin idioma, sin telemetría y sin el agente)

| Entrada | Definición | Invariancia |
|---|---|---|
| **S. estructura declarada** | número de campos compartidos por igualdad exacta normalizada (`_norma_sinonimo`): dimensiones (por ID), sustantivos clave, sinónimos, nombre y categoría | solo el par |
| **R. resonancia independiente** | número de sueños distintos en que B aparece en el top-5 de una consulta armada con los campos de A, y viceversa, con `ignorar_sinapsis=True` y en silencio | hereda la del ranking sin sinapsis |
| **K. competencia** | rango del par entre las sinapsis automáticas de A y de B, por S + R | solo los dos nodos |
| **V. vías de nacimiento** | número de vías B1–B12 que lo propusieron | **no es invariante** (exp. 16): solo para desempatar, y se audita |

## 3. El piso mecánico (fijado ahora)

Una sinapsis `a_prueba` se **consolida** si cumple **≥ 2 de 3**:
- (a) S ≥ 1;
- (b) R ≥ 2;
- (c) gana la competencia: está entre las 5 primeras de A o de B.

Las que no consolidan:
- Si llevan **3 sueños** sin consolidar, se **debilitan** (×0,5 sobre el peso de nacimiento).
- Con **6 sueños** sin consolidar, pasan a **cuarentena** (reversible).

**Protecciones:**
- `manual` nunca entra.
- Nunca se deja un nodo con menos de 5 pistas.
- Tope de 10 cuarentenas por sueño.
- Desde una DB vacía no hay evidencia, y nada se poda antes de 6 sueños.

## 4. El MLP (encima del piso)

- **Entradas:** S, R, K, V y el grado de cada nodo (como logaritmo).
- **Arquitectura:** 1 capa oculta de 8 unidades.
- **Salida:** probabilidad de «relacionado».
- **Entrenamiento:**
  - solo con mundos sintéticos (§5);
  - partición por **tema**, con el 20 % sellado que nunca se estudia;
  - techo de épocas por parada temprana sobre una validación aparte del sellado.
- **Decisión:**
  - consolida si p ≥ 0,5;
  - las demás reglas del piso siguen igual (ventanas, protecciones, topes);
  - **nunca consolida menos de lo que consolida el piso con S ≥ 2**: piso de seguridad.

## 5. Mundos de E1 y E2 (sin filtración léxica)

- **Textos:** los del corpus espejo (`mundos_espejo.py`), extendido con el mismo método a 8 temas × 6 facetas,
  en 4 idiomas.
- **Estructura declarada** (generada con semilla fija y probabilidades fijadas ahora):
  - P(compartir ≥ 1 dimensión | mismo tema) = 0,60;
  - P(compartir ≥ 1 dimensión | distinto tema) = 0,20;
  - P(compartir un sustantivo clave | mismo tema) = 0,30;
  - P(compartir un sustantivo clave | distinto tema) = 0,05.
- **Advertencia escrita antes:** aun así, el generador codifica la relación. Solo el examen humano al azar
  (decisión §4.2 B) puede validar el valor real.

## 6. Etapas y criterios

### E1 — la resonancia independiente (laboratorio; el motor se parchea en memoria en una copia en `/tmp`)

| # | Criterio | Umbral |
|---|---|---|
| C1.1 | Invariancia: R de cada par de D, con D frente a D∪I | idéntico en ≥ 98 % de los pares; el resto, explicado |
| C1.2 | **Bucle:** multiplicar por 3 el peso de 20 sinapsis al azar no cambia su R | 20/20 iguales |
| C1.3 | Reproducibilidad (misma semilla) | idéntico |
| C1.4 | Regresión: con `ignorar_sinapsis=False` el resultado de `buscar_por_frase` es idéntico al del motor sin parche | idéntico |
| C1.5 | Informativo, sin umbral: AUC de R y de S, relacionados frente a no relacionados, por idioma | — |

### E2 — ciclo de vida simulado (12 sueños)

| # | Criterio | Umbral |
|---|---|---|
| C2.1 | Precisión de las consolidadas por el **piso** | ≥ 0,50 y ≥ línea base + 0,15 (línea base: precisión de las automáticas al nacer en el mismo mundo) |
| C2.2 | Recall: relacionadas nacidas que no terminan en cuarentena | ≥ 0,90 |
| C2.3 | Aporte único: relacionadas consolidadas fuera del top-5 del canal 1 de las consultas del propio recuerdo | > 0 |
| C2.4 | Invariancia del estado final (D frente a D∪I) | ≥ 98 % idéntico |
| C2.5 | Otro orden de guardado | ≥ 95 % idéntico |
| C2.6 | Cuatro idiomas: \|precisión(idioma) − precisión(es)\| | ≤ 0,05 |
| C2.7 | `manual` | 0 cambios |
| C2.8 | QA y recall (con `ignorar_sinapsis=False`) | idénticos |
| **C2.9** | **Puerta del MLP:** F1 sobre los temas sellados frente al piso, en los 4 idiomas | MLP ≥ piso + 0,05 **en los 4**, cumpliendo además C2.2–C2.7. **Si no, el MLP no entra y se queda el piso** |

### E3 — examen real

Bloqueada hasta la decisión §4.2 de `DECISIONES_CONSENSO.md`.

### E4 — motor: sombra y después relevo

Bloqueada hasta el OK explícito de Dennys (§4.3).
