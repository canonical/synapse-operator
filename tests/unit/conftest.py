# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""pytest fixtures for the unit test."""

# pylint: disable=too-few-public-methods, protected-access

import typing
import unittest.mock
from secrets import token_hex

import ops
import pytest
from ops.pebble import ExecError
from ops.testing import Harness

import synapse
from charm import SynapseCharm
from constants import (
    COMMAND_MIGRATE_CONFIG,
    SYNAPSE_COMMAND_PATH,
    SYNAPSE_CONFIG_PATH,
    SYNAPSE_CONTAINER_NAME,
    TEST_SERVER_NAME,
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
def harness_fixture(request, monkeypatch) -> typing.Generator[Harness, None, None]:
    """Ops testing framework harness fixture."""
    harness = Harness(SynapseCharm)
    harness.set_model_name("testmodel")  # needed for testing Traefik
    synapse_container: ops.Container = harness.model.unit.get_container(SYNAPSE_CONTAINER_NAME)
    harness.set_can_connect(SYNAPSE_CONTAINER_NAME, True)
    synapse_container.make_dir("/data", make_parents=True)

    # unused-variable disabled to pass constants values to inner function
    command_path = SYNAPSE_COMMAND_PATH  # pylint: disable=unused-variable
    command_migrate_config = COMMAND_MIGRATE_CONFIG  # pylint: disable=unused-variable
    exit_code = 0
    if hasattr(request, "param"):
        exit_code = request.param

    def start_cmd_handler(argv: list[str]) -> synapse.ExecResult:
        """Handle the python command execution inside the Synapse container.

        Args:
            argv: arguments list.

        Returns:
            ExecResult instance.

        Raises:
            RuntimeError: command unknown.
        """
        nonlocal command_path, command_migrate_config, exit_code
        match argv:
            case [command_path, command_migrate_config]:  # pylint: disable=unused-variable
                return synapse.ExecResult(exit_code, "", "")
            case _:
                raise RuntimeError(f"unknown command: {argv}")

    inject_register_command_handler(monkeypatch, harness)
    harness.register_command_handler(  # type: ignore # pylint: disable=no-member
        container=synapse_container, executable=command_path, handler=start_cmd_handler
    )
    yield harness
    harness.cleanup()


@pytest.fixture(name="harness_server_name_configured")
def harness_server_name_configured_fixture(harness: Harness) -> Harness:
    """Ops testing framework harness fixture with server_name already configured."""
    harness.disable_hooks()
    harness.update_config({"server_name": TEST_SERVER_NAME})
    harness.enable_hooks()
    harness.begin_with_initial_hooks()
    container: ops.Container = harness.model.unit.get_container(SYNAPSE_CONTAINER_NAME)
    container.push(SYNAPSE_CONFIG_PATH, f'server_name: "{TEST_SERVER_NAME}"', make_dirs=True)
    harness.set_can_connect(harness.model.unit.containers[SYNAPSE_CONTAINER_NAME], True)
    harness.framework.reemit()
    harness.set_leader(True)
    return harness


@pytest.fixture(name="harness_server_name_changed")
def harness_server_name_changed_fixture(harness_server_name_configured: Harness) -> Harness:
    """Ops testing framework harness fixture with server_name changed.

    This is a workaround for the fact that Harness doesn't reinitialize the charm as expected.
    Reference: https://github.com/canonical/operator/issues/736
    """
    harness = harness_server_name_configured
    harness.disable_hooks()
    harness._framework = ops.framework.Framework(
        harness._storage, harness._charm_dir, harness._meta, harness._model
    )
    harness._charm = None
    server_name_changed = "pebble-layer-1.synapse.com"
    harness.update_config({"server_name": server_name_changed})
    harness.enable_hooks()
    harness.begin_with_initial_hooks()
    return harness


@pytest.fixture(name="harness_with_postgresql")
def harness_with_postgresql_fixture(
    harness_server_name_configured: Harness, datasource_postgresql_password: str
) -> Harness:
    """Ops testing framework harness fixture with postgresql relation.

    This is a workaround for the fact that Harness doesn't reinitialize the charm as expected.
    Reference: https://github.com/canonical/operator/issues/736
    """
    harness = harness_server_name_configured
    harness.disable_hooks()
    relation_id = harness.add_relation("database", "postgresql")
    harness.add_relation_unit(relation_id, "postgresql/0")
    harness.update_relation_data(
        relation_id,
        "postgresql",
        {
            "endpoints": "myhost:5432",
            "username": "user",
            "password": datasource_postgresql_password,
        },
    )
    harness._framework = ops.framework.Framework(
        harness._storage, harness._charm_dir, harness._meta, harness._model
    )
    harness._charm = None
    harness.enable_hooks()
    harness.begin()
    harness.set_leader(True)
    return harness


@pytest.fixture(name="container_mocked")
def container_mocked_fixture(monkeypatch: pytest.MonkeyPatch) -> unittest.mock.MagicMock:
    """Mock container base to others fixtures."""
    container = unittest.mock.MagicMock()
    monkeypatch.setattr(container, "can_connect", lambda: True)
    exec_process = unittest.mock.MagicMock()
    exec_process.wait_output = unittest.mock.MagicMock(return_value=(0, 0))
    exec_mock = unittest.mock.MagicMock(return_value=exec_process)
    monkeypatch.setattr(container, "exec", exec_mock)
    return container


@pytest.fixture(name="container_with_path_error_blocked")
def container_with_path_error_blocked_fixture(
    container_mocked: unittest.mock.MagicMock, monkeypatch: pytest.MonkeyPatch
) -> unittest.mock.MagicMock:
    """Mock container that gives an error on remove_path that blocks the action."""
    path_error = ops.pebble.PathError(kind="fake", message="Error erasing directory")
    remove_path_mock = unittest.mock.MagicMock(side_effect=path_error)
    monkeypatch.setattr(container_mocked, "remove_path", remove_path_mock)
    return container_mocked


@pytest.fixture(name="container_with_path_error_pass")
def container_with_path_error_pass_fixture(
    container_mocked: unittest.mock.MagicMock, monkeypatch: pytest.MonkeyPatch
) -> unittest.mock.MagicMock:
    """Mock container that gives an error on remove_path that doesn't block the action."""
    path_error = ops.pebble.PathError(
        kind="generic-file-error", message="unlinkat //data: device or resource busy"
    )
    remove_path_mock = unittest.mock.MagicMock(side_effect=path_error)
    monkeypatch.setattr(container_mocked, "remove_path", remove_path_mock)
    return container_mocked


@pytest.fixture(name="erase_database_mocked")
def erase_database_mocked_fixture(monkeypatch: pytest.MonkeyPatch) -> unittest.mock.MagicMock:
    """Mock erase_database."""
    database_mocked = unittest.mock.MagicMock()
    erase_database_mock = unittest.mock.MagicMock(side_effect=None)
    monkeypatch.setattr(database_mocked, "erase_database", erase_database_mock)
    monkeypatch.setattr(database_mocked, "get_conn", unittest.mock.MagicMock())
    monkeypatch.setattr(database_mocked, "get_relation_data", unittest.mock.MagicMock())
    return database_mocked


@pytest.fixture(name="datasource_postgresql_password")
def datasource_postgresql_password_fixture() -> str:
    """Generate random password"""
    return token_hex(16)
