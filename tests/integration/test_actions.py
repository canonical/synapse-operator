#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for Synapse charm actions."""
import logging
import typing

import requests
from juju.action import Action
from juju.application import Application
from juju.model import Model
from ops.model import ActiveStatus

from constants import SYNAPSE_PORT

# caused by pytest fixtures
# pylint: disable=too-many-arguments

# mypy has trouble to inferred types for variables that are initialized in subclasses.
ACTIVE_STATUS_NAME = typing.cast(str, ActiveStatus.name)  # type: ignore

logger = logging.getLogger(__name__)


async def test_reset_instance_action(
    model: Model, another_synapse_app: Application, another_server_name: str
):
    """
    arrange: a deployed Synapse charm in a blocked state due to a server_name change.
    act: call the reset_instance action.
    assert: the old instance is deleted and the new one configured.
    """
    unit = model.applications[another_synapse_app.name].units[0]
    # Status string defined in Juju
    # https://github.com/juju/juju/blob/2.9/core/status/status.go#L150
    assert unit.workload_status == "blocked"
    assert "server_name modification is not allowed" in unit.workload_status_message
    action_reset_instance: Action = await another_synapse_app.units[0].run_action(  # type: ignore
        "reset-instance"
    )
    await action_reset_instance.wait()
    assert action_reset_instance.status == "completed"
    assert action_reset_instance.results["reset-instance"]
    assert unit.workload_status == "active"
    config = await model.applications[another_synapse_app.name].get_config()
    current_server_name = config.get("server_name", {}).get("value")
    assert current_server_name == another_server_name


async def test_register_user_action(
    model: Model,
    synapse_app: Application,
    get_unit_ips: typing.Callable[[str], typing.Awaitable[tuple[str, ...]]],
) -> None:
    """
    arrange: a deployed Synapse charm.
    act: call the register user action.
    assert: the user is registered and the login is successful.
    """
    await model.wait_for_idle(status=ACTIVE_STATUS_NAME)
    username = "operator"
    unit = model.applications[synapse_app.name].units[0]
    action_register_user: Action = await synapse_app.units[0].run_action(  # type: ignore
        "register-user", username=username, admin=True
    )
    await action_register_user.wait()
    assert action_register_user.status == "completed"
    assert action_register_user.results["register-user"]
    password = action_register_user.results["user-password"]
    assert password
    assert unit.workload_status == "active"
    data = {"type": "m.login.password", "user": username, "password": password}
    for unit_ip in await get_unit_ips(synapse_app.name):
        response = requests.post(
            f"http://{unit_ip}:{SYNAPSE_PORT}/_matrix/client/r0/login", json=data, timeout=5
        )
        assert response.status_code == 200
        assert response.json()["access_token"]
