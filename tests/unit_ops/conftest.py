# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Synapse charm fixtures."""

import textwrap
from pathlib import Path
from secrets import token_hex

import pytest
from ops import pebble, testing

TEST_SERVER_NAME = "server-name-configured.synapse.com"


@pytest.fixture(scope="function", name="base_state")
def base_state_fixture(tmp_path: Path, postgresql_relation, synapse_config):
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
        "config": synapse_config,
        "relations": [postgresql_relation],
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
        "database": "synapse-mas",
        "endpoints": "postgresql-k8s-primary.local:5432",
        "password": token_hex(16),
        "username": "user1",
    }
    yield testing.Relation(
        endpoint="mas-database",
        interface="postgresql_client",
        remote_app_data=relation_data,
    )


@pytest.fixture(name="s3_backup_relation")
def s3_backup_relation_fixture(s3_relation_data):
    """S3 backup relation fixture."""
    yield testing.Relation(
        endpoint="media",
        interface="s3",
        remote_app_data=s3_relation_data,
    )


@pytest.fixture(name="s3_media_relation")
def s3_media_relation_fixture(s3_relation_data):
    """S3 media relation fixture."""
    yield testing.Relation(
        endpoint="backup",
        interface="s3",
        remote_app_data=s3_relation_data,
    )


@pytest.fixture(name="s3_relation_data")
def s3_relation_data_fixture():
    yield {
        "bucket": "bucket2",
        "region": "region2",
        "endpoint": "endpoint2",
        "access-key": "access_key2",
        "secret-key": token_hex(16),
        "path": "media",
    }


@pytest.fixture(name="synapse_container")
def synapse_container_fixture():
    """Synapse container fixture."""
    yield testing.Container("synapse", can_connect=True)  # type: ignore[call-arg]


@pytest.fixture(name="matrix_auth_secret")
def matrix_auth_secret_fixture(matrix_auth_secret_id):
    """Matrix Auth secret fixture."""
    moderation_token = "stt_YW1hbmAbcGxh_VQlRZRAGRlxACTqCrJxl_0Wcabc"  # nosec
    yield testing.Secret(
        id=matrix_auth_secret_id, tracked_content={"matrix-access-token": moderation_token}
    )


@pytest.fixture(name="synapse_config")
def synapse_config_fixture(matrix_auth_secret_id):
    yield {
        "server_name": TEST_SERVER_NAME,
        "moderation_access_token_secret_id": matrix_auth_secret_id,
    }


@pytest.fixture(name="matrix_auth_secret_id")
def matrix_auth_secret_id_fixture():
    yield token_hex(16)


@pytest.fixture(name="mas_context_secret")
def mas_context_secret_fixture():
    """MAS context secret fixture."""
    mas_context_content = {
        "encryption-key": token_hex(32),  # 64 characters (32 bytes hex)
        "signing-key-id": token_hex(4),  # 8 characters (4 bytes hex)
        "signing-key-rsa": "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC0test\n-----END PRIVATE KEY-----",
        "synapse-shared-secret": token_hex(16),  # 32 characters (16 bytes hex)
        "synapse-oidc-client-id": "01HJ7TQTEST000000000000000",
        "synapse-oidc-client-secret": token_hex(16),  # 32 characters (16 bytes hex)
        "upstream-oidc-provider-id": "01HJ7TQTEST000000000000001",
    }
    yield testing.Secret(
        label="mas.context",
        tracked_content=mas_context_content,
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
    base_state: dict, postgresql_relation, redis_relation, peers_relation, mas_context_secret
):
    """Multiple units fixture."""
    base_state["planned_units"] = 3
    base_state["leader"] = False
    base_state["relations"] = [postgresql_relation, redis_relation, peers_relation]
    base_state["secrets"] = [mas_context_secret]
    yield base_state
