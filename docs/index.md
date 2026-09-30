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

```{list-table}
   :header-rows: 1
   :widths: 15 30

* - 
  - 
* - **Get started**
  - {ref}`Guided tutorial <tutorial_getting_started>`
* - **Deployment**
  - {ref}`Integrate with SMTP <how_to_configure_smtp>` | {ref}`Configurations <reference_configurations>` | {ref}`Actions <reference_actions>`
* - **Operations**
  - {ref}`Back up and restore <how_to_backup_and_restore>` | {ref}`Horizontally scale <how_to_horizontally_scale>`
* - **Integrations**
  - {ref}`Relation endpoints <reference_integrations>`
* - **Design**
  - {ref}`Charm architecture <reference_charm_architecture>`
* - **Security**
  - {ref}`Federation and external access <reference_external_access>`
```

## How this documentation is organized

This documentation uses the
[Diátaxis documentation structure](https://diataxis.fr/).

- The {ref}`Tutorial <tutorial_index>` takes you step-by-step through deploying the Synapse charm for the first time.
- {ref}`How-to guides <how_to_index>` assume basic familiarity with the Synapse charm. They cover key operations and common tasks such as backups, scaling, and SMTP integration.
- {ref}`Reference <reference_index>` provides technical details on actions, configurations, integrations, and charm architecture.
- The {ref}`Changelog <changelog>` holds a record of all notable changes to the charm.

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
