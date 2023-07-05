#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for Synapse charm."""
import logging
import typing

import requests
from juju.action import Action
from juju.application import Application
from juju.model import Model
from ops.model import ActiveStatus
import pytest
from pytest_operator.plugin import OpsTest

from constants import SYNAPSE_PORT

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
        response = requests.get(f"http://{unit_ip}:{SYNAPSE_PORT}/_matrix/static/", timeout=5)
        assert response.status_code == 200
        assert "Welcome to the Matrix" in response.text

@pytest.mark.usefixtures("traefik_app")
async def test_with_ingress(
    ops_test: OpsTest,
    model: Model,
    synapse_app: Application,
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
    await model.wait_for_idle(status=ACTIVE_STATUS_NAME)

    traefik_ip = (await get_unit_ips(traefik_app_name))[0]
    response = requests.get(
        f"http://{traefik_ip}/_matrix/static/",
        headers={"Host": f"{ops_test.model_name}-{synapse_app.name}.{external_hostname}"},
        timeout=5,
    )
    assert response.status_code == 200
    assert "Welcome to the Matrix" in response.text

@pytest.mark.usefixtures("synapse_app","nginx_integrator_app")
async def test_with_nginx_route(
    model: Model,
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
    await model.wait_for_idle(status=ACTIVE_STATUS_NAME)

    response = requests.get(
        "http://127.0.0.1/_matrix/static/", headers={"Host": synapse_app_name}, timeout=5
    )
    assert response.status_code == 200
    assert "Welcome to the Matrix" in response.text


async def test_server_name_changed(model: Model, another_synapse_app: Application):
    """
    arrange: build and deploy the Synapse charm.
    act: change server_name via juju config.
    assert: the Synapse application should prevent the change.
    """
    unit = model.applications[another_synapse_app.name].units[0]
    # Status string defined in Juju
    # https://github.com/juju/juju/blob/2.9/core/status/status.go#L150
    assert unit.workload_status == "blocked"
    assert "server_name modification is not allowed" in unit.workload_status_message


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
