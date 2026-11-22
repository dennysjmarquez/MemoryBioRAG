"""Lanzador reproducible de QA emparejada. Usar venv con requirements.
Requiere copia de código completa bajo /tmp; rechaza recursos ausentes.
No modifica el código, el snapshot ni los gates de QA.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--code',type=Path,required=True)
    parser.add_argument('--corpus',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    code, corpus, output=(p.resolve() for p in (args.code,args.corpus,args.output))
    if not code.is_relative_to(Path('/tmp')) or not output.is_relative_to(Path('/tmp')):
        parser.error('Código y resultados deben estar bajo /tmp')
    if (code/'.env.local').exists() or (code/'.env').exists():
        parser.error('No cargar configuración privada')
    required=['scripts/evaluar_qa.py','scripts/qa_neurona.py','scripts/casos_qa_baseline_v1.jsonl',
              'scripts/qa_metrics_baseline.json','snapshots/qa_escape_qcr_20260811.db','db/hebbian_clusters.json']
    for name in required:
        if not (code/name).is_file():
            parser.error('Falta recurso requerido: '+name)
    if not corpus.is_dir():
        parser.error('Falta corpus NLTK')
    output.mkdir(parents=True,exist_ok=False)
    files=[code/name for name in required]
    for name in ('core','config','middleware'):
        files.extend((code/name).rglob('*.py'))
    manifest={str(p.relative_to(code)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    (output/'input_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    env=dict(os.environ,HOME=str(output/'home'),PYTHONHASHSEED='1',OPENBLAS_NUM_THREADS='1',
             OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',BIORAG_NLTK_AUTO_DOWNLOAD='0',
             BIORAG_NLTK_DATA=str(corpus),BIORAG_UPDATE_CHECK='0',BIORAG_DMN_SINTESIS_ACTIVA='0',
             BIORAG_PATH=str(code/required[4]),CONTEXT_QA_CODE=str(code),
             BIORAG_QA_DB_VIVA=str(output/'NO_LIVE_DATABASE.db'))
    Path(env['HOME']).mkdir()
    worker=Path(__file__).with_name('qa_selector_worker.py').resolve()
    for mode in ('baseline','selector'):
        variant=dict(env,CONTEXT_QA_MODE=mode,CONTEXT_QA_TRACE=str(output/(mode+'-trace.jsonl')),
                     BIORAG_QA_METRICS=str(output/(mode+'-metrics.json')),
                     BIORAG_QA_FAILED_CASES=str(output/(mode+'-failed.jsonl')),
                     BIORAG_QA_TEMP_DB=str(output/(mode+'-work.db')))
        with (output/(mode+'.log')).open('w') as log:
            result=subprocess.run([sys.executable,str(worker)],cwd=code,env=variant,stdout=log,stderr=subprocess.STDOUT)
        (output/(mode+'-exit.txt')).write_text(str(result.returncode)+'\n')
        print(mode,'exit',result.returncode,flush=True)
    return 0


if __name__=='__main__':
    raise SystemExit(main())
