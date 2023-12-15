# Getting Started

## What you’ll do
- Deploy the Synapse charm.
- Integrate with the PostgreSQL K8s charm.
- Integrate with the smtp-integrator charm.
- Expose the Synapse charm by using Traefik K8s charm.
- Create a user.
- Access your Synapse instance via Element Desktop.

Through the process, you'll verify the workload state, and log in to your
Synapse instance via Element Desktop application.

## Requirements
- Juju 3 installed.
- Juju controller and model created.

For more information about how to install Juju, see [Get started with Juju](https://juju.is/docs/olm/get-started-with-juju).

## Setting up a Tutorial Model

To manage resources effectively and to separate this tutorial's workload from
your usual work, we recommend creating a new model using the following command.

```
juju add-model synapse-tutorial
```

## Deploy the Synapse charm
Synapse requires connections to PostgreSQL. Deploy both charm applications.

### Deploy the charms:
```
juju deploy postgresql-k8s
juju deploy synapse
```

Run `juju status` to see the current status of the deployment. Synapse
unit should be in `waiting` status.

Set the server name by running the following command:
```
juju config synapse server_name=tutorial-synapse.juju.local
```

Run `juju status` again to see that the message has changed:
```
synapse/0*                 waiting   idle   10.1.74.70             Waiting for database availability
```

Provide integration between Synapse and PostgreSQL:
```
juju integrate synapse postgresql-k8s
```

Run `juju status` and wait until the Application status is `Active` as the
following example:
```
App                       Version                       Status  Scale  Charm                     Channel  Rev  Address         Exposed  Message
synapse                 3.2                           active      1  synapse                              17  10.152.183.68   no
```

The deployment is complete when the status is `Active`.

## Integrate with the smtp-integrator charm

For synapse to use smtp, it uses the smtp-integrator charm.
```
juju deploy smtp-integrator --channel edge
juju config smtp-integrator host=smtp.example.com port=25 user=alice password=whatever auth_type=plain transport_security=none domain=example.com
```

Configure the "From" mail for Synapse with:
```
juju config synapse notif_from=no-reply@example.com
```

You can run it with the legacy integration `smtp-legacy` or with
the new integration using secrets `smtp`. A Juju version 
with secrets will be required for the `smtp` integration.

With the old integration without using secrets, run:
```
juju integrate smtp-integrator:smtp-legacy synapse:smtp
```
For the new integration with secrets, run:
```
juju integrate smtp-integrator:smtp synapse:smtp
```

## Integrate with Traefik

The [Traefik charm](https://github.com/canonical/traefik-k8s-operator) exposes
Juju applications to the outside of a Kubernetes cluster, without relying on the
ingress resource of Kubernetes.

If you want to make Synapse charm available to external clients, you need to
deploy the Traefik charm and integrate Synapse with it.

### Deploy the charm Traefik:
```
juju deploy traefik-k8s --trust
```

Configure `external_hostname` as the same set for Synapse and the routing_mode:
```
juju config traefik-k8s external_hostname=juju.local
juju config traefik-k8s routing_mode=subdomain
```

Provide integration between Synapse and Traefik:
```
juju integrate synapse traefik-k8s
```

Now, you will need to go into your DNS settings and set the IP address of the
Traefik charm to the DNS entry you’re setting up. Getting the IP address can be
done using juju status.
```
App                       Version                       Status  Scale  Charm                     Channel  Rev  Address         Exposed  Message
traefik-k8s      2.9.6                 active       1  traefik-k8s      stable     110  10.152.183.225  no
```

You can configure the resolution of "tutorial-synapse.juju.local" by adding an
"A" record with the IP address "10.152.183.225" to the appropriate zone in your
DNS server's configuration. Save the changes and ensure that DNS caches are
flushed or DNS services are restarted if necessary. This will allow clients
querying your DNS server to resolve "tutorial-synapse.juju.local" to the
specified IP address. Note that it might take a few minutes for the DNS changes
to take effect.

In case you don’t have access to a DNS: The browser uses entries in the
`/etc/hosts` file to override what is returned by a DNS server. So, to resolve
it to your Traefik IP, edit /etc/hosts file and add the following line
accordingly:
```
10.152.183.225 tutorial-synapse.juju.local
```

Optional: run `echo "10.152.183.225 tutorial-synapse.juju.local" >> /etc/hosts`
to redirect the output of the command `echo` to the end of the file `/etc/hosts`.

After that, visit http://tutorial-synapse.juju.local in a browser and you'll be
presented with a screen with the following text: "It works! Synapse is running".

## Create a user
Create a user by running the following command:
```
juju run-action synapse/0 register-user username=alice password=<secure-password> admin=no
```

## Access via Element Desktop

Follow the [instructions](https://element.io/download) in Element Desktop to
install it.

Open it and click on “Sign in”. Then click on “Edit” to provide which server you
 want to use (tutorial-synapse.juju.local).

Now, you can fill in the username and password fields accordingly to the action
output. Then you should see a welcome page and it's ready to chat.

## Cleaning up the Environment

Well done! You've successfully completed the Synapse tutorial. To remove the
model environment you created during this tutorial, use the following command.

```
juju destroy model synapse-tutorial -y
```
