#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for Synapse charm integrated with Redis."""
import logging
import typing

import pytest
import requests
from juju.application import Application
from juju.model import Model
from ops.model import ActiveStatus
from pytest_operator.plugin import OpsTest

# mypy has trouble to inferred types for variables that are initialized in subclasses.
ACTIVE_STATUS_NAME = typing.cast(str, ActiveStatus.name)  # type: ignore

logger = logging.getLogger(__name__)


@pytest.mark.redis
async def test_synapse_scaling_nginx_configured(
    ops_test: OpsTest, model: Model, synapse_app: Application, redis_app: Application
):
    """
    arrange: integrate Synapse with Redis and scale 1 unit.
    act:  get the second unit IP address and request via ports 8080 and 8008.
    assert: 8080 should work because goes to the main unit and 8008 should fail.
    """
    await model.wait_for_idle(
        idle_period=30,
        apps=[synapse_app.name, redis_app.name],
        status=ACTIVE_STATUS_NAME,
    )
    await synapse_app.scale(2)
    await model.wait_for_idle(
        idle_period=30,
        apps=[synapse_app.name, redis_app.name],
        status=ACTIVE_STATUS_NAME,
    )
    assert ops_test.model
    status = await ops_test.model.get_status()
    unit = list(status.applications[synapse_app.name].units)[1]
    address = status["applications"][synapse_app.name]["units"][unit]["address"]

    response_worker = requests.get(
        f"http://{address}:8008/", headers={"Host": synapse_app.name}, timeout=5
    )
    response_nginx = requests.get(
        f"http://{address}:8080/", headers={"Host": synapse_app.name}, timeout=5
    )

    # Returns 404 because a worker can't handle the / endpoint.
    assert response_worker.status_code == 404
    assert response_nginx.status_code == 200


@pytest.mark.redis
async def test_synapse_scaling_down(
    ops_test: OpsTest, model: Model, synapse_app: Application, redis_app: Application
):
    """
    arrange: scale Synapse to two units and check if all units are working.
    act:  Scale the application down to 1 unit.
    assert: the Synapse application (remaining unit) should return a correct response.
    """
    await model.wait_for_idle(
        idle_period=30,
        apps=[synapse_app.name, redis_app.name],
        status=ACTIVE_STATUS_NAME,
    )
    await synapse_app.scale(2)
    await model.wait_for_idle(
        idle_period=30,
        apps=[synapse_app.name, redis_app.name],
        status=ACTIVE_STATUS_NAME,
    )
    assert ops_test.model
    status = await ops_test.model.get_status()
    for unit in list(status.applications[synapse_app.name].units):
        address = status["applications"][synapse_app.name]["units"][unit]["address"]
        response_worker = requests.get(
            f"http://{address}:8080/", headers={"Host": synapse_app.name}, timeout=5
        )
        assert response_worker.status_code == 200

    await synapse_app.scale(1)

    await model.wait_for_idle(
        idle_period=30,
        apps=[synapse_app.name, redis_app.name],
        status=ACTIVE_STATUS_NAME,
    )
    assert ops_test.model
    status = await ops_test.model.get_status()
    for unit in list(status.applications[synapse_app.name].units):
        address = status["applications"][synapse_app.name]["units"][unit]["address"]
        response_worker = requests.get(
            f"http://{address}:8080/", headers={"Host": synapse_app.name}, timeout=5
        )
        assert response_worker.status_code == 200
