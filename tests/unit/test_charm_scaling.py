# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Synapse charm scaling unit tests."""

import ops
from ops.testing import Harness

import synapse


def test_scaling_redis_required(harness: Harness) -> None:
    """
    arrange: charm deployed.
    act: scale charm to more than 1 unit.
    assert: Synapse charm is in BlockedStatus due lacking of Redis integration.
    """
    harness.begin()
    harness.set_leader(True)

    rel_id = harness.add_relation(synapse.SYNAPSE_PEER_RELATION_NAME, harness.charm.app.name)
    harness.add_relation_unit(rel_id, "synapse/1")

    assert isinstance(harness.model.unit.status, ops.BlockedStatus)

    harness.remove_relation_unit(rel_id, "synapse/1")
    assert isinstance(harness.model.unit.status, ops.ActiveStatus)


def test_scaling_redis_not_required(harness: Harness) -> None:
    """
    arrange: charm deployed and scaled to more than 1 unit.
    act: scale down.
    assert: Synapse charm is in ActiveStatus.
    """
    harness.begin()
    harness.set_leader(True)
    rel_id = harness.add_relation(synapse.SYNAPSE_PEER_RELATION_NAME, harness.charm.app.name)
    harness.add_relation_unit(rel_id, "synapse/1")
    assert isinstance(harness.model.unit.status, ops.BlockedStatus)

    harness.remove_relation_unit(rel_id, "synapse/1")

    assert isinstance(harness.model.unit.status, ops.ActiveStatus)
