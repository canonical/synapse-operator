# Contributing

This document explains the processes and practices recommended for contributing
enhancements to the Synapse operator.

## Overview

- Generally, before developing enhancements to this charm, you should consider
[opening an issue](https://github.com/canonical/synapse-operator/issues)
explaining your use case.
- If you would like to chat with us about your use-cases or proposed
implementation, you can reach us at [Canonical Matrix public channel](https://matrix.to/#/#charmhub-charmdev:ubuntu.com)
or [Discourse](https://discourse.charmhub.io/).
- Familiarizing yourself with the [Juju documentation](https://documentation.ubuntu.com/juju/3.6/howto/manage-charms/)
  will help you a lot when working on new features or bug fixes.
- All enhancements require review before being merged. Code review typically
examines
  - code quality
  - test coverage
  - user experience for Juju operators of this charm.
- Once your pull request is approved, we squash and merge your pull request branch onto
  the `main` branch. This creates a linear Git commit history.
- For further information on contributing, please refer to our
  [Contributing Guide](https://github.com/canonical/is-charms-contributing-guide).

## Code of conduct

When contributing, you must abide by the
[Ubuntu Code of Conduct](https://ubuntu.com/community/ethos/code-of-conduct).

## Changelog

Please ensure that any new feature, fix, or significant change is documented by
adding an entry to the [CHANGELOG.md](docs/changelog.md) file. Use the date of the
contribution as the header for new entries.

To learn more about changelog best practices, visit [Keep a Changelog](https://keepachangelog.com/).

## Submissions

If you want to address an issue or a bug in this project,
notify in advance the people involved to avoid confusion;
also, reference the issue or bug number when you submit the changes.

- [Fork](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/working-with-forks/about-forks)
  our [GitHub repository](link to GitHub repository)
  and add the changes to your fork, properly structuring your commits,
  providing detailed commit messages and signing your commits.
- Make sure the updated project builds and runs without warnings or errors;
  this includes linting, documentation, code and tests.
- Submit the changes as a
  [pull request (PR)](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-a-pull-request-from-a-fork).

Your changes will be reviewed in due time; if approved, they will be eventually merged.

### AI

You are free to use any tools you want while preparing your contribution, including
AI, provided that you do so lawfully and ethically.

Avoid using AI to complete issues tagged with the "good first issues" label. The
purpose of these issues is to provide newcomers with opportunities to contribute
to our projects and gain coding skills. Using AI to complete these tasks
undermines their purpose.

We have created instructions and tools that you can provide AI while preparing your contribution: [`copilot-collections`](https://github.com/canonical/copilot-collections)

While it isn't necessary to use `copilot-collections` while preparing your
contribution, these files contain details about our quality standards and
practices that will help the AI avoid common pitfalls when interacting with
our projects. By using these tools, you can avoid longer review times and nitpicks.

If you choose to use AI, please disclose this information to us by indicating
AI usage in the PR description (for instance, marking the checklist item about
AI usage). You don't need to go into explicit details about how and where you used AI.

Avoid submitting contributions that you don't fully understand.
You are responsible for the entire contribution, including the AI-assisted portions.
You must be willing to engage in discussion and respond to any questions, comments,
or suggestions we may have. 

### Signing commits

To improve contribution tracking,
we use the [Canonical contributor license agreement](https://assets.ubuntu.com/v1/ff2478d1-Canonical-HA-CLA-ANY-I_v1.2.pdf)
(CLA) as a legal sign-off, and we require all commits to have verified signatures.

#### Canonical contributor agreement

Canonical welcomes contributions to the Synapse operator. Please check out our
[contributor agreement](https://ubuntu.com/legal/contributors) if you're interested in contributing to the solution.

The CLA sign-off is simple line at the
end of the commit message certifying that you wrote it
or have the right to commit it as an open-source contribution.

#### Verified signatures on commits

All commits in a pull request must have cryptographic (verified) signatures.
To add signatures on your commits, follow the
[GitHub documentation](https://docs.github.com/en/authentication/managing-commit-signature-verification/signing-commits).

## Developing

To contribute to this charm, start with a working Juju/Charmcraft/Rockcraft setup:
[Set up your deployment - local testing and development](https://documentation.ubuntu.com/juju/3.6/howto/manage-your-juju-deployment/set-up-your-juju-deployment-local-testing-and-development/).

This guide documents workflow for `tox`, `charmcraft`, `rockcraft`, and `juju` commands.

## Developer environment

The code for this charm can be downloaded as follows:

```
git clone https://github.com/canonical/synapse-operator
```

Use tox-managed environments:

```bash
tox --notest -e unit
source .tox/unit/bin/activate
```

Or create an integration-focused development environment:

```bash
tox devenv -e integration
source venv/bin/activate
```

## Testing

Note that the [Synapse](synapse_rock/rockcraft.yaml) image need to be built and
pushed to MicroK8s for the tests to run. It should be tagged as
`localhost:32000/synapse:latest`so that Kubernetes knows how to pull them
from the MicroK8s repository. Note that the MicroK8s registry needs to be
enabled using `microk8s enable registry`. More details regarding the OCI image
below. The following commands can then be used to run the tests:

* `tox`: Runs all of the basic checks (`lint`, `unit`, `static`, and `coverage-report`).
* `tox -e fmt`: Runs formatting using `black` and `isort`.
* `tox -e lint`: Runs a range of static code analysis to check the code.
* `tox -e static`: Runs other checks such as `bandit` for security issues.
* `tox -e unit`: Runs the unit tests.
* `tox -e integration`: Runs the integration tests.

Available environments include:

```bash
tox -a
```

### Integration tests

#### Required integration inputs

Integration tests require a charm file and image unless you use `--use-existing`:

- CLI args:
  - `--charm-file`
  - `--synapse-image`
- Env alternatives (one-to-one mapping):
  - `CHARM_FILE`
  - `ROCK_IMAGE`

#### Full integration run (fresh deploy by tests)

```bash
tox -e integration -- \
  --charm-file="${CHARM_FILE}" \
  --synapse-image="${ROCK_IMAGE}"
```

#### Run a specific test (or subset)

```bash
tox -e integration -- \
  --charm-file="${CHARM_FILE}" \
  --synapse-image="${ROCK_IMAGE}" \
  -k "test_synapse_is_up"
```

#### Same run using env vars instead of explicit args

```bash
export CHARM_FILE="${CHARM_FILE}"
export ROCK_IMAGE="${ROCK_IMAGE}"
tox -e integration -- -k "test_synapse_is_up"
```

#### S3 integration tests (Localstack)

For S3-related tests, pass a Localstack host/IP (without `:4566`):

```bash
tox -e integration -- \
  --charm-file="${CHARM_FILE}" \
  --synapse-image="${ROCK_IMAGE}" \
  --localstack-address=127.0.0.1
```

Equivalent env var:

```bash
export LOCALSTACK_ADDRESS=127.0.0.1
tox -e integration -- \
  --charm-file="${CHARM_FILE}" \
  --synapse-image="${ROCK_IMAGE}"
```

#### `--use-existing` behavior

`--use-existing` tells test fixtures to reuse applications already present in the selected model instead of deploying Synapse/PostgreSQL from scratch.

```bash
tox -e integration -- --use-existing
```

When using `--use-existing`, ensure the model already contains the expected apps (notably `synapse`, and typically `postgresql-k8s` for DB-backed tests).  
If required apps are missing, tests that rely on them will fail.

## Build artifacts manually

### Build charm

Build the charm in this git repository using:

```bash
charmcraft pack --bases-index=0
CHARM_FILE="$(ls -1t ./*.charm | head -n1)"
echo "$CHARM_FILE"
```

For the integration tests (and also to deploy the charm locally), the synapse
image is required in the MicroK8s registry. To enable it:

```bash
microk8s enable registry
```

The following commands import the images in the Docker daemon and push them into
the registry:

```bash
cd [project_dir]/synapse_rock && rockcraft pack
skopeo --insecure-policy copy --dest-tls-verify=false oci-archive:synapse_1.0_amd64.rock docker://localhost:32000/synapse:latest
```

### Build and publish the ROCK image (for local MicroK8s)

```bash
microk8s enable registry

cd synapse_rock
rockcraft pack
cd ..

ROCK_FILE="$(ls -1t synapse_rock/*.rock | head -n1)"
ROCK_IMAGE="localhost:32000/synapse:latest"
SKOPEO_BIN="$(command -v skopeo || command -v rockcraft.skopeo)"

"$SKOPEO_BIN" --insecure-policy copy --dest-tls-verify=false \
  "oci-archive:${ROCK_FILE}" "docker://${ROCK_IMAGE}"
```

### Deploy

```bash
# Create a model
juju add-model synapse-dev
# Enable DEBUG logging
juju model-config logging-config="<root>=INFO;unit=DEBUG"
# Deploy the charm (assuming you're on amd64)
juju deploy ./synapse_ubuntu-22.04-amd64.charm \
  --resource synapse-image=localhost:32000/synapse:latest
```

Optional common follow-up:

```bash
juju config -m synapse-dev synapse server_name=my.synapse.local
```

### Configure `server_name`

Synapse requires a `server_name` to be set before starting. Note that this cannot
be changed later.

The following command will configure the `server_name` mychat.test.com:

```bash
juju configure synapse server_name=mychat.test.com
```

Read more about `server_name` in [Configuring Synapse](https://matrix-org.github.io/synapse/latest/usage/configuration/config_documentation.html#server_name).

