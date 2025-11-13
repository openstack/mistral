import logging
from fastapi import status, APIRouter, Depends
from fastapi.responses import JSONResponse, Response
import app.api.bluegreen.schemas.bluegreen as sch
import app.services.bluegreen_service as bs
from app.database import get_db_connection


LOG = logging.getLogger(__name__)

router = APIRouter()


# initDomain
@router.post("/init-domain",
             status_code=status.HTTP_200_OK)
async def init_domain(api_version: str, request: sch.BluegreenRequest):
    LOG.info("initDomain: done")

    return Response(status_code=status.HTTP_200_OK)


# warmup
@router.post("/warmup",
             status_code=status.HTTP_200_OK)
async def warmup(api_version: str, request: sch.BluegreenRequest,
                 db=Depends(get_db_connection)):

    result, response_status = await bs.clone_namespace(
        source_namespace=request.BGState.originNamespace.name,
        target_namespace=request.BGState.peerNamespace.name,
        db=db)

    if response_status == 200:
        return result
    else:
        return JSONResponse(
            content=result.model_dump(),
            status_code=response_status
        )


# commit
@router.post("/commit",
             status_code=status.HTTP_200_OK)
async def commit(api_version: str, request: sch.BluegreenRequest,
                 db=Depends(get_db_connection)):

    result, response_status = await bs.cleanup_namespace(
        namespace=request.BGState.originNamespace.name,
        db=db)

    if response_status == 200:
        return result
    else:
        return JSONResponse(
            content=result.model_dump(),
            status_code=response_status
        )


# promote
@router.post("/promote",
             status_code=status.HTTP_200_OK)
async def promote(api_version: str, request: sch.BluegreenRequest):
    LOG.info("promote: done")

    return Response(status_code=status.HTTP_200_OK)


# rollback
@router.post("/rollback",
             status_code=status.HTTP_200_OK)
async def rollback(api_version: str, request: sch.BluegreenRequest):
    LOG.info("rollback: done")

    return Response(status_code=status.HTTP_200_OK)
