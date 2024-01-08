# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""SMTPObserver unit tests."""

# pylint: disable=protected-access

from secrets import token_hex

import pytest
from charms.smtp_integrator.v0.smtp import AuthType, TransportSecurity
from ops.testing import Harness

from charm_state import CharmConfigInvalidError
from charm_types import SMTPConfiguration


def _test_get_relation_data_to_smtp_conf_parameters():
    """Generate parameters for the test_get_relation_as_smtp_conf.

    Returns:
        The tests.
    """
    password = token_hex(16)
    return [
        pytest.param(
            {
                "host": "127.0.0.1",
                "port": "25",
                "auth_type": AuthType.PLAIN,
                "transport_security": TransportSecurity.STARTTLS,
                "user": "username",
                "password": password,
            },
            SMTPConfiguration(
                enable_tls=True,
                force_tls=False,
                require_transport_security=True,
                host="127.0.0.1",
                port=25,
                user="username",
                password=password,
            ),
            id="plain auth type with starttls",
        ),
        pytest.param(
            {
                "host": "127.0.0.1",
                "port": "587",
                "auth_type": AuthType.PLAIN,
                "transport_security": TransportSecurity.TLS,
                "user": "username",
                "password": password,
            },
            SMTPConfiguration(
                enable_tls=True,
                force_tls=True,
                require_transport_security=True,
                host="127.0.0.1",
                port=587,
                user="username",
                password=password,
            ),
            id="plain auth type with tls",
        ),
    ]


@pytest.mark.parametrize(
    "relation_data, expected_config", _test_get_relation_data_to_smtp_conf_parameters()
)
def test_get_relation_as_smtp_conf(harness: Harness, relation_data, expected_config):
    """
    arrange: add relation_data from parameter.
    act: get SMTPConfiguration from smtp observer.
    assert: expected smtp configuration matches returned one.
    """
    harness.add_relation("smtp", "smtp-integrator", app_data=relation_data)
    harness.begin()

    smtp_configuration = harness.charm._smtp.get_relation_as_smtp_conf()

    assert smtp_configuration == expected_config


@pytest.mark.parametrize(
    "relation_data",
    [
        pytest.param(
            {
                "host": "127.0.0.1",
                "port": "25",
                "auth_type": AuthType.PLAIN,
                "username": "username",
                "password": token_hex(16),
                "transport_security": TransportSecurity.NONE,
            },
            id="auth type plan with transport security none",
        ),
        pytest.param(
            {
                "host": "127.0.0.1",
                "port": "25",
                "auth_type": AuthType.NONE,
                "transport_security": TransportSecurity.TLS,
            },
            id="auth type none with TLS",
        ),
    ],
)
def test_get_relation_fails_invalid_config(harness: Harness, relation_data):
    """
    arrange: add not supported invalid relation_data from parameter.
    act: get SMTPConfiguration from smtp observer.
    assert: raises exception CharmConfigInvalidError
    """
    harness.add_relation("smtp", "smtp-integrator", app_data=relation_data)
    harness.begin()

    with pytest.raises(CharmConfigInvalidError):
        harness.charm._smtp.get_relation_as_smtp_conf()


def test_get_relation_as_smtp_conf_password_from_juju_secret(harness: Harness):
    """
    arrange: add smtp relation to smtp-integration with secret.
    act: get smtp configuration from smtp observer.
    assert: password in smtp configuration is the same as the original secret.
    """
    password = token_hex(16)
    password_id = harness.add_model_secret("smtp-integrator", {"password": password})
    smtp_relation_data = {
        "auth_type": AuthType.PLAIN,
        "host": "127.0.0.1",
        "password_id": password_id,
        "port": "587",
        "transport_security": TransportSecurity.TLS,
        "user": "alice",
    }
    harness.add_relation("smtp", "smtp-integrator", app_data=smtp_relation_data)
    harness.grant_secret(password_id, "synapse")
    harness.begin()

    smtp_configuration = harness.charm._smtp.get_relation_as_smtp_conf()

    assert smtp_configuration["password"] == password
