# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Synapse backup unit tests."""

# pylint: disable=protected-access

import io
import tarfile
from secrets import token_hex
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

import backup


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


def test_create_tar_from_files(tmp_path):
    """
    arrange: Create two files inside a directory with data.
    act: Call tar_file_generator with the directory and the two files.
    assert: Check that all the files and dir are in the tar. In the case
       of the files, check that the files have the correct content.
    """
    base_dir = tmp_path
    media = base_dir / "media"
    media.mkdir()
    f1 = media / "f1.txt"
    f1.write_text("Text 1" * 1000, encoding="utf-8")
    f2 = media / "f2.txt"
    f2.write_bytes(b"\x00\x00" * 5000)
    files_to_tar = [
        media.relative_to(base_dir),
        f1.relative_to(base_dir),
        f2.relative_to(base_dir),
    ]

    gen = backup.tar_file_generator(files_to_tar, base_dir)

    tarfileobj = io.BytesIO(b"".join(gen))
    with tarfile.open(fileobj=tarfileobj) as tar:
        assert len(tar.getmembers()) == 3
        assert tar.getmember(str(media.relative_to(base_dir))).isdir()
        assert tar.getmember(str(f1.relative_to(base_dir))).isfile()
        f1tarobj = tar.extractfile(str(f1.relative_to(base_dir)))
        assert f1tarobj and f1tarobj.read() == f1.open("rb").read()
        assert tar.getmember(str(f2.relative_to(base_dir))).isfile()
        f2tarobj = tar.extractfile(str(f2.relative_to(base_dir)))
        assert f2tarobj and f2tarobj.read() == f2.open("rb").read()


def test_encrypt():
    """
    arrange: Given some plain text (binary) to encrypt and a password, split it so it is an
        iterable.
    act: Encrypt with the encrypt_generator.
    assert: Check that the encrypted text is different from the plain. Also
        decrypt and check that it is equal to the plain text.
    """
    plain_text = b"some text to encrypt\n with several\n lines"
    plain_text_split = plain_text.splitlines(keepends=True)
    password = token_hex(16)

    encrypted_text = b"".join(backup.encrypt_generator(plain_text_split, password))

    decrypted_text = b"".join(backup.decrypt_generator([encrypted_text], password))
    assert decrypted_text == plain_text
