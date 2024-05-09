# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""The DatabaseClient class."""
import logging
import typing

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import connection

from charm_types import DatasourcePostgreSQL
from exceptions import CharmDatabaseRelationNotFoundError

logger = logging.getLogger(__name__)


class DatabaseClient:
    """A class representing the Synapse application."""

    def __init__(
        self, datasource: typing.Optional[DatasourcePostgreSQL], alternative_database: str = ""
    ):
        """Initialize a new instance of the Synapse class.

        Args:
            datasource: datasource to use to connect.
            alternative_database: database to connect to.
                The default is to use the one provided by datasource.

        Raises:
            CharmDatabaseRelationNotFoundError: if there is no relation.
        """
        if datasource is None:
            raise CharmDatabaseRelationNotFoundError("No database relation was found.")
        self._datasource = datasource
        self._database_name = datasource["db"]
        self._alternative_database = alternative_database
        self._conn: connection = None

    def _connect(self) -> None:
        """Get connection.

        Raises:
            Error: something went wrong while connecting to the database.
        """
        if self._conn is None or self._conn.closed != 0:
            logger.debug("Connecting to database")
            try:
                user = self._datasource["user"]
                password = self._datasource["password"]
                host = self._datasource["host"]
                database_name = (
                    self._alternative_database
                    if self._alternative_database
                    else self._datasource["db"]
                )
                self._conn = psycopg2.connect(
                    f"dbname='{database_name}' user='{user}' host='{host}'"
                    f" password='{password}' connect_timeout=5"
                )
                self._conn.autocommit = True
            except psycopg2.Error as exc:
                logger.exception("Failed to connect to database: %s", str(exc))
                raise

    def _close(self) -> None:
        """Close database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def prepare(self) -> None:
        """Change database collate and ctype as required by Synapse.

        Raises:
            Error: something went wrong while preparing the database.
        """
        try:
            self._connect()
            with self._conn.cursor() as curs:
                curs.execute(
                    sql.SQL(
                        "SELECT datcollate, datctype FROM pg_database  WHERE datname = {};"
                    ).format(sql.Literal(self._database_name))
                )
                result = curs.fetchone()
                if result and result != ("C", "C"):
                    logging.debug(
                        "Prepare database. database_name: %s collation: %s",
                        self._database_name,
                        result,
                    )
                    curs.execute(
                        sql.SQL(
                            "UPDATE pg_database SET datcollate='C', datctype='C' "
                            "WHERE datname = {}"
                        ).format(sql.Literal(self._database_name))
                    )
                    logging.info("Database %s is ready to be used.", self._database_name)
                else:
                    logging.info(
                        "Database %s already has collation as %s, no action.",
                        self._database_name,
                        result,
                    )
        except psycopg2.Error as exc:
            logger.exception("Failed to prepare database: %r", exc)
            raise
        finally:
            self._close()

    def erase(self) -> None:
        """Erase database.

        Raises:
            Error: something went wrong while erasing the database.
        """
        # Since is not possible to delete the database while connected to it
        # this connection will use the template1 database, provided by PostgreSQL.
        try:
            self._connect()
            with self._conn.cursor() as curs:
                curs.execute(
                    sql.SQL("DROP DATABASE {}").format(sql.Identifier(self._database_name))
                )
                curs.execute(
                    sql.SQL(
                        "CREATE DATABASE {} "
                        "WITH LC_CTYPE = 'C' LC_COLLATE='C' TEMPLATE='template0';"
                    ).format(sql.Identifier(self._database_name))
                )
        except psycopg2.Error as exc:
            logger.exception("Failed to erase database: %r", exc)
            raise
        finally:
            self._close()
