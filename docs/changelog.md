(changelog)=

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

Each revision is versioned by the date of the revision.

## 2026-11-23

- Added a Kubernetes Service that routes to the main unit's pod. When the application is trusted (`juju trust <application> --scope=cluster`), NGINX on the other units sends the main unit's requests to this Service. The Service keeps its address when the pod is replaced, so the other units no longer restart NGINX to follow the main unit. Without trust, nothing changes.

## 2026-11-16

- Added the `valkey` integration, as a replacement for the `redis` integration. When both exist, the charm uses Valkey, so a deployment can add Valkey first and remove Redis later.
- Updated Synapse to 1.165.0. Valkey requires a username, which Synapse supports from 1.162.0.
- Fixed the charm writing the Redis host `None` when the `redis` integration has no address yet. The charm now waits.
- Stopped writing the values of changed Synapse settings to the debug log, because they can contain passwords.

## 2026-11-10

- Fixed requests timing out after the main unit's pod is replaced, for example by a refresh. The main unit now publishes its IP to the other units, which makes them restart NGINX and find it at its new address.

## 2026-11-04

- Updated the getting started tutorial to deploy `postgresql-k8s` from `14/stable` and `synapse` from `1/stable`, because the default channels no longer produce a working deployment. There is no change to the charm.
- Added `--destroy-storage` to the tutorial's cleanup command, because Juju refuses to destroy a model with persistent storage without it.
- Added Juju and MicroK8s setup steps to the getting started tutorial, replacing the link to the Juju setup guide, so that the tutorial and its Spread test use the same environment. There is no change to the charm.

## 2026-10-19

- Moved the documentation tooling to the centrally managed `platform-engineering-documentation-files` Copier template and added a scheduled workflow that keeps it in sync. There is no change to the charm.

## 2026-09-30

- Reworked the home page to follow the standard "In this documentation" and "How this documentation is organized" pattern.

## 2026-06-18

- Migrated the RTD documentation URL under the Canonical domain.

## 2026-04-27

- Set up RTD project for migrating Charmhub documentation.

## 2025-09-09

- Add changelog for tracking user-relevant changes.
- Add `rate_limiting_levels` configuration.
