# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""The Valkey relation observer."""

import logging
import typing
import warnings

import ops
from ops.framework import Object
from pydantic import ValidationError
from pydantic.warnings import UnsupportedFieldAttributeWarning

from charm_state import CharmBaseWithState, CharmState, inject_charm_state
from charm_types import RedisConfiguration

with warnings.catch_warnings():
    # Importing the library raises this warning, which Juju would log on every hook:
    # https://github.com/canonical/data-platform-charmlibs/issues/21
    warnings.simplefilter("ignore", UnsupportedFieldAttributeWarning)
    from dpcharmlibs.interfaces import (
        RequirerCommonModel,
        ResourceRequirerEventHandler,
        ValkeyResponseModel,
    )

logger = logging.getLogger(__name__)

VALKEY_RELATION_NAME = "valkey"
# Synapse uses two pub/sub channels and one key prefix. Valkey turns the resource into the
# client's key and channel patterns, and refuses to change it on an existing relation, so the
# charm asks for all of them.
VALKEY_RESOURCE = "*"
WAITING_MESSAGE = "Waiting for Valkey"
TLS_NOT_SUPPORTED_MESSAGE = "Valkey client TLS is not supported"


class ValkeyNotUsableError(Exception):
    """The Valkey relation can't be used to configure Synapse.

    Attrs:
        msg: why the relation can't be used, short enough for a unit status.
        needs_operator: True if only the operator can fix it, False if waiting is enough.
    """

    def __init__(self, msg: str, needs_operator: bool = False):
        """Initialize a new instance of the ValkeyNotUsableError exception.

        Args:
            msg: why the relation can't be used, short enough for a unit status.
            needs_operator: True if only the operator can fix it, False if waiting is enough.
        """
        super().__init__(msg)
        self.msg = msg
        self.needs_operator = needs_operator


class ValkeyObserver(Object):
    """The Valkey relation observer."""

    def __init__(self, charm: CharmBaseWithState, relation_name: str = VALKEY_RELATION_NAME):
        """Initialize the observer and register event handlers.

        Args:
            charm: The parent charm to attach the observer to.
            relation_name: The name of the relation to observe.
        """
        super().__init__(charm, f"{relation_name}-observer")
        self._charm = charm
        self._relation_name = relation_name
        self._valkey = ResourceRequirerEventHandler(
            charm,
            relation_name=relation_name,
            requests=[RequirerCommonModel(resource=VALKEY_RESOURCE)],
            response_model=ValkeyResponseModel,
        )
        # The library emits these when the unit first sees the credentials, when the endpoint
        # changes and when a secret changes. It emits nothing for the rest of what Valkey
        # publishes, such as its Sentinel list and its version, which Synapse doesn't use. So a
        # Valkey that scales or is refreshed doesn't make Synapse restart. The library also
        # emits nothing when the relation is removed.
        self.framework.observe(self._valkey.on.resource_created, self._on_valkey_changed)
        self.framework.observe(self._valkey.on.endpoints_changed, self._on_valkey_changed)
        self.framework.observe(self._valkey.on.authentication_updated, self._on_valkey_changed)
        self.framework.observe(charm.on[relation_name].relation_broken, self._on_valkey_changed)

    def get_charm(self) -> CharmBaseWithState:
        """Return the current charm.

        Returns:
           The current charm
        """
        return self._charm

    @inject_charm_state
    def _on_valkey_changed(self, _: ops.EventBase, charm_state: CharmState) -> None:
        """Reconcile after a change in the Valkey relation.

        Args:
            charm_state: The charm state.
        """
        logger.debug("_on_valkey_changed emitting reconcile")
        self.get_charm().reconcile(charm_state)

    def is_related(self) -> bool:
        """Check if there is a Valkey relation.

        A relation that is being removed doesn't count: its data can't be used any more.

        Returns:
            True if the charm is related to Valkey.
        """
        return self._get_relation() is not None

    def _get_relation(self) -> typing.Optional[ops.Relation]:
        """Get the Valkey relation.

        Returns:
            The relation, or None if there is none or it is being removed.
        """
        relation = self.model.get_relation(self._relation_name)
        if relation is None or not relation.active:
            return None
        return relation

    def _get_response(self, relation: ops.Relation) -> typing.Optional[ValkeyResponseModel]:
        """Read what Valkey published in the relation.

        Args:
            relation: the Valkey relation.

        Returns:
            Valkey's response to the charm's request, or None if there is none yet.

        Raises:
            ValkeyNotUsableError: if the response can't be read.
        """
        if relation.app is None:
            return None
        try:
            contract = self._valkey.interface.build_model(relation.id, component=relation.app)
        except ValidationError as exc:
            # The input can hold credentials, so only the failing fields are logged.
            logger.warning("Valkey relation data isn't valid: %s", exc.errors(include_input=False))
            raise ValkeyNotUsableError(WAITING_MESSAGE) from None
        except (ops.SecretNotFoundError, ops.ModelError, ValueError) as exc:
            # The secret is granted after the relation data is written, and removed with it.
            logger.info("Valkey relation data can't be read yet: %s", type(exc).__name__)
            raise ValkeyNotUsableError(WAITING_MESSAGE) from None
        return contract.requests[0] if contract.requests else None

    def get_relation_as_redis_conf(self) -> typing.Optional[RedisConfiguration]:
        """Get the connection details from the Valkey relation.

        Returns:
            The configuration to connect to Valkey, or None if the charm isn't related to it.

        Raises:
            ValkeyNotUsableError: if the relation exists and its data can't be used.
        """
        relation = self._get_relation()
        if relation is None:
            return None
        response = self._get_response(relation)
        if response is None or not response.endpoints:
            raise ValkeyNotUsableError(WAITING_MESSAGE)
        if response.tls:
            raise ValkeyNotUsableError(TLS_NOT_SUPPORTED_MESSAGE, needs_operator=True)
        if not response.username or not response.password:
            raise ValkeyNotUsableError(WAITING_MESSAGE)
        # Valkey on Kubernetes publishes one endpoint, the Service that follows the primary.
        endpoint = response.endpoints.split(",", 1)[0].strip()
        host, separator, port = endpoint.rpartition(":")
        if not separator or not host or not port.isdigit():
            logger.warning("Valkey published an endpoint that isn't host:port: %s", endpoint)
            raise ValkeyNotUsableError(WAITING_MESSAGE)
        return RedisConfiguration(
            host=host.strip("[]"),
            port=int(port),
            username=response.username,
            password=response.password,
        )
