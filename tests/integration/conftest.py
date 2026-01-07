# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for Synapse charm integration tests."""

import json
import re
import typing
from secrets import token_hex

import pytest
import pytest_asyncio
from juju.action import Action
from juju.application import Application
from juju.model import Model
from juju.unit import Unit
from ops.model import ActiveStatus, BlockedStatus
from pytest import Config
from pytest_operator.plugin import OpsTest

from auth.mas import MAS_CONFIGURATION_PATH, MAS_EXECUTABLE_PATH
from tests.conftest import SYNAPSE_IMAGE_PARAM
from tests.integration.dependencies import (
    NGINX_INGRESS_INTEGRATOR,
    OAUTH_EXTERNAL_IDP_INTEGRATOR,
    POSTGRESQL_K8S,
)

# caused by pytest fixtures, mark does not work in fixtures
# pylint: disable=too-many-arguments

# mypy has trouble to inferred types for variables that are initialized in subclasses.
ACTIVE_STATUS_NAME = typing.cast(str, ActiveStatus.name)  # type: ignore
WAITING_STATUS_NAME = "waiting"
PEBBLE_EXEC = "PEBBLE_SOCKET=/charm/containers/synapse/pebble.socket pebble exec --"
DUMP_MAS_CONFIG = f"{PEBBLE_EXEC} /mas-cli -c {MAS_CONFIGURATION_PATH} config dump"

# Application names and constants
EXTERNAL_HOSTNAME = "juju.test"
NGINX_INTEGRATOR_APP_NAME = "nginx-ingress-integrator"
POSTGRESQL_APP_NAME = "postgresql-k8s"
SYNAPSE_APP_NAME = "synapse"
OIDC_APP_NAME = "oidc"

# Server names
SERVER_NAME = "my.synapse.local"
ANOTHER_SERVER_NAME = "another.synapse.local"


@pytest_asyncio.fixture(scope="module", name="model")
async def model_fixture(ops_test: OpsTest) -> Model:
    """Return the current testing juju model."""
    assert ops_test.model
    return ops_test.model


@pytest_asyncio.fixture(scope="module", name="model_name")
async def model_name_fixture(ops_test: OpsTest) -> str:
    """Return the current testing juju model name."""
    assert ops_test.model_name
    return ops_test.model_name


@pytest_asyncio.fixture(scope="module", name="synapse_charm")
async def synapse_charm_fixture(pytestconfig: Config):
    """Get value from parameter charm-file."""
    charm = pytestconfig.getoption("--charm-file")
    use_existing = pytestconfig.getoption("--use-existing", default=False)
    if not use_existing:
        assert charm, "--charm-file must be set"
    return charm


@pytest_asyncio.fixture(scope="module", name="synapse_image")
def synapse_image_fixture(pytestconfig: Config):
    """Get value from parameter synapse-image."""
    synapse_image = pytestconfig.getoption(SYNAPSE_IMAGE_PARAM)
    use_existing = pytestconfig.getoption("--use-existing", default=False)
    if not use_existing:
        assert synapse_image, f"{SYNAPSE_IMAGE_PARAM} must be set"
    return synapse_image


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


# pylint: disable=too-many-positional-arguments
@pytest_asyncio.fixture(scope="module", name="synapse_app")
async def synapse_app_fixture(
    ops_test: OpsTest,
    synapse_image: str,
    model: Model,
    synapse_charm: str,
    postgresql_app: Application,
    pytestconfig: Config,
    get_unit_ips: typing.Callable[[str], typing.Awaitable[tuple[str, ...]]],
):
    """Build and deploy the Synapse charm."""
    use_existing = pytestconfig.getoption("--use-existing", default=False)
    if not use_existing and SYNAPSE_APP_NAME not in model.applications:
        resources = {
            "synapse-image": synapse_image,
        }
        async with ops_test.fast_forward():
            app = await model.deploy(
                f"./{synapse_charm}",
                resources=resources,
                application_name=SYNAPSE_APP_NAME,
                config={"server_name": SERVER_NAME},
            )
            await model.wait_for_idle(
                apps=[SYNAPSE_APP_NAME],
                status=typing.cast(str, BlockedStatus.name),
                idle_period=5,
            )
            synapse_ip = (await get_unit_ips(app.name))[0]
            await app.set_config({"public_baseurl": f"http://{synapse_ip}:8080"})
            await model.relate(f"{SYNAPSE_APP_NAME}:database", f"{postgresql_app.name}")
            await model.relate(
                f"{SYNAPSE_APP_NAME}:mas-database",
                f"{postgresql_app.name}:database",
            )
            await model.wait_for_idle(
                apps=[SYNAPSE_APP_NAME, postgresql_app.name],
                status=ACTIVE_STATUS_NAME,
                idle_period=5,
                raise_on_error=False,
            )
    app = model.applications.get(SYNAPSE_APP_NAME)
    return app


@pytest_asyncio.fixture(scope="module", name="postgresql_app")
async def postgresql_app_fixture(ops_test: OpsTest, model: Model, pytestconfig: Config):
    """Deploy postgresql."""
    use_existing = pytestconfig.getoption("--use-existing", default=False)
    if not use_existing and POSTGRESQL_APP_NAME not in model.applications:
        async with ops_test.fast_forward():
            await model.deploy(
                POSTGRESQL_K8S.charm_name,
                application_name=POSTGRESQL_APP_NAME,
                channel=POSTGRESQL_K8S.channel,
                revision=POSTGRESQL_K8S.revision,
                trust=POSTGRESQL_K8S.trust,
                config={"profile": "testing"},
            )
            await model.wait_for_idle(status=ACTIVE_STATUS_NAME)
    app = model.applications.get(POSTGRESQL_APP_NAME)
    assert app, "Synapse requires postgresql to be deployed"
    return app


@pytest_asyncio.fixture(scope="function", name="nginx_integrator_app")
async def nginx_integrator_app_fixture(
    ops_test: OpsTest,
    model: Model,
    synapse_app,
):
    """Deploy nginx-ingress-integrator."""
    try:
        async with ops_test.fast_forward():
            app = await model.deploy(
                NGINX_INGRESS_INTEGRATOR.charm_name,
                application_name=NGINX_INTEGRATOR_APP_NAME,
                trust=NGINX_INGRESS_INTEGRATOR.trust,
                channel=NGINX_INGRESS_INTEGRATOR.channel,
                revision=NGINX_INGRESS_INTEGRATOR.revision,
            )
            # The nginx-integrator charm goes into "waiting" when waiting
            await model.wait_for_idle(
                apps=[NGINX_INTEGRATOR_APP_NAME],
                raise_on_blocked=True,
                status=WAITING_STATUS_NAME,
            )
            await model.add_relation(f"{app.name}:nginx-route", f"{synapse_app.name}:nginx-route")
            await model.wait_for_idle(status=ACTIVE_STATUS_NAME, idle_period=10)
        yield app
    finally:
        await model.remove_application(app.name)
        await model.block_until(lambda: app.name not in model.applications, timeout=60)


@pytest_asyncio.fixture(scope="function", name="oauth_external_idp_integrator")
async def oauth_external_idp_integrator_fixture(
    ops_test: OpsTest, model: Model, mock_external_idp_config, synapse_app
):
    """Returns a oauth idp app."""
    try:
        async with ops_test.fast_forward():
            app = await model.deploy(
                OAUTH_EXTERNAL_IDP_INTEGRATOR.charm_name,
                application_name=OIDC_APP_NAME,
                channel=OAUTH_EXTERNAL_IDP_INTEGRATOR.channel,
                revision=OAUTH_EXTERNAL_IDP_INTEGRATOR.revision,
                config=mock_external_idp_config,
            )
            await model.wait_for_idle(apps=[app.name], idle_period=30)
            await synapse_app.model.relate(synapse_app.name, app.name)
            await model.wait_for_idle(
                apps=[app.name, synapse_app.name], status=ACTIVE_STATUS_NAME, idle_period=30
            )
        yield app
    finally:
        await model.remove_application(app.name)
        await model.block_until(lambda: app.name not in model.applications, timeout=60)


@pytest.fixture(scope="module", name="user_username")
def user_username_fixture() -> typing.Generator[str, None, None]:
    """Return the a username to be created for tests."""
    yield token_hex(16)


@pytest_asyncio.fixture(scope="module", name="user")
async def user_fixture(synapse_app: Application, user_username: str) -> tuple[str, str]:
    """Register a user and return the new password.

    Returns:
        The new user password
    """
    action_register_user: Action = await synapse_app.units[0].run_action(
        "register-user", username=user_username, admin=True
    )
    await action_register_user.wait()
    assert action_register_user.status == "completed"
    assert action_register_user.results.get("register-user")
    password = action_register_user.results.get("user-password")
    assert password
    return (user_username, password)


@pytest_asyncio.fixture(scope="module", name="access_token")
async def access_token_fixture(
    user: tuple[str, str],
    synapse_app: Application,
) -> str:
    """Return the access token after login with the username and password.

    Returns:
        The access token
    """
    username, _ = user
    pebble_exec_cmd = "PEBBLE_SOCKET=/charm/containers/synapse/pebble.socket pebble exec --"
    generate_token_cmd = (
        f"{pebble_exec_cmd} {MAS_EXECUTABLE_PATH} -c {MAS_CONFIGURATION_PATH}"
        " manage issue-compatibility-token"
        f" --yes-i-want-to-grant-synapse-admin-privileges {username}"
    )
    unit: Unit = synapse_app.units[0]
    action = await unit.run(generate_token_cmd)
    await action.wait()
    assert action.results["return-code"] == 0

    parsing_regex = r"Compatibility token issued: (?P<token>mct_.+) compat_access_token\.id"
    parsed_output = re.search(parsing_regex, action.results["stderr"])
    assert parsed_output is not None and parsed_output["token"]
    return parsed_output["token"]


@pytest.fixture(scope="module", name="mock_external_idp_config")
def mock_external_idp_config_fixture() -> dict:
    """Create the mock upstream idp config."""
    issuer_url = "https://issuer.internal"
    return {
        "issuer_url": "https://issuer.internal",
        "authorization_endpoint": f"{issuer_url}/oauth/authorize",
        "userinfo_endpoint": f"{issuer_url}/oauth/userinfo",
        "token_endpoint": f"{issuer_url}/oauth/token",
        "introspection_endpoint": f"{issuer_url}/oauth/introspect",
        "jwks_endpoint": f"{issuer_url}/oauth/discovery/keys",
        "client_id": "client_id",
        "client_secret": "client_secret",
    }
