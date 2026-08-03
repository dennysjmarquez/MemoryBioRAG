"""
Binding HDC (Hyperdimensional Computing) sobre vectores SDM de 2048 bits.
=========================================================================

Primitivas del pipeline HDC usado por BioRAG para representar predicados
(sujeto, accion, objeto) como vectores binarios y recuperarlos por rol.

Pipeline:
  1. Items:      generar_vector_sdm(concepto=..., contenido=...)   (SDM real)
  2. Densificar: los items SDM son ultra-dispersos (~16 bits de 2048). El bind
                 XOR de un item disperso contra un rol denso degenera (el rol
                 queda casi intacto, sim ≈ 0.99, y el unbind da señal ~0.01).
                 La densificación convierte cada item en un vector denso
                 pseudoaleatorio determinista por majority-vote de un vector
                 i.i.d. por cada bit activo del item.
  3. Roles:      vectores densos pseudoaleatorios deterministas (~50% de 1s).
  4. Bind:       item_densificado XOR rol.
  5. Bundle:     voto de mayoría bit a bit (NO encadenar XOR de N términos —
                 cancelación clásica del HDC).
  6. Unbind:     bundle XOR rol.
  7. Clean-up:   elegir el item conocido más similar (Hamming) al recuperado.

Métrica: similitud de Hamming normalizada (1 - dist/2048), la correcta para
vectores post-XOR (el Jaccard ponderado del SDM está pensado para vectores
dispersos pre-XOR y da ~0.01 en este dominio).

GENERACIÓN DE ITEMS — DOS MODOS:
  A) densificar(generar_vector_sdm(...)): modo original. PROBLEMA detectado
     2026-08-02: cuando concepto==contenido==string corto (patrón real del
     HDC), el string snake_case es UN solo token → el hash md5%512 del
     segmento contenido colapsa a 512 buckets → paradoja de cumpleaños →
     colisiones EXACTAS (dist=0) entre strings distintos (p.ej.
     bug_login_v2 == estilo_escritura_profesional). Barrido real: 65
     colisiones en 33.411 pares con contenido=concepto vs 0 con contenido
     largo de DB. El unbind no puede distinguir pares colisionados
     (ambigüedad irresoluble en clean-up memory).
  B) item_denso_desde_string(...): modo recomendado (Opción 1, decidida con
     Dennys). Genera el item hipervectorial directo por sha256 del string:
     cada bit es i.i.d. con p=0.5. Items distintos → direcciones aleatorias
     ortogonales (sim ≈ 0.5, no 0.60-0.70 como los densificados del SDM), y
     la probabilidad de colisión exacta es 2^-2048 ≈ 0. Mantiene el
     determinismo (misma firma = mismo vector). Verificado en el barrido de
     259 nodos / 33.411 pares → 0 colisiones.
"""

import hashlib
from core.sdm import SDM_BITS, SDM_BYTES, distancia_hamming

_vecs_densos_cache = {}


def _vector_denso(seed: int) -> bytes:
    """Vector denso i.i.d. pseudoaleatorio determinista (~50% de 1s)."""
    if seed not in _vecs_densos_cache:
        out = bytearray(SDM_BYTES)
        for i in range(SDM_BITS):
            h = int(hashlib.sha256(f"dd:{seed}:{i}".encode()).hexdigest(), 16)
            if h % 2 == 0:
                out[i // 8] |= (1 << (7 - (i % 8)))
        _vecs_densos_cache[seed] = bytes(out)
    return _vecs_densos_cache[seed]


def generar_rol(nombre: str, seed: int) -> bytes:
    """Vector de rol denso pseudoaleatorio determinista (~50% de 1s)."""
    out = bytearray(SDM_BYTES)
    for i in range(SDM_BITS):
        h = int(hashlib.sha256(f"{nombre}:{seed}:{i}".encode()).hexdigest(), 16)
        if h % 2 == 0:
            out[i // 8] |= (1 << (7 - (i % 8)))
    return bytes(out)


def item_denso_desde_string(texto: str, base_seed: int = 300000) -> bytes:
    """Item hipervectorial denso directo desde un string (Opción 1).

    Cada bit se deriva de sha256(f"item:{texto}:{base_seed}:{i}") → i.i.d. con
    p=0.5. Dos strings distintos producen direcciones ortogonales (sim ≈ 0.5)
    y la probabilidad de colisión exacta es 2^-2048 ≈ 0, eliminando la
    colisión del SDM (md5%512) cuando concepto==contenido==string corto.

    No pasa por generar_vector_sdm ni por densificar: es el estándar clásico
    del HDC (Kanerva): el item ES un vector denso pseudoaleatorio
    determinista. Los roles ya se generan así; esta función hace lo propio
    para items sin tocar core/sdm.py.
    """
    out = bytearray(SDM_BYTES)
    for i in range(SDM_BITS):
        h = int(hashlib.sha256(f"item:{texto}:{base_seed}:{i}".encode()).hexdigest(), 16)
        if h % 2 == 0:
            out[i // 8] |= (1 << (7 - (i % 8)))
    return bytes(out)


def densificar(v: bytes, base_seed: int = 100000) -> bytes:
    """Densificación determinista: majority-vote de vectores i.i.d. por bit
    activo del item disperso. Un bit activo en posicion i contribuye con
    _vector_denso(base_seed + i); el resultado es el majority-vote."""
    activos = [i for i in range(SDM_BITS) if v[i // 8] & (1 << (7 - (i % 8)))]
    if not activos:
        return bytes(SDM_BYTES)
    counts = [0] * SDM_BITS
    for i in activos:
        vd = _vector_denso(base_seed + i)
        for j in range(SDM_BITS):
            if vd[j // 8] & (1 << (7 - (j % 8))):
                counts[j] += 1
    umbral = len(activos) // 2
    out = bytearray(SDM_BYTES)
    for j in range(SDM_BITS):
        if counts[j] > umbral:
            out[j // 8] |= (1 << (7 - (j % 8)))
    return bytes(out)


def xor(a: bytes, b: bytes) -> bytes:
    """XOR bit a bit (bind / unbind)."""
    return bytes(x ^ y for x, y in zip(a, b))


def majority_vote(vs: list) -> bytes:
    """Bundle por voto de mayoría bit a bit sobre N vectores."""
    counts = [0] * SDM_BITS
    for v in vs:
        for i in range(SDM_BITS):
            if v[i // 8] & (1 << (7 - (i % 8))):
                counts[i] += 1
    out = bytearray(SDM_BYTES)
    for i in range(SDM_BITS):
        if counts[i] > len(vs) // 2:
            out[i // 8] |= (1 << (7 - (i % 8)))
    return bytes(out)


def sim_ham(a: bytes, b: bytes) -> float:
    """Similitud de Hamming normalizada: 1 - dist_hamming/2048."""
    return 1.0 - distancia_hamming(a, b) / SDM_BITS


def bind(item: bytes, rol: bytes) -> bytes:
    return xor(item, rol)


def unbind(bound: bytes, rol: bytes) -> bytes:
    return xor(bound, rol)


def recuperar_rol(bundle: bytes, rol: bytes, candidatos: dict) -> tuple:
    """Clean-up memory: devuelve (top1, similitud_top1) comparando el unbind
    del bundle con cada item densificado conocido."""
    rec = unbind(bundle, rol)
    sims = {nombre: sim_ham(rec, vec) for nombre, vec in candidatos.items()}
    top1 = max(sims, key=sims.get)
    return top1, sims[top1]
