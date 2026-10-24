"""Qué margen elegiría la regla "primero no dañar" (N._calibrar) para el campeón guardado.
Uso: python calibrar_margen.py ruta.db   (solo lectura)"""
import os
import sys
from _cargar_estado import cargar

N, est, campeon = cargar(sys.argv[1])
todos, n = est.estudio + est.guardia, len(est.estudio)
r = N._rangos(None, todos, 5)
a = r == 1
m, rc = N._calibrar(campeon, todos, n, r, N._por_cat(r, todos), int(a[n:].sum()), int(a.sum()) + 1, 5)
print(os.path.basename(sys.argv[1]), "margen", m, "guardia", int(a[n:].sum()), "->",
      int((rc == 1)[n:].sum()) if m is not None else None,
      "total", int(a.sum()), "->", int((rc == 1).sum()) if m is not None else None)
