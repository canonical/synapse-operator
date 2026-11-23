# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for the Kubernetes Service that routes to the main unit."""

import typing
from unittest.mock import MagicMock

import pytest
from lightkube.models.core_v1 import ServicePort, ServiceSpec
from lightkube.models.meta_v1 import ObjectMeta
from lightkube.resources.core_v1 import Service
from ops import testing

import macaroon_key
import pebble
import signing_key
from charm import SynapseCharm
from main_service import (
    MainService,
    MainServiceConflictError,
    MainServiceError,
    MainServiceNotPermittedError,
)
from tests.fake_kubernetes import FakeKubernetes

MAIN_POD_SELECTOR = {
    "app.kubernetes.io/name": "synapse",
    "statefulset.kubernetes.io/pod-name": "synapse-0",
}


def main_service() -> MainService:
    """Get the object under test, as the unit synapse/1 would build it.

    Returns:
        The main unit's Service of the application synapse in the namespace testmodel.
    """
    return MainService(app_name="synapse", namespace="testmodel", unit_name="synapse/1")


def other_application_s_service() -> Service:
    """Get a Service with the same name that Juju created for another application.

    Returns:
        The Service of an application called synapse-main.
    """
    return Service(
        metadata=ObjectMeta(
            name="synapse-main",
            namespace="testmodel",
            labels={"app.kubernetes.io/managed-by": "juju"},
        ),
        spec=ServiceSpec(
            clusterIP="10.152.183.200",
            selector={"app.kubernetes.io/name": "synapse-main"},
            ports=[ServicePort(port=65535)],
        ),
    )


def service_spec(kubernetes: FakeKubernetes) -> ServiceSpec:
    """Get the spec of the main unit's Service.

    Args:
        kubernetes: the fake Kubernetes API.

    Returns:
        The spec of the Service as stored.
    """
    spec = kubernetes.services["synapse-main"].spec
    assert spec
    return spec


def test_ensure_selects_only_the_main_pod(kubernetes: FakeKubernetes) -> None:
    """
    arrange: a trusted application without the Service.
    act: ensure the Service.
    assert: the Service routes the ports that NGINX proxies to the main unit's pod only, whether
        or not that pod is ready.
    """
    kubernetes.trusted = True

    main_service().ensure()

    spec = service_spec(kubernetes)
    assert spec.selector == MAIN_POD_SELECTOR
    assert {port.port: port.targetPort for port in spec.ports or []} == {8008: 8008, 9999: 9999}
    assert spec.publishNotReadyAddresses is True


def test_ensure_returns_the_cluster_ip(kubernetes: FakeKubernetes) -> None:
    """
    arrange: a trusted application without the Service.
    act: ensure the Service.
    assert: the cluster IP that Kubernetes gave the Service is returned.
    """
    kubernetes.trusted = True

    assert main_service().ensure() == "10.152.183.10"


def test_ensure_ties_the_service_to_the_statefulset(kubernetes: FakeKubernetes) -> None:
    """
    arrange: a trusted application without the Service.
    act: ensure the Service.
    assert: the StatefulSet owns the Service, so Kubernetes deletes it with the application.
    """
    kubernetes.trusted = True

    main_service().ensure()

    metadata = kubernetes.services["synapse-main"].metadata
    assert metadata
    assert [(owner.kind, owner.name, owner.uid) for owner in metadata.ownerReferences or []] == [
        ("StatefulSet", "synapse", "d6bae939-f55e-4aa9-a036-dd5b2cb02764")
    ]


def test_ensure_corrects_a_changed_service(kubernetes: FakeKubernetes) -> None:
    """
    arrange: a trusted application, ensure the Service, then make it select every pod.
    act: ensure the Service again.
    assert: it selects only the main unit's pod again and keeps its cluster IP.
    """
    kubernetes.trusted = True
    main_service().ensure()
    service_spec(kubernetes).selector = {"app.kubernetes.io/name": "synapse"}

    assert main_service().ensure() == "10.152.183.10"

    assert service_spec(kubernetes).selector == MAIN_POD_SELECTOR


def test_ensure_works_without_trust_once_the_service_exists(kubernetes: FakeKubernetes) -> None:
    """
    arrange: ensure the Service as a trusted application, then remove the trust.
    act: ensure the Service again.
    assert: the cluster IP is returned, because the charm may still read and patch the Service.
    """
    kubernetes.trusted = True
    main_service().ensure()
    kubernetes.trusted = False

    assert main_service().ensure() == "10.152.183.10"


def test_ensure_leaves_another_application_s_service_alone(kubernetes: FakeKubernetes) -> None:
    """
    arrange: a trusted application, and a Service with the same name that the StatefulSet
        doesn't own.
    act: ensure the Service.
    assert: it fails with a conflict and the other Service is unchanged.
    """
    kubernetes.trusted = True
    kubernetes.services["synapse-main"] = other_application_s_service()

    with pytest.raises(MainServiceConflictError):
        main_service().ensure()

    assert kubernetes.services["synapse-main"] == other_application_s_service()


def test_ensure_without_trust_is_not_permitted(kubernetes: FakeKubernetes) -> None:
    """
    arrange: an application that isn't trusted, without the Service.
    act: ensure the Service.
    assert: it fails as not permitted and creates nothing.
    """
    with pytest.raises(MainServiceNotPermittedError):
        main_service().ensure()

    assert not kubernetes.services


def test_ensure_needs_a_pod_of_the_statefulset(kubernetes: FakeKubernetes) -> None:
    """
    arrange: a trusted application, and a unit whose pod belongs to another StatefulSet.
    act: ensure the Service.
    assert: it fails and creates nothing, because a Service without the StatefulSet as its owner
        would never be removed, and would be taken for another application's Service later.
    """
    kubernetes.trusted = True
    service = MainService(app_name="synapse", namespace="testmodel", unit_name="other/1")

    with pytest.raises(MainServiceError):
        service.ensure()

    assert not kubernetes.services


def test_ensure_needs_a_cluster_ip(kubernetes: FakeKubernetes) -> None:
    """
    arrange: a trusted application, and a Kubernetes that gives the Service no cluster IP.
    act: ensure the Service.
    assert: it fails, so the leader never tells the units to use a Service without an address.
    """
    kubernetes.trusted = True
    kubernetes.cluster_ips = iter([""])

    with pytest.raises(MainServiceError):
        main_service().ensure()


@pytest.mark.parametrize(
    "attribute, value",
    [
        pytest.param("reachable", False, id="api-server-down"),
        pytest.param("server_error", True, id="api-server-error"),
    ],
)
def test_ensure_reports_a_kubernetes_failure(
    kubernetes: FakeKubernetes, attribute: str, value: bool
) -> None:
    """
    arrange: a trusted application, and an API server that is down or answers with an error.
    act: ensure the Service.
    assert: it fails with the general error, which doesn't say that the charm lacks permission
        or that the name is taken.
    """
    kubernetes.trusted = True
    setattr(kubernetes, attribute, value)

    with pytest.raises(MainServiceError) as exc_info:
        main_service().ensure()

    assert not isinstance(exc_info.value, (MainServiceNotPermittedError, MainServiceConflictError))


def run_config_changed(  # pylint: disable=too-many-arguments
    base_state: dict,
    monkeypatch: pytest.MonkeyPatch,
    *,
    relations: list,
    peers_relation: testing.PeerRelation,
    leader: bool,
    unit_id: int,
) -> tuple[testing.Context, testing.State, testing.PeerRelation]:
    """Run config-changed, which reconciles, on one unit of three.

    Args:
        base_state: the state with the Synapse container.
        monkeypatch: the pytest monkeypatch fixture.
        relations: the relations other than the peer relation.
        peers_relation: the peer relation.
        leader: whether the unit is the leader.
        unit_id: the number of the unit.

    Returns:
        The context, the state after the event and the peer relation after the event.
    """
    monkeypatch.setattr(signing_key, "is_secret_container_equal", MagicMock(return_value=True))
    monkeypatch.setattr(signing_key, "get_signing_key_secret", MagicMock())
    monkeypatch.setattr(signing_key, "write_to_secret", MagicMock())
    monkeypatch.setattr(signing_key, "write_to_container", MagicMock())
    monkeypatch.setattr(macaroon_key, "write_to_secret", MagicMock())
    monkeypatch.setattr(macaroon_key, "write_to_container", MagicMock())
    monkeypatch.setattr(pebble, "reconcile", MagicMock())
    base_state["planned_units"] = 3
    base_state["leader"] = leader
    base_state["relations"] = [*relations, peers_relation]
    context = testing.Context(charm_type=SynapseCharm, unit_id=unit_id)
    out = context.run(context.on.config_changed(), testing.State(**base_state))
    return context, out, typing.cast(testing.PeerRelation, out.get_relation(peers_relation.id))


def peers(
    app_data: typing.Optional[dict] = None, unit_data: typing.Optional[dict] = None
) -> testing.PeerRelation:
    """Get the peer relation with the given data.

    Args:
        app_data: the application's data.
        unit_data: this unit's data.

    Returns:
        The peer relation.
    """
    return testing.PeerRelation(
        endpoint="synapse-peers",
        interface="synapse-instance",
        local_app_data=app_data or {},
        local_unit_data=unit_data or {},
    )


def nginx_main_location(context: testing.Context, state: testing.State) -> str:
    """Get the NGINX configuration for requests that go to the main unit.

    Args:
        context: the context that the event ran in.
        state: the state after the event.

    Returns:
        The content of the file.
    """
    root = state.get_container("synapse").get_filesystem(context)
    return (root / "etc" / "nginx" / "main_location.conf").read_text(encoding="utf-8")


def test_leader_publishes_the_service_s_cluster_ip(
    base_state: dict,
    postgresql_relation,
    redis_relation,
    kubernetes: FakeKubernetes,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    arrange: a trusted application without the Service.
    act: reconcile on the leader.
    assert: the Service exists and the application's peer data has its cluster IP, which tells
        every unit to use it.
    """
    kubernetes.trusted = True

    _, _, peer = run_config_changed(
        base_state,
        monkeypatch,
        relations=[postgresql_relation, redis_relation],
        peers_relation=peers(),
        leader=True,
        unit_id=1,
    )

    assert service_spec(kubernetes).selector == MAIN_POD_SELECTOR
    assert peer.local_app_data["main-service-ip"] == "10.152.183.10"


def test_leader_without_trust_withdraws_the_service(
    base_state: dict,
    postgresql_relation,
    redis_relation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    arrange: an application that isn't trusted, whose Service is gone, with the cluster IP still
        in the peer data.
    act: reconcile on the leader.
    assert: the cluster IP is removed from the peer data, so the units go back to the main
        unit's pod address.
    """
    _, _, peer = run_config_changed(
        base_state,
        monkeypatch,
        relations=[postgresql_relation, redis_relation],
        peers_relation=peers(app_data={"main-service-ip": "10.152.183.10"}),
        leader=True,
        unit_id=1,
    )

    assert "main-service-ip" not in peer.local_app_data


def test_leader_withdraws_the_service_when_the_name_is_taken(
    base_state: dict,
    postgresql_relation,
    redis_relation,
    kubernetes: FakeKubernetes,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    arrange: a trusted application, another application's Service under the same name, and a
        cluster IP in the peer data.
    act: reconcile on the leader.
    assert: the cluster IP is removed from the peer data, so no unit routes to the other
        application.
    """
    kubernetes.trusted = True
    kubernetes.services["synapse-main"] = other_application_s_service()

    _, _, peer = run_config_changed(
        base_state,
        monkeypatch,
        relations=[postgresql_relation, redis_relation],
        peers_relation=peers(app_data={"main-service-ip": "10.152.183.10"}),
        leader=True,
        unit_id=1,
    )

    assert "main-service-ip" not in peer.local_app_data


def test_leader_keeps_the_service_when_kubernetes_is_unreachable(
    base_state: dict,
    postgresql_relation,
    redis_relation,
    kubernetes: FakeKubernetes,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    arrange: the cluster IP in the peer data, and an API server that doesn't answer.
    act: reconcile on the leader.
    assert: the reconcile succeeds and the cluster IP stays, so a short outage of the API server
        doesn't move every unit off the Service.
    """
    kubernetes.reachable = False

    _, out, peer = run_config_changed(
        base_state,
        monkeypatch,
        relations=[postgresql_relation, redis_relation],
        peers_relation=peers(app_data={"main-service-ip": "10.152.183.10"}),
        leader=True,
        unit_id=1,
    )

    assert peer.local_app_data["main-service-ip"] == "10.152.183.10"
    assert out.unit_status == testing.ActiveStatus()


def test_other_units_leave_the_service_to_the_leader(
    base_state: dict,
    postgresql_relation,
    redis_relation,
    kubernetes: FakeKubernetes,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    arrange: a trusted application without the Service.
    act: reconcile on a unit that isn't the leader.
    assert: no Service is created.
    """
    kubernetes.trusted = True

    run_config_changed(
        base_state,
        monkeypatch,
        relations=[postgresql_relation, redis_relation],
        peers_relation=peers(),
        leader=False,
        unit_id=1,
    )

    assert not kubernetes.services


def test_nginx_proxies_to_the_service(
    base_state: dict,
    postgresql_relation,
    redis_relation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    arrange: the cluster IP in the peer data.
    act: reconcile on a unit that isn't the main unit.
    assert: NGINX sends requests for the main unit to the Service.
    """
    context, out, _ = run_config_changed(
        base_state,
        monkeypatch,
        relations=[postgresql_relation, redis_relation],
        peers_relation=peers(app_data={"main-service-ip": "10.152.183.10"}),
        leader=False,
        unit_id=1,
    )

    assert "proxy_pass http://synapse-main:8008;" in nginx_main_location(context, out)


def test_nginx_proxies_to_the_main_pod_without_the_service(
    base_state: dict,
    postgresql_relation,
    redis_relation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    arrange: no cluster IP in the peer data.
    act: reconcile on a unit that isn't the main unit.
    assert: NGINX sends requests for the main unit to its pod address.
    """
    context, out, _ = run_config_changed(
        base_state,
        monkeypatch,
        relations=[postgresql_relation, redis_relation],
        peers_relation=peers(),
        leader=False,
        unit_id=1,
    )

    assert "proxy_pass http://synapse-0.synapse-endpoints:8008;" in nginx_main_location(
        context, out
    )


def test_main_unit_s_nginx_proxies_to_its_own_pod(
    base_state: dict,
    postgresql_relation,
    redis_relation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    arrange: the cluster IP in the peer data.
    act: reconcile on the main unit.
    assert: its NGINX sends requests to its own pod, not back to itself through the Service.
    """
    context, out, _ = run_config_changed(
        base_state,
        monkeypatch,
        relations=[postgresql_relation, redis_relation],
        peers_relation=peers(app_data={"main-service-ip": "10.152.183.10"}),
        leader=False,
        unit_id=0,
    )

    assert "proxy_pass http://synapse-0.synapse-endpoints:8008;" in nginx_main_location(
        context, out
    )


def test_main_unit_stops_publishing_its_ip_with_the_service(
    base_state: dict,
    postgresql_relation,
    redis_relation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    arrange: the cluster IP in the peer data, and the main unit's IP in its own peer data from
        the time before the Service.
    act: reconcile on the main unit.
    assert: the main unit removes its IP, so the other units no longer restart NGINX when the
        main unit's pod is replaced.
    """
    _, _, peer = run_config_changed(
        base_state,
        monkeypatch,
        relations=[postgresql_relation, redis_relation],
        peers_relation=peers(
            app_data={"main-service-ip": "10.152.183.10"}, unit_data={"main-unit-ip": "10.1.2.3"}
        ),
        leader=False,
        unit_id=0,
    )

    assert "main-unit-ip" not in peer.local_unit_data


def test_main_unit_publishes_its_ip_without_the_service(
    base_state: dict,
    postgresql_relation,
    redis_relation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    arrange: an application that isn't trusted, with a cluster IP left in the peer data.
    act: reconcile on the main unit, which is the leader.
    assert: in the same reconcile, the cluster IP is withdrawn and the main unit publishes its
        IP, so the other units follow it from then on.
    """
    _, _, peer = run_config_changed(
        base_state,
        monkeypatch,
        relations=[postgresql_relation, redis_relation],
        peers_relation=peers(app_data={"main-service-ip": "10.152.183.10"}),
        leader=True,
        unit_id=0,
    )

    assert "main-service-ip" not in peer.local_app_data
    assert peer.local_unit_data["main-unit-ip"] == "192.0.2.0"
