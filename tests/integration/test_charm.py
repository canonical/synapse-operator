#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Core integration tests for Synapse charm."""
import logging
import typing

import pytest
import requests
from juju.action import Action
from juju.application import Application
from juju.errors import JujuUnitError
from juju.model import Model
from juju.unit import Unit
from ops.model import ActiveStatus

import synapse

# Application name constants
NGINX_INTEGRATOR_APP_NAME = "nginx-ingress-integrator"
SYNAPSE_APP_NAME = "synapse"

# mypy has trouble to inferred types for variables that are initialized in subclasses.
ACTIVE_STATUS_NAME = typing.cast(str, ActiveStatus.name)  # type: ignore

logger = logging.getLogger(__name__)


@pytest.mark.abort_on_fail
async def test_synapse_is_up(
    synapse_app: Application,
    get_unit_ips: typing.Callable[[str], typing.Awaitable[tuple[str, ...]]],
):
    """
    arrange: build and deploy the Synapse charm.
    act: send a request to the Synapse application managed by the Synapse charm.
    assert: the Synapse application should return a correct response.
    """
    charm_config = await synapse_app.get_config()
    for unit_ip in await get_unit_ips(synapse_app.name):
        response = requests.get(
            f"http://{unit_ip}:{synapse.SYNAPSE_NGINX_PORT}/_matrix/static/", timeout=5
        )
        assert response.status_code == 200
        assert "Welcome to the Matrix" in response.text

        response = requests.get(f"http://{unit_ip}:{synapse.SYNAPSE_NGINX_PORT}/auth/", timeout=5)
        assert response.status_code == 200
        assert "Matrix Authentication Service" in response.text

        response = requests.get(
            (
                f"http://{unit_ip}:{synapse.SYNAPSE_NGINX_PORT}"
                "/auth/.well-known/openid-configuration"
            ),
            timeout=5,
        )
        assert response.status_code == 200
        openid_configuration = response.json()
        assert (
            openid_configuration.get("issuer")
            == f"{charm_config['public_baseurl'].get('value')}/auth/"
        )


async def test_synapse_scale_blocked(synapse_app: Application):
    """
    arrange: build and deploy the Synapse charm.
    act: scale Synapse.
    assert: the Synapse application is blocked since there is no Redis integration.
    """
    await synapse_app.scale(2)

    with pytest.raises(JujuUnitError):
        await synapse_app.model.wait_for_idle(
            idle_period=30, timeout=120, apps=[synapse_app.name], raise_on_blocked=True
        )

    await synapse_app.scale(1)

    await synapse_app.model.wait_for_idle(
        idle_period=30, timeout=120, apps=[synapse_app.name], status="active"
    )


@pytest.mark.usefixtures("synapse_app")
async def test_nginx_route_integration(
    model: Model,
    nginx_integrator_app: Application,
):
    """
    arrange: build and deploy the Synapse charm, and deploy the nginx-integrator.
    act: relate the nginx-integrator charm with the Synapse charm.
    assert: requesting the charm through nginx-integrator should return a correct response.
    """
    await model.add_relation(
        f"{SYNAPSE_APP_NAME}:nginx-route", f"{NGINX_INTEGRATOR_APP_NAME}:nginx-route"
    )
    await nginx_integrator_app.set_config({"service-hostname": SYNAPSE_APP_NAME})
    await model.wait_for_idle(idle_period=30, status=ACTIVE_STATUS_NAME)

    response = requests.get(
        "http://127.0.0.1/_matrix/static/", headers={"Host": SYNAPSE_APP_NAME}, timeout=5
    )
    assert response.status_code == 200
    assert "Welcome to the Matrix" in response.text


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
