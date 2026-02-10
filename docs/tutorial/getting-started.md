# Deploy the Synapse charm for the first time

## What you’ll do
- Deploy the Synapse charm.
- Integrate with the PostgreSQL K8s charm.
- Expose the Synapse charm by using Traefik K8s charm.
- Create a user.
- Access your Synapse instance using Element Desktop.

Through the process, you'll verify the workload state, and log in to your
Synapse instance using the Element Desktop application.

## Requirements

* A working station, e.g., a laptop, with amd64 architecture.
* Juju 3 installed and bootstrapped to a MicroK8s controller. You can accomplish
this process by using a [Multipass](https://multipass.run/) VM as outlined in this guide: [Set up your test environment](https://documentation.ubuntu.com/juju/3.6/howto/manage-your-juju-deployment/set-up-your-juju-deployment-local-testing-and-development/)

:warning: When using a Multipass VM, make sure to replace IP addresses with the
VM IP in steps that assume you're running locally. To get the IP address of the
Multipass instance run ``multipass info my-juju-vm``.

## Set up a tutorial model

To manage resources effectively and to separate this tutorial's workload from
your usual work, create a new model using the following command.

```
juju add-model synapse-tutorial
```

<!-- vale Canonical.007-Headings-sentence-case = NO -->
## Deploy the Synapse charm
<!-- vale Canonical.007-Headings-sentence-case = YES -->
Synapse requires connections to PostgreSQL. Deploy both charm applications.

### Deploy and integrate the charms
```
juju deploy postgresql-k8s --trust
juju deploy synapse --channel 2/edge
```

Run `juju status` to see the current status of the deployment. The Synapse
unit should be in a `blocked` status.

Set the server name by running the following command:
```
juju config synapse server_name=tutorial-synapse.juju.local
```

Run `juju status` again to see that the message has changed:

<!-- SPREAD SKIP -->

```
synapse/0*                 waiting   idle   10.1.74.70             Waiting for mas-database integration.
```

<!-- SPREAD SKIP END -->

Provide the integration between Synapse and PostgreSQL:
```
juju integrate synapse:mas-database postgresql-k8s
```

<!-- SPREAD 
juju wait-for application synapse --query='status=="active"' --timeout 10m
juju wait-for application postgresql-k8s --query='status=="active"' --timeout 10m
-->

Run `juju status` and wait until the Application status is `Active` as the
following example:

<!-- SPREAD SKIP -->

```
App                       Version                       Status  Scale  Charm                     Channel  Rev  Address         Exposed  Message
synapse                 3.2                           active      1  synapse                              17  10.152.183.68   no
```

<!-- SPREAD SKIP END -->

The deployment is complete when the status is `Active`.

## Integrate with Traefik

The [Traefik charm](https://github.com/canonical/traefik-k8s-operator) exposes
Juju applications to the outside of a Kubernetes cluster, without relying on the
ingress resource of Kubernetes.

If you want to make Synapse charm available to external clients, you need to
deploy the Traefik charm and integrate Synapse with it.

### Deploy the Traefik charm
```
juju deploy traefik-k8s --trust
```

Configure `external_hostname` as the same set for Synapse and the `routing_mode`:
```
juju config traefik-k8s external_hostname=juju.local
juju config traefik-k8s routing_mode=subdomain
```

With these settings, the Synapse hostname will have the Juju model name
appended to the front like `synapse-tutorial-synapse.juju.local`. 

Provide integration between Synapse and Traefik:
```
juju integrate synapse traefik-k8s
```

<!-- SPREAD 
juju wait-for application synapse --query='status=="active"' --timeout 10m
juju wait-for application traefik-k8s --query='status=="active"' --timeout 10m
-->

Now, you will need to go into your DNS settings and set the IP address of the
Traefik charm to the DNS entry you’re setting up. Getting the IP address can be
done using `juju status`.

<!-- SPREAD SKIP -->

```
Model             Controller          Cloud/Region        Version  SLA          Timestamp
synapse-tutorial  concierge-microk8s  microk8s/localhost  3.6.14   unsupported  18:10:46Z

App             Version  Status  Scale  Charm           Channel        Rev  Address         Exposed  Message
postgresql-k8s  14.15    active      1  postgresql-k8s  14/stable      495  10.152.183.23   no       
synapse                  active      1  synapse         2/edge         871  10.152.183.189  no       
traefik-k8s     2.11.0   active      1  traefik-k8s     latest/stable  263  10.152.183.88   no       Serving at http://juju.local

Unit               Workload  Agent  Address       Ports  Message
postgresql-k8s/0*  active    idle   10.1.233.203         Primary
synapse/0*         active    idle   10.1.233.205         
traefik-k8s/0*     active    idle   10.1.233.207         Serving at http://juju.local
```

<!-- SPREAD SKIP END -->

<!-- SPREAD
TRAEFIK_APP_IP=$(juju status --format json | jq -r '.applications."traefik-k8s".units."traefik-k8s/0".address')
-->

You can configure the resolution of `tutorial-synapse.juju.local` by adding an
"A" record with the IP address "10.1.233.207" to the appropriate zone in your
DNS server's configuration. Save the changes and ensure that DNS caches are
flushed or DNS services are restarted if necessary. This will allow clients
querying your DNS server to resolve `synapse-tutorial-synapse.juju.local` to the
specified IP address. Note that it might take a few minutes for the DNS changes
to take effect.

In case you don’t have access to a DNS: The browser uses entries in the
`/etc/hosts` file to override what is returned by a DNS server. So, to resolve
it to your Traefik IP, open the `/etc/hosts` file and add the line
`10.1.233.207 synapse-tutorial-synapse.juju.local`.

> Optional: run `echo "10.1.233.207 synapse-tutorial-synapse.juju.local" >> /etc/hosts`
to redirect the output of the command `echo` to the end of the file `/etc/hosts`.

<!-- SPREAD
echo "$TRAEFIK_APP_IP synapse-tutorial-synapse.juju.local" | sudo tee -a /etc/hosts
-->

After that, visit http://synapse-tutorial-synapse.juju.local in a browser and you'll be
presented with a screen with the following text: "It works! Synapse is running".

<!-- SPREAD
curl -H 'Host: synapse-tutorial-synapse.juju.local' http://synapse-tutorial-synapse.juju.local/
-->

## Create a user
Create a user by running the following command:
```
juju run synapse/0 register-user username=alice admin=no
```

The terminal output for the action will list the password like
``user-password: <password>``. Note this password as you will need
it in the next step.

<!-- vale Canonical.007-Headings-sentence-case = NO -->
## Access Synapse using the Element desktop client
<!-- vale Canonical.007-Headings-sentence-case = YES -->

Follow the [instructions](https://element.io/download) to
install Element Desktop.

Open it and click on “Sign in”. Then click on “Edit” to provide which server you
 want to use (`synapse-tutorial-synapse.juju.local`).

Now, you can fill in the username and password fields accordingly to the action
output. Then you should see a welcome page and it's ready to chat.

## Clean up the environment

Well done! You've successfully completed the Synapse tutorial. To remove the
model environment you created during this tutorial, use the following command.

<!-- SPREAD SKIP -->

```
juju destroy-model synapse-tutorial
```

<!-- SPREAD SKIP END -->