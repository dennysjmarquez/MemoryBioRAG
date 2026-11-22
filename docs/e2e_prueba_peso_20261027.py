from core.memory.scoring import _calcular_score_hibrido
cases = {
    'sin_lexico': {'bm25_norm': 0, 'concepto_ratio': 0},
    'con_bm25': {'bm25_norm': 0.5},
    'con_concepto': {'concepto_ratio': 0.5},
    'con_varias_senales': {'bm25_norm': 0.4, 'concepto_ratio': 0.2, 'dim_score': 0.3, 'sinonimos_ratio': 0.2},
}
for name, kw in cases.items():
    sin = _calcular_score_hibrido(None, tematico_score=0.0, **kw)
    con = _calcular_score_hibrido(None, tematico_score=1.0, **kw)
    print(f'{name}: tematico_0={sin:.4f} tematico_1={con:.4f} delta={con-sin:+.4f}')
