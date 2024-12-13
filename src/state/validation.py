# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""State of the Charm."""
import functools
import logging
import typing
from abc import ABC, abstractmethod

import ops

from state.mas import MASContextNotSetError

from .charm_state import CharmConfigInvalidError, CharmState
from .mas import MASConfiguration, MASDatasourceMissingError

logger = logging.getLogger(__name__)


class CharmBaseWithState(ops.CharmBase, ABC):
    """CharmBase than can build a CharmState."""

    @abstractmethod
    def build_charm_state(self) -> "CharmState":
        """Build charm state."""

    def get_charm(self) -> "CharmBaseWithState":
        """Return the current charm.

        Returns:
           The current charm
        """
        return self

    @abstractmethod
    def reconcile(self, charm_state: "CharmState", mas_configuration: MASConfiguration) -> None:
        """Reconcile Synapse configuration.

        Args:
            charm_state: The charm state.
            mas_configuration: Charm state component to configure MAS.
        """


class HasCharmWithState(typing.Protocol):  # pylint: disable=too-few-public-methods
    """Protocol that defines a class that returns a CharmBaseWithState."""

    def get_charm(self) -> CharmBaseWithState:
        """Get the charm that can build a state."""


C = typing.TypeVar("C", bound=HasCharmWithState)
E = typing.TypeVar("E", bound=ops.EventBase)


def validate_charm_state(  # pylint: disable=protected-access
    method: typing.Callable[[C, E], None]
) -> typing.Callable[[C, E], None]:
    """Create a decorator that injects the argument charm_state to an observer hook.

    If the configuration is invalid, set the charm state to Blocked if it is
    a Hook or the event to failed if it is an Action and do not call the wrapped observer.

    This decorator can be used in a class that observes a hook/action
    and that defines de get_charm function to get a charm that implements
    CharmBaseWithState.

    Because of https://github.com/canonical/operator/issues/1129,
    @functools.wraps cannot be used yet to have a properly created
    decorator.

    Args:
        method: observer method to wrap and inject the charm_state

    Returns:
        the function wrapper
    """

    @functools.wraps(method)
    def wrapper(instance: C, event: E) -> None:
        """Add the charm_state argument to the function.

        If the configuration is invalid, set the charm state to Blocked if it is
        a Hook or the event to failed if it is an Action and do not call the wrapped observer.

        Args:
            instance: the instance of the class with the method to inject the charm state.
            event: the event for the observer

        Returns:
            The value returned from the original function. That is, None.
        """
        charm = instance.get_charm()

        try:
            return method(instance, event)
        except (CharmConfigInvalidError, MASDatasourceMissingError) as exc:
            logger.exception("Error initializing charm state.")
            # There are two main types of events, Hooks and Actions.
            # Each one of them should be treated differently.
            if isinstance(event, ops.charm.ActionEvent):
                event.fail(str(exc))
            else:
                charm.model.unit.status = ops.BlockedStatus(str(exc))
        except MASContextNotSetError as exc:
            logger.exception("MAS context not set by leader.")
            charm.model.unit.status = ops.WaitingStatus(str(exc))

        return None

    return wrapper
