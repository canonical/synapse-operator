#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for Synapse charm needing the s3_backup_bucket fixture."""
import logging
import typing
from secrets import token_hex

import magic
import pytest
import requests
from juju.action import Action
from juju.application import Application
from juju.model import Model
from juju.unit import Unit
from ops.model import ActiveStatus

# caused by pytest fixtures
# pylint: disable=too-many-arguments, duplicate-code, unsupported-membership-test

# mypy has trouble to inferred types for variables that are initialized in subclasses.
ACTIVE_STATUS_NAME = typing.cast(str, ActiveStatus.name)  # type: ignore

logger = logging.getLogger(__name__)


@pytest.mark.s3
@pytest.mark.usefixtures("s3_backup_bucket")
async def test_synapse_enable_s3_backup_integration_success(
    model: Model,
    synapse_app: Application,
    s3_integrator_app_backup: Application,
):
    """
    arrange: Synapse App deployed and s3-integrator deployed with bucket created.
    act:  integrate s3-integrator with Synapse.
    assert: Synapse gets into active status.
    """
    await model.add_relation(s3_integrator_app_backup.name, f"{synapse_app.name}:backup")
    await model.wait_for_idle(apps=[s3_integrator_app_backup.name], status=ACTIVE_STATUS_NAME)

    await model.wait_for_idle(
        idle_period=30,
        apps=[synapse_app.name, s3_integrator_app_backup.name],
        status=ACTIVE_STATUS_NAME,
    )


async def test_synapse_enable_s3_backup_integration_no_bucket(
    model: Model,
    synapse_app: Application,
    s3_integrator_app_backup: Application,
):
    """
    arrange: Synapse App deployed and s3-integrator deployed.
    act:  integrate s3-integrator with Synapse.
    assert: Synapse gets into blocked status because the bucket does not exist.
    """
    await model.add_relation(s3_integrator_app_backup.name, f"{synapse_app.name}:backup")
    await model.wait_for_idle(apps=[s3_integrator_app_backup.name], status=ACTIVE_STATUS_NAME)

    await model.wait_for_idle(apps=[synapse_app.name], idle_period=5, status="blocked")
    assert synapse_app.units[0].workload_status == "blocked"
    assert "bucket does not exist" in synapse_app.units[0].workload_status_message


@pytest.mark.s3
@pytest.mark.usefixtures("s3_backup_bucket")
async def test_synapse_create_backup_correct(
    model: Model,
    synapse_app: Application,
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
    await model.add_relation(s3_integrator_app_backup.name, f"{synapse_app.name}:backup")
    passphrase = token_hex(16)
    await synapse_app.set_config({"backup_passphrase": passphrase})
    await model.wait_for_idle(
        idle_period=30,
        apps=[synapse_app.name, s3_integrator_app_backup.name],
        status=ACTIVE_STATUS_NAME,
    )

    synapse_unit: Unit = next(iter(synapse_app.units))
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
async def test_synapse_create_backup_no_passphrase(
    model: Model,
    synapse_app: Application,
    s3_integrator_app_backup: Application,
):
    """
    arrange: Synapse App deployed and related with s3-integrator. No backup_passphrase.
    act: Run create-backup action
    assert: The action fails because there is no passphrase.
    """
    await synapse_app.reset_config(["backup_passphrase"])
    await model.add_relation(s3_integrator_app_backup.name, f"{synapse_app.name}:backup")
    await model.wait_for_idle(
        idle_period=30,
        apps=[synapse_app.name, s3_integrator_app_backup.name],
        status=ACTIVE_STATUS_NAME,
    )

    synapse_unit: Unit = next(iter(synapse_app.units))
    backup_action: Action = await synapse_unit.run_action("create-backup")
    await backup_action.wait()

    assert backup_action.status == "failed"
    assert "backup-id" not in backup_action.results
    assert "Missing backup_passphrase" in backup_action.message


@pytest.mark.s3
@pytest.mark.usefixtures("s3_backup_bucket")
async def test_synapse_list_backups(
    model: Model,
    synapse_app: Application,
    s3_integrator_app_backup: Application,
):
    """
    arrange: Synapse App deployed and related with s3-integrator. Set backup_passphrase
        and create two backups.
    act: Run action list-backups
    assert: There should be two backups, with the same keys as the ones created.
    """
    await model.add_relation(s3_integrator_app_backup.name, f"{synapse_app.name}:backup")
    passphrase = token_hex(16)
    await synapse_app.set_config({"backup_passphrase": passphrase})
    await model.wait_for_idle(
        idle_period=30,
        apps=[synapse_app.name, s3_integrator_app_backup.name],
        status=ACTIVE_STATUS_NAME,
    )
    synapse_unit: Unit = next(iter(synapse_app.units))
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
    synapse_app: Application,
    s3_integrator_app_backup: Application,
):
    """
    arrange: Synapse App deployed and related with s3-integrator. Set backup_passphrase
        and create a backup.
    act: Run action restore-backup
    assert: Should not fail. Synapse should be started.
    """
    # This is just a smoke test as internals of the restored files are not checked.
    await model.add_relation(s3_integrator_app_backup.name, f"{synapse_app.name}:backup")
    passphrase = token_hex(16)
    await synapse_app.set_config({"backup_passphrase": passphrase})
    await model.wait_for_idle(
        idle_period=30,
        apps=[synapse_app.name, s3_integrator_app_backup.name],
        status=ACTIVE_STATUS_NAME,
    )
    synapse_unit: Unit = next(iter(synapse_app.units))
    backup_action: Action = await synapse_unit.run_action("create-backup")
    await backup_action.wait()

    restore_backup_action: Action = await synapse_unit.run_action(
        "restore-backup", **{"backup-id": backup_action.results["backup-id"]}
    )
    await restore_backup_action.wait()

    assert restore_backup_action.status == "completed"
    await synapse_app.model.wait_for_idle(
        idle_period=30, timeout=120, apps=[synapse_app.name], status="active"
    )


@pytest.mark.s3
@pytest.mark.usefixtures("s3_backup_bucket")
async def test_synapse_backup_delete(
    model: Model,
    synapse_app: Application,
    s3_integrator_app_backup: Application,
):
    """
    arrange: Synapse App deployed and related with s3-integrator. Set backup_passphrase
        and create a backup.
    act: Run action delete-backup with the created backup.
    assert: In list-backups, there should be no backup.
    """
    await model.add_relation(s3_integrator_app_backup.name, f"{synapse_app.name}:backup")
    passphrase = token_hex(16)
    await synapse_app.set_config({"backup_passphrase": passphrase})
    await model.wait_for_idle(
        idle_period=30,
        apps=[synapse_app.name, s3_integrator_app_backup.name],
        status=ACTIVE_STATUS_NAME,
    )
    synapse_unit: Unit = next(iter(synapse_app.units))
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
    synapse_app: Application,
    get_unit_ips: typing.Callable[[str], typing.Awaitable[tuple[str, ...]]],
    access_token: str,
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

    await model.add_relation(f"{s3_integrator_app_media.name}", f"{synapse_app.name}:media")
    await model.wait_for_idle(
        idle_period=30,
        apps=[synapse_app.name, s3_integrator_app_media.name],
        status=ACTIVE_STATUS_NAME,
    )

    synapse_ip = (await get_unit_ips(synapse_app.name))[0]
    headers = {
        "Authorization": f"Bearer {access_token}",
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
