#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for Synapse charm."""
import logging
import typing

import pytest
import requests
from juju.application import Application
from juju.model import Model
from ops.model import ActiveStatus
from saml_test_helper import SamlK8sTestHelper

import synapse

# caused by pytest fixtures
# pylint: disable=too-many-arguments

# mypy has trouble to inferred types for variables that are initialized in subclasses.
ACTIVE_STATUS_NAME = typing.cast(str, ActiveStatus.name)  # type: ignore

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_saml_auth(  # pylint: disable=too-many-locals
    model: Model,
    model_name: str,
    synapse_app: Application,
    nginx_integrator_app: Application,  # pylint: disable=unused-argument
    get_unit_ips: typing.Callable[[str], typing.Awaitable[tuple[str, ...]]],
):
    """
    arrange: integrate Synapse with SAML and NGINX charms, upload metadata to samltest.id
        and configure public_baseurl.
    act: simulate a user authenticating via SAML.
    assert: The SAML authentication process is executed successfully.
    """
    synapse_config = await synapse_app.get_config()
    server_name = synapse_config["server_name"]["value"]
    assert server_name
    saml_helper = SamlK8sTestHelper.deploy_saml_idp(model_name)

    saml_integrator_app: Application = await model.deploy(
        "saml-integrator",
        channel="latest/edge",
        series="jammy",
        trust=True,
    )
    await model.wait_for_idle()
    saml_helper.prepare_pod(model_name, f"{saml_integrator_app.name}-0")
    saml_helper.prepare_pod(model_name, f"{synapse_app.name}-0")
    await saml_integrator_app.set_config(
        {
            "entity_id": f"https://{saml_helper.SAML_HOST}/metadata",
            "metadata_url": f"https://{saml_helper.SAML_HOST}/metadata",
        }
    )
    await model.wait_for_idle(idle_period=30)
    await model.add_relation(saml_integrator_app.name, synapse_app.name)
    await model.wait_for_idle(
        idle_period=30,
        apps=[synapse_app.name, saml_integrator_app.name],
        status=ACTIVE_STATUS_NAME,
    )

    session = requests.session()
    headers = {"Host": server_name}
    for unit_ip in await get_unit_ips(synapse_app.name):
        response = session.get(
            f"http://{unit_ip}:{synapse.SYNAPSE_NGINX_PORT}/_synapse/client/saml2/metadata.xml",
            timeout=10,
            headers=headers,
        )
        assert response.status_code == 200
        saml_helper.register_service_provider(name=server_name, metadata=response.text)
        saml_page_path = "_matrix/client/r0/login/sso/redirect/saml"
        saml_page_params = "redirectUrl=http%3A%2F%2Flocalhost%2F&org.matrix.msc3824.action=login"
        redirect_response = session.get(
            f"http://{unit_ip}:{synapse.SYNAPSE_NGINX_PORT}/{saml_page_path}?{saml_page_params}",
            verify=False,
            timeout=10,
            headers=headers,
            allow_redirects=False,
        )
        assert redirect_response.status_code == 302
        redirect_url = redirect_response.headers["Location"]
        saml_response = saml_helper.redirect_sso_login(redirect_url)
        assert f"https://{server_name}" in saml_response.url

        url = saml_response.url.replace(
            f"https://{server_name}", f"http://{unit_ip}:{synapse.SYNAPSE_NGINX_PORT}"
        )
        logged_in_page = session.post(url, data=saml_response.data, headers={"Host": server_name})

        assert logged_in_page.status_code == 200
        assert "Continue to your account" in logged_in_page.text
