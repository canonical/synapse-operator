# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for Synapse charm integration tests."""


import json

import pytest
import pytest_asyncio
from juju.model import Model
from pytest import Config
from pytest_operator.plugin import OpsTest


@pytest_asyncio.fixture(scope="module", name="server_name")
async def fixture_server_name() -> str:
    """Return a server_name."""
    return "my.synapse.local"


@pytest_asyncio.fixture(scope="module", name="model")
async def fixture_model(ops_test: OpsTest) -> Model:
    """Return the current testing juju model."""
    assert ops_test.model
    return ops_test.model


@pytest_asyncio.fixture(scope="module", name="synapse_charm")
async def fixture_synapse_charm(ops_test) -> str:
    """Build the charm"""
    charm = await ops_test.build_charm(".")
    return charm


@pytest_asyncio.fixture(scope="module", name="synapse_image")
def fixture_synapse_image(pytestconfig: Config):
    """Get value from parameter synapse-image."""
    synapse_image = pytestconfig.getoption("--synapse-image")
    assert synapse_image, "--synapse-image must be set"
    return synapse_image


@pytest_asyncio.fixture(scope="module", name="synapse_app")
async def fixture_synapse_app(
    synapse_image: str,
    model: Model,
    server_name: str,
    synapse_charm: str,
):
    """Build and deploy the Synapse charm."""
    app_name = "synapse-k8s"

    resources = {
        "synapse-image": synapse_image,
    }
    app = await model.deploy(
        synapse_charm,
        resources=resources,
        application_name=app_name,
        series="jammy",
        config={"server_name": server_name},
    )
    await model.wait_for_idle(raise_on_blocked=True)
    return app


@pytest_asyncio.fixture(scope="module", name="get_unit_ips")
async def fixture_get_unit_ips(ops_test: OpsTest):
    """Return an async function to retrieve unit ip addresses of a certain application."""

    async def get_unit_ips(application_name: str):
        """Retrieve unit ip addresses of a certain application.

        Args:
            application_name: application name.

        Returns:
            a list containing unit ip addresses.
        """
        _, status, _ = await ops_test.juju("status", "--format", "json")
        status = json.loads(status)
        units = status["applications"][application_name]["units"]
        return tuple(
            unit_status["address"]
            for _, unit_status in sorted(units.items(), key=lambda kv: int(kv[0].split("/")[-1]))
        )

    return get_unit_ips


@pytest.fixture(scope="module", name="external_hostname")
def external_hostname_fixture() -> str:
    """Return the external hostname for ingress-related tests."""
    return "juju.test"


@pytest.fixture(scope="module", name="traefik_app_name")
def traefik_app_name_fixture() -> str:
    """Return the name of the traefix application deployed for tests."""
    return "traefik-k8s"


@pytest_asyncio.fixture(scope="module", name="traefik_app")
async def fixture_traefik_app(
    model: Model,
    synapse_app,  # pylint: disable=unused-argument
    traefik_app_name: str,
    external_hostname: str,
):
    """Deploy traefik."""
    app = await model.deploy(
        "traefik-k8s",
        application_name=traefik_app_name,
        trust=True,
        config={
            "external_hostname": external_hostname,
            "routing_mode": "subdomain",
        },
    )
    await model.wait_for_idle(raise_on_blocked=True)

    return app
