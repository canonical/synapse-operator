#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helper module used to manage interactions with Synapse."""

import logging
import typing
from pathlib import Path

import ops
import yaml
from jinja2 import Environment, FileSystemLoader
from ops.pebble import APIError, ExecError, PathError

from charm_types import MediaConfiguration
from state.charm_state import CharmState

SYNAPSE_CONFIG_DIR = "/data"

CHECK_ALIVE_NAME = "synapse-alive"
CHECK_NGINX_READY_NAME = "synapse-nginx-ready"
CHECK_READY_NAME = "synapse-ready"
COMMAND_MIGRATE_CONFIG = "migrate_config"
MODERATION_CONFIG_PATH = f"{SYNAPSE_CONFIG_DIR}/config/production.yaml"
SYNAPSE_EXPORTER_PORT = "9000"
STATS_EXPORTER_PORT = "9877"
SYNAPSE_COMMAND_PATH = "/start.py"
SYNAPSE_CONFIG_PATH = f"{SYNAPSE_CONFIG_DIR}/homeserver.yaml"
SYNAPSE_CONTAINER_NAME = "synapse"
SYNAPSE_CRON_SERVICE_NAME = "synapse-cron"
SYNAPSE_DATA_DIR = "/data"
SYNAPSE_DEFAULT_MEDIA_STORE_PATH = "/media_store"
SYNAPSE_FEDERATION_SENDER_SERVICE_NAME = "synapse-federation-sender"
SYNAPSE_GROUP = "synapse"
SYNAPSE_MEDIA_SYNC_CLEANUP_LOG = f"{SYNAPSE_CONFIG_DIR}/media_sync_cleanup.log"
SYNAPSE_NGINX_PORT = 8080
SYNAPSE_NGINX_SERVICE_NAME = "synapse-nginx"
SYNAPSE_PEER_RELATION_NAME = "synapse-peers"
SYNAPSE_PORT = 8008
SYNAPSE_SERVICE_NAME = "synapse"
SYNAPSE_USER = "synapse"
SYNAPSE_URL = f"http://localhost:{SYNAPSE_PORT}"
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
            f"one {configured_server_name}. Please revert the config."
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


def generate_nginx_config(container: ops.Container, main_unit_address: str) -> None:
    """Generate NGINX configuration based on templates.

    1. Copy template files as configuration files to be used.
    2. Run sed command to replace string main-unit in configuration files.
    3. Reload NGINX.

    Args:
        container: Container of the charm.
        main_unit_address: Main unit address to be used in configuration.
    """
    file_loader = FileSystemLoader(Path("./templates"), followlinks=True)
    env = Environment(loader=file_loader, autoescape=True)

    # List of templates and their corresponding output files
    templates = [
        ("main_location.conf.j2", "main_location.conf"),
        ("abuse_report_location.conf.j2", "abuse_report_location.conf"),
    ]

    for template_name, output_file in templates:
        template = env.get_template(template_name)
        output = template.render(main_unit_address=main_unit_address)
        container.push(f"/etc/nginx/{output_file}", output, make_dirs=True)


def generate_worker_config(unit_number: str, is_main: bool) -> dict:
    """Generate worker configuration.

    Args:
        unit_number: Unit number to be used in the worker_name field.
        is_main: if unit is main.

    Returns:
        Worker configuration.
    """
    worker_listeners = [
        {
            "type": "http",
            "bind_addresses": ["::"],
            "port": 8034,
            "resources": [{"names": ["replication"]}],
        }
    ]
    if not is_main:
        worker_listeners.extend(
            [
                {
                    "type": "http",
                    "bind_addresses": ["::"],
                    "port": 8008,
                    "x_forwarded": True,
                    "resources": [{"names": ["client", "federation"]}],
                },
                {
                    "type": "metrics",
                    "bind_addresses": ["::"],
                    "port": int(SYNAPSE_EXPORTER_PORT),
                },
            ]
        )
    worker_config = {
        "worker_app": "synapse.app.generic_worker",
        "worker_name": "federationsender1" if is_main else f"worker{unit_number}",
        "worker_listeners": worker_listeners,
        "worker_log_config": "/data/log.config",
    }
    return worker_config


def create_registration_secrets_files(container: ops.Container, charm_state: CharmState) -> None:
    """Create registration secrets files.

    Args:
        container: Container of the charm.
        charm_state: Instance of CharmState.
    """
    container.exec(["rm", "-f", f"{SYNAPSE_CONFIG_DIR}/appservice-registration-*.yaml"])
    if charm_state.registration_secrets:
        for registration_secret in charm_state.registration_secrets:
            registration_secret.file_path.write_text(registration_secret.value, encoding="utf-8")


def generate_moderation_config(container: ops.Container, charm_state: CharmState) -> None:
    """Generate moderation configuration.

    Args:
        container: Container of the charm.
        charm_state: Instance of CharmState.
    """
    with open("templates/moderation_production.yaml", encoding="utf-8") as moderation_config_file:
        config = yaml.safe_load(moderation_config_file)
        config["homeserverUrl"] = f"http://localhost:{SYNAPSE_NGINX_PORT}"
        config["rawHomeserverUrl"] = f"http://localhost:{SYNAPSE_NGINX_PORT}"
        config["accessToken"] = str(charm_state.moderation_token)
        room_alias = charm_state.synapse_config.moderation_room_alias
        config["managementRoom"] = f"#{room_alias}:{charm_state.synapse_config.server_name}"
        container.push(MODERATION_CONFIG_PATH, yaml.safe_dump(config), make_dirs=True)


def run_media_sync_cleanup(container: ops.Container, media_config: MediaConfiguration) -> None:
    """Run s3_media_upload command and clean media directory locally.

    Args:
        container: Container of the charm.
        media_config: Instance of MediaConfiguration.

    Raises:
        WorkloadError: if one of the commands fail.
    """
    if not media_config:
        logger.warning("media_sync_cleanup started but no media integration was found, skipping")
        return
    media_store_path = get_media_store_path(container)
    s3_media_upload_path = "/usr/local/bin/s3_media_upload"
    commands = [
        [
            s3_media_upload_path,
            "--no-progress",
            "update",
            "--homeserver-config-path",
            SYNAPSE_CONFIG_PATH,
            media_store_path,
            "1d",
        ],
        [
            s3_media_upload_path,
            "--no-progress",
            "upload",
            media_store_path,
            media_config["bucket"],
            "--delete",
            "--storage-class",
            "STANDARD",
            "--endpoint-url",
            media_config["endpoint_url"],
            "--prefix",
            media_config["prefix"],
        ],
    ]

    try:
        environment = {
            "AWS_ACCESS_KEY_ID": media_config["access_key_id"],
            "AWS_SECRET_ACCESS_KEY": media_config["secret_access_key"],
            "AWS_DEFAULT_REGION": media_config["region_name"],
        }
        for command in commands:
            logger.info("media_sync_cleanup executing: %s", " ".join(command))

            exec_process = container.exec(
                command,
                user=SYNAPSE_USER,
                group=SYNAPSE_GROUP,
                working_dir=SYNAPSE_CONFIG_DIR,
                environment=environment,
            )
            stdout, stderr = exec_process.wait_output()
            logger.info("media_sync_cleanup output: %s", stdout.strip())
            if stderr:
                logger.warning("media_sync_cleanup errors: %s", stderr.strip())

        logger.info("media_sync_cleanup completed successfully.")

    except (APIError, ops.pebble.ExecError) as exc:
        logger.error("media_sync_cleanup failed: %s", str(exc))
        raise WorkloadError("media_sync_cleanup failed, verify the logs") from exc
