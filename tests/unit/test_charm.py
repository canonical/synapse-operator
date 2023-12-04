# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Synapse charm unit tests."""

# pylint: disable=protected-access

import json
from secrets import token_hex
from unittest.mock import MagicMock, patch

import ops
import pytest
from ops.testing import Harness

import actions
import synapse
from charm import SynapseCharm
from pebble import PebbleServiceError

from .conftest import TEST_SERVER_NAME, TEST_SERVER_NAME_CHANGED


def test_synapse_pebble_layer(harness: Harness) -> None:
    """
    arrange: charm deployed.
    act: start the Synapse charm, set Synapse container to be ready and set server_name.
    assert: Synapse charm should submit the correct Synapse pebble layer to pebble.
    """
    harness.begin_with_initial_hooks()

    synapse_layer = harness.get_container_pebble_plan(synapse.SYNAPSE_CONTAINER_NAME).to_dict()[
        "services"
    ][synapse.SYNAPSE_SERVICE_NAME]
    assert isinstance(harness.model.unit.status, ops.ActiveStatus)
    assert synapse_layer == {
        "override": "replace",
        "summary": "Synapse application service",
        "command": synapse.SYNAPSE_COMMAND_PATH,
        "environment": {
            "SYNAPSE_NO_TLS": "True",
            "SYNAPSE_REPORT_STATS": "no",
            "SYNAPSE_SERVER_NAME": TEST_SERVER_NAME,
        },
        "startup": "enabled",
    }


@pytest.mark.parametrize(
    "harness",
    [
        pytest.param(1, id="harness_exit_code"),
    ],
    indirect=True,
)
def test_synapse_migrate_config_error(harness: Harness) -> None:
    """
    arrange: charm deployed.
    act: start the Synapse charm, set Synapse container to be ready and set server_name.
    assert: Synapse charm should be blocked by error on migrate_config command.
    """
    harness.begin_with_initial_hooks()

    assert isinstance(harness.model.unit.status, ops.BlockedStatus)
    assert "Migrate config failed" in str(harness.model.unit.status)


def test_container_down() -> None:
    """
    arrange: charm deployed.
    act: start the Synapse charm, set server_name, set Synapse container to be down
        and then try to change report_stats.
    assert: Synapse charm should submit the correct status.
    """
    harness = Harness(SynapseCharm)
    harness.update_config({"server_name": TEST_SERVER_NAME})
    harness.begin()
    harness.set_can_connect(harness.model.unit.containers[synapse.SYNAPSE_CONTAINER_NAME], False)

    harness.update_config({"report_stats": True})

    assert isinstance(harness.model.unit.status, ops.MaintenanceStatus)
    assert "Waiting for" in str(harness.model.unit.status)
    harness.cleanup()


def test_replan_nginx_container_down(harness: Harness) -> None:
    """
    arrange: Mock container as down.
    act: start the Synapse charm, set server_name, set NGINX Synapse container to be down
        and then try to change report_stats.
    assert: Synapse charm should submit the correct status.
    """
    harness.begin()
    harness.set_can_connect(
        harness.model.unit.containers[synapse.SYNAPSE_NGINX_CONTAINER_NAME], False
    )
    harness.update_config({"report_stats": True})
    assert isinstance(harness.model.unit.status, ops.MaintenanceStatus)
    assert "Waiting for" in str(harness.model.unit.status)


def test_server_name_empty() -> None:
    """
    arrange: charm deployed.
    act: start the Synapse charm and set Synapse container to be ready.
    assert: Synapse charm waits for server_name to be set.
    """
    harness = Harness(SynapseCharm)

    harness.begin()

    assert isinstance(harness.model.unit.status, ops.BlockedStatus)
    assert "invalid configuration: server_name" in str(harness.model.unit.status)


def test_traefik_integration(harness: Harness) -> None:
    """
    arrange: add relation with Traefik charm.
    act: update relation with expected URL.
    assert: Relation data is as expected.
    """
    harness.begin()
    harness.set_leader(True)
    harness.container_pebble_ready(synapse.SYNAPSE_CONTAINER_NAME)
    relation_id = harness.add_relation("ingress", "traefik")
    harness.add_relation_unit(relation_id, "traefik/0")

    app_name = harness.charm.app.name
    model_name = harness.model.name
    url = f"http://ingress:80/{model_name}-{app_name}"
    harness.update_relation_data(
        relation_id,
        "traefik",
        {"ingress": json.dumps({"url": url})},
    )

    app_data = harness.get_relation_data(relation_id, app_name)
    assert app_data == {
        "host": f"{app_name}-endpoints.{model_name}.svc.cluster.local",
        "model": model_name,
        "name": app_name,
        "port": str(synapse.SYNAPSE_NGINX_PORT),
        "strip-prefix": "true",
    }


def test_saml_integration_container_down(saml_configured: Harness) -> None:
    """
    arrange: start the Synapse charm, set server_name, set Synapse container to be down.
    act: emit saml_data_available.
    assert: Synapse charm should submit the correct status.
    """
    harness = saml_configured
    harness.begin()
    harness.set_can_connect(harness.model.unit.containers[synapse.SYNAPSE_CONTAINER_NAME], False)
    relation = harness.charm.framework.model.get_relation("saml", 0)

    harness.charm._saml.saml.on.saml_data_available.emit(relation)

    assert isinstance(harness.model.unit.status, ops.MaintenanceStatus)
    assert "Waiting for" in str(harness.model.unit.status)
    harness.cleanup()


def test_saml_integration_pebble_error(
    saml_configured: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    arrange: start the Synapse charm, set server_name, mock pebble to give an error.
    act: emit saml_data_available.
    assert: Synapse charm should submit the correct status.
    """
    harness = saml_configured
    harness.begin()
    relation = harness.charm.framework.model.get_relation("saml", 0)
    enable_saml_mock = MagicMock(side_effect=PebbleServiceError("fail"))
    monkeypatch.setattr(harness.charm._saml._pebble_service, "enable_saml", enable_saml_mock)

    harness.charm._saml.saml.on.saml_data_available.emit(relation)

    assert isinstance(harness.model.unit.status, ops.BlockedStatus)
    assert "SAML integration failed" in str(harness.model.unit.status)
    harness.cleanup()


def test_server_name_change(harness: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: change to a different server_name.
    assert: Synapse charm should prevent the change with a BlockStatus.
    """
    harness.begin()
    container: ops.Container = harness.model.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
    container.push(
        synapse.SYNAPSE_CONFIG_PATH, f'server_name: "{TEST_SERVER_NAME}"', make_dirs=True
    )
    charm_state_mock = MagicMock()
    charm_state_mock.server_name = TEST_SERVER_NAME_CHANGED
    monkeypatch.setattr(harness.charm.pebble_service, "_charm_state", charm_state_mock)

    harness.update_config({"server_name": TEST_SERVER_NAME_CHANGED})

    assert isinstance(harness.model.unit.status, ops.BlockedStatus)
    assert "server_name modification is not allowed" in str(harness.model.unit.status)


@patch("charm.JUJU_HAS_SECRETS", True)
@patch.object(ops.Application, "add_secret")
def test_get_admin_access_token_with_secrets(
    mock_add_secret, harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    arrange: start the Synapse charm, mock register_user and add_secret.
    act: get admin access token.
    assert: admin user is created, secret is created and the token is retrieved.
    """
    harness.begin_with_initial_hooks()
    # Mocking like the following doesn't get evaluated as expected
    # mock_juju_env.return_value = MagicMock(has_secrets=True)
    secret_mock = MagicMock
    secret_id = token_hex(16)
    secret_mock.id = secret_id
    mock_add_secret.return_value = secret_mock
    user_mock = MagicMock()
    admin_access_token_expected = token_hex(16)
    user_mock.access_token = admin_access_token_expected
    register_user_mock = MagicMock(return_value=user_mock)
    monkeypatch.setattr(actions, "register_user", register_user_mock)

    admin_access_token = harness.charm.get_admin_access_token()

    register_user_mock.assert_called_once()
    mock_add_secret.assert_called_once()
    assert admin_access_token == admin_access_token_expected
    peer_relation = harness.model.get_relation("synapse-peers")
    assert peer_relation
    assert (
        harness.get_relation_data(peer_relation.id, harness.charm.app.name).get("secret-id")
        == secret_id
    )
    assert isinstance(harness.model.unit.status, ops.ActiveStatus)


@patch("charm.JUJU_HAS_SECRETS", False)
@patch.object(ops.Application, "add_secret")
def test_get_admin_access_token_no_secrets(
    mock_add_secret, harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    arrange: start the Synapse charm, mock register_user and add_secret.
    act: get admin access token.
    assert: admin user is created, relation is updated and the token is
        retrieved.
    """
    harness.begin_with_initial_hooks()
    # Mocking like the following doesn't get evaluated as expected
    # mock_juju_env.return_value = MagicMock(has_secrets=True)
    user_mock = MagicMock()
    admin_access_token_expected = token_hex(16)
    user_mock.access_token = admin_access_token_expected
    register_user_mock = MagicMock(return_value=user_mock)
    monkeypatch.setattr(actions, "register_user", register_user_mock)

    admin_access_token = harness.charm.get_admin_access_token()

    register_user_mock.assert_called_once()
    mock_add_secret.assert_not_called()
    assert admin_access_token == admin_access_token_expected
    peer_relation = harness.model.get_relation("synapse-peers")
    assert peer_relation
    assert (
        harness.get_relation_data(peer_relation.id, harness.charm.app.name).get("secret-key")
        == admin_access_token_expected
    )
    assert isinstance(harness.model.unit.status, ops.ActiveStatus)


@patch("charm.JUJU_HAS_SECRETS", True)
@patch.object(ops.Application, "add_secret")
def test_get_admin_access_token_no_peer_relation(mock_add_secret, harness: Harness) -> None:
    """
    arrange: start the Synapse charm without relations.
    act: get admin access token.
    assert: add secret is not called and None is retrieved.
    """
    harness.begin()

    admin_access_token = harness.charm.get_admin_access_token()

    mock_add_secret.assert_not_called()
    assert not admin_access_token


@patch("charm.JUJU_HAS_SECRETS", True)
@patch.object(ops.Model, "get_secret")
def test_get_admin_access_token_existing_secret(mock_get_secret, harness: Harness) -> None:
    """
    arrange: start the Synapse charm, mock relation.
    act: get admin access token.
    assert: secret is queried and the token is retrieved.
    """
    harness.begin_with_initial_hooks()
    peer_relation = harness.model.get_relation("synapse-peers")
    assert peer_relation
    secret_id = token_hex(16)
    harness.update_relation_data(peer_relation.id, "synapse", {"secret-id": secret_id})
    # Mocking like the following doesn't get evaluated as expected
    # mock_juju_env.return_value = MagicMock(has_secrets=True)
    secret_mock = MagicMock
    secret_mock.id = secret_id
    admin_access_token_expected = token_hex(16)
    secret_mock.get_content = MagicMock(return_value={"secret-key": admin_access_token_expected})
    mock_get_secret.return_value = secret_mock

    admin_access_token = harness.charm.get_admin_access_token()

    assert admin_access_token == admin_access_token_expected
    peer_relation = harness.model.get_relation("synapse-peers")
    assert peer_relation
    assert (
        harness.get_relation_data(peer_relation.id, harness.charm.app.name).get("secret-id")
        == secret_id
    )
    assert isinstance(harness.model.unit.status, ops.ActiveStatus)


@patch("charm.JUJU_HAS_SECRETS", True)
@patch.object(ops.Model, "get_secret")
def test_get_admin_access_token_not_found_secret(mock_get_secret, harness: Harness) -> None:
    """
    arrange: start the Synapse charm, mock relation.
    act: get admin access token.
    assert: secret is not found, peer data is erased and None is retrieved.
    """
    harness.begin_with_initial_hooks()
    peer_relation = harness.model.get_relation("synapse-peers")
    assert peer_relation
    secret_id = token_hex(16)
    harness.update_relation_data(peer_relation.id, "synapse", {"secret-id": secret_id})
    # Mocking like the following doesn't get evaluated as expected
    # mock_juju_env.return_value = MagicMock(has_secrets=True)
    mock_get_secret.side_effect = ops.model.SecretNotFoundError()

    admin_access_token = harness.charm.get_admin_access_token()

    assert not admin_access_token
    peer_relation = harness.model.get_relation("synapse-peers")
    assert peer_relation
    assert not harness.get_relation_data(peer_relation.id, harness.charm.app.name).get("secret-id")
    assert isinstance(harness.model.unit.status, ops.ActiveStatus)


@patch("charm.JUJU_HAS_SECRETS", False)
def test_get_admin_access_token_existing_peer_data(harness: Harness) -> None:
    """
    arrange: start the Synapse charm, mock relation.
    act: get admin access token.
    assert: secret is queried and the token is retrieved.
    """
    harness.begin_with_initial_hooks()
    peer_relation = harness.model.get_relation("synapse-peers")
    assert peer_relation
    admin_access_token_expected = token_hex(16)
    harness.update_relation_data(
        peer_relation.id, "synapse", {"secret-key": admin_access_token_expected}
    )

    admin_access_token = harness.charm.get_admin_access_token()

    assert admin_access_token == admin_access_token_expected
    assert isinstance(harness.model.unit.status, ops.ActiveStatus)


def test_enable_federation_domain_whitelist_is_called(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready,
        set server_name and federation_domain_whitelist.
    act: call pebble change_config.
    assert: enable_federation_domain_whitelist is called.
    """
    harness.update_config({"federation_domain_whitelist": "foo"})
    harness.begin()
    harness.set_leader(True)
    monkeypatch.setattr(synapse, "execute_migrate_config", MagicMock())
    monkeypatch.setattr(synapse, "enable_metrics", MagicMock())
    monkeypatch.setattr(synapse, "enable_serve_server_wellknown", MagicMock())
    monkeypatch.setattr(synapse, "validate_config", MagicMock())
    enable_federation_mock = MagicMock()
    monkeypatch.setattr(synapse, "enable_federation_domain_whitelist", enable_federation_mock)

    harness.charm.pebble_service.change_config(container=MagicMock())

    enable_federation_mock.assert_called_once()


def test_disable_password_config_is_called(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready,
        set server_name and enable_password_config.
    act: call pebble change_config.
    assert: disable_password_config is called.
    """
    harness.update_config({"enable_password_config": False})
    harness.begin()
    harness.set_leader(True)
    monkeypatch.setattr(synapse, "execute_migrate_config", MagicMock())
    monkeypatch.setattr(synapse, "enable_metrics", MagicMock())
    monkeypatch.setattr(synapse, "enable_serve_server_wellknown", MagicMock())
    monkeypatch.setattr(synapse, "validate_config", MagicMock())
    disable_password_config_mock = MagicMock()
    monkeypatch.setattr(synapse, "disable_password_config", disable_password_config_mock)

    harness.charm.pebble_service.change_config(container=MagicMock())

    disable_password_config_mock.assert_called_once()


def test_nginx_replan(harness: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    arrange: start the Synapse charm, mock replan_nginx call.
    act: fire that NGINX container is ready.
    assert: Pebble Service replan NGINX is called.
    """
    harness.begin()
    replan_nginx_mock = MagicMock()
    monkeypatch.setattr(harness.charm.pebble_service, "replan_nginx", replan_nginx_mock)

    harness.container_pebble_ready(synapse.SYNAPSE_NGINX_CONTAINER_NAME)

    replan_nginx_mock.assert_called_once()


def test_nginx_replan_failure(harness: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    arrange: start the Synapse charm, mock replan_nginx call and set the container as down.
    act: fire that NGINX container is ready.
    assert: Pebble Service replan NGINX is not called.
    """
    harness.begin()
    replan_nginx_mock = MagicMock()
    monkeypatch.setattr(harness.charm.pebble_service, "replan_nginx", replan_nginx_mock)

    harness.set_can_connect(
        harness.model.unit.containers[synapse.SYNAPSE_NGINX_CONTAINER_NAME], False
    )
    harness.container_pebble_ready(synapse.SYNAPSE_NGINX_CONTAINER_NAME)

    replan_nginx_mock.assert_called_once()
    assert isinstance(harness.model.unit.status, ops.MaintenanceStatus)
