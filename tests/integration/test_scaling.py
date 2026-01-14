#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Core integration tests for Synapse charm."""

import logging
import typing

import pytest_asyncio
import requests
from juju.application import Application
from juju.model import Model
from ops.model import ActiveStatus, BlockedStatus
from pytest import Config
from pytest_operator.plugin import OpsTest

from tests.integration.dependencies import REDIS

from .conftest import SERVER_NAME

# pylint: disable=too-many-positional-arguments,duplicate-code, too-many-arguments

SYNAPSE_SCALING_APP_NAME = "synapse-scaling"
REDIS_APP_NAME = "redis"
# mypy has trouble to inferred types for variables that are initialized in subclasses.
ACTIVE_STATUS_NAME = typing.cast(str, ActiveStatus.name)  # type: ignore

logger = logging.getLogger(__name__)


@pytest_asyncio.fixture(scope="module", name="synapse_app_scaling")
async def synapse_app_scaling_fixture(
    ops_test: OpsTest,
    synapse_image: str,
    model: Model,
    synapse_charm: str,
    postgresql_app: Application,
    pytestconfig: Config,
    get_unit_ips: typing.Callable[[str], typing.Awaitable[tuple[str, ...]]],
):
    """Build and deploy the Synapse charm"""
    use_existing = pytestconfig.getoption("--use-existing", default=False)
    if not use_existing and SYNAPSE_SCALING_APP_NAME not in model.applications:
        resources = {
            "synapse-image": synapse_image,
        }
        async with ops_test.fast_forward():
            app = await model.deploy(
                f"./{synapse_charm}",
                resources=resources,
                application_name=SYNAPSE_SCALING_APP_NAME,
                config={"server_name": SERVER_NAME},
            )
            await model.wait_for_idle(
                apps=[SYNAPSE_SCALING_APP_NAME],
                status=typing.cast(str, BlockedStatus.name),
                idle_period=5,
            )
            synapse_ip = (await get_unit_ips(app.name))[0]
            await app.set_config({"public_baseurl": f"http://{synapse_ip}:8080"})
            await model.relate(f"{SYNAPSE_SCALING_APP_NAME}:database", f"{postgresql_app.name}")
            await model.relate(
                f"{SYNAPSE_SCALING_APP_NAME}:mas-database",
                f"{postgresql_app.name}:database",
            )
            await model.wait_for_idle(
                apps=[SYNAPSE_SCALING_APP_NAME, postgresql_app.name],
                status=ACTIVE_STATUS_NAME,
                idle_period=5,
                raise_on_error=False,
            )
    app = model.applications.get(SYNAPSE_SCALING_APP_NAME)
    return app


@pytest_asyncio.fixture(scope="module", name="redis_app")
async def redis_fixture(
    ops_test: OpsTest,
    model: Model,
    synapse_app_scaling,
):
    """Deploy redis."""
    async with ops_test.fast_forward():
        app = await model.deploy(
            REDIS.charm_name,
            application_name=REDIS_APP_NAME,
            channel=REDIS.channel,
            revision=REDIS.revision,
        )
        await model.add_relation(f"{app.name}:redis", synapse_app_scaling.name)
        await model.wait_for_idle(status=ACTIVE_STATUS_NAME, idle_period=10)
    yield app
    await model.remove_application(app.name)
    await model.block_until(lambda: app.name not in model.applications, timeout=60)


async def test_synapse_scaling_nginx_configured(
    ops_test: OpsTest, model: Model, synapse_app_scaling: Application, redis_app: Application
):
    """
    arrange: integrate Synapse with Redis and scale 1 unit.
    act:  get the second unit IP address and request via ports 8080 and 8008.
    assert: 8080 should work because goes to the main unit and 8008 should fail.
    """
    await model.wait_for_idle(
        idle_period=15,
        apps=[synapse_app_scaling.name, redis_app.name],
        status=ACTIVE_STATUS_NAME,
    )
    await synapse_app_scaling.scale(2)
    await model.wait_for_idle(
        idle_period=15,
        apps=[synapse_app_scaling.name, redis_app.name],
        status=ACTIVE_STATUS_NAME,
    )
    assert ops_test.model
    status = await ops_test.model.get_status()
    application = typing.cast(Application, status.applications[synapse_app_scaling.name])
    unit = list(application.units)[1]
    address = status["applications"][synapse_app_scaling.name]["units"][unit]["address"]

    response_worker = requests.get(
        f"http://{address}:8008/", headers={"Host": synapse_app_scaling.name}, timeout=5
    )
    response_nginx = requests.get(
        f"http://{address}:8080/", headers={"Host": synapse_app_scaling.name}, timeout=5
    )

    # Returns 404 because a worker can't handle the / endpoint.
    assert response_worker.status_code == 404
    assert response_nginx.status_code == 200


async def test_synapse_scaling_down(
    ops_test: OpsTest, model: Model, synapse_app_scaling: Application, redis_app: Application
):
    """
    arrange: scale Synapse to two units and check if all units are working.
    act:  Scale the application down to 1 unit.
    assert: the Synapse application (remaining unit) should return a correct response.
    """
    await model.wait_for_idle(
        idle_period=15,
        apps=[synapse_app_scaling.name, redis_app.name],
        status=ACTIVE_STATUS_NAME,
    )
    await synapse_app_scaling.scale(2)
    await model.wait_for_idle(
        idle_period=15,
        apps=[synapse_app_scaling.name, redis_app.name],
        status=ACTIVE_STATUS_NAME,
    )
    assert ops_test.model
    status = await ops_test.model.get_status()
    application = typing.cast(Application, status.applications[synapse_app_scaling.name])
    for unit in list(application.units):
        address = status["applications"][synapse_app_scaling.name]["units"][unit]["address"]
        response_worker = requests.get(
            f"http://{address}:8080/", headers={"Host": synapse_app_scaling.name}, timeout=5
        )
        assert response_worker.status_code == 200

    await synapse_app_scaling.scale(1)

    await model.wait_for_idle(
        idle_period=15,
        apps=[synapse_app_scaling.name, redis_app.name],
        status=ACTIVE_STATUS_NAME,
    )
    assert ops_test.model
    status = await ops_test.model.get_status()
    application = typing.cast(Application, status.applications[synapse_app_scaling.name])
    for unit in list(application.units):
        address = status["applications"][synapse_app_scaling.name]["units"][unit]["address"]
        response_worker = requests.get(
            f"http://{address}:8080/", headers={"Host": synapse_app_scaling.name}, timeout=5
        )
        assert response_worker.status_code == 200
