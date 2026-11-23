# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""The Kubernetes Service that routes to the main unit."""

import logging

import httpx2
from lightkube.config.kubeconfig import KubeConfig
from lightkube.core.client import Client
from lightkube.core.exceptions import ApiError, ConfigError
from lightkube.models.core_v1 import ServicePort, ServiceSpec
from lightkube.models.meta_v1 import ObjectMeta, OwnerReference
from lightkube.resources.core_v1 import Pod, Service

import synapse
from charm_state import MAIN_UNIT_ID

logger = logging.getLogger(__name__)
# The Kubernetes client logs every request at INFO.
logging.getLogger("httpx2").setLevel(logging.WARNING)

# The ports that NGINX sends requests for the main unit to. The second one is Mjolnir's web API,
# which receives abuse reports. See mjolnir_production.yaml.
PORTS = {"synapse": synapse.SYNAPSE_PORT, "mjolnir": 9999}
FORBIDDEN = 403
NOT_FOUND = 404


class MainServiceError(Exception):
    """The Service couldn't be read or written."""


class MainServiceNotPermittedError(MainServiceError):
    """The charm isn't allowed to create the Service."""


class MainServiceConflictError(MainServiceError):
    """A Service with the same name belongs to something else."""


class MainService:  # pylint: disable=too-few-public-methods
    """The Service that routes to the main unit's pod.

    NGINX on every unit looks up the main unit's address only when it starts. A pod gets a new
    IP when it is replaced, but a Service keeps its cluster IP, and Kubernetes points it at the
    new pod. So NGINX can keep the address it looked up for as long as the Service exists.

    Attributes:
        name: the name of the Service, which is also its DNS name inside the namespace.
    """

    def __init__(self, app_name: str, namespace: str, unit_name: str) -> None:
        """Construct.

        Args:
            app_name: the name of the application.
            namespace: the Kubernetes namespace, which is the name of the model.
            unit_name: the name of this unit.
        """
        self._app_name = app_name
        self._namespace = namespace
        self._pod_name = unit_name.replace("/", "-")
        self.name = f"{app_name}-main"

    def ensure(self) -> str:
        """Create the Service, or put it back as it should be.

        Juju lets every charm read and patch Services, and lets a trusted one create them. So
        creating the Service needs ``juju trust``, and keeping it afterwards doesn't.

        Returns:
            The cluster IP of the Service.

        Raises:
            MainServiceNotPermittedError: if the charm isn't allowed to create the Service.
            MainServiceConflictError: if a Service with the same name belongs to something else.
            MainServiceError: if the Kubernetes API fails in any other way.
        """
        try:
            client = Client(
                config=KubeConfig.from_service_account(),
                namespace=self._namespace,
                field_manager=self._app_name,
                # The API server is inside the cluster, so it is never behind the model's proxy.
                trust_env=False,
            )
            existing = self._get(client)
            if existing is not None and not self._owners(existing):
                raise MainServiceConflictError(
                    f"The Service {self.name} exists and doesn't belong to {self._app_name}"
                )
            applied = client.apply(self._build(self._get_statefulset(client)), force=True)
        except ApiError as exc:
            if exc.status.code == FORBIDDEN:
                raise MainServiceNotPermittedError(exc.status.message) from exc
            raise MainServiceError(exc.status.message) from exc
        except (httpx2.HTTPError, ConfigError) as exc:
            raise MainServiceError(str(exc)) from exc
        cluster_ip = applied.spec.clusterIP if applied.spec else None
        if not cluster_ip:
            raise MainServiceError(f"The Service {self.name} has no cluster IP")
        return cluster_ip

    def _get(self, client: Client) -> Service | None:
        """Get the Service.

        Args:
            client: the Kubernetes client.

        Returns:
            The Service, or None if it doesn't exist.

        Raises:
            ApiError: if the Kubernetes API fails, other than by not finding the Service.
        """
        try:
            return client.get(Service, self.name, namespace=self._namespace)
        except ApiError as exc:
            if exc.status.code == NOT_FOUND:
                return None
            raise

    def _owners(self, resource: Pod | Service) -> list[OwnerReference]:
        """Get the references that say the application's StatefulSet owns a resource.

        Args:
            resource: the pod or the Service.

        Returns:
            The references, which are empty if the StatefulSet doesn't own the resource.
        """
        owners = resource.metadata.ownerReferences if resource.metadata else None
        return [
            owner
            for owner in owners or []
            if owner.kind == "StatefulSet" and owner.name == self._app_name
        ]

    def _get_statefulset(self, client: Client) -> list[OwnerReference]:
        """Get the reference to the application's StatefulSet from this unit's pod.

        A charm that isn't trusted may read its pod, but not the StatefulSet.

        Args:
            client: the Kubernetes client.

        Returns:
            The reference, as a list for the Service's metadata.

        Raises:
            MainServiceError: if the pod doesn't belong to the StatefulSet.
        """
        owners = self._owners(client.get(Pod, self._pod_name, namespace=self._namespace))
        if not owners:
            raise MainServiceError(f"The pod {self._pod_name} has no StatefulSet")
        return owners

    def _build(self, owners: list[OwnerReference]) -> Service:
        """Build the Service as it should be.

        Args:
            owners: the reference to the application's StatefulSet. With it, Kubernetes deletes
                the Service when the application is removed.

        Returns:
            The Service.
        """
        return Service(
            metadata=ObjectMeta(name=self.name, namespace=self._namespace, ownerReferences=owners),
            spec=ServiceSpec(
                type="ClusterIP",
                # Kubernetes gives every pod of a StatefulSet this label, and the main unit is
                # always unit 0, so nothing has to label the pod again after it is replaced.
                selector={
                    "app.kubernetes.io/name": self._app_name,
                    "statefulset.kubernetes.io/pod-name": f"{self._app_name}-{MAIN_UNIT_ID}",
                },
                # There is one pod behind the Service and no other to send requests to, so
                # readiness has nothing to choose between. This matches the pod address that
                # NGINX used before, which Juju also publishes for pods that aren't ready.
                publishNotReadyAddresses=True,
                ports=[
                    ServicePort(name=name, port=port, targetPort=port, protocol="TCP")
                    for name, port in PORTS.items()
                ],
            ),
        )
