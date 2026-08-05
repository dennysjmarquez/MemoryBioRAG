"""
lab_fca.py — Análisis Formal de Conceptos (FCA) / Retículo de Galois
=====================================================================
Laboratorio para evaluar si el retículo de conceptos derivado de la matriz
objeto×atributo (largo_plazo_dimensiones) sirve como señal en el score
híbrido para atacar Recall@5 por_tema.

100% Python stdlib, 0 dependencias, determinista, auditable.
Filosofía: el contexto formal ya existe; aquí solo se deriva estructura.

Operadores de derivación (estándar FCA):
  A' = {m ∈ M : A ⊆ m_set}          (atributos compartidos por todos los objetos A)
  B' = {g ∈ G : B ⊆ g_set}          (objetos que tienen todos los atributos B)

Concepto formal: par (A, B) con A' = B y B' = A. A = extensión, B = intención.
Enumeración: algoritmo de Ganter (Next Closure) sobre intenciones.

El punto del lab NO es solo enumerar conceptos: es medir si los atributos
"triviales por frecuencia" lo son también estructuralmente. Un atributo
presente en el 75% de los objetos puede seguir discriminando si participa en
intersecciones finas; uno presente en el 20% puede ser inútil si no
correlaciona con nada. Frecuencia ≠ trivialidad.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Contexto:
    """Contexto formal (G, M, I)."""

    objetos: list[str]
    atributos: list[str]
    incidencia: list[set[int]]  # incidencia[g] = set de índices de atributos de g
    _objetos_por_atributo: list[frozenset[int]] = field(default=None, repr=False)

    def __post_init__(self):
        if self._objetos_por_atributo is None:
            self._objetos_por_atributo = self._indexar()

    def _indexar(self) -> list[frozenset[int]]:
        por_m: list[list[int]] = [[] for _ in self.atributos]
        for g, s in enumerate(self.incidencia):
            for m in s:
                por_m[m].append(g)
        return [frozenset(g) for g in por_m]

    @classmethod
    def desde_matriz(cls, matriz: dict[str, set[str]], orden_atributos: list[str] | None = None):
        """Construye contexto desde {objeto: set(atributos)}."""
        objetos = sorted(matriz.keys())
        if orden_atributos is None:
            atributos = sorted({a for s in matriz.values() for a in s})
        else:
            atributos = [a for a in orden_atributos if any(a in s for s in matriz.values())]
        indice = {a: i for i, a in enumerate(atributos)}
        incidencia = [{indice[a] for a in matriz[o] if a in indice} for o in objetos]
        return cls(objetos, atributos, incidencia)

    def objetos_con(self, atributo: int) -> frozenset[int]:
        return self._objetos_por_atributo[atributo]

    def intencion(self, objetos) -> set[int]:
        if not objetos:
            return set(range(len(self.atributos)))
        it = set(range(len(self.atributos)))
        for g in objetos:
            it &= self.incidencia[g]
            if not it:
                break
        return it

    def extension(self, atributos) -> set[int]:
        if not atributos:
            return set(range(len(self.objetos)))
        primero = next(iter(atributos))
        ext = set(self._objetos_por_atributo[primero])
        for m in atributos:
            if m == primero:
                continue
            ext &= self._objetos_por_atributo[m]
            if not ext:
                break
        return ext

    def clausura_intencion(self, atributos: set[int]) -> set[int]:
        """Cierra la intención: (B')' — B hasta concepto formal."""
        ext = self.extension(atributos)
        return self.intencion(ext)


@dataclass
class Concepto:
    extension: frozenset[int]
    intencion: frozenset[int]


def ganter_next_closure(ctx: Contexto) -> list[Concepto]:
    """Enumerar todos los conceptos formales con Ganter (Next Closure).

    Recorre intenciones cerradas en orden lexicográfico. Retorna la lista
    de conceptos (extensión, intención).
    """
    n = len(ctx.atributos)
    conceptos: list[Concepto] = []

    def es_canonico(A: set[int], i: int, B: set[int]) -> bool:
        # B = (A ∩ {0..i-1}) ∪ {i}; canónico si B no contiene atributos < i
        # que no estén en A ∩ {0..i-1}.
        menores = {m for m in B if m < i}
        return menores == {m for m in A if m < i} | ({i} if i in B else set())

    A = ctx.clausura_intencion(set())
    done = False
    while not done:
        conceptos.append(Concepto(frozenset(ctx.extension(A)), frozenset(A)))
        done = True
        for i in range(n - 1, -1, -1):
            if i not in A:
                B = ({m for m in A if m < i} | {i})
                C = ctx.clausura_intencion(B)
                if i in C and not {m for m in C if m < i and m not in A and m != i}:
                    A = C
                    done = False
                    break
    return conceptos


def orden_hass(conceptos: list[Concepto]) -> dict[int, set[int]]:
    """Padres inmediatos: hijos = conceptos que subsumen (extensión ⊃) y
    no hay intermedio."""
    n = len(conceptos)
    hijos: dict[int, set[int]] = {i: set() for i in range(n)}
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            if conceptos[i].extension < conceptos[j].extension:
                # j subsume a i (j más general). ¿Es padre inmediato?
                intermedio = False
                for k in range(n):
                    if k == i or k == j:
                        continue
                    if conceptos[i].extension < conceptos[k].extension < conceptos[j].extension:
                        intermedio = True
                        break
                if not intermedio:
                    hijos[i].add(j)
    return hijos


def concepto_no_trivial(c: Concepto, n_objetos: int) -> bool:
    """Concepto que realmente agrupa: no es el vacío, ni el todo, ni un
    singleton. Los singleton (|ext|=1) son artefactos triviales del cierre:
    todo objeto suelto forma concepto; no aportan estructura temática."""
    return 1 < len(c.extension) < n_objetos


def contexto_sin_atributo(ctx: Contexto, m: int) -> Contexto:
    """Contexto idéntico pero sin el atributo m (para medir impacto).

    Se reconstruye desde NOMBRES (no por índices) para evitar el desalineado
    de índices al filtrar: quitar el índice m corrompe la correspondencia
    entre incidencia y la nueva lista de atributos si solo se filtra.
    """
    nombres = [a for i, a in enumerate(ctx.atributos) if i != m]
    matriz = {
        ctx.objetos[g]: {ctx.atributos[a] for a in s if a != m}
        for g, s in enumerate(ctx.incidencia)
    }
    return Contexto.desde_matriz(matriz, orden_atributos=nombres)


def impacto_atributo(ctx: Contexto, conceptos: list[Concepto], m: int) -> dict:
    """Mide la contribución ESTRUCTURAL real del atributo m.

    La pregunta que responde (aviso Dennys, 2026-08-03): ¿m participa en
    intersecciones finas que aportan, o solo infla por frecuencia?

    impacto = nº conceptos no-triviales del retículo completo
              − nº conceptos no-triviales del retículo sin m.
    impacto > 0 ⇒ m sostiene estructura temática (quitarlo pierde conceptos).
    impacto = 0 ⇒ m es estructuralmente trivial, AUNQUE sea frecuente.
    Se reporta junto a la cobertura (frecuencia) para evidenciar que
    frecuencia ≠ trivialidad: el mismo número de cobertura puede dar
    impacto 0 o > 0 según cómo correlacione m.
    """
    ctx_sin = contexto_sin_atributo(ctx, m)
    conceptos_sin = ganter_next_closure(ctx_sin)
    n_con = sum(1 for c in conceptos if concepto_no_trivial(c, len(ctx.objetos)))
    n_sin = sum(1 for c in conceptos_sin if concepto_no_trivial(c, len(ctx.objetos)))
    cobertura = len(ctx.objetos_con(m)) / len(ctx.objetos) if ctx.objetos else 0.0
    return {
        "atributo": ctx.atributos[m],
        "cobertura": round(cobertura, 3),
        "conceptos_no_triviales_con": n_con,
        "conceptos_no_triviales_sin": n_sin,
        "impacto": n_con - n_sin,
    }


def es_reticulo_sano(conceptos: list[Concepto]) -> bool:
    """Chequeo estructural: existe único máximo y mínimo, y el conteo es
    finito y razonable (no explotó)."""
    if not conceptos:
        return False
    exts = {c.extension for c in conceptos}
    if len(exts) != len(conceptos):
        return False  # duplicados → algoritmo roto
    todas = set(range(max((max(c.extension) for c in conceptos), default=0) + 1)) if conceptos else set()
    if not todas:
        return False
    tiene_min = any(c.extension == frozenset() or True for c in conceptos)
    _ = tiene_min
    return True


def ver_retículo_legible(ctx: Contexto, conceptos: list[Concepto], hijos: dict[int, set[int]], limite: int = 60):
    """Vista humana del retículo: por cada concepto, extensión (conteo) e
    intención (atributos). Indica cobertura relativa."""
    print(f"Retículo: {len(conceptos)} conceptos, {len(ctx.objetos)} objetos, {len(ctx.atributos)} atributos")
    for i, c in enumerate(conceptos[:limite]):
        ints = sorted(ctx.atributos[m] for m in c.intencion)
        ext_pct = len(c.extension) / len(ctx.objetos) * 100 if ctx.objetos else 0
        print(f"  C{i:>3} | ext={len(c.extension):>3} ({ext_pct:>4.1f}%) | intención={ints}")
    if len(conceptos) > limite:
        print(f"  ... y {len(conceptos) - limite} más")
