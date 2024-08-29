# How to contribute

## Overview

This document explains the processes and practices recommended for contributing
enhancements to the Synapse operator.

- Generally, before developing enhancements to this charm, you should consider
[opening an issue](https://github.com/canonical/synapse-operator/issues)
explaining your use case.
- If you would like to chat with us about your use-cases or proposed
implementation, you can reach us at [Canonical Matrix public channel](https://matrix.to/#/#charmhub-charmdev:ubuntu.com)
or [Discourse](https://discourse.charmhub.io/).
- Familiarising yourself with the [Charmed Operator Framework](https://juju.is/docs/sdk)
library will help you a lot when working on new features or bug fixes.
- All enhancements require review before being merged. Code review typically
examines
  - code quality
  - test coverage
  - user experience for Juju operators of this charm.
- Please help us out in ensuring easy to review branches by rebasing your pull
request branch onto the `main` branch. This also avoids merge commits and
creates a linear Git commit history.
- Please generate src documentation for every commit. See the section below for
more details.

## Developing

The code for this charm can be downloaded as follows:

```
git clone https://github.com/canonical/synapse-operator
```

You can use the environments created by `tox` for development:

```shell
tox --notest -e unit
source .tox/unit/bin/activate
```

### Testing

Note that the [Synapse](synapse_rock/rockcraft.yaml) and [Synapse NGINX](synapse_nginx_rock/rockcraft.yaml)
images need to be built and pushed to microk8s for the tests to run. They should
be tagged as `localhost:32000/synapse:latest` and
`localhost:32000/synapse-nginx:latest` so that Kubernetes knows how to pull them
from the MicroK8s repository. Note that the MicroK8s registry needs to be
enabled using `microk8s enable registry`. More details regarding the OCI images
below. The following commands can then be used to run the tests:

* `tox`: Runs all of the basic checks (`lint`, `unit`, `static`, and `coverage-report`).
* `tox -e fmt`: Runs formatting using `black` and `isort`.
* `tox -e lint`: Runs a range of static code analysis to check the code.
* `tox -e static`: Runs other checks such as `bandit` for security issues.
* `tox -e unit`: Runs the unit tests.
* `tox -e integration`: Runs the integration tests.

### Generating src docs for every commit

Run the following command:

```bash
echo -e "tox -e src-docs\ngit add src-docs\n" >> .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

## Build charm

Build the charm in this git repository using:

```shell
charmcraft pack
```
For the integration tests (and also to deploy the charm locally), the synapse
and synapse-nginx images are required in the microk8s registry. To enable it:

    microk8s enable registry

The following commands import the images in the Docker daemon and push them into
the registry:

    cd [project_dir]/synapse_rock && rockcraft pack
    skopeo --insecure-policy copy --dest-tls-verify=false oci-archive:synapse_1.0_amd64.rock docker://localhost:32000/synapse:latest
    cd [project_dir]/nginx_rock && rockcraft pack
    skopeo --insecure-policy copy --dest-tls-verify=false oci-archive:synapse-nginx_1.0_amd64.rock docker://localhost:32000/synapse-nginx:latest

### Deploy

```bash
# Create a model
juju add-model synapse-dev
# Enable DEBUG logging
juju model-config logging-config="<root>=INFO;unit=DEBUG"
# Deploy the charm (assuming you're on amd64)
juju deploy ./synapse_ubuntu-22.04-amd64.charm \
  --resource synapse-image=localhost:32000/synapse:latest \
  --resource synapse-nginx-image=localhost:32000/synapse-nginx:latest
```

### Configure `server_name`

Synapse requires a `server_name` to be set before starting. Note that this cannot
be changed later so if you want a different server name, will need to run the
action `reset-instance` to re-create everything.

The following command will configure the `server_name` mychat.test.com:

```bash
juju configure synapse server_name=mychat.test.com
```

Read more about `server_name` in [Configuring Synapse](https://matrix-org.github.io/synapse/latest/usage/configuration/config_documentation.html#server_name).

## Canonical Contributor Agreement

Canonical welcomes contributions to the Synapse Operator. Please check out our [contributor agreement](https://ubuntu.com/legal/contributors) if you're interested in contributing to the solution.
