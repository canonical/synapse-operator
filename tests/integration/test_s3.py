#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for Synapse charm needing the s3_backup_bucket fixture."""
import logging
import re
import typing
from secrets import token_hex

import boto3
import magic
import pytest
import pytest_asyncio
import requests
from botocore.config import Config as BotoConfig
from juju.action import Action
from juju.application import Application
from juju.model import Model
from juju.unit import Unit
from ops.model import ActiveStatus, BlockedStatus
from pytest import Config
from pytest_operator.plugin import OpsTest

from auth.mas import MAS_CONFIGURATION_PATH, MAS_EXECUTABLE_PATH
from tests.integration.conftest import SERVER_NAME
from tests.integration.dependencies import S3_INTEGRATOR

# caused by pytest fixtures
# pylint: disable=too-many-arguments, duplicate-code, unused-argument

# mypy has trouble to inferred types for variables that are initialized in subclasses.
ACTIVE_STATUS_NAME = typing.cast(str, ActiveStatus.name)  # type: ignore
S3_MEDIA_INTEGRATOR_APP_NAME = "s3-integrator-media"
S3_BACKUP_INTEGRATOR_APP_NAME = "s3-integrator-backup"
SYNAPSE_S3_APP_NAME = "synapse-s3"

logger = logging.getLogger(__name__)


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


@pytest.fixture(scope="function", name="s3_media_configuration")
def s3_media_configuration_fixture(localstack_address: str) -> dict:
    """Return the S3 configuration to use for media

    Returns:
        The S3 configuration as a dict
    """
    return {
        "endpoint": f"http://{localstack_address}:4566",
        "bucket": "synapse-media-bucket",
        "path": "/media",
        "region": "us-east-1",
        "s3-uri-style": "path",
    }


@pytest.fixture(scope="module", name="s3_media_credentials")
def s3_media_credentials_fixture(localstack_address: str) -> dict:
    """Return the S3 AWS credentials to use for media

    Returns:
        The S3 credentials as a dict
    """
    return {
        "access-key": token_hex(16),
        "secret-key": token_hex(16),
    }


@pytest.fixture(scope="function", name="boto_s3_media_client")
def boto_s3_media_client_fixture(
    model: Model, s3_media_configuration: dict, s3_media_credentials: dict
):
    """Return a S# boto3 client ready to use

    Returns:
        The boto S3 client
    """
    s3_client_config = BotoConfig(
        region_name=s3_media_configuration["region"],
        s3={
            "addressing_style": "virtual",
        },
        # no_proxy env variable is not read by boto3, so
        # this is needed for the tests to avoid hitting the proxy.
        proxies={},
    )

    s3_client = boto3.client(
        "s3",
        s3_media_configuration["region"],
        aws_access_key_id=s3_media_credentials["access-key"],
        aws_secret_access_key=s3_media_credentials["secret-key"],
        endpoint_url=s3_media_configuration["endpoint"],
        use_ssl=False,
        config=s3_client_config,
    )
    yield s3_client


@pytest.fixture(scope="function", name="s3_media_bucket")
def s3_media_bucket_fixture(
    s3_media_configuration: dict, s3_media_credentials: dict, boto_s3_media_client: typing.Any
):
    """Creates a bucket using S3 configuration."""
    bucket_name = s3_media_configuration["bucket"]
    boto_s3_media_client.create_bucket(Bucket=bucket_name)
    yield
    objectsresponse = boto_s3_media_client.list_objects(Bucket=bucket_name)
    if "Contents" in objectsresponse:
        for c in objectsresponse["Contents"]:
            boto_s3_media_client.delete_object(Bucket=bucket_name, Key=c["Key"])
    boto_s3_media_client.delete_bucket(Bucket=bucket_name)


@pytest_asyncio.fixture(scope="module", name="access_token_s3")
async def access_token_s3_fixture(
    user_s3: tuple[str, str],
    synapse_app_s3: Application,
) -> str:
    """Return the access token after login with the username and password.

    Returns:
        The access token
    """
    username, _ = user_s3
    pebble_exec_cmd = "PEBBLE_SOCKET=/charm/containers/synapse/pebble.socket pebble exec --"
    generate_token_cmd = (
        f"{pebble_exec_cmd} {MAS_EXECUTABLE_PATH} -c {MAS_CONFIGURATION_PATH}"
        " manage issue-compatibility-token"
        f" --yes-i-want-to-grant-synapse-admin-privileges {username}"
    )
    unit: Unit = synapse_app_s3.units[0]
    action = await unit.run(generate_token_cmd)
    await action.wait()
    assert action.results["return-code"] == 0

    parsing_regex = r"Compatibility token issued: (?P<token>mct_.+) compat_access_token\.id"
    parsed_output = re.search(parsing_regex, action.results["stderr"])
    assert parsed_output is not None and parsed_output["token"]
    return parsed_output["token"]


@pytest_asyncio.fixture(scope="module", name="user_s3")
async def user_s3_fixture(synapse_app_s3: Application, user_username: str) -> tuple[str, str]:
    """Register a user and return the new password.

    Returns:
        The new user password
    """
    action_register_user: Action = await synapse_app_s3.units[0].run_action(
        "register-user", username=user_username, admin=True
    )
    await action_register_user.wait()
    assert action_register_user.status == "completed"
    assert action_register_user.results.get("register-user")
    password = action_register_user.results.get("user-password")
    assert password
    return (user_username, password)


@pytest_asyncio.fixture(scope="function", name="s3_integrator_app_backup")
async def s3_integrator_app_backup_fixture(
    model: Model, s3_backup_configuration: dict, s3_backup_credentials: dict
):
    """Returns a s3-integrator app configured with backup parameters."""
    s3_integrator_app = await model.deploy(
        S3_INTEGRATOR.charm_name,
        application_name=S3_BACKUP_INTEGRATOR_APP_NAME,
        channel=S3_INTEGRATOR.channel,
        revision=S3_INTEGRATOR.revision,
        config=s3_backup_configuration,
    )
    await model.wait_for_idle(
        apps=[S3_BACKUP_INTEGRATOR_APP_NAME], idle_period=5, status="blocked"
    )
    action_sync_s3_credentials: Action = await s3_integrator_app.units[0].run_action(
        "sync-s3-credentials",
        **s3_backup_credentials,
    )
    await action_sync_s3_credentials.wait()
    await model.wait_for_idle(status=ACTIVE_STATUS_NAME)
    yield s3_integrator_app
    await model.remove_application(S3_BACKUP_INTEGRATOR_APP_NAME)
    await model.block_until(
        lambda: S3_BACKUP_INTEGRATOR_APP_NAME not in model.applications, timeout=60
    )


@pytest_asyncio.fixture(scope="function", name="s3_integrator_app_media")
async def s3_integrator_app_media_fixture(
    model: Model,
    s3_media_configuration: dict,
    s3_media_credentials: dict,
):
    """Returns a s3-integrator app configured with backup parameters."""
    s3_integrator_app = await model.deploy(
        S3_INTEGRATOR.charm_name,
        application_name=S3_MEDIA_INTEGRATOR_APP_NAME,
        channel=S3_INTEGRATOR.channel,
        revision=S3_INTEGRATOR.revision,
        config=s3_media_configuration,
    )
    await model.wait_for_idle(apps=[S3_MEDIA_INTEGRATOR_APP_NAME], idle_period=5, status="blocked")
    action_sync_s3_credentials: Action = await s3_integrator_app.units[0].run_action(
        "sync-s3-credentials",
        **s3_media_credentials,
    )
    await action_sync_s3_credentials.wait()
    await model.wait_for_idle(apps=[S3_MEDIA_INTEGRATOR_APP_NAME], status="active")

    yield s3_integrator_app
    await model.remove_application(S3_MEDIA_INTEGRATOR_APP_NAME)
    await model.block_until(
        lambda: S3_MEDIA_INTEGRATOR_APP_NAME not in model.applications, timeout=60
    )


# pylint: disable=too-many-positional-arguments
@pytest_asyncio.fixture(scope="module", name="synapse_app_s3")
async def synapse_app_s3_fixture(
    ops_test: OpsTest,
    synapse_image: str,
    model: Model,
    synapse_charm: str,
    postgresql_app: Application,
    pytestconfig: Config,
    get_unit_ips: typing.Callable[[str], typing.Awaitable[tuple[str, ...]]],
):
    """Build and deploy the Synapse charm"""
    use_existing = pytestconfig.getoption("--use-existing", default=False)
    if not use_existing and SYNAPSE_S3_APP_NAME not in model.applications:
        resources = {
            "synapse-image": synapse_image,
        }
        async with ops_test.fast_forward():
            app = await model.deploy(
                f"./{synapse_charm}",
                resources=resources,
                application_name=SYNAPSE_S3_APP_NAME,
                config={"server_name": SERVER_NAME},
            )
            await model.wait_for_idle(
                apps=[SYNAPSE_S3_APP_NAME],
                status=typing.cast(str, BlockedStatus.name),
                idle_period=5,
            )
            synapse_ip = (await get_unit_ips(app.name))[0]
            await app.set_config({"public_baseurl": f"http://{synapse_ip}:8080"})
            await model.relate(f"{SYNAPSE_S3_APP_NAME}:database", f"{postgresql_app.name}")
            await model.relate(
                f"{SYNAPSE_S3_APP_NAME}:mas-database",
                f"{postgresql_app.name}:database",
            )
            await model.wait_for_idle(
                apps=[SYNAPSE_S3_APP_NAME, postgresql_app.name],
                status=ACTIVE_STATUS_NAME,
                idle_period=5,
                raise_on_error=False,
            )
    app = model.applications.get(SYNAPSE_S3_APP_NAME)
    return app


async def test_synapse_enable_s3_backup_integration_no_bucket(
    model: Model,
    synapse_app_s3: Application,
    s3_integrator_app_backup: Application,
):
    """
    arrange: Synapse App deployed and s3-integrator deployed.
    act:  integrate s3-integrator with Synapse.
    assert: Synapse gets into blocked status because the bucket does not exist.
    """
    await model.add_relation(s3_integrator_app_backup.name, f"{synapse_app_s3.name}:backup")
    await model.wait_for_idle(apps=[s3_integrator_app_backup.name], status=ACTIVE_STATUS_NAME)

    await model.wait_for_idle(apps=[synapse_app_s3.name], idle_period=5, status="blocked")
    assert synapse_app_s3.units[0].workload_status == "blocked"
    assert "bucket does not exist" in synapse_app_s3.units[0].workload_status_message


@pytest.mark.s3
@pytest.mark.usefixtures("s3_backup_bucket")
async def test_synapse_create_backup_correct(
    model: Model,
    synapse_app_s3: Application,
    s3_integrator_app_backup: Application,
    s3_backup_configuration: dict,
    boto_s3_client: typing.Any,
):
    """
    arrange: Synapse App deployed and related with s3-integrator. backup_passphrase set.
    act: Run create-backup action
    assert: Correct response from the action that includes the backup-id.
       An encrypted object was created in S3 with the correct name.
    """
    await model.add_relation(s3_integrator_app_backup.name, f"{synapse_app_s3.name}:backup")
    passphrase = token_hex(16)
    await synapse_app_s3.set_config({"backup_passphrase": passphrase})
    await model.wait_for_idle(
        idle_period=30,
        apps=[synapse_app_s3.name, s3_integrator_app_backup.name],
        status=ACTIVE_STATUS_NAME,
    )

    synapse_unit: Unit = next(iter(synapse_app_s3.units))
    backup_action: Action = await synapse_unit.run_action("create-backup")
    await backup_action.wait()

    assert backup_action.status == "completed"
    assert "backup-id" in backup_action.results
    bucket_name = s3_backup_configuration["bucket"]
    path = s3_backup_configuration["path"].strip("/")
    object_key = f"{path}/{backup_action.results['backup-id']}"
    s3objresp = boto_s3_client.get_object(Bucket=bucket_name, Key=object_key)
    objbuf = s3objresp["Body"].read()
    # GnuPG 2.2.x and earlier outputs "GPG symmetrically encrypted data (AES256 cipher)"
    assert (
        "PGP symmetric key encrypted data - AES with 256-bit key salted & iterated - SHA512"
        in magic.from_buffer(objbuf)
    )


@pytest.mark.s3
@pytest.mark.usefixtures("s3_backup_bucket")
async def test_synapse_list_backups(
    model: Model,
    synapse_app_s3: Application,
    s3_integrator_app_backup: Application,
):
    """
    arrange: Synapse App deployed and related with s3-integrator. Set backup_passphrase
        and create two backups.
    act: Run action list-backups
    assert: There should be two backups, with the same keys as the ones created.
    """
    await model.add_relation(s3_integrator_app_backup.name, f"{synapse_app_s3.name}:backup")
    passphrase = token_hex(16)
    await synapse_app_s3.set_config({"backup_passphrase": passphrase})
    await model.wait_for_idle(
        idle_period=30,
        apps=[synapse_app_s3.name, s3_integrator_app_backup.name],
        status=ACTIVE_STATUS_NAME,
    )
    synapse_unit: Unit = next(iter(synapse_app_s3.units))
    backup_action_1: Action = await synapse_unit.run_action("create-backup")
    await backup_action_1.wait()
    backup_action_2: Action = await synapse_unit.run_action("create-backup")
    await backup_action_2.wait()

    list_backups_action: Action = await synapse_unit.run_action("list-backups")
    await list_backups_action.wait()

    assert list_backups_action.status == "completed"
    assert "backups" in list_backups_action.results
    backups = list_backups_action.results["backups"]
    assert len(backups) == 2
    assert backup_action_1.results["backup-id"] in backups
    assert backup_action_2.results["backup-id"] in backups


@pytest.mark.s3
@pytest.mark.usefixtures("s3_backup_bucket")
async def test_synapse_backup_restore(
    model: Model,
    synapse_app_s3: Application,
    s3_integrator_app_backup: Application,
):
    """
    arrange: Synapse App deployed and related with s3-integrator. Set backup_passphrase
        and create a backup.
    act: Run action restore-backup
    assert: Should not fail. Synapse should be started.
    """
    # This is just a smoke test as internals of the restored files are not checked.
    await model.add_relation(s3_integrator_app_backup.name, f"{synapse_app_s3.name}:backup")
    passphrase = token_hex(16)
    await synapse_app_s3.set_config({"backup_passphrase": passphrase})
    await model.wait_for_idle(
        idle_period=30,
        apps=[synapse_app_s3.name, s3_integrator_app_backup.name],
        status=ACTIVE_STATUS_NAME,
    )
    synapse_unit: Unit = next(iter(synapse_app_s3.units))
    backup_action: Action = await synapse_unit.run_action("create-backup")
    await backup_action.wait()

    restore_backup_action: Action = await synapse_unit.run_action(
        "restore-backup", **{"backup-id": backup_action.results["backup-id"]}
    )
    await restore_backup_action.wait()

    assert restore_backup_action.status == "completed"
    await synapse_app_s3.model.wait_for_idle(
        idle_period=30, timeout=120, apps=[synapse_app_s3.name], status="active"
    )


@pytest.mark.s3
@pytest.mark.usefixtures("s3_backup_bucket")
async def test_synapse_backup_delete(
    model: Model,
    synapse_app_s3: Application,
    s3_integrator_app_backup: Application,
):
    """
    arrange: Synapse App deployed and related with s3-integrator. Set backup_passphrase
        and create a backup.
    act: Run action delete-backup with the created backup.
    assert: In list-backups, there should be no backup.
    """
    await model.add_relation(s3_integrator_app_backup.name, f"{synapse_app_s3.name}:backup")
    passphrase = token_hex(16)
    await synapse_app_s3.set_config({"backup_passphrase": passphrase})
    await model.wait_for_idle(
        idle_period=30,
        apps=[synapse_app_s3.name, s3_integrator_app_backup.name],
        status=ACTIVE_STATUS_NAME,
    )
    synapse_unit: Unit = next(iter(synapse_app_s3.units))
    backup_action: Action = await synapse_unit.run_action("create-backup")
    await backup_action.wait()

    delete_backup_action: Action = await synapse_unit.run_action(
        "delete-backup", **{"backup-id": backup_action.results["backup-id"]}
    )
    await delete_backup_action.wait()

    assert delete_backup_action.status == "completed"
    list_backups_action: Action = await synapse_unit.run_action("list-backups")
    await list_backups_action.wait()
    assert list_backups_action.status == "completed"
    assert "backups" not in list_backups_action.results


@pytest.mark.s3
@pytest.mark.usefixtures("s3_media_bucket")
async def test_synapse_enable_media(  # pylint: disable=too-many-positional-arguments
    model: Model,
    synapse_app_s3: Application,
    get_unit_ips: typing.Callable[[str], typing.Awaitable[tuple[str, ...]]],
    access_token_s3: str,
    s3_integrator_app_media: Application,
    boto_s3_media_client: typing.Any,
    s3_media_configuration: dict,
):
    """
    arrange: Synapse App deployed and s3-integrator deployed with bucket created.
    act:  Assert media can be uploaded, and retrieved, from the S3 media bucket.
    assert: The media file is uploaded to the S3 bucket, and retrieved successfully.
    """
    bucket_name = s3_media_configuration["bucket"]

    await model.add_relation(f"{s3_integrator_app_media.name}", f"{synapse_app_s3.name}:media")
    await model.wait_for_idle(
        idle_period=30,
        apps=[synapse_app_s3.name, s3_integrator_app_media.name],
        status=ACTIVE_STATUS_NAME,
    )

    synapse_ip = (await get_unit_ips(synapse_app_s3.name))[0]
    headers = {
        "Authorization": f"Bearer {access_token_s3}",
        "Content-Type": "application/octet-stream",
    }
    media_file = "test_media_file.txt"

    # boto_s3_media_client.create_bucket(Bucket=s3_media_configuration["bucket"])
    # Upload media file
    response = requests.post(
        f"http://{synapse_ip}:8080/_matrix/media/v3/upload",
        headers=headers,
        params={"filename": media_file},
        data=b"",
        timeout=5,
    )
    assert response.status_code == 200

    media_id = response.json()["content_uri"].split("/")[3]
    # Key is in the format /local_content/AA/BB/CCCC..
    # The media_id is concatenation of AABBCCCC..
    key = f"/medialocal_content/{media_id[:2]}/{media_id[2:4]}/{media_id[4:]}"
    s3objresp = boto_s3_media_client.get_object(Bucket=bucket_name, Key=key)
    assert s3objresp["ResponseMetadata"]["HTTPStatusCode"] == 200


@pytest.mark.s3
@pytest.mark.usefixtures("s3_backup_bucket")
@pytest.mark.usefixtures("s3_media_bucket")
async def test_synapse_create_backup_correct_media_sync_cleanup(  # noqa: E501 pylint: disable=too-many-positional-arguments
    model: Model,
    synapse_app_s3: Application,
    s3_integrator_app_backup: Application,
    s3_backup_configuration: dict,
    boto_s3_client: typing.Any,
    s3_integrator_app_media: Application,
):
    """
    arrange: Synapse App deployed and related with s3-integrator together with media.
        enable_media_sync_cleanup and backup_passphrase set.
    act: Run create-backup action
    assert: Correct response from the action that includes the backup-id.
       An encrypted object was created in S3 with the correct name.
    """
    await model.add_relation(f"{s3_integrator_app_media.name}", f"{synapse_app_s3.name}:media")
    await model.wait_for_idle(
        idle_period=30,
        apps=[synapse_app_s3.name, s3_integrator_app_media.name],
        status=ACTIVE_STATUS_NAME,
    )

    await model.add_relation(s3_integrator_app_backup.name, f"{synapse_app_s3.name}:backup")
    passphrase = token_hex(16)
    await synapse_app_s3.set_config(
        {"backup_passphrase": passphrase, "enable_media_sync_cleanup": "true"}
    )
    await model.wait_for_idle(
        idle_period=30,
        apps=[synapse_app_s3.name, s3_integrator_app_backup.name],
        status=ACTIVE_STATUS_NAME,
    )

    synapse_unit: Unit = next(iter(synapse_app_s3.units))
    backup_action: Action = await synapse_unit.run_action("create-backup")
    await backup_action.wait()

    assert backup_action.status == "completed"
    assert backup_action.results["media-sync-cleanup-result"] == "correct"
    assert "backup-id" in backup_action.results
    bucket_name = s3_backup_configuration["bucket"]
    path = s3_backup_configuration["path"].strip("/")
    object_key = f"{path}/{backup_action.results['backup-id']}"
    s3objresp = boto_s3_client.get_object(Bucket=bucket_name, Key=object_key)
    objbuf = s3objresp["Body"].read()
    # GnuPG 2.2.x and earlier outputs "GPG symmetrically encrypted data (AES256 cipher)"
    assert (
        "PGP symmetric key encrypted data - AES with 256-bit key salted & iterated - SHA512"
        in magic.from_buffer(objbuf)
    )
