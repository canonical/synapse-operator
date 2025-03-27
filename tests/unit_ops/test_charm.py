# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Synapse charm unit tests."""

from unittest.mock import MagicMock

import pytest
from ops import testing

from charm import SynapseCharm


def test_moderation_enabled(monkeypatch: pytest.MonkeyPatch, base_state, matrix_auth_secret):
    """
    arrange: start the charm with all integrations and commands mocked.
    act: trigger config-changed event.
    assert: The moderation token is available and extracted from the secret. If
        secret not found, moderation token is None.
    """
    mock_reconcile = MagicMock()
    monkeypatch.setattr(SynapseCharm, "reconcile", mock_reconcile)
    monkeypatch.setattr(SynapseCharm, "_set_workload_version", MagicMock())
    ctx = testing.Context(SynapseCharm)
    # no secret found
    state = testing.State(**base_state)

    ctx.run(ctx.on.config_changed(), state)

    assert mock_reconcile.called
    args, _ = mock_reconcile.call_args
    assert args[0].moderation_token is None

    # secret found
    base_state["secrets"] = [matrix_auth_secret]
    state = testing.State(**base_state)

    ctx.run(ctx.on.config_changed(), state)

    assert mock_reconcile.called
    args, _ = mock_reconcile.call_args
    assert args[0].moderation_token == matrix_auth_secret.tracked_content["matrix-access-token"]
