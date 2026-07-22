"""
PostgreSQL connection parameters.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PgConnectionInfo:
    host: str
    port: str
    db_name: str
    user: str
    password: str

    @classmethod
    def from_dbaas_dict(cls, conn_props: dict) -> "PgConnectionInfo":
        return cls(
            host=conn_props["host"],
            port=str(conn_props["port"]),
            db_name=conn_props["name"],
            user=conn_props["username"],
            password=conn_props["password"],
        )
