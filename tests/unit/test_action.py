# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Register user action unit tests."""

# Disabled to access _on_register_user_action
# pylint: disable=protected-access

import unittest.mock
from unittest.mock import MagicMock

import ops
import pytest
from ops.charm import ActionEvent
from ops.testing import Harness

import synapse
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


def test_register_user_action_pebble_exec_error(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    arrange: Given a mocked synapse container with an exec method that raises ExecError.
    act: run verify_user_email.
    assert: The correct exception is raised.
    """
    harness.begin_with_initial_hooks()
    event = unittest.mock.MagicMock(spec=ActionEvent)
    event.params = {"username": "username", "admin": "no"}
    container = harness.model.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
    monkeypatch.setattr(
        container, "exec", MagicMock(side_effect=ops.pebble.ExecError([], 1, "", ""))
    )
    harness.charm._on_register_user_action(event)
    assert event.fail.call_count == 1


def test_register_user_action_action_container_not_ready(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    arrange: Given a mocked synapse container with an exec method that raises ExecError.
    act: run verify_user_email.
    assert: The correct exception is raised.
    """
    harness.begin_with_initial_hooks()
    event = unittest.mock.MagicMock(spec=ActionEvent)
    event.params = {"username": "username", "admin": "no"}
    container = harness.model.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
    monkeypatch.setattr(container, "can_connect", MagicMock(return_value=False))
    harness.charm._on_register_user_action(event)
    assert event.fail.call_count == 1


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
    event = unittest.mock.MagicMock(spec=ActionEvent)
    event.params = {"username": "username", "email": "user@email.com"}

    harness.charm._on_verify_user_email_action(event)

    assert event.set_results.call_count == 1
    event.set_results.assert_called_with({"verify-user-email": True})
    assert isinstance(harness.model.unit.status, ops.ActiveStatus)


def test_verify_user_email_action_pebble_exec_error(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    arrange: Given a mocked synapse container with an exec method that raises ExecError.
    act: run verify_user_email.
    assert: The correct exception is raised.
    """
    harness.begin_with_initial_hooks()
    event = unittest.mock.MagicMock(spec=ActionEvent)
    event.params = {"username": "username", "email": "user@email.com"}
    container = harness.model.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
    monkeypatch.setattr(
        container, "exec", MagicMock(side_effect=ops.pebble.ExecError([], 1, "", ""))
    )
    harness.charm._on_verify_user_email_action(event)
    assert event.fail.call_count == 1


def test_verify_user_email_action_container_not_ready(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    arrange: Given a mocked synapse container with an exec method that raises ExecError.
    act: run verify_user_email.
    assert: The correct exception is raised.
    """
    harness.begin_with_initial_hooks()
    event = unittest.mock.MagicMock(spec=ActionEvent)
    event.params = {"username": "username", "email": "user@email.com"}
    container = harness.model.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
    monkeypatch.setattr(container, "can_connect", MagicMock(return_value=False))
    harness.charm._on_verify_user_email_action(event)
    assert event.fail.call_count == 1


def test_anonymize_user_action(harness: Harness) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: run anonymize-user action.
    assert: User is deactivated and the charm is active.
    """
    harness.begin_with_initial_hooks()
    event = unittest.mock.MagicMock(spec=ActionEvent)
    event.params = {"username": "username"}
    harness.charm._on_anonymize_user_action(event)
    assert event.set_results.call_count == 1
    event.set_results.assert_called_with({"anonymize-user": True})
    assert isinstance(harness.model.unit.status, ops.ActiveStatus)


def test_anonymize_user_action_pebble_exec_error(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    arrange: Given a mocked synapse container with an exec method that raises ExecError.
    act: run verify_user_email.
    assert: The correct exception is raised.
    """
    harness.begin_with_initial_hooks()
    event = unittest.mock.MagicMock(spec=ActionEvent)
    event.params = {"username": "username"}
    container = harness.model.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
    monkeypatch.setattr(
        container, "exec", MagicMock(side_effect=ops.pebble.ExecError([], 1, "", ""))
    )
    harness.charm._on_anonymize_user_action(event)
    assert event.fail.call_count == 1


def test_anonymize_user_action_container_not_ready(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    arrange: Given a mocked synapse container with an exec method that raises ExecError.
    act: run verify_user_email.
    assert: The correct exception is raised.
    """
    harness.begin_with_initial_hooks()
    event = unittest.mock.MagicMock(spec=ActionEvent)
    event.params = {"username": "username"}
    container = harness.model.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
    monkeypatch.setattr(container, "can_connect", MagicMock(return_value=False))
    harness.charm._on_anonymize_user_action(event)
    assert event.fail.call_count == 1
