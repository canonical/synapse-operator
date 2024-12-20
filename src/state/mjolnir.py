# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""State of the Charm."""

import logging
import typing

import ops
from ops.model import SecretNotFoundError
from pydantic import Field
from pydantic.dataclasses import dataclass

from auth.mas import generate_admin_access_token, register_user
from state.charm_state import SynapseConfig
from synapse import SYNAPSE_CONTAINER_NAME, SYNAPSE_PEER_RELATION_NAME

logger = logging.getLogger()

MJOLNIR_CONTEXT_SECRET_LABEL = "mjolnir.context"
MJOLNIR_CONTEXT_KEY_ACCESS_TOKEN = "key-access-token"


class MjolnirNotMainUnitError(Exception):
    """Exception raised when mjolnir configuration state is initialized on a worker unit."""


class CharmContainerNotReadyError(Exception):
    """Exception raised when mjolnir configuration state is initialized on a worker unit."""


@dataclass(frozen=True)
class MjolnirConfiguration:
    """Information needed to configure Mjolnir.

    Attributes:
        user_id: MAS context to render configuration file.
        admin_access_token: The database URI used in MAS config.
        username: Mjolnir username.
    """

    user_id: str = Field(pattern=r"^@.+:.+$")
    admin_access_token: str = Field(pattern=r"^mct_.+$")
    username: str = "moderator"

    @classmethod
    def from_charm(
        cls, charm: ops.CharmBase, synapse_configuration: SynapseConfig
    ) -> "MjolnirConfiguration":
        """State component containing Mjolnir configuration information.

        Args:
            charm: The synapse charm.
            synapse_configuration: The synapse charm configuration.

        Raises:
            CharmContainerNotReadyError: When the charm container is not ready.
            MjolnirNotMainUnitError: When the mjolnir configuration is not initialized on the
            synapese main unit.

        Returns:
            MjolnirConfiguration: The Mjolnir configuration state component.
        """
        container = charm.unit.get_container(SYNAPSE_CONTAINER_NAME)
        if not container.can_connect():
            raise CharmContainerNotReadyError("Charm container not ready.")

        if peer_relation := charm.model.get_relation(SYNAPSE_PEER_RELATION_NAME):
            logger.debug(
                "Peer relation found, checking if is main unit before configuring Mjolnir"
            )
            # The default is charm.unit.name to make tests that use Harness.begin() work.
            # When not using begin_with_initial_hooks, the peer relation data is not created.
            main_unit_id = peer_relation.data[charm.app].get("main_unit_id", charm.unit.name)
            if charm.unit.name != main_unit_id:
                raise MjolnirNotMainUnitError("Not starting mjolnir on worker units.")

        try:
            secret = charm.model.get_secret(label=MJOLNIR_CONTEXT_SECRET_LABEL)
            mjolnir_context = secret.get_content()
            admin_access_token = typing.cast(
                str, mjolnir_context.get(MJOLNIR_CONTEXT_KEY_ACCESS_TOKEN)
            )
        except SecretNotFoundError:
            register_user(container, cls.username, is_admin=True)
            admin_access_token = generate_admin_access_token(container, cls.username)
            mjolnir_context = {MJOLNIR_CONTEXT_KEY_ACCESS_TOKEN: admin_access_token}
            charm.app.add_secret(mjolnir_context, label=MJOLNIR_CONTEXT_SECRET_LABEL)

        return cls(
            user_id=f"@{cls.username}:{synapse_configuration.server_name}",
            admin_access_token=admin_access_token,
        )
