# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Admin Access Token unit tests."""

# pylint: disable=protected-access

from secrets import token_hex
from unittest.mock import MagicMock, patch

import ops
import pytest
from ops.testing import Harness

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

    admin_access_token = harness.charm.token_service.get(MagicMock)

    create_admin_user_mock.assert_called_once()
    mock_add_secret.assert_called_once()
    assert admin_access_token == admin_access_token_expected
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

    admin_access_token = harness.charm.token_service.get(MagicMock)

    create_admin_user_mock.assert_called_once()
    mock_add_secret.assert_not_called()
    assert admin_access_token == admin_access_token_expected
    peer_relation = harness.model.get_relation("synapse-peers")
    assert peer_relation
    assert (
        harness.get_relation_data(peer_relation.id, harness.charm.app.name).get("secret-key")
        == admin_access_token_expected
    )
    assert isinstance(harness.model.unit.status, ops.ActiveStatus)
