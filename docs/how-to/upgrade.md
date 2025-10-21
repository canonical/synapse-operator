# How to upgrade

Before updating the charm you need to back up Synapse.

Additional information can be found about backing up in [How to back up and restore Synapse](https://charmhub.io/synapse/docs/how-to-backup-and-restore).

When upgrading a Synapse deployment with multiple units, scale down to a single unit before refreshing the charm.
The main unit handles database schema updates, ensuring worker units start successfully after the upgrade.

If needed, you can scale down to a single unit using `juju scale-application` like this:
```
juju scale-application synapse 1
```

Once the unit is active and idle, you can upgrade the Synapse charm running the following command:
```
juju refresh synapse
```
