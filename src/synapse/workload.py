#!/usr/bin/env python3

# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helper module used to manage interactions with Synapse."""

import logging
import typing
from pathlib import Path

import ops
import yaml
from ops.pebble import ExecError, PathError

from charm_state import CharmState

from .api import SYNAPSE_URL

SYNAPSE_CONFIG_DIR = "/data"

CHECK_ALIVE_NAME = "synapse-alive"
CHECK_MJOLNIR_READY_NAME = "synapse-mjolnir-ready"
CHECK_NGINX_READY_NAME = "synapse-nginx-ready"
CHECK_READY_NAME = "synapse-ready"
COMMAND_MIGRATE_CONFIG = "migrate_config"
MJOLNIR_CONFIG_PATH = f"{SYNAPSE_CONFIG_DIR}/config/production.yaml"
MJOLNIR_HEALTH_PORT = 7777
MJOLNIR_SERVICE_NAME = "mjolnir"
IRC_BRIDGE_CONFIG_PATH = f"{SYNAPSE_CONFIG_DIR}/config/irc_bridge.yaml"
IRC_BRIDGE_REGISTRATION_PATH = f"{SYNAPSE_CONFIG_DIR}/config/appservice-registration-irc.yaml"
IRC_BRIDGE_HEALTH_PORT = "5446"
IRC_BRIDGE_SERVICE_NAME = "irc"
IRC_BRIDGE_BOT_NAME = "irc_bot"
IRC_BRIDGE_RELATION_NAME = "irc-bridge-database"
CHECK_IRC_BRIDGE_READY_NAME = "synapse-irc-ready"
PROMETHEUS_TARGET_PORT = "9000"
SYNAPSE_COMMAND_PATH = "/start.py"
SYNAPSE_CONFIG_PATH = f"{SYNAPSE_CONFIG_DIR}/homeserver.yaml"
SYNAPSE_CONTAINER_NAME = "synapse"
SYNAPSE_CRON_SERVICE_NAME = "synapse-cron"
SYNAPSE_DATA_DIR = "/data"
SYNAPSE_DEFAULT_MEDIA_STORE_PATH = "/media_store"
SYNAPSE_GROUP = "synapse"
SYNAPSE_NGINX_CONTAINER_NAME = "synapse-nginx"
SYNAPSE_NGINX_PORT = 8080
SYNAPSE_NGINX_SERVICE_NAME = "synapse-nginx"
SYNAPSE_PEER_RELATION_NAME = "synapse-peers"
SYNAPSE_SERVICE_NAME = "synapse"
SYNAPSE_USER = "synapse"
SYNAPSE_WORKER_CONFIG_PATH = f"{SYNAPSE_CONFIG_DIR}/worker.yaml"
SYNAPSE_DB_RELATION_NAME = "database"

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


class CreateIRCBridgeConfigError(WorkloadError):
    """Exception raised when something goes wrong while creating irc bridge config."""


class CreateIRCBridgeRegistrationError(WorkloadError):
    """Exception raised when something goes wrong while creating irc bridge registration."""


class EnableSAMLError(WorkloadError):
    """Exception raised when something goes wrong while enabling SAML."""


class EnableSMTPError(WorkloadError):
    """Exception raised when something goes wrong while enabling SMTP."""


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


def get_media_store_path(container: ops.Container) -> str:
    """Get media_store_path from configuration file.

    Args:
        container: Container of the charm.

    Returns:
        media_store_path value.
    """
    media_store_path = _get_configuration_field(container=container, fieldname="media_store_path")
    if not media_store_path:
        media_store_path = SYNAPSE_DEFAULT_MEDIA_STORE_PATH
    return media_store_path


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


def enable_metrics(current_yaml: dict) -> None:
    """Change the Synapse configuration to enable metrics.

    Args:
    current_yaml: current configuration.

    Raises:
        EnableMetricsError: something went wrong enabling metrics.
    """
    try:
        metric_listener = {
            "port": int(PROMETHEUS_TARGET_PORT),
            "type": "metrics",
            "bind_addresses": ["::"],
        }
        current_yaml["listeners"].extend([metric_listener])
        current_yaml["enable_metrics"] = True
    except KeyError as exc:
        raise EnableMetricsError(str(exc)) from exc


def enable_replication(current_yaml: dict) -> None:
    """Change the Synapse configuration to enable replication.

    Args:
        current_yaml: current configuration.

    Raises:
        WorkloadError: something went wrong enabling replication.
    """
    try:
        resources = {"names": ["replication"]}
        metric_listener = {
            "port": 8034,
            "type": "http",
            "bind_addresses": ["::"],
            "resources": [resources],
        }
        current_yaml["listeners"].extend([metric_listener])
    except KeyError as exc:
        raise WorkloadError(str(exc)) from exc


def enable_forgotten_room_retention(current_yaml: dict) -> None:
    """Change the Synapse configuration to enable forgotten_room_retention_period.

    Args:
        current_yaml: current configuration.
    """
    current_yaml["forgotten_room_retention_period"] = "28d"


def disable_password_config(current_yaml: dict) -> None:
    """Change the Synapse configuration to disable password config.

    Args:
        current_yaml: current configuration.
    """
    current_yaml["password_config"] = {"enabled": False}


def disable_room_list_search(current_yaml: dict) -> None:
    """Change the Synapse configuration to disable room_list_search.

    Args:
        current_yaml: current configuration.
    """
    current_yaml["enable_room_list_search"] = False


def enable_serve_server_wellknown(current_yaml: dict) -> None:
    """Change the Synapse configuration to enable server wellknown file.

    Args:
        current_yaml: current configuration.
    """
    current_yaml["serve_server_wellknown"] = True


def enable_instance_map(current_yaml: dict, charm_state: CharmState) -> None:
    """Change the Synapse configuration to instance_map config.

    Args:
        current_yaml: current configuration.
        charm_state: Instance of CharmState.
    """
    current_yaml["instance_map"] = charm_state.instance_map_config


def enable_stream_writers(current_yaml: dict, charm_state: CharmState) -> None:
    """Change the Synapse configuration to stream_writers config.

    Args:
        current_yaml: current configuration.
        charm_state: Instance of CharmState.
    """
    persisters = []
    if charm_state.instance_map_config is not None:
        persisters = [key for key in charm_state.instance_map_config.keys() if key != "main"]
    current_yaml["stream_writers"] = {"events": persisters}


def enable_federation_domain_whitelist(current_yaml: dict, charm_state: CharmState) -> None:
    """Change the Synapse configuration to enable federation_domain_whitelist.

    Args:
        current_yaml: current configuration.
        charm_state: Instance of CharmState.

    Raises:
        WorkloadError: something went wrong enabling configuration.
    """
    try:
        federation_domain_whitelist = charm_state.synapse_config.federation_domain_whitelist
        if federation_domain_whitelist is not None:
            current_yaml["federation_domain_whitelist"] = _create_tuple_from_string_list(
                federation_domain_whitelist
            )
    except KeyError as exc:
        raise WorkloadError(str(exc)) from exc


def enable_trusted_key_servers(current_yaml: dict, charm_state: CharmState) -> None:
    """Change the Synapse configuration to set trusted_key_servers.

    Args:
        current_yaml: current configuration.
        charm_state: Instance of CharmState.

    Raises:
        WorkloadError: something went wrong enabling configuration.
    """
    try:
        trusted_key_servers = charm_state.synapse_config.trusted_key_servers
        if trusted_key_servers is not None:
            current_yaml["trusted_key_servers"] = tuple(
                {"server_name": f"{item}"}
                for item in _create_tuple_from_string_list(trusted_key_servers)
            )
    except KeyError as exc:
        raise WorkloadError(str(exc)) from exc


def enable_allow_public_rooms_over_federation(current_yaml: dict) -> None:
    """Change the Synapse configuration to allow public rooms in federation.

    Args:
        current_yaml: current configuration.
    """
    current_yaml["allow_public_rooms_over_federation"] = True


def _create_tuple_from_string_list(string_list: str) -> tuple[str, ...]:
    """Format IP range whitelist.

    Args:
        string_list: comma separated list configuration.

    Returns:
        Tuple as expected by Synapse.
    """
    return tuple(item.strip() for item in string_list.split(","))


def enable_ip_range_whitelist(current_yaml: dict, charm_state: CharmState) -> None:
    """Change the Synapse configuration to enable ip_range_whitelist.

    Args:
        current_yaml: current configuration.
        charm_state: Instance of CharmState.

    Raises:
        WorkloadError: something went wrong enabling configuration.
    """
    try:
        ip_range_whitelist = charm_state.synapse_config.ip_range_whitelist
        if ip_range_whitelist is None:
            logger.warning("enable_ip_range_whitelist called but config is empty")
            return
        current_yaml["ip_range_whitelist"] = _create_tuple_from_string_list(ip_range_whitelist)
    except KeyError as exc:
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


def _get_irc_bridge_config(charm_state: CharmState, db_connect_string: str) -> typing.Dict:
    """Create config as expected by irc bridge.

    Args:
        charm_state: Instance of CharmState.
        db_connect_string: database connection string.

    Returns:
        IRC Bridge configuration
    """
    irc_config_file = Path("templates/irc_bridge_production.yaml").read_text(encoding="utf-8")
    config = yaml.safe_load(irc_config_file)
    config["homeserver"]["url"] = SYNAPSE_URL
    config["homeserver"]["domain"] = charm_state.synapse_config.server_name
    config["database"]["connectionString"] = db_connect_string
    if charm_state.synapse_config.irc_bridge_admins:
        config["ircService"]["permissions"] = {}
        for admin in charm_state.synapse_config.irc_bridge_admins:
            config["ircService"]["permissions"][f"@{admin}"] = "admin"
    return config


def create_irc_bridge_config(
    container: ops.Container, charm_state: CharmState, db_connect_string: str
) -> None:
    """Create irc bridge configuration.

    Args:
        container: Container of the charm.
        charm_state: Instance of CharmState.
        db_connect_string: database connection string.

    Raises:
        CreateIRCBridgeConfigError: something went wrong creating irc bridge config.
    """
    try:
        config = _get_irc_bridge_config(
            charm_state=charm_state, db_connect_string=db_connect_string
        )
        container.push(IRC_BRIDGE_CONFIG_PATH, yaml.safe_dump(config), make_dirs=True)
    except ops.pebble.PathError as exc:
        raise CreateIRCBridgeConfigError(str(exc)) from exc


def _get_irc_bridge_app_registration(container: ops.Container) -> None:  # pragma: no cover
    # the functionality is tested already in unit tests creating files
    """Create registration file as expected by irc bridge.

    Args:
        container: Container of the charm.

    Raises:
        WorkloadError: something went wrong creating irc bridge registration.
    """
    registration_result = _exec(
        container,
        [
            "/bin/bash",
            "-c",
            f"[[ -f {IRC_BRIDGE_REGISTRATION_PATH} ]] || "
            f"/bin/node /app/app.js -r -f {IRC_BRIDGE_REGISTRATION_PATH} "
            f"-u http://localhost:{IRC_BRIDGE_HEALTH_PORT} "
            f"-c {IRC_BRIDGE_CONFIG_PATH} -l {IRC_BRIDGE_BOT_NAME}",
        ],
    )
    if registration_result.exit_code:
        logger.error(
            "creating irc app registration failed, stdout: %s, stderr: %s",
            registration_result.stdout,
            registration_result.stderr,
        )
        raise WorkloadError("Creating irc app registration failed, please check the logs")


def create_irc_bridge_app_registration(container: ops.Container) -> None:  # pragma: no cover
    # the functionality is tested already in unit tests creating files
    """Create irc bridge app registration.

    Args:
        container: Container of the charm.

    Raises:
        CreateIRCBridgeRegistrationError: error creating irc bridge app registration.
    """
    try:
        _get_irc_bridge_app_registration(container=container)
    except ops.pebble.PathError as exc:
        raise CreateIRCBridgeRegistrationError(str(exc)) from exc


def add_app_service_config_field(current_yaml: dict) -> None:
    """Add app_service_config_files to the Synapse configuration.

    Args:
        current_yaml: current configuration.
    """
    current_yaml["app_service_config_files"] = [IRC_BRIDGE_REGISTRATION_PATH]


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


def enable_saml(current_yaml: dict, charm_state: CharmState) -> None:
    """Change the Synapse configuration to enable SAML.

    Args:
        current_yaml: current configuration.
        charm_state: Instance of CharmState.

    Raises:
        EnableSAMLError: something went wrong enabling SAML.
    """
    try:
        if charm_state.synapse_config.public_baseurl is not None:
            current_yaml["public_baseurl"] = charm_state.synapse_config.public_baseurl
        # enable x_forwarded to pass expected headers
        current_listeners = current_yaml["listeners"]
        updated_listeners = [
            {
                **item,
                "x_forwarded": (
                    True
                    if "x_forwarded" in item and not item["x_forwarded"]
                    else item.get("x_forwarded", False)
                ),
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
    except KeyError as exc:
        raise EnableSAMLError(str(exc)) from exc


def enable_smtp(current_yaml: dict, charm_state: CharmState) -> None:
    """Change the Synapse configuration to enable SMTP.

    Args:
        current_yaml: current configuration.
        charm_state: Instance of CharmState.

    Raises:
        EnableSMTPError: something went wrong enabling SMTP.
    """
    try:
        current_yaml["email"] = {}
        current_yaml["email"]["enable_notifs"] = charm_state.synapse_config.enable_email_notifs
        current_yaml["email"]["notif_from"] = charm_state.synapse_config.notif_from

        if charm_state.smtp_config is None:
            raise EnableSMTPError(
                "SMTP Configuration not found. "
                "Please verify the integration between SMTP Integrator and Synapse."
            )

        smtp_config = charm_state.smtp_config
        current_yaml["email"]["smtp_host"] = smtp_config["host"]
        current_yaml["email"]["smtp_port"] = smtp_config["port"]
        if charm_state.smtp_config["user"] is not None:
            current_yaml["email"]["smtp_user"] = smtp_config["user"]
        if charm_state.smtp_config["password"] is not None:
            current_yaml["email"]["smtp_pass"] = smtp_config["password"]
        current_yaml["email"]["enable_tls"] = smtp_config["enable_tls"]
        current_yaml["email"]["force_tls"] = smtp_config["force_tls"]
        current_yaml["email"]["require_transport_security"] = smtp_config[
            "require_transport_security"
        ]
    except KeyError as exc:
        raise EnableSMTPError(str(exc)) from exc


def enable_media(current_yaml: dict, charm_state: CharmState) -> None:
    """Change the Synapse configuration to enable S3.

    Args:
        current_yaml: Current Configuration.
        charm_state: Instance of CharmState.

    Raises:
        WorkloadError: something went wrong enabling S3.
    """
    try:
        if charm_state.media_config is None:
            raise WorkloadError(
                "Media Configuration not found. "
                "Please verify the integration between Media and Synapse."
            )
        current_yaml["media_storage_providers"] = [
            {
                "module": "s3_storage_provider.S3StorageProviderBackend",
                "store_local": True,
                "store_remote": True,
                "store_synchronous": True,
                "config": {
                    "bucket": charm_state.media_config["bucket"],
                    "region_name": charm_state.media_config["region_name"],
                    "endpoint_url": charm_state.media_config["endpoint_url"],
                    "access_key_id": charm_state.media_config["access_key_id"],
                    "secret_access_key": charm_state.media_config["secret_access_key"],
                    "prefix": charm_state.media_config["prefix"],
                },
            },
        ]
    except KeyError as exc:
        raise WorkloadError(str(exc)) from exc


def enable_redis(current_yaml: dict, charm_state: CharmState) -> None:
    """Change the Synapse configuration to enable Redis.

    Args:
        current_yaml: current configuration.
        charm_state: Instance of CharmState.

    Raises:
        WorkloadError: something went wrong enabling SMTP.
    """
    try:
        current_yaml["redis"] = {}

        if charm_state.redis_config is None:
            raise WorkloadError(
                "Redis Configuration not found. "
                "Please verify the integration between Redis and Synapse."
            )

        redis_config = charm_state.redis_config
        current_yaml["redis"]["enabled"] = True
        current_yaml["redis"]["host"] = redis_config["host"]
        current_yaml["redis"]["port"] = redis_config["port"]
    except KeyError as exc:
        raise WorkloadError(str(exc)) from exc


def enable_room_list_publication_rules(current_yaml: dict, charm_state: CharmState) -> None:
    """Change the Synapse configuration to enable room_list_publication_rules.

    This configuration is based on publish_rooms_allowlist charm configuration.
    Once is set, a deny rule is added to prevent any other user to publish rooms.

    Args:
        current_yaml: current configuration.
        charm_state: Instance of CharmState.

    Raises:
        WorkloadError: something went wrong enabling room_list_publication_rules.
    """
    room_list_publication_rules = []
    # checking publish_rooms_allowlist to fix union-attr mypy error
    publish_rooms_allowlist = charm_state.synapse_config.publish_rooms_allowlist
    if publish_rooms_allowlist:
        for user in publish_rooms_allowlist:
            rule = {"user_id": user, "alias": "*", "room_id": "*", "action": "allow"}
            room_list_publication_rules.append(rule)

    if len(room_list_publication_rules) == 0:
        raise WorkloadError("publish_rooms_allowlist has unexpected value. Please, verify it.")

    last_rule = {"user_id": "*", "alias": "*", "room_id": "*", "action": "deny"}
    room_list_publication_rules.append(last_rule)
    current_yaml["room_list_publication_rules"] = room_list_publication_rules


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
        "SYNAPSE_CONFIG_DIR": SYNAPSE_CONFIG_DIR,
        "SYNAPSE_CONFIG_PATH": SYNAPSE_CONFIG_PATH,
        "SYNAPSE_DATA_DIR": SYNAPSE_DATA_DIR,
        "SYNAPSE_REPORT_STATS": f"{charm_state.synapse_config.report_stats}",
        "SYNAPSE_SERVER_NAME": f"{charm_state.synapse_config.server_name}",
        # TLS disabled so the listener is HTTP. HTTPS will be handled by Traefik.
        # TODO verify support to HTTPS backend before changing this  # pylint: disable=fixme
        "SYNAPSE_NO_TLS": str(True),
        "LD_PRELOAD": "/usr/lib/x86_64-linux-gnu/libjemalloc.so.2",
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


def generate_nginx_config(container: ops.Container, main_unit_address: str) -> None:
    """Generate NGINX configuration based on templates.

    1. Copy template files as configuration files to be used.
    2. Run sed command to replace string main-unit in configuration files.
    3. Reload NGINX.

    Args:
        container: Container of the charm.
        main_unit_address: Main unit address to be used in configuration.
    """
    container.exec(
        [
            "cp",
            "/etc/nginx/main_location.conf.template",
            "/etc/nginx/main_location.conf",
        ],
    ).wait()
    container.exec(
        ["sed", "-i", f"s/main-unit/{main_unit_address}/g", "/etc/nginx/main_location.conf"],
    ).wait()
    container.exec(
        [
            "cp",
            "/etc/nginx/abuse_report_location.conf.template",
            "/etc/nginx/abuse_report_location.conf",
        ],
    ).wait()
    container.exec(
        [
            "sed",
            "-i",
            f"s/main-unit/{main_unit_address}/g",
            "/etc/nginx/abuse_report_location.conf",
        ],
    ).wait()
