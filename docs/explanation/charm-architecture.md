# Charm architecture

Synapse is a drop in replacement for other chat servers like Mattermost and
Slack. It integrates with [PostgreSQL](https://www.postgresql.org/) as its
database.

The charm design leverages the [sidecar](https://kubernetes.io/blog/2015/06/the-distributed-system-toolkit-patterns/#example-1-sidecar-containers) pattern to allow multiple containers in each pod
with [Pebble](https://juju.is/docs/sdk/pebble) running as the workload
container’s entrypoint.

Pebble is a lightweight, API-driven process supervisor that is responsible for
configuring processes to run in a container and controlling those processes
throughout the workload lifecycle.

Pebble `services` are configured through [layers](https://github.com/canonical/pebble#layer-specification),
and the following containers represent each one a layer forming the effective
Pebble configuration, or `plan`:

1. An [NGINX](https://www.nginx.com/) container, which can be used to
efficiently serve static resources, as well as be the incoming point for all web
traffic to the pod.
2. The [Synapse](https://github.com/matrix-org/synapse) container itself, which
has Synapse installed and configured.

As a result, if you run a `kubectl get pods` on a namespace named for the Juju
model you've deployed the Synapse charm into, you'll see something like the
following:

```bash
NAME                             READY   STATUS    RESTARTS   AGE
synapse-0                         3/3     Running   0         6h4m
```

This shows there are 3 containers - the two named above, as well as a container
for the charm code itself.

All containers will have the command `/charm/bin/pebble`. Pebble is responsible for service management, as explained above.
processes startup as explained above.

## OCI images

We use [Rockcraft](https://canonical-rockcraft.readthedocs-hosted.com/en/latest/)
to build OCI Images for Synapse and NGINX.
The images are defined in [NGINX ROCK](https://github.com/canonical/synapse-operator/tree/main/nginx_rock/)
and [Synapse ROCK](https://github.com/canonical/synapse-operator/tree/main/synapse_rock).
They are published to [Charmhub](https://charmhub.io/), the official repository
of charms.
This is done by publishing a resource to Charmhub as described in the
[Juju SDK How-to guides](https://juju.is/docs/sdk/publishing).

## Containers

Configuration files for the containers can be found in the respective
directories that define the ROCKs, see the section above.

### NGINX

This container is the entry point for all web traffic to the pod (on port
`8080`). Serves static files directly and forwards non-static requests to
the Synapse container (on port `8008`).

NGINX provides static content cache, reverse proxy, and load balancer among 
multiple application servers, as well as other features. It can be used in front of
Synapse server to significantly reduce server and network load.

The workload that this container is running is defined in the [NGINX ROCK](https://github.com/canonical/synapse-operator/tree/main/nginx_rock/).

### Synapse

Synapse is a Python application run by the `start.py` script.

Synapse listens to non-TLS port `8008` serving by default. NGINX can then
forward non-static traffic to it.

The workload that this container is running is defined in the [Synapse ROCK](https://github.com/canonical/synapse-operator/tree/main/synapse_rock).

If Synapse is integrated with PostgreSQL, [Synapse Stats Exporter](https://github.com/canonical/synapse_stats_exporter) will be enabled.
Synapse Stats Exporter listens to non-TLS port `9877` and will be configured as a
target if the charm is integrated with Prometheus. It will provide two metrics: number of rooms and
number of users.

## Integrations

See [Integrations](https://charmhub.io/synapse/docs/reference/integrations).

## Charm code overview

The `src/charm.py` is the default entry point for a charm and has the
`SynapseOperatorCharm` Python class which inherits from the `CharmBase`.

CharmBase is the base class from which all Charms are formed, defined by [Ops](https://juju.is/docs/sdk/ops)
(Python framework for developing charms).

See more information in [Charm](https://juju.is/docs/sdk/constructs#heading--charm).

The `__init__` method guarantees that the charm observes all events relevant to
its operation and handles them.

Take, for example, when a configuration is changed by using the CLI.

1. User runs the command
```bash
juju config synapse server_name=myserver.myserver.com
```
2. A `config-changed` event is emitted
3. Event handlers are defined in the charm's framework observers. An example looks like the following:
```python
self.framework.observe(self.on.config_changed, self._on_config_changed)
4. The method `_on_config_changed` will take the necessary actions. 
The actions include waiting for all the relations to be ready and then configuring
the containers.