# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Admin Access Token unit tests."""

# pylint: disable=protected-access

from secrets import token_hex
from unittest.mock import MagicMock, patch

import ops
import pytest
from ops.testing import Harness

import admin_access_token
import synapse


@patch("admin_access_token.JUJU_HAS_SECRETS", True)
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
    create_admin_user_mock = MagicMock(return_value=user_mock)
    monkeypatch.setattr(synapse, "create_admin_user", create_admin_user_mock)
    monkeypatch.setattr(synapse, "is_token_valid", MagicMock(return_value=True))

    admin_access_token_real = harness.charm.token_service.get(MagicMock)

    create_admin_user_mock.assert_called_once()
    mock_add_secret.assert_called_once()
    assert admin_access_token_real == admin_access_token_expected
    peer_relation = harness.model.get_relation("synapse-peers")
    assert peer_relation
    assert (
        harness.get_relation_data(peer_relation.id, harness.charm.app.name).get("secret-id")
        == secret_id
    )
    assert isinstance(harness.model.unit.status, ops.ActiveStatus)


@patch("admin_access_token.JUJU_HAS_SECRETS", False)
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
    create_admin_user_mock = MagicMock(return_value=user_mock)
    monkeypatch.setattr(synapse, "create_admin_user", create_admin_user_mock)
    monkeypatch.setattr(synapse, "is_token_valid", MagicMock(return_value=True))

    admin_access_token_real = harness.charm.token_service.get(MagicMock)

    create_admin_user_mock.assert_called_once()
    mock_add_secret.assert_not_called()
    assert admin_access_token_real == admin_access_token_expected
    peer_relation = harness.model.get_relation("synapse-peers")
    assert peer_relation
    assert (
        harness.get_relation_data(peer_relation.id, harness.charm.app.name).get("secret-key")
        == admin_access_token_expected
    )
    assert isinstance(harness.model.unit.status, ops.ActiveStatus)


@pytest.mark.parametrize(
    "juju_has_secrets,is_token_valid",
    [(juju_secret, token_valid) for juju_secret in [True, False] for token_valid in [True, False]],
)
def test_get_admin_access_with_refresh(
    juju_has_secrets: bool, is_token_valid: bool, harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    arrange: start Synapse charm. mock create_admin_user and is_token_valid to return True/False.
        get an admin access token. is_token_valid should not be called yet, and a token
        should be returned.
    act: call get another admin access token.
    assert: is_token_valid should be called, and a new token should be returned if is_token_valid
        was False, otherwise it should be the initial token.
    """
    initial_token = token_hex(16)
    initial_user_mock = MagicMock()
    initial_user_mock.access_token = initial_token

    token_refreshed = token_hex(16)
    refreshed_user_mock = MagicMock()
    refreshed_user_mock.access_token = token_refreshed

    create_admin_user_mock = MagicMock(side_effect=[initial_user_mock, refreshed_user_mock])
    monkeypatch.setattr(synapse, "create_admin_user", create_admin_user_mock)
    is_token_valid_mock = MagicMock(return_value=is_token_valid)
    monkeypatch.setattr(synapse, "is_token_valid", is_token_valid_mock)
    monkeypatch.setattr(admin_access_token, "JUJU_HAS_SECRETS", juju_has_secrets)

    # Get admin access token
    harness.begin_with_initial_hooks()
    monkeypatch.setattr(synapse, "create_admin_user", create_admin_user_mock)
    initial_admin_access_token = harness.charm.token_service.get(MagicMock)
    is_token_valid_mock.assert_not_called()
    assert initial_admin_access_token == initial_token

    # Get admin access token. Should not be refreshed as it is valid.
    refreshed_admin_access_token = harness.charm.token_service.get(MagicMock)

    is_token_valid_mock.assert_called_once()
    assert refreshed_admin_access_token == (
        initial_token if is_token_valid else refreshed_admin_access_token
    )
