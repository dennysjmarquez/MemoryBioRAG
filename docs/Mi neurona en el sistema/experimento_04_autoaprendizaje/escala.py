"""Escala en la que vive la neurona: g(score) y su inversa.

Para score < 1-ε es el logit de siempre. Por encima (match exacto, +2.94) sigue
en línea recta con la pendiente del logit en 1-ε (~10⁴): los matches exactos
conservan su orden entre sí y quedan tan arriba que la corrección (|c| ~ 1)
no puede desordenarlos. Es monótona y tiene inversa exacta, así que el motor
recibe un score en la misma escala que hoy.
"""
import math

EPS = 1e-4
_L1 = math.log((1 - EPS) / EPS)
_PEND = 1.0 / (EPS * (1 - EPS))


def g(s):
    s = max(EPS, s)
    if s < 1 - EPS:
        return math.log(s / (1 - s))
    return _L1 + (s - (1 - EPS)) * _PEND


def g_inv(z):
    if z < _L1:
        return 1.0 / (1.0 + math.exp(-z))
    return (1 - EPS) + (z - _L1) / _PEND
