# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helper module used to manage interactions with Synapse secrets."""

import logging
import typing
from secrets import token_hex

import ops
from ops.jujuversion import JujuVersion

import actions
import synapse

PEER_RELATION_NAME = "synapse-peers"
# Disabling it since these are not hardcoded password
SECRET_ID = "secret-id"  # nosec
SECRET_KEY = "secret-key"  # nosec

logger = logging.getLogger(__name__)


def _update_peer_data(charm: ops.CharmBase, container: ops.model.Container) -> None:
    """Update peer data if needed.

    The admin access token is stored in a Secret (Juju 3) or in a peer relation
    data. If already exists, no action is taken. Otherwise, will create an admin
    user and store the token.

    Args:
        charm: The charm object.
        container: Synapse container.
    """
    # If there is no secret, we use peer relation data
    # If there is secret, then we update the secret and add the secret id to peer data
    peer_relation = charm.model.get_relation(PEER_RELATION_NAME)
    if not peer_relation:
        # there is no peer relation so nothing to be done
        return
    # The username is random because if the user exists, register_user will try to get the
    # access_token.
    # But to do that it needs an admin user and we don't have one yet.
    # So, to be on the safe side, the user name is randomly generated and if for any reason
    # there is no access token on peer data/secret, another user will be created.
    #
    # Using 16 to create a random value but to  be secure against brute-force attacks,
    # please check the docs:
    # https://docs.python.org/3/library/secrets.html#how-many-bytes-should-tokens-use
    username = token_hex(16)
    if JujuVersion.from_environ().has_secrets and not peer_relation.data[charm.app].get(SECRET_ID):
        # we can create secrets and the one that we need was not created yet
        logger.debug("Adding secret")
        admin_user = actions.register_user(container, username, True)
        secret = charm.app.add_secret({SECRET_KEY: admin_user.access_token})
        peer_relation.data[charm.app].update({SECRET_ID: secret.id})
        return

    if not JujuVersion.from_environ().has_secrets and not peer_relation.data[charm.app].get(
        SECRET_KEY
    ):
        # we can't create secrets and peer data is empty
        logger.debug("Updating peer relation data")
        admin_user = actions.register_user(container, username, True)
        peer_relation.data[charm.app].update({SECRET_KEY: admin_user.access_token})


def get_admin_access_token(charm: ops.CharmBase) -> typing.Optional[str]:
    """Get admin access token.

    Args:
        charm: The charm object.

    Returns:
        admin access token.
    """
    container = charm.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
    if not container.can_connect():
        logger.warning("Failed to get secret storage: waiting for pebble")
        return None
    peer_relation = charm.model.get_relation(PEER_RELATION_NAME)
    if not peer_relation:
        # there is no peer relation so nothing to be done
        logger.warning("Failed to get secret storage: waiting for peer relation")
        return None
    _update_peer_data(charm, container)
    if JujuVersion.from_environ().has_secrets:
        secret_id = peer_relation.data[charm.app].get(SECRET_ID)
        if secret_id:
            secret = charm.model.get_secret(id=secret_id)
            secret_value = secret.get_content().get(SECRET_KEY)
    else:
        secret_value = peer_relation.data[charm.app].get(SECRET_KEY)
    return secret_value
