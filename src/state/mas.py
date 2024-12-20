# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""State of the Charm."""

import dataclasses
import logging
import secrets
import typing

import ops
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from ops.model import SecretNotFoundError
from pydantic import BaseModel, Field, ValidationError
from ulid import ULID

from charm_types import DatasourcePostgreSQL

logger = logging.getLogger()

MAS_DATABASE_INTEGRATION_NAME = "mas-database"
MAS_DATABASE_NAME = "mas"
MAS_CONTEXT_LABEL = "mas.context"
MAS_ENCRYPTION_KEY_LENGTH = 32  # This is a requirement per the MAS docs


class MASDatasourceMissingError(Exception):
    """Exception raised when the MAS datasource is not configured."""


class MASContextNotSetError(Exception):
    """Exception raised when the MAS context is not set by the leader."""


class MASContextValidationError(Exception):
    """Exception raised when validation of the MAS Context failed."""


class MASContext(BaseModel):
    """Context used to render MAS configuration file.

    Attrs:
        encryption_key: Used for encrypting cookies and database fields
        signing_key_id: Key ID of RSA signing key
        signing_key_rsa: RSA private key for signing
        synapse_shared_secret: Used to authenticate MAS to the homeserver
        synapse_oidc_client_id: OIDC client ID used by synapse
        synapse_oidc_client_secret: OIDC client secret used by synapse
    """

    encryption_key: str = Field(min_length=64, max_length=64)
    signing_key_id: str = Field(min_length=8, max_length=8)
    signing_key_rsa: str = Field()
    synapse_shared_secret: str = Field(min_length=32, max_length=32)
    synapse_oidc_client_id: str = Field()
    synapse_oidc_client_secret: str = Field(min_length=32, max_length=32)


class SigningKey(typing.NamedTuple):
    """Stores a private key and its ID used for signing.

    Attributes:
        key_id: The key ID
        private_key: The private key
    """

    key_id: str
    private_key: str


def generate_rsa_signing_key() -> SigningKey:
    """Generate the MAS rsa signing key.

    Returns:
        SigningKey: The private_key, key_id pair
    """
    key_id = secrets.token_hex(4)
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=4096)
    # PKCS#8 PEM-encoded RSA is a supported format
    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return SigningKey(key_id, private_bytes.decode())


@dataclasses.dataclass(frozen=True)
class MASConfiguration:
    """Information needed to configure MAS.

    Attributes:
        datasource: datasource information.
        mas_context: MAS context to render configuration file.
        database_uri: The database URI used in MAS config.
        mas_prefix: The MAS listening prefix.
    """

    datasource: DatasourcePostgreSQL
    mas_context: MASContext

    @property
    def database_uri(self) -> str:
        """Build the database uri from datasource.

        Returns:
            str: The database uri
        """
        user = self.datasource["user"]
        password = self.datasource["password"]
        host = self.datasource["host"]
        port = self.datasource["port"]
        return f"postgresql://{user}:{password}@{host}:{port}/{MAS_DATABASE_NAME}"

    @property
    def mas_prefix(self) -> str:
        """Return the mas prefix.

        Returns:
            str: The MAS listening prefix
        """
        return "/auth/"

    @classmethod
    def from_charm(cls, charm: ops.CharmBase) -> "MASConfiguration":
        """State component containing MAS configuration information.

        Args:
            charm: The synapse charm

        Raises:
            MASContextNotSetError: When the leader has not set the MAS context.
            MASContextValidationError: When the parsed MAS context is not valid.

        Returns:
            MASConfiguration: The MAS configuration state component.
        """
        cls.validate(charm)
        # pylint: disable=protected-access
        datasource = charm._mas_database.get_relation_as_datasource()  # type: ignore

        try:
            secret = charm.model.get_secret(label=MAS_CONTEXT_LABEL)
            mas_context_secret = secret.get_content()
        except SecretNotFoundError:
            # pylint: disable=raise-missing-from
            # We don't use "raise MASContextNotSetError from exc" here
            # because SecretNotFoundError is not relevant to our error case.
            if not charm.unit.is_leader():
                logger.warning("Waiting for leader to set MAS context in secrets.")
                raise MASContextNotSetError("Waiting for leader to set MAS context.")

            # The leader unit skips raising the above exception to generate the initial values
            # for the MAS context and put them in juju secret which can be picked up by peer units
            signing_key = generate_rsa_signing_key()
            mas_context_secret = {
                "encryption-key": secrets.token_hex(MAS_ENCRYPTION_KEY_LENGTH),
                "signing-key-id": signing_key.key_id,
                "signing-key-rsa": signing_key.private_key,
                "synapse-shared-secret": secrets.token_hex(16),
                "synapse-oidc-client-id": str(ULID()),
                "synapse-oidc-client-secret": secrets.token_hex(16),
            }
            secret = charm.app.add_secret(content=mas_context_secret, label=MAS_CONTEXT_LABEL)

        try:
            mas_context = MASContext(
                encryption_key=mas_context_secret["encryption-key"],
                signing_key_id=mas_context_secret["signing-key-id"],
                signing_key_rsa=mas_context_secret["signing-key-rsa"],
                synapse_shared_secret=mas_context_secret["synapse-shared-secret"],
                synapse_oidc_client_id=mas_context_secret["synapse-oidc-client-id"],
                synapse_oidc_client_secret=mas_context_secret["synapse-oidc-client-secret"],
            )
        except ValidationError as exc:
            logger.exception("Error validating MAS context.")
            raise MASContextValidationError("MAS secret content validation failed") from exc

        return cls(datasource=datasource, mas_context=mas_context)

    @classmethod
    def validate(cls, charm: ops.CharmBase) -> None:
        """State component containing MAS configuration information.

        Args:
            charm: The synapse charm

        Raises:
            MASDatasourceMissingError: when mas-database integration is missing.
        """
        if not charm.model.relations.get(MAS_DATABASE_INTEGRATION_NAME):
            raise MASDatasourceMissingError("Waiting for mas-database integration.")
