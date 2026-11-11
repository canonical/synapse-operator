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


def _get_pod(namespace: str, name: str) -> typing.Optional[kubernetes.client.V1Pod]:
    """Get a pod from Kubernetes.

    Args:
        namespace: the pod's namespace, which is the model name.
        name: the pod name.

    Returns:
        The pod, or None if there is no pod with that name.
    """
    pods = kubernetes.client.CoreV1Api().list_namespaced_pod(
        namespace, field_selector=f"metadata.name={name}"
    )
    return pods.items[0] if pods.items else None


async def _wait_for_replaced_pod(
    namespace: str, name: str, old_uid: str
) -> typing.Optional[kubernetes.client.V1Pod]:
    """Wait until Kubernetes replaces a deleted pod with one that has an IP.

    The new pod has the same name and a new UID. Its IP is usually new, but can be the old one.

    Args:
        namespace: the pod's namespace, which is the model name.
        name: the pod name.
        old_uid: the deleted pod's UID.

    Returns:
        The new pod, or None if no new pod has an IP within ten minutes.
    """
    for _ in range(60):
        pod = _get_pod(namespace, name)
        if pod and pod.metadata.uid != old_uid and pod.status.pod_ip:
            return pod
        await asyncio.sleep(10)
    return None


async def _get_juju_unit_address(
    ops_test: OpsTest, app_name: str, unit_name: str
) -> typing.Optional[str]:
    """Get the address that Juju reports for a unit.

    Args:
        ops_test: the pytest-operator helper.
        app_name: the application name.
        unit_name: the unit name.

    Returns:
        The address, or None if Juju doesn't report the unit or its address.
    """
    return_code, stdout, _ = await ops_test.juju("status", "--format", "json")
    if return_code != 0:
        return None
    units = json.loads(stdout).get("applications", {}).get(app_name, {}).get("units", {})
    return units.get(unit_name, {}).get("address") or None


async def _wait_for_juju_unit_address(
    ops_test: OpsTest, app_name: str, unit_name: str, address: str
) -> typing.Optional[str]:
    """Wait until Juju reports an address for a unit.

    The charm gets the unit's address from Juju, so it can only act on a new one once Juju has it.

    Args:
        ops_test: the pytest-operator helper.
        app_name: the application name.
        unit_name: the unit name.
        address: the address to wait for.

    Returns:
        The address that Juju reported last, or None if it reported none.
    """
    reported = None
    for _ in range(30):
        reported = await _get_juju_unit_address(ops_test, app_name, unit_name)
        if reported == address:
            break
        await asyncio.sleep(10)
    return reported


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
    act: delete the main unit's pod, so that Kubernetes replaces it.
    assert: NGINX on every unit forwards requests to the main unit's new IP.
    """
    await model.wait_for_idle(
        idle_period=30, apps=[synapse_app.name, redis_app.name], status=ACTIVE_STATUS_NAME
    )
    await synapse_app.scale(2)
    await model.wait_for_idle(
        idle_period=30, apps=[synapse_app.name], status=ACTIVE_STATUS_NAME, wait_for_exact_units=2
    )
    kubernetes.config.load_kube_config()
    pod_names = [f"{synapse_app.name}-{number}" for number in range(2)]
    old_main_pod = _get_pod(model_name, pod_names[0])
    assert old_main_pod, f"there's no pod {pod_names[0]}"

    kubernetes.client.CoreV1Api().delete_namespaced_pod(name=pod_names[0], namespace=model_name)
    main_pod = await _wait_for_replaced_pod(model_name, pod_names[0], old_main_pod.metadata.uid)

    assert main_pod, f"{pod_names[0]} wasn't replaced by a pod with an IP"
    main_ip = main_pod.status.pod_ip
    if main_ip == old_main_pod.status.pod_ip:
        # Not a failure: the address NGINX already has is still right.
        pytest.skip(f"the new {pod_names[0]} pod got the old IP {main_ip} back, nothing to follow")
    main_unit = f"{synapse_app.name}/0"
    juju_address = await _wait_for_juju_unit_address(
        ops_test, synapse_app.name, main_unit, main_ip
    )
    assert juju_address == main_ip, (
        f"Juju hasn't caught up with {main_unit}'s new pod at {main_ip}: "
        f"it reports {juju_address or 'no address for the unit'}"
    )
    await model.wait_for_idle(
        idle_period=30, apps=[synapse_app.name], status=ACTIVE_STATUS_NAME, wait_for_exact_units=2
    )
    for pod_name in pod_names:
        pod = _get_pod(model_name, pod_name)
        assert pod and pod.status.pod_ip, f"there's no pod {pod_name} with an IP"
        assert await _nginx_reaches_main_unit(
            pod.status.pod_ip, synapse_app.name
        ), f"NGINX on {pod_name} doesn't reach the main unit at {main_ip}"
