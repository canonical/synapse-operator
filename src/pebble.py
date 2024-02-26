#!/usr/bin/env python3

# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Class to interact with pebble."""

import logging
import typing

import ops

import synapse
from charm_state import CharmState

logger = logging.getLogger(__name__)


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


def restart_synapse(charm_state: CharmState, container: ops.model.Container) -> None:
    """Restart Synapse service.

    This will force a restart even if its plan hasn't changed.

    Args:
        charm_state: Instance of CharmState
        container: Synapse container.
    """
    logger.debug("Restarting the Synapse container")
    container.add_layer(synapse.SYNAPSE_SERVICE_NAME, _pebble_layer(charm_state), combine=True)
    container.add_layer(
        synapse.SYNAPSE_CRON_SERVICE_NAME, _cron_pebble_layer(charm_state), combine=True
    )
    container.restart(synapse.SYNAPSE_SERVICE_NAME)


def replan_nginx(container: ops.model.Container) -> None:
    """Replan Synapse NGINX service.

    Args:
        container: Charm container.
    """
    container.add_layer("synapse-nginx", _nginx_pebble_layer(), combine=True)
    container.replan()


def replan_mjolnir(container: ops.model.Container) -> None:
    """Replan Synapse Mjolnir service.

    Args:
        container: Charm container.
    """
    container.add_layer("synapse-mjolnir", _mjolnir_pebble_layer(), combine=True)
    container.replan()


# The complexity of this method will be reviewed.
def change_config(charm_state: CharmState, container: ops.model.Container) -> None:  # noqa: C901
    """Change the configuration.

    Args:
        charm_state: Instance of CharmState
        container: Charm container.

    Raises:
        PebbleServiceError: if something goes wrong while interacting with Pebble.
    """
    try:
        synapse.execute_migrate_config(container=container, charm_state=charm_state)
        synapse.enable_metrics(container=container)
        synapse.enable_forgotten_room_retention(container=container)
        synapse.enable_serve_server_wellknown(container=container)
        if charm_state.saml_config is not None:
            logger.debug("pebble.change_config: Enabling SAML")
            synapse.enable_saml(container=container, charm_state=charm_state)
        if charm_state.smtp_config is not None:
            logger.debug("pebble.change_config: Enabling SMTP")
            synapse.enable_smtp(container=container, charm_state=charm_state)
        if not charm_state.synapse_config.enable_password_config:
            synapse.disable_password_config(container=container)
        if charm_state.synapse_config.federation_domain_whitelist:
            synapse.enable_federation_domain_whitelist(
                container=container, charm_state=charm_state
            )
        if charm_state.synapse_config.allow_public_rooms_over_federation:
            synapse.enable_allow_public_rooms_over_federation(container=container)
        if not charm_state.synapse_config.enable_room_list_search:
            synapse.disable_room_list_search(container=container)
        if charm_state.synapse_config.trusted_key_servers:
            synapse.enable_trusted_key_servers(container=container, charm_state=charm_state)
        if charm_state.synapse_config.ip_range_whitelist:
            synapse.enable_ip_range_whitelist(container=container, charm_state=charm_state)
        synapse.validate_config(container=container)
        restart_synapse(container=container, charm_state=charm_state)
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
        synapse.enable_redis(container=container, charm_state=charm_state)
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
        synapse.enable_saml(container=container, charm_state=charm_state)
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
        synapse.enable_smtp(container=container, charm_state=charm_state)
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


def _pebble_layer(charm_state: CharmState) -> ops.pebble.LayerDict:
    """Return a dictionary representing a Pebble layer.

    Args:
        charm_state: Instance of CharmState

    Returns:
        pebble layer for Synapse
    """
    layer = {
        "summary": "Synapse layer",
        "description": "pebble config layer for Synapse",
        "services": {
            synapse.SYNAPSE_SERVICE_NAME: {
                "override": "replace",
                "summary": "Synapse application service",
                "startup": "enabled",
                "command": synapse.SYNAPSE_COMMAND_PATH,
                "environment": synapse.get_environment(charm_state),
            }
        },
        "checks": {
            synapse.CHECK_READY_NAME: synapse.check_ready(),
            synapse.CHECK_ALIVE_NAME: synapse.check_alive(),
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
            synapse.CHECK_NGINX_READY_NAME: synapse.check_nginx_ready(),
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
            synapse.CHECK_MJOLNIR_READY_NAME: synapse.check_mjolnir_ready(),
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
