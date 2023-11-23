# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""The Database agent relation observer."""
import logging
import typing

import ops
from charms.data_platform_libs.v0.data_interfaces import (
    DatabaseCreatedEvent,
    DatabaseEndpointsChangedEvent,
    DatabaseRequires,
)
from ops.charm import CharmBase
from ops.framework import Object

import synapse
from charm_types import DatasourcePostgreSQL
from database_client import DatabaseClient
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

    def _change_config(self) -> None:
        """Change the configuration."""
        container = self._charm.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
        if not container.can_connect() or self._pebble_service is None:
            self._charm.unit.status = ops.MaintenanceStatus("Waiting for Synapse pebble")
            return
        try:
            self._pebble_service.change_config(container)
        # Avoiding duplication of code with _change_config in charm.py
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self._charm.model.unit.status = ops.BlockedStatus(f"Database failed: {exc}")
            return
        self._charm.unit.status = ops.ActiveStatus()

    def _on_database_created(self, _: DatabaseCreatedEvent) -> None:
        """Handle database created."""
        self.model.unit.status = ops.MaintenanceStatus("Preparing the database")
        # In case of psycopg2.Error, Juju will set ErrorStatus
        # See discussion here:
        # https://github.com/canonical/synapse-operator/pull/13#discussion_r1253285244
        datasource = self.get_relation_as_datasource()
        db_client = DatabaseClient(datasource=datasource)
        db_client.prepare()
        self._change_config()

    def _on_endpoints_changed(self, _: DatabaseEndpointsChangedEvent) -> None:
        """Handle endpoints change."""
        self._change_config()

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
