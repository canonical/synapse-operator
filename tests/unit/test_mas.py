# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Synapse charm unit tests."""

from unittest.mock import MagicMock

import pytest
import yaml
from ops.model import SecretNotFoundError
from ops.testing import Harness

from charm import SynapseCharm
from state.charm_state import SynapseConfig
from state.mas import MAS_DATABASE_INTEGRATION_NAME, MAS_DATABASE_NAME, MASConfiguration


# pylint: disable=protected-access
def test_mas_generate_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    arrange: charm deployed.
    act: start the Synapse charm, set Synapse container to be ready and set server_name.
    assert: Synapse charm should submit the correct Synapse pebble layer to pebble.
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
    rendered_mas_config = harness.charm._mas.generate_mas_config(
        mas_configuration, synapse_configuration, "10.1.1.0"
    )
    parsed_mas_config = yaml.safe_load(rendered_mas_config)
    assert parsed_mas_config["http"]["public_base"] == f"{config['public_baseurl']}/auth/"

    db_user = postgresql_relation_data["username"]
    db_password = postgresql_relation_data["password"]
    db_endpoint = postgresql_relation_data["endpoints"]
    assert (
        parsed_mas_config["database"]["uri"]
        == f"postgresql://{db_user}:{db_password}@{db_endpoint}/{MAS_DATABASE_NAME}"
    )
