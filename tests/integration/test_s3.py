#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for Synapse charm needing the s3_backup_bucket fixture."""
import logging
import typing
from secrets import token_hex

import magic
import pytest
from juju.action import Action
from juju.application import Application
from juju.model import Model
from juju.unit import Unit
from ops.model import ActiveStatus

# caused by pytest fixtures
# pylint: disable=too-many-arguments

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
    assert "GPG symmetrically encrypted data (AES256 cipher)" in magic.from_buffer(objbuf)


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


# @pytest.mark.s3
# @pytest.mark.usefixtures("s3_storage")
# async def test_synapse_media_upload(
#     model: Model,
#     synapse_app: Application,
#     s3_integrator_app_storage: Application,
#     s3_storage_configuration: dict,
#     boto_s3_client: typing.Any,
# ):
#     """
#     arrange: Synapse App deployed and related with s3-integrator. Set media_store_bucket.
#     act: Upload media to Synapse.
#     assert: The media is in the S3 bucket.
#     """
#     await model.add_relation(s3_integrator_app_storage.name, f"{synapse_app.name}:storage")
#     await synapse_app.set_config({"media_store_bucket": s3_storage_configuration["bucket"]})
#     await model.wait_for_idle(
#         idle_period=30,
#         apps=[synapse_app.name, s3_integrator_app_storage.name],
#         status=ACTIVE_STATUS_NAME,
#     )

#     # unsure about whether this is the correct way to do this.
#     synapse_unit: Unit = next(iter(synapse_app.units))
#     media_id = token_hex(16)
#     media_content = b"Hello, World!"
#     synapse_unit.run("/snap/bin/synapse.upload-media", media_id, stdin=media_content)

#     s3objresp = boto_s3_client.get_object(
#         Bucket=s3_storage_configuration["bucket"], Key=f"media/{media_id}"
#     )
#     objbuf = s3objresp["Body"].read()
#     assert objbuf == media_content
