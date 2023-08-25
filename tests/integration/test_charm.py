#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for Synapse charm."""
import html
import json
import logging
import re
import socket
import typing
from unittest.mock import patch

import pytest
import requests
import urllib3.exceptions
from juju.action import Action
from juju.application import Application
from juju.model import Model
from ops.model import ActiveStatus
from pytest_operator.plugin import OpsTest

from constants import SYNAPSE_NGINX_PORT, SYNAPSE_PORT
from synapse.api import SYNAPSE_VERSION_REGEX

# caused by pytest fixtures
# pylint: disable=too-many-arguments

# mypy has trouble to inferred types for variables that are initialized in subclasses.
ACTIVE_STATUS_NAME = typing.cast(str, ActiveStatus.name)  # type: ignore

logger = logging.getLogger(__name__)


async def test_synapse_is_up(
    synapse_app: Application,
    get_unit_ips: typing.Callable[[str], typing.Awaitable[tuple[str, ...]]],
):
    """
    arrange: build and deploy the Synapse charm.
    act: send a request to the Synapse application managed by the Synapse charm.
    assert: the Synapse application should return a correct response.
    """
    for unit_ip in await get_unit_ips(synapse_app.name):
        response = requests.get(
            f"http://{unit_ip}:{SYNAPSE_NGINX_PORT}/_matrix/static/", timeout=5
        )
        assert response.status_code == 200
        assert "Welcome to the Matrix" in response.text


@pytest.mark.usefixtures("synapse_app", "prometheus_app")
async def test_prometheus_integration(
    model: Model,
    prometheus_app_name: str,
    synapse_app_name: str,
    get_unit_ips: typing.Callable[[str], typing.Awaitable[tuple[str, ...]]],
):
    """
    arrange: after Synapse charm has been deployed.
    act: establish relations established with prometheus charm.
    assert: prometheus metrics endpoint for prometheus is active and prometheus has active scrape
        targets.
    """
    await model.add_relation(prometheus_app_name, synapse_app_name)
    await model.wait_for_idle(
        apps=[synapse_app_name, prometheus_app_name], status=ACTIVE_STATUS_NAME
    )

    for unit_ip in await get_unit_ips(prometheus_app_name):
        query_targets = requests.get(f"http://{unit_ip}:9090/api/v1/targets", timeout=10).json()
        assert len(query_targets["data"]["activeTargets"])


@pytest.mark.usefixtures("synapse_app", "prometheus_app", "grafana_app")
async def test_grafana_integration(
    model: Model,
    synapse_app_name: str,
    prometheus_app_name: str,
    grafana_app_name: str,
    get_unit_ips: typing.Callable[[str], typing.Awaitable[tuple[str, ...]]],
):
    """
    arrange: after Synapse charm has been deployed.
    act: establish relations established with grafana charm.
    assert: grafana Synapse dashboard can be found.
    """
    await model.relate(
        f"{prometheus_app_name}:grafana-source", f"{grafana_app_name}:grafana-source"
    )
    await model.relate(synapse_app_name, grafana_app_name)

    await model.wait_for_idle(
        apps=[synapse_app_name, prometheus_app_name, grafana_app_name],
        status=ACTIVE_STATUS_NAME,
        idle_period=60,
    )

    action = await model.applications[grafana_app_name].units[0].run_action("get-admin-password")
    await action.wait()
    password = action.results["admin-password"]
    grafana_ip = (await get_unit_ips(grafana_app_name))[0]
    sess = requests.session()
    sess.post(
        f"http://{grafana_ip}:3000/login",
        json={
            "user": "admin",
            "password": password,
        },
    ).raise_for_status()
    datasources = sess.get(f"http://{grafana_ip}:3000/api/datasources", timeout=10).json()
    datasource_types = set(datasource["type"] for datasource in datasources)
    assert "prometheus" in datasource_types
    dashboards = sess.get(
        f"http://{grafana_ip}:3000/api/search",
        timeout=10,
        params={"query": "Synapse Operator"},
    ).json()
    assert len(dashboards)


@pytest.mark.usefixtures("traefik_app")
async def test_traefik_integration(
    ops_test: OpsTest,
    model: Model,
    synapse_app: Application,
    traefik_app_name: str,
    external_hostname: str,
    get_unit_ips: typing.Callable[[str], typing.Awaitable[tuple[str, ...]]],
):
    """
    arrange: build and deploy the Synapse charm, and deploy the Traefik.
    act: relate the Traefik charm with the Synapse charm.
    assert: requesting the charm through Traefik should return a correct response.
    """
    await model.add_relation(synapse_app.name, traefik_app_name)
    await model.wait_for_idle(status=ACTIVE_STATUS_NAME)

    traefik_ip = (await get_unit_ips(traefik_app_name))[0]
    response = requests.get(
        f"http://{traefik_ip}/_matrix/static/",
        headers={"Host": f"{ops_test.model_name}-{synapse_app.name}.{external_hostname}"},
        timeout=5,
    )
    assert response.status_code == 200
    assert "Welcome to the Matrix" in response.text


@pytest.mark.usefixtures("synapse_app", "nginx_integrator_app")
async def test_nginx_route_integration(
    model: Model,
    synapse_app_name: str,
    nginx_integrator_app_name: str,
):
    """
    arrange: build and deploy the Synapse charm, and deploy the nginx-integrator.
    act: relate the nginx-integrator charm with the Synapse charm.
    assert: requesting the charm through nginx-integrator should return a correct response.
    """
    await model.add_relation(f"{synapse_app_name}", f"{nginx_integrator_app_name}")
    await model.wait_for_idle(status=ACTIVE_STATUS_NAME)

    response = requests.get(
        "http://127.0.0.1/_matrix/static/", headers={"Host": synapse_app_name}, timeout=5
    )
    assert response.status_code == 200
    assert "Welcome to the Matrix" in response.text


async def test_server_name_changed(model: Model, another_synapse_app: Application):
    """
    arrange: build and deploy the Synapse charm.
    act: change server_name via juju config.
    assert: the Synapse application should prevent the change.
    """
    unit = model.applications[another_synapse_app.name].units[0]
    # Status string defined in Juju
    # https://github.com/juju/juju/blob/2.9/core/status/status.go#L150
    assert unit.workload_status == "blocked"
    assert "server_name modification is not allowed" in unit.workload_status_message


async def test_reset_instance_action(
    model: Model, another_synapse_app: Application, another_server_name: str
):
    """
    arrange: a deployed Synapse charm in a blocked state due to a server_name change.
    act: call the reset_instance action.
    assert: the old instance is deleted and the new one configured.
    """
    unit = model.applications[another_synapse_app.name].units[0]
    # Status string defined in Juju
    # https://github.com/juju/juju/blob/2.9/core/status/status.go#L150
    assert unit.workload_status == "blocked"
    assert "server_name modification is not allowed" in unit.workload_status_message
    action_reset_instance: Action = await another_synapse_app.units[0].run_action(  # type: ignore
        "reset-instance"
    )
    await action_reset_instance.wait()
    assert action_reset_instance.status == "completed"
    assert action_reset_instance.results["reset-instance"]
    assert unit.workload_status == "active"
    config = await model.applications[another_synapse_app.name].get_config()
    current_server_name = config.get("server_name", {}).get("value")
    assert current_server_name == another_server_name


async def test_register_user_action(
    model: Model,
    synapse_app: Application,
    get_unit_ips: typing.Callable[[str], typing.Awaitable[tuple[str, ...]]],
) -> None:
    """
    arrange: a deployed Synapse charm.
    act: call the register user action.
    assert: the user is registered and the login is successful.
    """
    await model.wait_for_idle(status=ACTIVE_STATUS_NAME)
    username = "operator"
    unit = model.applications[synapse_app.name].units[0]
    action_register_user: Action = await synapse_app.units[0].run_action(  # type: ignore
        "register-user", username=username, admin=True
    )
    await action_register_user.wait()
    assert action_register_user.status == "completed"
    assert action_register_user.results["register-user"]
    password = action_register_user.results["user-password"]
    assert password
    assert unit.workload_status == "active"
    data = {"type": "m.login.password", "user": username, "password": password}
    for unit_ip in await get_unit_ips(synapse_app.name):
        response = requests.post(
            f"http://{unit_ip}:{SYNAPSE_NGINX_PORT}/_matrix/client/r0/login", json=data, timeout=5
        )
        assert response.status_code == 200
        assert response.json()["access_token"]


@pytest.mark.asyncio
async def test_workload_version(
    ops_test: OpsTest,
    synapse_app: Application,
    get_unit_ips: typing.Callable[[str], typing.Awaitable[tuple[str, ...]]],
) -> None:
    """
    arrange: a deployed Synapse charm.
    act: get status from Juju.
    assert: the workload version is set and match the one given by Synapse API request.
    """
    _, status, _ = await ops_test.juju("status", "--format", "json")
    status = json.loads(status)
    juju_workload_version = status["applications"][synapse_app.name].get("version", "")
    assert juju_workload_version
    for unit_ip in await get_unit_ips(synapse_app.name):
        res = requests.get(
            f"http://{unit_ip}:{SYNAPSE_PORT}/_synapse/admin/v1/server_version", timeout=5
        )
        server_version = res.json()["server_version"]
        version_match = re.search(SYNAPSE_VERSION_REGEX, server_version)
        assert version_match
        assert version_match.group(1) == juju_workload_version


@pytest.mark.asyncio
@pytest.mark.usefixtures("nginx_integrator_app")
async def test_saml_auth(  # pylint: disable=too-many-locals
    model: Model,
    synapse_app: Application,
    saml_integrator_app,
    get_unit_ips: typing.Callable[[str], typing.Awaitable[tuple[str, ...]]],
    nginx_integrator_app_name: str,
    synapse_app_name: str,
):
    """
    arrange: integrate Synapse with SAML and NGINX charms, upload metadata to samltest.id
        and configure public_baseurl.
    act: simulate a user authenticating via SAML.
    assert: The SAML authentication process is executed successfully.
    """
    requests_timeout = 10
    await model.add_relation(f"{synapse_app.name}", f"{nginx_integrator_app_name}")
    await model.wait_for_idle(status=ACTIVE_STATUS_NAME)
    response = requests.get(
        "http://127.0.0.1/_matrix/static/",
        headers={"Host": synapse_app_name},
        timeout=requests_timeout,
    )
    assert response.status_code == 200
    await model.add_relation(saml_integrator_app.name, synapse_app.name)
    await model.wait_for_idle(
        apps=[synapse_app.name, saml_integrator_app.name], status=ACTIVE_STATUS_NAME
    )
    saml_test_url = "https://samltest.id"
    for unit_ip in await get_unit_ips(synapse_app.name):
        response = requests.get(
            f"http://{unit_ip}:{SYNAPSE_NGINX_PORT}/_synapse/client/saml2/metadata.xml",
            timeout=requests_timeout,
        )
        assert response.status_code == 200
        samltest_upload_url = f"{saml_test_url}/upload.php"
        files = {"samlfile": ("metadata.xml", response.content)}
        headers = {"Content-type": "multipart/form-data; boundary=FILEUPLOAD"}
        upload_response = requests.post(
            samltest_upload_url, files=files, headers=headers, timeout=requests_timeout
        )
        assert upload_response.status_code == 200
    public_baseurl = f"http://{synapse_app_name}"
    # The linter does not recognize set_config as a method, so this errors must be ignored.
    await synapse_app.set_config(  # type: ignore[attr-defined] # pylint: disable=W0106
        {
            "public_baseurl": public_baseurl,
        }
    )
    await model.wait_for_idle(status="active")

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    original_getaddrinfo = socket.getaddrinfo

    def patched_getaddrinfo(*args):
        """Get address info forcing localhost as the IP.

        Args:
            args: Arguments from the getaddrinfo original method.

        Returns:
            Address information with localhost as the patched IP.
        """
        if args[0] == public_baseurl:
            return original_getaddrinfo("127.0.0.1", *args[1:])
        return original_getaddrinfo(*args)

    with patch.multiple(socket, getaddrinfo=patched_getaddrinfo), requests.session() as session:
        login_page = session.get(f"{public_baseurl}/_matrix/client/r0/login")
        assert login_page.status_code == 200
        saml_page_path = "_matrix/client/r0/login/sso/redirect/saml"
        saml_page_params = "redirectUrl=http%3A%2F%2Flocalhost%2F&org.matrix.msc3824.action=login"
        saml_page = session.get(
            f"{public_baseurl}/{saml_page_path}?{saml_page_params}",
            verify=False,
            timeout=requests_timeout,
            allow_redirects=True,
        )
        assert saml_page.status_code == 302
        payload_e1s1 = {"j_username": "rick", "j_password": "psych", "_eventId_proceed": ""}
        header_user = {
            "User-Agent": "Mozilla/5.0 (X11; "
            "Ubuntu; Linux x86_64; rv:73.0) Gecko/20100101 Firefox/73.0"
        }
        sso_execution_e1s1 = session.post(
            f"{saml_test_url}/idp/profile/SAML2/Redirect/SSO?execution=e1s1",
            headers=header_user,
            verify=False,
            timeout=requests_timeout,
            allow_redirects=True,
            data=payload_e1s1,
        )
        assert sso_execution_e1s1.status_code == 200
        payload_e1s2 = {
            "j_username": "rick",
            "j_password": "psych",
            "_eventId_proceed": "Accept",
            "_shib_idp_consentOptions": "_shib_idp_globalConsent",
        }
        sso_execution_e1s2 = session.post(
            f"{saml_test_url}/idp/profile/SAML2/Redirect/SSO?execution=e1s2",
            headers=header_user,
            verify=False,
            timeout=requests_timeout,
            allow_redirects=True,
            data=payload_e1s2,
        )
        assert sso_execution_e1s2.status_code == 200
        action_re = re.compile(r'<form action="([^"]*)" method="post">')
        relay_state_re = re.compile('<input type="hidden" name="RelayState" value="([^"]*)"/>')
        saml_response_re = re.compile('<input type="hidden" name="SAMLResponse" value="([^"]*)"/>')
        # Match[str] is indexable.
        relay_state = relay_state_re.search(sso_execution_e1s2.text)[1]  # type: ignore[index]
        saml_response = saml_response_re.search(sso_execution_e1s2.text)[1]  # type: ignore[index]
        logged_user = session.post(
            html.unescape(action_re.search(sso_execution_e1s2.text)[1]),  # type: ignore[index]
            headers=header_user,
            verify=False,
            timeout=requests_timeout,
            allow_redirects=True,
            data={
                "RelayState": html.unescape(relay_state),
                "SAMLResponse": html.unescape(saml_response),
            },
        )

        assert logged_user.status_code == 200
        assert "Continue to your account" in logged_user.text
