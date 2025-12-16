#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Core integration tests for Synapse charm."""
import logging
import typing

import pytest
import requests
from juju.application import Application
from juju.model import Model
from ops.model import ActiveStatus

import synapse

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
