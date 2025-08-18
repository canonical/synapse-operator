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


def signing_key_path(charm_state: CharmState) -> str:
    """Get signing key path.

    Args:
        charm_state: charm state.

    Returns:
        signing key path as string.
    """
    return f"{synapse.SYNAPSE_CONFIG_DIR}/{charm_state.synapse_config.server_name}.signing.key"


def get_signing_key_secret_content(
    peer_relation: ops.Relation, charm: ops.CharmBase
) -> typing.Optional[str]:
    """Get signing key secret content.

    Args:
        peer_relation: synapse peer relation.
        charm: charm instance.

    Returns:
        Content as string.
    """
    content = None
    secret_id = peer_relation.data[charm.app].get("secret-signing-id")
    if secret_id:
        try:
            secret = charm.model.get_secret(id=secret_id)
            content = secret.get_content().get("secret-signing-key")
        except (ops.model.SecretNotFoundError, ValueError, TypeError) as exc:
            logger.exception("Failed to get secret id %s: %s", secret_id, str(exc))
            del peer_relation.data[charm.app]["secret-signing-id"]
    return content


def get_signing_key_secret_label(
    peer_relation: ops.Relation, charm: ops.CharmBase
) -> typing.Optional[str]:
    """Get signing key secret label.

    Args:
        peer_relation: synapse peer relation.
        charm: charm instance.

    Returns:
        label as string.
    """
    label = None
    secret_id = peer_relation.data[charm.app].get("secret-signing-id")
    if secret_id:
        try:
            secret = charm.model.get_secret(id=secret_id)
            return secret.label
        except (ops.model.SecretNotFoundError, ValueError, TypeError) as exc:
            logger.exception("Failed to get secret id %s: %s", secret_id, str(exc))
    return label


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
    content = get_signing_key_secret_content(peer_relation, charm)
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
    signing_key = ""
    with container.pull(signing_key_path(charm_state)) as f:
        signing_key = f.read()
        signing_key = signing_key.rstrip()
    label = get_signing_key_secret_label(peer_relation, charm)
    if label == SIGNING_KEY_SECRET_LABEL and signing_key == get_signing_key_secret_content(
        peer_relation, charm
    ):
        logger.info("Received signing key but there is no change, skipping")
        return
    if charm.unit.is_leader():
        secret = charm.app.add_secret(
            {"secret-signing-key": signing_key}, label=SIGNING_KEY_SECRET_LABEL
        )
        peer_relation.data[charm.app].update({"secret-signing-id": typing.cast(str, secret.id)})
