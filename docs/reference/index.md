---
myst:
  html_meta:
    "description lang=en": "Technical reference documentation for the Synapse charm, including actions, configurations, and integrations."
---

(reference_index)=

# Reference

Technical information, specifications, and APIs for the Synapse charm.

## Charm interfaces

The Synapse charm controls its operations and interfaces through Juju actions,
configurations, and relation endpoints (integrations).

- [Actions](actions)
- [Configurations](configurations)
- [Integrations](integrations)

## Architecture and networking

Understanding the overall charm architecture provides the structural context
needed to see how your operational choices interact at runtime, while understanding
the external connectivity requirements empowers you to connect your Synapse deployment
to the rest of the world.

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
