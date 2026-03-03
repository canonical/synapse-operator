 I'm working in the synapse-operator repo at:
     /home/samuel.bouffard@canonical.com/projects/canonical/synapse-operator

   There is a detailed strategy and implementation plan at:
     docs/dev-tooling-strategy.md

   Please read that file in full before doing anything. The document is the authoritative
   source — it covers the architecture decisions, what each file does, and exact acceptance
   criteria for each phase.

   Then implement Phase 1 in full, following the ordered steps in §5 exactly:

     1. p1-tabs     — Fix tabs/spaces in all .mk files under raw_makefiles/make/
     2. p1-yq       — Consolidate HAS_YQ and shared derived vars into top of common.mk
     3. p1-tox      — Fix tox.mk: remove build-charm/publish-rock deps from tox-integration
     4. p1-hooks    — Add deploy-charm-pre/post no-op hook targets to juju.mk, wire into charm.mk
     5. p1-orchestration — Fix common.mk: integration target = build-charm + publish-rock + tox-integration
     6. p1-prereq-checks — Add .check-charmcraft / .check-rockcraft prerequisite targets
     7. p1-k8s-backend   — Add K8S_BACKEND ?= microk8s; rename DOCKER_REGISTRY → CONTAINER_REGISTRY
     8. p1-synapse-makefile — Create root Makefile in the repo root (synapse-specific, ~20 lines)
     9. p1-verify    — Run: make help, make lint, make unit; confirm targets resolve without errors

   The acceptance criteria are in §5 of the doc. Do not start Phase 2.

   Track your progress a todos table.
   Update each todo to in_progress before you start it and done when it passes its
   acceptance criteria.
