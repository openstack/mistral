import asyncpg
from asyncpg import Connection
import logging
import uuid
from datetime import datetime
from app.api.bluegreen.schemas.bluegreen import SyncResponse, ErrorResponse
from fastapi import status


LOG = logging.getLogger(__name__)


async def clone_namespace(source_namespace: str, target_namespace: str,
                          db: Connection):
    try:
        async with db.transaction():
            workflows = await db.fetch(
                "SELECT * FROM workflow_definitions_v2 WHERE namespace = $1",
                source_namespace
            )
            LOG.info(f'{len(workflows)} workflow(s) to clone')
            if not workflows:
                return SyncResponse(
                    status="Done",
                    message="No workflows to clone",
                    operationDetails=[]
                ), status.HTTP_200_OK

            clone_results = []

            for workflow in workflows:
                new_workflow_id = str(uuid.uuid4())
                current_time = datetime.now()
                insert_data = {
                    "created_at": current_time,
                    "updated_at": current_time,
                    "scope": workflow['scope'],
                    "project_id": workflow['project_id'],
                    "id": new_workflow_id,
                    "name": workflow['name'],
                    "definition": workflow['definition'],
                    "spec": workflow['spec'],
                    "tags": workflow['tags'],
                    "is_system": workflow['is_system'],
                    "namespace": target_namespace,
                    "workbook_name": workflow['workbook_name'],
                    "checksum": workflow['checksum']
                }

                try:
                    await db.execute("""
                        INSERT INTO workflow_definitions_v2 (
                            created_at, updated_at, scope, project_id, id,
                            name, definition, spec, tags, is_system, namespace,
                            workbook_name, checksum
                        ) VALUES (
                            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13
                        )
                    """, *insert_data.values())
                    clone_results.append(
                        {"name": workflow['name'], "status": "cloned"})
                except asyncpg.UniqueViolationError:
                    clone_results.append(
                        {"name": workflow['name'], "status": "duplicate"})
                except asyncpg.PostgresError as e:
                    LOG.error(f"Database error: {e}")
                    clone_results.append(
                        {"name": workflow['name'],
                         "status": "error",
                         "details": str(e)})

            if all(result["status"] == "cloned" for result in clone_results):
                LOG.info(f'{len(workflows)} workflow(s) cloned successfully.')
                return SyncResponse(
                    status="Done",
                    message="All workflows cloned successfully.",
                    operationDetails=clone_results
                ), status.HTTP_200_OK
            else:
                failed_count = sum(1 for result in clone_results
                                   if result["status"] != "cloned")
                LOG.info(f'{failed_count} workflow(s) failed to clone.')

                return ErrorResponse(
                    id=str(uuid.uuid4()),
                    reason="Partial success",
                    message="Some workflows failed to clone.",
                    status=status.HTTP_409_CONFLICT,
                    meta={"custom": {"details": clone_results}}
                ), status.HTTP_409_CONFLICT

    except asyncpg.PostgresError as e:
        LOG.error(f"Database error: {e}")
        return ErrorResponse(
            id=str(uuid.uuid4()),
            reason="Database error",
            message=str(e),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            meta={"custom": {"additionalInfo": "PostgresError"}}
        ), status.HTTP_500_INTERNAL_SERVER_ERROR
    except Exception as e:
        LOG.error(f"Unexpected Error: {e}")
        return ErrorResponse(
            id=str(uuid.uuid4()),
            reason="Unexpected error",
            message=str(e),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            meta={"custom": {"additionalInfo": "UnexpectedError"}}
        ), status.HTTP_500_INTERNAL_SERVER_ERROR


async def cleanup_namespace(namespace: str, db: Connection):
    try:
        async with db.transaction():
            count = await db.fetchval(
                "SELECT COUNT(1) FROM workflow_definitions_v2\
                      WHERE namespace = $1",
                namespace)
            LOG.info(f'{count} workflow(s) to clean')

            if count == 0:
                return SyncResponse(
                    message="No workflows to delete",
                    operationDetails=[]
                ), status.HTTP_200_OK

            await db.execute(
                "DELETE FROM workflow_definitions_v2 WHERE namespace = $1",
                namespace)

            return SyncResponse(
                message="All workflows deleted successfully.",
                operationDetails=[]
            ), status.HTTP_200_OK
    except asyncpg.PostgresError as e:
        LOG.error(f"Database error: {e}")
        return ErrorResponse(
            id=str(uuid.uuid4()),
            reason="Database error",
            message=str(e),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            meta={"custom": {"additionalInfo": "PostgresError"}},
            code=None,
            referenceError=None
        ), status.HTTP_500_INTERNAL_SERVER_ERROR
    except Exception as e:
        LOG.error(f"Unexpected Error: {e}")
        return ErrorResponse(
            id=str(uuid.uuid4()),
            reason="Unexpected error",
            message=str(e),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            meta={"custom": {"additionalInfo": "UnexpectedError"}},
            code=None,
            referenceError=None
        ), status.HTTP_500_INTERNAL_SERVER_ERROR
