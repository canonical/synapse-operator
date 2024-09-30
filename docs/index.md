# Synapse Operator

A Juju charm deploying and managing [Synapse](https://github.com/matrix-org/synapse) on Kubernetes. Synapse is a drop in replacement for other chat servers like Mattermost and Slack.

This charm simplifies initial deployment and "day N" operations of Synapse on Kubernetes, such as integration with SSO, access to S3 for redundant file storage and more. It allows for deployment on
many different Kubernetes platforms, from [MicroK8s](https://microk8s.io) to [Charmed Kubernetes](https://ubuntu.com/kubernetes) to public cloud Kubernetes offerings.

As such, the charm makes it easy for those looking to take control of their own Chat server whilst keeping operations simple, and gives them the freedom to deploy on the Kubernetes platform of their choice.

For DevOps or SRE teams this charm will make operating Synapse simple and straightforward through Juju's clean interface. It will allow easy deployment into multiple environments for testing of changes.

## In this documentation

| | |
|--|--|
|  [Tutorials](https://charmhub.io/synapse/docs/tutorial-getting-started)</br>  Get started - a hands-on introduction to using the charm for new users </br> |  [How-to guides](https://charmhub.io/synapse/docs/how-to-configure-smtp) </br> Step-by-step guides covering key operations and common tasks |
| [Reference](https://charmhub.io/synapse/docs/reference-actions) </br> Technical information - specifications, APIs, architecture | [Explanation](https://charmhub.io/synapse/docs/explanation-charm-architecture) </br> Concepts - discussion and clarification of key topics  |

## Contributing to this documentation

Documentation is an important part of this project, and we take the same open-source approach to the documentation as the code. As such, we welcome community contributions, suggestions and constructive feedback on our documentation. Our documentation is hosted on the [Charmhub forum](https://discourse.charmhub.io/) to enable easy collaboration. Please use the “Help us improve this documentation” links on each documentation page to either directly change something you see that’s wrong, or ask a question, or make a suggestion about a potential change via the comments section.

If there’s a particular area of documentation that you’d like to see that’s missing, please [file a bug](https://github.com/canonical/synapse-operator/issues).

## Project and community

Synapse is an open-source project that welcomes community contributions, suggestions, fixes and constructive feedback.

* [Read our Code of Conduct](https://ubuntu.com/community/code-of-conduct)
* [Join the Discourse forum](https://discourse.charmhub.io/tag/synapse)
* [Discuss on the Matrix chat service](https://matrix.to/#/#charmhub-charmdev:ubuntu.com)
* Contribute and report bugs to [the Synapse operator](https://github.com/canonical/synapse-operator)
* Check the [release notes](https://github.com/canonical/synapse-operator/releases)

# Contents

1. [Tutorial](tutorial)
  1. [Getting Started](tutorial/getting-started.md)
1. [How to](how-to)
  1. [Configure SMTP](how-to/configure-smtp.md)
  2. [Contribute](how-to/contribute.md)
  3. [Backup and Restore](how-to/backup-and-restore.md)
1. [Reference](reference)
  1. [Actions](reference/actions.md)
  2. [Integrations](reference/integrations.md)
1. [Explanation](explanation)
  1. [Charm architecture](explanation/charm-architecture.md)
