# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for the Synapse module using testing."""

import textwrap
from pathlib import Path
from secrets import token_hex

import pytest
from ops import pebble, testing


@pytest.fixture(scope="function", name="base_state")
def base_state_fixture(tmp_path: Path):
    """State with container and config file set."""
    config_file_path = tmp_path / "config.yaml"
    config_file_path.write_text(
        textwrap.dedent(
            """
        server_name: "test.synapse"
        listeners:
          - port: 8008
            tls: false
            type: http
            x_forwarded: true
            bind_addresses: ['::1', '127.0.0.1']
            resources:
              - names: [client, federation]
                compress: false
        signing_key_path: "/data/SERVERNAME.signing.key"
        """
        ),
        encoding="utf-8",
    )

    pebble_layer = pebble.Layer(
        {
            "summary": "Synapse layer",
            "description": "pebble config layer for synapse",
            "services": {
                "synapse": {},
            },
        }
    )
    yield {
        "leader": True,
        "config": {"server_name": "test.synapse"},
        "containers": {
            # mypy throws an error because it validates against ops.Container.
            testing.Container(  # type: ignore[call-arg]
                name="synapse",
                can_connect=True,
                execs={
                    testing.Exec(
                        command_prefix=["/start.py"],
                        return_code=0,
                    ),
                    testing.Exec(
                        command_prefix=["mkdir"],
                        return_code=0,
                    ),
                    testing.Exec(
                        command_prefix=["/usr/bin/python3"],
                        return_code=0,
                    ),
                },
                mounts={
                    "data": testing.Mount(
                        location="/data/homeserver.yaml", source=config_file_path
                    )
                },
                layers={"synapse": pebble_layer},
                service_statuses={"synapse": pebble.ServiceStatus.ACTIVE},
            )
        },
    }


@pytest.fixture(name="postgresql_relation")
def postgresql_relation_fixture():
    """Postgresql relation fixture."""
    relation_data = {
        "database": "synapse",
        "endpoints": "postgresql-k8s-primary.local:5432",
        "password": token_hex(16),
        "username": "user1",
    }
    yield testing.Relation(
        endpoint="database",
        interface="postgresql_client",
        remote_app_data=relation_data,
    )


@pytest.fixture(name="redis_relation")
def redis_relation_fixture():
    """Redis relation fixture."""
    relation_data = {
        "hostname": "redis-k8s-primary.local",
        "port": "1010",
    }
    yield testing.Relation(
        endpoint="redis",
        interface="redis",
        remote_units_data={1: relation_data},
    )


@pytest.fixture(name="peers_relation")
def peers_relation_fixture():
    """Peers relation fixture."""
    yield testing.PeerRelation(
        endpoint="synapse-peers",
        interface="synapse-instance",
    )


@pytest.fixture(name="multiple_units_base_state")
def multiple_units_base_state_fixture(
    base_state: dict, postgresql_relation, redis_relation, peers_relation
):
    """Multiple units fixture."""
    base_state["planned_units"] = 3
    base_state["leader"] = False
    base_state["relations"] = [postgresql_relation, redis_relation, peers_relation]
    yield base_state
