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

from .api import SYNAPSE_PORT, SYNAPSE_URL, VERSION_URL

CHECK_ALIVE_NAME = "synapse-alive"
CHECK_MJOLNIR_READY_NAME = "synapse-mjolnir-ready"
CHECK_NGINX_READY_NAME = "synapse-nginx-ready"
CHECK_READY_NAME = "synapse-ready"
COMMAND_MIGRATE_CONFIG = "migrate_config"
SYNAPSE_CONFIG_DIR = "/data"
MJOLNIR_CONFIG_PATH = f"{SYNAPSE_CONFIG_DIR}/config/production.yaml"
MJOLNIR_HEALTH_PORT = 7777
MJOLNIR_SERVICE_NAME = "mjolnir"
PROMETHEUS_TARGET_PORT = "9000"
SYNAPSE_COMMAND_PATH = "/start.py"
SYNAPSE_CONFIG_PATH = f"{SYNAPSE_CONFIG_DIR}/homeserver.yaml"
SYNAPSE_CONTAINER_NAME = "synapse"
SYNAPSE_NGINX_CONTAINER_NAME = "synapse-nginx"
SYNAPSE_NGINX_PORT = 8080
SYNAPSE_SERVICE_NAME = "synapse"

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


class CreateMjolnirConfigError(WorkloadError):
    """Exception raised when something goes wrong while creating mjolnir config."""


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
    check = Check(CHECK_ALIVE_NAME)
    check.override = "replace"
    check.level = "alive"
    check.tcp = {"port": SYNAPSE_PORT}
    return check.to_dict()


def check_nginx_ready() -> ops.pebble.CheckDict:
    """Return the Synapse NGINX container check.

    Returns:
        Dict: check object converted to its dict representation.
    """
    check = Check(CHECK_NGINX_READY_NAME)
    check.override = "replace"
    check.level = "ready"
    check.http = {"url": f"http://localhost:{SYNAPSE_NGINX_PORT}/health"}
    return check.to_dict()


def check_mjolnir_ready() -> ops.pebble.CheckDict:
    """Return the Synapse Mjolnir service check.

    Returns:
        Dict: check object converted to its dict representation.
    """
    check = Check(CHECK_MJOLNIR_READY_NAME)
    check.override = "replace"
    check.level = "ready"
    check.http = {"url": f"http://localhost:{MJOLNIR_HEALTH_PORT}/healthz"}
    return check.to_dict()


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
        return yaml.safe_load(configuration_content)[fieldname]
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


def get_registration_shared_secret(container: ops.Container) -> typing.Optional[str]:
    """Get registration_shared_secret from configuration file.

    Args:
        container: Container of the charm.

    Returns:
        registration_shared_secret value.
    """
    return _get_configuration_field(container=container, fieldname="registration_shared_secret")


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
    if (
        configured_server_name is not None
        and configured_server_name != charm_state.synapse_config.server_name
    ):
        msg = (
            f"server_name {charm_state.synapse_config.server_name} is different from the existing "
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


def validate_config(container: ops.Container) -> None:
    """Run the Synapse command to validate the configuration file.

    Args:
        container: Container of the charm.

    Raises:
        WorkloadError: something went wrong running migrate_config.
    """
    validate_config_result = _exec(
        container, ["/usr/bin/python3", "-m", "synapse.config", "-c", SYNAPSE_CONFIG_PATH]
    )
    if validate_config_result.exit_code:
        logger.error(
            "validate config failed, stdout: %s, stderr: %s",
            validate_config_result.stdout,
            validate_config_result.stderr,
        )
        raise WorkloadError("Validate config failed, please check the logs")


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


def disable_password_config(container: ops.Container) -> None:
    """Change the Synapse configuration to disable password config.

    Args:
        container: Container of the charm.

    Raises:
        WorkloadError: something went wrong disabling password config.
    """
    try:
        config = container.pull(SYNAPSE_CONFIG_PATH).read()
        current_yaml = yaml.safe_load(config)
        current_yaml["password_config"] = {"enabled": False}
        container.push(SYNAPSE_CONFIG_PATH, yaml.safe_dump(current_yaml))
    except ops.pebble.PathError as exc:
        raise WorkloadError(str(exc)) from exc


def enable_serve_server_wellknown(container: ops.Container) -> None:
    """Change the Synapse configuration to enable server wellknown file.

    Args:
        container: Container of the charm.

    Raises:
        WorkloadError: something went wrong enabling configuration.
    """
    try:
        config = container.pull(SYNAPSE_CONFIG_PATH).read()
        current_yaml = yaml.safe_load(config)
        current_yaml["serve_server_wellknown"] = True
        container.push(SYNAPSE_CONFIG_PATH, yaml.safe_dump(current_yaml))
    except ops.pebble.PathError as exc:
        raise WorkloadError(str(exc)) from exc


def enable_federation_domain_whitelist(container: ops.Container, charm_state: CharmState) -> None:
    """Change the Synapse configuration to enable federation_domain_whitelist.

    Args:
        container: Container of the charm.
        charm_state: Instance of CharmState.

    Raises:
        WorkloadError: something went wrong enabling configuration.
    """
    try:
        config = container.pull(SYNAPSE_CONFIG_PATH).read()
        current_yaml = yaml.safe_load(config)
        if charm_state.synapse_config.federation_domain_whitelist is not None:
            current_yaml["federation_domain_whitelist"] = [
                item.strip()
                for item in charm_state.synapse_config.federation_domain_whitelist.split(",")
            ]
            container.push(SYNAPSE_CONFIG_PATH, yaml.safe_dump(current_yaml))
    except ops.pebble.PathError as exc:
        raise WorkloadError(str(exc)) from exc


def enable_allow_public_rooms_over_federation(container: ops.Container) -> None:
    """Change the Synapse configuration to allow public rooms in federation.

    Args:
        container: Container of the charm.

    Raises:
        WorkloadError: something went wrong enabling configuration.
    """
    try:
        config = container.pull(SYNAPSE_CONFIG_PATH).read()
        current_yaml = yaml.safe_load(config)
        current_yaml["allow_public_rooms_over_federation"] = True
        container.push(SYNAPSE_CONFIG_PATH, yaml.safe_dump(current_yaml))
    except ops.pebble.PathError as exc:
        raise WorkloadError(str(exc)) from exc


def _create_ip_range_whitelist(ip_range_whitelist: str) -> list[str]:
    """Format IP range whitelist.

    Args:
        ip_range_whitelist: ip_range_whitelist configuration.

    Returns:
        IP range whitelist as expected by Synapse or None.
    """
    return [item.strip() for item in ip_range_whitelist.split(",")]


def enable_ip_range_whitelist(container: ops.Container, charm_state: CharmState) -> None:
    """Change the Synapse configuration to enable ip_range_whitelist.

    Args:
        container: Container of the charm.
        charm_state: Instance of CharmState.

    Raises:
        WorkloadError: something went wrong enabling configuration.
    """
    try:
        config = container.pull(SYNAPSE_CONFIG_PATH).read()
        current_yaml = yaml.safe_load(config)
        ip_range_whitelist = charm_state.synapse_config.ip_range_whitelist
        if ip_range_whitelist is None:
            logger.warning("enable_ip_range_whitelist called but config is empty")
            return
        current_yaml["ip_range_whitelist"] = _create_ip_range_whitelist(ip_range_whitelist)
        container.push(SYNAPSE_CONFIG_PATH, yaml.safe_dump(current_yaml))
    except ops.pebble.PathError as exc:
        raise WorkloadError(str(exc)) from exc


def _get_mjolnir_config(access_token: str, room_id: str) -> typing.Dict:
    """Create config as expected by mjolnir.

    Args:
        access_token: access token to be used by the mjolnir bot.
        room_id: management room id monitored by the Mjolnir.

    Returns:
        Mjolnir configuration
    """
    with open("templates/mjolnir_production.yaml", encoding="utf-8") as mjolnir_config_file:
        config = yaml.safe_load(mjolnir_config_file)
        config["homeserverUrl"] = SYNAPSE_URL
        config["rawHomeserverUrl"] = SYNAPSE_URL
        config["accessToken"] = access_token
        config["managementRoom"] = room_id
        return config


def create_mjolnir_config(container: ops.Container, access_token: str, room_id: str) -> None:
    """Create mjolnir configuration.

    Args:
        container: Container of the charm.
        access_token: access token to be used by the Mjolnir.
        room_id: management room id monitored by the Mjolnir.

    Raises:
        CreateMjolnirConfigError: something went wrong creating mjolnir config.
    """
    try:
        config = _get_mjolnir_config(access_token, room_id)
        container.push(MJOLNIR_CONFIG_PATH, yaml.safe_dump(config), make_dirs=True)
    except ops.pebble.PathError as exc:
        raise CreateMjolnirConfigError(str(exc)) from exc


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
    entity_id = (
        charm_state.synapse_config.public_baseurl
        if charm_state.synapse_config.public_baseurl is not None
        else f"https://{charm_state.synapse_config.server_name}"
    )
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
                "entityId": entity_id,
                "allow_unsolicited": True,
            },
        },
    }
    # login.staging.ubuntu.com and login.ubuntu.com
    # dont send uid in SAMLResponse so this will map
    # as expected
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
        if charm_state.synapse_config.public_baseurl is not None:
            current_yaml["public_baseurl"] = charm_state.synapse_config.public_baseurl
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


def enable_smtp(container: ops.Container, charm_state: CharmState) -> None:
    """Change the Synapse configuration to enable SMTP.

    Args:
        container: Container of the charm.
        charm_state: Instance of CharmState.

    Raises:
        WorkloadError: something went wrong enabling SMTP.
    """
    try:
        config = container.pull(SYNAPSE_CONFIG_PATH).read()
        current_yaml = yaml.safe_load(config)
        current_yaml["email"] = {}
        # The following three configurations are mandatory for SMTP.
        current_yaml["email"]["smtp_host"] = charm_state.synapse_config.smtp_host
        current_yaml["email"]["smtp_port"] = charm_state.synapse_config.smtp_port
        current_yaml["email"]["notif_from"] = charm_state.synapse_config.smtp_notif_from
        if charm_state.synapse_config.smtp_user:
            current_yaml["email"]["smtp_user"] = charm_state.synapse_config.smtp_user
        if charm_state.synapse_config.smtp_pass:
            current_yaml["email"]["smtp_pass"] = charm_state.synapse_config.smtp_pass
        if not charm_state.synapse_config.smtp_enable_tls:
            # Only set if the user set as false.
            # By default, if the server supports TLS, it will be used,
            # and the server must present a certificate that is valid for 'smtp_host'.
            current_yaml["email"]["enable_tls"] = charm_state.synapse_config.smtp_enable_tls
        container.push(SYNAPSE_CONFIG_PATH, yaml.safe_dump(current_yaml))
    except ops.pebble.PathError as exc:
        raise WorkloadError(str(exc)) from exc


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
        "SYNAPSE_SERVER_NAME": f"{charm_state.synapse_config.server_name}",
        "SYNAPSE_REPORT_STATS": f"{charm_state.synapse_config.report_stats}",
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
    for proxy_variable in ("http_proxy", "https_proxy", "no_proxy"):
        proxy_value = getattr(charm_state.proxy, proxy_variable)
        if proxy_value:
            environment[proxy_variable] = str(proxy_value)
            environment[proxy_variable.upper()] = str(proxy_value)
    return environment
