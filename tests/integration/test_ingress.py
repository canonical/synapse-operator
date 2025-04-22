# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for the Ingress integration of the Synapse charm."""
import ipaddress
import typing

import pytest
import pytest_asyncio
import requests
from juju.application import Application
from juju.client._definitions import FullStatus, UnitStatus
from juju.model import Model
from ops.model import ActiveStatus

# mypy has trouble to inferred types for variables that are initialized in subclasses.
ACTIVE_STATUS_NAME = typing.cast(str, ActiveStatus.name)  # type: ignore


@pytest_asyncio.fixture(scope="module", name="traefik_application_and_unit_ip")
async def traefik_application_fixture(model: Model):
    """The application related to Jenkins via ingress v2 relation."""
    traefik = await model.deploy(
        "traefik-k8s", channel="edge", trust=True, config={"routing_mode": "path"}
    )
    await model.wait_for_idle(
        status="active", apps=[traefik.name], timeout=20 * 60, idle_period=30, raise_on_error=False
    )
    status: FullStatus = await traefik.model.get_status([traefik.name])
    application = typing.cast(Application, status.applications[traefik.name])
    unit_status: UnitStatus = next(iter(traefik.units.values()))
    assert unit_status.public_address, "Invalid unit address"
    address = (
        unit_status.public_address
        if isinstance(unit_status.public_address, str)
        else unit_status.public_address.decode()
    )

    unit_ip = ipaddress.ip_address(address)
    return (traefik, unit_ip)


@pytest.mark.usefixtures("synapse_app")
async def test_nginx_route_integration(
    model: Model,
    traefik_application_and_unit_ip: tuple[
        Application, ipaddress.IPv4Address | ipaddress.IPv6Address
    ],
    synapse_app_name: str,
):
    """
    arrange: build and deploy the Synapse charm, and deploy the nginx-integrator.
    act: relate the nginx-integrator charm with the Synapse charm using the ingress integration.
    assert: requesting the charm through nginx-integrator should return a correct response.
    """
    traefik_application, traefik_ip = traefik_application_and_unit_ip
    await model.add_relation(f"{synapse_app_name}:ingress", f"{traefik_application}:ingress")
    await traefik_application.set_config({"external_hostname": synapse_app_name})
    await model.wait_for_idle(idle_period=30, status=ACTIVE_STATUS_NAME)

    synapse_url = (
        f"http://{traefik_ip}/_matrix/static/"
        if isinstance(traefik_ip, ipaddress.IPv4Address)
        else f"http://[{traefik_ip}]/_matrix/static/"
    )
    response = requests.get(synapse_url, headers={"Host": synapse_app_name}, timeout=5)
    assert response.status_code == 200
    assert "Welcome to the Matrix" in response.text
