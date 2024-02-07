# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Synapse backup unit tests."""

# pylint: disable=protected-access

import datetime
import os
import pathlib
from secrets import token_hex
from unittest.mock import MagicMock

import pytest
import yaml
from botocore.exceptions import ClientError
from dateutil.tz import tzutc  # type: ignore
from ops.testing import Harness

import backup
import synapse


def test_s3_relation_validation_fails_when_region_and_endpoint_not_set():
    """
    arrange: Create s3 relation data without region nor endpoint.
    act: Create S3Parameters pydantic BaseModel from relation data.
    assert: Raises ValueError as one of those two fields should be set.
    """
    s3_relation_data = {
        "access-key": token_hex(16),
        "secret-key": token_hex(16),
        "bucket": "backup-bucket",
        "path": "/synapse-backups",
        "s3-uri-style": "path",
    }

    with pytest.raises(ValueError):
        backup.S3Parameters(**s3_relation_data)


@pytest.mark.parametrize(
    "s3_relation_data",
    [
        pytest.param(
            {
                "access-key": token_hex(16),
                "secret-key": token_hex(16),
                "bucket": "backup-bucket",
                "region": "us-west-2",
            },
            id="region defined but not endpoint",
        ),
        pytest.param(
            {
                "access-key": token_hex(16),
                "secret-key": token_hex(16),
                "bucket": "backup-bucket",
                "endpoint": "https://s3.example.com",
            },
            id="endpoint defined but not region",
        ),
        pytest.param(
            {
                "access-key": token_hex(16),
                "secret-key": token_hex(16),
                "bucket": "backup-bucket",
                "region": "us-west-2",
                "endpoint": "https://s3.example.com",
            },
            id="both region and endpoint defined",
        ),
    ],
)
def test_s3_relation_validation_correct(s3_relation_data):
    """
    arrange: Create s3 relation data with correct data.
    act: Create S3Parameters pydantic BaseModel from relation data.
    assert: Relation data does not raise and region and endpoint equal
        to the original values.
    """
    s3_parameters = backup.S3Parameters(**s3_relation_data)
    assert s3_parameters.endpoint == s3_relation_data.get("endpoint")
    assert s3_parameters.region == s3_relation_data.get("region")


@pytest.mark.parametrize(
    "s3_relation_data, addressing_style",
    [
        pytest.param(
            {
                "access-key": token_hex(16),
                "secret-key": token_hex(16),
                "bucket": "backup-bucket",
                "region": "us-west-2",
                "s3-uri-style": "path",
            },
            "path",
            id="uri style path",
        ),
        pytest.param(
            {
                "access-key": token_hex(16),
                "secret-key": token_hex(16),
                "bucket": "backup-bucket",
                "region": "us-west-2",
                "s3-uri-style": "host",
            },
            "virtual",
            id="uri style host",
        ),
    ],
)
def test_s3_relation_data_addressing_style(s3_relation_data, addressing_style):
    """
    arrange: Create s3 relation data with correct data.
    act: Create S3Parameters pydantic BaseModel from relation data.
    assert: Check that the addressing style correspond to the expected value.
    """
    s3_parameters = backup.S3Parameters(**s3_relation_data)
    assert s3_parameters.addressing_style == addressing_style


def test_s3_client_create_correct(s3_parameters_backup):
    """
    arrange: Create S3Parameters for the new client.
    act: Create the new client.
    assert: The client gets created correctly.
    """
    s3_client = backup.S3Client(s3_parameters_backup)

    assert s3_client._client


def test_s3_client_create_error(s3_parameters_backup):
    """
    arrange: Create S3Parameters for the new client.
        Put access_key for the boto3 client to fail.
    act: Create the new client.
    assert: Raises S3Error.
    """
    s3_parameters_backup.access_key = None

    with pytest.raises(backup.S3Error) as err:
        backup.S3Client(s3_parameters_backup)
    assert "Error creating S3 client" in str(err.value)


def test_can_use_bucket_correct(s3_parameters_backup, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: Create S3Parameters and mock boto3 client so it does not raise on head_bucket.
    act: Run S3Client.can_use_bucket.
    assert: Check that the function returns True.
    """
    s3_client = backup.S3Client(s3_parameters_backup)
    monkeypatch.setattr(s3_client._client, "head_bucket", MagicMock())

    assert s3_client.can_use_bucket()


def test_can_use_bucket_bucket_error(s3_parameters_backup, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: Create S3Parameters and mock boto3 library so it fails when checking the bucket.
    act: Run can_use_bucket.
    assert: Check that the function returns False.
    """
    s3_client = backup.S3Client(s3_parameters_backup)
    monkeypatch.setattr(
        s3_client._client, "head_bucket", MagicMock(side_effect=ClientError({}, "HeadBucket"))
    )

    assert not s3_client.can_use_bucket()


def test_list_backups_correct(s3_parameters_backup, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: Create a S3Client. Mock response to return a real one in list_backups.
    act: run list_backups.
    assert: The expected list of backups is correctly parsed.
    """
    s3_client = backup.S3Client(s3_parameters_backup)
    s3_example_response = {
        "ResponseMetadata": {
            "RequestId": "17AFBDF4A3306A4F",
            "HostId": "dd9025bab4ad464b049177c95eb6ebf374d3b3fd1af9251148b658df7ac2e3e8",
            "HTTPStatusCode": 200,
        },
        "IsTruncated": False,
        "Contents": [
            {
                "Key": "synapse-backups/20240201122721",
                "LastModified": datetime.datetime(2024, 2, 1, 12, 27, 23, 749000, tzinfo=tzutc()),
                "ETag": '"ed4a010045db523f7adc1ddc19e26971"',
                "Size": 38296,
            },
            {
                "Key": "synapse-backups/20240201122942",
                "LastModified": datetime.datetime(2024, 2, 1, 12, 29, 43, 804000, tzinfo=tzutc()),
                "ETag": '"200e44b3b6e4c1e98b1a902e5260b9be"',
                "Size": 50000,
            },
        ],
        "Name": "backups-bucket",
        "Prefix": "synapse-backups",
        "MaxKeys": 1000,
        "EncodingType": "url",
        "KeyCount": 2,
    }
    list_objects_v2_mock = MagicMock(return_value=s3_example_response)
    monkeypatch.setattr(s3_client._client, "list_objects_v2", list_objects_v2_mock)

    backups = s3_client.list_backups()

    assert backups == [
        backup.S3Backup(
            backup_id="20240201122721",
            etag='"ed4a010045db523f7adc1ddc19e26971"',
            last_modified=datetime.datetime(2024, 2, 1, 12, 27, 23, 749000, tzinfo=tzutc()),
            prefix="synapse-backups",
            s3_object_key="synapse-backups/20240201122721",
            size=38296,
        ),
        backup.S3Backup(
            backup_id="20240201122942",
            etag='"200e44b3b6e4c1e98b1a902e5260b9be"',
            last_modified=datetime.datetime(2024, 2, 1, 12, 29, 43, 804000, tzinfo=tzutc()),
            prefix="synapse-backups",
            s3_object_key="synapse-backups/20240201122942",
            size=50000,
        ),
    ]


def test_list_backups_correct_no_root_slash(s3_parameters_backup, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: Create a S3Client. Mock response to return a real one in list_backups with Keys
        without root slash as returned by MinIO even when created with them.
    act: run list_backups.
    assert: The expected list of backups is correctly parsed.
    """
    s3_parameters_backup.path = s3_parameters_backup.path.strip("/")
    s3_client = backup.S3Client(s3_parameters_backup)
    s3_example_response = {
        "ResponseMetadata": {
            "RequestId": "17AFBDF4A3306A4F",
            "HostId": "dd9025bab4ad464b049177c95eb6ebf374d3b3fd1af9251148b658df7ac2e3e8",
            "HTTPStatusCode": 200,
        },
        "IsTruncated": False,
        "Contents": [
            {
                "Key": "synapse-backups/20240201122942",
                "LastModified": datetime.datetime(2024, 2, 1, 12, 29, 43, 804000, tzinfo=tzutc()),
                "ETag": '"200e44b3b6e4c1e98b1a902e5260b9be"',
                "Size": 50000,
            },
        ],
        "Name": "backups-bucket",
        "Prefix": "synapse-backups/",
        "MaxKeys": 1000,
        "EncodingType": "url",
        "KeyCount": 2,
    }
    list_objects_v2_mock = MagicMock(return_value=s3_example_response)
    monkeypatch.setattr(s3_client._client, "list_objects_v2", list_objects_v2_mock)

    backups = s3_client.list_backups()

    assert backups == [
        backup.S3Backup(
            backup_id="20240201122942",
            etag='"200e44b3b6e4c1e98b1a902e5260b9be"',
            last_modified=datetime.datetime(2024, 2, 1, 12, 29, 43, 804000, tzinfo=tzutc()),
            prefix="synapse-backups",
            s3_object_key="synapse-backups/20240201122942",
            size=50000,
        ),
    ]


def test_list_backups_empty(s3_parameters_backup, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: Create a S3Client. Mock response to return a real one in list_backups without backups.
    act: run list_backups.
    assert: The expected list of backups is correctly parsed.
    """
    s3_client = backup.S3Client(s3_parameters_backup)
    s3_example_response = {
        "ResponseMetadata": {
            "RequestId": "17AFBDF4A3306A4F",
            "HostId": "dd9025bab4ad464b049177c95eb6ebf374d3b3fd1af9251148b658df7ac2e3e8",
            "HTTPStatusCode": 200,
        },
        "IsTruncated": False,
        "Name": "backups-bucket",
        "Prefix": "synapse",
        "MaxKeys": 1000,
        "EncodingType": "url",
        "KeyCount": 0,
    }
    list_objects_v2_mock = MagicMock(return_value=s3_example_response)
    monkeypatch.setattr(s3_client._client, "list_objects_v2", list_objects_v2_mock)

    backups = s3_client.list_backups()

    assert not backups


def test_list_backups_error(s3_parameters_backup, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: Create a S3Client. Mock response to raise a ClienError Exception.
    act: run list_backups.
    assert: A S3Error should be raised.
    """
    s3_client = backup.S3Client(s3_parameters_backup)
    list_objects_v2_mock = MagicMock(side_effect=ClientError({}, "No Such Bucket"))
    monkeypatch.setattr(s3_client._client, "list_objects_v2", list_objects_v2_mock)

    with pytest.raises(backup.S3Error) as err:
        s3_client.list_backups()
    assert "Error listing" in str(err.value)


def test_create_backup_correct(
    harness: Harness, s3_parameters_backup, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: Given the Synapse container, s3parameters, passphrase, the backup key and its location
        mock prepare_container, calculate_size and get paths
    act: Call create_backup
    assert: A command is executed to backup and has at least the paths.
    """
    container = harness.model.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
    passphrase = token_hex(16)
    monkeypatch.setattr(backup, "_prepare_container", MagicMock())
    monkeypatch.setattr(backup, "_calculate_size", MagicMock(return_value=1000))
    monkeypatch.setattr(backup, "_get_paths_to_backup", MagicMock(return_value=["file1", "dir1"]))

    def backup_command_handler(args: list[str]) -> synapse.ExecResult:
        """Handler for the exec of the backup command.

        Args:
            args: argument given to the container.exec.

        Returns:
            tuple with status_code, stdout and stderr.
        """
        # simple check to see that at least the files are in the command
        assert any(("'file1'" in arg for arg in args))
        assert any(("'dir1'" in arg for arg in args))
        return synapse.ExecResult(0, "", "")

    harness.register_command_handler(  # type: ignore # pylint: disable=no-member
        container=container,
        executable=backup.BASH_COMMAND,
        handler=backup_command_handler,
    )

    backup.create_backup(container, s3_parameters_backup, passphrase)


def test_create_backup_no_files(
    harness: Harness, s3_parameters_backup, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: Given the Synapse container, s3parameters, passphrase, the backup key and its location
        mock _prepare_container, calculate_size and get paths. get paths is empty
    act: Call create_backup
    assert: BackupError exception because there is nothing to back up
    """
    container = harness.model.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
    passphrase = token_hex(16)
    monkeypatch.setattr(backup, "_prepare_container", MagicMock())
    monkeypatch.setattr(backup, "_calculate_size", MagicMock(return_value=1000))
    monkeypatch.setattr(backup, "_get_paths_to_backup", MagicMock(return_value=[]))
    with pytest.raises(backup.BackupError) as err:
        backup.create_backup(container, s3_parameters_backup, passphrase)
    assert "No paths to back up" in str(err.value)


def test_create_backup_failure(
    harness: Harness, s3_parameters_backup, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: Given the Synapse container, s3parameters, passphrase, the backup key and its location
        mock prepare_container, calculate_size and get paths. Mock the backup command to fail
    act: Call create_backup
    assert: BackupError exception because the back up failed
    """
    container = harness.model.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
    passphrase = token_hex(16)
    monkeypatch.setattr(backup, "_prepare_container", MagicMock())
    monkeypatch.setattr(backup, "_calculate_size", MagicMock(return_value=1000))
    monkeypatch.setattr(backup, "_get_paths_to_backup", MagicMock(return_value=["file1", "dir1"]))

    def backup_command_handler(_: list[str]) -> synapse.ExecResult:
        """Handler for the exec of the backup command.

        Returns:
            tuple with status_code, stdout and stderr.
        """
        return synapse.ExecResult(1, "", "")

    harness.register_command_handler(  # type: ignore # pylint: disable=no-member
        container=container,
        executable=backup.BASH_COMMAND,
        handler=backup_command_handler,
    )
    with pytest.raises(backup.BackupError) as err:
        backup.create_backup(container, s3_parameters_backup, passphrase)
    assert "Backup Command Failed" in str(err.value)


def test_prepare_container_correct(harness: Harness, s3_parameters_backup):
    """
    arrange: Given the Synapse container, s3parameters, passphrase and its location
    act: Call _prepare_container
    assert: The file with the passphare is in the container. AWS commands did not fail.
    """
    passphrase = token_hex(16)
    container = harness.model.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
    synapse_root = harness.get_filesystem_root(container)
    passphrase_relative_dir = pathlib.Path(backup.PASSPHRASE_FILE).relative_to("/").parent
    passphrase_dir = synapse_root / passphrase_relative_dir
    passphrase_dir.mkdir(exist_ok=True)

    def aws_command_handler(argv: list[str]) -> synapse.ExecResult:
        """Handler for the exec of the aws command.

        Args:
            argv: argument given to the container.exec.

        Returns:
            tuple with status_code, stdout and stderr.
        """
        assert argv[0:3] == [
            backup.AWS_COMMAND,
            "configure",
            "set",
        ]
        # let the rest of checks for the integration tests.
        return synapse.ExecResult(0, "", "")

    harness.register_command_handler(  # type: ignore # pylint: disable=no-member
        container=container,
        executable=backup.AWS_COMMAND,
        handler=aws_command_handler,
    )

    backup._prepare_container(container, s3_parameters_backup, passphrase)

    assert container.pull(backup.PASSPHRASE_FILE).read() == passphrase


def test_prepare_container_error_aws(harness: Harness, s3_parameters_backup):
    """
    arrange: Given the Synapse container, s3parameters, passphrase and its location
        mock container.exec when aws commands are called.
    act: Call prepare_container
    assert: BackupError exception is raised.
    """
    passphrase = token_hex(16)
    container = harness.model.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
    synapse_root = harness.get_filesystem_root(container)
    passphrase_relative_dir = pathlib.Path(backup.PASSPHRASE_FILE).relative_to("/").parent
    passphrase_dir = synapse_root / passphrase_relative_dir
    passphrase_dir.mkdir(exist_ok=True)

    def aws_command_handler(_: list[str]) -> synapse.ExecResult:
        """Handler for the exec of the aws command.

        Returns:
            tuple with status_code, stdout and stderr.
        """
        # let the rest of checks for the integration tests.
        return synapse.ExecResult(1, "", "error")

    harness.register_command_handler(  # type: ignore # pylint: disable=no-member
        container=container,
        executable=backup.AWS_COMMAND,
        handler=aws_command_handler,
    )

    with pytest.raises(backup.BackupError) as err:
        backup._prepare_container(container, s3_parameters_backup, passphrase)
    assert "Error configuring AWS" in str(err.value)


def test_build_backup_command_correct(s3_parameters_backup):
    """
    arrange: Given some s3 parameters for backup, a name for the key in the bucket,
         paths, passphrase file location and passphrase file
    act: run _build_backup_command
    assert: the command is the correct calling bash with pipes.
    """
    # pylint: disable=line-too-long
    paths_to_backup = ["/data/homeserver.db", "/data/example.com.signing.key"]

    command = backup._build_backup_command(
        s3_parameters_backup, "20230101231200", paths_to_backup, "/root/.gpg_passphrase", 1000
    )

    assert list(command) == [
        backup.BASH_COMMAND,
        "-c",
        f"set -euxo pipefail; tar -c '/data/homeserver.db' '/data/example.com.signing.key' | gpg --batch --no-symkey-cache --passphrase-file '/root/.gpg_passphrase' --symmetric | {backup.AWS_COMMAND} s3 cp --expected-size=1000 - 's3://synapse-backup-bucket/synapse-backups/20230101231200'",  # noqa: E501
    ]


def test_get_paths_to_backup_correct(harness: Harness):
    """
    arrange: Create a container filesystem like the one in Synapse, with data and config.
    act: Run get_paths_to_backup.
    assert: Check that sqlite homeserver db, the signing key and the local media paths are
        in the paths to backup, and nothing else.
    """
    container = harness.model.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
    synapse_root = harness.get_filesystem_root(container)

    data_dir = synapse_root / pathlib.Path(synapse.SYNAPSE_DATA_DIR).relative_to("/")
    (data_dir / "homeserver.db").open("w").write("backup")
    media_dir = data_dir / "media"
    media_dir.mkdir()
    local_content_dir = media_dir / "local_content"
    local_content_dir.mkdir()
    (local_content_dir / "onefile").open("w").write("backup")
    remote_content_dir = media_dir / "remote_content"
    remote_content_dir.mkdir()
    (remote_content_dir / "onefile").open("w").write("do not backup")

    config_dir = synapse_root / pathlib.Path(synapse.SYNAPSE_CONFIG_DIR).relative_to("/")
    (config_dir / "example.com.signing.key").open("w").write("backup")
    (config_dir / "log.config").open("w").write("do not backup")
    media_storage_path = "/" / media_dir.relative_to(synapse_root)
    homeserver = yaml.safe_dump({"media_store_path": str(media_storage_path)})
    (config_dir / "homeserver.yaml").open("w").write(homeserver)

    paths_to_backup = list(backup._get_paths_to_backup(container))

    assert len(paths_to_backup) == 3
    assert os.path.join(synapse.SYNAPSE_CONFIG_DIR, "example.com.signing.key") in paths_to_backup
    assert os.path.join(synapse.SYNAPSE_DATA_DIR, "homeserver.db") in paths_to_backup
    assert os.path.join(synapse.SYNAPSE_DATA_DIR, "media", "local_content") in paths_to_backup


def test_get_paths_to_backup_empty(harness: Harness):
    """
    arrange: Create an empty container filesystem.
    act: Call get_paths_to_backup
    assert: The paths to backup should be empty.
    """
    container = harness.model.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)

    paths_to_backup = list(backup._get_paths_to_backup(container))

    assert len(paths_to_backup) == 0


def test_calculate_size(harness: Harness):
    """
    arrange: given a container and a list of paths
    act: call backup.calculate_size
    assert: exec is run in the container, with the correct command and the stdout is parsed to int.
    """
    container = harness.model.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
    paths = ["path1", "path2"]

    def du_handler(argv: list[str]) -> synapse.ExecResult:
        """Handler for the exec of bash.

        Args:
            argv: argument given to the container.exec.

        Returns:
            tuple with status_code, stdout and stderr.
        """
        assert argv == [
            "/usr/bin/bash",
            "-c",
            "set -euxo pipefail; du -bsc 'path1' 'path2' | tail -n1 | cut -f 1",
        ]
        return synapse.ExecResult(0, "1000", "")

    # A better option would be to use run harness.handle_exec,
    # but the harness is monkey patched in conftest.py
    harness.register_command_handler(  # type: ignore # pylint: disable=no-member
        container=container,
        executable="/usr/bin/bash",
        handler=du_handler,
    )

    size = backup._calculate_size(container, paths)

    assert size == 1000
