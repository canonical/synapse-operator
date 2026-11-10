#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for Synapse charm integrated with Redis."""

import asyncio
import json
import logging
import typing

import kubernetes
import pytest
import requests
from juju.application import Application
from juju.model import Model
from ops.model import ActiveStatus
from pytest_operator.plugin import OpsTest

import synapse

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
    application = typing.cast(Application, status.applications[synapse_app.name])
    unit = list(application.units)[1]
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
    application = typing.cast(Application, status.applications[synapse_app.name])
    for unit in list(application.units):
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
    application = typing.cast(Application, status.applications[synapse_app.name])
    for unit in list(application.units):
        address = status["applications"][synapse_app.name]["units"][unit]["address"]
        response_worker = requests.get(
            f"http://{address}:8080/", headers={"Host": synapse_app.name}, timeout=5
        )
        assert response_worker.status_code == 200


@pytest.mark.redis
async def test_synapse_prometheus_configured(
    model: Model,
    synapse_app: Application,
    redis_app: Application,
    get_unit_ips: typing.Callable[[str], typing.Awaitable[tuple[str, ...]]],
):
    """
    arrange: integrate Synapse with Redis and scale 1 unit.
    act:  get all unit IPs and do a http request via port 9000.
    assert: collect metrics should work for all units.
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
    for unit_ip in await get_unit_ips(synapse_app.name):
        response = requests.get(f"http://{unit_ip}:{synapse.SYNAPSE_EXPORTER_PORT}/", timeout=5)
        assert response.status_code == 200
        assert "python_gc_objects_collected_total" in response.text


async def _get_unit_addresses(ops_test: OpsTest, app_name: str) -> dict[str, str]:
    """Get the address of each unit of an application.

    Args:
        ops_test: the pytest-operator helper.
        app_name: the application name.

    Returns:
        The address of each unit, by unit name.
    """
    _, stdout, _ = await ops_test.juju("status", "--format", "json")
    units = json.loads(stdout)["applications"][app_name]["units"]
    return {name: unit.get("address", "") for name, unit in units.items()}


async def _nginx_reaches_main_unit(address: str, host: str) -> bool:
    """Check that NGINX on a unit forwards a request for / to the main unit.

    Only the main unit serves /. While NGINX uses an old address, the request times out.

    Args:
        address: the unit's address.
        host: the Host header to send.

    Returns:
        True if the main unit answers within two minutes.
    """
    for _ in range(12):
        try:
            response = requests.get(f"http://{address}:8080/", headers={"Host": host}, timeout=5)
            if response.status_code == 200:
                return True
        except requests.RequestException as exc:
            logger.info("NGINX on %s did not reach the main unit yet: %s", address, exc)
        await asyncio.sleep(10)
    return False


@pytest.mark.redis
async def test_synapse_nginx_follows_replaced_main_unit(
    ops_test: OpsTest,
    model: Model,
    model_name: str,
    synapse_app: Application,
    redis_app: Application,
):
    """
    arrange: integrate Synapse with Redis and scale to two units.
    act: delete the main unit's pod, so that it comes back with a new address.
    assert: NGINX on every unit forwards requests to the main unit's new address.
    """
    apps = [synapse_app.name, redis_app.name]
    await model.wait_for_idle(idle_period=30, apps=apps, status=ACTIVE_STATUS_NAME)
    await synapse_app.scale(2)
    await model.wait_for_idle(idle_period=30, apps=apps, status=ACTIVE_STATUS_NAME)
    main_unit = f"{synapse_app.name}/0"
    old_address = (await _get_unit_addresses(ops_test, synapse_app.name))[main_unit]

    kubernetes.config.load_kube_config()
    kubernetes.client.CoreV1Api().delete_namespaced_pod(
        name=f"{synapse_app.name}-0", namespace=model_name
    )
    new_address = old_address
    for _ in range(60):
        await asyncio.sleep(10)
        new_address = (await _get_unit_addresses(ops_test, synapse_app.name)).get(main_unit, "")
        if new_address and new_address != old_address:
            break
    assert new_address != old_address, "the main unit kept its address, so this can't be checked"
    await model.wait_for_idle(idle_period=30, apps=apps, status=ACTIVE_STATUS_NAME)

    for unit, address in (await _get_unit_addresses(ops_test, synapse_app.name)).items():
        assert await _nginx_reaches_main_unit(
            address, synapse_app.name
        ), f"NGINX on {unit} doesn't reach the main unit at {new_address}"
