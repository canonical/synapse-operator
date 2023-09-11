# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Mjolnir unit tests."""

# pylint: disable=protected-access

from secrets import token_hex
from unittest.mock import ANY, MagicMock, patch

import ops
import pytest
from ops.testing import Harness

import actions
from constants import SYNAPSE_CONTAINER_NAME
from mjolnir import Mjolnir
from user import User


@patch.object(ops.JujuVersion, "from_environ")
def test_update_peer_data_no_secrets(
    mock_juju_env, harness_server_name_configured: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    arrange: start the Synapse charm, set server_name, mock container and create_admin_user.
    act: call _update_peer_data.
    assert: relation data is updated with access token.
    """
    mock_juju_env.return_value = MagicMock(has_secrets=False)
    harness = harness_server_name_configured
    harness.set_leader(True)
    container_mock = MagicMock()
    username = "any-user"
    user = User(username=username, admin=True)
    user.access_token = token_hex(16)
    create_admin_user_mock = MagicMock(return_value=user)
    monkeypatch.setattr(Mjolnir, "create_admin_user", create_admin_user_mock)

    harness.charm._mjolnir._update_peer_data(container_mock)

    create_admin_user_mock.assert_called_once_with(container_mock)
    peer_relation = harness.model.get_relation("synapse-peers")
    assert peer_relation
    assert (
        harness.get_relation_data(peer_relation.id, harness.charm.app.name).get("secret-key")
        == user.access_token
    )


@patch.object(ops.JujuVersion, "from_environ")
def test_update_peer_data_with_secrets(
    mock_juju_env, harness_server_name_configured: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    arrange: start the Synapse charm, set server_name, mock container and create_admin_user.
    act: call _update_peer_data.
    assert: secret with access token.
    """
    mock_juju_env.return_value = MagicMock(has_secrets=True)
    harness = harness_server_name_configured
    harness.set_leader(True)
    container_mock = MagicMock()
    username = "any-user"
    user = User(username=username, admin=True)
    user.access_token = token_hex(16)
    create_admin_user_mock = MagicMock(return_value=user)
    monkeypatch.setattr(Mjolnir, "create_admin_user", create_admin_user_mock)
    secret_mock = MagicMock
    secret_id = token_hex(16)
    secret_mock.id = secret_id
    add_secret_mock = MagicMock(return_value=secret_mock)
    monkeypatch.setattr(harness.charm.app, "add_secret", add_secret_mock)

    harness.charm._mjolnir._update_peer_data(container_mock)

    create_admin_user_mock.assert_called_once_with(container_mock)
    add_secret_mock.assert_called_once_with({"secret-key": user.access_token})
    peer_relation = harness.model.get_relation("synapse-peers")
    assert peer_relation
    assert (
        harness.get_relation_data(peer_relation.id, harness.charm.app.name).get("secret-id")
        == secret_id
    )


def test_create_admin_user(
    harness_server_name_configured: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    arrange: start the Synapse charm, set server_name, mock container and register_user.
    act: call create_admin_user.
    assert: register_user is called once.
    """
    harness = harness_server_name_configured
    container_mock = MagicMock()
    register_user_mock = MagicMock()
    monkeypatch.setattr(actions, "register_user", register_user_mock)

    harness.charm._mjolnir.create_admin_user(container_mock)

    register_user_mock.assert_called_once_with(container_mock, ANY, True)


def test_on_collect_status_blocked(
    harness_server_name_configured: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    arrange: start the Synapse charm, set server_name, mock container, get_membership_room_id
        and _update_peer_data.
    act: call _on_collect_status.
    assert: status is blocked.
    """
    harness = harness_server_name_configured
    harness.set_leader(True)
    container: ops.Container = harness.model.unit.get_container(SYNAPSE_CONTAINER_NAME)
    monkeypatch.setattr(container, "get_services", MagicMock(return_value=None))
    peer_data_mock = MagicMock()
    monkeypatch.setattr(Mjolnir, "_update_peer_data", peer_data_mock)
    monkeypatch.setattr(Mjolnir, "get_membership_room_id", MagicMock(return_value=None))
    charm_state_mock = MagicMock()
    charm_state_mock.enable_mjolnir = True
    harness.charm._mjolnir._charm_state = charm_state_mock

    event_mock = MagicMock()
    harness.charm._mjolnir._on_collect_status(event_mock)

    peer_data_mock.assert_called_once()
    event_mock.add_status.assert_called_once_with(
        ops.BlockedStatus(
            "moderators not found and is required by Mjolnir. Please, check the logs."
        )
    )


def test_on_collect_status_active(
    harness_server_name_configured: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    arrange: start the Synapse charm, set server_name, mock container, get_membership_room_id
        and _update_peer_data.
    act: call _on_collect_status.
    assert: status is active.
    """
    harness = harness_server_name_configured
    harness.set_leader(True)
    container: ops.Container = harness.model.unit.get_container(SYNAPSE_CONTAINER_NAME)
    monkeypatch.setattr(container, "get_services", MagicMock(return_value=None))
    peer_data_mock = MagicMock()
    monkeypatch.setattr(Mjolnir, "_update_peer_data", peer_data_mock)
    membership_room_id_mock = MagicMock(return_value="123")
    monkeypatch.setattr(Mjolnir, "get_membership_room_id", membership_room_id_mock)
    enable_mjolnir_mock = MagicMock(return_value=None)
    monkeypatch.setattr(Mjolnir, "enable_mjolnir", enable_mjolnir_mock)
    charm_state_mock = MagicMock()
    charm_state_mock.enable_mjolnir = True
    harness.charm._mjolnir._charm_state = charm_state_mock

    event_mock = MagicMock()
    harness.charm._mjolnir._on_collect_status(event_mock)

    peer_data_mock.assert_called_once()
    membership_room_id_mock.assert_called_once()
    enable_mjolnir_mock.assert_called_once()
    event_mock.add_status.assert_called_once_with(ops.ActiveStatus())
