# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Tests for the create_user function in the synapse.admin module."""

from unittest.mock import MagicMock, patch

from ops.testing import Harness

import synapse
from synapse.admin import create_user


def test_create_user_success(harness: Harness, monkeypatch):
    """
    arrange: start the Synapse charm and set the necessary parameters.
    act: call the create_user function.
    assert: user is created successfully and the access token is generated.
    """
    harness.begin_with_initial_hooks()
    container = harness.model.unit.containers["synapse"]
    username = "test_user"
    admin = True
    admin_access_token = "admin_token"
    server = "test_server"

    monkeypatch.setattr(
        synapse.workload, "get_registration_shared_secret", MagicMock(return_value="shared_secret")
    )
    monkeypatch.setattr(
        synapse.workload, "_get_configuration_field", MagicMock(return_value="shared_secret")
    )
    monkeypatch.setattr(synapse.api, "register_user", MagicMock(return_value="access_token"))

    with patch("synapse.api._do_request") as mock_request:
        mock_request.return_value.status_code = 200
        mock_request.return_value.json.return_value = {
            "access_token": "access_token",
            "nonce": "sense",
        }
        user = create_user(
            container=container,
            username=username,
            admin=admin,
            admin_access_token=admin_access_token,
            server=server,
        )

    assert user is not None
    assert user.username == username
    assert user.admin == admin
    assert user.access_token is not None


def test_create_user_no_shared_secret(harness: Harness, monkeypatch):
    """
    arrange: start the Synapse charm without the registration shared secret.
    act: call the create_user function.
    assert: user creation fails and None is returned.
    """
    harness.begin_with_initial_hooks()
    container = harness.model.unit.containers["synapse"]
    username = "test_user"
    admin = True
    admin_access_token = "admin_token"
    server = "test_server"

    monkeypatch.setattr(
        synapse.workload, "get_registration_shared_secret", MagicMock(return_value=None)
    )
    monkeypatch.setattr(synapse.workload, "_get_configuration_field", MagicMock(return_value=None))

    user = create_user(
        container=container,
        username=username,
        admin=admin,
        admin_access_token=admin_access_token,
        server=server,
    )

    assert user is None
