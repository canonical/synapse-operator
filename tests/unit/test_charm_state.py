# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Synapse charm state unit tests."""

# Disable attribute-defined-outside-init as this would imply many unnecessary init methods.
# pylint: disable=attribute-defined-outside-init,duplicate-code

import ops
import pytest
from ops.testing import ActionFailed, Harness

from state.charm_state import (
    CharmBaseWithState,
    CharmConfigInvalidError,
    CharmState,
    SynapseConfig,
    validate_charm_state,
)


class SimpleCharm(CharmBaseWithState):
    """Simple charm that builds a charm_state."""

    def build_charm_state(self) -> CharmState:
        """Build charm state.

        Returns:
            A valid charm state
        """
        synapse_config = SynapseConfig(
            server_name="example.com", public_baseurl="https://example.com"
        )  # type: ignore[call-arg]
        return CharmState(
            synapse_config=synapse_config,
            datasource=None,
            smtp_config=None,
            media_config=None,
            redis_config=None,
            instance_map_config=None,
            registration_secrets=None,
        )

    def reconcile(self, charm_state) -> None:
        """Reconcile configuration.

        Args:
            charm_state: The charm state.
        """


def test_validate_charm_state_correct() -> None:
    """
    arrange: Create a charm that gets charm_state on start and stores it
        in an attribute of the class.
    act: Emit install event.
    assert: Charmed should not be blocked. CharmState is stored in the attribute
        of the charm.
    """

    class FakeCharm(SimpleCharm):
        """Fake charm with on_start handler."""

        @validate_charm_state
        def on_start(self, _: ops.HookEvent, charm_state: CharmState):
            """Event handler for on_start.

            Args:
                charm_state: Injected CharmState
            """
            self.charm_state = charm_state

    harness = Harness(FakeCharm)
    harness.begin()
    charm = harness.charm
    charm.framework.observe(charm.on.install, charm.on_start)

    charm.on.install.emit()

    assert harness.model.unit.status != ops.BlockedStatus()
    assert isinstance(charm.charm_state, CharmState)


def test_validate_charm_state_in_observer_correct() -> None:
    """
    arrange: Create a charm and an observer that gets charm_state on start and stores it
        in an attribute of the class. This observer follows the convention of having
        the _charm attribute pointing to the charm.
    act: Emit install event.
    assert: Charmed should not be blocked. CharmState is stored in the attribute
        of the observer.
    """

    class Observer(ops.Object):
        """Fake observer with on_start."""

        def __init__(self, charm: CharmBaseWithState):
            """Init method.

            Args:
                 charm: Charm.
            """
            super().__init__(charm, "some-observer")
            self._charm = charm

        def get_charm(self) -> CharmBaseWithState:
            """Get the charm that can build a state.

            Returns:
                The current charm.
            """
            return self._charm

        @validate_charm_state
        def on_start(self, _: ops.HookEvent, charm_state: CharmState):
            """Event handler for on_start.

            Args:
                charm_state: Injected CharmState
            """
            self.charm_state = charm_state

    harness = Harness(SimpleCharm)
    harness.begin()
    charm = harness.charm
    observer = Observer(charm)
    charm.framework.observe(charm.on.install, observer.on_start)

    charm.on.install.emit()

    assert harness.model.unit.status != ops.BlockedStatus()
    assert isinstance(observer.charm_state, CharmState)


def test_validate_charm_state_hook_failed() -> None:
    """
    arrange: Create a charm and that gets charm_state injected on start and stores
       it in an attribute. Raise when trying to get the state with CharmConfigInvalidError.
    act: Emit install event.
    assert: Charmed should be blocked. CharmState is stored in the attribute
        of the observer as the handler was not called..
    """

    class FakeCharm(SimpleCharm):
        """Fake observer with on_start."""

        def build_charm_state(self) -> CharmState:
            """Build charm state.

            Raises:
                CharmConfigInvalidError: always
            """
            raise CharmConfigInvalidError("Invalid configuration")

        @validate_charm_state
        def on_start(self, _: ops.HookEvent, charm_state: CharmState):
            """Event handler for on_start.

            Args:
                charm_state: Injected CharmState
            """
            self.charm_state = charm_state

    harness = Harness(FakeCharm)
    harness.begin()
    charm = harness.charm
    charm.framework.observe(charm.on.install, charm.on_start)
    charm.on.install.emit()

    assert harness.model.unit.status == ops.BlockedStatus("Invalid configuration")
    assert not hasattr(charm, "charm_state")


def test_validate_charm_state_action_failed() -> None:
    """
    arrange: Create a charm with an action "create-backup" that stores the charm_state
        in an attribute of the class, and that raises when trying to get the
        charm_state and the create_backup action observer.
    act: Run action create-backup
    assert: Action should fail with error invalid configuration. No charm_state attribute exists.
    """

    class FakeCharm(SimpleCharm):
        """Fake observer with on_create_backup."""

        def build_charm_state(self) -> CharmState:
            """Build charm state.

            Raises:
                CharmConfigInvalidError: always
            """
            raise CharmConfigInvalidError("Invalid configuration")

        @validate_charm_state
        def on_create_backup_action(self, _: ops.ActionEvent, charm_state: CharmState):
            """Action handler for create-backup action.

            Args:
                charm_state: Injected CharmState
            """
            self.charm_state = charm_state

    harness = Harness(FakeCharm)
    harness.begin()
    charm = harness.charm
    # Very low level. If a best approach is found, replace it.
    charm.meta.actions["create-backup"] = ops.ActionMeta("create-backup")
    charm.on.define_event("create_backup_action", ops.ActionEvent)
    charm.framework.observe(charm.on.create_backup_action, charm.on_create_backup_action)

    with pytest.raises(ActionFailed) as err:
        harness.run_action("create-backup")
    assert "Invalid configuration" in str(err.value.message)
    assert not hasattr(charm, "charm_state")
