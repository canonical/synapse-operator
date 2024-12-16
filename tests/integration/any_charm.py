# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

# pylint: disable=import-error,consider-using-with,no-member,too-few-public-methods

"""This code should be loaded into any-charm which is used for integration tests."""

import logging
import typing

from any_charm_base import AnyCharmBase
from matrix_auth import MatrixAuthRequirerData, MatrixAuthRequires
from ops.framework import Object
from pydantic import SecretStr

logger = logging.getLogger(__name__)


class AnyCharm(AnyCharmBase):
    """Execute a simple charm to test the relation."""

    def __init__(self, *args, **kwargs):
        """Initialize the charm and observe the relation events.

        Args:
            args: Arguments to pass to the parent class.
            kwargs: Keyword arguments to pass to the parent class
        """
        super().__init__(*args, **kwargs)

        self.plugin_auth = MatrixAuthRequires(self, relation_name="require-matrix-auth")
        self.framework.observe(
            self.plugin_auth.on.matrix_auth_request_processed,
            self._on_matrix_auth_request_processed,
        )

    def _on_matrix_auth_request_processed(self, _: Object) -> None:
        """Handle the matrix auth request processed event."""
        logger.info("Matrix auth request processed")
        content = """id: irc
hs_token: 82c7a893d020b5f28eaf7ba31e1d1091b12ebafc5ceb1b6beac2b93defc1b301
as_token: a66ae41f82b05bebfc9c259135ce1ce35c856000d542ab5d1f01e0212439d534
namespaces:
  users:
    - exclusive: true
      regex: '@irc_.*:yourhomeserverdomain'
  aliases:
    - exclusive: true
      regex: '#irc_.*:yourhomeserverdomain'
url: 'http://localhost:8090'
sender_localpart: appservice-irc
rate_limited: false
protocols:
  - irc"""
        registration = typing.cast(SecretStr, content)
        any_charm_data = MatrixAuthRequirerData(registration=registration)
        relation = self.model.get_relation(self.plugin_auth.relation_name)
        if relation:
            logger.info("Matrix auth request setting relation data")
            self.plugin_auth.update_relation_data(
                relation=relation, matrix_auth_requirer_data=any_charm_data
            )
