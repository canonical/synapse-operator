# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Synapse observability unit tests."""

# pylint: disable=protected-access

from ops.testing import Harness

import synapse


def test_main_prometheus_target(prometheus_configured: Harness) -> None:
    """
    arrange: charm deployed, integrated with Redis and set as a leader.
    act: start the Synapse charm.
    assert: Synapse charm is the main_unit so targets are 9000 (main) and 9877 (stats exporter).
    """
    harness = prometheus_configured
    harness.set_leader(True)
    harness.begin_with_initial_hooks()

    assert harness.charm._observability._metrics_endpoint._scrape_jobs == [
        {"metrics_path": "/metrics", "static_configs": [{"targets": ["*:9000", "*:9877"]}]}
    ]


def test_worker_prometheus_target(prometheus_configured: Harness) -> None:
    """
    arrange: charm deployed.
    act: start the Synapse charm, set Synapse container to be ready and set server_name.
    assert: Synapse charm is worker so target is 9101 (worker).
    """
    harness = prometheus_configured
    harness.begin()
    harness.set_leader(False)
    harness.add_relation(
        synapse.SYNAPSE_PEER_RELATION_NAME,
        harness.charm.app.name,
        app_data={"main_unit_id": "synapse/1"},
    )

    assert harness.charm._observability._metrics_endpoint._scrape_jobs == [
        {"metrics_path": "/metrics", "static_configs": [{"targets": ["*:9101"]}]}
    ]
