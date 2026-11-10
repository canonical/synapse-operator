# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Tests for when the charm restarts Synapse."""

from unittest.mock import MagicMock

import ops
import pytest
import yaml
from ops.testing import Harness

import pebble
import signing_key
import synapse

from .conftest import TEST_SERVER_NAME

SIGNING_KEY_PATH = f"/data/{TEST_SERVER_NAME}.signing.key"
REGISTRATION_PATH = "/data/appservice-registration-bridge.yaml"
# Like the image's template, this one names files that Synapse reads when it starts.
TEMPLATE = {
    "server_name": TEST_SERVER_NAME,
    "listeners": [{"type": "http", "port": 8008, "bind_addresses": ["::"]}],
    "signing_key_path": SIGNING_KEY_PATH,
    "log_config": "/data/log.config",
    "app_service_config_files": [REGISTRATION_PATH],
}


@pytest.fixture(name="restarts")
def restarts_fixture(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Count Synapse restarts, and still restart it."""
    restart_synapse = MagicMock(side_effect=pebble.restart_synapse)
    monkeypatch.setattr(pebble, "restart_synapse", restart_synapse)
    return restart_synapse


@pytest.fixture(name="started")
def started_fixture(harness: Harness, restarts: MagicMock) -> Harness:
    """Start the charm, then forget the restarts it needed to start."""
    container = harness.model.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)

    def render_template(_argv: list[str]) -> synapse.ExecResult:
        """Render the template as migrate_config does.

        Args:
            _argv: the command.

        Returns:
            A successful result.
        """
        container.push(synapse.SYNAPSE_NEW_CONFIG_PATH, yaml.safe_dump(TEMPLATE), make_dirs=True)
        return synapse.ExecResult(0, "", "")

    # The harness fixture adds register_command_handler.
    harness.register_command_handler(  # type: ignore[attr-defined] # pylint: disable=no-member
        container=container, executable=synapse.SYNAPSE_COMMAND_PATH, handler=render_template
    )
    container.push(REGISTRATION_PATH, "as_token: one", make_dirs=True)
    harness.set_leader(True)
    harness.begin_with_initial_hooks()
    assert restarts.called
    restarts.reset_mock()
    return harness


def _live_config(harness: Harness) -> dict:
    """Read the configuration Synapse uses.

    Args:
        harness: the harness.

    Returns:
        The configuration.
    """
    root = harness.get_filesystem_root(synapse.SYNAPSE_CONTAINER_NAME)
    return yaml.safe_load((root / synapse.SYNAPSE_CONFIG_PATH[1:]).read_text(encoding="utf-8"))


def _new_config_exists(harness: Harness) -> bool:
    """Check if the configuration the charm builds is still on disk.

    Args:
        harness: the harness.

    Returns:
        True if the file exists.
    """
    root = harness.get_filesystem_root(synapse.SYNAPSE_CONTAINER_NAME)
    return (root / synapse.SYNAPSE_NEW_CONFIG_PATH[1:]).exists()


def _reconcile(harness: Harness) -> None:
    """Reconcile without changing anything, as a peer relation change does.

    Args:
        harness: the harness.
    """
    harness.charm.on.config_changed.emit()


def test_no_restart_without_changes(started: Harness, restarts: MagicMock) -> None:
    """
    arrange: start the charm.
    act: reconcile twice without changing anything.
    assert: Synapse isn't restarted, and its configuration is complete and unchanged.
    """
    config_before = _live_config(started)

    _reconcile(started)
    _reconcile(started)

    restarts.assert_not_called()
    assert _live_config(started) == config_before
    assert config_before["public_baseurl"] == f"https://{TEST_SERVER_NAME}"
    assert not _new_config_exists(started)
    assert isinstance(started.model.unit.status, ops.ActiveStatus)


def test_restart_when_a_setting_changes(started: Harness, restarts: MagicMock) -> None:
    """
    arrange: start the charm.
    act: change an option that changes homeserver.yaml.
    assert: Synapse is restarted once with the new setting.
    """
    started.update_config({"block_non_admin_invites": True})

    restarts.assert_called_once()
    assert _live_config(started)["block_non_admin_invites"] is True
    assert not _new_config_exists(started)


def test_unset_setting_is_removed(started: Harness, restarts: MagicMock) -> None:
    """
    arrange: start the charm, then set an option.
    act: unset the option.
    assert: Synapse is restarted once, and the setting is gone from homeserver.yaml.
    """
    started.update_config({"block_non_admin_invites": True})
    restarts.reset_mock()

    started.update_config({"block_non_admin_invites": False})

    restarts.assert_called_once()
    assert "block_non_admin_invites" not in _live_config(started)


def test_removed_relation_settings_are_removed(
    redis_configured: Harness, started: Harness, restarts: MagicMock
) -> None:
    """
    arrange: start the charm with a Redis relation.
    act: remove the relation.
    assert: Synapse is restarted once, and the Redis settings are gone from homeserver.yaml.
    """
    assert redis_configured is started
    assert _live_config(started)["redis"]["host"] == "redis-host"
    relation = started.model.get_relation("redis")
    assert relation

    started.remove_relation(relation.id)

    restarts.assert_called_once()
    assert "redis" not in _live_config(started)


def test_listeners_are_not_duplicated(started: Harness, restarts: MagicMock) -> None:
    """
    arrange: start the charm.
    act: change an option three times.
    assert: Synapse is restarted each time, and each listener port appears once.
    """
    for value in (True, False, True):
        started.update_config({"block_non_admin_invites": value})

    assert restarts.call_count == 3
    ports = [listener["port"] for listener in _live_config(started)["listeners"]]
    assert sorted(ports) == sorted(set(ports))
    assert len(ports) == 3


def test_restart_when_the_environment_changes(started: Harness, restarts: MagicMock) -> None:
    """
    arrange: start the charm.
    act: change report_stats, which only changes Synapse's environment here.
    assert: Synapse is restarted once with the new environment.
    """
    config_before = _live_config(started)

    started.update_config({"report_stats": True})

    restarts.assert_called_once()
    assert _live_config(started) == config_before
    plan = started.get_container_pebble_plan(synapse.SYNAPSE_CONTAINER_NAME)
    environment = plan.services[synapse.SYNAPSE_SERVICE_NAME].environment
    assert environment["SYNAPSE_REPORT_STATS"] == "yes"


def test_restart_when_synapse_is_not_running(started: Harness, restarts: MagicMock) -> None:
    """
    arrange: start the charm, then stop Synapse.
    act: reconcile without changing anything.
    assert: Synapse is restarted once.
    """
    container = started.model.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
    container.stop(synapse.SYNAPSE_SERVICE_NAME)

    _reconcile(started)

    restarts.assert_called_once()
    assert container.get_service(synapse.SYNAPSE_SERVICE_NAME).is_running()


def test_restart_when_the_signing_key_secret_changes(
    started: Harness, restarts: MagicMock
) -> None:
    """
    arrange: start the charm.
    act: change the signing key in its secret, as when a unit started before the leader shared
        its key, then reconcile twice.
    assert: the charm writes the new key and restarts Synapse once.
    """
    peer_relation = started.model.get_relation(synapse.SYNAPSE_PEER_RELATION_NAME)
    assert peer_relation
    secret_id = peer_relation.data[started.charm.app][signing_key.SIGNING_KEY_PEER_ID]
    secret = started.model.get_secret(id=secret_id)
    secret.set_content({signing_key.SIGNING_KEY_SECRET_CONTENT_ID: "ed25519 a_new 0123"})
    # Make the unit see the new revision.
    secret.get_content(refresh=True)

    _reconcile(started)
    _reconcile(started)

    restarts.assert_called_once()
    container = started.model.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
    assert container.pull(SIGNING_KEY_PATH).read() == "ed25519 a_new 0123"


def test_restart_when_an_appservice_registration_changes(
    started: Harness, restarts: MagicMock
) -> None:
    """
    arrange: start the charm.
    act: change an application service registration that homeserver.yaml names, then reconcile
        twice.
    assert: Synapse is restarted once.
    """
    container = started.model.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
    container.push(REGISTRATION_PATH, "as_token: two")

    _reconcile(started)
    _reconcile(started)

    restarts.assert_called_once()


def test_invalid_configuration_is_not_used(started: Harness, restarts: MagicMock) -> None:
    """
    arrange: start the charm, and make the configuration check fail.
    act: change an option, then make the check pass and reconcile.
    assert: the invalid configuration doesn't replace the live one, and the change is applied
        once the check passes.
    """
    container = started.model.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
    config_before = _live_config(started)
    started.register_command_handler(  # type: ignore[attr-defined] # pylint: disable=no-member
        container=container,
        executable="/usr/bin/python3",
        handler=lambda _: synapse.ExecResult(1, "", "invalid"),
    )

    with pytest.raises(pebble.PebbleServiceError):
        started.update_config({"block_non_admin_invites": True})

    restarts.assert_not_called()
    assert _live_config(started) == config_before

    started.register_command_handler(  # type: ignore[attr-defined] # pylint: disable=no-member
        container=container,
        executable="/usr/bin/python3",
        handler=lambda _: synapse.ExecResult(0, "", ""),
    )
    _reconcile(started)

    restarts.assert_called_once()
    assert _live_config(started)["block_non_admin_invites"] is True


def test_failed_restart_is_retried(started: Harness, restarts: MagicMock) -> None:
    """
    arrange: start the charm, and make the next restart fail.
    act: change an option, then reconcile twice.
    assert: the next reconcile restarts Synapse again, and the one after doesn't.
    """
    restart_synapse = restarts.side_effect

    def fail_once(**kwargs) -> None:
        """Fail the first restart.

        Args:
            kwargs: restart_synapse arguments.

        Raises:
            ChangeError: on the first call.
        """
        if restarts.call_count == 1:
            raise ops.pebble.ChangeError("cannot start service", MagicMock())
        restart_synapse(**kwargs)

    restarts.side_effect = fail_once

    with pytest.raises(ops.pebble.ChangeError):
        started.update_config({"block_non_admin_invites": True})
    _reconcile(started)

    assert restarts.call_count == 2
    restarts.reset_mock()
    _reconcile(started)
    restarts.assert_not_called()


def test_check_change_applies_without_restart(started: Harness, restarts: MagicMock) -> None:
    """
    arrange: start the charm.
    act: change the alive check settings.
    assert: the check has the new settings, and Synapse isn't restarted.
    """
    started.update_config({"experimental_alive_check": "1m,3,10s"})

    restarts.assert_not_called()
    plan = started.get_container_pebble_plan(synapse.SYNAPSE_CONTAINER_NAME)
    check = plan.checks[synapse.CHECK_ALIVE_NAME]
    assert (check.period, check.threshold, check.timeout) == ("1m", 3, "10s")


def test_migrate_config_writes_the_new_configuration(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    arrange: start the charm.
    act: run migrate_config.
    assert: the command renders the template to the new configuration, not the live one.
    """
    harness.begin()
    exec_mock = MagicMock(return_value=synapse.ExecResult(0, "", ""))
    monkeypatch.setattr(synapse.workload, "_exec", exec_mock)

    synapse.execute_migrate_config(
        container=harness.model.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME),
        charm_state=harness.charm.build_charm_state(),
    )

    environment = exec_mock.call_args.kwargs["environment"]
    assert environment["SYNAPSE_CONFIG_PATH"] == synapse.SYNAPSE_NEW_CONFIG_PATH
