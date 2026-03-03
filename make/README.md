# Generic Make Workflow (`make/`)

This directory contains a reusable, modular Make-based workflow intended to be used as the foundation for a generic workflow CLI.

## Design goals

- Keep **project-specific logic out** of shared makefiles.
- Keep orchestration in one place (`common.mk`).
- Expose behavior through **environment variables**, **target args**, and **hooks**.
- Make targets composable and override-friendly for wrapper CLIs.

## File map

- `common.mk`: shared defaults/derived variables, includes modules, top-level orchestration targets.
- `rock.mk`: ROCK build/publish logic.
- `charm.mk`: charm build/deploy logic.
- `juju.mk`: Juju model setup and deploy hook extension points.
- `tox.mk`: tox environment runner targets.
- `docs.mk`: docs tooling targets (`vale`, `lychee`).
- `help.mk`: output helpers and `make help`.

## Configuration model

### 1) Required project-level variables (set in root `Makefile`)

- `CHARM_NAME`
- `ROCK_NAME`
- `OCI_RESOURCE_NAME`

Typical optional project overrides:

- `ROCK_DIR` (default in common: `rock`)
- `LINT_TARGETS` (default: `tox-lint docs-check`)

Example project `Makefile`:

```make
CHARM_NAME        := my-charm
ROCK_NAME         := my-charm
OCI_RESOURCE_NAME := my-image
ROCK_DIR          ?= rock
LINT_TARGETS      := tox-lint

deploy-charm-post:
    @echo "project-specific post deploy"

MAKE_DIR := make
include $(MAKE_DIR)/common.mk
```

### 2) Shared defaults and derived values (`common.mk`)

Defaults:

- `CONTAINER_REGISTRY ?= localhost:32000`
- `ROCK_PLATFORM ?= amd64`
- `CHARM_VERSION ?= $(shell git describe --tags --always --dirty)`
- `CHARM_PLATFORM ?= amd64`
- `CHARM_BASE_INDEX ?= 0`

Derived values include:

- `ROCK_IMAGE`, `ROCK_DYNAMIC_ARTIFACT`, `ROCK_IMAGE_TAG`
- `CHARM_DYNAMIC_ARTIFACT`, `JUJU_DEPLOY_BASE`, base/channel strings

`yq` is validated once in `common.mk` (`HAS_YQ`), then reused everywhere.

## Top-level targets (`common.mk`)

- `build`: `build-rock` + `build-charm`
- `publish`: `publish-rock`
- `deploy`: `deploy-charm` (includes pre/post hooks)
- `clean`: `clean-rock` + `clean-charm` + `clean-docs`
- `lint`: `$(LINT_TARGETS)`
- `unit`: `tox-unit`
- `integration`: `build-charm` + `publish-rock` + `tox-integration`

## Module interfaces and extension points

### ROCK (`rock.mk`)

Important override points:

- `SKOPEO_CMD ?= ...` (auto-detects `skopeo`, falls back to `rockcraft.skopeo`)
- `SKOPEO_ARGS ?= --insecure-policy copy --dest-tls-verify=false`
- `K8S_BACKEND ?= microk8s`
- `CONTAINER_CLI ?= $(K8S_BACKEND) ctr`
- `REGISTRY_CHECK_TARGET ?= check-microk8s-registry`

Validation targets:

- `.check-rockcraft`
- `.check-skopeo`

### Charm (`charm.mk`)

- Build: `build-charm`
- Deploy: `deploy-charm` (depends on `publish-rock` + hooks)
- Validation target: `.check-charmcraft`

### Juju (`juju.mk`)

- `setup-juju-model` checks existence via:
  - `juju show-model $(JUJU_MODEL_NAME) || juju add-model $(JUJU_MODEL_NAME)`
- Hook targets (default no-op, meant for override):
  - `deploy-charm-pre`
  - `deploy-charm-post`

### Tox (`tox.mk`)

- `tox-lint`, `tox-unit`, `tox-integration`
- Generic argument pass-through variables:
  - `TOX_LINT_ARGS`
  - `TOX_UNIT_ARGS`
  - `TOX_INTEGRATION_ARGS`
- Generic env for integration runs:
  - `CHARM_FILE`, `ROCK_IMAGE`, `OCI_RESOURCE_NAME`, `JUJU_DEPLOY_BASE`

### Docs (`docs.mk`)

- `docs-check`, `vale`, `lychee`, `clean-docs`
- If a project is not configured for docs tooling, set `LINT_TARGETS := tox-lint` in root `Makefile`.

## Genericity contract (for Phase 2 consumers)

Shared makefiles should remain generic by following these rules:

1. Project-specific names/resources stay in root `Makefile` variables.
2. Project-specific behavior uses hook overrides (`deploy-charm-pre/post`) or external scripts called by those hooks.
3. Test selection and suite-specific flags are passed via `TOX_*_ARGS`, not hardcoded in shared modules.
4. Backend/tooling assumptions are configurable via variables (`SKOPEO_CMD`, `K8S_BACKEND`, `CONTAINER_CLI`, `REGISTRY_CHECK_TARGET`, etc.).

For concrete commands, see `make/EXAMPLES.md`.
