#!/usr/bin/env python3

# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charm for Synapse on kubernetes."""

import itertools
import logging
import typing

import ops
from charms.data_platform_libs.v0.data_interfaces import DatabaseRequires
from ops.main import main

# pydantic is causing this no-name-in-module problem
from pydantic import ValidationError  # pylint: disable=no-name-in-module,import-error

from config import KNOWN_CHARM_CONFIG, ConfigInvalidError, SynapseConfig
from containers import synapse
from database_client import DatabaseClient
from integrations import database

logger = logging.getLogger(__name__)

SYNAPSE_CONTAINER_NAME = "synapse"


class SynapseCharm(ops.CharmBase):
    """Charm the service."""

    def __init__(self, *args: typing.Any) -> None:
        """Construct.

        Args:
            args: class arguments.
        """
        super().__init__(*args)
        self.database = DatabaseRequires(
            self,
            relation_name=database.RELATION_NAME,
            database_name=database.DATABASE_NAME,
            extra_user_roles="SUPERUSER",
        )
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.synapse_pebble_ready, self._on_pebble_ready)
        self.framework.observe(self.database.on.database_created, self._on_database_created)
        self.framework.observe(self.database.on.endpoints_changed, self._on_endpoints_changed)

    def get_charm_configuration(self) -> SynapseConfig:
        """Get charm configuration.

        Raises:
            ConfigInvalidError: if configuration is invalid.

        Returns:
            SynapseConfig: Charm configuration.
        """
        synapse_config = {k: v for k, v in self.config.items() if k in KNOWN_CHARM_CONFIG}
        try:
            synapse_config = SynapseConfig(**synapse_config)  # type: ignore
        except ValidationError as exc:
            error_fields = set(
                itertools.chain.from_iterable(error["loc"] for error in exc.errors())
            )
            error_field_str = " ".join(f"{f}" for f in error_fields)
            raise ConfigInvalidError(f"invalid configuration: {error_field_str}") from exc
        # ignoring because mypy fails with:
        # "has incompatible type "**dict[str, str]"; expected ...""
        return synapse_config  # type: ignore

    def reconcile(self) -> None:
        """Change configuration.

        Raises:
            PebbleError: if something goes wrong while interacting with Pebble.
        """
        # Get configuration from the charm
        try:
            synapse_config = self.get_charm_configuration()
        except ConfigInvalidError as exc:
            self.model.unit.status = ops.BlockedStatus(exc.msg)
            return
        self.model.unit.status = ops.MaintenanceStatus("Configuring Synapse")
        # Get configuration from integrations
        database_config = database.get_configuration(self.model, self.database)
        # Generate environment variables
        env = synapse.synapse_environment(
            synapse_config=synapse_config, database_config=database_config
        )
        try:
            container = self.unit.get_container(SYNAPSE_CONTAINER_NAME)
            synapse.execute_migrate_config(container, env)
            container.add_layer(
                synapse.SYNAPSE_SERVICE_NAME, synapse.pebble_layer(env), combine=True
            )
            container.restart(synapse.SYNAPSE_SERVICE_NAME)
        except (ops.pebble.ConnectionError, synapse.ContainerError) as exc:
            # implement retry
            logger.exception(str(exc))
            raise
        self.model.unit.status = ops.ActiveStatus()

    def _on_config_changed(self, _: ops.HookEvent) -> None:
        """Handle changed configuration."""
        self.reconcile()

    def _on_pebble_ready(self, _: ops.HookEvent) -> None:
        """Handle pebble ready event."""
        self.reconcile()

    def _on_database_created(self, _: ops.HookEvent) -> None:
        """Handle database created."""
        database_config = database.get_configuration(self.model, self.database)
        if database_config is None:
            logger.error("database created event received but there is no integration data")
            return
        # this is needed due Synapse requires specific database collation
        db_client = DatabaseClient(database_config=database_config)
        db_client.prepare()
        self.reconcile()

    def _on_endpoints_changed(self, _: ops.HookEvent) -> None:
        """Handle database endpoints changed."""
        self.reconcile()


if __name__ == "__main__":  # pragma: nocover
    main(SynapseCharm)
