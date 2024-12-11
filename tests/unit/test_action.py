# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Register user action unit tests."""

# Disabled to access _on_register_user_action
# pylint: disable=protected-access

import unittest.mock

import ops
import pytest
from ops.charm import ActionEvent
from ops.testing import Harness

from user import User


def test_register_user_action(harness: Harness) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: run register-user action.
    assert: User is created and the charm is active.
    """
    harness.begin_with_initial_hooks()
    user = "username"
    event = unittest.mock.MagicMock(spec=ActionEvent)
    event.params = {
        "username": user,
        "admin": "no",
    }

    # Calling to test the action since is not possible calling via harness
    harness.charm._on_register_user_action(event)

    assert event.set_results.call_count == 1
    event.set_results.assert_called_with(
        {"register-user": True, "user-password": unittest.mock.ANY}
    )
    assert isinstance(harness.model.unit.status, ops.ActiveStatus)


def test_username_empty():
    """
    arrange: create a user.
    act: set username as empty.
    assert: ValueError is raised.
    """
    with pytest.raises(ValueError, match="Username must not be empty"):
        User(username="", admin=True)


def test_verify_user_email_action(harness: Harness) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: run register-user action.
    assert: User is created and the charm is active.
    """
    harness.begin_with_initial_hooks()
    user = "username"
    event = unittest.mock.MagicMock(spec=ActionEvent)
    event.params = {
        "username": user,
        "email": "user@email.com",
    }

    # Calling to test the action since is not possible calling via harness
    harness.charm._on_verify_user_email_action(event)

    assert event.set_results.call_count == 1
    event.set_results.assert_called_with({"verify-user-email": True})
    assert isinstance(harness.model.unit.status, ops.ActiveStatus)
