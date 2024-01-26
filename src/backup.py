# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Provides backup functionality for Synapse."""

import hashlib
import io
import logging
import os
import tarfile
from typing import Any, Generator, Iterable, List, Optional

from aws_encryption_sdk import EncryptionSDKClient
from aws_encryption_sdk.identifiers import (
    Algorithm,
    CommitmentPolicy,
    EncryptionKeyType,
    WrappingAlgorithm,
)
from aws_encryption_sdk.internal.crypto.wrapping_keys import WrappingKey
from aws_encryption_sdk.key_providers.raw import RawMasterKeyProvider
from boto3 import client
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from botocore.exceptions import ConnectionError as BotoConnectionError
from pydantic import BaseModel, Field, validator

logger = logging.getLogger(__name__)


class S3Error(Exception):
    """Generic S3 Exception."""


class S3Parameters(BaseModel):
    """Configuration for accessing S3 bucket.

    Attributes:
        access_key: AWS access key.
        secret_key: AWS secret key.
        region: The region to connect to the object storage.
        bucket: The bucket name.
        endpoint: The endpoint used to connect to the object storage.
        path: The path inside the bucket to store objects.
        s3_uri_style: The S3 protocol specific bucket path lookup type. Can be "path" or "host".
        addressing_style: S3 protocol addressing style, can be "path" or "virtual".
    """

    access_key: str = Field(alias="access-key")
    secret_key: str = Field(alias="secret-key")
    region: Optional[str]
    bucket: str
    endpoint: Optional[str]
    path: str = Field(default="")
    s3_uri_style: str = Field(alias="s3-uri-style", default="host")

    @validator("endpoint", always=True)
    @classmethod
    def check_endpoint_or_region_set(cls, endpoint: str, values: dict[str, Any]) -> str:
        """Validate that either region or endpoint is set.

        Args:
            endpoint: endpoint attribute
            values: all attributes in S3 configuration

        Returns:
            value of the endpoint attribute

        Raises:
            ValueError: if the configuration is invalid.
        """
        region = values.get("region")
        if not region and not endpoint:
            raise ValueError('one of "region" or "endpoint" needs to be set')
        return endpoint

    @property
    def addressing_style(self) -> str:
        """Translates s3_uri_style to AWS addressing_style."""
        if self.s3_uri_style == "path":
            return "path"
        return "virtual"


class S3Client:
    """S3 Client Wrapper around boto3 library."""

    # pylint: disable=too-few-public-methods
    def __init__(self, s3_parameters: S3Parameters):
        """Initialize the S3 client.

        Args:
            s3_parameters: Parameter to configure the S3 connection.
        """
        self._s3_parameters = s3_parameters
        self._client = self._create_client()

    def _create_client(self) -> Any:
        """Create new boto3 S3 client.

        Creating the client does not connect to the server.

        Returns:
            New instantiated boto3 S3 client.

        Raises:
            S3Error: If it was not possible to create the client.
        """
        try:
            s3_client_config = Config(
                region_name=self._s3_parameters.region,
                s3={
                    "addressing_style": self._s3_parameters.addressing_style,
                },
            )
            s3_client = client(
                "s3",
                self._s3_parameters.region,
                aws_access_key_id=self._s3_parameters.access_key,
                aws_secret_access_key=self._s3_parameters.secret_key,
                endpoint_url=self._s3_parameters.endpoint,
                config=s3_client_config,
            )
        except (TypeError, BotoCoreError) as exc:
            logger.exception("Error creating S3 client")
            raise S3Error("Error creating S3 client") from exc
        return s3_client

    def can_use_bucket(self) -> bool:
        """Check if a bucket exists and is accessible in an S3 compatible object store.

        Returns:
            True if the bucket exists and is accessible
        """
        try:
            self._client.head_bucket(Bucket=self._s3_parameters.bucket)
        except (ClientError, BotoConnectionError):
            logger.exception(
                "Bucket %s doesn't exist or you don't have access to it.",
                self._s3_parameters.bucket,
            )
            return False
        return True


class StaticRandomMasterKeyProvider(RawMasterKeyProvider):
    """KeyProvider to store the password to use for encryption/decryption."""

    master_key = b"master_key"
    provider_id = "static-random"

    def __init__(self, **kwargs: dict):  # pylint: disable=unused-argument
        """Initialize empty map of keys."""
        self._static_keys: dict = {}

    def _get_raw_key(self, key_id: bytes) -> WrappingKey:
        """Return the password after hashing it with sha256."""
        static_key = self._static_keys[key_id]
        static_key = hashlib.sha256(static_key.encode("utf-8")).digest()
        return WrappingKey(
            wrapping_algorithm=WrappingAlgorithm.AES_256_GCM_IV12_TAG16_NO_PADDING,
            wrapping_key=static_key,
            wrapping_key_type=EncryptionKeyType.SYMMETRIC,
        )

    def add_static_password(self, password: str) -> None:
        """Add the password to use for the encryption/decryption."""
        self._static_keys[self.master_key] = password
        self.add_master_key(self.master_key)


class BytesIOIterable(io.BufferedIOBase):
    """Class that created a file like object from an iterable."""

    def __init__(self, iterable: Iterable[bytes]):
        """Initialize the object with the iterable."""
        self._input_iter = iter(iterable)
        self._buffer = bytearray()

    def read(self, size: int | None = -1, /) -> bytes:
        """Return up to size bytes from the input iterable."""
        if size == -1 or size is None:
            size = int(1e7)  # for simplicity and memory efficiency

        # Just return up to size. Do not get more elements
        # as it implies using more memory.
        if len(self._buffer) > size:
            response = bytes(self._buffer[0:size])
            del self._buffer[0:size]
            return response

        try:
            while len(self._buffer) < size:
                self._buffer += next(self._input_iter)
        except StopIteration:
            pass

        response = bytes(self._buffer[0:size])
        del self._buffer[0:size]
        return response


def encrypt_generator(inputstream: Iterable[bytes], password: str) -> Generator[bytes, None, None]:
    """Encrypt an inputstream (iterator) and return another iterator.

    https://docs.aws.amazon.com/encryption-sdk/latest/developer-guide/python-example-code.html#python-example-streams
    """
    master_key_provider = StaticRandomMasterKeyProvider()
    master_key_provider.add_static_password(password)
    input_file = BytesIOIterable(inputstream)
    encryption_client = EncryptionSDKClient(
        commitment_policy=CommitmentPolicy.REQUIRE_ENCRYPT_REQUIRE_DECRYPT
    )
    with encryption_client.stream(
        algorithm=Algorithm.AES_256_GCM_HKDF_SHA512_COMMIT_KEY,
        mode="e",
        source=input_file,
        key_provider=master_key_provider,
    ) as encryptor:
        for chunk in encryptor:
            yield chunk


def decrypt_generator(inputstream: Iterable[bytes], password: str) -> Generator[bytes, None, None]:
    """Decrypt an inputstream (iterator) and return another iterator.

    https://docs.aws.amazon.com/encryption-sdk/latest/developer-guide/python-example-code.html#python-example-streams
    """
    master_key_provider = StaticRandomMasterKeyProvider()
    master_key_provider.add_static_password(password)
    input_file = BytesIOIterable(inputstream)
    decryption_client = EncryptionSDKClient(
        commitment_policy=CommitmentPolicy.REQUIRE_ENCRYPT_REQUIRE_DECRYPT
    )
    with decryption_client.stream(
        mode="decrypt-unsigned",
        source=input_file,
        key_provider=master_key_provider,
    ) as decryptor:
        for chunk in decryptor:
            yield chunk


def tar_file_generator(
    files_to_tar: List[str], base_dir: str, open_func: Any = open
) -> Generator[bytes, None, None]:
    """Create a tar file with input files and yields the bytes.

    TODO files_to_tar relative to base_dir
    TODO should we get the files from pebble, using another open/stat/whatever
    """
    output_file = io.BytesIO()
    with tarfile.open(fileobj=output_file, mode="w|") as tar:
        for filename in files_to_tar:
            absolute_filename = os.path.join(base_dir, filename)
            tarinfo = tar.gettarinfo(name=absolute_filename, arcname=filename)
            if tarinfo.isreg():
                with open_func(absolute_filename, "rb") as f:
                    tar.addfile(tarinfo, f)
            elif tarinfo.isdir():
                tar.addfile(tarinfo)
            yield output_file.getvalue()
            output_file.seek(0)
            output_file.truncate(0)
    pending_bytes = output_file.getvalue()
    if len(pending_bytes) > 0:
        yield pending_bytes


# pylint: disable=unused-argument
# flake8: noqa
def create_backup(s3_parameters: S3Parameters, backup_name: str) -> None:
    """Create a new back up for Synapse.

    Args:
        s3_parameters: S3 parameters for the bucket to create the backup.
        backup_name: Name for the backup.
    """
    raise NotImplementedError
