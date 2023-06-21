#!/usr/bin/env python3

# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charm for Synapse on kubernetes."""

import logging
from typing import Any, Dict

import ops
from ops.main import main

from charm_state import CharmState
from constants import (
    CHECK_READY_NAME,
    SYNAPSE_COMMAND_PATH,
    SYNAPSE_CONTAINER_NAME,
    SYNAPSE_SERVICE_NAME,
)
from exceptions import CharmConfigInvalidError, CommandMigrateConfigError
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
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        try:
            self._charm_state = CharmState.from_charm(charm=self)
        except CharmConfigInvalidError as exc:
            self.model.unit.status = ops.BlockedStatus(exc.msg)
            return
        self._synapse = Synapse(charm_state=self._charm_state)

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
        server_name_configured = self._synapse.server_name_configured(container)
        if (
            server_name_configured is not None
            and server_name_configured != self._charm_state.server_name
        ):
            msg = (
                f"server_name {self._charm_state.server_name} is different from the existing one"
                f" {server_name_configured}."
                " Please run the action reset-instance if you really want to change it."
            )
            self.model.unit.status = ops.BlockedStatus(msg)
            return
        self.model.unit.status = ops.MaintenanceStatus("Configuring Synapse")
        try:
            self._synapse.execute_migrate_config(container)
        except CommandMigrateConfigError as exc:
            self.model.unit.status = ops.BlockedStatus(exc.msg)
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


if __name__ == "__main__":  # pragma: nocover
    main(SynapseCharm)
