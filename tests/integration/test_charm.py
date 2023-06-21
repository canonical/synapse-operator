#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for Synapse charm."""
import logging
import typing

import requests
from juju.application import Application
from juju.model import Model
from ops.model import ActiveStatus
from pytest_operator.plugin import OpsTest

from constants import SYNAPSE_PORT

# caused by pytest fixtures
# pylint: disable=too-many-arguments

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
        response = requests.get(f"http://{unit_ip}:{SYNAPSE_PORT}/_matrix/static/", timeout=5)
        assert response.status_code == 200
        assert "Welcome to the Matrix" in response.text


async def test_with_ingress(
    ops_test: OpsTest,
    model: Model,
    synapse_app: Application,
    traefik_app,  # pylint: disable=unused-argument
    traefik_app_name: str,
    external_hostname: str,
    get_unit_ips: typing.Callable[[str], typing.Awaitable[tuple[str, ...]]],
):
    """
    arrange: build and deploy the Synapse charm, and deploy the Traefik.
    act: relate the Traefik charm with the Synapse charm.
    assert: requesting the charm through Traefik should return a correct response.
    """
    await model.add_relation(synapse_app.name, traefik_app_name)
    # mypy doesn't see that ActiveStatus has a name
    await model.wait_for_idle(status=ActiveStatus.name)  # type: ignore

    traefik_ip = (await get_unit_ips(traefik_app_name))[0]
    response = requests.get(
        f"http://{traefik_ip}/_matrix/static/",
        headers={"Host": f"{ops_test.model_name}-{synapse_app.name}.{external_hostname}"},
        timeout=5,
    )
    assert response.status_code == 200
    assert "Welcome to the Matrix" in response.text
