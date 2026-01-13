# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration test charm dependencies.

This module defines the charm dependencies used in integration tests.
When these values are updated, integration tests should be run to verify
compatibility. This file is monitored by Renovate for automated updates.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class CharmDependency:
    """Represents a charm dependency with its deployment configuration.

    Attributes:
        charm_name: The name of the charm to deploy
        channel: The channel to deploy from (e.g., "latest/stable")
        revision: Optional specific revision number to deploy
        trust: Whether to deploy with the --trust flag
    """

    charm_name: str
    channel: str
    revision: Optional[int] = None
    trust: bool = False


# Integration test charm dependencies
# These are the charms that integrate with Synapse and should be tested
# for compatibility
NGINX_INGRESS_INTEGRATOR = CharmDependency(
    charm_name="nginx-ingress-integrator",
    channel="latest/edge",
    revision=253,
    trust=True,
)

# Use juju-info to know specific revision and architecture
# https://canonical-charmed-postgresql-k8s.readthedocs-hosted.com/14/reference/releases/
POSTGRESQL_K8S = CharmDependency(
    charm_name="postgresql-k8s",
    channel="14/stable",
    revision=495,
    trust=True,
)

S3_INTEGRATOR = CharmDependency(
    charm_name="s3-integrator",
    channel="1/edge",
    revision=255,
)

REDIS = CharmDependency(
    charm_name="redis-k8s",
    channel="latest/edge",
    revision=42,
)

OAUTH_EXTERNAL_IDP_INTEGRATOR = CharmDependency(
    charm_name="oauth-external-idp-integrator",
    channel="latest/edge",
    revision=6,
)

# Collection of all integration dependencies for easy iteration
INTEGRATION_DEPENDENCIES = {
    "nginx-ingress-integrator": NGINX_INGRESS_INTEGRATOR,
    "postgresql-k8s": POSTGRESQL_K8S,
    "s3-integrator": S3_INTEGRATOR,
    "redis": REDIS,
    "oauth-external-idp-integrator": OAUTH_EXTERNAL_IDP_INTEGRATOR,
}
