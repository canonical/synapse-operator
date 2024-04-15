# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Provide the IRC bridge class to represent the matrix-appservice-app plugin for Synapse."""

# disabling due the fact that collect status does many checks
# pylint: disable=too-many-return-statements

import logging

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


def enable_irc_bridge(charm_state: CharmState, container: ops.model.Container) -> None:
    """Enable irc service.

    The required steps to enable the IRC bridge are:
     - Create the IRC bridge configuration file.
     - Generate a PEM file for the IRC bridge.

    Args:
        charm_state: Instance of CharmState.
        container: The container to enable the IRC bridge in.

    """
    if not container.can_connect():
        logger.info("Pebble socket not available. Deferring configuration.")
        return
    logger.info("Enabling IRC bridge.")
    db_connect_string = _get_db_connection(charm_state)
    if db_connect_string == "":
        logger.info("No database connection string found. Skipping IRC bridge configuration.")
        return
    synapse.create_irc_bridge_config(
        container=container, charm_state=charm_state, db_connect_string=db_connect_string
    )
    _create_pem_file(container=container)


def _create_pem_file(container: ops.model.Container) -> None:
    """Create a PEM file for the IRC bridge.

    Args:
        container: The container to create the PEM file in.

    Raises:
        PEMCreateError: If the PEM file creation fails.
    """
    pem_create_command = [
        "/bin/bash",
        "-c",
        "[[ -f /data/config/irc_passkey.pem ]] || "
        + "openssl genpkey -out /data/config/irc_passkey.pem "
        + "-outform PEM -algorithm RSA -pkeyopt rsa_keygen_bits:2048",
    ]
    logger.info("Creating PEM file for IRC bridge.")
    try:
        exec_process = container.exec(
            pem_create_command,
        )
        stdout, stderr = exec_process.wait_output()
        logger.info("PEM create output: %s. %s.", stdout, stderr)
    except (APIError, ExecError) as exc:
        raise PEMCreateError("PEM creation failed.") from exc


def _get_db_connection(charm_state: CharmState) -> str:
    """Get the database connection string.

    Args:
        charm_state: Instance of CharmState.

    Returns:
        The database connection string.
    """
    if charm_state.irc_bridge_datasource is None:
        return ""
    db_connect_string = (
        "postgres://"
        f"{charm_state.irc_bridge_datasource['user']}"
        f":{charm_state.irc_bridge_datasource['password']}"
        f"@{charm_state.irc_bridge_datasource['host']}"
        f":{charm_state.irc_bridge_datasource['port']}"
        f"/{charm_state.irc_bridge_datasource['db']}"
    )
    return db_connect_string
