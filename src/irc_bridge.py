# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Provide the IRC bridge class to represent the matrix-appservice-app plugin for Synapse."""

# disabling due the fact that collect status does many checks
# pylint: disable=too-many-return-statements

import logging
import typing

import ops

import actions
import synapse
from charm_state import CharmState

logger = logging.getLogger(__name__)

IRC_SERVICE_NAME = "irc"


class IRCBridge(ops.Object):  # pylint: disable=too-few-public-methods
    """A class representing the IRC bridge plugin for Synapse application.

    See https://github.com/matrix-org/matrix-appservice-irc/ for more details about it.
    """

    def __init__(self, charm: ops.CharmBase, charm_state: CharmState):
        """Initialize a new instance of the IRC bridge class.

        Args:
            charm: The charm object that the IRC bridge instance belongs to.
            charm_state: Instance of CharmState.
        """
        super().__init__(charm, "mjolnir")
        self._charm = charm
        self._charm_state = charm_state
        self.framework.observe(charm.on.collect_unit_status, self._on_collect_status)

    @property
    def _pebble_service(self) -> typing.Any:
        """Return instance of pebble service.

        Returns:
            instance of pebble service or none.
        """
        return getattr(self._charm, "pebble_service", None)

    def _on_collect_status(self, event: ops.CollectStatusEvent) -> None:
        """Collect status event handler.

        Args:
            event: Collect status event.
        """
        if not self._charm_state.synapse_config.enable_irc_bridge:
            return
        container = self._charm.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
        if not container.can_connect():
            self._charm.unit.status = ops.MaintenanceStatus("Waiting for Synapse pebble")
            return
        irc_service = container.get_services(IRC_SERVICE_NAME)
        if irc_service:
            logger.debug("%s service already exists, skipping", IRC_SERVICE_NAME)
            return
        self.enable_irc_bridge()
        event.add_status(ops.ActiveStatus())

    def enable_irc_bridge(self) -> None:
        """Enable irc service.

        The required steps to enable the IRC bridge are:
         - Create the IRC bridge configuration file.
         - Create the IRC bridge registration file.
         - Finally, add IRC bridge pebble layer.

        """
        container = self._charm.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
        if not container.can_connect():
            self._charm.unit.status = ops.MaintenanceStatus("Waiting for Synapse pebble")
            return
        self._charm.model.unit.status = ops.MaintenanceStatus("Configuring IRC bridge")
        actions.create_irc_app_registration(
            container=container
        )
        synapse.create_irc_config(
            container=container
        )
        self._pebble_service.replan_irc(container)
        self._charm.model.unit.status = ops.ActiveStatus()

