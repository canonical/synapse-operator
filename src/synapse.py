#!/usr/bin/env python3

# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helper module used to manage interactions with Synapse."""

import logging
import typing

import ops
from ops.pebble import Check, ExecError

from charm_state import CharmState
from charm_types import ExecResult
from exceptions import CommandMigrateConfigError

COMMAND_MIGRATE_CONFIG = "migrate_config"
COMMAND_PATH = "/start.py"
CHECK_READY_NAME = "synapse-ready"

logger = logging.getLogger(__name__)


class Synapse:  # pylint: disable=too-few-public-methods
    """A class representing the Synapse application."""

    def __init__(self, charm_state: CharmState):
        """Initialize a new instance of the Synapse class.

        Args:
            charm_state: The state of the charm that the Synapse instance belongs to.
        """
        self._charm_state = charm_state

    def check_ready(self) -> typing.Dict:
        """Return the Synapse container check.

        Returns:
            Dict: check object converted to its dict representation.
        """
        check = Check(CHECK_READY_NAME)
        check.override = "replace"
        check.level = "ready"
        check.tcp = {"port": self._charm_state.synapse_port}
        # _CheckDict cannot be imported
        return check.to_dict()  # type: ignore

    def synapse_environment(self) -> typing.Dict[str, str]:
        """Generate a environment dictionary from the charm configurations.

        Returns:
            A dictionary representing the Synapse environment variables.
        """
        return {
            "SYNAPSE_SERVER_NAME": f"{self._charm_state.server_name}",
            "SYNAPSE_REPORT_STATS": f"{self._charm_state.report_stats}",
            # TLS disabled so the listener is HTTP. HTTPS will be handled by Traefik.
            "SYNAPSE_NO_TLS": str(True),
        }

    def execute_migrate_config(self, container: ops.Container) -> None:
        """Run the Synapse command migrate_config.

        Args:
            container: Container of the charm.

        Raises:
            CommandMigrateConfigError: something went wrong running migrate_config.
        """
        migrate_config_command = [COMMAND_PATH, COMMAND_MIGRATE_CONFIG]
        migrate_config_result = self._exec(
            container,
            migrate_config_command,
            environment=self.synapse_environment(),
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
        self,
        container: ops.Container,
        command: list[str],
        environment: dict[str, str] | None = None,
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
