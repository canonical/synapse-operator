# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""SMTPObserver unit tests."""

# pylint: disable=protected-access

import pytest
from charms.smtp_integrator.v0.smtp import AuthType, TransportSecurity
from ops.testing import Harness

from charm_types import SMTPConfiguration

RELATION_DATA_TO_SMTP_CONF_PARAMS = [
    (
        {
            "host": "127.0.0.1",
            "port": "25",
            "auth_type": AuthType.NONE,
            "transport_security": TransportSecurity.NONE,
        },
        SMTPConfiguration(
            enable_tls=False,
            force_tls=False,
            require_transport_security=False,
            host="127.0.0.1",
            port=25,
            user=None,
            password=None,
        ),
    ),
    (
        {
            "host": "127.0.0.1",
            "port": "25",
            "auth_type": AuthType.PLAIN,
            "transport_security": TransportSecurity.STARTTLS,
            "user": "username",
            "password": "SECRET",  # no sec
        },
        SMTPConfiguration(
            enable_tls=True,
            force_tls=False,
            require_transport_security=True,
            host="127.0.0.1",
            port=25,
            user="username",
            password="SECRET",  # nosec
        ),
    ),
    (
        {
            "host": "127.0.0.1",
            "port": "587",
            "auth_type": AuthType.PLAIN,
            "transport_security": TransportSecurity.TLS,
            "user": "username",
            "password": "SECRET",  # nosec
        },
        SMTPConfiguration(
            enable_tls=True,
            force_tls=True,
            require_transport_security=True,
            host="127.0.0.1",
            port=587,
            user="username",
            password="SECRET",  # nosec
        ),
    ),
]


@pytest.mark.parametrize("relation_data, expected_config", RELATION_DATA_TO_SMTP_CONF_PARAMS)
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


def test_get_relation_as_smtp_conf_password_from_juju_secret(harness: Harness):
    """
    arrange: add smtp relation to smtp-integration with secret.
    act: get smtp configuration from smtp observer.
    assert: password in smtp configuration is the same as the original secret.
    """
    password_id = harness.add_model_secret("smtp-integrator", {"password": "SECRET"})
    smtp_relation_data = {
        "host": "127.0.0.1",
        "port": "587",
        "user": "username",
        "password_id": password_id,
        "auth_type": AuthType.PLAIN,
        "transport_security": TransportSecurity.TLS,
    }
    harness.add_relation("smtp", "smtp-integrator", app_data=smtp_relation_data)
    harness.grant_secret(password_id, "synapse")
    harness.begin()

    smtp_configuration = harness.charm._smtp.get_relation_as_smtp_conf()

    assert smtp_configuration["password"] == "SECRET"
