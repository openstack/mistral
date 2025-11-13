from fastapi import APIRouter
from app.api.bluegreen.endpoints import bluegreen


api_router = APIRouter()
api_router.include_router(
    bluegreen.router, prefix="/{api_version}/operation", tags=["bluegreen"])
