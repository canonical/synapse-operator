---
myst:
  html_meta:
    "description lang=en": "Technical reference documentation for the Synapse charm, including actions, configurations, and integrations."
---

(reference_index)=

# Reference

Technical information, specifications, and APIs for the Synapse charm.

## Charm interfaces
<!--
Themes: operator control surfaces, configuration parameters, Juju actions, integration endpoints
Justification: shared domain — operator-facing and cross-charm interfaces through which the charm is controlled and connected
User journey context: configuration, integration, all stages (lookup-driven)
Juju ecosystem scope: charm-specific (actions, configurations), cross-charm (integration endpoints)
-->

- [Actions](actions)
- [Configurations](configurations)
- [Integrations](integrations)

## Architecture and networking
<!--
Themes: sidecar pattern, Pebble layers, container design, external access, federation, network ports
Justification: shared concern — structural and behavioral description of charm internals and external connectivity requirements
User journey context: pre-deployment planning, configuration, integration
Juju ecosystem scope: charm-specific (container architecture), model-level (network access, federation)
-->

- [Charm architecture](charm-architecture)
- [External access](external-access)

```{toctree}
:maxdepth: 1
:hidden:
actions
configurations
external-access
integrations
charm-architecture
```
