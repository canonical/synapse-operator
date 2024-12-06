# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

# Ignoring for the config change call
# mypy: disable-error-code="attr-defined"

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

from charm_types import DatasourcePostgreSQL
from database_client import DatabaseClient
from state.mas import MASConfiguration
from state.validation import CharmBaseWithState, validate_charm_state

logger = logging.getLogger(__name__)


class DatabaseObserver(Object):
    """The Database relation observer."""

    def __init__(self, charm: CharmBaseWithState, relation_name: str, database_name: str) -> None:
        """Initialize the observer and register event handlers.

        Args:
            charm: The parent charm to attach the observer to.
            relation_name: The name of the relation to observe.
            database_name: The database name.
        """
        super().__init__(charm, f"{relation_name}-observer")
        self._charm = charm
        # SUPERUSER is required to update pg_database
        self.database = DatabaseRequires(
            self._charm,
            relation_name=relation_name,
            database_name=database_name,
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

    @validate_charm_state
    def _on_database_created(self, _: DatabaseCreatedEvent) -> None:
        """Handle database created."""
        charm = self.get_charm()
        charm_state = charm.build_charm_state()
        MASConfiguration.validate(charm)
        charm.reconcile(charm_state)

    @validate_charm_state
    def _on_endpoints_changed(self, _: DatabaseEndpointsChangedEvent) -> None:
        """Handle endpoints change."""
        charm = self.get_charm()
        charm_state = charm.build_charm_state()
        MASConfiguration.validate(charm)
        charm.reconcile(charm_state)

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


class SynapseDatabaseObserver(DatabaseObserver):
    """The database relation observer."""

    @typing.override
    @validate_charm_state
    def _on_database_created(self, _: DatabaseCreatedEvent) -> None:
        """Handle database created events."""
        self.model.unit.status = ops.MaintenanceStatus("Preparing the database")
        # In case of psycopg2.Error, Juju will set ErrorStatus
        # See discussion here:
        # https://github.com/canonical/synapse-operator/pull/13#discussion_r1253285244
        datasource = self.get_relation_as_datasource()
        db_client = DatabaseClient(datasource=datasource)
        db_client.prepare()
