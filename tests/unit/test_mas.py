# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Synapse charm unit tests."""

from unittest.mock import MagicMock

import pytest
import yaml
from ops.model import SecretNotFoundError
from ops.testing import Harness

from auth.mas import (
    generate_admin_access_token,
    generate_mas_config,
    generate_synapse_msc3861_config,
)
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


def test_generate_admin_access_token() -> None:
    """
    arrange: Given a mocked synapse container with an exec method that raises ExecError.
    act: run verify_user_email.
    assert: The correct exception is raised.
    """
    access_token = "mct_ePEtkuchAMoIDTQ5EyhecPKZry6CWG_hRAnb1"
    mock_issue_mct_output = (
        "2024-12-19T00:31:06.072775Z  "
        "INFO mas_cli::commands::manage: crates/cli/src/commands/manage.rs:295: "
        f"Compatibility token issued: {access_token} "
        "compat_access_token.id=01JFE56JAC215GX3SM8ZAD8BDH "
        "compat_session.id=01JFE56JABDT45508DSCWM4VF0 "
        "compat_session.device=Qssg28l9Wb "
        "user.id=01JFAJDSY2PMMV278XF04TS34W user.username=xxxx"
    )
    container = MagicMock()
    exec_process_mock = MagicMock()
    exec_process_mock.wait_output = MagicMock(return_value=(mock_issue_mct_output, None))
    container.exec = MagicMock(return_value=exec_process_mock)
    assert access_token == generate_admin_access_token(container, "admin")
