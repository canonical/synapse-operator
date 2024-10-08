# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Synapse backup observer unit tests."""

import datetime
from secrets import token_hex
from typing import Type
from unittest.mock import ANY, MagicMock

import ops
import pytest
from ops.testing import ActionFailed, Harness

import backup
import synapse


@pytest.mark.parametrize(
    "relation_data, can_use_bucket, expected_status_cls, expected_str_in_status",
    [
        pytest.param(
            {
                "access-key": token_hex(16),
                "secret-key": token_hex(16),
                "region": "eu-west-1",
                "bucket": "synapse-backup-bucket",
                "endpoint": "https:/example.com",
                "path": "/synapse-backups",
                "s3-uri-style": "path",
            },
            True,
            ops.BlockedStatus,
            "configuration is invalid",
            id="Correct S3 configuration",
        ),
        pytest.param(
            {
                "access-key": token_hex(16),
                "secret-key": token_hex(16),
                "region": "eu-west-1",
                "bucket": "synapse-backup-bucket",
                "endpoint": "https://example.com",
                "path": "/synapse-backups",
                "s3-uri-style": "path",
            },
            True,
            ops.ActiveStatus,
            "",
            id="Invalid S3 endpoint",
        ),
        pytest.param(
            {
                "access-key": token_hex(16),
                "secret-key": token_hex(16),
            },
            True,
            ops.BlockedStatus,
            "S3 configuration is invalid",
            id="Invalid S3 configuration",
        ),
        pytest.param(
            {
                "access-key": token_hex(16),
                "secret-key": token_hex(16),
                "region": "eu-west-1",
                "bucket": "synapse-backup-bucket",
                "s3-uri-style": "path",
            },
            False,
            ops.BlockedStatus,
            "bucket does not exist",
            id="Bucket does not exist or not accessible",
        ),
    ],
)
def test_on_s3_credentials_changed(  # pylint: disable=too-many-positional-arguments
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
    relation_data: dict,
    can_use_bucket: bool,
    expected_status_cls: Type,
    expected_str_in_status: str,
):
    """
    arrange: start the Synapse charm. Mock function can_use_bucket as the pytest param.
    act: Add integration with s3-integrator.
    assert: The unit should be in the expected state with the expected message.
    """
    # pylint: disable=too-many-arguments
    monkeypatch.setattr(backup.S3Client, "can_use_bucket", MagicMock(return_value=can_use_bucket))
    harness.begin_with_initial_hooks()

    harness.add_relation("backup", "s3-integrator", app_data=relation_data)

    assert isinstance(harness.model.unit.status, expected_status_cls)
    assert expected_str_in_status in str(harness.model.unit.status)


def test_on_s3_credentials_gone_set_active(harness: Harness):
    """
    arrange: start the Synapse charm. Integrate with s3-integrator with missing data,
       so the charm is in blocked status.
    act: Remove the s3-integratior integration
    assert: The unit should be active.
    """
    s3_relation_data = {
        "access-key": token_hex(16),
        "secret-key": token_hex(16),
    }
    relation_id = harness.add_relation("backup", "s3-integrator", app_data=s3_relation_data)
    harness.begin_with_initial_hooks()

    harness.remove_relation(relation_id)

    assert harness.model.unit.status == ops.ActiveStatus()


def test_create_backup_correct(
    s3_relation_data_backup, harness: Harness, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: start the Synapse charm. Integrate with s3-integrator.
        Mock can_use_bucket and create_backup.
    act: Run the backup action.
    assert: Backup should end correctly, returning correct and the backup name.
    """
    monkeypatch.setattr(backup.S3Client, "can_use_bucket", MagicMock(return_value=True))
    create_backup = MagicMock()
    monkeypatch.setattr(backup, "create_backup", create_backup)

    harness.update_config({"backup_passphrase": token_hex(16)})
    harness.add_relation("backup", "s3-integrator", app_data=s3_relation_data_backup)
    harness.begin_with_initial_hooks()

    output = harness.run_action("create-backup")
    create_backup.assert_called_once()
    assert "backup-id" in output.results
    assert output.results["result"] == "correct"


def test_create_backup_no_passphrase(
    s3_relation_data_backup, harness: Harness, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: start the Synapse charm. Integrate with s3-integrator.
        Mock can_use_bucket to True and do not set backup_password.
    act: Run the backup action.
    assert: Backup should fail because of missing backup_passphrase.
    """
    monkeypatch.setattr(backup.S3Client, "can_use_bucket", MagicMock(return_value=True))
    monkeypatch.setattr(
        backup, "create_backup", MagicMock(side_effect=backup.S3Error("Generic Error"))
    )

    harness.add_relation("backup", "s3-integrator", app_data=s3_relation_data_backup)
    harness.begin_with_initial_hooks()

    with pytest.raises(ActionFailed) as err:
        harness.run_action("create-backup")
    assert "Missing backup_passphrase" in str(err.value.message)


def test_create_backup_wrong_backup_failure(
    s3_relation_data_backup, harness: Harness, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: start the Synapse charm. Integrate with s3-integrator. Mock create_backup
        to fail.
    act: Run the backup action.
    assert: Backup should fail with error
    """
    monkeypatch.setattr(backup.S3Client, "can_use_bucket", MagicMock(return_value=True))
    monkeypatch.setattr(
        backup, "create_backup", MagicMock(side_effect=backup.BackupError("Generic Error"))
    )

    harness.add_relation("backup", "s3-integrator", app_data=s3_relation_data_backup)
    harness.begin_with_initial_hooks()
    harness.update_config({"backup_passphrase": token_hex(16)})

    with pytest.raises(ActionFailed) as err:
        harness.run_action("create-backup")
    assert "Error Creating Backup" in str(err.value.message)


def test_create_backup_wrong_s3_parameters(harness: Harness):
    """
    arrange: start the Synapse charm. Do not integrate with S3.
    act: Run the backup action.
    assert: Backup should fail with error because there is no S3 integration
    """
    harness.begin_with_initial_hooks()
    harness.update_config({"backup_passphrase": token_hex(16)})

    with pytest.raises(ActionFailed) as err:
        harness.run_action("create-backup")
    assert "Wrong S3 configuration" in str(err.value.message)


def test_list_backups_correct(
    s3_relation_data_backup: dict, harness: Harness, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: Start the Synapse charm. Integrate with S3. Mock can_use_bucket and
        backup.list_backups to return backups.
    act: Run action list-backups.
    assert: Check that the backups and the formatted output is correct.
    """
    harness.add_relation("backup", "s3-integrator", app_data=s3_relation_data_backup)
    monkeypatch.setattr(backup.S3Client, "can_use_bucket", MagicMock(return_value=True))
    backups = [
        backup.S3Backup(
            backup_id="202301311259",
            last_modified=datetime.datetime(2024, 1, 1, 0, 0, 0),
            size=1_000_000_000_000,
        ),
        backup.S3Backup(
            backup_id="202401311259",
            last_modified=datetime.datetime(2024, 2, 1, 0, 0, 0),
            size=20_000_000_000_000,
        ),
    ]

    monkeypatch.setattr(backup.S3Client, "list_backups", MagicMock(return_value=backups))

    harness.begin_with_initial_hooks()
    action = harness.run_action("list-backups")
    results = action.results
    assert results["backups"] == {
        "202301311259": {"last-modified": "2024-01-01 00:00:00", "size": "1000000000000"},
        "202401311259": {"last-modified": "2024-02-01 00:00:00", "size": "20000000000000"},
    }

    expected_formatted_output = """
backup-id                     | last-modified                |            size
------------------------------------------------------------------------------
202301311259                  | 2024-01-01 00:00:00          |   1000000000000
202401311259                  | 2024-02-01 00:00:00          |  20000000000000"""
    assert "\n" + results["formatted"] == expected_formatted_output


def test_restore_backup_correct(
    s3_relation_data_backup, harness: Harness, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: Start the Synapse charm. Integrate with s3-integrator.
        Mock can_use_bucket, exists_backup and restore_backup.
    act: Run the restore backup action with a backup-id.
    assert: Backup should be restored. restore_backup should be called.
    """
    monkeypatch.setattr(backup.S3Client, "can_use_bucket", MagicMock(return_value=True))
    monkeypatch.setattr(backup.S3Client, "exists_backup", MagicMock(return_value=True))
    restore_backup = MagicMock()
    monkeypatch.setattr(backup, "restore_backup", restore_backup)
    backup_passphrase = token_hex(16)
    harness.update_config({"backup_passphrase": backup_passphrase})
    harness.add_relation("backup", "s3-integrator", app_data=s3_relation_data_backup)
    harness.begin_with_initial_hooks()

    output = harness.run_action("restore-backup", params={"backup-id": "backup-2024"})

    assert output.results["result"] == "correct"
    container = harness.model.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
    restore_backup.assert_called_once_with(container, ANY, backup_passphrase, "backup-2024")


def test_restore_backup_wrong_s3_parameters(harness: Harness):
    """
    arrange: start the Synapse charm. Do not integrate with S3.
    act: Run the restore action.
    assert: Backup should fail with error because there is no S3 integration
    """
    harness.begin_with_initial_hooks()
    harness.update_config({"backup_passphrase": token_hex(16)})

    with pytest.raises(ActionFailed) as err:
        harness.run_action("restore-backup", params={"backup-id": "backup-2024"})
    assert "Wrong S3 configuration" in str(err.value.message)


def test_restore_backup_does_not_exist(
    s3_relation_data_backup, harness: Harness, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: start the Synapse charm. Integrate with s3-integrator.
        Mock can_use_bucket to True and exists_backup to False.
    act: Run the restore action.
    assert: Backup should fail because of missing backup_passphrase.
    """
    monkeypatch.setattr(backup.S3Client, "can_use_bucket", MagicMock(return_value=True))
    monkeypatch.setattr(backup.S3Client, "exists_backup", MagicMock(return_value=False))

    harness.add_relation("backup", "s3-integrator", app_data=s3_relation_data_backup)
    harness.begin_with_initial_hooks()

    with pytest.raises(ActionFailed) as err:
        harness.run_action("restore-backup", params={"backup-id": "backup-2024"})
    assert "does not exist" in str(err.value.message)


def test_restore_backup_no_passphrase(
    s3_relation_data_backup, harness: Harness, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: start the Synapse charm. Integrate with s3-integrator.
        Mock can_use_bucket to True, exists_backup and do not set backup_password.
    act: Run the restore action.
    assert: Backup should fail because of missing backup_passphrase.
    """
    monkeypatch.setattr(backup.S3Client, "can_use_bucket", MagicMock(return_value=True))
    monkeypatch.setattr(backup.S3Client, "exists_backup", MagicMock(return_value=True))

    harness.add_relation("backup", "s3-integrator", app_data=s3_relation_data_backup)
    harness.begin_with_initial_hooks()

    with pytest.raises(ActionFailed) as err:
        harness.run_action("restore-backup", params={"backup-id": "backup-2024"})
    assert "Missing backup_passphrase" in str(err.value.message)


def test_restore_backup_wrong_restore_failure(
    s3_relation_data_backup, harness: Harness, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: start the Synapse charm. Integrate with s3-integrator. Mock exists_backup
        and restore_backup to fail.
    act: Run the restore action.
    assert: Backup should fail with error
    """
    monkeypatch.setattr(backup.S3Client, "can_use_bucket", MagicMock(return_value=True))
    monkeypatch.setattr(backup.S3Client, "exists_backup", MagicMock(return_value=True))
    monkeypatch.setattr(
        backup, "restore_backup", MagicMock(side_effect=backup.BackupError("Generic Error"))
    )

    harness.add_relation("backup", "s3-integrator", app_data=s3_relation_data_backup)
    harness.begin_with_initial_hooks()
    harness.update_config({"backup_passphrase": token_hex(16)})

    with pytest.raises(ActionFailed) as err:
        harness.run_action("restore-backup", params={"backup-id": "backup-2024"})
    assert "Error Restoring Backup" in str(err.value.message)


def test_delete_backup_correct(
    s3_relation_data_backup: dict, harness: Harness, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: Start the Synapse charm. Integrate with S3. Mock can_use_bucket, exists_backup and
        backup.delete_backup.
    act: Run action delete-backup.
    assert: Response is correct and s3 client delete_backup is called with the correct args.
    """
    harness.add_relation("backup", "s3-integrator", app_data=s3_relation_data_backup)
    monkeypatch.setattr(backup.S3Client, "can_use_bucket", MagicMock(return_value=True))
    monkeypatch.setattr(backup.S3Client, "exists_backup", MagicMock(return_value=True))
    delete_backup_mock = MagicMock()
    monkeypatch.setattr(backup.S3Client, "delete_backup", delete_backup_mock)

    harness.begin_with_initial_hooks()
    action = harness.run_action("delete-backup", params={"backup-id": "backup-2024"})

    assert action.results["result"] == "correct"
    delete_backup_mock.assert_called_once_with("backup-2024")


def test_delete_backup_does_not_exist(
    s3_relation_data_backup: dict, harness: Harness, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: Start the Synapse charm. Integrate with S3. Mock can_use_bucket, exists_backup and
        backup.delete_backup.
    act: Run action delete-backup.
    assert: Does not raise, but the result shows that the backup does not exist
        and s3 client delete_backup is not called.
    """
    harness.add_relation("backup", "s3-integrator", app_data=s3_relation_data_backup)
    monkeypatch.setattr(backup.S3Client, "can_use_bucket", MagicMock(return_value=True))
    monkeypatch.setattr(backup.S3Client, "exists_backup", MagicMock(return_value=False))
    delete_backup_mock = MagicMock()
    monkeypatch.setattr(backup.S3Client, "delete_backup", delete_backup_mock)

    harness.begin_with_initial_hooks()

    action = harness.run_action("delete-backup", params={"backup-id": "backup-2024"})

    assert "does not exist" in action.results["result"]
    delete_backup_mock.assert_not_called()


def test_delete_backup_s3_error(
    s3_relation_data_backup: dict, harness: Harness, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: Start the Synapse charm. Integrate with S3. Mock can_use_bucket, exists_backup
        and backup.delete_backup to raise S3Error.
    act: Run action delete-backup.
    assert: Raises ActionFailed.
    """
    harness.add_relation("backup", "s3-integrator", app_data=s3_relation_data_backup)
    monkeypatch.setattr(backup.S3Client, "can_use_bucket", MagicMock(return_value=True))
    monkeypatch.setattr(backup.S3Client, "exists_backup", MagicMock(return_value=True))
    delete_backup_mock = MagicMock(side_effect=backup.S3Error("Error"))
    monkeypatch.setattr(backup.S3Client, "delete_backup", delete_backup_mock)

    harness.set_leader(True)
    harness.begin_with_initial_hooks()

    with pytest.raises(ActionFailed) as err:
        harness.run_action("delete-backup", params={"backup-id": "backup-2024"})
    assert "Error deleting backup" in str(err.value.message)
