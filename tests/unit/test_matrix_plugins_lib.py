# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""MatrixAuth library unit tests"""

from secrets import token_hex

import ops
import pytest
from charms.synapse.v0.matrix_auth import (
    MatrixAuthProviderData,
    MatrixAuthProvides,
    MatrixAuthRequestProcessed,
    MatrixAuthRequestReceived,
    MatrixAuthRequirerData,
    MatrixAuthRequires,
)
from ops.testing import Harness

REQUIRER_METADATA = """
name: matrix-auth-consumer
requires:
  matrix-auth:
    interface: matrix-auth
"""

PROVIDER_METADATA = """
name: matrix-auth-producer
provides:
  matrix-auth:
    interface: matrix-auth
"""

SAMPLE_PROVIDER_DATA = {
    "homeserver": "https://example.com",
    "shared_secret_id": "test-secret-id",
}

SAMPLE_REQUIRER_DATA = {
    "registration_secret_id": "test-registration-id",
}


class MatrixAuthRequirerCharm(ops.CharmBase):
    """Class for requirer charm testing."""

    def __init__(self, *args):
        """Initialise the MatrixAuthRequirerCharm class.

        Args:
            args: Arguments to pass to the parent class.
        """
        super().__init__(*args)
        self.matrix_auth = MatrixAuthRequires(self)
        self.events = []
        self.framework.observe(
            self.matrix_auth.on.matrix_auth_request_processed, self._record_event
        )

    def _record_event(self, event: ops.EventBase) -> None:
        """Record the event.

        Args:
            event: The event to record.
        """
        self.events.append(event)


class MatrixAuthProviderCharm(ops.CharmBase):
    """Class for provider charm testing."""

    def __init__(self, *args):
        """Initialise the MatrixAuthProviderCharm class.

        Args:
            args: Arguments to pass to the parent class.
        """
        super().__init__(*args)
        self.matrix_auth = MatrixAuthProvides(self)
        self.events = []
        self.framework.observe(
            self.matrix_auth.on.matrix_auth_request_received, self._record_event
        )

    def _record_event(self, event: ops.EventBase) -> None:
        """Record the event.

        Args:
            event: The event to record.
        """
        self.events.append(event)


# Tests for MatrixAuthRequires


def test_matrix_auth_requirer_does_not_emit_event_when_no_data():
    """
    arrange: set up a charm with no relation data to be populated.
    act: add a matrix-auth relation.
    assert: no events are emitted.
    """
    harness = Harness(MatrixAuthRequirerCharm, meta=REQUIRER_METADATA)
    harness.begin()
    harness.set_leader(True)
    harness.add_relation("matrix-auth", "matrix-auth-provider")
    relation = harness.charm.framework.model.get_relation("matrix-auth", 0)
    harness.charm.on.matrix_auth_relation_changed.emit(relation)
    assert len(harness.charm.events) == 0


@pytest.mark.parametrize("is_leader", [True, False])
def test_matrix_auth_requirer_with_valid_relation_data_emits_event(is_leader, monkeypatch):
    """
    arrange: set up a charm.
    act: add a matrix-auth relation with valid data.
    assert: a MatrixAuthRequestProcessed event containing the relation data is emitted.
    """
    harness = Harness(MatrixAuthRequirerCharm, meta=REQUIRER_METADATA)
    harness.begin()
    harness.set_leader(is_leader)

    # Mock the get_shared_secret method to return a test secret
    def mock_get_shared_secret(*args):  # pylint: disable=unused-argument
        """Mock get_shared_secret method.

        Args:
            args: Arguments passed to the method.

        Returns:
            str: The shared secret.
        """
        return "test-shared-secret"

    monkeypatch.setattr(MatrixAuthProviderData, "get_shared_secret", mock_get_shared_secret)

    harness.add_relation("matrix-auth", "matrix-auth-provider", app_data=SAMPLE_PROVIDER_DATA)

    assert len(harness.charm.events) == 1
    event = harness.charm.events[0]
    assert isinstance(event, MatrixAuthRequestProcessed)

    relation_data = event.get_matrix_auth_provider_relation_data()
    assert relation_data.homeserver == SAMPLE_PROVIDER_DATA["homeserver"]
    assert relation_data.shared_secret.get_secret_value() == "test-shared-secret"


@pytest.mark.parametrize("is_leader", [True, False])
def test_matrix_auth_requirer_with_invalid_relation_data_doesnt_emit_event(is_leader):
    """
    arrange: set up a charm.
    act: add a matrix-auth relation with invalid data.
    assert: a MatrixAuthRequestProcessed event is not emitted.
    """
    invalid_relation_data = {
        "homeserver": "https://example.com",
        # Missing shared_secret_id
    }

    harness = Harness(MatrixAuthRequirerCharm, meta=REQUIRER_METADATA)
    harness.begin()
    harness.set_leader(is_leader)
    harness.add_relation("matrix-auth", "matrix-auth-provider", app_data=invalid_relation_data)

    assert len(harness.charm.events) == 0


def test_matrix_auth_requirer_get_remote_relation_data_without_relation():
    """
    arrange: set up a charm without any matrix-auth relation.
    act: call get_remote_relation_data function.
    assert: get_remote_relation_data should return None.
    """
    harness = Harness(MatrixAuthRequirerCharm, meta=REQUIRER_METADATA)
    harness.begin()
    harness.set_leader(True)
    assert harness.charm.matrix_auth.get_remote_relation_data() is None


def test_matrix_auth_requirer_get_remote_relation_data_with_valid_data(monkeypatch):
    """
    arrange: set up a charm with matrix-auth relation with valid relation data.
    act: call get_remote_relation_data function.
    assert: get_remote_relation_data should return a valid MatrixAuthProviderData object.
    """
    harness = Harness(MatrixAuthRequirerCharm, meta=REQUIRER_METADATA)
    harness.begin()
    harness.set_leader(True)

    # Mock the get_shared_secret method to return a test secret
    def mock_get_shared_secret(*args):  # pylint: disable=unused-argument
        """Mock get_shared_secret method.

        Args:
            args: Arguments passed to the method.

        Returns:
            str: The shared secret.
        """
        return "test-shared-secret"

    monkeypatch.setattr(MatrixAuthProviderData, "get_shared_secret", mock_get_shared_secret)

    harness.add_relation("matrix-auth", "matrix-auth-provider", app_data=SAMPLE_PROVIDER_DATA)

    relation_data = harness.charm.matrix_auth.get_remote_relation_data()
    assert relation_data is not None
    assert relation_data.homeserver == SAMPLE_PROVIDER_DATA["homeserver"]
    assert relation_data.shared_secret.get_secret_value() == "test-shared-secret"


# Tests for MatrixAuthProvides


def test_matrix_auth_provider_does_not_emit_event_when_no_data():
    """
    arrange: set up a charm with no relation data to be populated.
    act: add a matrix-auth relation.
    assert: no events are emitted.
    """
    harness = Harness(MatrixAuthProviderCharm, meta=PROVIDER_METADATA)
    harness.begin()
    harness.set_leader(True)
    harness.add_relation("matrix-auth", "matrix-auth-consumer")
    relation = harness.charm.framework.model.get_relation("matrix-auth", 0)
    harness.charm.on.matrix_auth_relation_changed.emit(relation)
    assert len(harness.charm.events) == 0


@pytest.mark.parametrize("is_leader", [True, False])
def test_matrix_auth_provider_with_valid_relation_data_emits_event(is_leader, monkeypatch):
    """
    arrange: set up a charm.
    act: add a matrix-auth relation with valid data.
    assert: a MatrixAuthRequestReceived event is emitted.
    """
    harness = Harness(MatrixAuthProviderCharm, meta=PROVIDER_METADATA)
    harness.begin()
    harness.set_leader(is_leader)

    # Mock the get_registration method to return a test registration
    def mock_get_registration(*args):  # pylint: disable=unused-argument
        """Mock get_registration method.

        Args:
            args: Arguments passed to the method.

        Returns:
            str: The registration.
        """
        return "test-registration"

    monkeypatch.setattr(MatrixAuthRequirerData, "get_registration", mock_get_registration)

    harness.add_relation("matrix-auth", "matrix-auth-consumer", app_data=SAMPLE_REQUIRER_DATA)

    assert len(harness.charm.events) == 1
    event = harness.charm.events[0]
    assert isinstance(event, MatrixAuthRequestReceived)


@pytest.mark.parametrize("is_leader", [True, False])
def test_matrix_auth_provider_with_invalid_relation_data_doesnt_emit_event(is_leader):
    """
    arrange: set up a charm.
    act: add a matrix-auth relation with invalid data.
    assert: a MatrixAuthRequestReceived event is not emitted.
    """
    invalid_relation_data: dict[str, str] | None = {
        # Missing registration_secret_id
    }

    harness = Harness(MatrixAuthProviderCharm, meta=PROVIDER_METADATA)
    harness.begin()
    harness.set_leader(is_leader)
    harness.add_relation("matrix-auth", "matrix-auth-consumer", app_data=invalid_relation_data)

    assert len(harness.charm.events) == 0


def test_matrix_auth_provider_update_relation_data():
    """
    arrange: set up a charm with a matrix-auth relation.
    act: update the relation data.
    assert: the relation data is updated correctly.
    """
    harness = Harness(MatrixAuthProviderCharm, meta=PROVIDER_METADATA)
    harness.begin()
    harness.set_leader(True)
    rel_id = harness.add_relation("matrix-auth", "matrix-auth-consumer")
    relation = harness.model.get_relation("matrix-auth", rel_id)
    secret = token_hex(16)

    provider_data = MatrixAuthProviderData(
        homeserver="https://example.com",
        shared_secret=secret,
    )

    harness.charm.matrix_auth.update_relation_data(relation, provider_data)

    relation_data = harness.get_relation_data(rel_id, harness.charm.app.name)
    assert relation_data["homeserver"] == "https://example.com"
    assert "shared_secret_id" in relation_data  # The actual ID will be generated


def test_matrix_auth_provider_get_remote_relation_data(monkeypatch):
    """
    arrange: set up a charm with a matrix-auth relation and valid requirer data.
    act: call get_remote_relation_data function.
    assert: get_remote_relation_data returns a valid MatrixAuthRequirerData object.
    """
    harness = Harness(MatrixAuthProviderCharm, meta=PROVIDER_METADATA)
    harness.begin()
    harness.set_leader(True)

    # Mock the get_registration method to return a test registration
    def mock_get_registration(*args):  # pylint: disable=unused-argument
        """Mock get_registration method.

        Args:
            args: Arguments passed to the method.

        Returns:
            str: The registration.
        """
        return "test-registration"

    monkeypatch.setattr(MatrixAuthRequirerData, "get_registration", mock_get_registration)

    harness.add_relation("matrix-auth", "matrix-auth-consumer", app_data=SAMPLE_REQUIRER_DATA)

    relation_data = harness.charm.matrix_auth.get_remote_relation_data()
    assert relation_data is not None
    assert relation_data.registration.get_secret_value() == "test-registration"
