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

# No sensitive data
SIGNING_KEY_SECRET_LABEL = "synapse-signing-key"  # nosec
SIGNING_KEY_SECRET_CONTENT_ID = "secret-signing-key"  # nosec
SIGNING_KEY_PEER_ID = "secret-signing-id"


class SigningKeyWriteError(Exception):
    """Error during signing key write to container."""


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

    Raises:
        SigningKeyWriteError: in case of error writing the secret to the container.
    """
    secret = get_signing_key_secret(peer_relation, charm)
    if not secret:
        logger.warning("Signing key secret not found")
        raise SigningKeyWriteError("Signing key secret not found.")

    content = secret.get_content().get(SIGNING_KEY_SECRET_CONTENT_ID)
    if not content:
        logger.error("Signing key secret content not found")
        raise SigningKeyWriteError(
            f"Signing key secret content with ID {SIGNING_KEY_SECRET_CONTENT_ID}  not found."
        )

    container.push(
        signing_key_path(charm_state),
        content,
        make_dirs=True,
        encoding="utf-8",
    )


def is_secret_container_equal(
    peer_relation: ops.Relation,
    charm: ops.CharmBase,
    charm_state: CharmState,
    container: ops.Container,
) -> bool:
    """Check if secret and file in the container have the same content.

    Args:
        peer_relation: synapse peer relation.
        charm: charm instance.
        charm_state: charm state.
        container: container.

    Returns:
        if secret and file in container has the same content or not.
    """
    signing_key = ""
    with container.pull(signing_key_path(charm_state)) as f:
        signing_key = f.read()
        signing_key = signing_key.rstrip()

    existing_secret = get_signing_key_secret(peer_relation, charm)
    if existing_secret and signing_key == existing_secret.get_content().get(
        SIGNING_KEY_SECRET_CONTENT_ID
    ):
        return True
    return False


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
    if existing_secret and signing_key == existing_secret.get_content().get(
        SIGNING_KEY_SECRET_CONTENT_ID
    ):
        if existing_secret.label != SIGNING_KEY_SECRET_LABEL:
            logger.info("Signing key secret label was updated, id: %s", existing_secret.id)
            existing_secret.set_info(label=SIGNING_KEY_SECRET_LABEL)
        logger.info("Received signing key but there is no change, skipping")
        return

    if existing_secret:
        # the existing secret already has label but has different content
        # so we must only update it
        try:
            existing_secret.set_content(new_content)
            existing_secret.set_info(label=SIGNING_KEY_SECRET_LABEL)
            logger.info("Signing key secret was updated, id: %s", existing_secret.id)
            return
        except (ops.model.SecretNotFoundError, ValueError, TypeError) as exc:
            logger.exception("Failed to get secret id %s: %s", existing_secret, str(exc))
    # secret not found
    # so we create a new one
    new_secret = charm.app.add_secret(new_content, label=SIGNING_KEY_SECRET_LABEL)
    peer_relation.data[charm.app].update({SIGNING_KEY_PEER_ID: typing.cast(str, new_secret.id)})
    logger.info("New signing key secret was created, id: %s", new_secret.id)
