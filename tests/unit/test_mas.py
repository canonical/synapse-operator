# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Synapse MAS charm unit tests."""

from unittest.mock import MagicMock, patch

import pytest
import yaml
from ops.model import SecretNotFoundError
from ops.testing import Harness

from auth.mas import (
    generate_mas_config,
    generate_oauth_client_config,
    generate_synapse_msc3861_config,
)
from charm import SynapseCharm
from charm_state import SynapseConfig
from state.mas import (
    MAS_DATABASE_INTEGRATION_NAME,
    MAS_DATABASE_NAME,
    MASConfiguration,
    MASContextNotSetError,
    MASDatasourceMissingError,
)


def test_mas_generate_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    arrange: Given a synapse charm related to postgresql and MAS enabled.
    act: Generate the mas charm state and the mas configuration.
    assert: The mas config is correctly generated with the expected values.
    """
    monkeypatch.setattr("ops.model.Model.get_secret", MagicMock(side_effect=SecretNotFoundError))
    monkeypatch.setattr("ops.model.Application.add_secret", MagicMock())

    harness = Harness(SynapseCharm)
    harness.update_config({"enable_mas": True})
    postgresql_relation_data = {
        "endpoints": "myhost:5432",
        "username": "user",
        "password": "password",
    }
    harness.add_relation(MAS_DATABASE_INTEGRATION_NAME, "db", app_data=postgresql_relation_data)
    harness.set_leader(True)
    harness.begin()

    mas_configuration = MASConfiguration.from_charm(harness.charm)
    config = {
        "server_name": "foo",
        "public_baseurl": "https://foo",
        "enable_password_config": True,
    }
    synapse_configuration = SynapseConfig(**config)  # type: ignore[arg-type]
    rendered_mas_config = generate_mas_config(
        mas_configuration, synapse_configuration, None, None, "10.1.1.0"
    )
    rendered_msc3861_config = generate_synapse_msc3861_config(
        mas_configuration, synapse_configuration
    )
    parsed_mas_config = yaml.safe_load(rendered_mas_config)
    assert (
        parsed_mas_config["http"]["public_base"]
        == f"{config['public_baseurl']}{mas_configuration.mas_prefix}"
    )

    db_user = postgresql_relation_data["username"]
    db_password = postgresql_relation_data["password"]
    db_endpoint = postgresql_relation_data["endpoints"]
    assert (
        parsed_mas_config["database"]["uri"]
        == f"postgresql://{db_user}:{db_password}@{db_endpoint}/{MAS_DATABASE_NAME}"
    )

    assert (
        rendered_msc3861_config["issuer"]
        == f"{synapse_configuration.public_baseurl}{mas_configuration.mas_prefix}"
    )

    oauth_client_config = generate_oauth_client_config(mas_configuration, synapse_configuration)
    assert oauth_client_config.redirect_uri == (
        f"{synapse_configuration.public_baseurl}"
        f"/auth/upstream/callback/{mas_configuration.mas_context.upstream_oidc_provider_id}"
    )


def test_mas_configuration_from_charm_success() -> None:
    """
    arrange: Given a synapse charm with MAS database relation and MAS enabled.
    act: Create MAS configuration from charm.
    assert: MAS configuration is successfully created.
    """
    harness = Harness(SynapseCharm)
    harness.update_config({"enable_mas": True})
    postgresql_relation_data = {
        "endpoints": "myhost:5432",
        "username": "user",
        "password": "password",
    }
    harness.add_relation(MAS_DATABASE_INTEGRATION_NAME, "db", app_data=postgresql_relation_data)
    harness.set_leader(True)

    with (
        patch("ops.model.Model.get_secret", side_effect=SecretNotFoundError),
        patch("ops.model.Application.add_secret", return_value=MagicMock()),
    ):
        harness.begin()
        mas_configuration = MASConfiguration.from_charm(harness.charm)

        assert mas_configuration.datasource["user"] == "user"
        assert mas_configuration.datasource["password"] == "password"
        assert mas_configuration.datasource["host"] == "myhost"
        assert mas_configuration.datasource["port"] == "5432"
        assert mas_configuration.mas_prefix == "/auth/"
        assert MAS_DATABASE_NAME in mas_configuration.database_uri


def test_mas_configuration_missing_database_relation() -> None:
    """
    arrange: Given a synapse charm without MAS database relation.
    act: Try to create MAS configuration from charm.
    assert: MASDatasourceMissingError is raised.
    """
    harness = Harness(SynapseCharm)
    harness.update_config({"enable_mas": True})
    harness.begin()

    with pytest.raises(MASDatasourceMissingError, match="Waiting for mas-database integration"):
        MASConfiguration.from_charm(harness.charm)


def test_mas_configuration_context_not_set_non_leader() -> None:
    """
    arrange: Given a non-leader synapse charm with MAS database relation but no secrets.
    act: Try to create MAS configuration from charm.
    assert: MASContextNotSetError is raised.
    """
    harness = Harness(SynapseCharm)
    harness.update_config({"enable_mas": True})
    postgresql_relation_data = {
        "endpoints": "myhost:5432",
        "username": "user",
        "password": "password",
    }
    harness.add_relation(MAS_DATABASE_INTEGRATION_NAME, "db", app_data=postgresql_relation_data)
    harness.set_leader(False)  # Non-leader unit

    with patch("ops.model.Model.get_secret", side_effect=SecretNotFoundError):
        harness.begin()
        with pytest.raises(MASContextNotSetError, match="Waiting for leader to set MAS context"):
            MASConfiguration.from_charm(harness.charm)


def test_mas_enabled_property() -> None:
    """
    arrange: Given a synapse charm.
    act: Check mas_enabled property with different config values.
    assert: Property returns correct boolean values.
    """
    harness = Harness(SynapseCharm)

    # Test default (False)
    harness.begin()
    assert harness.charm.mas_enabled is False

    # Test explicitly set to True
    harness.update_config({"enable_mas": True})
    assert harness.charm.mas_enabled is True

    # Test explicitly set to False
    harness.update_config({"enable_mas": False})
    assert harness.charm.mas_enabled is False


def test_get_mas_configuration_disabled() -> None:
    """
    arrange: Given a synapse charm with MAS disabled.
    act: Call get_mas_configuration.
    assert: Returns None.
    """
    harness = Harness(SynapseCharm)
    harness.update_config({"enable_mas": False})
    harness.begin()

    result = harness.charm.get_mas_configuration()
    assert result is None


def test_get_mas_configuration_enabled_no_database() -> None:
    """
    arrange: Given a synapse charm with MAS enabled but no database relation.
    act: Call get_mas_configuration.
    assert: Returns None.
    """
    harness = Harness(SynapseCharm)
    harness.update_config({"enable_mas": True})
    harness.begin()

    result = harness.charm.get_mas_configuration()
    assert result is None


def test_get_mas_configuration_enabled_with_database() -> None:
    """
    arrange: Given a synapse charm with MAS enabled and database relation.
    act: Call get_mas_configuration.
    assert: Returns MAS configuration.
    """
    harness = Harness(SynapseCharm)
    harness.update_config({"enable_mas": True})
    postgresql_relation_data = {
        "endpoints": "myhost:5432",
        "username": "user",
        "password": "password",
    }
    harness.add_relation(MAS_DATABASE_INTEGRATION_NAME, "db", app_data=postgresql_relation_data)
    harness.set_leader(True)

    with (
        patch("ops.model.Model.get_secret", side_effect=SecretNotFoundError),
        patch("ops.model.Application.add_secret", return_value=MagicMock()),
    ):
        harness.begin()
        result = harness.charm.get_mas_configuration()

        assert result is not None
        assert isinstance(result, MASConfiguration)


def test_get_mas_database_config_no_relation() -> None:
    """
    arrange: Given a synapse charm without MAS database relation.
    act: Call get_mas_database_config.
    assert: Returns None.
    """
    harness = Harness(SynapseCharm)
    harness.begin()

    result = harness.charm.get_mas_database_config()
    assert result is None


def test_get_mas_database_config_with_relation() -> None:
    """
    arrange: Given a synapse charm with MAS database relation.
    act: Call get_mas_database_config.
    assert: Returns database configuration dictionary.
    """
    harness = Harness(SynapseCharm)
    postgresql_relation_data = {
        "endpoints": "myhost:5432",
        "username": "user",
        "password": "password",
        "database": "mas",  # Add the database name explicitly
    }
    harness.add_relation(MAS_DATABASE_INTEGRATION_NAME, "db", app_data=postgresql_relation_data)
    harness.begin()

    result = harness.charm.get_mas_database_config()

    assert result is not None
    assert result == {
        "host": "myhost",
        "port": "5432",
        "database": "synapse",  # Database observer returns "synapse" by default
        "username": "user",
        "password": "password",
    }


def test_mas_context_secrets_generation() -> None:
    """
    arrange: Given a leader unit with MAS enabled and database relation.
    act: Generate MAS configuration which creates secrets.
    assert: Secrets are properly generated with correct format.
    """
    harness = Harness(SynapseCharm)
    harness.update_config({"enable_mas": True, "oidc_subject_claim": "user.email"})
    postgresql_relation_data = {
        "endpoints": "myhost:5432",
        "username": "user",
        "password": "password",
    }
    harness.add_relation(MAS_DATABASE_INTEGRATION_NAME, "db", app_data=postgresql_relation_data)
    harness.set_leader(True)

    with (
        patch("ops.model.Model.get_secret", side_effect=SecretNotFoundError),
        patch("ops.model.Application.add_secret", return_value=MagicMock()) as add_secret_mock,
    ):
        harness.begin()
        mas_configuration = MASConfiguration.from_charm(harness.charm)

        # Verify secret was created
        add_secret_mock.assert_called_once()
        secret_content = add_secret_mock.call_args[1]["content"]

        # Check that all required keys are present
        required_keys = [
            "encryption-key",
            "signing-key-id",
            "signing-key-rsa",
            "synapse-shared-secret",
            "synapse-oidc-client-id",
            "synapse-oidc-client-secret",
            "upstream-oidc-provider-id",
        ]
        for key in required_keys:
            assert key in secret_content
            assert secret_content[key]  # Not empty

        # Verify encryption key length (64 hex chars = 32 bytes)
        assert len(secret_content["encryption-key"]) == 64

        # Verify signing key ID length (8 hex chars = 4 bytes)
        assert len(secret_content["signing-key-id"]) == 8

        # Verify shared secret length (32 hex chars = 16 bytes)
        assert len(secret_content["synapse-shared-secret"]) == 32

        # Verify OIDC client secret length (32 hex chars = 16 bytes)
        assert len(secret_content["synapse-oidc-client-secret"]) == 32

        # Verify signing key is PEM format
        assert "-----BEGIN PRIVATE KEY-----" in secret_content["signing-key-rsa"]
        assert "-----END PRIVATE KEY-----" in secret_content["signing-key-rsa"]

        # Verify mas context properties
        assert mas_configuration.mas_context.oidc_subject_claim == "user.email"
