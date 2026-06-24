# BioRAG Config Module
import os

_ESCAPE_SEQUENCES = {
    '\\n': '\n',
    '\\t': '\t',
    '\\r': '\r',
    '\\\\': '\\',
    '\\"': '"',
    "\\'": "'",
}


def _unescape(value: str) -> str:
    """Interpreta secuencias de escape básicas sin dependencias externas."""
    result = []
    i = 0
    while i < len(value):
        if value[i] == '\\' and i + 1 < len(value):
            seq = value[i:i + 2]
            if seq in _ESCAPE_SEQUENCES:
                result.append(_ESCAPE_SEQUENCES[seq])
                i += 2
                continue
        result.append(value[i])
        i += 1
    return ''.join(result)


def _load_env_local():
    """Carga .env.local si existe (override de defaults del código).

    Soporta valores simples y valores entre comillas dobles o simples
    que ocupen varias líneas. Interpreta escapes como \\n y \\t.
    """
    env_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env.local'
    )
    if not os.path.exists(env_path):
        return

    with open(env_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        raw_line = lines[i]
        stripped = raw_line.strip()

        if not stripped or stripped.startswith('#'):
            i += 1
            continue

        if '=' not in stripped:
            i += 1
            continue

        key, value = stripped.split('=', 1)
        key = key.strip()
        value = value.strip()

        quote = None
        if value.startswith('"'):
            quote = '"'
        elif value.startswith("'"):
            quote = "'"

        if quote is not None:
            buffer = value[1:]
            closed = buffer.endswith(quote)
            while not closed and i + 1 < len(lines):
                i += 1
                buffer += '\n' + lines[i].rstrip('\n')
                closed = buffer.rstrip().endswith(quote)

            if closed:
                # Quitar la comilla de cierre (y espacios previos si los hubiera)
                value = buffer.rstrip()[:-1]
            else:
                value = buffer

            value = _unescape(value)

        if key not in os.environ:
            os.environ[key] = value

        i += 1


_load_env_local()
