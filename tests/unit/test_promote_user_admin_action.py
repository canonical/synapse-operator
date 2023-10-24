# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Register user action unit tests."""

# Disabled to access _on_register_user_action
# pylint: disable=protected-access

import unittest.mock
from secrets import token_hex

import pytest
from ops.charm import ActionEvent
from ops.testing import Harness

import synapse
from charm import SynapseCharm


def test_promote_user_admin_action(harness: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: run promote-user-admin action.
    assert: event results are returned as expected.
    """
    harness.begin_with_initial_hooks()
    admin_access_token = token_hex(16)
    promote_user_admin_mock = unittest.mock.Mock()
    monkeypatch.setattr(
        SynapseCharm,
        "get_admin_access_token",
        unittest.mock.MagicMock(return_value=admin_access_token),
    )
    monkeypatch.setattr("synapse.promote_user_admin", promote_user_admin_mock)
    user = "username"
    event = unittest.mock.MagicMock(spec=ActionEvent)
    event.params = {
        "username": user,
    }

    harness.charm._on_promote_user_admin_action(event)

    assert event.set_results.call_count == 1
    event.set_results.assert_called_with({"promote-user-admin": True})
    promote_user_admin_mock.assert_called_with(
        user=unittest.mock.ANY, server=unittest.mock.ANY, admin_access_token=admin_access_token
    )


def test_promote_user_admin_api_error(harness: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: run promote-user-admin action.
    assert: event fails as expected.
    """
    harness.begin_with_initial_hooks()
    fail_message = "Some fail message"
    synapse_api_error = synapse.APIError(fail_message)
    promote_user_admin_mock = unittest.mock.MagicMock(side_effect=synapse_api_error)
    monkeypatch.setattr("synapse.promote_user_admin", promote_user_admin_mock)
    admin_access_token = token_hex(16)
    monkeypatch.setattr(
        SynapseCharm,
        "get_admin_access_token",
        unittest.mock.MagicMock(return_value=admin_access_token),
    )
    user = "username"
    event = unittest.mock.MagicMock(spec=ActionEvent)
    event.params = {
        "username": user,
    }

    def event_store_failure(failure_message: str) -> None:
        """Define a failure message for the event.

        Args:
            failure_message: failure message content to be defined.
        """
        event.fail_message = failure_message

    event.fail = event_store_failure
    event.params = {
        "username": user,
    }

    harness.charm._on_promote_user_admin_action(event)

    assert fail_message in event.fail_message


def test_promote_user_admin_container_down(harness: Harness) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be off.
    act: run promote-user-admin action.
    assert: event fails as expected.
    """
    harness.begin_with_initial_hooks()
    harness.set_can_connect(harness.model.unit.containers[synapse.SYNAPSE_CONTAINER_NAME], False)
    event = unittest.mock.Mock()

    harness.charm._on_promote_user_admin_action(event)

    assert event.set_results.call_count == 0
    assert event.fail.call_count == 1
    assert "Failed to connect to the container" == event.fail.call_args[0][0]


def test_promote_user_admin_action_no_token(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: run promote-user-admin action.
    assert: event fails as expected.
    """
    harness.begin_with_initial_hooks()
    promote_user_admin_mock = unittest.mock.Mock()
    monkeypatch.setattr(
        SynapseCharm,
        "get_admin_access_token",
        unittest.mock.MagicMock(return_value=None),
    )
    monkeypatch.setattr("synapse.promote_user_admin", promote_user_admin_mock)
    event = unittest.mock.Mock()

    harness.charm._on_promote_user_admin_action(event)

    assert event.set_results.call_count == 0
    assert event.fail.call_count == 1
    assert "Failed to get admin access token" == event.fail.call_args[0][0]
