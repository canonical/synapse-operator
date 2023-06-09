# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for Synapse charm integration tests."""


import json

import pytest
import pytest_asyncio
from juju.application import Application
from juju.model import Model
from pytest import Config
from pytest_operator.plugin import OpsTest


@pytest_asyncio.fixture(scope="module", name="server_name")
async def server_name_fixture() -> str:
    """Return a server_name."""
    return "my.synapse.local"


@pytest_asyncio.fixture(scope="module", name="another_server_name")
async def another_server_name_fixture() -> str:
    """Return a server_name."""
    return "another.synapse.local"


@pytest_asyncio.fixture(scope="module", name="model")
async def model_fixture(ops_test: OpsTest) -> Model:
    """Return the current testing juju model."""
    assert ops_test.model
    return ops_test.model


@pytest_asyncio.fixture(scope="module", name="synapse_charm")
async def synapse_charm_fixture(ops_test) -> str:
    """Build the charm"""
    charm = await ops_test.build_charm(".")
    return charm


@pytest_asyncio.fixture(scope="module", name="synapse_image")
def synapse_image_fixture(pytestconfig: Config):
    """Get value from parameter synapse-image."""
    synapse_image = pytestconfig.getoption("--synapse-image")
    assert synapse_image, "--synapse-image must be set"
    return synapse_image


@pytest_asyncio.fixture(scope="module", name="synapse_app_name")
def synapse_app_name_fixture() -> str:
    """Get Synapse application name."""
    return "synapse"


@pytest_asyncio.fixture(scope="module", name="synapse_app")
async def synapse_app_fixture(
    synapse_app_name: str,
    synapse_image: str,
    model: Model,
    server_name: str,
    synapse_charm: str,
):
    """Build and deploy the Synapse charm."""
    resources = {
        "synapse-image": synapse_image,
    }
    app = await model.deploy(
        synapse_charm,
        resources=resources,
        application_name=synapse_app_name,
        series="jammy",
        config={"server_name": server_name},
    )
    await model.wait_for_idle(raise_on_blocked=True)
    return app


@pytest_asyncio.fixture(scope="module", name="get_unit_ips")
async def get_unit_ips_fixture(ops_test: OpsTest):
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
async def traefik_app_fixture(
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


@pytest.fixture(scope="module", name="nginx_integrator_app_name")
def nginx_integrator_app_name_fixture() -> str:
    """Return the name of the nginx integrator application deployed for tests."""
    return "nginx-ingress-integrator"


@pytest_asyncio.fixture(scope="module", name="nginx_integrator_app")
async def nginx_integrator_app_fixture(
    model: Model,
    synapse_app,  # pylint: disable=unused-argument
    nginx_integrator_app_name: str,
):
    """Deploy nginx-ingress-integrator."""
    app = await model.deploy(
        "nginx-ingress-integrator",
        application_name=nginx_integrator_app_name,
        trust=True,
    )
    await model.wait_for_idle(raise_on_blocked=True)
    return app


@pytest_asyncio.fixture(scope="function", name="another_synapse_app")
async def another_synapse_app_fixture(
    model: Model, synapse_app: Application, server_name: str, another_server_name: str
):
    """Change server_name."""
    # First we guarantee that the first server_name is set
    # Then change it.
    await synapse_app.set_config({"server_name": server_name})

    await model.wait_for_idle()

    await synapse_app.set_config({"server_name": another_server_name})

    await model.wait_for_idle()

    yield synapse_app
