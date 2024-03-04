# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""The DatabaseClient class."""
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import connection

from integrations.database import DatabaseConfig


class DatabaseClient:
    """A class representing the Synapse application."""

    def __init__(self, database_config: DatabaseConfig, alternative_database: str = ""):
        """Initialize a new instance of the Synapse class.

        Args:
            database_config: datasource to use to connect.
            alternative_database: database to connect to.
                The default is to use the one provided by datasource.
        """
        self._database_config = database_config
        self._database_name = database_config["db"]
        self._alternative_database = alternative_database
        self._conn: connection = None

    def _connect(self) -> None:
        """Get connection."""
        if self._conn is None or self._conn.closed != 0:
            user = self._database_config["user"]
            password = self._database_config["password"]
            host = self._database_config["host"]
            database_name = (
                self._alternative_database
                if self._alternative_database
                else self._database_config["db"]
            )
            self._conn = psycopg2.connect(
                f"dbname='{database_name}' user='{user}' host='{host}'"
                f" password='{password}' connect_timeout=5"
            )
            self._conn.autocommit = True

    def _close(self) -> None:
        """Close database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def prepare(self) -> None:
        """Change database collate and ctype as required by Synapse."""
        try:
            self._connect()
            with self._conn.cursor() as curs:
                curs.execute(
                    sql.SQL(
                        "UPDATE pg_database SET datcollate='C', datctype='C' WHERE datname = {}"
                    ).format(sql.Literal(self._database_name))
                )
        finally:
            self._close()

    def erase(self) -> None:
        """Erase database."""
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
        finally:
            self._close()
