# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""The Redis agent relation observer."""

import logging
from typing import Any, Optional

import ops
from charms.redis_k8s.v0.redis import RedisRequires
from ops.charm import CharmBase, HookEvent
from ops.framework import Object, StoredState

import synapse
from charm_types import RedisConfiguration
from pebble import PebbleServiceError

logger = logging.getLogger(__name__)


class RedisObserver(Object):
    """The Redis relation observer."""

    _stored = StoredState()

    def __init__(self, charm: CharmBase):
        """Initialize the observer and register event handlers.

        Args:
            charm: The parent charm to attach the observer to.
        """
        super().__init__(charm, "redis-observer")
        self._charm = charm
        self._stored.set_default(
            redis_relation={},
        )
        self.redis = RedisRequires(self._charm, self._stored)
        self.framework.observe(
            self._charm.on.redis_relation_updated, self._on_redis_relation_updated
        )

    def get_relation_as_redis_conf(self) -> Optional[RedisConfiguration]:
        """Get the hostname and port from the redis relation data.

        Returns:
            RedisConfiguration instance with the hostname and port of the related redis or None
            if not found.
        """
        redis_config = None
        # This is the current recommended way of accessing the relation data.
        for redis_unit in self._stored.redis_relation:  # type: ignore
            # mypy fails to see that this is indexable
            redis_unit_data = self._stored.redis_relation[redis_unit]  # type: ignore
            try:
                redis_hostname = str(redis_unit_data.get("hostname"))
                redis_port = int(redis_unit_data.get("port"))
                redis_config = RedisConfiguration(host=redis_hostname, port=redis_port)
            except (ValueError, TypeError) as exc:
                # the relation databag is empty at that point.
                logger.exception("Failed to get Redis relation data: %s", str(exc))
                return None

            logger.debug(
                "Got redis connection details from relation of %s:%s", redis_hostname, redis_port
            )
        if not redis_config:
            logger.info("Redis databag is empty.")
        return redis_config

    def _enable_redis(self) -> None:
        """Enable Redis."""
        # Other observers do this check too.
        container = self._charm.unit.get_container(
            synapse.SYNAPSE_CONTAINER_NAME
        )  # pylint: disable=duplicate-code
        if not container.can_connect() or self._pebble_service is None:
            self._charm.unit.status = ops.MaintenanceStatus("Waiting for Synapse pebble")
            return
        try:
            self._pebble_service.enable_redis(container)
        except PebbleServiceError as exc:
            self._charm.model.unit.status = ops.BlockedStatus(f"Redis integration failed: {exc}")
            return
        self._charm.unit.status = ops.ActiveStatus()

    def _on_redis_relation_updated(self, _: HookEvent) -> None:
        """Handle redis relation updated event."""
        self.model.unit.status = ops.MaintenanceStatus("Preparing the Redis integration")
        logger.debug("_on_redis_relation_updated: Enabling Redis")
        self._enable_redis()

    @property
    def _pebble_service(self) -> Any:
        """Return instance of pebble service.

        Returns:
            instance of pebble service or none.
        """
        return getattr(self._charm, "pebble_service", None)
