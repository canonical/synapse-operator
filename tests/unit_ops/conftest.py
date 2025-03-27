# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Synapse charm fixtures."""

import pytest
from ops import testing

TEST_SERVER_NAME = "server-name-configured.synapse.com"


@pytest.fixture(name="postgresql_relation")
def postgresql_relation_fixture():
    """Postgresql relation fixture."""
    database_data = {
        "database": "synapse-mas",
        "endpoints": "postgresql-k8s-primary.local:5432",
        "password": "123",
        "username": "user1",
    }
    yield testing.Relation(
        id=1,
        endpoint="mas-database",
        interface="postgresql_client",
        remote_app_data=database_data,
    )


@pytest.fixture(name="synapse_container")
def synapse_container_fixture():
    """Synapse container fixture."""
    yield testing.Container("synapse", can_connect=True)  # type: ignore[call-arg]


@pytest.fixture(name="matrix_auth_secret")
def matrix_auth_secret_fixture():
    """Matrix Auth secret fixture."""
    moderation_token = "stt_YW1hbmAbcGxh_VQlRZRAGRlxACTqCrJxl_0Wcabc"  # nosec
    yield testing.Secret(id="123", tracked_content={"matrix-access-token": moderation_token})


@pytest.fixture(name="synapse_config")
def synapse_config_fixture():
    yield {"server_name": TEST_SERVER_NAME, "moderation_access_token_secret_id": "123"}


@pytest.fixture(name="base_state")
def base_state_fixture(synapse_config, synapse_container, postgresql_relation):
    input_state = {
        "leader": True,
        "config": synapse_config,
        "containers": {synapse_container},
        "relations": [postgresql_relation],
    }
    yield input_state
