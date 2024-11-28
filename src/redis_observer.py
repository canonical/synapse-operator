# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

# Ignoring for the is_main call
# mypy: disable-error-code="attr-defined"

"""The Redis agent relation observer."""

import logging
from typing import Optional

import ops
from charms.redis_k8s.v0.redis import RedisRequires
from ops.framework import Object

from charm_types import RedisConfiguration
from state.mas import MASConfiguration
from state.validate import CharmBaseWithState, validate_charm_state

logger = logging.getLogger(__name__)


class RedisObserver(Object):
    """The Redis relation observer."""

    def __init__(self, charm: CharmBaseWithState):
        """Initialize the observer and register event handlers.

        Args:
            charm: The parent charm to attach the observer to.
        """
        super().__init__(charm, "redis-observer")
        self._charm = charm
        self.redis = RedisRequires(self._charm)
        self.framework.observe(
            self._charm.on.redis_relation_updated, self._on_redis_relation_updated
        )

    def get_charm(self) -> CharmBaseWithState:
        """Return the current charm.

        Returns:
           The current charm
        """
        return self._charm

    def get_relation_as_redis_conf(self) -> Optional[RedisConfiguration]:
        """Get the hostname and port from the redis relation data.

        Returns:
            RedisConfiguration instance with the hostname and port of the related redis or None
            if not found.
        """
        redis_config = None
        try:
            if self.redis.relation_data:
                redis_hostname = str(self.redis.relation_data.get("hostname"))
                redis_port = int(self.redis.relation_data.get("port"))
                logger.debug(
                    "Got redis connection details from relation %s:%s", redis_hostname, redis_port
                )
                redis_config = RedisConfiguration(host=redis_hostname, port=redis_port)
        except (ValueError, TypeError) as exc:
            # the relation databag is empty at that point.
            logger.exception("Failed to get Redis relation data: %s", str(exc))
            return None

        if not redis_config:
            logger.info("Redis databag is empty.")
        return redis_config

    @validate_charm_state
    def _on_redis_relation_updated(self, _: ops.EventBase) -> None:
        """Handle redis relation updated event."""
        charm = self.get_charm()
        charm_state = charm.build_charm_state()
        MASConfiguration.validate(charm)

        self.model.unit.status = ops.MaintenanceStatus("Preparing the Redis integration")
        logger.debug("_on_redis_relation_updated emitting reconcile")
        charm.reconcile(charm_state)
