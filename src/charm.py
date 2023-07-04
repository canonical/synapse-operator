#!/usr/bin/env python3

# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charm for Synapse on kubernetes."""

import logging
from typing import Any, Dict

import ops
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

    def __init__(self, *args: Any) -> None:
        """Construct.

        Args:
            args: class arguments.
        """
        super().__init__(*args)
        try:
            self._charm_state = CharmState.from_charm(charm=self)
        except CharmConfigInvalidError as exc:
            self.model.unit.status = ops.BlockedStatus(exc.msg)
            return
        self._database = DatabaseObserver(self)
        self._synapse = Synapse(
            charm_state=self._charm_state, database_data=self._database.get_relation_data())
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

    def _on_config_changed(self, event: ops.HookEvent) -> None:
        """Handle changed configuration.

        Args:
            event: Event triggering after config is changed.
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

    @property
    def _pebble_layer(self) -> Dict:
        """Return a dictionary representing a Pebble layer."""
        return {
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
        self.model.unit.status = ops.MaintenanceStatus("Resetting Synapse instance")
        try:
            self._synapse.reset_instance(container)
            self._synapse.execute_migrate_config(container)
            results["reset-instance"] = True
        except (ops.pebble.PathError, CommandMigrateConfigError) as exc:
            self.model.unit.status = ops.BlockedStatus(str(exc))
            event.fail(str(exc))
            return
        self.model.unit.status = ops.ActiveStatus()
        # results is a dict and set_results expects _SerializedData
        event.set_results(results)  # type: ignore[arg-type]


if __name__ == "__main__":  # pragma: nocover
    main(SynapseCharm)
