---
myst:
  html_meta:
    "description lang=en": "Learn how to deploy, configure and operate the Synapse charm using Juju."
---

# Synapse charm

A Juju charm deploying and managing [Synapse](https://github.com/matrix-org/synapse) on Kubernetes. Synapse is a drop-in replacement for other chat servers like Mattermost and Slack.

This charm simplifies initial deployment and "day N" operations of Synapse on Kubernetes, such as integration with SSO, access to S3 for redundant file storage and more. It allows for deployment on many different Kubernetes platforms, from [MicroK8s](https://microk8s.io) to [Charmed Kubernetes](https://ubuntu.com/kubernetes) to public cloud Kubernetes offerings.

For DevOps or SRE teams this charm will make operating Synapse simple and straightforward through Juju's clean interface. It will allow easy deployment into multiple environments for testing of changes.

## In this documentation

| | |
|--|--|
| {ref}`Tutorials <tutorial_index>` </br> Get started - a hands-on introduction to using the charm for new users | {ref}`How-to guides <how_to_index>` </br> Step-by-step guides covering key operations and common tasks |
| {ref}`Reference <reference_index>` </br> Technical information - specifications, APIs, architecture |  |

## Project and community

Synapse is an open-source project that welcomes community contributions, suggestions, fixes and constructive feedback.

- [Read our Code of Conduct](https://ubuntu.com/community/code-of-conduct)
- [Join the Discourse forum](https://discourse.charmhub.io/)
- [Discuss on the Matrix chat service](https://matrix.to/#/#charmhub-charmdev:ubuntu.com)
- [Contribute and report bugs](https://github.com/canonical/synapse-operator/issues)
- Check the [release notes](https://github.com/canonical/synapse-operator/releases)

```{toctree}
:hidden:
tutorial/index
how-to/index
reference/index
changelog
```
