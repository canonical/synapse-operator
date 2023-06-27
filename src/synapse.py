#!/usr/bin/env python3

# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helper module used to manage interactions with Synapse."""

import logging
import typing

import ops
import yaml
from ops.pebble import Check, ExecError, PathError

from charm_state import CharmState
from charm_types import ExecResult
from constants import (
    CHECK_READY_NAME,
    COMMAND_MIGRATE_CONFIG,
    SYNAPSE_COMMAND_PATH,
    SYNAPSE_CONFIG_DIR,
    SYNAPSE_CONFIG_PATH,
    SYNAPSE_PORT,
)
from exceptions import CommandMigrateConfigError, ServerNameModifiedError

logger = logging.getLogger(__name__)


class Synapse:
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
        check.tcp = {"port": SYNAPSE_PORT}
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
            # TODO verify support to HTTPS backend before changing this  # pylint: disable=fixme
            "SYNAPSE_NO_TLS": str(True),
        }

    def execute_migrate_config(self, container: ops.Container) -> None:
        """Run the Synapse command migrate_config.

        Args:
            container: Container of the charm.

        Raises:
            CommandMigrateConfigError: something went wrong running migrate_config.
        """
        # TODO validate if is possible to use SDK instead of command  # pylint: disable=fixme
        migrate_config_command = [SYNAPSE_COMMAND_PATH, COMMAND_MIGRATE_CONFIG]
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

    def check_server_name(self, container: ops.Container) -> None:
        """Check server_name.

        Check if server_name of the state has been modified in relation to the configuration file.

        Args:
            container: Container of the charm.

        Raises:
            PathError: if somethings goes wrong while reading the configuration file.
            ServerNameModifiedError: if server_name from state is different than the one in the
                configuration file.
        """
        try:
            configuration_content = str(
                container.pull(SYNAPSE_CONFIG_PATH, encoding="utf-8").read()
            )
            configured_server_name = yaml.safe_load(configuration_content)["server_name"]
            if (
                configured_server_name is not None
                and configured_server_name != self._charm_state.server_name
            ):
                msg = (
                    f"server_name {self._charm_state.server_name} is different from the existing "
                    f" one {configured_server_name}. Please revert the config or run the action "
                    "reset-instance if you to erase the existing instance and start a new one."
                )
                logger.error(msg)
                raise ServerNameModifiedError(
                    "The server_name modification is not allowed, please check the logs"
                )
        except PathError as path_error:
            if path_error.kind == "not-found":
                logger.debug(
                    "configuration file %s not found, will be created by config-changed",
                    SYNAPSE_CONFIG_PATH,
                )
            else:
                logger.error(
                    "exception while reading configuration file %s: %s",
                    SYNAPSE_CONFIG_PATH,
                    path_error,
                )
                raise

    def reset_instance_action(self, container: ops.Container) -> None:
        """Erase data and config server_name.

        Args:
            container: Container of the charm.

        Raises:
            PathError: if somethings goes wrong while erasing the Synapse directory.
        """
        logging.debug("Erasing directory %s", SYNAPSE_CONFIG_DIR)
        try:
            container.remove_path(SYNAPSE_CONFIG_DIR, recursive=True)
        except PathError as path_error:
            # The error "unlinkat //data: device or resource busy" is expected
            # when removing the entire directory because it's a volume mount.
            # The files will be removed but SYNAPSE_CONFIG_DIR directory will
            # remain.
            if "device or resource busy" in str(path_error):
                pass
            else:
                logger.error(
                    "exception while erasing directory %s: %s", SYNAPSE_CONFIG_DIR, path_error
                )
                raise

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
