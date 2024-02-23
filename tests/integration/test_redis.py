#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for Synapse charm integrated with Redis."""
import logging
import typing

import pytest
from juju.application import Application
from juju.model import Model
from ops.model import ActiveStatus

# caused by pytest fixtures
# pylint: disable=too-many-arguments

# mypy has trouble to inferred types for variables that are initialized in subclasses.
ACTIVE_STATUS_NAME = typing.cast(str, ActiveStatus.name)  # type: ignore

logger = logging.getLogger(__name__)


@pytest.mark.redis
async def test_synapse_enable_redis(
    model: Model,
    synapse_app: Application,
    relation_name: str,
):
    """
    arrange: build and deploy the Synapse charm.
    act:  integrate with Redis.
    assert: the Synapse application is active.
    """
    redis_app = await model.deploy(
        "redis-k8s",
        channel="latest/edge",
    )
    await model.wait_for_idle(status=ACTIVE_STATUS_NAME)
    await model.add_relation(f"{redis_app.name}:{relation_name}", synapse_app.name)
    await model.wait_for_idle(
        idle_period=30,
        apps=[synapse_app.name, redis_app.name],
        status=ACTIVE_STATUS_NAME,
    )
