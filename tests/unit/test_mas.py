# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Synapse charm unit tests."""

from unittest.mock import MagicMock

import pytest
import yaml
from ops.model import SecretNotFoundError
from ops.testing import Harness

from auth.mas import generate_mas_config, generate_synapse_msc3861_config
from charm import SynapseCharm
from state.charm_state import SynapseConfig
from state.mas import MAS_DATABASE_INTEGRATION_NAME, MAS_DATABASE_NAME, MASConfiguration


def test_mas_generate_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    arrange: Given a synapse charm related to postgresql.
    act: Generate the mas charm state and the mas configuration.
    assert: The mas config is correctly generated with the expected values.
    """
    monkeypatch.setattr("ops.model.Model.get_secret", MagicMock(side_effect=SecretNotFoundError))
    monkeypatch.setattr("ops.model.Application.add_secret", MagicMock())

    harness = Harness(SynapseCharm)
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
    }
    synapse_configuration = SynapseConfig(**config)  # type: ignore[arg-type]
    rendered_mas_config = generate_mas_config(mas_configuration, synapse_configuration, "10.1.1.0")
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
