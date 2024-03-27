# Copyright 2024 Canonical Ltd.
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
from ops.framework import Object

import pebble
import synapse
from charm_state import CharmBaseWithState, CharmState, inject_charm_state
from charm_types import DatasourcePostgreSQL
from database_client import DatabaseClient

logger = logging.getLogger(__name__)


class DatabaseObserver(Object):
    """The Database relation observer."""

    def __init__(self, charm: CharmBaseWithState, relation_name: str) -> None:
        """Initialize the observer and register event handlers.

        Args:
            charm: The parent charm to attach the observer to.
            relation_name: The name of the relation to observe.
        """
        super().__init__(charm, f"{relation_name}-observer")
        self._charm = charm
        # SUPERUSER is required to update pg_database
        self.database = DatabaseRequires(
            self._charm,
            relation_name=relation_name,
            database_name=self._charm.app.name,
            extra_user_roles="SUPERUSER",
        )
        self.framework.observe(self.database.on.database_created, self._on_database_created)
        self.framework.observe(self.database.on.endpoints_changed, self._on_endpoints_changed)

    def get_charm(self) -> CharmBaseWithState:
        """Return the current charm.

        Returns:
           The current charm
        """
        return self._charm

    def _change_config(self, charm_state: CharmState) -> None:
        """Change the configuration.

        Args:
            charm_state: Instance of CharmState
        """
        container = self._charm.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
        if not container.can_connect():
            self._charm.unit.status = ops.MaintenanceStatus("Waiting for Synapse pebble")
            return
        try:
            # getting information from charm if is main unit or not.
            pebble.change_config(
                charm_state, container, is_main=self._charm.is_main()  # type: ignore[attr-defined]
            )
        # Avoiding duplication of code with _change_config in charm.py
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self._charm.model.unit.status = ops.BlockedStatus(f"Database failed: {exc}")
            return
        self._charm.unit.status = ops.ActiveStatus()

    @inject_charm_state
    def _on_database_created(self, _: DatabaseCreatedEvent, charm_state: CharmState) -> None:
        """Handle database created.

        Args:
            charm_state: The charm state.
        """
        self.model.unit.status = ops.MaintenanceStatus("Preparing the database")
        # In case of psycopg2.Error, Juju will set ErrorStatus
        # See discussion here:
        # https://github.com/canonical/synapse-operator/pull/13#discussion_r1253285244
        datasource = self.get_relation_as_datasource()
        db_client = DatabaseClient(datasource=datasource)
        if self.database.relation_name == synapse.SYNAPSE_DB_RELATION_NAME:
            db_client.prepare()
        self._change_config(charm_state)

    @inject_charm_state
    def _on_endpoints_changed(
        self, _: DatabaseEndpointsChangedEvent, charm_state: CharmState
    ) -> None:
        """Handle endpoints change.

        Args:
            charm_state: The charm state.
        """
        self._change_config(charm_state)

    def get_relation_as_datasource(self) -> typing.Optional[DatasourcePostgreSQL]:
        """Get database data from relation.

        Returns:
            Dict: Information needed for setting environment variables.
        """
        # not using get_relation due this issue
        # https://github.com/canonical/operator/issues/1153
        if not self.model.relations.get(self.database.relation_name):
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
