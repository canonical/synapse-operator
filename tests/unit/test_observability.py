# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Synapse observability unit tests."""

# pylint: disable=protected-access

from ops.testing import Harness

import synapse


def test_prometheus_target(prometheus_configured: Harness) -> None:
    """
    arrange: charm deployed, integrated with Redis and set as a leader.
    act: start the Synapse charm.
    assert: Synapse charm has Prometheus targets 9000 (Synapse) and 9877 (Stats exporter).
    """
    harness = prometheus_configured
    harness.set_leader(True)
    harness.begin_with_initial_hooks()

    assert harness.charm._observability._metrics_endpoint._scrape_jobs == [
        {
            "metrics_path": "/metrics",
            "static_configs": [
                {
                    "targets": [
                        f"*:{synapse.SYNAPSE_EXPORTER_PORT}",
                        f"*:{synapse.STATS_EXPORTER_PORT}",
                    ]
                }
            ],
        }
    ]
