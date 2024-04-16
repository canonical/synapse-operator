# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for Synapse charm integration tests."""


import json
import typing
from secrets import token_hex

import boto3
import pytest
import pytest_asyncio
from botocore.config import Config as BotoConfig
from juju.action import Action
from juju.application import Application
from juju.model import Model
from ops.model import ActiveStatus
from pytest import Config
from pytest_operator.plugin import OpsTest

from tests.conftest import SYNAPSE_IMAGE_PARAM, SYNAPSE_NGINX_IMAGE_PARAM
from tests.integration.helpers import get_access_token, register_user

# caused by pytest fixtures, mark does not work in fixtures
# pylint: disable=too-many-arguments, unused-argument

# mypy has trouble to inferred types for variables that are initialized in subclasses.
ACTIVE_STATUS_NAME = typing.cast(str, ActiveStatus.name)  # type: ignore


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


@pytest_asyncio.fixture(scope="module", name="model_name")
async def model_name_fixture(ops_test: OpsTest) -> str:
    """Return the current testing juju model name."""
    assert ops_test.model_name
    return ops_test.model_name


@pytest_asyncio.fixture(scope="module", name="synapse_charm")
async def synapse_charm_fixture(pytestconfig: Config):
    """Get value from parameter charm-file."""
    charm = pytestconfig.getoption("--charm-file")
    assert charm, "--charm-file must be set"
    return charm


@pytest_asyncio.fixture(scope="module", name="synapse_image")
def synapse_image_fixture(pytestconfig: Config):
    """Get value from parameter synapse-image."""
    synapse_image = pytestconfig.getoption(SYNAPSE_IMAGE_PARAM)
    assert synapse_image, f"{SYNAPSE_IMAGE_PARAM} must be set"
    return synapse_image


@pytest_asyncio.fixture(scope="module", name="synapse_nginx_image")
def synapse_nginx_image_fixture(pytestconfig: Config):
    """Get value from parameter synapse-nginx-image."""
    synapse_nginx_image = pytestconfig.getoption(SYNAPSE_NGINX_IMAGE_PARAM)
    assert synapse_nginx_image, f"{SYNAPSE_NGINX_IMAGE_PARAM} must be set"
    return synapse_nginx_image


@pytest_asyncio.fixture(scope="module", name="synapse_app_name")
def synapse_app_name_fixture() -> str:
    """Get Synapse application name."""
    return "synapse"


@pytest_asyncio.fixture(scope="module", name="synapse_app_charmhub_name")
def synapse_app_charmhub_name_fixture() -> str:
    """Get Synapse application name from Charmhub fixture."""
    return "synapse-charmhub"


@pytest_asyncio.fixture(scope="module", name="synapse_app")
async def synapse_app_fixture(
    ops_test: OpsTest,
    synapse_app_name: str,
    synapse_app_charmhub_name: str,
    synapse_image: str,
    synapse_nginx_image: str,
    model: Model,
    server_name: str,
    synapse_charm: str,
    postgresql_app: Application,
    postgresql_app_name: str,
    pytestconfig: Config,
):
    """Build and deploy the Synapse charm."""
    use_existing = pytestconfig.getoption("--use-existing", default=False)
    if use_existing or synapse_app_name in model.applications:
        return model.applications[synapse_app_name]
    resources = {
        "synapse-image": synapse_image,
        "synapse-nginx-image": synapse_nginx_image,
    }
    app = await model.deploy(
        f"./{synapse_charm}",
        resources=resources,
        application_name=synapse_app_name,
        series="jammy",
        config={"server_name": server_name},
    )
    async with ops_test.fast_forward():
        await model.wait_for_idle(raise_on_blocked=True, status=ACTIVE_STATUS_NAME)
        await model.relate(f"{synapse_app_name}:database", f"{postgresql_app_name}")
        await model.wait_for_idle(status=ACTIVE_STATUS_NAME)
    return app


@pytest_asyncio.fixture(scope="module", name="synapse_charmhub_app")
async def synapse_charmhub_app_fixture(
    ops_test: OpsTest,
    model: Model,
    server_name: str,
    synapse_app_charmhub_name: str,
    postgresql_app: Application,
    postgresql_app_name: str,
    synapse_charm: str,
):
    """Deploy synapse from Charmhub."""
    async with ops_test.fast_forward():
        app = await model.deploy(
            "synapse",
            application_name=synapse_app_charmhub_name,
            trust=True,
            channel="latest/edge",
            series="jammy",
            config={"server_name": server_name},
        )
        await model.wait_for_idle(
            apps=[synapse_app_charmhub_name, postgresql_app_name],
            status=ACTIVE_STATUS_NAME,
            idle_period=5,
        )
        await model.relate(f"{synapse_app_charmhub_name}:database", f"{postgresql_app_name}")
        await model.wait_for_idle(idle_period=5)
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


@pytest.fixture(scope="module", name="nginx_integrator_app_name")
def nginx_integrator_app_name_fixture() -> str:
    """Return the name of the nginx integrator application deployed for tests."""
    return "nginx-ingress-integrator"


@pytest_asyncio.fixture(scope="module", name="nginx_integrator_app")
async def nginx_integrator_app_fixture(
    ops_test: OpsTest,
    model: Model,
    synapse_app,
    nginx_integrator_app_name: str,
    pytestconfig: Config,
):
    """Deploy nginx-ingress-integrator."""
    use_existing = pytestconfig.getoption("--use-existing", default=False)
    if use_existing or nginx_integrator_app_name in model.applications:
        return model.applications[nginx_integrator_app_name]
    async with ops_test.fast_forward():
        app = await model.deploy(
            "nginx-ingress-integrator",
            application_name=nginx_integrator_app_name,
            trust=True,
            channel="latest/edge",
        )
        await model.wait_for_idle(raise_on_blocked=True, status=ACTIVE_STATUS_NAME)
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


@pytest.fixture(scope="module", name="postgresql_app_name")
def postgresql_app_name_app_name_fixture() -> str:
    """Return the name of the postgresql application deployed for tests."""
    return "postgresql-k8s"


@pytest_asyncio.fixture(scope="module", name="postgresql_app")
async def postgresql_app_fixture(
    ops_test: OpsTest, model: Model, postgresql_app_name: str, pytestconfig: Config
):
    """Deploy postgresql."""
    use_existing = pytestconfig.getoption("--use-existing", default=False)
    if use_existing or postgresql_app_name in model.applications:
        return model.applications[postgresql_app_name]
    async with ops_test.fast_forward():
        await model.deploy(postgresql_app_name, channel="14/stable", trust=True)
        await model.wait_for_idle(status=ACTIVE_STATUS_NAME)


@pytest.fixture(scope="module", name="irc_postgresql_app_name")
def irc_postgresql_app_name_app_name_fixture() -> str:
    """Return the name of the postgresql application deployed for irc bridge tests."""
    return "irc-postgresql-k8s"


@pytest_asyncio.fixture(scope="module", name="irc_postgresql_app")
async def irc_postgresql_app_fixture(
    ops_test: OpsTest,
    model: Model,
    postgresql_app_name: str,
    irc_postgresql_app_name: str,
    pytestconfig: Config,
):
    """Deploy postgresql."""
    use_existing = pytestconfig.getoption("--use-existing", default=False)
    if use_existing:
        return model.applications[irc_postgresql_app_name]
    async with ops_test.fast_forward():
        app = await model.deploy(
            postgresql_app_name,
            application_name=irc_postgresql_app_name,
            channel="14/stable",
            trust=True,
        )
        await model.wait_for_idle(status=ACTIVE_STATUS_NAME)
    return app


@pytest.fixture(scope="module", name="grafana_app_name")
def grafana_app_name_fixture() -> str:
    """Return the name of the grafana application deployed for tests."""
    return "grafana-k8s"


@pytest_asyncio.fixture(scope="module", name="grafana_app")
async def grafana_app_fixture(
    ops_test: OpsTest,
    model: Model,
    grafana_app_name: str,
):
    """Deploy grafana."""
    async with ops_test.fast_forward():
        app = await model.deploy(
            grafana_app_name,
            application_name=grafana_app_name,
            channel="latest/edge",
            trust=True,
        )
        await model.wait_for_idle(raise_on_blocked=True, status=ACTIVE_STATUS_NAME)

    return app


@pytest.fixture(scope="module", name="prometheus_app_name")
def prometheus_app_name_fixture() -> str:
    """Return the name of the prometheus application deployed for tests."""
    return "prometheus-k8s"


@pytest_asyncio.fixture(scope="module", name="prometheus_app")
async def deploy_prometheus_fixture(
    ops_test: OpsTest,
    model: Model,
    prometheus_app_name: str,
):
    """Deploy prometheus."""
    async with ops_test.fast_forward():
        app = await model.deploy(
            prometheus_app_name,
            application_name=prometheus_app_name,
            channel="latest/edge",
            trust=True,
        )
        # Sometimes it comes back after an error.
        await model.wait_for_idle(
            raise_on_error=False, raise_on_blocked=True, status=ACTIVE_STATUS_NAME
        )

    return app


@pytest.fixture(scope="module", name="user_username")
def user_username_fixture() -> typing.Generator[str, None, None]:
    """Return the a username to be created for tests."""
    yield token_hex(16)


@pytest_asyncio.fixture(scope="module", name="user_password")
async def user_password_fixture(synapse_app: Application, user_username: str) -> str:
    """Register a user and return the new password.

    Returns:
        The new user password
    """
    return await register_user(synapse_app, user_username)


@pytest_asyncio.fixture(scope="module", name="access_token")
async def access_token_fixture(
    user_username: str,
    user_password: str,
    synapse_app: Application,
    get_unit_ips: typing.Callable[[str], typing.Awaitable[tuple[str, ...]]],
) -> str:
    """Return the access token after login with the username and password.

    Returns:
        The access token
    """
    synapse_ip = (await get_unit_ips(synapse_app.name))[0]
    return get_access_token(synapse_ip, user_username, user_password)


@pytest.fixture(scope="module", name="localstack_address")
def localstack_address_fixture(pytestconfig: Config):
    """Provides localstack IP address to be used in the integration test."""
    address = pytestconfig.getoption("--localstack-address")
    if not address:
        raise ValueError("--localstack-address argument is required for selected test cases")
    yield address


@pytest.fixture(scope="module", name="s3_backup_configuration")
def s3_backup_configuration_fixture(localstack_address: str) -> dict:
    """Return the S3 configuration to use for backups

    Returns:
        The S3 configuration as a dict
    """
    return {
        "endpoint": f"http://{localstack_address}:4566",
        "bucket": "backups-bucket",
        "path": "/synapse",
        "region": "us-east-1",
        "s3-uri-style": "path",
    }


@pytest.fixture(scope="module", name="s3_backup_credentials")
def s3_backup_credentials_fixture(localstack_address: str) -> dict:
    """Return the S3 AWS credentials to use for backups

    Returns:
        The S3 credentials as a dict
    """
    return {
        "access-key": token_hex(16),
        "secret-key": token_hex(16),
    }


@pytest.fixture(scope="function", name="boto_s3_client")
def boto_s3_client_fixture(s3_backup_configuration: dict, s3_backup_credentials: dict):
    """Return a S# boto3 client ready to use

    Returns:
        The boto S3 client
    """
    s3_client_config = BotoConfig(
        region_name=s3_backup_configuration["region"],
        s3={
            "addressing_style": "virtual",
        },
        # no_proxy env variable is not read by boto3, so
        # this is needed for the tests to avoid hitting the proxy.
        proxies={},
    )

    s3_client = boto3.client(
        "s3",
        s3_backup_configuration["region"],
        aws_access_key_id=s3_backup_credentials["access-key"],
        aws_secret_access_key=s3_backup_credentials["secret-key"],
        endpoint_url=s3_backup_configuration["endpoint"],
        use_ssl=False,
        config=s3_client_config,
    )
    yield s3_client


@pytest.fixture(scope="function", name="s3_backup_bucket")
def s3_backup_bucket_fixture(
    s3_backup_configuration: dict, s3_backup_credentials: dict, boto_s3_client: typing.Any
):
    """Creates a bucket using S3 configuration."""
    bucket_name = s3_backup_configuration["bucket"]
    boto_s3_client.create_bucket(Bucket=bucket_name)
    yield
    objectsresponse = boto_s3_client.list_objects(Bucket=bucket_name)
    if "Contents" in objectsresponse:
        for c in objectsresponse["Contents"]:
            boto_s3_client.delete_object(Bucket=bucket_name, Key=c["Key"])
    boto_s3_client.delete_bucket(Bucket=bucket_name)


@pytest_asyncio.fixture(scope="function", name="s3_integrator_app_backup")
async def s3_integrator_app_backup_fixture(
    model: Model, s3_backup_configuration: dict, s3_backup_credentials: dict
):
    """Returns a s3-integrator app configured with backup parameters."""
    s3_integrator_app_name = "s3-integrator-backup"
    s3_integrator_app = await model.deploy(
        "s3-integrator",
        application_name=s3_integrator_app_name,
        channel="latest/edge",
        config=s3_backup_configuration,
    )
    await model.wait_for_idle(apps=[s3_integrator_app_name], idle_period=5, status="blocked")
    action_sync_s3_credentials: Action = await s3_integrator_app.units[0].run_action(
        "sync-s3-credentials",
        **s3_backup_credentials,
    )
    await action_sync_s3_credentials.wait()
    await model.wait_for_idle(status=ACTIVE_STATUS_NAME)
    yield s3_integrator_app
    await model.remove_application(s3_integrator_app_name)
    await model.block_until(lambda: s3_integrator_app_name not in model.applications, timeout=60)


@pytest.fixture(scope="function", name="s3_media")
async def s3_media_fixture(
    model: Model,
    synapse_app: Application,
    get_unit_ips: typing.Callable[[str], typing.Awaitable[tuple[str, ...]]],
    access_token: str,
    relation_name: str,
):
    """Return the Synapse application with the media configuration."""
    synapse_ip = (await get_unit_ips(synapse_app.name))[0]
    await synapse_app.set_config(
        {
            "media_store": "s3",
            "media_store_bucket": "media-bucket",
            "media_store_path": "/media",
            "media_store_s3_endpoint": f"http://{synapse_ip}:4566",
            "media_store_s3_access_key": token_hex(16),
            "media_store_s3_secret_key": token_hex(16),
            "media_store_s3_region": "us-east-1",
            "media_store_s3_uri_style": "path",
        }
    )
    await model.wait_for_idle()
    yield synapse_app
    await model.wait_for_idle()


@pytest_asyncio.fixture(scope="function", name="s3_integrator_app_media")
async def s3_integrator_app_media_fixture(
    model: Model, s3_media_configuration: dict, s3_media_credentials: dict
):
    """Returns a s3-integrator app configured with media parameters."""
    s3_integrator_app_name = "s3-integrator-media"
    s3_integrator_app = await model.deploy(
        "s3-integrator",
        application_name=s3_integrator_app_name,
        channel="latest/edge",
        config=s3_media_configuration,
    )
    await model.wait_for_idle(apps=[s3_integrator_app_name], idle_period=5, status="blocked")
    action_sync_s3_credentials: Action = await s3_integrator_app.units[0].run_action(
        "sync-s3-credentials",
        **s3_media_credentials,
    )
    await action_sync_s3_credentials.wait()
    await model.wait_for_idle(status=ACTIVE_STATUS_NAME)
    yield s3_integrator_app
    await model.remove_application(s3_integrator_app_name)
    await model.block_until(lambda: s3_integrator_app_name not in model.applications, timeout=60)
