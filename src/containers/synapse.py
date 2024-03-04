#!/usr/bin/env python3

# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helper module used to manage interactions with Synapse."""

import typing

import ops
from ops.pebble import Check, ExecError

from config import SynapseConfig
from integrations.database import DatabaseConfig

CHECK_READY_NAME = "synapse-ready"
COMMAND_MIGRATE_CONFIG = "migrate_config"
SYNAPSE_COMMAND_PATH = "/start.py"
SYNAPSE_PORT = 8008
SYNAPSE_CONFIG_DIR = "/data"
SYNAPSE_CONFIG_PATH = f"{SYNAPSE_CONFIG_DIR}/homeserver.yaml"

SYNAPSE_SERVICE_NAME = "synapse"


class ContainerError(Exception):
    """Exception raised when a charm configuration is found to be invalid.

    Attrs:
        msg (str): Explanation of the error.
    """

    def __init__(self, msg: str):
        """Initialize a new instance of the PebbleError exception.

        Args:
            msg (str): Explanation of the error.
        """
        self.msg = msg


class ExecResult(typing.NamedTuple):
    """A named tuple representing the result of executing a command.

    Attributes:
        exit_code: The exit status of the command (0 for success, non-zero for failure).
        stdout: The standard output of the command as a string.
        stderr: The standard error output of the command as a string.
    """

    exit_code: int
    stdout: str
    stderr: str


def pebble_layer(environment: typing.Dict[str, str]) -> ops.pebble.LayerDict:
    """Return a dictionary representing a Pebble layer.

    Args:
        environment: Synapse environment.

    Returns:
        LayerDict: Pebble layer.
    """
    layer = {
        "summary": "Synapse layer",
        "description": "pebble config layer for Synapse",
        "services": {
            SYNAPSE_SERVICE_NAME: {
                "override": "replace",
                "summary": "Synapse application service",
                "startup": "enabled",
                "command": SYNAPSE_COMMAND_PATH,
                "environment": environment,
            }
        },
        "checks": {
            CHECK_READY_NAME: check_ready(),
        },
    }
    return typing.cast(ops.pebble.LayerDict, layer)


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


def synapse_environment(
    synapse_config: SynapseConfig, database_config: typing.Optional[DatabaseConfig]
) -> typing.Dict[str, str]:
    """Generate a environment dictionary from the charm configurations.

    Args:
        synapse_config: Synapse configuration.
        database_config: Database configuration.

    Returns:
        A dictionary representing the Synapse environment variables.
    """
    environment = {
        "SYNAPSE_SERVER_NAME": f"{synapse_config.server_name}",
        "SYNAPSE_REPORT_STATS": f"{synapse_config.report_stats}",
        # TLS disabled so the listener is HTTP. HTTPS will be handled by Traefik.
        # TODO verify support to HTTPS backend before changing this  # pylint: disable=fixme
        "SYNAPSE_NO_TLS": str(True),
    }

    if database_config is not None:
        environment["POSTGRES_DB"] = database_config["db"]
        environment["POSTGRES_HOST"] = database_config["host"]
        environment["POSTGRES_PORT"] = database_config["port"]
        environment["POSTGRES_USER"] = database_config["user"]
        environment["POSTGRES_PASSWORD"] = database_config["password"]
    return environment


def execute_migrate_config(
    container: ops.Container,
    environment: typing.Dict[str, str],
) -> None:
    """Run the Synapse command migrate_config.

    Args:
        container: Container of the charm.
        environment: Synapse environment.

    Raises:
        ContainerError: something went wrong running migrate_config.
    """
    migrate_config_command = [SYNAPSE_COMMAND_PATH, COMMAND_MIGRATE_CONFIG]
    migrate_config_result = _exec(
        container,
        migrate_config_command,
        environment=environment,
    )
    if migrate_config_result.exit_code:
        raise ContainerError("Migrate config failed, please review your charm configuration")


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
    exec_process = container.exec(command, environment=environment, working_dir=SYNAPSE_CONFIG_DIR)
    try:
        stdout, stderr = exec_process.wait_output()
        return ExecResult(0, typing.cast(str, stdout), typing.cast(str, stderr))
    except ExecError as exc:
        return ExecResult(
            exc.exit_code, typing.cast(str, exc.stdout), typing.cast(str, exc.stderr)
        )
