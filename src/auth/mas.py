# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helper module used to manage MAS-related workloads."""
import logging
import secrets
import typing

import ops
from charms.hydra.v0.oauth import ClientConfig, OauthProviderConfig
from jinja2 import Environment, FileSystemLoader, select_autoescape

from charm_state import SynapseConfig
from charm_types import SMTPConfiguration
from state.mas import MASConfiguration

logger = logging.getLogger()

MAS_TEMPLATE_FILE_NAME = "mas_config.yaml.j2"
MAS_SERVICE_NAME = "synapse-mas"
MAS_EXECUTABLE_PATH = "/mas-cli"
MAS_WORKING_DIR = "/mas"
MAS_CONFIGURATION_PATH = f"{MAS_WORKING_DIR}/config.yaml"

MAS_AUTHORIZATION_GRANT = ["authorization_code"]
MAS_OIDC_SCOPE = "openid profile email"
# Disabling bandit checks since these are only the labels for juju secret
MAS_TOKEN_ENDPOINT_AUTH_METHOD = "client_secret_basic"  # nosec
ADMIN_TOKEN_SECRET_LABEL = "admin.token"  # nosec


class MASCLIBaseError(Exception):
    """Base exception for mas-cli related operations."""


class MASConfigInvalidError(Exception):
    """Exception raised when validation of the MAS config failed."""


class MASRegisterUserFailedError(Exception):
    """Exception raised when user registration failed."""


class MASProvisionUserFailedError(Exception):
    """Exception raised when provisioning of users failed."""


class MASConfigSyncError(MASCLIBaseError):
    """Exception raised when synchronisation of the MAS config failed."""


class MASVerifyUserEmailFailedError(MASCLIBaseError):
    """Exception raised when validation of the MAS config failed."""


class MASDeactivateUserFailedError(MASCLIBaseError):
    """Exception raised when deactivation of a MAS user failed."""


class MASGenerateAdminAccessTokenError(MASCLIBaseError):
    """Exception raised when generation of admin token failed."""


def validate_mas_config(container: ops.model.Container) -> None:
    """Validate current MAS configuration.

    Args:
        container: Synapse container.

    Raises:
        MASConfigInvalidError: when validation of the MAS config failed.
    """
    command = [MAS_EXECUTABLE_PATH, "config", "check", "-c", MAS_CONFIGURATION_PATH]

    try:
        process = container.exec(command=command, working_dir=MAS_WORKING_DIR)
        process.wait_output()
    except ops.pebble.ExecError as exc:
        logger.exception("Validation of the MAS config failed.")
        raise MASConfigInvalidError("Validation of the MAS config failed.") from exc


def sync_mas_config(container: ops.model.Container) -> None:
    """Sync the MAS configuration with the database.

    Args:
        container: Synapse container.

    Raises:
        MASConfigSyncError: when synchronisation of the MAS config failed.
    """
    command = [MAS_EXECUTABLE_PATH, "config", "sync", "--prune", "-c", MAS_CONFIGURATION_PATH]

    try:
        process = container.exec(command=command, working_dir=MAS_WORKING_DIR)
        process.wait()
    except ops.pebble.ExecError as exc:
        logger.exception("Error syncing MAS config with the database.")
        raise MASConfigSyncError("Error syncing MAS config with the database.") from exc


def register_user(
    container: ops.model.Container,
    username: str,
    is_admin: bool = False,
) -> str:
    """Register a new user with MAS. Afterwards start a provisioning job for all users.

    Args:
        container: Synapse container.
        username: The username.
        is_admin: Whether the user is an admin. Defaults to False.

    Raises:
        MASRegisterUserFailedError: when user registration fails

    Returns:
        str: The generated user password
    """
    password = secrets.token_hex(16)
    command = [
        MAS_EXECUTABLE_PATH,
        "-c",
        MAS_CONFIGURATION_PATH,
        "manage",
        "register-user",
        "--yes",
        username,
        "--password",
        str(password),
    ]
    if is_admin:
        command.append("--admin")
    try:
        process = container.exec(command=command, working_dir=MAS_WORKING_DIR)
        process.wait_output()
    except ops.pebble.ExecError as exc:
        logger.exception("Error registering new user.")
        raise MASRegisterUserFailedError("Error registering new user.") from exc

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
        logger.exception("Error verifying the user email.")
        raise MASVerifyUserEmailFailedError("Error verifying the user email.") from exc


def deactivate_user(container: ops.model.Container, username: str) -> None:
    """Deactivate an user with mas-cli.

    Args:
        container: Synapse container.
        username: Username to create the access token.

    Raises:
        MASDeactivateUserFailedError: when deactivation of the user fails
    """
    command = [
        MAS_EXECUTABLE_PATH,
        "-c",
        MAS_CONFIGURATION_PATH,
        "manage",
        "lock-user",
        "--deactivate",
        username,
    ]

    try:
        process = container.exec(command=command, working_dir=MAS_WORKING_DIR)
        process.wait_output()
    except ops.pebble.ExecError as exc:
        logger.exception("Error deactivating user.")
        raise MASDeactivateUserFailedError("Error deactivating user.") from exc


def generate_mas_config(
    mas_configuration: MASConfiguration,
    synapse_configuration: SynapseConfig,
    oauth_provider_info: typing.Optional[OauthProviderConfig],
    smtp_configuration: typing.Optional[SMTPConfiguration],
    main_unit_address: str,
) -> str:
    """Render the MAS configuration file.

    Args:
        mas_configuration: Path of the template to load.
        synapse_configuration: Context needed to render the template.
        smtp_configuration: SMTP configuration.
        main_unit_address: Address of synapse main unit.
        oauth_provider_info: upstream provider configuration.

    Returns:
        str: The rendered MAS configuration.
    """
    mas_context = mas_configuration.mas_context

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
        # False with a capital F is not handled properly by MAS -_-
        "enable_password_config": (
            "true" if synapse_configuration.enable_password_config else "false"
        ),
        "synapse_server_name_config": synapse_configuration.server_name,
        "synapse_main_unit_address": main_unit_address,
        "upstream_oidc_provider_id": mas_context.upstream_oidc_provider_id,
        "oauth_provider_info": oauth_provider_info,
        "mas_oidc_scope": MAS_OIDC_SCOPE,
        "smtp_configuration": smtp_configuration,
        "oidc_subject_claim": f'"{{{{ {mas_context.oidc_subject_claim} }}}}"',
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
    mas_configuration: MASConfiguration, synapse_configuration: SynapseConfig
) -> dict:
    """Render synapse's msc3861 configuration.

    msc3861 delegates authentication to the Matrix Authentication Service (MAS).

    Args:
        mas_configuration: Path of the template to load.
        synapse_configuration: Context needed to render the template.

    Returns:
        str: The rendered msc3861 configuration.
    """
    mas_context = mas_configuration.mas_context
    mas_prefix = mas_configuration.mas_prefix
    # MAS public address is used when redirecting the client to MAS for login
    mas_public_address = f"{synapse_configuration.public_baseurl}{mas_prefix}"
    return {
        "enabled": True,
        "issuer": mas_public_address,
        "client_id": mas_context.synapse_oidc_client_id,
        "client_auth_method": "client_secret_basic",
        "client_secret": mas_context.synapse_oidc_client_secret,
        "admin_token": mas_context.synapse_shared_secret,
        "account_management_url": f"{mas_public_address}account",
    }


def generate_oauth_client_config(
    mas_configuration: MASConfiguration, synapse_configuration: SynapseConfig
) -> ClientConfig:
    """Generate the oauth client config.

    Args:
        mas_configuration: Path of the template to load.
        synapse_configuration: Context needed to render the template.

    Returns:
        ClientConfig: Oauth client config.
    """
    redirect_uri = (
        f"{synapse_configuration.public_baseurl}"
        f"/auth/upstream/callback/{mas_configuration.mas_context.upstream_oidc_provider_id}"
    )
    return ClientConfig(
        redirect_uri=redirect_uri,
        scope=MAS_OIDC_SCOPE,
        grant_types=MAS_AUTHORIZATION_GRANT,
        token_endpoint_auth_method=MAS_TOKEN_ENDPOINT_AUTH_METHOD,
    )
