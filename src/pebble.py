#!/usr/bin/env python3

# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Class to interact with pebble."""

import logging
import typing

import ops
import yaml
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


def check_synapse_ready() -> ops.pebble.CheckDict:
    """Return the Synapse container ready check.

    Returns:
        Dict: check object converted to its dict representation.
    """
    check = Check(synapse.CHECK_READY_NAME)
    check.override = "replace"
    check.level = "ready"
    check.http = {"url": f"{synapse.SYNAPSE_URL}/health"}
    return check.to_dict()


def check_synapse_alive() -> ops.pebble.CheckDict:
    """Return the Synapse container alive check.

    Returns:
        Dict: check object converted to its dict representation.
    """
    check = Check(synapse.CHECK_ALIVE_NAME)
    check.override = "replace"
    check.level = "alive"
    check.tcp = {"port": synapse.SYNAPSE_PORT}
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
    return check.to_dict()


def check_irc_bridge_ready() -> ops.pebble.CheckDict:
    """Return the Synapse IRC bridge service check.

    Returns:
        Dict: check object converted to its dict representation.
    """
    check = Check(synapse.CHECK_IRC_BRIDGE_READY_NAME)
    check.override = "replace"
    check.level = "ready"
    check.http = {"url": f"http://localhost:{synapse.IRC_BRIDGE_HEALTH_PORT}"}
    return check.to_dict()


def replan_nginx(container: ops.model.Container, main_unit_address: str) -> None:
    """Replan Synapse NGINX service and regenerate configuration.

    Args:
        container: Charm container.
        main_unit_address: Main unit address to be used in configuration.
    """
    container.add_layer("synapse-nginx", _nginx_pebble_layer(), combine=True)
    synapse.generate_nginx_config(container=container, main_unit_address=main_unit_address)
    container.replan()


def replan_mjolnir(container: ops.model.Container) -> None:
    """Replan Synapse Mjolnir service.

    Args:
        container: Charm container.
    """
    container.add_layer("synapse-mjolnir", _mjolnir_pebble_layer(), combine=True)
    container.replan()


def replan_irc_bridge(container: ops.model.Container) -> None:
    """Replan Synapse IRC bridge service.

    Args:
        container: Charm container.
    """
    container.add_layer("synapse-irc", _irc_bridge_pebble_layer(), combine=True)
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


def _push_synapse_config(container: ops.model.Container, current_synapse_config: dict) -> None:
    """Push the Synapse configuration to the container.

    Args:
        container: Synapse container.
        current_synapse_config: Synapse configuration.

    Raises:
        PebbleServiceError: if something goes wrong while interacting with Pebble.
    """
    try:
        container.push(
            synapse.SYNAPSE_CONFIG_PATH, yaml.dump(current_synapse_config).encode("utf-8")
        )
    except ops.pebble.PathError as exc:
        raise PebbleServiceError(str(exc)) from exc


# The complexity of this method will be reviewed.
def change_config(  # noqa: C901
    charm_state: CharmState,
    container: ops.model.Container,
    is_main: bool = True,
    unit_number: str = "",
) -> None:
    """Change the configuration (main and worker).

    Args:
        charm_state: Instance of CharmState
        container: Charm container.
        is_main: if unit is main.
        unit_number: unit number id to set the worker name.

    Raises:
        PebbleServiceError: if something goes wrong while interacting with Pebble.
    """
    try:
        synapse.execute_migrate_config(container=container, charm_state=charm_state)
        current_synapse_config = _get_synapse_config(container)
        synapse.enable_metrics(current_synapse_config)
        synapse.enable_forgotten_room_retention(current_synapse_config)
        synapse.enable_serve_server_wellknown(current_synapse_config)
        if charm_state.instance_map_config is not None:
            logger.debug("pebble.change_config: Enabling instance_map")
            synapse.enable_instance_map(current_synapse_config, charm_state=charm_state)
            logger.debug("pebble.change_config: Enabling stream_writers")
            synapse.enable_stream_writers(current_synapse_config, charm_state=charm_state)
        if charm_state.saml_config is not None:
            logger.debug("pebble.change_config: Enabling SAML")
            synapse.enable_saml(current_synapse_config, charm_state=charm_state)
        if charm_state.smtp_config is not None:
            logger.debug("pebble.change_config: Enabling SMTP")
            synapse.enable_smtp(current_synapse_config, charm_state=charm_state)
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
        if charm_state.datasource:
            logger.info("Synapse Stats Exporter enabled.")
            replan_stats_exporter(container=container, charm_state=charm_state)
        with open("templates/worker.yaml", encoding="utf-8") as worker_config_file:
            config = yaml.safe_load(worker_config_file)
            config["worker_name"] = f"worker{unit_number}"
            container.push(synapse.SYNAPSE_WORKER_CONFIG_PATH, yaml.safe_dump(config))
        _push_synapse_config(container, current_synapse_config)
        synapse.validate_config(container=container)
        restart_synapse(container=container, charm_state=charm_state, is_main=is_main)
    except (synapse.WorkloadError, ops.pebble.PathError) as exc:
        raise PebbleServiceError(str(exc)) from exc


def enable_redis(charm_state: CharmState, container: ops.model.Container) -> None:
    """Enable Redis while receiving on_redis_relation_updated event.

    Args:
        container: Charm container.
        charm_state: Instance of CharmState.

    Raises:
        PebbleServiceError: if something goes wrong while interacting with Pebble.
    """
    try:
        logger.debug("pebble.enable_redis: Enabling Redis")
        current_yaml = _get_synapse_config(container)
        synapse.enable_redis(current_yaml, charm_state=charm_state)
        _push_synapse_config(container, current_yaml)
        restart_synapse(container=container, charm_state=charm_state)
    except (synapse.WorkloadError, ops.pebble.PathError) as exc:
        raise PebbleServiceError(str(exc)) from exc


def enable_saml(charm_state: CharmState, container: ops.model.Container) -> None:
    """Enable SAML while receiving on_saml_data_available event.

    Args:
        charm_state: Instance of CharmState
        container: Charm container.

    Raises:
        PebbleServiceError: if something goes wrong while interacting with Pebble.
    """
    try:
        logger.debug("pebble.enable_saml: Enabling SAML")
        current_yaml = _get_synapse_config(container)
        synapse.enable_saml(current_yaml, charm_state=charm_state)
        _push_synapse_config(container, current_yaml)
        restart_synapse(container=container, charm_state=charm_state)
    except (synapse.WorkloadError, ops.pebble.PathError) as exc:
        raise PebbleServiceError(str(exc)) from exc


def enable_smtp(charm_state: CharmState, container: ops.model.Container) -> None:
    """Enable SMTP while receiving on_smtp_data_available event.

    Args:
        charm_state: Instance of CharmState
        container: Charm container.

    Raises:
        PebbleServiceError: if something goes wrong while interacting with Pebble.
    """
    try:
        logger.debug("pebble.enable_smtp: Enabling SMTP")
        current_yaml = _get_synapse_config(container)
        synapse.enable_smtp(current_yaml, charm_state=charm_state)
        _push_synapse_config(container, current_yaml)
        restart_synapse(container=container, charm_state=charm_state)
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
            synapse.CHECK_READY_NAME: check_synapse_ready(),
            synapse.CHECK_ALIVE_NAME: check_synapse_alive(),
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


def _irc_bridge_pebble_layer() -> ops.pebble.LayerDict:
    """Generate pebble config for the irc bridge service.

    Returns:
        The pebble configuration for the irc bridge service.
    """
    command_params = (
        f"-c {synapse.IRC_BRIDGE_CONFIG_PATH}"
        f" -f {synapse.IRC_BRIDGE_REGISTRATION_PATH}"
        f" -p {synapse.IRC_BRIDGE_HEALTH_PORT}"
    )
    layer = {
        "summary": "Synapse irc layer",
        "description": "Synapse irc layer",
        "services": {
            synapse.IRC_BRIDGE_SERVICE_NAME: {
                "override": "replace",
                "summary": "IRC service",
                "command": f"/bin/node /app/app.js {command_params}",
                "startup": "enabled",
            },
        },
        "checks": {
            synapse.CHECK_IRC_BRIDGE_READY_NAME: check_irc_bridge_ready(),
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
