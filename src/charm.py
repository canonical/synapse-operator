#!/usr/bin/env python3

# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charm for Synapse on kubernetes."""

import logging
from typing import Any, Dict

from ops.charm import CharmBase, HookEvent
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus, WaitingStatus

import synapse
from charm_state import CharmState
from exceptions import CharmConfigInvalidError, CommandMigrateConfigError

logger = logging.getLogger(__name__)


class SynapseOperatorCharm(CharmBase):
    """Charm the service."""

    def __init__(self, *args: Any) -> None:
        """Construct.

        Args:
            args: class arguments.
        """
        super().__init__(*args)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.state: CharmState = CharmState(self)

    def _on_config_changed(self, event: HookEvent) -> None:
        """Handle changed configuration.

        Args:
            event: Event triggering after config is changed.
        """
        container = self.unit.get_container(self.state.container_name)
        if not container.can_connect():
            event.defer()
            self.unit.status = WaitingStatus("Waiting for pebble")
            return
        self.model.unit.status = MaintenanceStatus("Configuring Synapse")
        try:
            synapse.execute_migrate_config(container, self.state)
        except (CommandMigrateConfigError, CharmConfigInvalidError) as exc:
            self.model.unit.status = BlockedStatus(exc.msg)
            event.defer()
            return
        container.add_layer(self.state.container_name, self._pebble_layer, combine=True)
        container.replan()
        self.unit.status = ActiveStatus()

    @property
    def _pebble_layer(self) -> Dict:
        """Return a dictionary representing a Pebble layer."""
        return {
            "summary": "Synapse layer",
            "description": "pebble config layer for Synapse",
            "services": {
                "synapse": {
                    "override": "replace",
                    "summary": "synapse",
                    "startup": "enabled",
                    "command": synapse.COMMAND_PATH,
                    "environment": synapse.synapse_environment(self.state),
                }
            },
            "checks": {
                synapse.CHECK_READY_NAME: synapse.check_ready(self.state),
            },
        }


if __name__ == "__main__":  # pragma: nocover
    main(SynapseOperatorCharm)
