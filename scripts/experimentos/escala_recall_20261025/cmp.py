import json,sys
labs=sys.argv[1:]; M=[json.load(open(f'/tmp/v/met_{l}.json')) for l in labs]
print(f"{'categoría':20s}"+''.join(f"| {l:>14s} " for l in labs))
for k in M[0]['categorias']:
    print(f"{k:20s}"+''.join(f"| {m['categorias'][k]['recall_at_1']:6} {m['categorias'][k]['recall_at_5']:6} " for m in M))
print(f"{'GLOBAL R@1 R@5':20s}"+''.join(f"| {m['global']['recall_at_1']:6} {m['global']['recall_at_5']:6} " for m in M))
print(f"{'MRR / FP':20s}"+''.join(f"| {m['global'].get('mrr',0):6.3f} {str(m['global']['negativos_fp'])+'/40':>6s} " for m in M))
