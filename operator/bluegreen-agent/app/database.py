import asyncpg
from app.config import PG_HOST, PG_PORT, PG_USER, PG_PASSWORD, PG_DB_NAME
from fastapi import Request
from app.logger import get_logger


LOG = get_logger(__name__)


async def create_db_pool():
    LOG.info('Configuring DB connection')
    return await asyncpg.create_pool(
        host=PG_HOST,
        port=PG_PORT,
        user=PG_USER,
        password=PG_PASSWORD,
        database=PG_DB_NAME
    )


async def get_db_connection(request: Request):
    async with request.app.state.db_pool.acquire() as connection:
        yield connection
