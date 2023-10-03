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
import secret_storage
import synapse
from charm import SynapseCharm
from mjolnir import Mjolnir
from user import User


@patch.object(ops.JujuVersion, "from_environ")
def test_update_peer_data_no_secrets(
    mock_juju_env, harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    arrange: start the Synapse charm, set server_name, mock container and create_admin_user.
    act: call _update_peer_data.
    assert: relation data is updated with access token.
    """
    mock_juju_env.return_value = MagicMock(has_secrets=False)
    harness.set_leader(True)
    harness.update_config({"enable_mjolnir": True})
    harness.begin_with_initial_hooks()
    container_mock = MagicMock()
    username = "any-user"
    user = User(username=username, admin=True)
    user.access_token = token_hex(16)
    create_admin_user_mock = MagicMock(return_value=user)
    monkeypatch.setattr(secret_storage.actions, "register_user", create_admin_user_mock)

    secret_storage._update_peer_data(harness.charm, container_mock)

    create_admin_user_mock.assert_called_once()
    peer_relation = harness.model.get_relation("synapse-peers")
    assert peer_relation
    assert (
        harness.get_relation_data(peer_relation.id, harness.charm.app.name).get("secret-key")
        == user.access_token
    )


@patch.object(ops.JujuVersion, "from_environ")
def test_update_peer_data_with_secrets(
    mock_juju_env, harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    arrange: start the Synapse charm, set server_name, mock container and create_admin_user.
    act: call _update_peer_data.
    assert: secret with access token.
    """
    harness = Harness(SynapseCharm)
    harness.update_config({"enable_mjolnir": True})
    harness.begin_with_initial_hooks()
    mock_juju_env.return_value = MagicMock(has_secrets=True)
    harness.set_leader(True)
    container_mock = MagicMock()
    username = "any-user"
    user = User(username=username, admin=True)
    user.access_token = token_hex(16)
    create_admin_user_mock = MagicMock(return_value=user)
    monkeypatch.setattr(secret_storage.actions, "register_user", create_admin_user_mock)
    secret_mock = MagicMock
    secret_id = token_hex(16)
    secret_mock.id = secret_id
    add_secret_mock = MagicMock(return_value=secret_mock)
    monkeypatch.setattr(harness.charm.app, "add_secret", add_secret_mock)

    secret_storage._update_peer_data(harness.charm, container_mock)

    create_admin_user_mock.assert_called_once()
    add_secret_mock.assert_called_once_with({"secret-key": user.access_token})
    peer_relation = harness.model.get_relation("synapse-peers")
    assert peer_relation
    assert (
        harness.get_relation_data(peer_relation.id, harness.charm.app.name).get("secret-id")
        == secret_id
    )


def test_get_membership_room_id(harness: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    arrange: start the Synapse charm, set server_name, mock get_admin_access_token.
    act: call get_membership_room_id.
    assert: get_membership_room_id is called once with expected args.
    """
    harness.set_leader(True)
    harness.update_config({"enable_mjolnir": True})
    harness.begin_with_initial_hooks()
    admin_access_token = token_hex(16)
    get_room_id = MagicMock()
    monkeypatch.setattr(synapse, "get_room_id", get_room_id)
    monkeypatch.setattr(
        secret_storage, "get_admin_access_token", MagicMock(return_value=admin_access_token)
    )

    harness.charm._mjolnir.get_membership_room_id()

    get_room_id.assert_called_once_with(
        room_name="moderators", admin_access_token=admin_access_token
    )


def test_on_collect_status_blocked(harness: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    arrange: start the Synapse charm, set server_name, mock container, get_membership_room_id
        and _update_peer_data.
    act: call _on_collect_status.
    assert: status is blocked.
    """
    harness.update_config({"enable_mjolnir": True})
    harness.begin_with_initial_hooks()
    harness.set_leader(True)
    monkeypatch.setattr(Mjolnir, "get_membership_room_id", MagicMock(return_value=None))
    charm_state_mock = MagicMock()
    charm_state_mock.enable_mjolnir = True
    harness.charm._mjolnir._charm_state = charm_state_mock

    event_mock = MagicMock()
    harness.charm._mjolnir._on_collect_status(event_mock)

    event_mock.add_status.assert_called_once_with(
        ops.BlockedStatus(
            "moderators not found and is required by Mjolnir. Please, check the logs."
        )
    )


def test_on_collect_status_service_exists(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    arrange: start the Synapse charm, set server_name, mock get_services to return something.
    act: call _on_collect_status.
    assert: no actions is taken because the service exists.
    """
    harness.update_config({"enable_mjolnir": True})
    harness.begin_with_initial_hooks()
    harness.set_leader(True)
    container: ops.Container = harness.model.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
    monkeypatch.setattr(container, "get_services", MagicMock(return_value=MagicMock()))
    enable_mjolnir_mock = MagicMock()
    monkeypatch.setattr(Mjolnir, "enable_mjolnir", enable_mjolnir_mock)

    event_mock = MagicMock()
    harness.charm._mjolnir._on_collect_status(event_mock)

    event_mock.add_status.assert_not_called()
    enable_mjolnir_mock.assert_not_called()


def test_on_collect_status_container_off(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    arrange: start the Synapse charm, set server_name, mock container to not connect.
    act: call _on_collect_status.
    assert: no actions is taken because the container is off.
    """
    harness.update_config({"enable_mjolnir": True})
    harness.begin_with_initial_hooks()
    container: ops.Container = harness.model.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
    monkeypatch.setattr(container, "can_connect", MagicMock(return_value=False))
    enable_mjolnir_mock = MagicMock()
    monkeypatch.setattr(Mjolnir, "enable_mjolnir", enable_mjolnir_mock)

    event_mock = MagicMock()
    harness.charm._mjolnir._on_collect_status(event_mock)

    event_mock.add_status.assert_not_called()
    enable_mjolnir_mock.assert_not_called()


def test_on_collect_status_active(harness: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    arrange: start the Synapse charm, set server_name, mock container, get_membership_room_id
        and _update_peer_data.
    act: call _on_collect_status.
    assert: status is active.
    """
    harness.update_config({"enable_mjolnir": True})
    harness.begin_with_initial_hooks()
    harness.set_leader(True)
    admin_access_token = token_hex(16)
    monkeypatch.setattr(
        secret_storage, "get_admin_access_token", MagicMock(return_value=admin_access_token)
    )
    membership_room_id_mock = MagicMock(return_value="123")
    monkeypatch.setattr(Mjolnir, "get_membership_room_id", membership_room_id_mock)
    enable_mjolnir_mock = MagicMock(return_value=None)
    monkeypatch.setattr(Mjolnir, "enable_mjolnir", enable_mjolnir_mock)
    charm_state_mock = MagicMock()
    charm_state_mock.enable_mjolnir = True
    harness.charm._mjolnir._charm_state = charm_state_mock

    event_mock = MagicMock()
    harness.charm._mjolnir._on_collect_status(event_mock)

    membership_room_id_mock.assert_called_once()
    enable_mjolnir_mock.assert_called_once()
    event_mock.add_status.assert_called_once_with(ops.ActiveStatus())


def test_on_collect_status_api_error(harness: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    arrange: start the Synapse charm, set server_name, mock container, mock get_membership_room_id
        to raise an API error.
    act: call _on_collect_status.
    assert: mjolnir is not enabled.
    """
    harness.update_config({"enable_mjolnir": True})
    harness.begin_with_initial_hooks()
    harness.set_leader(True)
    admin_access_token = token_hex(16)
    monkeypatch.setattr(
        secret_storage, "get_admin_access_token", MagicMock(return_value=admin_access_token)
    )
    membership_room_id_mock = MagicMock(side_effect=synapse.APIError("error"))
    monkeypatch.setattr(Mjolnir, "get_membership_room_id", membership_room_id_mock)
    enable_mjolnir_mock = MagicMock(return_value=None)
    monkeypatch.setattr(Mjolnir, "enable_mjolnir", enable_mjolnir_mock)
    charm_state_mock = MagicMock()
    charm_state_mock.enable_mjolnir = True
    harness.charm._mjolnir._charm_state = charm_state_mock

    event_mock = MagicMock()
    harness.charm._mjolnir._on_collect_status(event_mock)

    membership_room_id_mock.assert_called_once()
    enable_mjolnir_mock.assert_not_called()


@patch.object(ops.JujuVersion, "from_environ")
def test_get_admin_access_token_no_secrets(mock_juju_env, harness: Harness) -> None:
    """
    arrange: start the Synapse charm, set server_name, no secrets.
    act: update relation data with secret key.
    assert: token is returned as expected.
    """
    harness.update_config({"enable_mjolnir": True})
    harness.begin_with_initial_hooks()
    mock_juju_env.return_value = MagicMock(has_secrets=False)
    peer_relation = harness.model.get_relation("synapse-peers")
    assert peer_relation

    expected_token = token_hex(16)
    harness.update_relation_data(peer_relation.id, "synapse", {"secret-key": expected_token})

    assert harness.charm._mjolnir._admin_access_token == expected_token


@patch.object(ops.JujuVersion, "from_environ")
def test_get_admin_access_token_with_secrets(
    mock_juju_env, harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    arrange: start the Synapse charm, set server_name, with secrets.
    act: update relation data with secret key.
    assert: token is returned as expected.
    """
    harness.update_config({"enable_mjolnir": True})
    harness.begin_with_initial_hooks()
    mock_juju_env.return_value = MagicMock(has_secrets=True)
    peer_relation = harness.model.get_relation("synapse-peers")
    assert peer_relation
    expected_id = token_hex(16)
    harness.update_relation_data(peer_relation.id, "synapse", {"secret-id": expected_id})
    secret_mock = MagicMock
    expected_token = token_hex(16)
    expected_content = {"secret-key": expected_token}
    secret_mock.get_content = MagicMock(return_value=expected_content)
    get_secret_mock = MagicMock(return_value=secret_mock)
    monkeypatch.setattr(harness.charm.model, "get_secret", get_secret_mock)

    token = harness.charm._mjolnir._admin_access_token

    get_secret_mock.assert_called_once()
    assert token == expected_token


def test_enable_mjolnir(harness: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    arrange: start the Synapse charm, set server_name, mock calls to validate args.
    act: call enable_mjolnir.
    assert: all steps are taken as required.
    """
    harness.update_config({"enable_mjolnir": True})
    harness.begin_with_initial_hooks()
    harness.set_leader(True)
    admin_access_token = token_hex(16)
    monkeypatch.setattr(
        secret_storage, "get_admin_access_token", MagicMock(return_value=admin_access_token)
    )
    mjolnir_user_mock = MagicMock()
    mjolnir_access_token = token_hex(16)
    mjolnir_user_mock.access_token = mjolnir_access_token
    register_user_mock = MagicMock(return_value=mjolnir_user_mock)
    monkeypatch.setattr(actions, "register_user", register_user_mock)
    room_id = token_hex(16)
    get_room_id = MagicMock(return_value=room_id)
    monkeypatch.setattr(synapse, "get_room_id", get_room_id)
    make_room_admin = MagicMock()
    monkeypatch.setattr(synapse, "make_room_admin", make_room_admin)
    create_mjolnir_config = MagicMock()
    monkeypatch.setattr(synapse, "create_mjolnir_config", create_mjolnir_config)
    override_rate_limit = MagicMock()
    monkeypatch.setattr(synapse, "override_rate_limit", override_rate_limit)

    harness.charm._mjolnir.enable_mjolnir()

    register_user_mock.assert_called_once_with(ANY, ANY, ANY, admin_access_token, ANY)
    get_room_id.assert_called_once_with(
        room_name="management", admin_access_token=admin_access_token
    )
    make_room_admin.assert_called_once_with(
        user=ANY, server=ANY, admin_access_token=admin_access_token, room_id=room_id
    )
    create_mjolnir_config.assert_called_once_with(
        container=ANY, access_token=mjolnir_access_token, room_id=room_id
    )
    override_rate_limit.assert_called_once_with(
        user=ANY, charm_state=ANY, admin_access_token=admin_access_token
    )
    assert harness.model.unit.status == ops.ActiveStatus()


def test_enable_mjolnir_room_none(harness: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    arrange: start the Synapse charm, set server_name, mock calls to validate args,
        get_room_id returns None.
    act: call enable_mjolnir.
    assert: all steps are taken as required.
    """
    harness.update_config({"enable_mjolnir": True})
    harness.begin_with_initial_hooks()
    harness.set_leader(True)
    admin_access_token = token_hex(16)
    monkeypatch.setattr(
        secret_storage, "get_admin_access_token", MagicMock(return_value=admin_access_token)
    )
    mjolnir_user_mock = MagicMock()
    mjolnir_access_token = token_hex(16)
    mjolnir_user_mock.access_token = mjolnir_access_token
    register_user_mock = MagicMock(return_value=mjolnir_user_mock)
    monkeypatch.setattr(actions, "register_user", register_user_mock)
    get_room_id = MagicMock(return_value=None)
    monkeypatch.setattr(synapse, "get_room_id", get_room_id)
    room_id = token_hex(16)
    create_management_room = MagicMock(return_value=room_id)
    monkeypatch.setattr(synapse, "create_management_room", create_management_room)
    make_room_admin = MagicMock()
    monkeypatch.setattr(synapse, "make_room_admin", make_room_admin)
    create_mjolnir_config = MagicMock()
    monkeypatch.setattr(synapse, "create_mjolnir_config", create_mjolnir_config)
    override_rate_limit = MagicMock()
    monkeypatch.setattr(synapse, "override_rate_limit", override_rate_limit)

    harness.charm._mjolnir.enable_mjolnir()

    register_user_mock.assert_called_once_with(ANY, ANY, ANY, admin_access_token, ANY)
    get_room_id.assert_called_once_with(
        room_name="management", admin_access_token=admin_access_token
    )
    create_management_room.assert_called_once_with(admin_access_token=admin_access_token)
    make_room_admin.assert_called_once_with(
        user=ANY, server=ANY, admin_access_token=admin_access_token, room_id=room_id
    )
    create_mjolnir_config.assert_called_once_with(
        container=ANY, access_token=mjolnir_access_token, room_id=room_id
    )
    override_rate_limit.assert_called_once_with(
        user=ANY, charm_state=ANY, admin_access_token=admin_access_token
    )
    assert harness.model.unit.status == ops.ActiveStatus()


def test_enable_mjolnir_container_off(harness: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    arrange: start the Synapse charm, set server_name, mock container to not connect.
    act: call enable_mjolnir.
    assert: the next step, register user, is not called.
    """
    harness.update_config({"enable_mjolnir": True})
    harness.begin_with_initial_hooks()
    container: ops.Container = harness.model.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
    monkeypatch.setattr(container, "can_connect", MagicMock(return_value=False))
    register_user_mock = MagicMock()
    monkeypatch.setattr(actions, "register_user", register_user_mock)

    harness.charm._mjolnir.enable_mjolnir()

    register_user_mock.assert_not_called()
