# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Synapse charm unit tests."""

from secrets import token_hex
from unittest.mock import MagicMock

import pytest
from ops import testing
from pytest import MonkeyPatch

import backup
import pebble
import synapse
from charm import SynapseCharm


def test_moderation_enabled(monkeypatch: pytest.MonkeyPatch, base_state, matrix_auth_secret):
    """
    arrange: start the charm with all integrations and commands mocked.  If
        secret not found, moderation token is None.
    act: trigger config-changed event.
    assert: The moderation token is available and extracted from the secret.
    """
    mock_reconcile = MagicMock()
    monkeypatch.setattr(SynapseCharm, "reconcile", mock_reconcile)
    monkeypatch.setattr(SynapseCharm, "_set_workload_version", MagicMock())
    ctx = testing.Context(SynapseCharm)
    state = testing.State(**base_state)
    ctx.run(ctx.on.config_changed(), state)
    assert mock_reconcile.called
    args, _ = mock_reconcile.call_args
    assert args[0].moderation_token is None

    base_state["secrets"] = [matrix_auth_secret]
    state = testing.State(**base_state)
    ctx.run(ctx.on.config_changed(), state)

    assert mock_reconcile.called
    args, _ = mock_reconcile.call_args
    assert args[0].moderation_token == matrix_auth_secret.tracked_content["matrix-access-token"]


def test_create_backup_correct_enable_media_sync_cleanup(
    monkeypatch: pytest.MonkeyPatch, base_state, s3_media_relation, s3_backup_relation
):
    """
    arrange: start the Synapse charm. Integrate with s3-integrator.
        Mock can_use_bucket and create_backup.
    act: Run the backup action.
    assert: Backup should end correctly, returning correct and the backup name.
    """
    monkeypatch.setattr(backup.S3Client, "can_use_bucket", MagicMock(return_value=True))
    create_backup = MagicMock()
    monkeypatch.setattr(backup, "create_backup", create_backup)
    run_media_sync_cleanup_mock = MagicMock()
    monkeypatch.setattr(synapse, "run_media_sync_cleanup", run_media_sync_cleanup_mock)
    ctx = testing.Context(SynapseCharm)
    base_state["config"]["enable_media_sync_cleanup"] = True
    base_state["config"]["backup_passphrase"] = token_hex(16)
    base_state["relations"].extend([s3_media_relation, s3_backup_relation])
    state = testing.State(**base_state)

    ctx.run(ctx.on.action("create-backup"), state)

    create_backup.assert_called_once()
    assert "backup-id" in ctx.action_results
    assert ctx.action_results["result"] == "correct"
    assert ctx.action_results["media-sync-cleanup-result"] == "correct"
    run_media_sync_cleanup_mock.assert_called_once()


def test_config_changed_multiple_units_with_redis(
    multiple_units_base_state: dict, monkeypatch: MonkeyPatch, mas_context_secret
):
    """
    arrange: prepare synapse state.
    act: run config_changed.
    assert: instance_map_config is correct.
    """
    multiple_units_base_state["secrets"] = [mas_context_secret]
    state = testing.State(**multiple_units_base_state)
    context = testing.Context(
        charm_type=SynapseCharm,
    )
    monkeypatch.setattr(SynapseCharm, "_set_workload_version", MagicMock())
    monkeypatch.setattr(pebble, "reconcile", MagicMock())
    monkeypatch.setattr(
        SynapseCharm, "get_signing_key", MagicMock(return_value="mock_signing_key")
    )
    monkeypatch.setattr(
        SynapseCharm, "get_macaroon_key", MagicMock(return_value="mock_macaroon_key")
    )

    with context(context.on.config_changed(), state) as manager:
        out = manager.run()
        assert manager.charm.build_charm_state().instance_map_config == {
            "federationsender1": {"host": "synapse-0.synapse-endpoints", "port": 8034},
            "main": {"host": "synapse-0.synapse-endpoints", "port": 8035},
            "worker1": {"host": "synapse-1.synapse-endpoints", "port": 8034},
            "worker2": {"host": "synapse-2.synapse-endpoints", "port": 8034},
        }
        assert out.unit_status == testing.ActiveStatus()


def test_config_changed_workers_ignore_list(
    multiple_units_base_state: dict, monkeypatch: MonkeyPatch
):
    """
    arrange: prepare synapse state and set workers_ignore_list.
    act: run config_changed.
    assert: instance_map_config is correct without worker in workers_ignore_list.
    """
    multiple_units_base_state["config"]["workers_ignore_list"] = "worker1"
    state = testing.State(**multiple_units_base_state)
    context = testing.Context(
        charm_type=SynapseCharm,
    )
    monkeypatch.setattr(SynapseCharm, "_set_workload_version", MagicMock())
    monkeypatch.setattr(pebble, "reconcile", MagicMock())
    monkeypatch.setattr(
        SynapseCharm, "get_signing_key", MagicMock(return_value="mock_signing_key")
    )
    monkeypatch.setattr(
        SynapseCharm, "get_macaroon_key", MagicMock(return_value="mock_macaroon_key")
    )

    with context(context.on.config_changed(), state) as manager:
        out = manager.run()
        assert manager.charm.build_charm_state().instance_map_config == {
            "federationsender1": {"host": "synapse-0.synapse-endpoints", "port": 8034},
            "main": {"host": "synapse-0.synapse-endpoints", "port": 8035},
            "worker2": {"host": "synapse-2.synapse-endpoints", "port": 8034},
        }
        assert out.unit_status == testing.ActiveStatus()
