# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""The Jenkins agent relation observer."""
import logging
import typing

import psycopg2
from charms.data_platform_libs.v0.data_interfaces import DatabaseRequires
from ops.charm import CharmBase
from ops.framework import Object
from psycopg2 import sql
from psycopg2.extensions import connection

logger = logging.getLogger(__name__)


class DatabaseObserver(Object):
    """The Database relation observer."""

    _RELATION_NAME = "database"

    def __init__(self, charm: CharmBase):
        """Initialize the observer and register event handlers.

        Args:
            charm: The parent charm to attach the observer to.
        """
        super().__init__(charm, "database-observer")
        self._charm = charm
        # SUPERUSER is required to update pg_database
        self.database = DatabaseRequires(
            self._charm,
            relation_name=self._RELATION_NAME,
            database_name=self._charm.app.name,
            extra_user_roles="SUPERUSER",
        )

    def get_relation_data(self) -> typing.Optional[typing.Dict]:
        """Get database data from relation.

        Returns:
            Dict: Information needed for setting environment variables.
        """
        if self.model.get_relation(self._RELATION_NAME) is None:
            return None

        relation_id = self.database.relations[0].id
        relation_data = self.database.fetch_relation_data()[relation_id]

        endpoint = relation_data.get("endpoints", ":")

        return {
            "POSTGRES_USER": relation_data.get("username", ""),
            "POSTGRES_PASSWORD": relation_data.get("password", ""),
            "POSTGRES_HOST": endpoint.split(":")[0],
            "POSTGRES_PORT": endpoint.split(":")[1],
            "POSTGRES_DB": self._charm.app.name,
        }

    def prepare_database(self) -> None:
        """Change database collate and ctype as required by Synapse.

        Raises:
           Error: something went wrong while preparing the database.
        """
        conn = self.get_conn()
        database_name = self.get_database_name()
        if conn is not None:
            try:
                with conn.cursor() as curs:
                    curs.execute(
                        sql.SQL(
                            "UPDATE pg_database "
                            "SET datcollate='C', datctype='C' "
                            "WHERE datname = {}"
                        ).format(sql.Literal(database_name))
                    )
            except psycopg2.Error as exc:
                logger.error("Failed to prepare database: %s", str(exc))
                raise

    def erase_database(self) -> None:
        """Erase database.

        Raises:
           Error: something went wrong while erasing the database.
        """
        # Since is not possible to delete the database while connected to it
        # this connection will use the template1 database, provided by PostgreSQL.
        conn = self.get_conn("template1")
        database_name = self.get_database_name()
        if conn is not None:
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

    def get_conn(self, database_name: str = "") -> connection | None:
        """Get connection.

        Args:
            database_name: database to connect to.

        Raises:
           Error: something went wrong while connecting to the database.

        Returns:
            Connection or None if there is no relation data
        """
        relation_data = self.get_relation_data()
        if relation_data is not None:
            try:
                user = relation_data.get("POSTGRES_USER")
                password = relation_data.get("POSTGRES_PASSWORD")
                host = relation_data.get("POSTGRES_HOST")
                if not database_name:
                    database_name = self.get_database_name()
                conn = psycopg2.connect(
                    f"dbname='{database_name}' user='{user}' host='{host}'"
                    f"password='{password}' connect_timeout=1"
                )
                conn.autocommit = True
                return conn
            except psycopg2.Error as exc:
                logger.error("Failed to connect to database: %s", str(exc))
                raise
        return None

    def get_database_name(self) -> str:
        """Get database name from relation.

        Returns:
            database name
        """
        relation_data = self.get_relation_data()
        if relation_data is not None:
            return relation_data.get("POSTGRES_DB", "")
        return ""
