# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Register user action unit tests."""

# pylint: disable=protected-access

import typing
import unittest.mock

import ops
import pytest
from ops.charm import ActionEvent
from ops.testing import Harness

import synapse
from user import User


@pytest.mark.parametrize("harness", [0], indirect=True)
def test_register_user_action(
    harness_server_name_configured: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: run register-user action.
    assert: Synapse charm should reset the instance.
    """
    harness = harness_server_name_configured
    harness.set_leader(True)
    get_registration_mock = unittest.mock.Mock(return_value="shared_secret")
    monkeypatch.setattr("synapse.get_registration_shared_secret", get_registration_mock)
    register_user_mock = unittest.mock.MagicMock()
    monkeypatch.setattr("synapse.register_user", register_user_mock)
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


@pytest.mark.parametrize("harness", [0], indirect=True)
def test_register_user_registration_none(
    harness_server_name_configured: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: run register-user action.
    assert: event fails if registration shared secret is not found.
    """
    harness = harness_server_name_configured
    harness.set_leader(True)
    get_registration_mock = unittest.mock.Mock(return_value=None)
    monkeypatch.setattr("synapse.get_registration_shared_secret", get_registration_mock)
    register_user_mock = unittest.mock.MagicMock()
    monkeypatch.setattr("synapse.register_user", register_user_mock)
    user = "username"
    event = unittest.mock.MagicMock(spec=ActionEvent)

    def event_store_failure(failure_message: str) -> None:
        """Define a failure message for the event.

        Args:
            failure_message: failure message content to be defined.
        """
        event.fail_message = failure_message

    event.fail = event_store_failure
    event.params = {
        "username": user,
        "admin": "no",
    }
    # Calling to test the action since is not possible calling via harness
    harness.charm._on_register_user_action(event)
    assert "registration_shared_secret was not found" in event.fail_message
    assert isinstance(harness.model.unit.status, ops.ActiveStatus)


@pytest.mark.parametrize("harness", [0], indirect=True)
def test_register_user_action_api_error(
    harness_server_name_configured: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: run register-user action.
    assert: Synapse API fails.
    """
    harness = harness_server_name_configured
    harness.set_leader(True)
    get_registration_mock = unittest.mock.Mock(return_value="shared_secret")
    monkeypatch.setattr("synapse.get_registration_shared_secret", get_registration_mock)
    fail_message = "Some fail message"
    synapse_api_error = synapse.SynapseAPIError(fail_message)
    register_user_mock = unittest.mock.MagicMock(side_effect=synapse_api_error)
    monkeypatch.setattr("synapse.register_user", register_user_mock)
    user = "username"
    event = unittest.mock.MagicMock(spec=ActionEvent)

    def event_store_failure(failure_message: str) -> None:
        """Define a failure message for the event.

        Args:
            failure_message: failure message content to be defined.
        """
        event.fail_message = failure_message

    event.fail = event_store_failure
    event.params = {
        "username": user,
        "admin": "no",
    }
    # Calling to test the action since is not possible calling via harness
    harness.charm._on_register_user_action(event)
    assert fail_message in event.fail_message
    assert isinstance(harness.model.unit.status, ops.ActiveStatus)


def test_username_empty():
    """
    arrange: create a user.
    act: set username as empty.
    assert: ValueError is raised.
    """
    user_data: dict[str, typing.Any] = {
        "username": "",
        "admin": "yes",
    }
    with pytest.raises(ValueError, match="Username must not be empty"):
        _ = User(**user_data)


def test_invalid_admin():
    """
    arrange: create a user.
    act: set admin as invalid value.
    assert: ValueError is raised.
    """
    user_data: dict[str, typing.Any] = {
        "username": "username",
        "admin": "anything",
    }
    with pytest.raises(ValueError, match="Admin should be set as yes or no."):
        _ = User(**user_data)
