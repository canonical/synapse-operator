# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for the Valkey integration and for choosing between Valkey and Redis."""

import dataclasses
import json
import typing
from unittest.mock import MagicMock

import ops
import pytest
import yaml
from ops import testing
from pytest import MonkeyPatch

import pebble
import signing_key
from charm import SynapseCharm

VALKEY_HOST = "valkey-primary.testing.svc.cluster.local"
VALKEY_USERNAME = "relation-7-0123456789abcdef"
VALKEY_PASSWORD = "sEcReTpAsSwOrDfOrVaLkEy0123456789"  # nosec
REQUEST_ID = "0123456789abcdef"
REQUEST = {"resource": "*", "request-id": REQUEST_ID, "salt": "abcdefghijklmnop"}
REDIS_SECTION = {"enabled": True, "host": "redis-k8s-primary.local", "port": 1010}
VALKEY_SECTION = {
    "enabled": True,
    "host": VALKEY_HOST,
    "port": 6379,
    "username": VALKEY_USERNAME,
    "password": VALKEY_PASSWORD,
}


def make_valkey(
    endpoints: typing.Optional[str] = f"{VALKEY_HOST}:6379",
    credentials: typing.Optional[dict] = None,
    tls: str = "false",
    respond: bool = True,
) -> tuple[testing.Relation, list[testing.Secret]]:
    """Create a Valkey relation as Charmed Valkey fills it, with its secrets.

    Args:
        endpoints: the endpoints field of the response, None to leave it out.
        credentials: the content of the user secret, None for a username and a password,
            an empty dictionary to leave the secret out of the response.
        tls: the tls field of the TLS secret.
        respond: False for a relation that Valkey hasn't answered yet.

    Returns:
        The relation and the secrets that it refers to.
    """
    if not respond:
        return testing.Relation(endpoint="valkey", interface="valkey_client"), []
    if credentials is None:
        credentials = {"username": VALKEY_USERNAME, "password": VALKEY_PASSWORD}
    tls_secret = testing.Secret(tracked_content={"tls": tls})
    secrets = [tls_secret]
    response = {**REQUEST, "secret-tls": tls_secret.id, "mode": "sentinel", "version": "9.0.4"}
    if endpoints is not None:
        response["endpoints"] = endpoints
    if credentials:
        user_secret = testing.Secret(tracked_content=credentials)
        secrets.append(user_secret)
        response["secret-user"] = user_secret.id
    relation = testing.Relation(
        endpoint="valkey",
        interface="valkey_client",
        remote_app_name="valkey",
        remote_app_data={
            "version": "v1",
            "requests": json.dumps([response]),
            "data": json.dumps({REQUEST_ID: REQUEST}),
        },
    )
    return relation, secrets


def run(
    monkeypatch: MonkeyPatch,
    base_state: dict,
    relations: list,
    secrets: typing.Iterable[testing.Secret] = (),
    event: typing.Optional[typing.Callable] = None,
    units: int = 3,
) -> tuple[testing.Context, testing.State]:
    """Run one event with the given relations and return the context and the resulting state.

    Args:
        monkeypatch: the pytest monkeypatch fixture.
        base_state: the state with the Synapse container.
        relations: the relations to add to the state.
        secrets: the secrets that the relations refer to.
        event: a function that takes the context and returns the event, config-changed if None.
        units: the number of planned units.

    Returns:
        The context and the state after the event.
    """
    monkeypatch.setattr(signing_key, "is_secret_container_equal", MagicMock(return_value=True))
    monkeypatch.setattr(signing_key, "get_signing_key_secret", MagicMock())
    monkeypatch.setattr(signing_key, "write_to_secret", MagicMock())
    monkeypatch.setattr(signing_key, "write_to_container", MagicMock())
    base_state["planned_units"] = units
    base_state["leader"] = False
    base_state["relations"] = relations
    base_state["secrets"] = list(secrets)
    context = testing.Context(charm_type=SynapseCharm)
    out = context.run(
        event(context) if event else context.on.config_changed(), testing.State(**base_state)
    )
    return context, out


def redis_section(context: testing.Context, state: testing.State) -> typing.Optional[dict]:
    """Get the redis section of the Synapse configuration in the container.

    Args:
        context: the context that the event ran in.
        state: the state after the event.

    Returns:
        The redis section, or None if the configuration has none.
    """
    file = state.get_container("synapse").get_filesystem(context) / "data" / "homeserver.yaml"
    return yaml.safe_load(file.read_text()).get("redis")


def test_valkey_only(base_state: dict, postgresql_relation, peers_relation, monkeypatch):
    """
    arrange: three units, a complete Valkey relation and no Redis relation.
    act: run config_changed.
    assert: Synapse is configured for Valkey with the username and password, the unit is active.
    """
    valkey, secrets = make_valkey()

    context, out = run(
        monkeypatch, base_state, [postgresql_relation, peers_relation, valkey], secrets
    )

    assert redis_section(context, out) == VALKEY_SECTION
    assert out.unit_status == testing.ActiveStatus()


def test_valkey_wins_over_redis(
    base_state: dict, postgresql_relation, redis_relation, peers_relation, monkeypatch
):
    """
    arrange: three units, a complete Valkey relation and a Redis relation.
    act: run config_changed.
    assert: Synapse is configured for Valkey and the status says that Redis is unused.
    """
    valkey, secrets = make_valkey()

    context, out = run(
        monkeypatch,
        base_state,
        [postgresql_relation, redis_relation, peers_relation, valkey],
        secrets,
    )

    assert redis_section(context, out) == VALKEY_SECTION
    assert out.unit_status == testing.ActiveStatus(
        "Using Valkey. The redis integration is no longer used"
    )


@pytest.mark.parametrize(
    "valkey_arguments, message",
    [
        pytest.param({"respond": False}, "Waiting for Valkey", id="no response yet"),
        pytest.param({"endpoints": None}, "Waiting for Valkey", id="no endpoint"),
        pytest.param({"endpoints": ""}, "Waiting for Valkey", id="empty endpoint"),
        pytest.param({"endpoints": "valkey-primary"}, "Waiting for Valkey", id="no port"),
        pytest.param({"endpoints": "valkey:port"}, "Waiting for Valkey", id="port not a number"),
        pytest.param({"endpoints": ":6379"}, "Waiting for Valkey", id="no host"),
        pytest.param({"credentials": {}}, "Waiting for Valkey", id="no user secret"),
        pytest.param(
            {"credentials": {"username": VALKEY_USERNAME}}, "Waiting for Valkey", id="no password"
        ),
        pytest.param(
            {"credentials": {"password": VALKEY_PASSWORD}}, "Waiting for Valkey", id="no username"
        ),
        pytest.param({"tls": "true"}, "Valkey client TLS is not supported", id="client TLS"),
    ],
)
def test_valkey_not_usable_falls_back_to_redis(
    valkey_arguments: dict,
    message: str,
    base_state: dict,
    postgresql_relation,
    redis_relation,
    peers_relation,
    monkeypatch,
):
    """
    arrange: three units, a Redis relation and a Valkey relation that can't be used.
    act: run config_changed.
    assert: Synapse is configured for Redis, without credentials, and the status says why.
    """
    valkey, secrets = make_valkey(**valkey_arguments)

    context, out = run(
        monkeypatch,
        base_state,
        [postgresql_relation, redis_relation, peers_relation, valkey],
        secrets,
    )

    assert redis_section(context, out) == REDIS_SECTION
    assert out.unit_status == testing.ActiveStatus(f"Using Redis. {message}")


@pytest.mark.parametrize(
    "valkey_arguments, status",
    [
        pytest.param(
            {"respond": False}, testing.WaitingStatus("Waiting for Valkey"), id="no response yet"
        ),
        pytest.param(
            {"credentials": {}}, testing.WaitingStatus("Waiting for Valkey"), id="no user secret"
        ),
        pytest.param(
            {"tls": "true"},
            testing.BlockedStatus("Valkey client TLS is not supported"),
            id="client TLS",
        ),
    ],
)
def test_valkey_not_usable_without_redis_leaves_synapse_alone(
    valkey_arguments: dict,
    status: ops.StatusBase,
    base_state: dict,
    postgresql_relation,
    peers_relation,
    monkeypatch,
):
    """
    arrange: three units, no Redis relation and a Valkey relation that can't be used.
    act: run config_changed.
    assert: the workload isn't reconfigured and the status says why.
    """
    valkey, secrets = make_valkey(**valkey_arguments)
    reconcile_mock = MagicMock()
    monkeypatch.setattr(pebble, "reconcile", reconcile_mock)

    _, out = run(monkeypatch, base_state, [postgresql_relation, peers_relation, valkey], secrets)

    reconcile_mock.assert_not_called()
    assert out.unit_status == status


def test_valkey_unreadable_secret_falls_back_to_redis(
    base_state: dict, postgresql_relation, redis_relation, peers_relation, monkeypatch
):
    """
    arrange: three units, a Redis relation and a Valkey relation whose secret isn't granted yet.
    act: run config_changed.
    assert: Synapse is configured for Redis and the status says that it waits for Valkey.
    """
    valkey, _ = make_valkey()

    context, out = run(
        monkeypatch, base_state, [postgresql_relation, redis_relation, peers_relation, valkey]
    )

    assert redis_section(context, out) == REDIS_SECTION
    assert out.unit_status == testing.ActiveStatus("Using Redis. Waiting for Valkey")


@pytest.mark.parametrize(
    "remote_app_data",
    [
        pytest.param({"version": "v1", "requests": "{not json"}, id="requests not JSON"),
        pytest.param({"version": "v1", "requests": '{"resource": "*"}'}, id="requests not a list"),
        pytest.param({"version": "v9", "requests": "[]"}, id="unknown version"),
        pytest.param(
            {
                "version": "v1",
                "requests": json.dumps([{**REQUEST, "secret-user": "not-a-secret"}]),
            },
            id="secret field not a secret URI",
        ),
    ],
)
def test_valkey_invalid_data_falls_back_to_redis(
    remote_app_data: dict,
    base_state: dict,
    postgresql_relation,
    redis_relation,
    peers_relation,
    monkeypatch,
):
    """
    arrange: three units, a Redis relation and a Valkey relation with data that can't be parsed.
    act: run config_changed.
    assert: the charm doesn't fail, and Synapse is configured for Redis.
    """
    valkey = testing.Relation(
        endpoint="valkey", interface="valkey_client", remote_app_data=remote_app_data
    )

    context, out = run(
        monkeypatch, base_state, [postgresql_relation, redis_relation, peers_relation, valkey]
    )

    assert redis_section(context, out) == REDIS_SECTION
    assert out.unit_status == testing.ActiveStatus("Using Redis. Waiting for Valkey")


def test_valkey_first_of_several_endpoints(
    base_state: dict, postgresql_relation, peers_relation, monkeypatch
):
    """
    arrange: three units and a Valkey relation that lists two endpoints.
    act: run config_changed.
    assert: Synapse is configured for the first endpoint.
    """
    valkey, secrets = make_valkey(endpoints="10.1.0.5:6380, 10.1.0.6:6380")

    context, out = run(
        monkeypatch, base_state, [postgresql_relation, peers_relation, valkey], secrets
    )

    assert redis_section(context, out) == {**VALKEY_SECTION, "host": "10.1.0.5", "port": 6380}


def test_valkey_single_unit(base_state: dict, postgresql_relation, monkeypatch):
    """
    arrange: one unit with a complete Valkey relation.
    act: run config_changed.
    assert: Synapse is configured for Valkey.
    """
    valkey, secrets = make_valkey()

    context, out = run(monkeypatch, base_state, [postgresql_relation, valkey], secrets, units=1)

    assert redis_section(context, out) == VALKEY_SECTION
    assert out.unit_status == testing.ActiveStatus()


def test_single_unit_valkey_not_ready(base_state: dict, postgresql_relation, monkeypatch):
    """
    arrange: one unit with a Valkey relation that isn't answered yet and no Redis relation.
    act: run config_changed.
    assert: Synapse runs without a cache and the status says that it waits for Valkey.
    """
    valkey, _ = make_valkey(respond=False)

    context, out = run(monkeypatch, base_state, [postgresql_relation, valkey], units=1)

    assert redis_section(context, out) is None
    assert out.unit_status == testing.ActiveStatus("Waiting for Valkey")


def test_valkey_relation_broken_goes_back_to_redis(
    base_state: dict, postgresql_relation, redis_relation, peers_relation, monkeypatch
):
    """
    arrange: three units on Valkey, with a Redis relation.
    act: remove the Valkey relation.
    assert: Synapse is configured for Redis again, with no credentials left behind.
    """
    valkey, secrets = make_valkey()

    context, out = run(
        monkeypatch,
        base_state,
        [postgresql_relation, redis_relation, peers_relation, valkey],
        secrets,
        event=lambda context: context.on.relation_broken(valkey),
    )

    assert redis_section(context, out) == REDIS_SECTION
    assert out.unit_status == testing.ActiveStatus()


def test_valkey_relation_broken_without_redis(
    base_state: dict, postgresql_relation, peers_relation, monkeypatch
):
    """
    arrange: three units on Valkey, with no Redis relation.
    act: remove the Valkey relation.
    assert: the workload isn't reconfigured and the unit is blocked.
    """
    valkey, secrets = make_valkey()
    reconcile_mock = MagicMock()
    monkeypatch.setattr(pebble, "reconcile", reconcile_mock)

    _, out = run(
        monkeypatch,
        base_state,
        [postgresql_relation, peers_relation, valkey],
        secrets,
        event=lambda context: context.on.relation_broken(valkey),
    )

    reconcile_mock.assert_not_called()
    assert out.unit_status == testing.BlockedStatus("Valkey or Redis integration is required.")


def test_redis_relation_broken_keeps_valkey(
    base_state: dict, postgresql_relation, redis_relation, peers_relation, monkeypatch
):
    """
    arrange: three units on Valkey, with a Redis relation.
    act: remove the Redis relation.
    assert: Synapse stays configured for Valkey.
    """
    valkey, secrets = make_valkey()

    context, out = run(
        monkeypatch,
        base_state,
        [postgresql_relation, redis_relation, peers_relation, valkey],
        secrets,
        event=lambda context: context.on.relation_broken(redis_relation),
    )

    assert redis_section(context, out) == VALKEY_SECTION


@pytest.mark.parametrize(
    "redis_data, status",
    [
        pytest.param({}, testing.WaitingStatus("Waiting for Redis"), id="empty databag"),
        pytest.param({"port": "6379"}, testing.WaitingStatus("Waiting for Redis"), id="no host"),
        pytest.param(
            {"hostname": "10.1.0.9", "port": "none"},
            testing.WaitingStatus("Waiting for Redis"),
            id="port not a number",
        ),
    ],
)
def test_redis_incomplete_data_isn_t_written(
    redis_data: dict,
    status: ops.StatusBase,
    base_state: dict,
    postgresql_relation,
    peers_relation,
    monkeypatch,
):
    """
    arrange: three units and a Redis relation that has no usable address yet.
    act: run config_changed.
    assert: the workload isn't reconfigured, so no host "None" is written, and the unit waits.
    """
    redis = testing.Relation(
        endpoint="redis", interface="redis", remote_units_data={1: redis_data}
    )
    reconcile_mock = MagicMock()
    monkeypatch.setattr(pebble, "reconcile", reconcile_mock)

    _, out = run(monkeypatch, base_state, [postgresql_relation, peers_relation, redis])

    reconcile_mock.assert_not_called()
    assert out.unit_status == status


def test_redis_only_has_no_credentials(
    base_state: dict, postgresql_relation, redis_relation, peers_relation, monkeypatch
):
    """
    arrange: three units and a Redis relation.
    act: run config_changed.
    assert: Synapse is configured for Redis, without a username or a password.
    """
    context, out = run(
        monkeypatch, base_state, [postgresql_relation, redis_relation, peers_relation]
    )

    assert redis_section(context, out) == REDIS_SECTION
    assert out.unit_status == testing.ActiveStatus()


def test_no_cache_single_unit(base_state: dict, postgresql_relation, monkeypatch):
    """
    arrange: one unit with no Valkey and no Redis relation.
    act: run config_changed.
    assert: Synapse runs without a cache.
    """
    context, out = run(monkeypatch, base_state, [postgresql_relation], units=1)

    assert redis_section(context, out) is None
    assert out.unit_status == testing.ActiveStatus()


@pytest.mark.parametrize(
    "event",
    [
        pytest.param(
            lambda context, relation: context.on.relation_changed(relation), id="changed"
        ),
        pytest.param(lambda context, relation: context.on.relation_broken(relation), id="broken"),
    ],
)
def test_valkey_event_reconciles_once(
    event: typing.Callable,
    base_state: dict,
    postgresql_relation,
    redis_relation,
    peers_relation,
    monkeypatch,
):
    """
    arrange: three units and a complete Valkey relation that the unit hasn't seen before.
    act: run a Valkey relation event.
    assert: the charm reconciles exactly once.
    """
    valkey, secrets = make_valkey()
    reconcile_mock = MagicMock()
    monkeypatch.setattr("charm.SynapseCharm.reconcile", reconcile_mock)

    run(
        monkeypatch,
        base_state,
        [postgresql_relation, redis_relation, peers_relation, valkey],
        secrets,
        event=lambda context: event(context, valkey),
    )

    reconcile_mock.assert_called_once()


@pytest.mark.parametrize(
    "changed_field, value, reconciles",
    [
        pytest.param("sentinel-endpoints", "valkey-1.valkey-endpoints:26379", 0, id="sentinels"),
        pytest.param("version", "9.0.5", 0, id="version"),
        pytest.param("endpoints", f"{VALKEY_HOST}:6380", 1, id="endpoint"),
    ],
)
def test_valkey_change_that_synapse_doesn_t_use_isn_t_reconciled(
    changed_field: str,
    value: str,
    reconciles: int,
    base_state: dict,
    postgresql_relation,
    peers_relation,
    monkeypatch,
):
    """
    arrange: three units on Valkey, and a unit that has already seen the relation data.
    act: change one field of what Valkey publishes and run relation_changed.
    assert: the charm reconciles for the endpoint only, so that a Valkey that scales or is
        refreshed doesn't restart Synapse.
    """
    valkey, secrets = make_valkey()
    context, out = run(
        monkeypatch,
        base_state,
        [postgresql_relation, peers_relation, valkey],
        secrets,
        event=lambda context: context.on.relation_changed(valkey),
    )
    seen = out.get_relation(valkey.id)
    response = json.loads(seen.remote_app_data["requests"])[0]
    response[changed_field] = value
    changed = dataclasses.replace(
        seen, remote_app_data={**seen.remote_app_data, "requests": json.dumps([response])}
    )
    state = dataclasses.replace(
        out, relations=[r for r in out.relations if r.id != valkey.id] + [changed]
    )
    reconcile_mock = MagicMock()
    monkeypatch.setattr("charm.SynapseCharm.reconcile", reconcile_mock)

    context.run(context.on.relation_changed(changed), state)

    assert reconcile_mock.call_count == reconciles


@pytest.mark.parametrize(
    "with_redis, status_before, status_after",
    [
        pytest.param(
            False,
            testing.BlockedStatus("Valkey or Redis integration is required."),
            testing.WaitingStatus("Waiting for Valkey"),
            id="no Redis",
        ),
        pytest.param(
            True,
            testing.ActiveStatus(),
            testing.ActiveStatus("Using Redis. Waiting for Valkey"),
            id="Redis in use",
        ),
    ],
)
def test_valkey_relation_created_updates_status_only(  # pylint: disable=too-many-arguments
    with_redis: bool,
    status_before: ops.StatusBase,
    status_after: ops.StatusBase,
    base_state: dict,
    postgresql_relation,
    redis_relation,
    peers_relation,
    monkeypatch,
):
    """
    arrange: three units and a Valkey relation that Valkey hasn't answered yet.
    act: run the Valkey relation_created event.
    assert: the status says that the unit waits for Valkey, and Synapse isn't reconfigured.
    """
    valkey, _ = make_valkey(respond=False)
    reconcile_mock = MagicMock()
    monkeypatch.setattr("charm.SynapseCharm.reconcile", reconcile_mock)
    base_state["unit_status"] = status_before
    relations = [postgresql_relation, peers_relation, valkey]
    if with_redis:
        relations.append(redis_relation)

    _, out = run(
        monkeypatch,
        base_state,
        relations,
        event=lambda context: context.on.relation_created(valkey),
    )

    reconcile_mock.assert_not_called()
    assert out.unit_status == status_after


def test_valkey_secret_changed_reconciles(
    base_state: dict, postgresql_relation, peers_relation, monkeypatch
):
    """
    arrange: three units on Valkey, and a unit that has registered the relation's secrets.
    act: change the content of the user secret.
    assert: the charm reconciles and writes the new password.
    """
    new_password = "aNeWpAsSwOrDfOrVaLkEy9876543210"  # nosec
    valkey, secrets = make_valkey()
    context, out = run(
        monkeypatch,
        base_state,
        [postgresql_relation, peers_relation, valkey],
        secrets,
        event=lambda context: context.on.relation_changed(valkey),
    )
    assert redis_section(context, out) == VALKEY_SECTION
    user_secret = next(s for s in out.secrets if "username" in s.tracked_content)
    changed = testing.Secret(
        id=user_secret.id,
        label=user_secret.label,
        tracked_content=user_secret.tracked_content,
        latest_content={"username": VALKEY_USERNAME, "password": new_password},
    )
    state = testing.State(
        leader=False,
        planned_units=3,
        config=out.config,
        containers=out.containers,
        relations=out.relations,
        secrets=[changed] + [s for s in out.secrets if s.id != user_secret.id],
    )

    out = context.run(context.on.secret_changed(changed), state)

    assert redis_section(context, out) == {**VALKEY_SECTION, "password": new_password}


def test_valkey_password_isn_t_logged(
    base_state: dict, postgresql_relation, redis_relation, peers_relation, monkeypatch
):
    """
    arrange: three units on Redis and a complete Valkey relation that the unit hasn't seen.
    act: run the Valkey relation-changed event, which reconfigures Synapse for Valkey.
    assert: the password is in the configuration and in no log line, at any level.
    """
    valkey, secrets = make_valkey()

    context, out = run(
        monkeypatch,
        base_state,
        [postgresql_relation, redis_relation, peers_relation, valkey],
        secrets,
        event=lambda context: context.on.relation_changed(valkey),
    )

    assert redis_section(context, out) == VALKEY_SECTION
    assert context.juju_log, "no log lines were captured"
    assert not [line for line in context.juju_log if VALKEY_PASSWORD in line.message]
    assert any("The changed keys are" in line.message for line in context.juju_log)
