# How to back up Synapse

This document shows how to back up Synapse.

## Deploy s3-integrator charm

Synapse gets backed up to a S3 compatible object storage. To get the credentials, the `s3-integrator` is used. Refer to
[s3-integrator](https://charmhub.io/s3-integrator/) for specific configuration options.

```
juju deploy s3-integrator --channel edge
juju config s3-integrator endpoint=<s3 endpoint> bucket=<bucket name> path=<optional-path> region=<region> s3-uri-style=<path or host>
juju run s3-integrator/leader sync-s3-credentials access-key=<access-key> secret-key=<secret-key>
```

Integrate with Synapse with:

`juju integrate synapse:backup s3-integrator`

## Configure the passphrase

The backup will be encrypted before being sent using symmetric encryption. You need
to set the desired password with:
```
juju config synapse backup_passphrase=<secret passphase>
```

## Run the backup

Run the backup with the next command:
```
juju run synapse/leader create-backup
```

A new object should be placed in the S3 compatible object storage. This file is a tar
file encrypted with the `gpg` command.