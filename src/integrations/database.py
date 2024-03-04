# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""The Database integration."""
import typing

import ops
from charms.data_platform_libs.v0.data_interfaces import DatabaseRequires

DATABASE_NAME = "synapse"
RELATION_NAME = "database"


class DatabaseConfig(typing.TypedDict):
    """A named tuple representing a Datasource PostgreSQL.

    Attributes:
        user: User.
        password: Password.
        host: Host (IP or DNS without port or protocol).
        port: Port.
        db: Database name.
    """

    user: str
    password: str
    host: str
    port: str
    db: str


def get_configuration(
    model: ops.Model, database: DatabaseRequires
) -> typing.Optional[DatabaseConfig]:
    """Get database data from relation.

    Args:
        model: Juju model.
        database: database relation object.

    Returns:
        DatabaseConfig: Database configuration or None if no integration.
    """
    if model.get_relation(RELATION_NAME) is None:
        return None

    relation_id = database.relations[0].id
    relation_data = database.fetch_relation_data()[relation_id]

    endpoint = relation_data.get("endpoints", ":")

    return DatabaseConfig(
        user=relation_data.get("username", ""),
        password=relation_data.get("password", ""),
        host=endpoint.split(":")[0],
        port=endpoint.split(":")[1],
        db=DATABASE_NAME,
    )
