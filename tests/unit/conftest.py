# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""pytest fixtures for the unit test."""

# pylint: disable=too-few-public-methods

import typing

import ops
import pytest
from ops.pebble import ExecError
from ops.testing import Harness

from charm import SynapseCharm
from charm_types import ExecResult
from constants import (
    COMMAND_ARG_ERROR,
    COMMAND_MIGRATE_CONFIG,
    COMMAND_PATH,
    SYNAPSE_CONTAINER_NAME,
)


def inject_register_command_handler(monkeypatch: pytest.MonkeyPatch, harness: Harness):
    """A helper function for injecting an implementation of the register_command_handler method.

    Args:
        monkeypatch: monkey patch instance.
        harness: harness instance.
    """
    handler_table: dict[str, typing.Callable[[list[str]], tuple[int, str, str]]] = {}

    class ExecProcessStub:
        """A mock object that simulates the execution of a process in the container."""

        def __init__(self, command: list[str], exit_code: int, stdout: str, stderr: str):
            """Initialize the ExecProcessStub object.

            Args:
                command: command to execute.
                exit_code: exit code to return.
                stdout: message to stdout.
                stderr: message to stderr.
            """
            self._command = command
            self._exit_code = exit_code
            self._stdout = stdout
            self._stderr = stderr

        def wait_output(self):
            """Simulate the wait_output method of the container object.

            Returns:
                stdout and stderr from command execution.

            Raises:
                ExecError: something wrong with the command execution.
            """
            if self._exit_code == 0:
                return self._stdout, self._stderr
            raise ExecError(
                command=self._command,
                exit_code=self._exit_code,
                stdout=self._stdout,
                stderr=self._stderr,
            )

    def exec_stub(command: list[str], **_kwargs):
        """A mock implementation of the `exec` method of the container object.

        Args:
            command: command to execute.
            _kwargs: optional arguments.

        Returns:
            ExecProcessStub instance.
        """
        executable = command[0]
        handler = handler_table[executable]
        exit_code, stdout, stderr = handler(command)
        return ExecProcessStub(command=command, exit_code=exit_code, stdout=stdout, stderr=stderr)

    def register_command_handler(
        container: ops.Container | str,
        executable: str,
        handler=typing.Callable[[list[str]], typing.Tuple[int, str, str]],
    ):
        """Registers a handler for a specific executable command.

        Args:
            container: container to register the command.
            executable: executable name.
            handler: handler function to be used.
        """
        container = (
            harness.model.unit.get_container(container)
            if isinstance(container, str)
            else container
        )
        handler_table[executable] = handler
        monkeypatch.setattr(container, "exec", exec_stub)

    monkeypatch.setattr(
        harness, "register_command_handler", register_command_handler, raising=False
    )


@pytest.fixture(name="harness")
def harness_fixture(monkeypatch) -> typing.Generator[Harness, None, None]:
    """Ops testing framework harness fixture."""
    harness = Harness(SynapseCharm)
    synapse_container: ops.Container = harness.model.unit.get_container(SYNAPSE_CONTAINER_NAME)
    harness.set_can_connect(SYNAPSE_CONTAINER_NAME, True)
    synapse_container.make_dir("/data", make_parents=True)

    # unused-variable disabled to pass constants values to inner function
    command_path = COMMAND_PATH  # pylint: disable=unused-variable
    command_migrate_config = COMMAND_MIGRATE_CONFIG  # pylint: disable=unused-variable
    command_arg_error = COMMAND_ARG_ERROR  # pylint: disable=unused-variable

    def start_cmd_handler(argv: list[str]) -> ExecResult:
        """Handle the python command execution inside the Synapse container.

        Args:
            argv: arguments list.

        Returns:
            ExecResult instance.

        Raises:
            RuntimeError: command unknown.
        """
        nonlocal command_path, command_migrate_config, command_arg_error
        match argv:
            case [command_path, command_migrate_config]:  # pylint: disable=unused-variable
                return ExecResult(0, "", "")
            case [command_path, command_arg_error]:  # pylint: disable=unused-variable
                return ExecResult(1, "", "")
            case _:
                raise RuntimeError(f"unknown command: {argv}")

    inject_register_command_handler(monkeypatch, harness)
    harness.register_command_handler(  # type: ignore # pylint: disable=no-member
        container=synapse_container, executable=command_path, handler=start_cmd_handler
    )
    yield harness
    harness.cleanup()
