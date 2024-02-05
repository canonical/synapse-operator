# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""IRC bridge unit tests."""

# pylint: disable=protected-access

from unittest import mock
from unittest.mock import ANY, MagicMock

import ops
import pytest
import yaml
from ops.testing import Harness

import synapse
import synapse.workload
from irc_bridge import IRCBridge
from synapse.workload import (
    IRC_BRIDGE_CONFIG_PATH,
    IRC_BRIDGE_REGISTRATION_PATH,
    SYNAPSE_CONFIG_PATH,
    CreateIRCBridgeConfigError,
    CreateIRCBridgeRegistrationError,
    WorkloadError,
    _add_app_service_config_field,
    _get_irc_bridge_app_registration,
    create_irc_bridge_app_registration,
    create_irc_bridge_config,
)


def test_on_collect_status_service_exists(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    arrange: start the Synapse charm, set server_name, mock get_services to return something.
    act: call _on_collect_status.
    assert: no actions is taken because the service exists.
    """
    harness.update_config({"enable_irc_bridge": True})
    harness.begin_with_initial_hooks()
    harness.set_leader(True)
    container: ops.Container = harness.model.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
    monkeypatch.setattr(container, "get_services", MagicMock(return_value=MagicMock()))
    enable_irc_bridge_mock = MagicMock()
    monkeypatch.setattr(IRCBridge, "enable_irc_bridge", enable_irc_bridge_mock)

    event_mock = MagicMock()
    harness.charm._irc_bridge._on_collect_status(event_mock)

    event_mock.add_status.assert_not_called()
    enable_irc_bridge_mock.assert_not_called()


def test_on_collect_status_no_service(harness: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    arrange: start the Synapse charm, set server_name, mock get_services to return a empty dict.
    act: call _on_collect_status.
    assert: action is taken because the IRC bridge service can start before Synapse.
    """
    harness.update_config({"enable_irc_bridge": True})
    harness.begin_with_initial_hooks()
    harness.set_leader(True)
    container: ops.Container = harness.model.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
    monkeypatch.setattr(container, "get_services", MagicMock(return_value={}))
    enable_irc_bridge_mock = MagicMock()
    monkeypatch.setattr(IRCBridge, "enable_irc_bridge", enable_irc_bridge_mock)

    event_mock = MagicMock()
    harness.charm._irc_bridge._on_collect_status(event_mock)

    assert isinstance(harness.model.unit.status, ops.ActiveStatus)
    enable_irc_bridge_mock.assert_called_once()


def test_on_collect_status_container_off(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    arrange: start the Synapse charm, set server_name, mock container to not connect.
    act: call _on_collect_status.
    assert: no actions is taken because the container is off.
    """
    harness.update_config({"enable_irc_bridge": True})
    harness.begin_with_initial_hooks()
    container: ops.Container = harness.model.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
    monkeypatch.setattr(container, "can_connect", MagicMock(return_value=False))
    enable_irc_bridge_mock = MagicMock()
    monkeypatch.setattr(IRCBridge, "enable_irc_bridge", enable_irc_bridge_mock)

    event_mock = MagicMock()
    harness.charm._irc_bridge._on_collect_status(event_mock)

    event_mock.add_status.assert_not_called()
    enable_irc_bridge_mock.assert_not_called()


def test_on_collect_status_active(harness: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    arrange: start the Synapse charm, set server_name, mock container, get_membership_room_id
        and _update_peer_data.
    act: call _on_collect_status.
    assert: status is active.
    """
    harness.update_config({"enable_irc_bridge": True})
    harness.begin_with_initial_hooks()
    harness.set_leader(True)
    enable_irc_bridge_mock = MagicMock(return_value=None)
    monkeypatch.setattr(IRCBridge, "enable_irc_bridge", enable_irc_bridge_mock)
    charm_state_mock = MagicMock()
    charm_state_mock.enable_irc_bridge = True
    harness.charm._irc_bridge._charm_state = charm_state_mock

    event_mock = MagicMock()
    harness.charm._irc_bridge._on_collect_status(event_mock)

    enable_irc_bridge_mock.assert_called_once()
    event_mock.add_status.assert_called_once_with(ops.ActiveStatus())


def test_enable_irc_bridge(harness: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    arrange: start the Synapse charm, set server_name, mock calls to validate args.
    act: call enable_irc_bridge.
    assert: all steps are taken as required.
    """
    harness.update_config({"enable_irc_bridge": True})
    harness.begin_with_initial_hooks()
    harness.set_leader(True)
    create_irc_bridge_config_mock = MagicMock()
    monkeypatch.setattr(synapse, "create_irc_bridge_config", create_irc_bridge_config_mock)
    create_irc_bridge_app_registration_mock = MagicMock()
    monkeypatch.setattr(
        synapse, "create_irc_bridge_app_registration", create_irc_bridge_app_registration_mock
    )
    monkeypatch.setattr(
        harness.charm._irc_bridge,
        "_get_db_connection",
        MagicMock(return_value="db_connect_string"),
    )
    harness.charm._irc_bridge.enable_irc_bridge()
    create_irc_bridge_config_mock.assert_called_once_with(
        container=ANY, server_name=ANY, db_connect_string=ANY
    )
    create_irc_bridge_app_registration_mock.assert_called_once_with(container=ANY)
    assert harness.model.unit.status == ops.ActiveStatus()


def test_create_irc_bridge_config_success(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: create a mock container and mock _get_irc_bridge_config function.
    act: call create_irc_bridge_config.
    assert: container.push is called with the correct arguments.
    """
    container_mock = MagicMock()
    server_name = "server_name"
    db_connect_string = "db_connect_string"
    _get_irc_bridge_config_mock = MagicMock(return_value={"key": "value"})

    monkeypatch.setattr(synapse.workload, "_get_irc_bridge_config", _get_irc_bridge_config_mock)
    create_irc_bridge_config(
        container_mock, server_name=server_name, db_connect_string=db_connect_string
    )

    container_mock.push.assert_called_once_with(
        IRC_BRIDGE_CONFIG_PATH, yaml.safe_dump({"key": "value"}), make_dirs=True
    )


def test_create_irc_bridge_config_path_error(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: create a mock container and mock _get_irc_bridge_config function to raise PathError.
    act: call create_irc_bridge_config.
    assert: CreateIRCBridgeConfigError is raised.
    """
    container_mock = MagicMock()
    server_name = "server_name"
    db_connect_string = "db_connect_string"
    _get_irc_bridge_config_mock = MagicMock(
        side_effect=ops.pebble.PathError(kind="not-found", message="Path not found")
    )

    monkeypatch.setattr(synapse.workload, "_get_irc_bridge_config", _get_irc_bridge_config_mock)
    with pytest.raises(CreateIRCBridgeConfigError):
        create_irc_bridge_config(
            container_mock, server_name=server_name, db_connect_string=db_connect_string
        )


def test_create_irc_bridge_app_registration_success(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: create a mock container and mock _get_irc_bridge_app_registration function.
    act: call create_irc_bridge_app_registration.
    assert: container.push is called with the correct arguments.
    """
    container_mock = MagicMock()
    _get_irc_bridge_app_registration_mock = MagicMock(return_value={"key": "value"})

    monkeypatch.setattr(
        "synapse.workload._get_irc_bridge_app_registration", _get_irc_bridge_app_registration_mock
    )
    monkeypatch.setattr("synapse.workload._add_app_service_config_field", MagicMock())
    create_irc_bridge_app_registration(container_mock)

    container_mock.push.assert_called_once_with(
        IRC_BRIDGE_REGISTRATION_PATH, yaml.safe_dump({"key": "value"}), make_dirs=True
    )


def test_create_irc_bridge_app_registration_path_error(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: create a mock container and app registration function to raise PathError.
    act: call create_irc_bridge_app_registration.
    assert: CreateIRCBridgeRegistrationError is raised.
    """
    container_mock = MagicMock()
    _get_irc_bridge_app_registration_mock = MagicMock(
        side_effect=ops.pebble.PathError(kind="not-found", message="Path not found")
    )

    monkeypatch.setattr(
        "synapse.workload._get_irc_bridge_app_registration", _get_irc_bridge_app_registration_mock
    )
    monkeypatch.setattr("synapse.workload._add_app_service_config_field", MagicMock())
    with pytest.raises(CreateIRCBridgeRegistrationError):
        create_irc_bridge_app_registration(container_mock)


def test_get_irc_bridge_app_registration_success():
    """
    arrange: mock the _exec function to return a successful result
    act: call _get_irc_bridge_app_registration
    assert: the expected registration config is returned
    """
    expected_config = {"key": "value"}
    container_mock = MagicMock()
    mock_exec = mock.Mock(return_value=mock.Mock(exit_code=0))
    mock_open = mock.mock_open(read_data="key: value")
    with mock.patch("synapse.workload._exec", mock_exec), mock.patch("builtins.open", mock_open):
        config = _get_irc_bridge_app_registration(container_mock)
    assert config == expected_config


def test_get_irc_bridge_app_registration_failure():
    """
    arrange: mock the _exec function to return a non-zero exit code
    act: call _get_irc_bridge_app_registration
    assert: a WorkloadError is raised
    """
    mock_exec = mock.Mock(return_value=mock.Mock(exit_code=1, stdout="stdout", stderr="stderr"))
    container_mock = MagicMock()
    with mock.patch("synapse.workload._exec", mock_exec):
        with pytest.raises(WorkloadError):
            _get_irc_bridge_app_registration(container_mock)


def test_add_app_service_config_field_success(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: create a mock container and mock the necessary functions.
    act: call _add_app_service_config_field.
    assert: container.push is called with the correct arguments.
    """
    container_mock = MagicMock()
    pull_mock = MagicMock(return_value=mock.Mock(read=mock.Mock(return_value=b"key: value")))
    monkeypatch.setattr(container_mock, "pull", pull_mock)
    monkeypatch.setattr(container_mock, "push", MagicMock())
    monkeypatch.setattr(yaml, "safe_load", MagicMock(return_value={"key": "value"}))
    monkeypatch.setattr(yaml, "safe_dump", MagicMock(return_value="key: value"))

    _add_app_service_config_field(container_mock)

    container_mock.pull.assert_called_once_with(SYNAPSE_CONFIG_PATH)
    container_mock.push.assert_called_once_with(SYNAPSE_CONFIG_PATH, "key: value")


def test_add_app_service_config_field_path_error(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: create a mock container and mock the necessary functions to raise PathError.
    act: call _add_app_service_config_field.
    assert: WorkloadError is raised.
    """
    container_mock = MagicMock()
    pull_mock = MagicMock(
        side_effect=ops.pebble.PathError(kind="not-found", message="Path not found")
    )
    monkeypatch.setattr(container_mock, "pull", pull_mock)

    with pytest.raises(WorkloadError):
        _add_app_service_config_field(container_mock)
