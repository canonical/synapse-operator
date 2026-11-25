# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""An in-memory stand-in for the parts of the Kubernetes API that the charm uses."""

import itertools
import typing

import httpx2
from lightkube.core.exceptions import ApiError
from lightkube.models.meta_v1 import ObjectMeta, OwnerReference, Status
from lightkube.resources.core_v1 import Pod, Service


class FakeKubernetes:
    """The Kubernetes API of one namespace, with the permissions Juju gives a charm.

    A charm may always read pods and Services and patch existing ones. It may create a Service
    only if the application is trusted.

    Attributes:
        STATEFULSET_UID: the UID of the StatefulSet that owns every pod.
        trusted: whether the application is trusted.
        reachable: whether the API server answers.
        server_error: whether the API server answers every request with an error.
        services: the Services in the namespace, by name.
        cluster_ips: the cluster IPs that new Services get, in order.
    """

    STATEFULSET_UID = "d6bae939-f55e-4aa9-a036-dd5b2cb02764"

    def __init__(self) -> None:
        """Start with an untrusted application and no Services."""
        self.trusted = False
        self.reachable = True
        self.server_error = False
        self.services: dict[str, Service] = {}
        self.cluster_ips: typing.Iterator[str] = (
            f"10.152.183.{host}" for host in itertools.count(10)
        )

    def new_client(self, **_kwargs: typing.Any) -> "FakeKubernetes":
        """Stand in for the lightkube Client class.

        Returns:
            This object, which answers the client's calls.
        """
        return self

    def _check_available(self) -> None:
        """Fail the request if the API server is down or broken.

        Raises:
            ConnectError: if the API server doesn't answer.
            ApiError: if the API server answers with an error.
        """
        if not self.reachable:
            raise httpx2.ConnectError("[Errno 111] Connection refused")
        if self.server_error:
            raise ApiError(status=Status(code=500, reason="InternalError", message="etcd is down"))

    def get(
        self, res: type, name: str, *, namespace: typing.Optional[str] = None
    ) -> typing.Union[Pod, Service]:
        """Read a pod or a Service.

        Args:
            res: the kind of resource.
            name: the name of the resource.
            namespace: the namespace of the resource.

        Returns:
            The resource.

        Raises:
            ApiError: if the Service doesn't exist.
        """
        self._check_available()
        if res is Pod:
            return Pod(
                metadata=ObjectMeta(
                    name=name,
                    namespace=namespace,
                    ownerReferences=[
                        OwnerReference(
                            apiVersion="apps/v1",
                            kind="StatefulSet",
                            name=name.rsplit("-", 1)[0],
                            uid=self.STATEFULSET_UID,
                            controller=True,
                            blockOwnerDeletion=True,
                        )
                    ],
                )
            )
        if name not in self.services:
            raise ApiError(
                status=Status(code=404, reason="NotFound", message=f'services "{name}" not found')
            )
        return self.services[name]

    def apply(self, obj: Service, **_kwargs: typing.Any) -> Service:
        """Create a Service, or replace an existing one, keeping its cluster IP.

        Args:
            obj: the Service.

        Returns:
            The Service as stored.

        Raises:
            ApiError: if the Service doesn't exist and the application isn't trusted.
        """
        self._check_available()
        assert obj.metadata and obj.metadata.name and obj.spec
        name = obj.metadata.name
        existing = self.services.get(name)
        if existing is None and not self.trusted:
            raise ApiError(
                status=Status(
                    code=403,
                    reason="Forbidden",
                    message=f'services "{name}" is forbidden: cannot create resource "services"',
                )
            )
        obj.spec.clusterIP = (
            existing.spec.clusterIP if existing and existing.spec else next(self.cluster_ips)
        )
        self.services[name] = obj
        return obj
