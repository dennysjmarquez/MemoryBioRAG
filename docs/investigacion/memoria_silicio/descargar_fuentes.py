"""Descarga explícita opcional. No ejecutada en Arena: red editorial limitada.

Solo URLs HTTPS del catálogo fijo; PDFs fuera del checkout, límite 32 MiB/fuente,
manifest real con SHA256. Nunca sobreescribe archivos ya existentes.
Revisar permisos/licencias antes de redistribuir. No importa código de los papers.
"""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
from urllib.parse import urlparse
from urllib.request import Request, urlopen

MAX_BYTES = 32 * 1024 * 1024
HOSTS = {'arxiv.org', 'www.nature.com'}


def check_url(url):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname not in HOSTS or parsed.username or parsed.password:
        raise ValueError('URL editorial no permitida')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    folder = args.output.expanduser().resolve()
    repo = Path(__file__).resolve().parents[3]
    if folder.is_relative_to(repo):
        parser.error('Los PDFs deben quedar fuera del checkout Git')
    folder.mkdir(parents=True, exist_ok=True)
    manifest = folder/'download_manifest.json'
    if manifest.exists():
        parser.error('El directorio ya tiene manifest; usar otro para preservar evidencia')
    records = []
    sources = json.loads(Path(__file__).with_name('fuentes.json').read_text())['sources']
    for source in sources:
        url = source['pdf']
        record = dict(key=source['key'], requested_url=url, status='error')
        temp_name = None
        try:
            check_url(url)
            target = folder/(source['key']+'.pdf')
            if target.exists():
                raise ValueError('Archivo existente: no sobreescribir')
            request = Request(url, headers={'User-Agent': 'BioRAG-Research-Archive/0.1'})
            with urlopen(request, timeout=60) as response:
                check_url(response.geturl())
                digest, size, prefix = hashlib.sha256(), 0, b''
                with tempfile.NamedTemporaryFile(dir=folder, delete=False) as stream:
                    temp_name = stream.name
                    while True:
                        chunk = response.read(65536)
                        if not chunk:
                            break
                        if not prefix:
                            prefix = chunk[:5]
                        size += len(chunk)
                        if size > MAX_BYTES:
                            raise ValueError('Excede límite 32 MiB')
                        digest.update(chunk)
                        stream.write(chunk)
                if prefix != b'%PDF-':
                    raise ValueError('Respuesta no es PDF; no archivar página de error')
            # x evita sobreescritura incluso si otro proceso creó target.
            with target.open('xb') as out, open(temp_name, 'rb') as content:
                import shutil
                shutil.copyfileobj(content, out)
            record.update(status='downloaded', filename=target.name, bytes=size, sha256=digest.hexdigest())
        except Exception as exc:
            record['error'] = str(exc)
        finally:
            if temp_name:
                Path(temp_name).unlink(missing_ok=True)
        records.append(record)
        print(source['key'], record['status'])
    manifest.write_text(json.dumps(dict(sources=records), ensure_ascii=False, indent=2)+'\n')
    return 0 if all(r['status'] == 'downloaded' for r in records) else 1


if __name__ == '__main__':
    raise SystemExit(main())
