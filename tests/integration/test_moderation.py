#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Core integration tests for Synapse charm."""
import typing

import requests
from juju.action import Action
from juju.application import Application
from juju.model import Model
from juju.unit import Unit


async def test_anonymize_user(synapse_app: Application) -> None:
    """
    arrange: build and deploy the Synapse charm, create an user, get the access token and assert
        that the user is not an admin.
    act:  run action to anonymize user.
    assert: the Synapse application is active and the API request returns as expected.
    """
    operator_username = "operator-new"
    synapse_unit: Unit = next(iter(synapse_app.units))
    action_register_user: Action = await synapse_unit.run_action(
        "register-user", username=operator_username, admin=False
    )
    await action_register_user.wait()
    assert action_register_user.status == "completed"

    action_anonymize: Action = await synapse_unit.run_action(
        "anonymize-user", username=operator_username
    )
    await action_anonymize.wait()
    assert action_anonymize.status == "completed"


async def test_moderation(
    model: Model,
    synapse_app: Application,
    get_unit_ips: typing.Callable[[str], typing.Awaitable[tuple[str, ...]]],
):
    """
    arrange: deploy the charm, create user and moderation room and create the
        moderation secret.
    act: set moderation_access_token_secret_id
    assert: the Draupnir health endpoint should return OK.
    """
    # create user
    synapse_unit: Unit = next(iter(synapse_app.units))
    register_user_action: Action = await synapse_unit.run_action(
        "register-user", username="moderator", admin=True
    )
    await register_user_action.wait()
    assert register_user_action.status == "completed"
    assert register_user_action.results["user-password"]
    password = register_user_action.results["user-password"]
    # get token
    synapse_ip = (await get_unit_ips(synapse_app.name))[0]
    url = f"http://{synapse_ip}:8080/_matrix/client/r0/login"
    headers = {"Content-Type": "application/json"}
    data = {
        "type": "m.login.password",
        "identifier": {"type": "m.id.user", "user": "moderator"},
        "password": f"{password}",
    }
    response = requests.post(url, json=data, headers=headers, timeout=10)
    assert response.status_code == 200
    access_token = response.json().get("access_token")
    assert access_token
    # create room
    url = f"http://{synapse_ip}:8080/_matrix/client/v3/createRoom"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    data = {"room_alias_name": "moderators", "name": "moderators", "visibility": "private"}
    response = requests.post(url, json=data, headers=headers, timeout=10)
    assert response.status_code == 200
    room_id = response.json().get("room_id")
    assert room_id
    # create secret
    # refers to juju secret name, not hardcoded password.
    secret = await model.add_secret(
        "moderation", data_args=[f"matrix-access-token={access_token}"]
    )
    secret_id = secret.split(":")[-1]
    await model.grant_secret("moderation", synapse_app.name)

    # change synapse configuration
    await synapse_app.set_config({"moderation_access_token_secret_id": secret_id})
    await synapse_app.model.wait_for_idle(
        idle_period=30, timeout=120, apps=[synapse_app.name], status="active"
    )

    # verify draupnir health endpoint
    response = requests.get(f"http://{synapse_ip}:7777/", timeout=5)
    assert response.status_code == 200
    assert "health code: 200" in response.text
