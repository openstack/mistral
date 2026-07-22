"""
DBaaS REST API client for database lifecycle management.
"""

import logging
import requests

from pg_connection import PgConnectionInfo

logger = logging.getLogger(__name__)

_MICROSERVICE_NAME = "mistral-operator"
_DB_TYPE = "postgresql"


class DBaaSHelper:
    def __init__(self, aggregator_url, dbaas_user, dbaas_password, namespace):
        self._base = aggregator_url.rstrip("/")
        self._auth = (dbaas_user, dbaas_password)
        self._namespace = namespace

    def _classifier(self):
        return {
            "microserviceName": _MICROSERVICE_NAME,
            "scope": "service",
            "namespace": self._namespace,
        }

    def get_by_classifier(self):
        url = (
            f"{self._base}/api/v3/dbaas/{self._namespace}"
            "/databases/get-by-classifier/postgresql"
        )
        body = {
            "classifier": self._classifier(),
            "originService": _MICROSERVICE_NAME,
        }
        resp = requests.post(url, json=body, auth=self._auth)
        if resp.status_code == 404:
            return None
        if resp.status_code == 200:
            return resp.json()
        logger.error(
            "DBaaS get_by_classifier failed: %s %s", resp.status_code, resp.text
        )
        resp.raise_for_status()

    def create_db(self):
        url = f"{self._base}/api/v3/dbaas/{self._namespace}/databases"
        body = {
            "classifier": self._classifier(),
            "type": _DB_TYPE,
            "originService": _MICROSERVICE_NAME,
        }
        resp = requests.put(url, json=body, auth=self._auth)
        if resp.status_code in (200, 201):
            logger.info("DBaaS: database created/retrieved successfully")
            return resp.json()
        logger.error("DBaaS create_db failed: %s %s", resp.status_code, resp.text)
        resp.raise_for_status()

    def register_external_db(self, pg:PgConnectionInfo):
        url = (
            f"{self._base}/api/v3/dbaas/{self._namespace}"
            "/databases/registration/externally_manageable"
        )
        connection_url = f"jdbc:postgresql://{pg.host}:{pg.port}/{pg.db_name}"
        body = {
            "classifier": self._classifier(),
            "connectionProperties": [
                {
                    "host": pg.host,
                    "port": pg.port,
                    "url": connection_url,
                    "role": "admin",
                    "name": pg.db_name,
                    "username": pg.user,
                    "password": pg.password,
                }
            ],
            "dbName": pg.db_name,
            "type": _DB_TYPE,
            "updateConnectionProperties": False,
        }
        resp = requests.put(url, json=body, auth=self._auth)
        if resp.status_code in (200, 201):
            logger.info("DBaaS: external database registered successfully")
            return resp.json()
        logger.error(
            "DBaaS register_external_db failed: %s %s", resp.status_code, resp.text
        )
        resp.raise_for_status()

    def migrate_external_to_internal(
        self, pg:PgConnectionInfo
    ):
        url = f"{self._base}/api/v3/dbaas/migration/databases"
        connection_url = f"jdbc:postgresql://{pg.host}:{pg.port}/{pg.db_name}"
        body = [
            {
                "backupDisabled": False,
                "classifier": self._classifier(),
                "connectionProperties": [
                    {
                        "host": pg.host,
                        "port": pg.port,
                        "url": connection_url,
                        "role": "admin",
                        "name": pg.db_name,
                        "username": pg.user,
                        "password": pg.password,
                    }
                ],
                "name": pg.db_name,
                "namespace": self._namespace,
                "dbHost": pg.host,
                "resources": [
                    {
                        "kind": "user",
                        "name": pg.user,
                    }
                ],
                "type": _DB_TYPE,
            }
        ]
        resp = requests.put(url, json=body, auth=self._auth)
        if resp.status_code == 200:
            logger.info("DBaaS: database migrated from external to internal")
        else:
            logger.error(
                "DBaaS migrate_external_to_internal failed: %s %s",
                resp.status_code,
                resp.text,
            )
            resp.raise_for_status()
