# Contributing

To contribute to this charm, start with a working Juju/Charmcraft/Rockcraft setup:
<https://juju.is/docs/sdk/dev-setup>.

This guide documents workflow for `tox`, `charmcraft`, `rockcraft`, and `juju` commands.

## Developer environment

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

## Build artifacts manually

### Build the charm

```bash
charmcraft pack --bases-index=0
CHARM_FILE="$(ls -1t ./*.charm | head -n1)"
echo "$CHARM_FILE"
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

## Run tox environments

Available environments include:

```bash
tox -a
```

Common commands:

```bash
tox -e fmt          # format with isort/black
tox -e lint         # style + static checks
tox -e unit         # unit tests + coverage report
tox -e static       # bandit
tox -e src-docs     # regenerate src docs
```

## Integration tests

### Required integration inputs

Integration tests require a charm file and image unless you use `--use-existing`:

- CLI args:
  - `--charm-file`
  - `--synapse-image`
- Env alternatives (one-to-one mapping):
  - `CHARM_FILE`
  - `ROCK_IMAGE`

### Full integration run (fresh deploy by tests)

```bash
tox -e integration -- \
  --charm-file="${CHARM_FILE}" \
  --synapse-image="${ROCK_IMAGE}"
```

### Run a specific test (or subset)

```bash
tox -e integration -- \
  --charm-file="${CHARM_FILE}" \
  --synapse-image="${ROCK_IMAGE}" \
  -k "test_synapse_is_up"
```

### Same run using env vars instead of explicit args

```bash
export CHARM_FILE="${CHARM_FILE}"
export ROCK_IMAGE="${ROCK_IMAGE}"
tox -e integration -- -k "test_synapse_is_up"
```

### S3 integration tests (Localstack)

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

### `--use-existing` behavior

`--use-existing` tells test fixtures to reuse applications already present in the selected model instead of deploying Synapse/PostgreSQL from scratch.

```bash
tox -e integration -- --use-existing
```

When using `--use-existing`, ensure the model already contains the expected apps (notably `synapse`, and typically `postgresql-k8s` for DB-backed tests).  
If required apps are missing, tests that rely on them will fail.

## Deploy locally with Juju

```bash
JUJU_MODEL_NAME="synapse-dev"
juju add-model "${JUJU_MODEL_NAME}"
juju model-config -m "${JUJU_MODEL_NAME}" logging-config="<root>=INFO;unit=DEBUG"

juju deploy -m "${JUJU_MODEL_NAME}" "${CHARM_FILE}" \
  --resource synapse-image="${ROCK_IMAGE}"
```

Optional common follow-up:

```bash
juju config -m "${JUJU_MODEL_NAME}" synapse server_name=my.synapse.local
```

## Optional pre-commit hook for src docs

```bash
echo -e "tox -e src-docs\ngit add src-docs\n" > .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```
