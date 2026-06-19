# BioRAG Config Module
import os

def _load_env_local():
    """Carga .env.local si existe (override de defaults del código)."""
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env.local')
    if not os.path.exists(env_path):
        return
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                # No sobreescribir si ya está en el entorno
                if key not in os.environ:
                    os.environ[key] = value

_load_env_local()
