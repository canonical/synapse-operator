#!/usr/bin/env python3

# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charm for Synapse on kubernetes."""

import logging
import typing

import ops
import psycopg2
from charms.data_platform_libs.v0.data_interfaces import DatabaseCreatedEvent
from charms.nginx_ingress_integrator.v0.nginx_route import require_nginx_route
from charms.traefik_k8s.v1.ingress import IngressPerAppRequirer
from ops.charm import ActionEvent
from ops.main import main

from charm_state import CharmState
from constants import (
    CHECK_READY_NAME,
    SYNAPSE_COMMAND_PATH,
    SYNAPSE_CONTAINER_NAME,
    SYNAPSE_PORT,
    SYNAPSE_SERVICE_NAME,
)
from database import DatabaseObserver
from exceptions import CharmConfigInvalidError, CommandMigrateConfigError, ServerNameModifiedError
from synapse import Synapse

logger = logging.getLogger(__name__)


class SynapseCharm(ops.CharmBase):
    """Charm the service."""

    def __init__(self, *args: typing.Any) -> None:
        """Construct.

        Args:
            args: class arguments.
        """
        super().__init__(*args)
        self.database = DatabaseObserver(self)
        try:
            self._charm_state = CharmState.from_charm(charm=self)
        except CharmConfigInvalidError as exc:
            self.model.unit.status = ops.BlockedStatus(exc.msg)
            return
        self.framework.observe(
            self.database.database.on.database_created, self._on_database_created
        )
        self.framework.observe(
            self.database.database.on.endpoints_changed, self._on_endpoints_changed
        )
        self._synapse = Synapse(charm_state=self._charm_state)
        # service-hostname is a required field so we're hardcoding to the same
        # value as service-name. service-hostname should be set via Nginx
        # Ingress Integrator charm config.
        require_nginx_route(
            charm=self,
            service_hostname=self.app.name,
            service_name=self.app.name,
            service_port=SYNAPSE_PORT,
        )
        self._ingress = IngressPerAppRequirer(
            self,
            port=SYNAPSE_PORT,
            # We're forced to use the app's service endpoint
            # as the ingress per app interface currently always routes to the leader.
            # https://github.com/canonical/traefik-k8s-operator/issues/159
            host=f"{self.app.name}-endpoints.{self.model.name}.svc.cluster.local",
            strip_prefix=True,
        )
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.reset_instance_action, self._on_reset_instance_action)

    def _change_config(self, event: ops.HookEvent) -> None:
        """Change the configuration.

        Args:
            event: Event triggering the need of changing the configuration.
        """
        container = self.unit.get_container(SYNAPSE_CONTAINER_NAME)
        if not container.can_connect():
            event.defer()
            self.unit.status = ops.WaitingStatus("Waiting for pebble")
            return
        try:
            self.model.unit.status = ops.MaintenanceStatus("Configuring Synapse")
            self._synapse.execute_migrate_config(container)
        except (
            CharmConfigInvalidError,
            CommandMigrateConfigError,
            ops.pebble.PathError,
            ServerNameModifiedError,
        ) as exc:
            self.model.unit.status = ops.BlockedStatus(str(exc))
            return
        container.add_layer(SYNAPSE_CONTAINER_NAME, self._pebble_layer, combine=True)
        container.replan()
        self.unit.status = ops.ActiveStatus()

    def _on_config_changed(self, event: ops.HookEvent) -> None:
        """Handle changed configuration.

        Args:
            event: Event triggering after config is changed.
        """
        self._change_config(event)

    @property
    def _pebble_layer(self) -> ops.pebble.LayerDict:
        """Return a dictionary representing a Pebble layer."""
        layer = {
            "summary": "Synapse layer",
            "description": "pebble config layer for Synapse",
            "services": {
                SYNAPSE_SERVICE_NAME: {
                    "override": "replace",
                    "summary": "Synapse application service",
                    "startup": "enabled",
                    "command": SYNAPSE_COMMAND_PATH,
                    "environment": self._synapse.synapse_environment(),
                }
            },
            "checks": {
                CHECK_READY_NAME: self._synapse.check_ready(),
            },
        }
        return typing.cast(ops.pebble.LayerDict, layer)

    @property
    def _pebble_layer_without_restart(self) -> ops.pebble.LayerDict:
        """Return a dictionary representing a Pebble layer without restart."""
        new_layer = self._pebble_layer
        new_layer["services"][SYNAPSE_SERVICE_NAME]["on-success"] = "ignore"
        new_layer["services"][SYNAPSE_SERVICE_NAME]["on-failure"] = "ignore"
        ignore = {CHECK_READY_NAME: "ignore"}
        new_layer["services"][SYNAPSE_SERVICE_NAME]["on-check-failure"] = ignore
        return new_layer

    def _on_reset_instance_action(self, event: ActionEvent) -> None:
        """Reset instance and report action result.

        Args:
            event: Event triggering the reset instance action.
        """
        results = {
            "reset-instance": False,
        }
        if not self.model.unit.is_leader():
            event.fail("Only the juju leader unit can run reset instance action")
            return
        container = self.unit.get_container(SYNAPSE_CONTAINER_NAME)
        if not container.can_connect():
            event.fail("Failed to connect to container")
            return
        # This is needed in the case of relation with Postgresql.
        # If there is open connections it won't be possible to drop the database.
        logger.info("Replan service to not restart")
        container.add_layer(
            SYNAPSE_CONTAINER_NAME, self._pebble_layer_without_restart, combine=True
        )
        container.replan()
        try:
            self.model.unit.status = ops.MaintenanceStatus("Stop Synapse instance")
            logger.info("Stop Synapse instance")
            container.stop(SYNAPSE_SERVICE_NAME)
            self.model.unit.status = ops.MaintenanceStatus("Erase Synapse data")
            self._synapse.reset_instance(container)
            if self.database.connection_params is not None:
                self.model.unit.status = ops.MaintenanceStatus("Erase Synapse database")
                self.database.erase_database()
            self._synapse.execute_migrate_config(container)
            self.model.unit.status = ops.MaintenanceStatus("Start Synapse database")
            logger.info("Start Synapse database")
            container.add_layer(SYNAPSE_CONTAINER_NAME, self._pebble_layer, combine=True)
            container.replan()
            results["reset-instance"] = True
        except (psycopg2.Error, ops.pebble.PathError, CommandMigrateConfigError) as exc:
            self.model.unit.status = ops.BlockedStatus(str(exc))
            event.fail(str(exc))
            return
        self.model.unit.status = ops.ActiveStatus()
        # results is a dict and set_results expects _SerializedData
        event.set_results(results)  # type: ignore[arg-type]

    def _on_database_created(self, event: DatabaseCreatedEvent) -> None:
        """Handle database created.

        Args:
            event: Event triggering the database created handler.
        """
        self.model.unit.status = ops.MaintenanceStatus("Preparing the database")
        # In case of psycopg2.Error, Juju will set ErrorStatus
        # See discussion here:
        # https://github.com/canonical/synapse-operator/pull/13#discussion_r1253285244
        self.database.prepare_database()
        self._change_config(event)

    def _on_endpoints_changed(self, event: DatabaseCreatedEvent) -> None:
        """Handle endpoints change.

        Args:
            event: Event triggering the endpoints changed handler.
        """
        self._change_config(event)


if __name__ == "__main__":  # pragma: nocover
    main(SynapseCharm)
