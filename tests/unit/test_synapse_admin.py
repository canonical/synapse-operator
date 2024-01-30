# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Synapse admin unit tests."""

# pylint: disable=protected-access


from secrets import token_hex
from unittest.mock import MagicMock

import pytest
from ops.testing import Harness

import synapse


def test_create_user_success(harness: Harness, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: mock register_user and get_registration_shared_secret.
    act: call create_user.
    assert: the mocks are called and user is returned.
    """
    harness.begin()
    register_user_mock = MagicMock()
    get_registration_shared_secret_mock = MagicMock()
    monkeypatch.setattr("synapse.api.register_user", register_user_mock)
    monkeypatch.setattr(
        "synapse.workload.get_registration_shared_secret", get_registration_shared_secret_mock
    )

    username = token_hex(16)
    # Passing container as a mock since is not used in this test
    user = synapse.create_user(container=MagicMock, username=username)  # type: ignore[arg-type]

    register_user_mock.assert_called_once()
    get_registration_shared_secret_mock.assert_called_once()
    assert user


def test_create_user_error(harness: Harness, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: mock get_registration_shared_secret to return None.
    act: call create_user.
    assert: register_user is not called and return value is None.
    """
    harness.begin()
    register_user_mock = MagicMock()
    get_registration_shared_secret_mock = MagicMock(return_value=None)
    monkeypatch.setattr("synapse.api.register_user", register_user_mock)
    monkeypatch.setattr(
        "synapse.workload.get_registration_shared_secret", get_registration_shared_secret_mock
    )

    username = token_hex(16)
    # Passing container as a mock since is not used in this test
    user = synapse.create_user(container=MagicMock, username=username)  # type: ignore[arg-type]

    register_user_mock.assert_not_called()
    get_registration_shared_secret_mock.assert_called_once()
    assert not user
