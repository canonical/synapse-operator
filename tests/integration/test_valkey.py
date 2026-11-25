#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for Synapse charm integrated with Valkey.

The tests run in order on one deployment, and move it from Redis to Valkey and back the way an
operator would. After every step, all the Matrix data created at the start must still be there
on every unit, and the units must still deliver new messages to each other.
"""

import asyncio
import logging
import typing

import kubernetes
import pytest
import pytest_asyncio
import yaml
from juju.application import Application
from juju.model import Model
from kubernetes.stream import stream
from ops.model import ActiveStatus, BlockedStatus
from pytest_operator.plugin import OpsTest

from tests.integration.matrix_data import MatrixData

# mypy has trouble to inferred types for variables that are initialized in subclasses.
ACTIVE_STATUS_NAME = typing.cast(str, ActiveStatus.name)  # type: ignore
BLOCKED_STATUS_NAME = typing.cast(str, BlockedStatus.name)  # type: ignore
VALKEY_APP_NAME = "valkey"
VALKEY_ENDPOINT = f"{VALKEY_APP_NAME}:valkey-client"
UNITS = 2

logger = logging.getLogger(__name__)


def _exec(namespace: str, pod_name: str, command: list[str]) -> str:
    """Run a command in the Synapse container of a pod.

    Args:
        namespace: the pod's namespace, which is the model name.
        pod_name: the pod name.
        command: the command and its arguments.

    Returns:
        The command's output.
    """
    return stream(
        kubernetes.client.CoreV1Api().connect_get_namespaced_pod_exec,
        pod_name,
        namespace,
        container="synapse",
        command=command,
        stderr=False,
        stdin=False,
        stdout=True,
        tty=False,
    )


def _pod_ip(pod: kubernetes.client.V1Pod) -> typing.Optional[str]:
    """Get the IP of a pod.

    Args:
        pod: the pod, as the Kubernetes API returned it.

    Returns:
        The pod's IP, or None if it doesn't have one yet.
    """
    return pod.status.pod_ip if pod.status else None


def _pod_uid(pod: kubernetes.client.V1Pod) -> typing.Optional[str]:
    """Get the UID of a pod, which changes when the pod is replaced.

    Args:
        pod: the pod, as the Kubernetes API returned it.

    Returns:
        The pod's UID, or None if the API returned no metadata.
    """
    return pod.metadata.uid if pod.metadata else None


def _pod_ips(namespace: str, app_name: str, units: int) -> list[str]:
    """Get the current IP of every pod of an application.

    Args:
        namespace: the pods' namespace, which is the model name.
        app_name: the application name.
        units: the number of units.

    Returns:
        The IP of each pod, in unit order.
    """
    api = kubernetes.client.CoreV1Api()
    ips = []
    for number in range(units):
        ip = _pod_ip(api.read_namespaced_pod(f"{app_name}-{number}", namespace))
        assert ip, f"{app_name}-{number} has no IP"
        ips.append(ip)
    return ips


def _pod_uids(namespace: str, app_name: str, units: int) -> dict[str, typing.Optional[str]]:
    """Get the UID of every pod of an application.

    Args:
        namespace: the pods' namespace, which is the model name.
        app_name: the application name.
        units: the number of units.

    Returns:
        The UID of each pod, by pod name.
    """
    api = kubernetes.client.CoreV1Api()
    pod_names = [f"{app_name}-{number}" for number in range(units)]
    return {name: _pod_uid(api.read_namespaced_pod(name, namespace)) for name in pod_names}


def _synapse_config(namespace: str, app_name: str, units: int) -> list[dict]:
    """Get the Synapse configuration of every unit.

    Args:
        namespace: the pods' namespace, which is the model name.
        app_name: the application name.
        units: the number of units.

    Returns:
        The configuration of each unit, in unit order.
    """
    return [
        yaml.safe_load(_exec(namespace, f"{app_name}-{number}", ["cat", "/data/homeserver.yaml"]))
        for number in range(units)
    ]


def _cache_config(namespace: str, app_name: str, units: int) -> list[dict]:
    """Get the redis section of the Synapse configuration of every unit.

    Synapse uses this section for Valkey too.

    Args:
        namespace: the pods' namespace, which is the model name.
        app_name: the application name.
        units: the number of units.

    Returns:
        The redis section of each unit, in unit order.
    """
    return [config["redis"] for config in _synapse_config(namespace, app_name, units)]


def _synapse_started(namespace: str, app_name: str, units: int) -> list[str]:
    """Get when Pebble started the Synapse service of every unit.

    Args:
        namespace: the pods' namespace, which is the model name.
        app_name: the application name.
        units: the number of units.

    Returns:
        The start time of each unit's Synapse service, in unit order.
    """
    return [
        _exec(
            namespace,
            f"{app_name}-{number}",
            ["/charm/bin/pebble", "services", "synapse", "--abs-time"],
        )
        .splitlines()[-1]
        .split()[3]
        for number in range(units)
    ]


async def _wait_for_new_pods(namespace: str, old_uids: dict[str, typing.Optional[str]]) -> None:
    """Wait until Kubernetes has replaced every given pod with one that has an IP.

    Args:
        namespace: the pods' namespace, which is the model name.
        old_uids: the UID of each pod before it was replaced, by pod name.

    Raises:
        AssertionError: if a pod wasn't replaced within 15 minutes.
    """
    api = kubernetes.client.CoreV1Api()
    waiting = list(old_uids)
    for _ in range(90):
        waiting = []
        for pod_name, old_uid in old_uids.items():
            pods = api.list_namespaced_pod(namespace, field_selector=f"metadata.name={pod_name}")
            if not (pods.items and _pod_uid(pods.items[0]) != old_uid and _pod_ip(pods.items[0])):
                waiting.append(pod_name)
        if not waiting:
            return
        await asyncio.sleep(10)
    raise AssertionError(f"not replaced by a pod with an IP: {', '.join(waiting)}")


async def _replace_pod(namespace: str, pod_name: str) -> None:
    """Delete a pod and wait until Kubernetes has replaced it with one that has an IP.

    Args:
        namespace: the pod's namespace, which is the model name.
        pod_name: the pod name.
    """
    api = kubernetes.client.CoreV1Api()
    old_uid = _pod_uid(api.read_namespaced_pod(pod_name, namespace))
    api.delete_namespaced_pod(name=pod_name, namespace=namespace)
    await _wait_for_new_pods(namespace, {pod_name: old_uid})


async def _wait_for_synapse(model: Model, synapse_app: Application, units: int = UNITS) -> None:
    """Wait until every Synapse unit is active and idle.

    Args:
        model: the Juju model.
        synapse_app: the Synapse application.
        units: the number of units to wait for.
    """
    await model.wait_for_idle(
        apps=[synapse_app.name],
        status=ACTIVE_STATUS_NAME,
        idle_period=30,
        wait_for_exact_units=units,
        timeout=20 * 60,
    )


@pytest_asyncio.fixture(scope="module", name="valkey_app")
async def valkey_app_fixture(ops_test: OpsTest, model: Model) -> Application:
    """Deploy Valkey, without integrating it."""
    # The Juju CLI deploys it, because python-libjuju doesn't know Valkey's base, Ubuntu 26.04.
    # Valkey creates Kubernetes Services and labels its pods, which needs trust.
    return_code, _, stderr = await ops_test.juju(
        "deploy", "valkey", VALKEY_APP_NAME, "--channel", "9/stable", "--trust"
    )
    assert return_code == 0, stderr
    await model.block_until(lambda: VALKEY_APP_NAME in model.applications, timeout=5 * 60)
    await model.wait_for_idle(apps=[VALKEY_APP_NAME], status=ACTIVE_STATUS_NAME, timeout=20 * 60)
    return model.applications[VALKEY_APP_NAME]


@pytest_asyncio.fixture(scope="module", name="matrix_data")
async def matrix_data_fixture(
    model: Model,
    model_name: str,
    synapse_app: Application,
    redis_app: Application,  # pylint: disable=unused-argument
    valkey_app: Application,  # pylint: disable=unused-argument
) -> MatrixData:
    """Scale Synapse to two units on Redis and create the data that the tests check."""
    kubernetes.config.load_kube_config()
    await synapse_app.scale(UNITS)
    await _wait_for_synapse(model, synapse_app)
    data = await MatrixData.create(synapse_app, _pod_ips(model_name, synapse_app.name, UNITS))
    data.check(_pod_ips(model_name, synapse_app.name, UNITS))
    return data


async def test_switch_from_redis_to_valkey(
    model: Model, model_name: str, synapse_app: Application, matrix_data: MatrixData
):
    """
    arrange: two Synapse units integrated with Redis, with data, and Valkey deployed.
    act: integrate Synapse with Valkey, leaving the Redis integration in place.
    assert: every unit uses Valkey with a username and a password, says so in its status, and
        has all the data.
    """
    assert all(
        "username" not in section for section in _cache_config(model_name, synapse_app.name, UNITS)
    )

    await model.integrate(f"{synapse_app.name}:valkey", VALKEY_ENDPOINT)
    await model.wait_for_idle(apps=[VALKEY_APP_NAME], status=ACTIVE_STATUS_NAME)
    await _wait_for_synapse(model, synapse_app)

    for section in _cache_config(model_name, synapse_app.name, UNITS):
        assert section["host"].startswith(f"{VALKEY_APP_NAME}-primary"), section["host"]
        assert section["username"].startswith("relation-")
        assert section["password"]
    for unit in synapse_app.units:
        assert unit.workload_status_message == (
            "Using Valkey. The redis integration is no longer used"
        )
    matrix_data.check(_pod_ips(model_name, synapse_app.name, UNITS))


async def test_valkey_pod_replaced(
    model: Model, model_name: str, synapse_app: Application, matrix_data: MatrixData
):
    """
    arrange: two Synapse units that use Valkey.
    act: delete the Valkey pod, so that Kubernetes replaces it with one that has a new IP.
    assert: Synapse isn't reconfigured or restarted, reconnects by itself, and has all the data.
    """
    config_before = _cache_config(model_name, synapse_app.name, UNITS)
    started_before = _synapse_started(model_name, synapse_app.name, UNITS)

    await _replace_pod(model_name, f"{VALKEY_APP_NAME}-0")
    await model.wait_for_idle(
        apps=[VALKEY_APP_NAME], status=ACTIVE_STATUS_NAME, idle_period=30, timeout=20 * 60
    )

    matrix_data.check(_pod_ips(model_name, synapse_app.name, UNITS))
    assert _cache_config(model_name, synapse_app.name, UNITS) == config_before
    assert _synapse_started(model_name, synapse_app.name, UNITS) == started_before


@pytest.mark.parametrize("unit_number", [1, 0], ids=["worker", "main"])
async def test_synapse_pod_replaced(
    unit_number: int,
    model: Model,
    model_name: str,
    synapse_app: Application,
    matrix_data: MatrixData,
):
    """
    arrange: two Synapse units that use Valkey.
    act: delete one Synapse pod, so that Kubernetes replaces it with one that has a new IP.
    assert: every unit keeps the same Valkey host, user and password, and has all the data.
    """
    config_before = _cache_config(model_name, synapse_app.name, UNITS)
    for section in config_before:
        assert section["host"].startswith(f"{VALKEY_APP_NAME}-primary"), section["host"]

    await _replace_pod(model_name, f"{synapse_app.name}-{unit_number}")
    await _wait_for_synapse(model, synapse_app)

    # The leader asks Valkey for the user. A new request would get new credentials and
    # restart every unit, so the same user must still be in use.
    assert _cache_config(model_name, synapse_app.name, UNITS) == config_before
    matrix_data.check(_pod_ips(model_name, synapse_app.name, UNITS))


async def test_synapse_scaling_with_valkey(
    model: Model, model_name: str, synapse_app: Application, matrix_data: MatrixData
):
    """
    arrange: two Synapse units that use Valkey.
    act: scale to three units, then back to two.
    assert: after each change, every unit, the new one included, uses the same Valkey host, user
        and password, and has all the data.
    """
    config_before = _cache_config(model_name, synapse_app.name, UNITS)

    await synapse_app.scale(UNITS + 1)
    await _wait_for_synapse(model, synapse_app, UNITS + 1)

    assert _cache_config(model_name, synapse_app.name, UNITS + 1) == [config_before[0]] * (
        UNITS + 1
    )
    matrix_data.check(_pod_ips(model_name, synapse_app.name, UNITS + 1))

    await synapse_app.scale(UNITS)
    await _wait_for_synapse(model, synapse_app)

    assert _cache_config(model_name, synapse_app.name, UNITS) == config_before
    matrix_data.check(_pod_ips(model_name, synapse_app.name, UNITS))


async def test_rollback_from_valkey_to_redis(
    model: Model,
    model_name: str,
    synapse_app: Application,
    redis_app: Application,
    matrix_data: MatrixData,
):
    """
    arrange: two Synapse units that use Valkey, still integrated with Redis.
    act: remove the Valkey integration.
    assert: every unit uses Redis again, without a username or a password, and has all the data.
    """
    await synapse_app.remove_relation("valkey", VALKEY_ENDPOINT)
    await model.wait_for_idle(apps=[VALKEY_APP_NAME, redis_app.name], status=ACTIVE_STATUS_NAME)
    await _wait_for_synapse(model, synapse_app)

    for section in _cache_config(model_name, synapse_app.name, UNITS):
        assert not section["host"].startswith(VALKEY_APP_NAME), section["host"]
        assert "username" not in section and "password" not in section
    for unit in synapse_app.units:
        assert unit.workload_status_message == ""
    matrix_data.check(_pod_ips(model_name, synapse_app.name, UNITS))


async def test_remove_redis_while_using_valkey(
    model: Model,
    model_name: str,
    synapse_app: Application,
    redis_app: Application,
    matrix_data: MatrixData,
):
    """
    arrange: two Synapse units that use Valkey, still integrated with Redis.
    act: remove the Redis integration and then the Redis application.
    assert: every unit keeps the same Valkey configuration and has all the data.
    """
    await model.integrate(f"{synapse_app.name}:valkey", VALKEY_ENDPOINT)
    await model.wait_for_idle(apps=[VALKEY_APP_NAME], status=ACTIVE_STATUS_NAME)
    await _wait_for_synapse(model, synapse_app)
    config_before = _cache_config(model_name, synapse_app.name, UNITS)
    assert all(section["username"].startswith("relation-") for section in config_before)

    await synapse_app.remove_relation("redis", f"{redis_app.name}:redis")
    await _wait_for_synapse(model, synapse_app)
    await model.remove_application(redis_app.name, block_until_done=True)
    await _wait_for_synapse(model, synapse_app)

    assert _cache_config(model_name, synapse_app.name, UNITS) == config_before
    for unit in synapse_app.units:
        assert unit.workload_status_message == ""
    matrix_data.check(_pod_ips(model_name, synapse_app.name, UNITS))


async def test_remove_and_add_valkey_without_redis(
    model: Model, model_name: str, synapse_app: Application, matrix_data: MatrixData
):
    """
    arrange: two Synapse units that use Valkey, with no Redis integration.
    act: remove the Valkey integration, then add it again.
    assert: without it the units are blocked and keep their configuration. With it again, they
        use the new credentials, and all the data is there.
    """
    config_before = _cache_config(model_name, synapse_app.name, UNITS)

    await synapse_app.remove_relation("valkey", VALKEY_ENDPOINT)
    await model.wait_for_idle(
        apps=[synapse_app.name], status=BLOCKED_STATUS_NAME, idle_period=30, timeout=20 * 60
    )

    for unit in synapse_app.units:
        assert unit.workload_status_message == "Valkey or Redis integration is required."
    assert _cache_config(model_name, synapse_app.name, UNITS) == config_before

    await model.integrate(f"{synapse_app.name}:valkey", VALKEY_ENDPOINT)
    await model.wait_for_idle(apps=[VALKEY_APP_NAME], status=ACTIVE_STATUS_NAME)
    await _wait_for_synapse(model, synapse_app)

    config_after = _cache_config(model_name, synapse_app.name, UNITS)
    for before, after in zip(config_before, config_after):
        assert after["host"] == before["host"]
        assert after["username"] != before["username"]
    matrix_data.check(_pod_ips(model_name, synapse_app.name, UNITS))


async def test_config_change_keeps_valkey(
    model: Model, model_name: str, synapse_app: Application, matrix_data: MatrixData
):
    """
    arrange: two Synapse units that use Valkey, with no Redis integration.
    act: enable a charm option, then reset it.
    assert: each time, every unit's Synapse configuration follows the option, keeps the same
        Valkey host, user and password, and has all the data.
    """
    # Every reconcile renders the Synapse configuration again from the template, so the
    # Valkey settings must be added back each time.
    config_before = _cache_config(model_name, synapse_app.name, UNITS)

    await synapse_app.set_config({"block_non_admin_invites": "true"})
    await _wait_for_synapse(model, synapse_app)

    configs = _synapse_config(model_name, synapse_app.name, UNITS)
    assert [config["block_non_admin_invites"] for config in configs] == [True] * UNITS
    assert [config["redis"] for config in configs] == config_before
    matrix_data.check(_pod_ips(model_name, synapse_app.name, UNITS))

    await synapse_app.reset_config(["block_non_admin_invites"])
    await _wait_for_synapse(model, synapse_app)

    # The charm writes the option only when it is enabled, so the rebuilt file has none.
    configs = _synapse_config(model_name, synapse_app.name, UNITS)
    assert all("block_non_admin_invites" not in config for config in configs)
    assert [config["redis"] for config in configs] == config_before
    matrix_data.check(_pod_ips(model_name, synapse_app.name, UNITS))


# pylint: disable-next=too-many-arguments,too-many-positional-arguments
async def test_rolling_refresh_on_valkey(
    ops_test: OpsTest,
    model: Model,
    model_name: str,
    synapse_app: Application,
    synapse_charm: str,
    matrix_data: MatrixData,
):
    """
    arrange: two Synapse units that use Valkey, with no Redis integration.
    act: refresh Synapse to the same charm. Kubernetes replaces the pods one at a time, the
        main unit last, as it does in every refresh and every rollback.
    assert: every pod was replaced. Every unit keeps the same Valkey host, user and password,
        and has all the data, and the units deliver new messages to each other.
    """
    uids_before = _pod_uids(model_name, synapse_app.name, UNITS)
    config_before = _cache_config(model_name, synapse_app.name, UNITS)

    return_code, _, stderr = await ops_test.juju(
        "refresh", synapse_app.name, "--path", f"./{synapse_charm}"
    )
    assert return_code == 0, stderr
    await _wait_for_new_pods(model_name, uids_before)
    await _wait_for_synapse(model, synapse_app)

    assert _cache_config(model_name, synapse_app.name, UNITS) == config_before
    # Every unit is checked through its own NGINX, and the media file and the account data
    # come from the main unit. A unit whose NGINX still points at the main unit's old pod
    # fails here, although it reports active.
    matrix_data.check(_pod_ips(model_name, synapse_app.name, UNITS))
