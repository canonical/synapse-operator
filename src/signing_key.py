#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Synapse signing key."""


import logging
import typing

import ops

import synapse
from charm_state import CharmState

logger = logging.getLogger(__name__)

SIGNING_KEY_SECRET_LABEL = "synapse-signing-key"
SIGNING_KEY_SECRET_CONTENT_ID = "secret-signing-key"
SIGNING_KEY_PEER_ID = "secret-signing-id"


def signing_key_path(charm_state: CharmState) -> str:
    """Get signing key path.

    Args:
        charm_state: charm state.

    Returns:
        signing key path as string.
    """
    return f"{synapse.SYNAPSE_CONFIG_DIR}/{charm_state.synapse_config.server_name}.signing.key"


def get_signing_key_secret(
    peer_relation: ops.Relation, charm: ops.CharmBase
) -> typing.Optional[ops.Secret]:
    """Get signing key secret .

    Args:
        peer_relation: synapse peer relation.
        charm: charm instance.

    Returns:
        Secret.
    """
    signing_secret = None
    secret_id = peer_relation.data[charm.app].get(SIGNING_KEY_PEER_ID)
    if secret_id:
        try:
            signing_secret = charm.model.get_secret(id=secret_id)
            return signing_secret
        except (ops.model.SecretNotFoundError, ValueError, TypeError) as exc:
            logger.exception("Failed to get secret id %s: %s", secret_id, str(exc))
            del peer_relation.data[charm.app][SIGNING_KEY_PEER_ID]
    return signing_secret


def write_to_container(
    peer_relation: ops.Relation,
    charm: ops.CharmBase,
    charm_state: CharmState,
    container: ops.Container,
) -> None:
    """Get signing key from secret and write to container.

    Args:
        peer_relation: synapse peer relation.
        charm: charm instance.
        charm_state: charm state.
        container: container.
    """
    secret = get_signing_key_secret(peer_relation, charm)
    if secret:
        content = secret.get_content().get(SIGNING_KEY_SECRET_CONTENT_ID)
        if content:
            container.push(
                signing_key_path(charm_state),
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
    """Create secret with signing key content.

    Args:
        peer_relation: synapse peer relation.
        charm: charm instance.
        charm_state: charm state.
        container: container.
    """
    if not charm.unit.is_leader():
        # only leader writes secrets
        return

    signing_key = ""
    with container.pull(signing_key_path(charm_state)) as f:
        signing_key = f.read()
        signing_key = signing_key.rstrip()
    new_content = {"secret-signing-key": signing_key}

    existing_secret = get_signing_key_secret(peer_relation, charm)

    if (
        existing_secret
        and existing_secret.label == SIGNING_KEY_SECRET_LABEL
        and signing_key == existing_secret.get_content().get(SIGNING_KEY_SECRET_CONTENT_ID)
    ):
        logger.info("Received signing key but there is no change, skipping")
        return

    if existing_secret and existing_secret.label:
        # the existing secret already has label but has different content
        # so we must only update it
        try:
            existing_secret.set_content(new_content)
            logger.info("Signing key secret was updated, id: %d", existing_secret.id)
            return
        except (ops.model.SecretNotFoundError, ValueError, TypeError) as exc:
            logger.exception("Failed to get secret id %s: %s", existing_secret, str(exc))
    # secret not found or no label
    # so we create a new one
    new_secret = charm.app.add_secret(new_content, label=SIGNING_KEY_SECRET_LABEL)
    peer_relation.data[charm.app].update({SIGNING_KEY_PEER_ID: typing.cast(str, new_secret.id)})
    logger.info("New signing key secret was created, id: %s", new_secret.id)
