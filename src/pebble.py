#!/usr/bin/env python3

# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

# Ignoring for the config change call
# mypy: disable-error-code="attr-defined"

"""Class to interact with pebble."""

import logging
import typing

import ops
import yaml
from deepdiff import DeepDiff
from ops.pebble import Check

import synapse
from charm_state import CharmState

logger = logging.getLogger(__name__)

STATS_EXPORTER_SERVICE_NAME = "stats-exporter"


class PebbleServiceError(Exception):
    """Exception raised when something fails while interacting with Pebble.

    Attrs:
        msg (str): Explanation of the error.
    """

    def __init__(self, msg: str):
        """Initialize a new instance of the PebbleServiceError exception.

        Args:
            msg (str): Explanation of the error.
        """
        self.msg = msg


def check_synapse_alive(charm_state: CharmState) -> ops.pebble.CheckDict:
    """Return the Synapse container alive check.

    Args:
        charm_state: Instance of CharmState.

    Returns:
        Dict: check object converted to its dict representation.
    """
    check = Check(synapse.CHECK_ALIVE_NAME)
    check.override = "replace"
    check.level = "alive"
    check.tcp = {"port": synapse.SYNAPSE_PORT}
    experimental_alive_check = charm_state.synapse_config.experimental_alive_check
    if experimental_alive_check:
        # The default values will tolerate failure for ~10 minutes before restarting Synapse
        check.period = experimental_alive_check.get("period", "2m")
        check.threshold = experimental_alive_check.get("threshold", 5)
        check.timeout = experimental_alive_check.get("timeout", "20s")
    return check.to_dict()


def check_synapse_ready() -> ops.pebble.CheckDict:
    """Return the Synapse container ready check.

    Returns:
        Dict: check object converted to its dict representation.
    """
    check = Check(synapse.CHECK_READY_NAME)
    check.override = "replace"
    check.level = "ready"
    check.timeout = "20s"
    check.period = "2m"
    check.threshold = 5
    check.http = {"url": f"{synapse.SYNAPSE_URL}/health"}
    return check.to_dict()


def restart_synapse(
    charm_state: CharmState, container: ops.model.Container, is_main: bool = True
) -> None:
    """Restart Synapse service.

    This will force a restart even if its plan hasn't changed.

    Args:
        charm_state: Instance of CharmState
        container: Synapse container.
        is_main: if unit is main.
    """
    logger.debug("Restarting the Synapse container. Main: %s", str(is_main))
    container.add_layer(
        synapse.SYNAPSE_SERVICE_NAME, _pebble_layer(charm_state, is_main), combine=True
    )
    container.add_layer(
        synapse.SYNAPSE_CRON_SERVICE_NAME, _cron_pebble_layer(charm_state), combine=True
    )
    container.restart(synapse.SYNAPSE_SERVICE_NAME)


def check_nginx_ready() -> ops.pebble.CheckDict:
    """Return the Synapse NGINX container check.

    Returns:
        Dict: check object converted to its dict representation.
    """
    check = Check(synapse.CHECK_NGINX_READY_NAME)
    check.override = "replace"
    check.level = "ready"
    check.http = {"url": f"http://localhost:{synapse.SYNAPSE_NGINX_PORT}/health"}
    return check.to_dict()


def check_mjolnir_ready() -> ops.pebble.CheckDict:
    """Return the Synapse Mjolnir service check.

    Returns:
        Dict: check object converted to its dict representation.
    """
    check = Check(synapse.CHECK_MJOLNIR_READY_NAME)
    check.override = "replace"
    check.level = "ready"
    check.http = {"url": f"http://localhost:{synapse.MJOLNIR_HEALTH_PORT}/healthz"}
    check.timeout = "10s"
    check.threshold = 5
    check.period = "1m"
    return check.to_dict()


def restart_nginx(container: ops.model.Container, main_unit_address: str) -> None:
    """Restart Synapse NGINX service and regenerate configuration.

    Args:
        container: Charm container.
        main_unit_address: Main unit address to be used in configuration.
    """
    container.add_layer("synapse-nginx", _nginx_pebble_layer(), combine=True)
    synapse.generate_nginx_config(container=container, main_unit_address=main_unit_address)
    container.restart(synapse.SYNAPSE_NGINX_SERVICE_NAME)


def replan_mjolnir(container: ops.model.Container) -> None:
    """Replan Synapse Mjolnir service.

    Args:
        container: Charm container.
    """
    container.add_layer("synapse-mjolnir", _mjolnir_pebble_layer(), combine=True)
    container.replan()


def replan_stats_exporter(container: ops.model.Container, charm_state: CharmState) -> None:
    """Replan Synapse StatsExporter service.

    Args:
        container: Charm container.
        charm_state: Instance of CharmState.
    """
    layer = _stats_exporter_pebble_layer()
    datasource = charm_state.datasource
    if datasource is not None:
        layer["services"][STATS_EXPORTER_SERVICE_NAME]["environment"] = {
            "PROM_SYNAPSE_DATABASE": datasource["db"],
            "PROM_SYNAPSE_HOST": datasource["host"],
            "PROM_SYNAPSE_PORT": datasource["port"],
            "PROM_SYNAPSE_USER": datasource["user"],
            "PROM_SYNAPSE_PASSWORD": datasource["password"],
        }
        try:
            container.add_layer(STATS_EXPORTER_SERVICE_NAME, layer, combine=True)
            container.start(STATS_EXPORTER_SERVICE_NAME)
        except ops.pebble.Error as e:
            # Error being ignore to prevent Synapse Stats Exporter to affect
            # Synapse. This can be caught in logs or using Prometheus alert.
            logger.debug("Ignoring error while restarting Synapse Stats Exporter")
            logger.exception(str(e))


def replan_synapse_federation_sender(
    container: ops.model.Container, charm_state: CharmState
) -> None:
    """Replan Synapse Federation Sender service.

    Args:
        container: Charm container.
        charm_state: Instance of CharmState.
    """
    container.add_layer(
        "synapse-federation-sender", _pebble_layer_federation_sender(charm_state), combine=True
    )
    container.replan()


def _get_synapse_config(container: ops.model.Container) -> dict:
    """Get the current Synapse configuration.

    Args:
        container: Synapse container.

    Returns:
        dict: Synapse configuration.

    Raises:
        PebbleServiceError: if something goes wrong while interacting with Pebble.
    """
    try:
        config = container.pull(synapse.SYNAPSE_CONFIG_PATH).read()
        current_synapse_config = yaml.safe_load(config)
        return current_synapse_config
    except ops.pebble.PathError as exc:
        raise PebbleServiceError(str(exc)) from exc


def _push_synapse_config(
    container: ops.model.Container,
    current_synapse_config: dict,
    config_path: str = synapse.SYNAPSE_CONFIG_PATH,
) -> None:
    """Push the Synapse configuration to the container.

    Args:
        container: Synapse container.
        current_synapse_config: Synapse configuration.
        config_path: Synapse configuration file path.

    Raises:
        PebbleServiceError: if something goes wrong while interacting with Pebble.
    """
    try:
        container.push(config_path, yaml.dump(current_synapse_config).encode("utf-8"))
    except ops.pebble.PathError as exc:
        raise PebbleServiceError(str(exc)) from exc


def _environment_has_changed(
    charm_state: CharmState, container: ops.model.Container, is_main: bool = True
) -> bool:
    """Check if environment has changed.

    Args:
        charm_state: Instance of CharmState
        container: Charm container.
        is_main: if unit is main.

    Returns:
        True if environment has changed.
    """
    existing_services = container.get_plan().to_dict().get("services", {})
    current_services = _pebble_layer(charm_state, is_main).get("services", {})

    existing_env = existing_services.get(synapse.SYNAPSE_SERVICE_NAME, {}).get("environment", {})
    current_env = current_services.get(synapse.SYNAPSE_SERVICE_NAME, {}).get("environment", {})

    env_has_changed = DeepDiff(
        existing_env,
        current_env,
        ignore_order=True,
        ignore_string_case=True,
    )
    logging.debug("The environment change is: %s", env_has_changed)
    return env_has_changed is not None


# The complexity of this method will be reviewed.
def reconcile(  # noqa: C901 pylint: disable=too-many-branches,too-many-statements
    charm_state: CharmState,
    container: ops.model.Container,
    is_main: bool = True,
    unit_number: str = "",
) -> None:
    """Reconcile Synapse configuration with charm state.

    This is the main entry for changes that require a restart done via Pebble.

    Args:
        charm_state: Instance of CharmState
        container: Charm container.
        is_main: if unit is main.
        unit_number: unit number id to set the worker name.

    Raises:
        PebbleServiceError: if something goes wrong while interacting with Pebble.
    """
    try:
        if _environment_has_changed(container=container, charm_state=charm_state, is_main=is_main):
            # Configurations set via environment variables:
            # synapse_report_stats, database, and proxy
            logging.info("Environment has changed, configuration will be recreated.")
            synapse.execute_migrate_config(container=container, charm_state=charm_state)
        existing_synapse_config = _get_synapse_config(container)
        current_synapse_config = _get_synapse_config(container)
        if charm_state.synapse_config.block_non_admin_invites:
            logger.debug("pebble.change_config: Enabling Block non admin invites")
            synapse.block_non_admin_invites(current_synapse_config, charm_state=charm_state)
        synapse.enable_metrics(current_synapse_config)
        synapse.enable_forgotten_room_retention(current_synapse_config)
        synapse.enable_media_retention(current_synapse_config)
        synapse.enable_stale_devices_deletion(current_synapse_config)
        synapse.enable_rc_joins_remote_rate(current_synapse_config, charm_state=charm_state)
        synapse.enable_serve_server_wellknown(current_synapse_config)
        synapse.enable_replication(current_synapse_config)
        if charm_state.synapse_config.invite_checker_policy_rooms:
            logger.debug("pebble.change_config: Enabling enable_synapse_invite_checker")
            synapse.enable_synapse_invite_checker(current_synapse_config, charm_state=charm_state)
        if charm_state.synapse_config.limit_remote_rooms_complexity:
            logger.debug("pebble.change_config: Enabling limit_remote_rooms_complexity")
            synapse.enable_limit_remote_rooms_complexity(
                current_synapse_config, charm_state=charm_state
            )
        if charm_state.instance_map_config is not None:
            logger.debug("pebble.change_config: Enabling instance_map")
            synapse.enable_instance_map(current_synapse_config, charm_state=charm_state)
            logger.debug("pebble.change_config: Enabling stream_writers")
            synapse.enable_stream_writers(current_synapse_config, charm_state=charm_state)
            # the main unit will have an additional layer for running federation sender worker
            if is_main:
                logging.info("pebble.change_config: Adding Federation Sender layer")
                synapse.enable_federation_sender(current_synapse_config)
                replan_synapse_federation_sender(container=container, charm_state=charm_state)
        if charm_state.saml_config is not None:
            logger.debug("pebble.change_config: Enabling SAML")
            synapse.enable_saml(current_synapse_config, charm_state=charm_state)
        if charm_state.smtp_config is not None:
            logger.debug("pebble.change_config: Enabling SMTP")
            synapse.enable_smtp(current_synapse_config, charm_state=charm_state)
        if charm_state.media_config is not None:
            logger.debug("pebble.change_config: Enabling Media")
            synapse.enable_media(current_synapse_config, charm_state=charm_state)
        if charm_state.redis_config is not None:
            logger.debug("pebble.change_config: Enabling Redis")
            synapse.enable_redis(current_synapse_config, charm_state=charm_state)
        if not charm_state.synapse_config.enable_password_config:
            synapse.disable_password_config(current_synapse_config)
        if charm_state.synapse_config.federation_domain_whitelist:
            synapse.enable_federation_domain_whitelist(
                current_synapse_config, charm_state=charm_state
            )
        if charm_state.synapse_config.allow_public_rooms_over_federation:
            synapse.enable_allow_public_rooms_over_federation(current_synapse_config)
        if not charm_state.synapse_config.enable_room_list_search:
            synapse.disable_room_list_search(current_synapse_config)
        if charm_state.synapse_config.trusted_key_servers:
            synapse.enable_trusted_key_servers(current_synapse_config, charm_state=charm_state)
        if charm_state.synapse_config.ip_range_whitelist:
            synapse.enable_ip_range_whitelist(current_synapse_config, charm_state=charm_state)
        if charm_state.synapse_config.publish_rooms_allowlist:
            synapse.enable_room_list_publication_rules(
                current_synapse_config, charm_state=charm_state
            )
        if charm_state.datasource and is_main:
            logger.info("Synapse Stats Exporter enabled.")
            replan_stats_exporter(container=container, charm_state=charm_state)
        config_has_changed = DeepDiff(
            existing_synapse_config,
            current_synapse_config,
            ignore_order=True,
            ignore_string_case=True,
        )
        if config_has_changed:
            logging.info("Configuration has changed, Synapse will be restarted.")
            logging.debug("The change is: %s", config_has_changed)
            # Push worker configuration
            _push_synapse_config(
                container,
                synapse.generate_worker_config(unit_number, is_main),
                config_path=synapse.SYNAPSE_WORKER_CONFIG_PATH,
            )
            # Push main configuration
            _push_synapse_config(container, current_synapse_config)
            synapse.validate_config(container=container)
            restart_synapse(container=container, charm_state=charm_state, is_main=is_main)
        else:
            logging.info("Configuration has not changed, no action.")
    except (synapse.WorkloadError, ops.pebble.PathError) as exc:
        raise PebbleServiceError(str(exc)) from exc


def reset_instance(charm_state: CharmState, container: ops.model.Container) -> None:
    """Reset instance.

    Args:
        charm_state: Instance of CharmState
        container: Charm container.

    Raises:
        PebbleServiceError: if something goes wrong while interacting with Pebble.
    """
    # This is needed in the case of relation with Postgresql.
    # If there is open connections it won't be possible to drop the database.
    try:
        logger.info("Replan service to not restart")
        container.add_layer(
            synapse.SYNAPSE_CONTAINER_NAME,
            _pebble_layer_without_restart(charm_state),
            combine=True,
        )
        container.replan()
        logger.info("Stop Synapse instance")
        container.stop(synapse.SYNAPSE_SERVICE_NAME)
        logger.info("Erase Synapse data")
        synapse.reset_instance(container)
    except ops.pebble.PathError as exc:
        raise PebbleServiceError(str(exc)) from exc


def _pebble_layer(charm_state: CharmState, is_main: bool = True) -> ops.pebble.LayerDict:
    """Return a dictionary representing a Pebble layer.

    Args:
        charm_state: Instance of CharmState
        is_main: if unit is main.

    Returns:
        pebble layer for Synapse
    """
    command = synapse.SYNAPSE_COMMAND_PATH
    if not is_main:
        command = (
            f"{command} run -m synapse.app.generic_worker "
            f"--config-path {synapse.SYNAPSE_CONFIG_PATH} "
            f"--config-path {synapse.SYNAPSE_WORKER_CONFIG_PATH}"
        )

    layer = {
        "summary": "Synapse layer",
        "description": "pebble config layer for Synapse",
        "services": {
            synapse.SYNAPSE_SERVICE_NAME: {
                "override": "replace",
                "summary": "Synapse application service",
                "startup": "enabled",
                "command": command,
                "environment": synapse.get_environment(charm_state),
            }
        },
        "checks": {
            synapse.CHECK_ALIVE_NAME: check_synapse_alive(charm_state),
            synapse.CHECK_READY_NAME: check_synapse_ready(),
        },
    }
    return typing.cast(ops.pebble.LayerDict, layer)


def _pebble_layer_without_restart(charm_state: CharmState) -> ops.pebble.LayerDict:
    """Return a dictionary representing a Pebble layer without restart.

    Args:
        charm_state: Instance of CharmState

    Returns:
        pebble layer
    """
    new_layer = _pebble_layer(charm_state)
    new_layer["services"][synapse.SYNAPSE_SERVICE_NAME]["on-success"] = "ignore"
    new_layer["services"][synapse.SYNAPSE_SERVICE_NAME]["on-failure"] = "ignore"
    ignore = {synapse.CHECK_READY_NAME: "ignore"}
    new_layer["services"][synapse.SYNAPSE_SERVICE_NAME]["on-check-failure"] = ignore
    return new_layer


def _nginx_pebble_layer() -> ops.pebble.LayerDict:
    """Generate pebble config for the synapse-nginx container.

    Returns:
        The pebble configuration for the NGINX container.
    """
    layer = {
        "summary": "Synapse nginx layer",
        "description": "Synapse nginx layer",
        "services": {
            synapse.SYNAPSE_NGINX_SERVICE_NAME: {
                "override": "replace",
                "summary": "Nginx service",
                "command": "/usr/sbin/nginx",
                "startup": "enabled",
            },
        },
        "checks": {
            synapse.CHECK_NGINX_READY_NAME: check_nginx_ready(),
        },
    }
    return typing.cast(ops.pebble.LayerDict, layer)


def _mjolnir_pebble_layer() -> ops.pebble.LayerDict:
    """Generate pebble config for the mjolnir service.

    Returns:
        The pebble configuration for the mjolnir service.
    """
    command_params = f"bot --mjolnir-config {synapse.MJOLNIR_CONFIG_PATH}"
    layer = {
        "summary": "Synapse mjolnir layer",
        "description": "Synapse mjolnir layer",
        "services": {
            synapse.MJOLNIR_SERVICE_NAME: {
                "override": "replace",
                "summary": "Mjolnir service",
                "command": f"/mjolnir-entrypoint.sh {command_params}",
                "startup": "enabled",
            },
        },
        "checks": {
            synapse.CHECK_MJOLNIR_READY_NAME: check_mjolnir_ready(),
        },
    }
    return typing.cast(ops.pebble.LayerDict, layer)


def _cron_pebble_layer(charm_state: CharmState) -> ops.pebble.LayerDict:
    """Generate pebble config for the cron service.

    Args:
        charm_state: Instance of CharmState

    Returns:
        The pebble configuration for the cron service.
    """
    layer = {
        "summary": "Synapse cron layer",
        "description": "Synapse cron layer",
        "services": {
            synapse.SYNAPSE_CRON_SERVICE_NAME: {
                "override": "replace",
                "summary": "Cron service",
                "command": "/usr/local/bin/run_cron.py",
                "environment": synapse.get_environment(charm_state),
                "startup": "enabled",
            },
        },
    }
    return typing.cast(ops.pebble.LayerDict, layer)


def _stats_exporter_pebble_layer() -> ops.pebble.LayerDict:
    """Generate pebble config for the Synapse Stats Exporter service.

    Returns:
        The pebble configuration for the Synapse Stats Exporter service.
    """
    layer = {
        "summary": "Synapse Stats Exporter layer",
        "description": "Synapse Stats Exporter",
        "services": {
            STATS_EXPORTER_SERVICE_NAME: {
                "override": "replace",
                "summary": "Synapse Stats Exporter service",
                "command": "synapse-stats-exporter",
                "startup": "disabled",
                "on-failure": "ignore",
            }
        },
    }
    return typing.cast(ops.pebble.LayerDict, layer)


def _pebble_layer_federation_sender(charm_state: CharmState) -> ops.pebble.LayerDict:
    """Return a dictionary representing a Pebble layer.

    Args:
        charm_state: Instance of CharmState

    Returns:
        pebble layer for Synapse federation sender
    """
    command = (
        f"{synapse.SYNAPSE_COMMAND_PATH} run -m synapse.app.generic_worker "
        f"--config-path {synapse.SYNAPSE_CONFIG_PATH} "
        f"--config-path {synapse.SYNAPSE_WORKER_CONFIG_PATH}"
    )

    layer = {
        "summary": "Synapse Federation Sender layer",
        "description": "pebble config layer for Synapse",
        "services": {
            "synapse-federation-sender": {
                "override": "replace",
                "summary": "Synapse Federation Sender application service",
                "startup": "enabled",
                "command": command,
                "environment": synapse.get_environment(charm_state),
            }
        },
    }
    return typing.cast(ops.pebble.LayerDict, layer)
