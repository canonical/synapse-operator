# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helper module used to manage MAS-related workloads."""
import logging
import secrets

import ops
from jinja2 import Environment, FileSystemLoader, select_autoescape

from state.charm_state import SynapseConfig
from state.mas import MASConfiguration

logger = logging.getLogger()

MAS_TEMPLATE_FILE_NAME = "mas_config.yaml.j2"

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
                "working-dir": MAS_WORKING_DIR,
            }
        },
    }
)


class MASConfigInvalidError(Exception):
    """Exception raised when validation of the MAS config failed."""


class MASRegisterUserFailedError(Exception):
    """Exception raised when validation of the MAS config failed."""


class MASVerifyUserEmailFailedError(Exception):
    """Exception raised when validation of the MAS config failed."""


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


def generate_mas_config(
    mas_configuration: MASConfiguration,
    synapse_configuration: SynapseConfig,
    main_unit_address: str,
) -> str:
    """Render the MAS configuration file.

    Args:
        mas_configuration: Path of the template to load.
        synapse_configuration: Context needed to render the template.
        main_unit_address: Address of synapse main unit.

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
        "account_management_url": f"{mas_public_address}account",
        "issuer_metadata": {
            "authorization_endpoint": f"{mas_local_address}authorize",
            "token_endpoint": f"{mas_local_address}oauth2/token",
            "jwks_uri": f"{mas_local_address}oauth2/keys.json",
            "registration_endpoint": f"{mas_local_address}oauth2/registration",
            "introspection_endpoint": f"{mas_local_address}oauth2/introspect",
        },
    }
