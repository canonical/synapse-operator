# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for Synapse charm oauth integration."""

import logging

import yaml
from juju.application import Application

from .conftest import DUMP_MAS_CONFIG

logger = logging.getLogger(__name__)


async def test_oauth(
    synapse_app: Application,
    oauth_external_idp_integrator: Application,
):
    """
    arrange: build and deploy the Synapse charm.
    act: send a request to the Synapse application managed by the Synapse charm.
    assert: the Synapse application should return a correct response.
    """
    await synapse_app.model.relate(synapse_app.name, oauth_external_idp_integrator.name)
    await synapse_app.model.wait_for_idle(
        idle_period=30,
        timeout=120,
        apps=[synapse_app.name, oauth_external_idp_integrator.name],
        status="active",
    )

    action = await synapse_app.units[0].run(DUMP_MAS_CONFIG)
    await action.wait()
    assert action.results["return-code"] == 0

    mas_config = yaml.safe_load(action.results["stdout"])
    assert mas_config["upstream_oauth2"]["providers"][0]["issuer"] == "https://issuer.internal"
