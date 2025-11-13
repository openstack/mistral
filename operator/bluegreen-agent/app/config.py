import os
from dotenv import load_dotenv

load_dotenv()

DEBUG_LOG = os.getenv('DEBUG_LOG', 'false').lower() == 'true'
LOG_LEVEL = 'DEBUG' if DEBUG_LOG else 'INFO'
LOG_LEVEL = LOG_LEVEL.upper()
PG_HOST = os.getenv('PG_HOST', 'postgres')
PG_PORT = os.getenv('PG_PORT', '5434')
PG_USER = os.getenv('PG_USER', 'mistral_nc')
PG_PASSWORD = os.getenv('PG_PASSWORD')
PG_DB_NAME = os.getenv('PG_DB_NAME', 'mistral_nc')
PG_IDLE_TIMEOUT = os.getenv('PG_IDLE_TIMEOUT', '30s')
