#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for MAS (Matrix Authentication Service) functionality."""

# Similar to synapse is up
# pylint: disable=R0801

import logging
import typing

import pytest
import requests
import yaml
from juju.application import Application

import synapse
from auth.mas import MAS_CONFIGURATION_PATH

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_mas_is_up(
    synapse_app: Application,
    get_unit_ips: typing.Callable[[str], typing.Awaitable[tuple[str, ...]]],
):
    """
    arrange: build and deploy the Synapse charm with MAS enabled.
    act: send a request to the MAS endpoints managed by the Synapse charm.
    assert: the MAS application should return correct responses.
    """
    # Enable MAS in the charm configuration
    await synapse_app.set_config({"enable_mas": "true"})

    # Wait for the charm to settle after configuration change
    await synapse_app.get_status()

    charm_config = await synapse_app.get_config()
    for unit_ip in await get_unit_ips(synapse_app.name):
        # Test that Synapse is still responding
        response = requests.get(
            f"http://{unit_ip}:{synapse.SYNAPSE_NGINX_PORT}/_matrix/static/", timeout=5
        )
        assert response.status_code == 200
        assert "Welcome to the Matrix" in response.text

        # Test MAS auth endpoint
        response = requests.get(f"http://{unit_ip}:{synapse.SYNAPSE_NGINX_PORT}/auth/", timeout=5)
        assert response.status_code == 200
        assert "Matrix Authentication Service" in response.text

        # Test OpenID Connect configuration endpoint
        response = requests.get(
            f"http://{unit_ip}:{synapse.SYNAPSE_NGINX_PORT}"
            "/auth/.well-known/openid-configuration",
            timeout=5,
        )
        assert response.status_code == 200
        openid_configuration = response.json()
        assert (
            openid_configuration.get("issuer")
            == f"{charm_config['public_baseurl'].get('value')}/auth/"
        )


@pytest.mark.asyncio
async def test_mas_oauth_integration(
    synapse_app: Application,
    oauth_external_idp_integrator: Application,
):
    """
    arrange: build and deploy the Synapse charm with MAS enabled and OAuth integration.
    act: relate Synapse to OAuth external IDP integrator and check MAS configuration.
    assert: the MAS configuration should include OAuth provider details.
    """
    # Enable MAS in the charm configuration
    await synapse_app.set_config({"enable_mas": "true"})

    # Create relation between Synapse and OAuth integrator
    await synapse_app.model.relate(synapse_app.name, oauth_external_idp_integrator.name)
    await synapse_app.model.wait_for_idle(
        idle_period=30,
        timeout=120,
        apps=[synapse_app.name, oauth_external_idp_integrator.name],
        status="active",
    )

    # Dump MAS configuration to verify OAuth integration
    pebble_exec = "PEBBLE_SOCKET=/charm/containers/synapse/pebble.socket pebble exec --"
    dump_mas_config = f"{pebble_exec} mas-cli -c {MAS_CONFIGURATION_PATH} config dump"
    action = await synapse_app.units[0].run(dump_mas_config)
    await action.wait()
    assert action.results["return-code"] == 0

    mas_config = yaml.safe_load(action.results["stdout"])
    assert mas_config["upstream_oauth2"]["providers"][0]["issuer"] == "https://issuer.internal"
