#!/usr/bin/env python3

# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helper module used to manage interactions with Synapse."""

import logging
import typing

import ops
import yaml
from ops.pebble import Check, ExecError, PathError

from charm_state import CharmState
from constants import (
    CHECK_READY_NAME,
    COMMAND_MIGRATE_CONFIG,
    PROMETHEUS_TARGET_PORT,
    SYNAPSE_COMMAND_PATH,
    SYNAPSE_CONFIG_DIR,
    SYNAPSE_CONFIG_PATH,
    SYNAPSE_NGINX_PORT,
    SYNAPSE_PORT,
)

from .api import VERSION_URL

logger = logging.getLogger(__name__)


class WorkloadError(Exception):
    """Exception raised when something fails while interacting with workload.

    Attrs:
        msg (str): Explanation of the error.
    """

    def __init__(self, msg: str):
        """Initialize a new instance of the SynapseWorkloadError exception.

        Args:
            msg (str): Explanation of the error.
        """
        self.msg = msg


class CommandMigrateConfigError(WorkloadError):
    """Exception raised when a charm configuration is invalid."""


class ServerNameModifiedError(WorkloadError):
    """Exception raised while checking configuration file."""


class EnableMetricsError(WorkloadError):
    """Exception raised when something goes wrong while enabling metrics."""


class EnableSAMLError(WorkloadError):
    """Exception raised when something goes wrong while enabling SAML."""


class ExecResult(typing.NamedTuple):
    """A named tuple representing the result of executing a command.

    Attributes:
        exit_code: The exit status of the command (0 for success, non-zero for failure).
        stdout: The standard output of the command as a string.
        stderr: The standard error output of the command as a string.
    """

    exit_code: int
    stdout: str
    stderr: str


def check_ready() -> ops.pebble.CheckDict:
    """Return the Synapse container ready check.

    Returns:
        Dict: check object converted to its dict representation.
    """
    check = Check(CHECK_READY_NAME)
    check.override = "replace"
    check.level = "ready"
    check.http = {"url": VERSION_URL}
    return check.to_dict()


def check_alive() -> ops.pebble.CheckDict:
    """Return the Synapse container alive check.

    Returns:
        Dict: check object converted to its dict representation.
    """
    check = Check(CHECK_READY_NAME)
    check.override = "replace"
    check.level = "alive"
    check.tcp = {"port": SYNAPSE_PORT}
    return check.to_dict()


def check_nginx_ready() -> ops.pebble.CheckDict:
    """Return the Synapse NGINX container check.

    Returns:
        Dict: check object converted to its dict representation.
    """
    check = Check(CHECK_READY_NAME)
    check.override = "replace"
    check.level = "ready"
    check.tcp = {"port": SYNAPSE_NGINX_PORT}
    return check.to_dict()


def execute_migrate_config(container: ops.Container, charm_state: CharmState) -> None:
    """Run the Synapse command migrate_config.

    Args:
        container: Container of the charm.
        charm_state: Instance of CharmState.

    Raises:
        CommandMigrateConfigError: something went wrong running migrate_config.
    """
    _check_server_name(container=container, charm_state=charm_state)
    # TODO validate if is possible to use SDK instead of command  # pylint: disable=fixme
    migrate_config_command = [SYNAPSE_COMMAND_PATH, COMMAND_MIGRATE_CONFIG]
    migrate_config_result = _exec(
        container,
        migrate_config_command,
        environment=get_environment(charm_state),
    )
    if migrate_config_result.exit_code:
        logger.error(
            "migrate config failed, stdout: %s, stderr: %s",
            migrate_config_result.stdout,
            migrate_config_result.stderr,
        )
        raise CommandMigrateConfigError(
            "Migrate config failed, please review your charm configuration"
        )


def enable_metrics(container: ops.Container) -> None:
    """Change the Synapse configuration to enable metrics.

    Args:
        container: Container of the charm.

    Raises:
        EnableMetricsError: something went wrong enabling metrics.
    """
    try:
        config = container.pull(SYNAPSE_CONFIG_PATH).read()
        current_yaml = yaml.safe_load(config)
        metric_listener = {
            "port": int(PROMETHEUS_TARGET_PORT),
            "type": "metrics",
            "bind_addresses": ["::"],
        }
        current_yaml["listeners"].extend([metric_listener])
        current_yaml["enable_metrics"] = True
        container.push(SYNAPSE_CONFIG_PATH, yaml.safe_dump(current_yaml))
    except ops.pebble.PathError as exc:
        raise EnableMetricsError(str(exc)) from exc


def _create_pysaml2_config(charm_state: CharmState) -> typing.Dict:
    """Create config as expected by pysaml2.

    Args:
        charm_state: Instance of CharmState.

    Returns:
        Pysaml2 configuration.

    Raises:
        EnableSAMLError: if SAML configuration is not found.
    """
    if charm_state.saml_config is None:
        raise EnableSAMLError(
            "SAML Configuration not found. "
            "Please verify the integration between SAML Integrator and Synapse."
        )

    saml_config = charm_state.saml_config
    sp_config = {
        "metadata": {
            "remote": [
                {
                    "url": saml_config["metadata_url"],
                },
            ],
        },
        "allow_unknown_attributes": True,
        "service": {
            "sp": {
                "entityId": saml_config["entity_id"],
                "allow_unsolicited": True,
            },
        },
    }
    # login.staging.canonical.com and login.canonical.com
    # dont send uid in SAMLResponse so this will map
    # fullname to uid
    if "ubuntu.com" in saml_config["metadata_url"]:
        sp_config["attribute_map_dir"] = "/usr/local/attributemaps"

    return sp_config


def enable_saml(container: ops.Container, charm_state: CharmState) -> None:
    """Change the Synapse configuration to enable SAML.

    Args:
        container: Container of the charm.
        charm_state: Instance of CharmState.

    Raises:
        EnableSAMLError: something went wrong enabling SAML.
    """
    try:
        config = container.pull(SYNAPSE_CONFIG_PATH).read()
        current_yaml = yaml.safe_load(config)
        if charm_state.public_baseurl is not None:
            current_yaml["public_baseurl"] = charm_state.public_baseurl
        # enable x_forwarded to pass expected headers
        current_listeners = current_yaml["listeners"]
        updated_listeners = [
            {
                **item,
                "x_forwarded": True
                if "x_forwarded" in item and not item["x_forwarded"]
                else item.get("x_forwarded", False),
            }
            for item in current_listeners
        ]
        current_yaml["listeners"] = updated_listeners
        current_yaml["saml2_enabled"] = True
        current_yaml["saml2_config"] = {}
        current_yaml["saml2_config"]["sp_config"] = _create_pysaml2_config(charm_state)
        user_mapping_provider_config = {
            "config": {
                "mxid_source_attribute": "uid",
                "grandfathered_mxid_source_attribute": "uid",
                "mxid_mapping": "dotreplace",
            },
        }
        current_yaml["saml2_config"]["user_mapping_provider"] = user_mapping_provider_config
        container.push(SYNAPSE_CONFIG_PATH, yaml.safe_dump(current_yaml))
    except ops.pebble.PathError as exc:
        raise EnableSAMLError(str(exc)) from exc


def get_registration_shared_secret(container: ops.Container) -> typing.Optional[str]:
    """Get registration_shared_secret from configuration file.

    Args:
        container: Container of the charm.

    Returns:
        registration_shared_secret value.
    """
    return _get_configuration_field(container=container, fieldname="registration_shared_secret")


def reset_instance(container: ops.Container) -> None:
    """Erase data and config server_name.

    Args:
        container: Container of the charm.

    Raises:
        PathError: if somethings goes wrong while erasing the Synapse directory.
    """
    logging.debug("Erasing directory %s", SYNAPSE_CONFIG_DIR)
    try:
        container.remove_path(SYNAPSE_CONFIG_DIR, recursive=True)
    except PathError as path_error:
        # The error "unlinkat //data: device or resource busy" is expected
        # when removing the entire directory because it's a volume mount.
        # The files will be removed but SYNAPSE_CONFIG_DIR directory will
        # remain.
        if "device or resource busy" in str(path_error):
            pass
        else:
            logger.exception(
                "exception while erasing directory %s: %r", SYNAPSE_CONFIG_DIR, path_error
            )
            raise


def get_environment(charm_state: CharmState) -> typing.Dict[str, str]:
    """Generate a environment dictionary from the charm configurations.

    Args:
        charm_state: Instance of CharmState.

    Returns:
        A dictionary representing the Synapse environment variables.
    """
    environment = {
        "SYNAPSE_SERVER_NAME": f"{charm_state.server_name}",
        "SYNAPSE_REPORT_STATS": f"{charm_state.report_stats}",
        # TLS disabled so the listener is HTTP. HTTPS will be handled by Traefik.
        # TODO verify support to HTTPS backend before changing this  # pylint: disable=fixme
        "SYNAPSE_NO_TLS": str(True),
    }
    datasource = charm_state.datasource
    if datasource is not None:
        environment["POSTGRES_DB"] = datasource["db"]
        environment["POSTGRES_HOST"] = datasource["host"]
        environment["POSTGRES_PORT"] = datasource["port"]
        environment["POSTGRES_USER"] = datasource["user"]
        environment["POSTGRES_PASSWORD"] = datasource["password"]
    return environment


def _check_server_name(container: ops.Container, charm_state: CharmState) -> None:
    """Check server_name.

    Check if server_name of the state has been modified in relation to the configuration file.

    Args:
        container: Container of the charm.
        charm_state: Instance of CharmState.

    Raises:
        ServerNameModifiedError: if server_name from state is different than the one in the
            configuration file.
    """
    configured_server_name = _get_configuration_field(container=container, fieldname="server_name")
    if configured_server_name is not None and configured_server_name != charm_state.server_name:
        msg = (
            f"server_name {charm_state.server_name} is different from the existing "
            f"one {configured_server_name}. Please revert the config or run the action "
            "reset-instance if you want to erase the existing instance and start a new "
            "one."
        )
        logger.error(msg)
        raise ServerNameModifiedError(
            "The server_name modification is not allowed, please check the logs"
        )


def _exec(
    container: ops.Container,
    command: list[str],
    environment: dict[str, str] | None = None,
) -> ExecResult:
    """Execute a command inside the Synapse workload container.

    Args:
        container: Container of the charm.
        command: A list of strings representing the command to be executed.
        environment: Environment variables for the command to be executed.

    Returns:
        ExecResult: An `ExecResult` object representing the result of the command execution.
    """
    exec_process = container.exec(command, environment=environment, working_dir=SYNAPSE_CONFIG_DIR)
    try:
        stdout, stderr = exec_process.wait_output()
        return ExecResult(0, typing.cast(str, stdout), typing.cast(str, stderr))
    except ExecError as exc:
        return ExecResult(
            exc.exit_code, typing.cast(str, exc.stdout), typing.cast(str, exc.stderr)
        )


def _get_configuration_field(container: ops.Container, fieldname: str) -> typing.Optional[str]:
    """Get configuration field.

    Args:
        container: Container of the charm.
        fieldname: field to get.

    Raises:
        PathError: if somethings goes wrong while reading the configuration file.

    Returns:
        configuration field value.
    """
    try:
        configuration_content = str(container.pull(SYNAPSE_CONFIG_PATH, encoding="utf-8").read())
        value = yaml.safe_load(configuration_content)[fieldname]
        return value
    except PathError as path_error:
        if path_error.kind == "not-found":
            logger.debug(
                "configuration file %s not found, will be created by config-changed",
                SYNAPSE_CONFIG_PATH,
            )
            return None
        logger.exception(
            "exception while reading configuration file %s: %r",
            SYNAPSE_CONFIG_PATH,
            path_error,
        )
        raise
