# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for Synapse charm integration tests."""


import json

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


@pytest_asyncio.fixture(scope="module", name="build_charm")
async def build_charm_fixture(ops_test) -> str:
    """Build the charm"""
    charm = await ops_test.build_charm(".")
    return charm


@pytest_asyncio.fixture(scope="module", name="synapse_app")
async def synapse_app_fixture(
    build_charm: str,
    model: Model,
    server_name: str,
    pytestconfig: Config,
):
    """Build and deploy the Synapse charm."""
    app_name = "synapse-k8s"

    resources = {
        "synapse-image": pytestconfig.getoption("--synapse-image"),
    }
    app = await model.deploy(
        build_charm,
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
