# Make Workflow Examples

All examples are intended to demonstrate generic usage patterns through overrides.

## 1) Discover targets

```bash
make help
```

## 2) Build and publish artifacts

```bash
make build
make publish
```

## 3) Lint and unit test

```bash
make lint
make unit
```

Project opts out of docs checks:

```bash
LINT_TARGETS="tox-lint" make lint
```

## 4) Integration: run only a focused subset

Example using suite-specific pytest options through `TOX_INTEGRATION_ARGS`:

```bash
TOX_INTEGRATION_ARGS="--charm-file=./my-charm_1.2.3_ubuntu-22.04_amd64.charm --synapse-image=localhost:32000/my-charm:1.2.3-abcd123 -k test_active" make tox-integration
```

Minimal smoke pattern used during validation:

```bash
TOX_INTEGRATION_ARGS="--charm-file=./<artifact>.charm --synapse-image=<registry>/<image>:<tag> -k test_synapse_is_up" make integration
```

## 5) Deploy in a specific model

```bash
make setup-juju-model JUJU_MODEL_NAME=dev-alice
make deploy JUJU_MODEL_NAME=dev-alice
```

## 6) Hook-based project customization

In root `Makefile`:

```make
deploy-charm-pre:
    @echo "prepare dependencies"

deploy-charm-post:
    @echo "configure relations and wait logic"
```

Then run:

```bash
make deploy
```

## 7) Override registry tooling/backend

Use explicit `skopeo` and custom registry precheck target:

```bash
make publish-rock SKOPEO_CMD=skopeo REGISTRY_CHECK_TARGET=check-microk8s-registry
```

Use a different container CLI for force publish cleanup:

```bash
make publish-rock-force CONTAINER_CLI="nerdctl -n k8s.io"
```

## 8) Override tagging/versioning

```bash
make build-charm CHARM_VERSION=rev123-custom
make build-rock ROCK_IMAGE_TAG=1.2.3-dev
```

## 9) Reuse pattern for wrapper CLIs

Wrapper CLIs should call make targets and pass configuration via env/args, for example:

```bash
TOX_INTEGRATION_ARGS="-k test_active" make tox-integration
JUJU_MODEL_NAME=ci-model make setup-juju-model
JUJU_MODEL_NAME=ci-model make deploy
```

This keeps the shared makefiles reusable while allowing project-specific behavior externally.
