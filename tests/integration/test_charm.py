#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Core integration tests for Synapse charm."""

import logging
import typing
from secrets import token_hex

import pytest
import requests
import yaml
from juju.action import Action
from juju.application import Application
from juju.errors import JujuUnitError
from juju.model import Model
from juju.unit import Unit
from ops.model import ActiveStatus

import synapse
from auth.mas import MAS_CONFIGURATION_PATH, MAS_EXECUTABLE_PATH

# mypy has trouble to inferred types for variables that are initialized in subclasses.
ACTIVE_STATUS_NAME = typing.cast(str, ActiveStatus.name)  # type: ignore

logger = logging.getLogger(__name__)


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


async def test_synapse_validate_configuration(synapse_app: Application):
    """
    arrange: build and deploy the Synapse charm.
    act: configure ip_range_whitelist with invalid IP and revert it.
    assert: the Synapse application should be blocked and then active.
    """
    await synapse_app.set_config({"ip_range_whitelist": "foo"})

    await synapse_app.model.wait_for_idle(
        idle_period=30, timeout=120, apps=[synapse_app.name], status="blocked"
    )

    await synapse_app.reset_config(["ip_range_whitelist"])

    await synapse_app.model.wait_for_idle(
        idle_period=30, timeout=120, apps=[synapse_app.name], status="active"
    )


async def test_synapse_configure_roomids(synapse_app: Application):
    """
    arrange: build and deploy the Synapse charm.
    act: configure  invite_checker_policy_rooms with valid room ids.
    assert: the Synapse application should be active after setting and
        reverting the config.
    """
    await synapse_app.set_config(
        {"invite_checker_policy_rooms": "a1b2c3d4e5f6g7h8i9j:foo.bar,w1x2y3z4A5B6C7D8E9F:xyz.org"}
    )

    await synapse_app.model.wait_for_idle(
        idle_period=30, timeout=120, apps=[synapse_app.name], status="active"
    )

    await synapse_app.reset_config(["invite_checker_policy_rooms"])

    await synapse_app.model.wait_for_idle(
        idle_period=30, timeout=120, apps=[synapse_app.name], status="active"
    )


async def test_enable_stats_exporter(
    synapse_app: Application,
    synapse_app_name: str,
    get_unit_ips: typing.Callable[[str], typing.Awaitable[tuple[str, ...]]],
) -> None:
    """
    arrange: Synapse is integrated with Postgresql.
    act:  request Synapse Stats Exporter URL.
    assert: Synapse Stats Exporter returns as expected.
    """
    await synapse_app.model.wait_for_idle(
        idle_period=30, timeout=120, apps=[synapse_app.name], status="active"
    )

    synapse_ip = (await get_unit_ips(synapse_app.name))[0]
    response = requests.get(
        f"http://{synapse_ip}:9877/", headers={"Host": synapse_app_name}, timeout=5
    )

    assert response.status_code == 200
    assert "synapse_total_users" in response.text


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


@pytest.mark.parametrize(
    "relation_name",
    [
        pytest.param("smtp-legacy"),
        pytest.param("smtp", marks=[pytest.mark.requires_secrets]),
    ],
)
async def test_synapse_enable_smtp(
    model: Model,
    synapse_app: Application,
    relation_name: str,
):
    """
    arrange: build and deploy the Synapse charm. Create an user and get the access token
        Deploy, configure and integrate with Synapse the smtp-integrator charm.
    act:  try to check if a given email address is not already associated.
    assert: the Synapse application is active and the error returned is the one expected.
    """
    if "smtp-integrator" in model.applications:
        await model.remove_application("smtp-integrator")
        await model.block_until(lambda: "smtp-integrator" not in model.applications, timeout=60)
        await model.wait_for_idle(status=ACTIVE_STATUS_NAME, idle_period=5)

    smtp_integrator_app = await model.deploy(
        "smtp-integrator",
        channel="latest/edge",
        config={
            "auth_type": "plain",
            "host": "127.0.0.1",
            "password": token_hex(16),
            "transport_security": "tls",
            "user": "username",
        },
    )
    await model.wait_for_idle(status=ACTIVE_STATUS_NAME)
    await model.add_relation(f"{smtp_integrator_app.name}:{relation_name}", synapse_app.name)
    await model.wait_for_idle(
        idle_period=180,
        apps=[synapse_app.name, smtp_integrator_app.name],
        status=ACTIVE_STATUS_NAME,
    )

    pebble_exec_cmd = "PEBBLE_SOCKET=/charm/containers/synapse/pebble.socket pebble exec --"
    dump_mas_config_cmd = (
        f"{pebble_exec_cmd} {MAS_EXECUTABLE_PATH} -c {MAS_CONFIGURATION_PATH} config dump"
    )
    unit: Unit = synapse_app.units[0]
    action = await unit.run(dump_mas_config_cmd)
    await action.wait()
    assert action.results["return-code"] == 0
    mas_config = yaml.safe_load(action.results["stdout"])
    assert mas_config["email"]["hostname"] == "127.0.0.1"


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


@pytest.mark.usefixtures("synapse_app")
async def test_nginx_route_integration(
    model: Model,
    nginx_integrator_app: Application,
    synapse_app_name: str,
    nginx_integrator_app_name: str,
):
    """
    arrange: build and deploy the Synapse charm, and deploy the nginx-integrator.
    act: relate the nginx-integrator charm with the Synapse charm.
    assert: requesting the charm through nginx-integrator should return a correct response.
    """
    await model.add_relation(
        f"{synapse_app_name}:nginx-route", f"{nginx_integrator_app_name}:nginx-route"
    )
    await nginx_integrator_app.set_config({"service-hostname": synapse_app_name})
    await model.wait_for_idle(idle_period=30, status=ACTIVE_STATUS_NAME)

    response = requests.get(
        "http://127.0.0.1/_matrix/static/", headers={"Host": synapse_app_name}, timeout=5
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
