from fastapi import FastAPI
from app.api.bluegreen.routes import api_router as bg_router
from app.database import create_db_pool
from app.logger import get_logger
from fastapi import Depends
from app.database import get_db_connection
import os

logger = get_logger(__name__)
app = FastAPI()


@app.on_event("startup")
async def startup():
    app.state.db_pool = await create_db_pool()


@app.on_event("shutdown")
async def shutdown():
    await app.state.db_pool.close()

app.include_router(bg_router, prefix='/api/bluegreen')

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting the Mistral bluegreen application")
    tls_enabled = os.getenv('TLS_ENABLED', 'False').lower() in ['true', '1', 't', 'yes']

    if tls_enabled:
        cert_dir = '/tls/'
        tls_key_path = cert_dir + 'tls.key'
        tls_cert_path = cert_dir + 'tls.crt'
        tls_ca_path = cert_dir + 'ca.crt'
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8000,
            ssl_certfile=tls_cert_path,
            ssl_keyfile=tls_key_path,
            ssl_ca_certs=tls_ca_path
        )
    else:
        uvicorn.run(app, host="0.0.0.0", port=8000)


@app.get("/")
async def read_root(db=Depends(get_db_connection)):
    try:
        async with db.transaction():
            result = await db.fetchval("SELECT 1")
        db_status = "Connected" if result == 1 else "Disconnected"
    except Exception as e:
        db_status = f"Error: {e}"

    return {
        "service": "Bluegreen Deployment Agent",
        "version": "1.0.0",
        "status": "Running",
        "database_status": db_status
    }
