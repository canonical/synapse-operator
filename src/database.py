# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""The Jenkins agent relation observer."""
import logging
import typing

import ops
import psycopg2
from charms.data_platform_libs.v0.data_interfaces import (
    DatabaseCreatedEvent,
    DatabaseEndpointsChangedEvent,
    DatabaseRequires,
)
from ops.charm import CharmBase
from ops.framework import Object
from psycopg2 import sql
from psycopg2.extensions import connection

from charm_types import DatasourcePostgreSQL
from constants import SYNAPSE_CONTAINER_NAME
from exceptions import CharmDatabaseRelationNotFoundError

logger = logging.getLogger(__name__)


class DatabaseObserver(Object):
    """The Database relation observer.

    Attrs:
        _pebble_service: instance of pebble service.
    """

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
        self.framework.observe(self.database.on.database_created, self._on_database_created)
        self.framework.observe(self.database.on.endpoints_changed, self._on_endpoints_changed)

    @property
    def _pebble_service(self) -> typing.Any:
        """Return instance of pebble service.

        Returns:
            instance of pebble service or none.
        """
        return getattr(self._charm, "pebble_service", None)

    def _change_config(self, event: typing.Any) -> None:
        """Change the configuration.

        Args:
            event: Event triggering the database created or endpoints changed handler.
        """
        container = self._charm.unit.get_container(SYNAPSE_CONTAINER_NAME)
        if not container.can_connect() or self._pebble_service is None:
            event.defer()
            self._charm.unit.status = ops.WaitingStatus("Waiting for pebble")
            return
        try:
            self._pebble_service.change_config(container)
        # Avoiding duplication of code with _change_config in charm.py
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self._charm.model.unit.status = ops.BlockedStatus(f"Database failed: {exc}")
            return
        self._charm.unit.status = ops.ActiveStatus()

    def _on_database_created(self, event: DatabaseCreatedEvent) -> None:
        """Handle database created.

        Args:
            event: Event triggering the database created handler.
        """
        self.model.unit.status = ops.MaintenanceStatus("Preparing the database")
        # In case of psycopg2.Error, Juju will set ErrorStatus
        # See discussion here:
        # https://github.com/canonical/synapse-operator/pull/13#discussion_r1253285244
        self.prepare_database()
        self._change_config(event)

    def _on_endpoints_changed(self, event: DatabaseEndpointsChangedEvent) -> None:
        """Handle endpoints change.

        Args:
            event: Event triggering the endpoints changed handler.
        """
        self._change_config(event)

    def get_relation_as_datasource(self) -> typing.Optional[DatasourcePostgreSQL]:
        """Get database data from relation.

        Returns:
            Dict: Information needed for setting environment variables.
        """
        if self.model.get_relation(self._RELATION_NAME) is None:
            return None

        relation_id = self.database.relations[0].id
        relation_data = self.database.fetch_relation_data()[relation_id]

        endpoint = relation_data.get("endpoints", ":")

        return DatasourcePostgreSQL(
            user=relation_data.get("username", ""),
            password=relation_data.get("password", ""),
            host=endpoint.split(":")[0],
            port=endpoint.split(":")[1],
            db=self._charm.app.name,
        )

    def get_database_name(self) -> str:
        """Get database name.

        Raises:
            CharmDatabaseRelationNotFoundError: if there is no relation.

        Returns:
            str: database name.
        """
        datasource = self.get_relation_as_datasource()
        if datasource is None:
            raise CharmDatabaseRelationNotFoundError("No database relation was found.")
        return datasource["db"]

    def prepare_database(self) -> None:
        """Change database collate and ctype as required by Synapse.

        Raises:
           Error: something went wrong while preparing the database.
        """
        conn = self.get_conn()
        database_name = self.get_database_name()
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

    def get_conn(self, database_name: str = "") -> connection:
        """Get connection.

        Args:
            database_name: database to connect to.

        Raises:
           Error: something went wrong while connecting to the database.
           CharmDatabaseRelationNotFoundError: if there is no relation.

        Returns:
            Connection with the database
        """
        datasource = self.get_relation_as_datasource()
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
