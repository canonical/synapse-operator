# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""The SMTP integrator relation observer."""

import logging
from typing import Optional

import ops
from charms.smtp_integrator.v0.smtp import (
    AuthType,
    SmtpDataAvailableEvent,
    SmtpRelationData,
    SmtpRequires,
    TransportSecurity,
)
from ops.framework import Object
from pydantic.v1 import ValidationError

from charm_types import SMTPConfiguration
from state.charm_state import CharmConfigInvalidError
from state.mas import MASConfiguration
from state.validation import CharmBaseWithState, validate_charm_state

logger = logging.getLogger(__name__)


class SMTPObserver(Object):
    """The SMTP relation observer."""

    _RELATION_NAME = "smtp"

    def __init__(self, charm: CharmBaseWithState):
        """Initialize the observer and register event handlers.

        Args:
            charm: The parent charm to attach the observer to.
        """
        super().__init__(charm, "smtp-observer")
        self._charm = charm
        self.smtp = SmtpRequires(
            self._charm,
            relation_name=self._RELATION_NAME,
        )
        self.framework.observe(
            self.smtp.on.smtp_data_available,
            self._on_smtp_relation_data_available,
        )

    def get_charm(self) -> CharmBaseWithState:
        """Return the current charm.

        Returns:
           The current charm
        """
        return self._charm

    @validate_charm_state
    def _on_smtp_relation_data_available(self, _: SmtpDataAvailableEvent) -> None:
        """Handle SMTP data available."""
        charm = self.get_charm()
        charm_state = charm.build_charm_state()
        mas_configuration = MASConfiguration.from_charm(charm)

        self.model.unit.status = ops.MaintenanceStatus("Preparing the SMTP integration")
        logger.debug("_on_smtp_relation_data_available emitting reconcile")
        self.get_charm().reconcile(charm_state, mas_configuration)

    def get_relation_as_smtp_conf(self) -> Optional[SMTPConfiguration]:
        """Get SMTP data from relation.

        Returns:
            Dict: Information needed for setting environment variables.

        Raises:
            CharmConfigInvalidError: If the SMTP configurations is not supported.
        """
        if not self.model.relations.get(self._RELATION_NAME):
            return None
        try:
            relation_data: Optional[SmtpRelationData] = self.smtp.get_relation_data()
        except (ValidationError, ValueError):
            # ValidationError happens in the smtp(_legacy)relation_created event, as
            # the relation databag is empty at that point.
            logger.info("SMTP databag is empty. SMTP information will be set in the next event.")
            return None

        if relation_data is None:
            return None

        if relation_data.transport_security == TransportSecurity.NONE:
            raise CharmConfigInvalidError("Transport security NONE is not supported for SMTP")

        if relation_data.auth_type != AuthType.PLAIN:
            raise CharmConfigInvalidError("Only PLAIN auth type is supported for SMTP")

        user = relation_data.user
        password = self._get_password_from_relation_data(relation_data)

        # Not all combinations for the next variables are correct. See:
        # https://github.com/matrix-org/synapse/blob/develop/synapse/config/emailconfig.py
        force_tls = False
        enable_tls = False
        require_transport_security = False
        if relation_data.transport_security == TransportSecurity.STARTTLS:
            enable_tls = True
            require_transport_security = True
        elif relation_data.transport_security == TransportSecurity.TLS:
            force_tls = True
            enable_tls = True
            require_transport_security = True

        return SMTPConfiguration(
            enable_tls=enable_tls,
            force_tls=force_tls,
            require_transport_security=require_transport_security,
            host=relation_data.host,
            port=relation_data.port,
            user=user,
            password=password,
        )

    def _get_password_from_relation_data(self, relation_data: SmtpRelationData) -> Optional[str]:
        """Get smtp password from relation data.

        Arguments:
            relation_data: The relation data from where to extract the password

        Returns:
            the password or None if no password found
        """
        # If the relation data password_id exists, that means that
        # Juju version is >= 3.0 and secrets are used for the password.
        # Otherwise, use the field password as a fallback
        if relation_data.password_id:
            secret = self.model.get_secret(id=relation_data.password_id)
            content = secret.get_content()
            return content["password"]
        return relation_data.password
