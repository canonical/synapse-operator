#!/usr/bin/env python3

# Copyright 2023 Canonical Ltd.
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


class PebbleService:
    """The charm pebble service manager."""

    def __init__(self, charm_state: CharmState):
        """Initialize the pebble service.

        Args:
            charm_state: Instance of CharmState.
        """
        self._charm_state = charm_state

    def restart_synapse(self, container: ops.model.Container) -> None:
        """Restart Synapse service.

        This will force a restart even if its plan hasn't changed.

        Args:
            container: Synapse container.
        """
        logger.debug("Restarting the Synapse container")
        container.add_layer(synapse.SYNAPSE_CONTAINER_NAME, self._pebble_layer, combine=True)
        container.restart(synapse.SYNAPSE_SERVICE_NAME)

    def replan_nginx(self, container: ops.model.Container) -> None:
        """Replan Synapse NGINX service.

        Args:
            container: Charm container.
        """
        container.add_layer("synapse-nginx", self._nginx_pebble_layer, combine=True)
        container.replan()

    def replan_mjolnir(self, container: ops.model.Container) -> None:
        """Replan Synapse Mjolnir service.

        Args:
            container: Charm container.
        """
        container.add_layer("synapse-mjolnir", self._mjolnir_pebble_layer, combine=True)
        container.replan()

    def change_config(self, container: ops.model.Container) -> None:
        """Change the configuration.

        Args:
            container: Charm container.

        Raises:
            PebbleServiceError: if something goes wrong while interacting with Pebble.
        """
        try:
            synapse.execute_migrate_config(container=container, charm_state=self._charm_state)
            synapse.enable_metrics(container=container)
            synapse.enable_serve_server_wellknown(container=container)
            if self._charm_state.saml_config is not None:
                logger.debug("pebble.change_config: Enabling SAML")
                synapse.enable_saml(container=container, charm_state=self._charm_state)
            if self._charm_state.synapse_config.smtp_host:
                synapse.enable_smtp(container=container, charm_state=self._charm_state)
            if not self._charm_state.synapse_config.enable_password_config:
                synapse.disable_password_config(container=container)
            if self._charm_state.synapse_config.federation_domain_whitelist:
                synapse.enable_federation_domain_whitelist(
                    container=container, charm_state=self._charm_state
                )
            self.restart_synapse(container)
        except (synapse.WorkloadError, ops.pebble.PathError) as exc:
            raise PebbleServiceError(str(exc)) from exc

    def enable_saml(self, container: ops.model.Container) -> None:
        """Enable SAML while receiving on_saml_data_available event.

        Args:
            container: Charm container.

        Raises:
            PebbleServiceError: if something goes wrong while interacting with Pebble.
        """
        try:
            logger.debug("pebble.enable_saml: Enabling SAML")
            synapse.enable_saml(container=container, charm_state=self._charm_state)
            self.restart_synapse(container)
        except (synapse.WorkloadError, ops.pebble.PathError) as exc:
            raise PebbleServiceError(str(exc)) from exc

    def reset_instance(self, container: ops.model.Container) -> None:
        """Reset instance.

        Args:
            container: Charm container.

        Raises:
            PebbleServiceError: if something goes wrong while interacting with Pebble.
        """
        # This is needed in the case of relation with Postgresql.
        # If there is open connections it won't be possible to drop the database.
        try:
            logger.info("Replan service to not restart")
            container.add_layer(
                synapse.SYNAPSE_CONTAINER_NAME, self._pebble_layer_without_restart, combine=True
            )
            container.replan()
            logger.info("Stop Synapse instance")
            container.stop(synapse.SYNAPSE_SERVICE_NAME)
            logger.info("Erase Synapse data")
            synapse.reset_instance(container)
        except ops.pebble.PathError as exc:
            raise PebbleServiceError(str(exc)) from exc

    @property
    def _pebble_layer(self) -> ops.pebble.LayerDict:
        """Return a dictionary representing a Pebble layer."""
        layer = {
            "summary": "Synapse layer",
            "description": "pebble config layer for Synapse",
            "services": {
                synapse.SYNAPSE_SERVICE_NAME: {
                    "override": "replace",
                    "summary": "Synapse application service",
                    "startup": "enabled",
                    "command": synapse.SYNAPSE_COMMAND_PATH,
                    "environment": synapse.get_environment(self._charm_state),
                }
            },
            "checks": {
                synapse.CHECK_READY_NAME: synapse.check_ready(),
                synapse.CHECK_ALIVE_NAME: synapse.check_alive(),
            },
        }
        return typing.cast(ops.pebble.LayerDict, layer)

    @property
    def _pebble_layer_without_restart(self) -> ops.pebble.LayerDict:
        """Return a dictionary representing a Pebble layer without restart."""
        new_layer = self._pebble_layer
        new_layer["services"][synapse.SYNAPSE_SERVICE_NAME]["on-success"] = "ignore"
        new_layer["services"][synapse.SYNAPSE_SERVICE_NAME]["on-failure"] = "ignore"
        ignore = {synapse.CHECK_READY_NAME: "ignore"}
        new_layer["services"][synapse.SYNAPSE_SERVICE_NAME]["on-check-failure"] = ignore
        return new_layer

    @property
    def _nginx_pebble_layer(self) -> ops.pebble.LayerDict:
        """Generate pebble config for the synapse-nginx container.

        Returns:
            The pebble configuration for the NGINX container.
        """
        layer = {
            "summary": "Synapse nginx layer",
            "description": "Synapse nginx layer",
            "services": {
                "synapse-nginx": {
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

    @property
    def _mjolnir_pebble_layer(self) -> ops.pebble.LayerDict:
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
