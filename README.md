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

## Learn more
* [Read more](https://charmhub.io/synapse) <!--Link to the charm's official documentation-->

## Project and community
* [Issues](https://github.com/canonical/synapse-operator/issues) <!--Link to GitHub issues (if applicable)-->
* [Contributing](https://charmhub.io/synapse/docs/contributing) <!--Link to any contribution guides--> 
* [Matrix](https://matrix.to/#/#charmhub-charmdev:ubuntu.com) <!--Link to contact info (if applicable), e.g. Matrix channel-->

