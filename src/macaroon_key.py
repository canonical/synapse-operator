#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Synapse macaroon key."""

# Similar to signing-key
# pylint: disable=R0801

import logging
import typing

import ops

import synapse
from charm_state import CharmState

logger = logging.getLogger(__name__)

# No sensitive data
MACAROON_KEY_SECRET_LABEL = "synapse-macaroon-key"  # nosec
MACAROON_KEY_SECRET_CONTENT_ID = "secret-macaroon-key"  # nosec
MACAROON_KEY_PEER_ID = "secret-macaroon-id"


def macaroon_key_path(charm_state: CharmState) -> str:
    """Get macaroon key path.

    Args:
        charm_state: charm state.

    Returns:
        macaroon key path as string.
    """
    return f"{synapse.SYNAPSE_CONFIG_DIR}/{charm_state.synapse_config.server_name}.macaroon.key"


def get_macaroon_key_secret(
    peer_relation: ops.Relation, charm: ops.CharmBase
) -> typing.Optional[ops.Secret]:
    """Get macaroon key secret .

    Args:
        peer_relation: synapse peer relation.
        charm: charm instance.

    Returns:
        Secret.
    """
    macaroon_secret = None
    secret_id = peer_relation.data[charm.app].get(MACAROON_KEY_PEER_ID)
    if secret_id:
        try:
            macaroon_secret = charm.model.get_secret(id=secret_id)
            return macaroon_secret
        except (ops.model.SecretNotFoundError, ValueError, TypeError) as exc:
            logger.exception("Failed to get macaroon secret id %s: %s", secret_id, str(exc))
            del peer_relation.data[charm.app][MACAROON_KEY_PEER_ID]
    return macaroon_secret


def write_to_container(
    peer_relation: ops.Relation,
    charm: ops.CharmBase,
    charm_state: CharmState,
    container: ops.Container,
) -> None:
    """Get macaroon key from secret and write to container.

    Args:
        peer_relation: synapse peer relation.
        charm: charm instance.
        charm_state: charm state.
        container: container.
    """
    secret = get_macaroon_key_secret(peer_relation, charm)
    if secret:
        content = secret.get_content().get(MACAROON_KEY_SECRET_CONTENT_ID)
        if content:
            container.push(
                macaroon_key_path(charm_state),
                content,
                make_dirs=True,
                encoding="utf-8",
            )


def write_to_secret(
    peer_relation: ops.Relation,
    charm: ops.CharmBase,
    charm_state: CharmState,
    container: ops.Container,
) -> None:
    """Create secret with macaroon key content.

    Args:
        peer_relation: synapse peer relation.
        charm: charm instance.
        charm_state: charm state.
        container: container.
    """
    if not charm.unit.is_leader():
        # only leader writes secrets
        return

    macaroon_key = ""
    with container.pull(macaroon_key_path(charm_state)) as f:
        macaroon_key = f.read()
        macaroon_key = macaroon_key.rstrip()
    new_content = {"secret-macaroon-key": macaroon_key}

    existing_secret = get_macaroon_key_secret(peer_relation, charm)
    if existing_secret and macaroon_key == existing_secret.get_content().get(
        MACAROON_KEY_SECRET_CONTENT_ID
    ):
        if existing_secret.label != MACAROON_KEY_SECRET_LABEL:
            logger.info("Macaroon key secret label was updated, id: %s", existing_secret.id)
            existing_secret.set_info(label=MACAROON_KEY_SECRET_LABEL)
        logger.info("Received macaroon key but there is no change, skipping")
        return

    if existing_secret:
        # the existing secret already has label but has different content
        # so we must only update it
        try:
            existing_secret.set_content(new_content)
            existing_secret.set_info(label=MACAROON_KEY_SECRET_LABEL)
            logger.info("Macaroon key secret was updated, id: %s", existing_secret.id)
            return
        except (ops.model.SecretNotFoundError, ValueError, TypeError) as exc:
            logger.exception("Failed to get macaroon secret id %s: %s", existing_secret, str(exc))
    # secret not found
    # so we create a new one
    new_secret = charm.app.add_secret(new_content, label=MACAROON_KEY_SECRET_LABEL)
    peer_relation.data[charm.app].update({MACAROON_KEY_PEER_ID: typing.cast(str, new_secret.id)})
    logger.info("New macaroon key secret was created, id: %s", new_secret.id)
