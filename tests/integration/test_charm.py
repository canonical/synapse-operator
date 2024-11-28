#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Core integration tests for Synapse charm."""
import json
import logging
import re
import typing
from secrets import token_hex

import pytest
import requests
from juju.action import Action
from juju.application import Application
from juju.errors import JujuUnitError
from juju.model import Model
from juju.unit import Unit
from ops.model import ActiveStatus
from pytest_operator.plugin import OpsTest

import synapse
from tests.integration.helpers import create_moderators_room, get_access_token, register_user

# caused by pytest fixtures
# pylint: disable=too-many-arguments

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
    for unit_ip in await get_unit_ips(synapse_app.name):
        response = requests.get(
            f"http://{unit_ip}:{synapse.SYNAPSE_NGINX_PORT}/_matrix/static/", timeout=5
        )
        assert response.status_code == 200
        assert "Welcome to the Matrix" in response.text

    pebble_exec_cmd = "PEBBLE_SOCKET=/charm/containers/synapse/pebble.socket pebble exec --"
    mas_cli_check_cmd = f"{pebble_exec_cmd} mas-cli help"
    unit: Unit = synapse_app.units[0]
    action = await unit.run(mas_cli_check_cmd)
    await action.wait()
    assert action.results["return-code"] == 0, "Error running mas-cli."

    check_assets_cmd = """
        [ -d /mas/share/assets ] && \\
        [ -f /mas/share/policy.wasm ] && \\
        [ -d /mas/share/templates ] && \\
        [ -d /mas/share/translations ] && echo "ok!"
    """
    action = await unit.run("/bin/bash -c " f"'{pebble_exec_cmd} {check_assets_cmd}'")
    await action.wait()
    assert action.results["return-code"] == 0, "mas assets folder not found."
    assert "ok!" in action.results["stdout"]


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


@pytest.mark.asyncio
async def test_workload_version(
    ops_test: OpsTest,
    synapse_app: Application,
    get_unit_ips: typing.Callable[[str], typing.Awaitable[tuple[str, ...]]],
) -> None:
    """
    arrange: a deployed Synapse charm.
    act: get status from Juju.
    assert: the workload version is set and match the one given by Synapse API request.
    """
    await synapse_app.model.wait_for_idle(idle_period=30, apps=[synapse_app.name], status="active")
    _, status, _ = await ops_test.juju("status", "--format", "json")
    status = json.loads(status)
    juju_workload_version = status["applications"][synapse_app.name].get("version", "")
    assert juju_workload_version
    for unit_ip in await get_unit_ips(synapse_app.name):
        res = requests.get(
            f"http://{unit_ip}:{synapse.SYNAPSE_PORT}/_synapse/admin/v1/server_version", timeout=5
        )
        server_version = res.json()["server_version"]
        version_match = re.search(synapse.SYNAPSE_VERSION_REGEX, server_version)
        assert version_match
        assert version_match.group(1) == juju_workload_version


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
    get_unit_ips: typing.Callable[[str], typing.Awaitable[tuple[str, ...]]],
    access_token: str,
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
        idle_period=30,
        apps=[synapse_app.name, smtp_integrator_app.name],
        status=ACTIVE_STATUS_NAME,
    )

    synapse_ip = (await get_unit_ips(synapse_app.name))[0]
    authorization_token = f"Bearer {access_token}"
    headers = {"Authorization": authorization_token}
    sample_check = {
        "client_secret": "this_is_my_secret_string",
        "email": "example@example.com",
        "id_server": "id.matrix.org",
        "send_attempt": "1",
    }
    sess = requests.session()
    res = sess.post(
        f"http://{synapse_ip}:8080/_matrix/client/r0/register/email/requestToken",
        json=sample_check,
        headers=headers,
        timeout=5,
    )

    assert res.status_code == 500
    # If the configuration change fails, will return something like:
    # "Email-based registration has been disabled on this server".
    # The expected error confirms that the e-mail is configured but failed since
    # is not a real SMTP server.
    assert "error was encountered when sending the email" in res.text


async def test_promote_user_admin(
    synapse_app: Application,
    get_unit_ips: typing.Callable[[str], typing.Awaitable[tuple[str, ...]]],
) -> None:
    """
    arrange: build and deploy the Synapse charm, create an user, get the access token and assert
        that the user is not an admin.
    act:  run action to promote user to admin.
    assert: the Synapse application is active and the API request returns as expected.
    """
    operator_username = "operator"
    action_register_user: Action = await synapse_app.units[0].run_action(  # type: ignore
        "register-user", username=operator_username, admin=False
    )
    await action_register_user.wait()
    assert action_register_user.status == "completed"
    password = action_register_user.results["user-password"]
    synapse_ip = (await get_unit_ips(synapse_app.name))[0]
    sess = requests.session()
    res = sess.post(
        f"http://{synapse_ip}:8080/_matrix/client/r0/login",
        # same thing is done on fixture but we are creating a non-admin user here.
        json={  # pylint: disable=duplicate-code
            "identifier": {"type": "m.id.user", "user": operator_username},
            "password": password,
            "type": "m.login.password",
        },
        timeout=5,
    )
    res.raise_for_status()
    access_token = res.json()["access_token"]
    authorization_token = f"Bearer {access_token}"
    headers = {"Authorization": authorization_token}
    # List Accounts is a request that only admins can perform.
    res = sess.get(
        f"http://{synapse_ip}:8080/_synapse/admin/v2/users?from=0&limit=10&guests=false",
        headers=headers,
        timeout=5,
    )
    assert res.status_code == 403

    action_promote: Action = await synapse_app.units[0].run_action(  # type: ignore
        "promote-user-admin", username=operator_username
    )
    await action_promote.wait()
    assert action_promote.status == "completed"

    res = sess.get(
        f"http://{synapse_ip}:8080/_synapse/admin/v2/users?from=0&limit=10&guests=false",
        headers=headers,
        timeout=5,
    )
    assert res.status_code == 200


async def test_anonymize_user(
    synapse_app: Application,
    get_unit_ips: typing.Callable[[str], typing.Awaitable[tuple[str, ...]]],
) -> None:
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
    password = action_register_user.results["user-password"]
    synapse_ip = (await get_unit_ips(synapse_app.name))[0]
    with requests.session() as sess:
        res = sess.post(
            f"http://{synapse_ip}:8080/_matrix/client/r0/login",
            # same thing is done on fixture but we are creating a non-admin user here.
            json={  # pylint: disable=duplicate-code
                "identifier": {"type": "m.id.user", "user": operator_username},
                "password": password,
                "type": "m.login.password",
            },
            timeout=5,
        )
        res.raise_for_status()

    action_anonymize: Action = await synapse_unit.run_action(
        "anonymize-user", username=operator_username
    )
    await action_anonymize.wait()
    assert action_anonymize.status == "completed"

    with requests.session() as sess:
        res = sess.post(
            f"http://{synapse_ip}:8080/_matrix/client/r0/login",
            # same thing is done on fixture but we are creating a non-admin user here.
            json={  # pylint: disable=duplicate-code
                "identifier": {"type": "m.id.user", "user": operator_username},
                "password": password,
                "type": "m.login.password",
            },
            timeout=5,
        )
    assert res.status_code == 403


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


@pytest.mark.mjolnir
async def test_synapse_enable_mjolnir(
    ops_test: OpsTest,
    synapse_app: Application,
    access_token: str,
    get_unit_ips: typing.Callable[[str], typing.Awaitable[tuple[str, ...]]],
):
    """
    arrange: build and deploy the Synapse charm, create an user, get the access token,
        enable Mjolnir and create the management room.
    act: check Mjolnir health point.
    assert: the Synapse application is active and Mjolnir health point returns a correct response.
    """
    await synapse_app.set_config({"enable_mjolnir": "true"})
    await synapse_app.model.wait_for_idle(
        idle_period=30, timeout=120, apps=[synapse_app.name], status="blocked"
    )
    synapse_ip = (await get_unit_ips(synapse_app.name))[0]
    create_moderators_room(synapse_ip, access_token)
    async with ops_test.fast_forward():
        # using fast_forward otherwise would wait for model config update-status-hook-interval
        await synapse_app.model.wait_for_idle(
            idle_period=30, apps=[synapse_app.name], status="active"
        )

    res = requests.get(f"http://{synapse_ip}:{synapse.MJOLNIR_HEALTH_PORT}/healthz", timeout=5)

    assert res.status_code == 200


# pylint: disable=too-many-positional-arguments
@pytest.mark.mjolnir
async def test_synapse_with_mjolnir_from_refresh_is_up(
    ops_test: OpsTest,
    model: Model,
    synapse_charmhub_app: Application,
    get_unit_ips: typing.Callable[[str], typing.Awaitable[tuple[str, ...]]],
    synapse_charm: str,
    synapse_image: str,
):
    """
    arrange: build and deploy the Synapse charm from charmhub and enable Mjolnir.
    act: Refresh the charm with the local one.
    assert: Synapse and Mjolnir health points should return correct responses.
    """
    await synapse_charmhub_app.set_config({"enable_mjolnir": "true"})
    await model.wait_for_idle(apps=[synapse_charmhub_app.name], status="blocked")
    synapse_ip = (await get_unit_ips(synapse_charmhub_app.name))[0]
    user_username = token_hex(16)
    user_password = await register_user(synapse_charmhub_app, user_username)
    access_token = get_access_token(synapse_ip, user_username, user_password)
    create_moderators_room(synapse_ip, access_token)
    async with ops_test.fast_forward():
        await synapse_charmhub_app.model.wait_for_idle(
            idle_period=30, apps=[synapse_charmhub_app.name], status="active"
        )

    resources = {
        "synapse-image": synapse_image,
    }
    await synapse_charmhub_app.refresh(path=f"./{synapse_charm}", resources=resources)
    async with ops_test.fast_forward():
        await synapse_charmhub_app.model.wait_for_idle(
            idle_period=30, apps=[synapse_charmhub_app.name], status="active"
        )

    # Unit ip could change because it is a different pod.
    synapse_ip = (await get_unit_ips(synapse_charmhub_app.name))[0]
    response = requests.get(
        f"http://{synapse_ip}:{synapse.SYNAPSE_NGINX_PORT}/_matrix/static/", timeout=5
    )
    assert response.status_code == 200
    assert "Welcome to the Matrix" in response.text

    mjolnir_response = requests.get(
        f"http://{synapse_ip}:{synapse.MJOLNIR_HEALTH_PORT}/healthz", timeout=5
    )
    assert mjolnir_response.status_code == 200
