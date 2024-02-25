# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""The Redis agent relation observer."""

import logging

from charms.redis_k8s.v0.redis import RedisRelationCharmEvents, RedisRequires
from ops.charm import CharmBase, HookEvent
from ops.framework import Object, StoredState

logger = logging.getLogger(__name__)


class RedisObserver(Object):
    """The Redis relation observer.

    Attrs:
        on: listen to Redis events.
        _stored: stored state.
    """

    on = RedisRelationCharmEvents()
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
        self._stored.set_default(redis_relation={})
        self.redis = RedisRequires(self._charm, self._stored)
        self.framework.observe(self.on.redis_relation_updated, self._on_redis_relation_updated)

    def _on_redis_relation_updated(self, _: HookEvent) -> None:
        """Handle redis relation updated event."""
        logger.info("Redis relation changed.")
