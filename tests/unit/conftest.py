# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""pytest fixtures for the unit test."""

# pylint: disable=too-few-public-methods, protected-access

import time
import typing
import unittest.mock
from secrets import token_hex
from unittest.mock import MagicMock

import ops
import pytest
import yaml
from charms.smtp_integrator.v0.smtp import AuthType, TransportSecurity
from ops.pebble import ExecError
from ops.testing import Harness

import synapse
from charm import SynapseCharm
from s3_parameters import S3Parameters

TEST_SERVER_NAME = "server-name-configured.synapse.com"
TEST_SERVER_NAME_CHANGED = "pebble-layer-1.synapse.com"


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

        def wait(self):
            """Simulate the wait method of the container object."""
            self.wait_output()

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
    monkeypatch.setattr(synapse, "get_version", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(synapse, "create_admin_user", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(time, "sleep", lambda *_args, **_kwargs: "")
    # Assume that MAS is working properly
    monkeypatch.setattr("auth.mas.MasService.generate_mas_config", MagicMock(return_value=""))
    monkeypatch.setattr("pebble._push_mas_config", MagicMock())

    harness = Harness(SynapseCharm)
    # Necessary for traefik-k8s.v2.ingress library as it calls binding.network.bind_address
    harness.add_network("10.0.0.10")
    harness.update_config({"server_name": TEST_SERVER_NAME})
    harness.add_relation("mas-database", "postgresql-k8s")
    harness.set_model_name("testmodel")  # needed for testing Traefik
    synapse_container: ops.Container = harness.model.unit.get_container(
        synapse.SYNAPSE_CONTAINER_NAME
    )
    harness.set_can_connect(synapse.SYNAPSE_CONTAINER_NAME, True)
    synapse_container.make_dir("/data", make_parents=True)
    synapse_container.push(f"/data/{TEST_SERVER_NAME}.signing.key", "123")
    # unused-variable disabled to pass constants values to inner function
    command_path = synapse.SYNAPSE_COMMAND_PATH  # pylint: disable=unused-variable
    command_migrate_config = synapse.COMMAND_MIGRATE_CONFIG  # pylint: disable=unused-variable
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
        nonlocal command_path, command_migrate_config, exit_code, synapse_container
        match argv:
            case [command_path, command_migrate_config]:  # pylint: disable=unused-variable
                config_content = {
                    "listeners": [
                        {"type": "http", "port": 8080, "bind_addresses": ["::"]},
                    ],
                    "server_name": TEST_SERVER_NAME,
                }
                synapse_container.push(
                    synapse.SYNAPSE_CONFIG_PATH, yaml.safe_dump(config_content), make_dirs=True
                )
                return synapse.ExecResult(exit_code, "", "")
            case _:
                raise RuntimeError(f"unknown command: {argv}")

    inject_register_command_handler(monkeypatch, harness)
    # Disabling no-member in the following lines due error:
    # 'Harness[SynapseCharm] has no attribute "register_command_handler"
    harness.register_command_handler(  # type: ignore # pylint: disable=no-member
        container=synapse_container, executable=command_path, handler=start_cmd_handler
    )
    harness.register_command_handler(  # type: ignore # pylint: disable=no-member
        container=synapse_container,
        executable="/usr/bin/python3",
        handler=lambda _: synapse.ExecResult(0, "", ""),
    )
    harness.register_command_handler(  # type: ignore # pylint: disable=no-member
        container=synapse_container,
        executable="cp",
        handler=lambda _: synapse.ExecResult(0, "", ""),
    )
    harness.register_command_handler(  # type: ignore # pylint: disable=no-member
        container=synapse_container,
        executable="sed",
        handler=lambda _: synapse.ExecResult(0, "", ""),
    )
    harness.register_command_handler(  # type: ignore # pylint: disable=no-member
        container=synapse_container,
        executable="rm",
        handler=lambda _: synapse.ExecResult(0, "", ""),
    )
    yield harness
    harness.cleanup()


@pytest.fixture(name="smtp_configured")
def smtp_configured_fixture(harness: Harness) -> Harness:
    """Harness fixture with smtp relation configured"""
    harness.update_config({"server_name": TEST_SERVER_NAME, "public_baseurl": TEST_SERVER_NAME})
    password_id = harness.add_model_secret("smtp-integrator", {"password": token_hex(16)})
    smtp_relation_data = {
        "auth_type": AuthType.PLAIN,
        "host": "127.0.0.1",
        "password_id": password_id,
        "port": "25",
        "transport_security": TransportSecurity.TLS,
        "user": "username",
    }
    harness.add_relation("smtp", "smtp-integrator", app_data=smtp_relation_data)
    harness.grant_secret(password_id, "synapse")
    harness.set_can_connect(synapse.SYNAPSE_CONTAINER_NAME, True)
    harness.set_leader(True)
    return harness


@pytest.fixture(name="redis_configured")
def redis_configured_fixture(harness: Harness) -> Harness:
    """Harness fixture with redis relation configured"""
    harness.update_config({"server_name": TEST_SERVER_NAME, "public_baseurl": TEST_SERVER_NAME})
    harness.add_relation("redis", "redis", unit_data={"hostname": "redis-host", "port": "1010"})
    harness.set_can_connect(synapse.SYNAPSE_CONTAINER_NAME, True)
    harness.set_leader(True)
    return harness


@pytest.fixture(name="prometheus_configured")
def prometheus_configured_fixture(harness: Harness) -> Harness:
    """Harness fixture with prometheus relation configured"""
    harness.update_config({"server_name": TEST_SERVER_NAME, "public_baseurl": TEST_SERVER_NAME})
    harness.add_relation("metrics-endpoint", "prometheus-k8s")
    harness.set_can_connect(synapse.SYNAPSE_CONTAINER_NAME, True)
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


@pytest.fixture(name="s3_relation_data_backup")
def s3_relation_data_backup_fixture() -> dict:
    """Returns valid S3 relation data."""
    return {
        "access-key": token_hex(16),
        "secret-key": token_hex(16),
        "bucket": "synapse-backup-bucket",
        "path": "/synapse-backups",
        "s3-uri-style": "path",
        "endpoint": "https://s3.example.com",
    }


@pytest.fixture(name="s3_parameters_backup")
def s3_parameters_backup_fixture(s3_relation_data_backup) -> S3Parameters:
    """Returns valid S3 Parameters."""
    return S3Parameters(**s3_relation_data_backup)


@pytest.fixture(name="s3_relation_data_media")
def s3_relation_data_media_fixture() -> dict:
    """Returns valid S3 relation data."""
    return {
        "access-key": token_hex(16),
        "secret-key": token_hex(16),
        "bucket": "synapse-media-bucket",
        "path": "/synapse-media",
        "s3-uri-style": "path",
        "endpoint": "https://s3.example.com",
    }


@pytest.fixture(name="s3_parameters_media")
def s3_parameters_media_fixture(s3_relation_data_media) -> S3Parameters:
    """Returns valid S3 Parameters."""
    return S3Parameters(**s3_relation_data_media)


@pytest.fixture(name="config_content")
def config_content_fixture() -> dict:
    """Returns valid Synapse configuration."""
    config_content = """
    listeners:
      - type: http
        port: 8080
        bind_addresses: ['::']
    """
    return yaml.safe_load(config_content)


@pytest.fixture(name="mocked_synapse_calls")
def mocked_synapse_calls_fixture(monkeypatch):
    """Mock synapse calls functions."""
    monkeypatch.setattr(
        synapse.workload, "get_registration_shared_secret", MagicMock(return_value="shared_secret")
    )
    monkeypatch.setattr(
        synapse.workload, "_get_configuration_field", MagicMock(return_value="shared_secret")
    )
    monkeypatch.setattr(synapse.api, "register_user", MagicMock(return_value="access_token"))
    monkeypatch.setattr(synapse, "create_management_room", MagicMock(return_value=token_hex(16)))
