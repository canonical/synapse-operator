# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""The Database handler."""
import logging
import typing

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import connection

from charm_types import DatasourcePostgreSQL
from exceptions import CharmDatabaseRelationNotFoundError

logger = logging.getLogger(__name__)


def get_conn(
    datasource: typing.Optional[DatasourcePostgreSQL], database_name: str = ""
) -> connection:
    """Get connection.

    Args:
        datasource: datasource to use to connect.
        database_name: database to connect to.

    Raises:
       Error: something went wrong while connecting to the database.
       CharmDatabaseRelationNotFoundError: if there is no relation.

    Returns:
        Connection with the database
    """
    if datasource is None:
        raise CharmDatabaseRelationNotFoundError("No database relation was found.")
    try:
        user = datasource["user"]
        password = datasource["password"]
        host = datasource["host"]
        if not database_name:
            database_name = datasource["db"]
        conn = psycopg2.connect(
            f"dbname='{database_name}' user='{user}' host='{host}'"
            f" password='{password}' connect_timeout=1"
        )
        conn.autocommit = True
        return conn
    except psycopg2.Error as exc:
        logger.exception("Failed to connect to database: %s", str(exc))
        raise


def prepare(datasource: typing.Optional[DatasourcePostgreSQL], database_name: str) -> None:
    """Change database collate and ctype as required by Synapse.

    Args:
        datasource: datasource to use to connect.
        database_name: database to connect to.

    Raises:
        Error: something went wrong while preparing the database.
    """
    conn = get_conn(datasource=datasource)
    try:
        with conn.cursor() as curs:
            curs.execute(
                sql.SQL(
                    "UPDATE pg_database SET datcollate='C', datctype='C' WHERE datname = {}"
                ).format(sql.Literal(database_name))
            )
    except psycopg2.Error as exc:
        logger.error("Failed to prepare database: %s", str(exc))
        raise


def erase(datasource: typing.Optional[DatasourcePostgreSQL], database_name: str) -> None:
    """Erase database.

    Args:
        datasource: datasource to use to connect.
        database_name: database to connect to.

    Raises:
        Error: something went wrong while erasing the database.
    """
    # Since is not possible to delete the database while connected to it
    # this connection will use the template1 database, provided by PostgreSQL.
    conn = get_conn(datasource=datasource, database_name="template1")
    try:
        with conn.cursor() as curs:
            curs.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(database_name)))
            curs.execute(
                sql.SQL(
                    "CREATE DATABASE {} "
                    "WITH LC_CTYPE = 'C' LC_COLLATE='C' TEMPLATE='template0';"
                ).format(sql.Identifier(database_name))
            )
    except psycopg2.Error as exc:
        logger.error("Failed to erase database: %s", str(exc))
        raise
