# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helper module used to manage MAS-related workloads."""

import logging
import secrets
import typing

import ops
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jinja2 import Environment, FileSystemLoader, select_autoescape
from ops.model import SecretNotFoundError
from pydantic import BaseModel, Field, ValidationError
from ulid import ULID

from state.charm_state import SynapseConfig
from state.mas import MASConfiguration

MAS_TEMPLATE_FILE_NAME = "mas_config.yaml.j2"
SYNAPSE_PEER_INTEGRATION_NAME = "synapse-peers"
MAS_ENCRYPTION_AND_SIGNING_SECRET_LABEL = "mas.secrets"
MAS_ENCRYPTION_KEY_LENGTH = 32  # This is a requirement per the MAS docs

logger = logging.getLogger()

MAS_SERVICE_NAME = "synapse-mas"
MAS_EXECUTABLE_PATH = "/usr/bin/mas-cli"
MAS_WORKING_DIR = "/mas"
MAS_CONFIGURATION_PATH = f"{MAS_WORKING_DIR}/config.yaml"

MAS_PEBBLE_LAYER = ops.pebble.LayerDict(
    {
        "summary": "Matrix Authentication Service layer",
        "description": "pebble config layer for MAS",
        "services": {
            MAS_SERVICE_NAME: {
                "override": "replace",
                "summary": "Matrix Authentication Service",
                "startup": "enabled",
                "command": f"{MAS_EXECUTABLE_PATH} server -c {MAS_CONFIGURATION_PATH}",
            }
        },
    }
)


def validate_mas_config(container: ops.model.Container) -> None:
    """Validate current MAS configuration.

    Args:
        container: Synapse container.

    Raises:
        MASConfigInvalidError: if validation of the MAS config failed.
    """
    command = [MAS_EXECUTABLE_PATH, "config", "check", "-c", MAS_CONFIGURATION_PATH]
    try:
        process = container.exec(command=command, working_dir=MAS_WORKING_DIR)
        process.wait_output()
    except ops.pebble.ExecError as exc:
        logger.error("Error validating MAS configuration: %s", exc.stderr)
        raise MASConfigInvalidError("Error validating MAS configuration.") from exc


def sync_mas_config(container: ops.model.Container) -> None:
    """Sync the MAS configuration with the database.

    Args:
        container: Synapse container.
    """
    command = [MAS_EXECUTABLE_PATH, "config", "sync", "--prune", "-c", MAS_CONFIGURATION_PATH]
    process = container.exec(command=command, working_dir=MAS_WORKING_DIR)
    process.wait()


def register_user(
    container: ops.model.Container,
    username: str,
    is_admin: bool = False,
) -> str:
    """Register a new user with MAS.

    Args:
        container: Synapse container.
        username: The username.
        is_admin: Whether the user is an admin. Defaults to False.

    Raises:
        MASRegisterUserFailedError: when user registration fails

    Returns:
        str: The generated user password
    """
    password = secrets.token_urlsafe(16)
    command = [
        MAS_EXECUTABLE_PATH,
        "-c",
        MAS_CONFIGURATION_PATH,
        "manage",
        "register-user",
        "--yes",
        username,
        "--password",
        password,
    ]
    if is_admin:
        command.append("--admin")
    try:
        process = container.exec(command=command, working_dir=MAS_WORKING_DIR)
        process.wait_output()
    except ops.pebble.ExecError as exc:
        logger.error("Error registering new user: %s", exc.stderr)
        raise MASRegisterUserFailedError("Error validating MAS configuration.") from exc

    return password


def verify_user_email(
    container: ops.model.Container,
    username: str,
    email: str,
) -> None:
    """Verify a user email with mas-cli.

    Args:
        container: Synapse container.
        username: The username.
        email: The user's email.

    Raises:
        MASVerifyUserEmailFailedError: when user registration fails
    """
    command = [
        MAS_EXECUTABLE_PATH,
        "-c",
        MAS_CONFIGURATION_PATH,
        "manage",
        "verify-email",
        username,
        email,
    ]

    try:
        process = container.exec(command=command, working_dir=MAS_WORKING_DIR)
        process.wait_output()
    except ops.pebble.ExecError as exc:
        logger.error("Error verifying the user email: %s", exc.stderr)
        raise MASVerifyUserEmailFailedError("Error verifying the user email.") from exc


class MASContextNotSetError(Exception):
    """Exception raised when the MAS context is not set by the leader."""


class MASContextValidationError(Exception):
    """Exception raised when validation of the MAS Context failed."""


class MASConfigInvalidError(Exception):
    """Exception raised when validation of the MAS config failed."""


class MASRegisterUserFailedError(Exception):
    """Exception raised when validation of the MAS config failed."""


class MASVerifyUserEmailFailedError(Exception):
    """Exception raised when validation of the MAS config failed."""


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


class MasService:
    """Service class to manage MAS configuration."""

    def __init__(self, charm: ops.CharmBase) -> None:
        """Init method for the class.

        Args:
            charm: The synapse charm.
        """
        self.charm = charm
        self.model = charm.model
        self.application = charm.app

    def get_mas_context(self) -> typing.Optional[MASContext]:
        """Get the keys used for encryption and signing.

        Raises:
            MASContextValidationError: when validation of MASContext fails.

        Returns:
            MASContext: Encryption and signing key information.
        """
        try:
            secret = self.model.get_secret(label=MAS_ENCRYPTION_AND_SIGNING_SECRET_LABEL)
            encryption_and_signing_keys = secret.get_content()
        except SecretNotFoundError:
            if not self.charm.unit.is_leader():
                logger.warning("Waiting for leader to set MAS context in secrets.")
                return None

            signing_key = generate_rsa_signing_key()
            encryption_and_signing_keys = {
                "encryption-key": secrets.token_hex(MAS_ENCRYPTION_KEY_LENGTH),
                "signing-key-id": signing_key.key_id,
                "signing-key-rsa": signing_key.private_key,
                "synapse-shared-secret": secrets.token_hex(16),
                "synapse-oidc-client-id": str(ULID()),
                "synapse-oidc-client-secret": secrets.token_hex(16),
            }
            secret = self.application.add_secret(
                content=encryption_and_signing_keys, label=MAS_ENCRYPTION_AND_SIGNING_SECRET_LABEL
            )

        try:
            return MASContext(
                encryption_key=encryption_and_signing_keys["encryption-key"],
                signing_key_id=encryption_and_signing_keys["signing-key-id"],
                signing_key_rsa=encryption_and_signing_keys["signing-key-rsa"],
                synapse_shared_secret=encryption_and_signing_keys["synapse-shared-secret"],
                synapse_oidc_client_id=encryption_and_signing_keys["synapse-oidc-client-id"],
                synapse_oidc_client_secret=encryption_and_signing_keys[
                    "synapse-oidc-client-secret"
                ],
            )
        except ValidationError as exc:
            raise MASContextValidationError("MAS secret content validation failed") from exc

    def generate_mas_config(
        self,
        mas_configuration: MASConfiguration,
        synapse_configuration: SynapseConfig,
        main_unit_address: str,
    ) -> str:
        """Render the MAS configuration file.

        Args:
            mas_configuration: Path of the template to load.
            synapse_configuration: Context needed to render the template.
            main_unit_address: Address of synapse main unit.

        Raises:
            MASContextNotSetError: When the MAS context is not set by the leader.

        Returns:
            str: The rendered MAS configuration.
        """
        mas_context = self.get_mas_context()
        if not mas_context:
            raise MASContextNotSetError("Waiting for leader to set MAS context.")

        context = {
            "mas_prefix": mas_configuration.mas_prefix,
            "encryption_key": mas_context.encryption_key,
            "signing_key_id": mas_context.signing_key_id,
            "signing_key_rsa": mas_context.signing_key_rsa,
            "synapse_oidc_client_id": mas_context.synapse_oidc_client_id,
            "synapse_oidc_client_secret": mas_context.synapse_oidc_client_secret,
            "synapse_shared_secret": mas_context.synapse_shared_secret,
            "synapse_public_baseurl": synapse_configuration.public_baseurl,
            "mas_database_uri": mas_configuration.database_uri,
            "enable_password_config": synapse_configuration.enable_password_config,
            "synapse_server_name_config": synapse_configuration.server_name,
            "synapse_main_unit_address": main_unit_address,
        }
        env = Environment(
            loader=FileSystemLoader("./templates"),
            autoescape=select_autoescape(),
            keep_trailing_newline=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        template = env.get_template(MAS_TEMPLATE_FILE_NAME)
        return template.render(context)

    def generate_synapse_msc3861_config(
        self, mas_configuration: MASConfiguration, synapse_configuration: SynapseConfig
    ) -> dict:
        """Render synapse's msc3861 configuration.

        msc3861 delegates authentication to the Matrix Authentication Service (MAS).

        Args:
            mas_configuration: Path of the template to load.
            synapse_configuration: Context needed to render the template.

        Raises:
            MASContextNotSetError: When the MAS context is not set by the leader.

        Returns:
            str: The rendered msc3861 configuration.
        """
        mas_context = self.get_mas_context()
        if not mas_context:
            raise MASContextNotSetError("Waiting for leader to set MAS context.")

        mas_prefix = mas_configuration.mas_prefix
        # We explicitly set the oauth2 endpoints using MAS local address
        # This is to avoid problems with TLS self-signed certificates
        # when the charm is behind an https ingress
        mas_local_address = f"http://localhost:8081{mas_prefix}"
        # MAS public address is used when redirecting the client to MAS for login
        mas_public_address = f"{synapse_configuration.public_baseurl}{mas_prefix}"
        return {
            "enabled": True,
            "issuer": mas_public_address,
            "client_id": mas_context.synapse_oidc_client_id,
            "client_auth_method": "client_secret_basic",
            "client_secret": mas_context.synapse_oidc_client_secret,
            "admin_token": mas_context.synapse_shared_secret,
            "account_management_url": f"{mas_public_address}/account",
            "issuer_metadata": {
                "authorization_endpoint": f"{mas_local_address}/authorize",
                "token_endpoint": f"{mas_local_address}/oauth2/token",
                "jwks_uri": f"{mas_local_address}/oauth2/keys.json",
                "registration_endpoint": f"{mas_local_address}/oauth2/registration",
                "introspection_endpoint": f"{mas_local_address}/oauth2/introspect",
            },
        }
