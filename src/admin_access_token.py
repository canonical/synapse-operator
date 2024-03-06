# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

# While this is a refactor,is expected to have few public methods.
# pylint: disable=too-few-public-methods

"""The Admin Access Token service."""
import logging
import typing

import ops
from ops.jujuversion import JujuVersion

import synapse

logger = logging.getLogger(__name__)

JUJU_HAS_SECRETS = JujuVersion.from_environ().has_secrets
PEER_RELATION_NAME = "synapse-peers"
# Disabling it since these are not hardcoded password
SECRET_ID = "secret-id"  # nosec
SECRET_KEY = "secret-key"  # nosec


class AdminAccessTokenService:
    """The Admin Access Token Service.

    Attrs:
        _app: instance of Juju application.
        _model: instance of Juju model.
    """

    def __init__(self, app: ops.Application, model: ops.Model):
        """Initialize the service.

        Args:
            app: instance of Juju application.
            model: instance of Juju model.
        """
        self._app = app
        self._model = model

    def get(self, container: ops.Container) -> typing.Optional[str]:
        """Get admin access token from peer relation.

        If the admin token is not valid or it does not exist it creates one.

        Args:
            container: Workload container.

        Returns:
            admin access token or None if fails.
        """
        admin_access_token = self._get_from_peer_relation()
        if admin_access_token is None or not synapse.is_token_valid(admin_access_token):
            admin_access_token = self._renew_token(container)
        return admin_access_token

    def _get_from_peer_relation(self) -> typing.Optional[str]:
        """Get admin access token from peer relation.

        Returns:
            Admin access token or None if not found or failure.
        """
        peer_relation = self._model.get_relation(PEER_RELATION_NAME)
        if not peer_relation:
            logger.error(
                "Failed to get admin access token: no peer relation %s found", PEER_RELATION_NAME
            )
            return None
        admin_access_token = None
        if JUJU_HAS_SECRETS:
            secret_id = peer_relation.data[self._app].get(SECRET_ID)
            if secret_id:
                try:
                    secret = self._model.get_secret(id=secret_id)
                    admin_access_token = secret.get_content().get(SECRET_KEY)
                except ops.model.SecretNotFoundError as exc:
                    logger.exception("Failed to get secret id %s: %s", secret_id, str(exc))
                    del peer_relation.data[self._app][SECRET_ID]
                    return None
        else:
            # There is no Secrets support and none relation data was created
            # So lets create the user and store its token in the peer relation
            secret_value = peer_relation.data[self._app].get(SECRET_KEY)
            if secret_value:
                admin_access_token = secret_value
        return admin_access_token

    def _renew_token(self, container: ops.Container) -> typing.Optional[str]:
        """Create/Renew an admin access token and put it in the peer relation.

        Args:
            container: Workload container.

        Returns:
            admin access token or None if not found or failure.
        """
        peer_relation = self._model.get_relation(PEER_RELATION_NAME)
        if not peer_relation:
            logger.error(
                "Failed to get admin access token: no peer relation %s found", PEER_RELATION_NAME
            )
            return None
        admin_user = synapse.create_admin_user(container)
        if not admin_user:
            logger.error("Error getting admin access token")
            return None
        if JUJU_HAS_SECRETS:
            logger.debug("Adding/ secret")
            secret = self._app.add_secret({SECRET_KEY: admin_user.access_token})
            peer_relation.data[self._app].update({SECRET_ID: secret.id})
            admin_access_token = admin_user.access_token
        else:
            logger.debug("Adding peer data")
            peer_relation.data[self._app].update({SECRET_KEY: admin_user.access_token})
            admin_access_token = admin_user.access_token
        return admin_access_token
