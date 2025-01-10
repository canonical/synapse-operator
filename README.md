[![CharmHub Badge](https://charmhub.io/synapse/badge.svg)](https://charmhub.io/synapse)
[![Publish to edge](https://github.com/canonical/synapse-operator/actions/workflows/publish_charm.yaml/badge.svg)](https://github.com/canonical/synapse-operator/actions/workflows/publish_charm.yaml)
[![Promote charm](https://github.com/canonical/synapse-operator/actions/workflows/promote_charm.yaml/badge.svg)](https://github.com/canonical/synapse-operator/actions/workflows/promote_charm.yaml)
[![Discourse Status](https://img.shields.io/discourse/status?server=https%3A%2F%2Fdiscourse.charmhub.io&style=flat&label=CharmHub%20Discourse)](https://discourse.charmhub.io)

# Synapse Operator

A Juju charm deploying and managing Synapse on Kubernetes. Synapse is a drop in
replacement for other chat servers like Mattermost and Slack.

This charm simplifies initial deployment and "day N" operations of Synapse
on Kubernetes, such as integration with SSO, access to S3 for redundant file
storage and more. It allows for deployment on
many different Kubernetes platforms, from [MicroK8s](https://microk8s.io) to
[Charmed Kubernetes](https://ubuntu.com/kubernetes) to public cloud Kubernetes
offerings.

As such, the charm makes it easy for those looking to take control of their own
Chat server whilst keeping operations simple, and gives them the
freedom to deploy on the Kubernetes platform of their choice.

For DevOps or SRE teams this charm will make operating Synapse simple and
straightforward through Juju's clean interface. It will allow easy deployment
into multiple environments for testing of changes.

## Get started

To begin, refer to the [Getting Started](https://charmhub.io/synapse/docs/tutorial-getting-started)
tutorial for step-by-step instructions.

### Basic operations

#### Configure a server name

The configuration `server_name` sets the public-facing domain of the server and
refers to [`server_name`](https://matrix-org.github.io/synapse/latest/usage/configuration/config_documentation.html#server_name) Synapse configuration.

To change it to `tutorial-synapse.juju.local`, for example, run the following
command:

```
juju config synapse server_name=tutorial-synapse.juju.local
```

#### Create a user

The following command creates a local user named `alice`.

```
juju run synapse/0 register-user username=alice password=<secure-password> admin=no
```

#### Promote user to admin

The following command can be used to promote an existing user to admin.

```
juju run synapse/0 promote-user-admin username=alice
```

## Learn more
* [Read more](https://charmhub.io/synapse)
* [Developer documentation](https://element-hq.github.io/synapse/latest/development/contributing_guide.html)
* [Official webpage](https://github.com/element-hq/synapse)
* [Troubleshooting](https://element-hq.github.io/synapse/latest/usage/administration/admin_faq.html)


## Project and community
* [Issues](https://github.com/canonical/synapse-operator/issues)
* [Contributing](https://charmhub.io/synapse/docs/contributing)
* [Matrix](https://matrix.to/#/#charmhub-charmdev:ubuntu.com)
