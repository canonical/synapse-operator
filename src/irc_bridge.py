# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Provide the IRC bridge class to represent the matrix-appservice-app plugin for Synapse."""

# disabling due the fact that collect status does many checks
# pylint: disable=too-many-return-statements

import logging
import typing

import ops
from ops.pebble import APIError, ExecError

import synapse
from charm_state import CharmState

logger = logging.getLogger(__name__)

IRC_SERVICE_NAME = "irc"


class PEMCreateError(Exception):
    """An exception raised when the PEM file creation fails."""

    def __init__(self, message: str):
        """Initialize a new instance of the PEMCreateError class.

        Args:
            message: The error message.
        """
        super().__init__(message)


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
        super().__init__(charm, "irc-bridge")
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
        # pylint:disable=duplicate-code
        if not self._charm_state.synapse_config.enable_irc_bridge:
            return
        if self._charm_state.irc_bridge_datasource is None:
            ops.MaintenanceStatus("Waiting for irc bridge db relation")
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
         - Generate a PEM file for the IRC bridge.
         - Finally, add IRC bridge pebble layer.

        """
        container = self._charm.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
        if not container.can_connect():
            self._charm.unit.status = ops.MaintenanceStatus("Waiting for Synapse pebble")
            return
        self._charm.model.unit.status = ops.MaintenanceStatus("Configuring IRC bridge")
        server_name = self._charm_state.synapse_config.server_name
        db_connect_string = self._get_db_connection()
        synapse.create_irc_bridge_config(
            container=container, server_name=server_name, db_connect_string=db_connect_string
        )
        synapse.create_irc_bridge_app_registration(container=container)
        self._create_pem_file(container=container)
        self._pebble_service.replan_irc_bridge(container)
        self._pebble_service.restart_synapse(container)
        self._charm.model.unit.status = ops.ActiveStatus()

    def _create_pem_file(self, container: ops.model.Container) -> None:
        """Create a PEM file for the IRC bridge.

        Args:
            container: The container to create the PEM file in.

        Raises:
            PEMCreateError: If the PEM file creation fails.
        """
        self._charm.model.unit.status = ops.MaintenanceStatus("Creating PEM file for IRC bridge")
        pem_create_command = [
            "/bin/bash",
            "-c",
            "[[ -f /data/config/passkey.pem ]] || "
            + "openssl genpkey -out /data/config/passkey.pem "
            + "-outform PEM -algorithm RSA -pkeyopt rsa_keygen_bits:2048",
        ]
        logger.info("Creating PEM file for IRC bridge.")
        try:
            exec_process = container.exec(
                pem_create_command,
                environment={},
            )
            stdout, stderr = exec_process.wait_output()
            logger.info("PEM create output: %s. %s.", stdout, stderr)
        except (APIError, ExecError) as exc:
            raise PEMCreateError("PEM creation failed.") from exc
        self._charm.model.unit.status = ops.ActiveStatus()

    def _get_db_connection(self) -> str:
        """Get the database connection string.

        Returns:
            The database connection string.
        """
        db_connect_string = (
            "postgres://"
            + f"{self._charm_state.irc_bridge_datasource['user']}"  # type: ignore
            + f":{self._charm_state.irc_bridge_datasource['password']}"  # type: ignore
            + f"@{self._charm_state.irc_bridge_datasource['host']}"  # type: ignore
            + f":{self._charm_state.irc_bridge_datasource['port']}"  # type: ignore
            + f"/{self._charm_state.irc_bridge_datasource['db']}"  # type: ignore
        )
        return db_connect_string
