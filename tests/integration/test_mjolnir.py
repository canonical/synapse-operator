#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for Synapse charm refresh."""

import typing
from secrets import token_hex

import pytest
import requests
from juju.application import Application
from juju.model import Model
from pytest_operator.plugin import OpsTest

import synapse
from tests.integration.helpers import create_moderators_room, get_access_token, register_user

# caused by pytest fixtures
# pylint: disable=too-many-arguments

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

@pytest.mark.mjolnir
async def test_synapse_with_mjolnir_from_refresh_is_up(
    ops_test: OpsTest,
    model: Model,
    synapse_charmhub_app: Application,
    get_unit_ips: typing.Callable[[str], typing.Awaitable[tuple[str, ...]]],
    synapse_charm: str,
    synapse_image: str,
    synapse_nginx_image: str,
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
        "synapse-nginx-image": synapse_nginx_image,
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
