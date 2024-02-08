# How to back up and restore Synapse

This document shows how to back up and restore Synapse.

A backup strategy is an integral part of disaster recovery, and should be
planned accordingly. The main goal of a backup is the possibility of being
restored and the backup and restore process should be tested as part of
normal operations.

The process of backing up and restoring depends on whether an external database
is used, so the step to run the backup for PostgreSQL must be done only if PostgreSQL
is used in the original Synapse application.

## Back up Synapse

### Deploy s3-integrator charm

Synapse gets backed up to a S3 compatible object storage. The bucket for the backup should be provisioned before the backup is performed.

For Synapse to get the credentials, the `s3-integrator` is used. Refer to [s3-integrator](https://charmhub.io/s3-integrator/) for specific configuration options. 

```
juju deploy s3-integrator --channel edge
juju config s3-integrator endpoint=<s3 endpoint> bucket=<bucket name> path=<optional-path> region=<region> s3-uri-style=<path or host>
juju run s3-integrator/leader sync-s3-credentials access-key=<access-key> secret-key=<secret-key>
```

Integrate with Synapse with:

`juju integrate synapse:backup s3-integrator`

### Configure the passphrase

The backup will be encrypted before being sent using symmetric encryption. You need
to set the desired password with:
```
juju config synapse backup_passphrase=<secret passphase>
```

### Create the backup

Create the backup with the next command:
```
juju run synapse/leader create-backup
```

A new object should be placed in the S3 compatible object storage, a tar file encrypted with the `gpg` command.


You can list the available backups with the `list-backups` command:
```
juju run synapse/leader list-backups
```

### Back up PostgreSQL

Follow the instructions of the PostgreSQL charm:
 - For [postgresql-k8s](https://charmhub.io/postgresql-k8s/docs/h-create-and-list-backups).
 - For [postgresql](https://charmhub.io/postgresql/docs/h-create-and-list-backups).

If you plan to restore PostgreSQL in a different model or cluster, you will need
to also back up the cluster passwords. See:
 - For [postgresql-k8s](https://charmhub.io/postgresql-k8s/docs/h-migrate-cluster-via-restore).
 - For [postgresql](https://charmhub.io/postgresql/docs/h-migrate-cluster-via-restore).


## Restore

The recommendation is to first restore PostgreSQL if necessary. Then deploying,
configuring and integrating Synapse with other charms as done in a normal deployment
and finally restoring Synapse. 

The PostgreSQL and Synapse charm revisions should be the same ones as the ones used
for the backup. The configuration for Synapse before restoring the backup should also
match the configuration in the original application. This is specially important for 
the configuration option `server_name` and any other configuration related to the filesystem.


### Restore PostgreSQL


If you use the PostgreSQL integration, follow the instructions given by PostgreSQL:
 - For postgresql-k8s: [local restore](https://charmhub.io/postgresql/docs/h-restore-backup), [foreign backup](https://charmhub.io/postgresql/docs/h-migrate-cluster-via-restore).
 - for postgresql: [local restore](https://charmhub.io/postgresql/docs/h-restore-backup), [foreign backup](https://charmhub.io/postgresql/docs/h-migrate-cluster-via-restore).

If you used the foreign backup, once the backup for PostgreSQL is restored, you should remove the S3 integration,
as it was created in a different cluster, by running:

```
juju remove-relation s3-integrator postgresql
```

### Deploy Synapse

Synapse should be deployed, integrated with all necessary charms and configured. If necessary, Synapse should be integrated with the PostgreSQL charm that
has already being restored.

### Restore Synapse


Set the `backup_passphrase` to the passphrase used for the backup.
```
juju config synapse backup_passphrase=<secret passphase>
```

Integrate with S3, following the same instructions as in the backup procedure, that is, similar to:

```
juju deploy s3-integrator --channel edge
juju config s3-integrator endpoint=<s3 endpoint> bucket=<bucket name> path=<optional-path> region=<region> s3-uri-style=<path or host>
juju run s3-integrator/leader sync-s3-credentials access-key=<access-key> secret-key=<secret-key>
```

Integrate with Synapse with:

`juju integrate synapse:backup s3-integrator`

List the backups and take note of the desired `backup-id`
```
juju run synapse/leader list-backups
```

Restore the backup:
```
juju run synapse/leader restore-backup backup-id=<backup-id from the list of backups>
```

At this point, Synapse should be active and the restore procedure complete.