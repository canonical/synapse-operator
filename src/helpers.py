#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Synapse charm helpers."""


import logging
import typing

import ops

import pebble
import signing_key
import synapse
from charm_state import CharmState

logger = logging.getLogger(__name__)

MAIN_UNIT_ID = 0


def is_mjolnir_enabled(charm: ops.CharmBase, charm_state: CharmState) -> bool:
    """Check if Mjolnir should be enabled.

    Args:
        charm: charm instance.
        charm_state: charm state.

    Return:
        True if is main and config is enabled.
    """
    return is_main(charm) and charm_state.synapse_config.enable_mjolnir


def peer_relation(charm: ops.CharmBase) -> typing.Optional[ops.Relation]:
    """Get peer relation.

    Args:
        charm: charm instance.

    Returns:
        Synapse peer relation.
    """
    peer_relations = charm.model.relations[synapse.SYNAPSE_PEER_RELATION_NAME]
    if not peer_relations:
        return None
    return peer_relations[0]


def is_main(charm: ops.CharmBase) -> bool:
    """Verify if this unit is the main.

    Args:
        charm: charm instance.

    Returns:
        bool: true if is the main unit.
    """
    return f"/{MAIN_UNIT_ID}" in charm.unit.name


def get_unit_address(charm: ops.CharmBase, unit_id: int) -> str:
    """Get unit address.

    Args:
        charm: charm instance.
        unit_id: number as 0 in synapse/0.

    Returns:
        unit address as unit-0.synapse-endpoints.
    """
    return f"{charm.app.name}-{unit_id}.{charm.app.name}-endpoints"


def get_unit_number(charm: ops.CharmBase) -> str:
    """Get unit number.

    Args:
        charm: charm instance.

    Returns:
        unit number as 0 in synapse/0.
    """
    return charm.unit.name.split("/")[1]


def create_instance_map(charm: ops.CharmBase) -> typing.Optional[typing.Dict]:
    """Create instance_map configuration.

    Args:
        charm: charm instance.

    Returns:
        Instance map configuration as a dict or None if there is only one unit.
    """
    planned_units = charm.app.planned_units()
    if planned_units == 1:
        logger.debug("Only one unit is planned; skipping instance_map configuration.")
        return None

    instance_map = {
        "main": {
            "host": get_unit_address(charm, MAIN_UNIT_ID),
            "port": 8035,
        },
        "federationsender1": {
            "host": get_unit_address(charm, MAIN_UNIT_ID),
            "port": 8034,
        },
    }

    for unit_id in range(planned_units):
        if unit_id == MAIN_UNIT_ID:
            continue
        instance_name = f"worker{unit_id}"
        instance_map[instance_name] = {
            "host": get_unit_address(charm, unit_id),
            "port": 8034,
        }

    return instance_map


def configure_and_start_services(
    charm: ops.CharmBase, charm_state: CharmState, container: ops.Container
) -> None:
    """Configure and start pebble layers.

    Args:
        charm: charm instance.
        charm_state: charm state.
        container: charm container.
    """
    signing_key.write_to_container(peer_relation(charm), charm, charm_state, container)
    pebble.reconcile(
        charm_state, container, is_main=is_main(charm), unit_number=get_unit_number(charm)
    )
    pebble.restart_nginx(container, get_unit_address(charm, MAIN_UNIT_ID))
    signing_key.write_to_secret(peer_relation(charm), charm, charm_state, container)
