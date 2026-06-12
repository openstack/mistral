import os
from dotenv import load_dotenv

load_dotenv()

_SECRETS_DIR = '/var/run/secrets/mistral'


def _read_secret(key, default=None):
    path = os.path.join(_SECRETS_DIR, key)
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return default


DEBUG_LOG = os.getenv('DEBUG_LOG', 'false').lower() == 'true'
LOG_LEVEL = 'DEBUG' if DEBUG_LOG else 'INFO'
LOG_LEVEL = LOG_LEVEL.upper()
PG_HOST = os.getenv('PG_HOST', 'postgres')
PG_PORT = os.getenv('PG_PORT', '5434')
PG_USER = _read_secret('pg-user') or os.getenv('PG_USER', 'mistral_nc')
PG_PASSWORD = _read_secret('pg-password') or os.getenv('PG_PASSWORD')
PG_DB_NAME = os.getenv('PG_DB_NAME', 'mistral_nc')
PG_IDLE_TIMEOUT = os.getenv('PG_IDLE_TIMEOUT', '30s')
