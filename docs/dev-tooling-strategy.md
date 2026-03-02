# Developer Tooling Strategy

> **Context:** This document analyses three inter-connected topics around standardising the local development workflow for our charm repositories:
> 1. Adapting the existing `raw_makefiles` set to work with `synapse-operator`, including how to handle the genuine differences between charm deployments
> 2. What a cleaner, more production-ready Makefile architecture would look like — framed in the context of those files living inside a Vex binary rather than copy-pasted per repo
> 3. Whether [Vex](https://github.com/srbouffard/vex) is a good candidate for a team-wide charm development CLI, updated to reflect [PR #2](https://github.com/srbouffard/vex/pull/2) which adds native `.env` file loading and version pinning
>
> The baseline for this analysis is the Makefile set introduced in [canonical/discourse-k8s-operator#379](https://github.com/canonical/discourse-k8s-operator/pull/379), copied into `raw_makefiles/`.

---

## Table of Contents

1. [Adapting `raw_makefiles` for synapse-operator](#1-adapting-raw_makefiles-for-synapse-operator)
2. [A Cleaner Makefile Architecture](#2-a-cleaner-makefile-architecture)
3. [Vex as a Team CLI](#3-vex-as-a-team-cli)
4. [Recommendation Summary](#4-recommendation-summary)

---

## 1. Adapting `raw_makefiles` for synapse-operator

### What the makefiles actually do (and don't do)

It's worth being precise about what these files handle, because it directly determines whether there are hidden per-charm differences.

The `make/` files cover:
- **Artifact lifecycle** (`rock.mk`, `charm.mk`): build the ROCK OCI image, build the charm, compute content-hash-based tags, rename artifacts
- **Registry publishing** (`rock.mk`): push the ROCK to the local MicroK8s registry, with idempotency checks
- **Tox delegation** (`tox.mk`): install tox in a venv, invoke `tox -e <env>` with the right environment variables pointing at built artifacts
- **Juju model setup** (`juju.mk`): create/configure the Juju model

What they **deliberately do not handle**:
- Deploying charm dependencies (PostgreSQL, Redis, etc.)
- Creating Juju relations
- Setting charm configuration (e.g. `server_name` for synapse)
- Any post-deploy assertions or wait logic

For **integration tests**, this is a non-issue: `pytest-operator` handles all of that inside the test suite itself. The makefile's job is just to point tox at the right built artifacts via `CHARM_FILE`, `ROCK_IMAGE`, etc. That part is genuinely generic.

For **local deployment** (`make deploy`), this is a real limitation. The current `deploy-charm` in `charm.mk` issues a bare `juju deploy`:

```makefile
juju deploy -m $(JUJU_MODEL_NAME) ./$(CHARM_DYNAMIC_ARTIFACT) --resource $(OCI_RESOURCE_NAME)=$(ROCK_IMAGE)
```

That command deploys the charm unit but leaves it in a blocked state for synapse (missing `server_name`, no PostgreSQL relation). It is not a working deployment by itself.

### How to handle per-charm deployment differences: the hook script pattern

The right solution is **hook scripts**: define optional extension points that repos can provide, with the generic makefiles calling them if they exist and doing nothing otherwise.

For Make this looks like **hook targets with default no-op implementations**:

```makefile
# juju.mk — generic, no-op hooks by default
deploy-charm-pre: ## (Override in root Makefile) Run before deploying the charm.
deploy-charm-post: ## (Override in root Makefile) Run after deploying the charm (set config, add relations, etc.).

deploy-charm: $(CHARM_DYNAMIC_ARTIFACT) publish-rock deploy-charm-pre ## Build & publish artifacts, then deploy.
	@$(call msg,"--> Deploying Charm: $(CHARM_NAME)")
	@juju deploy -m $(JUJU_MODEL_NAME) ./$(CHARM_DYNAMIC_ARTIFACT) --resource $(OCI_RESOURCE_NAME)=$(ROCK_IMAGE)
	@$(MAKE) deploy-charm-post
```

Then in the synapse root `Makefile`:

```makefile
# synapse-specific post-deploy setup
deploy-charm-post:
	@$(call msg,"--> Configuring Synapse...")
	@juju config $(CHARM_NAME) server_name=synapse.local
	@juju deploy -m $(JUJU_MODEL_NAME) postgresql-k8s
	@juju relate $(CHARM_NAME):database postgresql-k8s:database
	@juju wait-for unit $(CHARM_NAME)/0 --query='workload-status=="active"' --timeout=5m
```

For **Vex** (discussed in §3), this hook pattern transfers directly: the Vex component YAMLs call `make` targets using Vex's `make` runtime. The makefiles themselves contain the `deploy-charm-post` hook logic which checks for and calls `scripts/charm-deploy-post.sh` in the CWD. Nothing changes from the makefile perspective — the hook is in the makefile, not in any bundled script.

This pattern — **generic logic in the makefiles, charm-specific hooks in the repo** — is the key design principle for anything that must stay generic while accommodating per-charm variation.

### What needs to change for synapse today

Only a **single new file** at the repo root is needed for build/test/lint. The `raw_makefiles/Makefile` was written for discourse and should not be modified. Create a `Makefile` at the synapse repo root:

```makefile
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

# ==============================================================================
# Project: Synapse K8s Operator
# This file contains ONLY project-specific configuration.
# ==============================================================================

CHARM_NAME          := synapse
ROCK_NAME           := synapse
OCI_RESOURCE_NAME   := synapse-image
ROCK_DIR            ?= synapse_rock

# Override the default lint to exclude docs-check until vale/lychee are configured.
lint: tox-lint

# Synapse-specific post-deploy setup (PostgreSQL relation, server_name, etc.)
deploy-charm-post:
	@$(call msg,"--> Configuring Synapse post-deploy...")
	# Add charm-specific juju config/relate commands here

# ==============================================================================
# Makefile common logic
# ==============================================================================

MAKE_DIR := raw_makefiles/make
include $(MAKE_DIR)/common.mk
```

**Variable mapping:**
- `CHARM_NAME` → charm artifact name stem (`synapse_ubuntu-22.04-amd64.charm`)
- `ROCK_NAME` → matches `name:` in `synapse_rock/rockcraft.yaml`
- `OCI_RESOURCE_NAME` → matches `resources.synapse-image` in `metadata.yaml`
- `ROCK_DIR` → overrides the `rock/` default in `rock.mk`

> **Note:** `deploy-charm-pre` / `deploy-charm-post` hooks don't yet exist in the current `raw_makefiles/` — they need to be added as part of the v2 improvements described in §2.

### Known issues in the current makefiles (inherited from the PR)

These are real bugs or design gaps raised in the PR review, not yet resolved:

| Issue | Location | Severity | Details |
|---|---|---|---|
| Mixed tabs/spaces | Several `.mk` files | 🔴 High | Can cause `missing separator` errors depending on editor/Make version. |
| `tox-integration` depends on `build-charm`/`publish-rock` | `tox.mk:44` | 🟡 Medium | `tox.mk` shouldn't know about `charm.mk`/`rock.mk`. Orchestration belongs in `common.mk`. Flagged as a potential blocker by reviewer. |
| Duplicate `HAS_YQ` definition | `rock.mk` and `charm.mk` | 🟡 Medium | Both files independently run `$(shell command -v yq)`. |
| Hard-coded microk8s in `publish-rock-force` | `rock.mk:54` | 🟡 Medium | `microk8s ctr images rm` is not portable to other K8s substrates. |
| No deploy hook extension points | `charm.mk` | 🟡 Medium | No way to add charm-specific post-deploy steps without overriding the entire `deploy-charm` target. |
| `docs-check` in `lint` | `common.mk:28` | 🟡 Medium | Requires `vale` and `lychee`. Synapse does not have these set up. Workaround: override `lint` in root `Makefile`. |
| `tox.mk` declares `.PHONY` for targets it doesn't own | `tox.mk:33` | 🟢 Low | `lint`, `unit`, `integration` are aliases in `common.mk`. |
| `DOCKER_REGISTRY` naming | `rock.mk:9` | 🟢 Low | `CONTAINER_REGISTRY` would be more accurate. |

---

## 2. A Cleaner Makefile Architecture

> **Important framing shift:** If we adopt Vex, the `make/` files will be **bundled inside the Vex binary**, not copy-pasted into each charm repo. This changes everything about how we think about improvements. The fixes below should be made once, in the workspace repository that produces the binary. Individual charm repos never touch the makefiles.

### Is the current architecture sound?

**Yes, the core philosophy is correct.** The root config file as the sole project-specific entry point, with generic shared logic underneath, is a clean and proven pattern. The intent is right. The v1 implementation has gaps that will accumulate friction, but they're all fixable.

### Proposed improvements for a v2

#### A. Make `common.mk` the exclusive orchestrator

The single most impactful change, flagged as a potential blocker by reviewer @amandahla: `tox.mk` should not directly depend on `build-charm` or `publish-rock`. Each `.mk` file defines only its own targets and variables. `common.mk` orchestrates across files.

**Current (problematic):**
```makefile
# tox.mk - knows too much about other modules
tox-integration: $(TOX) build-charm publish-rock
    ...
```

**Proposed:**
```makefile
# tox.mk - only knows how to run tox
tox-integration: $(TOX)
    ...

# common.mk - is the only orchestrator
integration: build-charm publish-rock tox-integration
```

This makes each `.mk` file independently replaceable. Swapping `tox` for `uv` means only touching one file.

#### B. Add deploy hook extension points

As established in §1, `deploy-charm` needs pre/post hooks for charm-specific setup:

```makefile
# juju.mk — hooks with default no-op implementations
deploy-charm-pre:  ## (Override in charm.env) Run before deploying the charm.
deploy-charm-post: ## (Override in charm.env) Run after deploying the charm.

deploy-charm: $(CHARM_DYNAMIC_ARTIFACT) publish-rock deploy-charm-pre
	@juju deploy -m $(JUJU_MODEL_NAME) ./$(CHARM_DYNAMIC_ARTIFACT) --resource $(OCI_RESOURCE_NAME)=$(ROCK_IMAGE)
	@$(MAKE) deploy-charm-post
```

With Vex, this is the same: the Vex component calls `make deploy-charm`, and the makefile's `deploy-charm-post` hook checks for `scripts/charm-deploy-post.sh` in the CWD.

#### C. Centralise shared variable derivation

Both `rock.mk` and `charm.mk` independently check for `yq`. A single block at the top of `common.mk`:

```makefile
# common.mk - single source of truth for shared derived variables
HAS_YQ := $(shell command -v yq)
ifndef HAS_YQ
    $(error yq is required. Install with: snap install yq)
endif

ROCK_VERSION_BASE := $(shell yq '.version // "1.0"' $(ROCK_DIR)/rockcraft.yaml)
ROCK_CONTENT_HASH := $(shell find $(ROCK_DIR) -type f -not -name '*.rock' -print0 | sort -z | xargs -0 cat | sha1sum | cut -c1-7)
...
```

#### D. Abstract the K8s substrate

Replace the hard-coded microk8s references with a `K8S_BACKEND` variable (default: `microk8s`), allowing `kind`, `k3s`, etc.:

```makefile
K8S_BACKEND ?= microk8s
DOCKER_REGISTRY ?= localhost:32000  # could also vary by backend
```

#### E. Fix tabs/spaces and `DOCKER_REGISTRY` naming

Tabs only, everywhere. Rename `DOCKER_REGISTRY` to `CONTAINER_REGISTRY`. These are cosmetic but the tab issue is a real source of cryptic errors.

#### F. Add prerequisite checks for primary tooling

```makefile
.check-charmcraft:
    @command -v charmcraft >/dev/null || $(call errmsg,"charmcraft not found. Install with: snap install charmcraft --classic")

build-charm: .check-charmcraft $(CHARM_DYNAMIC_ARTIFACT)
```

#### G. Unify `publish-rock` and `publish-rock-force` with a flag

Per reviewer suggestion: `make publish-rock FORCE=true` instead of two separate targets.

### Summary: current v1 vs proposed v2

| Concern | Current v1 | Proposed v2 |
|---|---|---|
| Where does it live? | Copy-pasted per repo | Bundled in Vex binary, single source |
| Orchestration | Split between `common.mk` and `tox.mk` | `common.mk` exclusively |
| Per-charm deployment differences | Not handled | `deploy-charm-pre/post` hooks |
| K8s substrate | Hard-coded microk8s | `K8S_BACKEND` variable |
| `yq` dependency | Declared twice | Once in `common.mk` |
| Tab/space consistency | Mixed | Tabs only |
| Updates across repos | Copy-paste again | Release new binary version |

---

## 3. Vex as a Team CLI

### What Vex does

[Vex](https://github.com/srbouffard/vex) is a Go binary that wraps scripts and task files (bash, python, Make, Just) into a typed, validated CLI. Its workspace mode is the relevant feature here: a directory of YAML component definitions becomes a nested CLI tree, which can be compiled to a single standalone binary via `vex build`.

Key properties:
- **Dependency validation** before execution (`bins`, `python`, `env` checks)
- **Workspace → standalone binary** via `vex build` using Go embed — no runtime dependency on Vex
- **Runtime agnostic** — supports bash, python, `make <target>`, `just <recipe>`
- **Fast** (<50ms startup)
- **Human-readable YAML configuration**

### PR #2: `.env` loading and version pinning (in progress)

[PR #2](https://github.com/srbouffard/vex/pull/2) adds the two features that are critical for the charm use case:

**1. Native `.env` file loading**

`vex.yaml` gains an `env_file` property. Crucially, the file is resolved from the **caller's CWD** (the charm repo), not from the embedded workspace. This is the key design decision that makes a generic binary work with per-repo configuration:

```yaml
# vex.yaml (inside the charm binary)
name: charm
env_file: charm.env  # resolved from wherever the binary is invoked
```

In each charm repo:
```bash
# charm.env (in the repo root, checked in or gitignored per preference)
CHARM_NAME=synapse
ROCK_NAME=synapse
OCI_RESOURCE_NAME=synapse-image
ROCK_DIR=synapse_rock
```

If no `env_file` is specified, Vex automatically tries `.env` in CWD. Variables loaded from the file flow into the existing `env:` argument binding in components, and are available as environment variables in the subprocess (so `make` targets and bash scripts can read them naturally).

**2. Version pinning**

`vex.yaml` gains a `version` field. Each charm repo can have a `.charm-version` file pinning which binary version it was tested with:

```yaml
# vex.yaml
name: charm
version: 1.2.0
version_file: .charm-version
```

```bash
# .charm-version (in the charm repo)
1.2.0
```

On mismatch: warning by default, hard failure with `--strict-version` (useful in CI). Standalone compiled binaries bypass the version check — they are self-enclosed.

This mechanism solves the "team upgrades the binary but CI uses a different version" problem cleanly.

### Full architecture with Vex

With PR #2 merged, the complete picture for our charm tooling looks like this:

```
┌─────────────────────────────────────────────────────────────────┐
│  User interface:  charm <command> [flags]                       │  ← compiled Vex binary
│  Produced by:     vex build charm-workspace/                    │
│  Distributed via: snap / apt / GH release / brew               │
├─────────────────────────────────────────────────────────────────┤
│  Inside the binary (invisible to users):                        │
│  ├── vex.yaml             workspace config, env_file, version   │
│  ├── build/rock.yaml      'charm build rock'                    │
│  ├── build/charm.yaml     'charm build charm'                   │
│  ├── test/lint.yaml       'charm test lint'                     │
│  ├── test/unit.yaml       'charm test unit'                     │
│  ├── test/integration.yaml 'charm test integration'             │
│  ├── deploy.yaml          'charm deploy'                        │
│  ├── make/                generic makefiles (rock, charm, tox…) │
│  └── (no scripts — components call make targets directly)      │
├─────────────────────────────────────────────────────────────────┤
│  In each charm repo (the only charm-specific files):            │
│  ├── charm.env            CHARM_NAME, ROCK_NAME, OCI_RESOURCE…  │
│  ├── .charm-version       1.2.0  (pins the binary version)      │
│  └── scripts/             optional hook scripts:                │
│      └── charm-deploy-post.sh  relations, config, wait          │
└─────────────────────────────────────────────────────────────────┘
```

Developer experience:

```bash
charm help
charm build
charm build rock
charm build charm
charm test lint
charm test unit
charm test integration --filter test_active
charm test integration --charm-version rev211-rc1
charm deploy
```

### Example workspace internals

**`vex.yaml`:**
```yaml
name: charm
description: Canonical charm development CLI
version: 1.0.0
env_file: charm.env
version_file: .charm-version
dependencies:
  bins: [make, yq, charmcraft, rockcraft, juju, skopeo]
```

**`test/integration.yaml`:**
```yaml
command: "test integration"
description: "Build artifacts and run integration tests"
runtime: make
script: make/common.mk
target: tox-integration
args:
  - name: filter
    type: string
    env: TOX_INTEGRATION_ARGS
    help: "pytest -k filter expression (e.g. test_active)"
  - name: charm-version
    type: string
    env: CHARM_VERSION
    help: "Override the charm version tag (default: git describe)"
```

**`deploy.yaml`:**
```yaml
command: deploy
description: "Build, publish, and deploy the charm (runs deploy-charm-post hook if present in repo)"
runtime: make
script: make/common.mk
target: deploy
```

The `deploy-charm-post` hook in the makefile checks for `scripts/charm-deploy-post.sh` in the CWD — that script lives in each charm repo, not in the binary.

### Vex pros and cons for this use case

| | |
|---|---|
| ✅ **Tech agnosticism** | `charm build`, `charm test` stay stable even if the internals move from Make to Just or uv |
| ✅ **Dependency validation** | Early, clear failure with install hints before any script runs |
| ✅ **Typed arguments** | `--filter`, `--charm-version` become first-class typed flags |
| ✅ **Single distributable binary** | `./pfe-workflow` works without Vex, Make, or Python installed separately by the user |
| ✅ **CI alignment** | CI runs the exact same `./pfe-workflow test integration` as developers locally — same binary |
| ✅ **Version pinning** (PR #2) | `.charm-version` in each repo pins the expected binary version; `--strict-version` blocks CI on mismatch |
| ✅ **`.env` loading** (PR #2) | `charm.env` in each repo provides per-charm variables — CWD-based resolution is the right design |
| ✅ **No Vex runtime dependency** | `vex build` compiles a standalone binary; team members never install Vex |
| ✅ **Hook script pattern** | Per-charm `scripts/charm-deploy-post.sh` handles Juju relations/config without modifying the binary |
| ❌ **New YAML layer** | The workspace YAML is a new thing to learn on top of Make |
| ❌ **Build step required** | Team must build/release the binary when the workspace changes |
| ❌ **Early project** | Vex is pre-1.0; API may evolve |

---

## 4. Recommendation Summary

### For immediate use (synapse today)

Create a single `Makefile` at the synapse repo root (shown in §1) pointing to `raw_makefiles/make`. Override the `lint` target to skip `docs-check` until vale/lychee are configured. Add `deploy-charm-pre` and `deploy-charm-post` override targets for synapse-specific setup (this requires adding the hook targets to `juju.mk` first). This is a ~15-line change.

### For a v2 Makefile refactor (do once, in the Vex workspace repo)

If we go with Vex, these improvements happen once in the workspace repository that produces the binary — not in individual charm repos:

1. Fix tab/space inconsistencies
2. Move orchestration of `integration` fully into `common.mk`
3. Deduplicate `HAS_YQ` — single declaration in `common.mk`
4. Add `deploy-charm-pre` / `deploy-charm-post` no-op hooks
5. Add `K8S_BACKEND` variable, remove hard-coded microk8s references
6. Add prerequisite checks for `charmcraft` and `rockcraft`

### For the Vex CLI track

With PR #2 merged, Vex now has all the features needed for the charm use case. The recommended path:

1. **Now**: Merge PR #2, then build a `charm-workspace/` with the generic makefiles and Vex component YAMLs — test it with synapse using just `charm.env` and (optionally) `scripts/charm-deploy-post.sh` in the repo
2. **Short term**: Release the `pfe-workflow` binary for the team to install; each repo adds `charm.env` and `.charm-version`; CI installs the binary and runs `./pfe-workflow test integration`
3. **Long term**: The makefiles inside the binary become an implementation detail — if the team wants to switch to `just` or `uv`, that's a new binary release, not a change in any charm repo

The CI alignment goal — "same command in CI as locally" — is most cleanly achieved with the Vex binary approach, since `./pfe-workflow test integration` is unambiguous regardless of the underlying CI system.

---

## 5. Implementation Plan

> **Status: not started.** All steps below are pending. Start at Step 1 of Phase 1 and work in order — each step lists its dependencies explicitly.
>
> **For an implementing agent:** read §1–4 for context, then execute the steps in this section sequentially. The acceptance criteria at the end of each phase define what "done" means before moving on.

> **Status (as of 2026-03-02):** Not started. All items below are pending. Start at Step 1 of Phase 1 — it unblocks everything else.

The work splits into two sequential phases. Phase 1 must be confirmed working before Phase 2 begins.

---

### Phase 1: Rebuild the Makefile Set

**Goal:** A corrected, self-contained `make/` directory that works with synapse (and any other charm) with zero bugs from the known issue list. Verified by running all targets against the synapse repo.

**Inputs:** `raw_makefiles/make/` (current v1 files)  
**Output:** A new `make/` directory at the repo root (or a standalone repo if we want the submodule path), plus a synapse-specific root `Makefile`

#### Ordered work items

The order matters: items marked with ← dependency must wait for their predecessor.

**Step 1 — Fix tabs/spaces (prerequisite for everything else)**

In all `.mk` files, replace any space-based indentation with tabs. Recipe lines (the commands under a target) must be tabs. Variable assignment blocks can use spaces. The mixed state currently causes intermittent `missing separator` errors.

Files to touch: `common.mk`, `rock.mk`, `charm.mk`, `juju.mk`, `tox.mk`, `docs.mk`, `help.mk`

**Step 2 — Consolidate `HAS_YQ` and shared derived variables into `common.mk`**

Remove the `HAS_YQ` blocks from `rock.mk` and `charm.mk`. Add a single block at the top of `common.mk` (before the includes) that:
- Checks for `yq` and errors with an install hint if missing
- Computes all cross-cutting derived variables: `ROCK_VERSION_BASE`, `ROCK_CONTENT_HASH`, `ROCK_IMAGE_TAG`, `ROCK_STATIC_ARTIFACT`, `ROCK_DYNAMIC_ARTIFACT`, `ROCK_IMAGE`, `CHARM_BASE_NAME`, `CHARM_BASE_CHANNEL`, `CHARM_BASE_STRING`, `JUJU_DEPLOY_BASE`, `CHARM_STATIC_ARTIFACT`, `CHARM_DYNAMIC_ARTIFACT`
- `rock.mk` and `charm.mk` then reference these variables without computing them

**Step 3 — Fix `tox.mk`: remove cross-module dependencies ← requires Step 2**

Remove `build-charm publish-rock` from the `tox-integration` prerequisites. `tox-integration` becomes:
```makefile
tox-integration: $(TOX)
    @$(call msg,"--> Running tox environment: integration")
    @$(call msg,"    ROCK_IMAGE:'$(ROCK_IMAGE)'  CHARM_FILE:'$(CHARM_DYNAMIC_ARTIFACT)'")
    $(INTEGRATION_TEST_ENV) $(TOX) -e integration -- $(TOX_INTEGRATION_ARGS)
```

Remove the duplicate `.PHONY` declarations for `lint`, `unit`, `integration` from `tox.mk` — those belong only in `common.mk`.

**Step 4 — Add deploy hook extension points to `juju.mk` ← requires Step 1**

Add default no-op hook targets:
```makefile
## (Override in root Makefile) Run before deploying the charm (pre-requisite deploys, etc.).
deploy-charm-pre:

## (Override in root Makefile) Run after deploying the charm (config, relations, wait-for-active, etc.).
deploy-charm-post:
```

Modify `deploy-charm` in `charm.mk` to call them:
```makefile
deploy-charm: $(CHARM_DYNAMIC_ARTIFACT) publish-rock deploy-charm-pre
    @$(call msg,"--> Deploying Charm: $(CHARM_NAME)")
    @juju deploy -m $(JUJU_MODEL_NAME) ./$(CHARM_DYNAMIC_ARTIFACT) --resource $(OCI_RESOURCE_NAME)=$(ROCK_IMAGE)
    @$(MAKE) deploy-charm-post
```

**Step 5 — Fix `common.mk` orchestration ← requires Steps 3 and 4**

Update `common.mk` to own the full `integration` workflow:
```makefile
integration: build-charm publish-rock tox-integration  ## Deploy the charm, then run integration tests.
```

And wire up `deploy` to use the hook pattern:
```makefile
deploy: deploy-charm  ## Deploy the charm for local testing (runs pre/post hooks).
```

**Step 6 — Add prerequisite checks for `charmcraft` and `rockcraft`**

In `charm.mk`:
```makefile
.check-charmcraft:
    @command -v charmcraft >/dev/null 2>&1 || \
        $(call errmsg,"charmcraft not found. Install with: snap install charmcraft --classic")

build-charm: .check-charmcraft $(CHARM_DYNAMIC_ARTIFACT)
```

Same pattern for `rockcraft` in `rock.mk`.

**Step 7 — Replace microk8s hardcoding with `K8S_BACKEND` variable**

In `rock.mk`, replace `microk8s ctr images rm` in `publish-rock-force` with a conditional:
```makefile
K8S_BACKEND ?= microk8s

publish-rock-force: $(ROCK_DIR)/$(ROCK_DYNAMIC_ARTIFACT) check-microk8s-registry
    @$(call msg,"--> Force Publishing ROCK: $(ROCK_IMAGE)")
    @$(K8S_BACKEND) ctr images rm $(ROCK_IMAGE) || true
    $(SKOPEO_COPY_CMD) oci-archive:$(ROCK_DIR)/$(ROCK_DYNAMIC_ARTIFACT) docker://$(ROCK_IMAGE)
```

Rename `DOCKER_REGISTRY` to `CONTAINER_REGISTRY`.

**Step 8 — Create the synapse root `Makefile`**

```makefile
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

# ==============================================================================
# Project: Synapse K8s Operator
# This file contains ONLY project-specific configuration.
# ==============================================================================

CHARM_NAME        := synapse
ROCK_NAME         := synapse
OCI_RESOURCE_NAME := synapse-image
ROCK_DIR          ?= synapse_rock

# Override the default lint to exclude docs-check until vale/lychee are configured.
lint: tox-lint

# Synapse-specific post-deploy: deploy PostgreSQL, configure server_name, etc.
deploy-charm-post:
    @$(call msg,"--> Synapse post-deploy setup...")
    # TODO: fill in juju config/relate commands

# ==============================================================================
MAKE_DIR := make
include $(MAKE_DIR)/common.mk
```

> At this point, the `make/` directory should be moved from `raw_makefiles/make/` to a top-level `make/` directory so `MAKE_DIR := make` works from the repo root. `raw_makefiles/` can be kept for reference or removed.

#### Acceptance criteria for Phase 1

Run the following in the synapse repo root and verify each succeeds:

```bash
make help           # prints all targets without errors
make lint           # tox lint passes
make unit           # tox unit passes
make build-rock     # produces synapse_rock/synapse_<version>-<hash>_amd64.rock
make build-charm    # produces synapse_<git-version>_ubuntu-22.04_amd64.charm
```

For the deployment targets, verify dry-run behaviour:
```bash
# With juju available and a model set up:
make setup-juju-model
make deploy         # should build, publish, deploy, and call deploy-charm-post hook
```

---

### Phase 2: Vexify the Makefile Set

**Prerequisite:** Phase 1 complete and verified.  
**Prerequisite:** Vex PR #2 merged.

**Goal:** A `charm-workspace/` directory that bundles the Phase 1 `make/` files and Vex component YAMLs into a workspace. `vex build charm-workspace/` produces a `charm` binary. That binary, when invoked from any charm repo containing `charm.env`, provides the full developer CLI.

#### Files to create in `charm-workspace/`

```
charm-workspace/
├── vex.yaml                        workspace root config
├── make/                           copy of the Phase 1 make/ directory
│   ├── common.mk
│   ├── rock.mk
│   ├── charm.mk
│   ├── juju.mk
│   ├── tox.mk
│   ├── help.mk
│   └── docs.mk
├── build/
│   ├── rock.yaml                   'pfe-workflow build rock'
│   └── charm.yaml                  'pfe-workflow build charm'
├── test/
│   ├── lint.yaml                   'pfe-workflow test lint'
│   ├── unit.yaml                   'pfe-workflow test unit'
│   └── integration.yaml            'pfe-workflow test integration'
├── deploy.yaml                     'pfe-workflow deploy'
└── publish/
    └── rock.yaml                   'pfe-workflow publish rock'
```

Each component YAML uses Vex's `make` runtime and calls the corresponding `make` target directly. No bash scripts are bundled — the makefiles contain all the logic, including the hook mechanism that calls charm-specific scripts from the CWD.

#### Key file contents

**`vex.yaml`:**
```yaml
name: charm
description: Canonical charm development CLI
version: 1.0.0
env_file: charm.env
version_file: .charm-version
dependencies:
  bins: [make, yq, charmcraft, rockcraft, juju, skopeo]
```

**`build/rock.yaml`:**
```yaml
command: "build rock"
description: "Build the ROCK OCI image"
runtime: make
script: make/common.mk
target: build-rock
```

**`test/integration.yaml`:**
```yaml
command: "test integration"
description: "Build artifacts and run integration tests"
runtime: make
script: make/common.mk
target: tox-integration
args:
  - name: filter
    type: string
    env: TOX_INTEGRATION_ARGS
    help: "pytest -k filter expression (e.g. test_active)"
  - name: charm-version
    type: string
    env: CHARM_VERSION
    help: "Override the charm version tag (default: git describe)"
```

**`deploy.yaml`:**
```yaml
command: deploy
description: "Build, publish, and deploy the charm"
runtime: make
script: make/common.mk
target: deploy
```

The `deploy` make target calls `deploy-charm-post`, which the makefile defines as a no-op by default. Each charm repo overrides it by providing `scripts/charm-deploy-post.sh` — the makefile hook checks for and calls that file from the CWD at runtime.

#### What each charm repo needs (and nothing more)

```
charm.env                       # required: CHARM_NAME, ROCK_NAME, OCI_RESOURCE_NAME, ROCK_DIR
.charm-version                  # recommended: pins the pfe-workflow binary version
scripts/
  charm-deploy-post.sh          # optional: charm-specific juju setup after deploy
                                # called by the deploy-charm-post make hook if present
```

#### Acceptance criteria for Phase 2

```bash
# In the charm-workspace directory:
vex build charm-workspace/ -o ./pfe-workflow

# In the synapse repo root:
./pfe-workflow help
./pfe-workflow build rock
./pfe-workflow build charm
./pfe-workflow test lint
./pfe-workflow test unit
./pfe-workflow test integration --filter test_active
./pfe-workflow deploy
```

Each command should behave identically to the equivalent `make` target from Phase 1, reading configuration from `charm.env`.

Also verify version pinning:
```bash
echo "1.0.0" > .charm-version
./pfe-workflow test lint                   # should succeed silently
echo "9.9.9" > .charm-version
./pfe-workflow test lint                   # should warn about version mismatch
./pfe-workflow test lint --strict-version  # should fail hard
```

---

### Decisions

1. **Where does `charm-workspace/` live?** Built out inside this repo (`synapse-operator`) for the prototype. Once verified, the workspace and makefile set move to their own repository for team-wide use.

2. **CLI name:** `pfe-workflow` — GitHub releases for distribution (details defined when the dedicated repo is created).

3. **Does `charm.env` get committed?** Yes — it's project config, not secrets. A new contributor can `git clone` and immediately run the CLI.

4. **What happens to the root `Makefile`?** Removed once the CLI is in use. It won't be needed — the `pfe-workflow` binary is the entry point. During the build-out phase in this repo both can coexist.
