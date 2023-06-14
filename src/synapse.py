#!/usr/bin/env python3

# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helper module used to manage interactions with Synapse."""

import logging
import typing

import ops
from ops.pebble import Check, ExecError

from charm_state import SYNAPSE_PORT, CharmState
from charm_types import ExecResult
from exceptions import CharmConfigInvalidError, CommandMigrateConfigError

COMMAND_MIGRATE_CONFIG = "migrate_config"
COMMAND_PATH = "/start.py"
CHECK_READY_NAME = "synapse-ready"

logger = logging.getLogger(__name__)


def check_ready() -> typing.Dict:
    """Return the Synapse container check.

    Returns:
        Dict: check object converted to its dict representation.
    """
    check = Check(CHECK_READY_NAME)
    check.override = "replace"
    check.level = "ready"
    check.tcp = {"port": SYNAPSE_PORT}
    # _CheckDict cannot be imported
    return check.to_dict()  # type: ignore


def synapse_environment(state: CharmState) -> typing.Dict[str, str]:
    """Generate a environment dictionary from the charm configurations.

    Args:
        state: The state of the charm.

    Returns:
        A dictionary representing the Synapse environment variables.
    """
    return {
        "SYNAPSE_SERVER_NAME": f"{state.server_name}",
        "SYNAPSE_REPORT_STATS": f"{state.report_stats}",
        # TLS disabled so the listener is HTTP instead of HTTPS
        "SYNAPSE_NO_TLS": "True",
    }


def is_configuration_valid(state: CharmState) -> bool:
    """Check if configuration is valid.

    Args:
        state: The state of the charm.

    Returns:
        True if they are all set
    """
    return all([state.server_name, state.report_stats])


def is_server_name_valid(state: CharmState) -> bool:
    """Check if server name is valid.

    Args:
        state: The state of the charm.

    Returns:
        True if server name is valid
    """
    return bool(state.server_name)


def execute_migrate_config(container: ops.Container, state: CharmState) -> None:
    """Run the Synapse command migrate_config.

    Args:
        container: Container of the charm.
        state: State of the charm.

    Raises:
        CommandMigrateConfigError: something went wrong running migrate_config.
        CharmConfigInvalidError: charm configuration is not valid.
    """
    if not is_server_name_valid(state):
        raise CharmConfigInvalidError(
            "The server_name is empty, please review your charm configuration"
        )
    if not is_configuration_valid(state):
        raise CharmConfigInvalidError(
            "Configuration is not valid, please review your charm configuration"
        )
    migrate_config_command = [COMMAND_PATH, COMMAND_MIGRATE_CONFIG]
    migrate_config_result = _exec(
        container, migrate_config_command, environment=synapse_environment(state)
    )
    if migrate_config_result.exit_code:
        logger.error(
            "migrate config failed, stdout: %s, stderr: %s",
            migrate_config_result.stdout,
            migrate_config_result.stderr,
        )
        raise CommandMigrateConfigError(
            "Migrate config failed, please review your charm configuration"
        )


def _exec(
    container: ops.Container, command: list[str], environment: dict[str, str] | None = None
) -> ExecResult:
    """Execute a command inside the Synapse workload container.

    Args:
        container: Container of the charm.
        command: A list of strings representing the command to be executed.
        environment: Environment variables for the command to be executed.

    Returns:
        ExecResult: An `ExecResult` object representing the result of the command execution.
    """
    exec_process = container.exec(command, environment=environment)
    try:
        stdout, stderr = exec_process.wait_output()
        return ExecResult(0, typing.cast(str, stdout), typing.cast(str, stderr))
    except ExecError as exc:
        return ExecResult(
            exc.exit_code, typing.cast(str, exc.stdout), typing.cast(str, exc.stderr)
        )
