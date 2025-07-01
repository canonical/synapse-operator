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
        """
        ),
        encoding="utf-8",
    )
    pebble_layer = pebble.Layer(
        {
            "summary": "Synapse layer",
            "description": "pebble config layer for maubot",
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
        "database": "maubot",
        "endpoints": "postgresql-k8s-primary.local:5432",
        "password": token_hex(16),
        "username": "user1",
    }
    yield testing.Relation(
        endpoint="postgresql",
        interface="postgresql_client",
        remote_app_data=relation_data,
    )
