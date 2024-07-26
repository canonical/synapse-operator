# How to horizontally scale

A Synapse deployment can scale horizontally by running multiple Synapse processes called workers.
While adding more units to the Synapse charm, one of them will be the Main process and others,
the workers. This architecture has specific requirements that will be described in this document.

For more details about scaling, refer to ["Scaling synapse via workers"](https://element-hq.github.io/synapse/latest/workers.html#scaling-synapse-via-workers) in the Synapse documentation.

## Requirements

- Synapse charm deployed and integrated with PostgreSQL charm.

The tutorial ["Getting started"](https://discourse.charmhub.io/t/synapse-docs-getting-started/12737) can be used to meet this requirement.

## Steps

### Deploy Redis and integrate it with Synapse

Run the following commands.

```
juju deploy redis-k8s --channel edge
juju integrate synapse redis
```

Once the output of the `juju status` command shows that the units are active and idle, proceed with
the next step.

### Deploy S3-integrator and integrate it with Synapse

This will enable S3 storage provider so media will be stored on a S3 bucket. Replace the
configuration options with your specific configuration.

```
juju deploy s3-integrator s3-integrator-media --channel edge
juju config s3-integrator-media endpoint=http://endpoint bucket=synapse-media-bucket path=/media region=us-east-1 s3-uri-style=path
juju integrate synapse:media s3-integrator-media
```
Once the output of the `juju status` command shows that the units are active and idle, proceed with
the next step.

### Scale Synapse application

With all integrations set, scale Synapse up by running the following command.

```
juju scale-application synapse 3
```

### Verify status

The output of `juju status` should look like this now.

```
$ juju status --relations
Model             Controller    Cloud/Region         Version  SLA          Timestamp
prod-synapse-k8s  ctr1          cloud1/default  3.1.8    unsupported  20:04:20Z

SAAS             Status       Store         URL
postgresql       active       cloud1  admin/prod-chat-synapse-db.postgresql

App                       Version  Status   Scale  Charm                     Channel        Rev  Address        Exposed  Message
media-s3-integrator                active      1  s3-integrator             latest/stable   13  10.10.10.1      no         
redis                     7.0.4    active       1  redis-k8s                 latest/edge     27  10.10.10.2   no       
synapse                            active       3  synapse                   latest/stable  303  10.10.10.3    no       

Unit                         Workload     Agent  Address          Ports  Message      
media-s3-integrator/0*       maintenance  idle   192.168.1.2         
redis/0*                     active       idle   192.168.1.7          
synapse/0                    active       idle   192.168.1.4         
synapse/1*                   active       idle   192.168.1.8         
synapse/2                    active       idle   192.168.1.6          

Integration provider                      Requirer                                  Interface            Type     Message 
media-s3-integrator:s3-credentials        synapse:media                             s3                   regular  
media-s3-integrator:s3-integrator-peers   media-s3-integrator:s3-integrator-peers   s3-integrator-peers  peer     
postgresql:database                       synapse:database                          postgresql_client    regular  
redis:redis                               synapse:redis                             redis                regular  
redis:redis-peers                         redis:redis-peers                         redis-peers          peer     
synapse:synapse-peers                     synapse:synapse-peers                     synapse-instance     peer 
```
