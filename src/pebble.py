#!/usr/bin/env python3

# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Class to interact with pebble."""

import logging
import typing

import ops

from constants import (
    CHECK_READY_NAME,
    SYNAPSE_COMMAND_PATH,
    SYNAPSE_CONTAINER_NAME,
    SYNAPSE_SERVICE_NAME,
)
from synapse import Synapse

logger = logging.getLogger(__name__)


class PebbleService:
    """The charm pebble service manager."""

    def __init__(self, synapse: Synapse):
        """Initialize the pebble service.

        Args:
            synapse: Instance to interact with Synapse.
        """
        self._synapse = synapse

    def replan(self, container: ops.model.Container) -> None:
        """Replan the pebble service.

        Args:
            container: Charm container.
        """
        container.add_layer(SYNAPSE_CONTAINER_NAME, self._pebble_layer, combine=True)
        container.replan()

    def change_config(self, container: ops.model.Container) -> None:
        """Change the configuration.

        Args:
            container: Charm container.
        """
        self._synapse.execute_migrate_config(container)
        self.replan(container)

    def reset_instance(self, container: ops.model.Container) -> None:
        """Reset instance.

        Args:
            container: Charm container.
        """
        # This is needed in the case of relation with Postgresql.
        # If there is open connections it won't be possible to drop the database.
        logger.info("Replan service to not restart")
        container.add_layer(
            SYNAPSE_CONTAINER_NAME, self._pebble_layer_without_restart, combine=True
        )
        container.replan()
        logger.info("Stop Synapse instance")
        container.stop(SYNAPSE_SERVICE_NAME)
        logger.info("Erase Synapse data")
        self._synapse.reset_instance(container)

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
