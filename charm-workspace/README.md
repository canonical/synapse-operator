# pfe-workflow CLI Usage

This workspace defines the `pfe-workflow` CLI used to build, test, publish, and deploy the charm.

## 1) Build the CLI

```bash
./bin/vex build charm-workspace/ -o ./pfe-workflow
```

## 2) Discover commands

```bash
./pfe-workflow help
./pfe-workflow test --help
./pfe-workflow test integration --help
```

## 3) Build artifacts

```bash
./pfe-workflow build rock
./pfe-workflow build charm
```

## 4) Run checks

```bash
./pfe-workflow test lint
./pfe-workflow test unit
```

## 5) Integration test patterns

### Fast smoke run (single test)

```bash
./pfe-workflow test integration --filter "test_synapse_is_up"
```

### Full integration run

```bash
./pfe-workflow test integration
```

### Full integration run including S3 cases

```bash
./pfe-workflow test integration --extra-args="--localstack-address=127.0.0.1:4566"
```

## 6) Deploy with an explicit model

```bash
JUJU_MODEL_NAME="synapse-dev-$(date +%s)" ./pfe-workflow deploy
```

## 7) Use a custom env file

`pfe-workflow` loads `charm.env` by default, but you can override it:

```bash
./pfe-workflow --env-file ./charm.env test unit
```
