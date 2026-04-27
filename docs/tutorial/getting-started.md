(tutorial_getting_started)=

# Deploy the Synapse charm for the first time

## What you’ll do

- Deploy the Synapse charm.
- Integrate with the PostgreSQL K8s charm.
- Expose the Synapse charm by using Traefik K8s charm.
- Create a user.
- Access your Synapse instance via Element Desktop.

Through the process, you'll verify the workload state, and log in to your
Synapse instance via Element Desktop application.

## Requirements

* A working station, e.g., a laptop, with amd64 architecture.
* Juju 3 installed and bootstrapped to a MicroK8s controller. You can accomplish
this process by using a [Multipass](https://multipass.run/) VM as outlined in this guide: [Set up / Tear down your test environment](https://juju.is/docs/juju/set-up--tear-down-your-test-environment)

```{warning}
When using a Multipass VM, make sure to replace IP addresses with the
VM IP in steps that assume you're running locally. To get the IP address of the
Multipass instance run ``multipass info my-juju-vm``.
```

## Set up a Tutorial Model

To manage resources effectively and to separate this tutorial's workload from
your usual work, create a new model using the following command.

```bash
juju add-model synapse-tutorial
```

## Deploy the Synapse charm

Synapse requires connections to PostgreSQL. Deploy both charm applications.

### Deploy and integrate the charms

```bash
juju deploy postgresql-k8s --trust
juju deploy synapse
```

Run `juju status` to see the current status of the deployment.

Wait until the Synapse unit is in a `blocked` status, waiting for the required `server_name` configuration.

```bash
juju wait-for application synapse --query='status=="blocked"' --timeout 10m
```

Once in `blocked` status, set the server name by running the following command:

```bash
juju config synapse server_name=synapse-tutorial-synapse.juju.local
```

Running `juju status` again, you will see Synapse move into `maintenance` status.

<!-- SPREAD SKIP -->

```{terminal}
:output-only:

Unit               Workload     Agent      Address      Ports  Message
synapse/0*         maintenance  executing  10.1.65.170         Configuring Synapse
```

<!-- SPREAD SKIP END -->

Wait until the Synapse unit is in back to an `active` status:

```bash
juju wait-for application synapse --query='status=="active"' --timeout 10m
```

Provide the integration between Synapse and PostgreSQL:

```bash
juju integrate synapse:database postgresql-k8s
```

Running `juju status`, you will see Synapse and PostgreSQL both start executing the integration request.

<!-- SPREAD SKIP -->

```{terminal}
:output-only:

Model             Controller          Cloud/Region        Version  SLA          Timestamp
synapse-tutorial  concierge-microk8s  microk8s/localhost  3.6.14   unsupported  14:58:26-04:00

App             Version  Status       Scale  Charm           Channel        Rev  Address         Exposed  Message
postgresql-k8s  14.20    active           1  postgresql-k8s  14/stable      774  10.152.183.189  no       
synapse         1.115.0  maintenance      1  synapse         latest/stable  426  10.152.183.212  no       Configuring Synapse

Unit               Workload     Agent      Address      Ports  Message
postgresql-k8s/0*  active       executing  10.1.65.156         Primary
synapse/0*         maintenance  executing  10.1.65.170         Configuring Synapse 
```

<!-- SPREAD SKIP END -->

Wait until the both applications become `active`:

```bash
juju wait-for application synapse --query='status=="active"' --timeout 10m
juju wait-for application postgresql-k8s --query='status=="active"' --timeout 10m
```

## Integrate with Traefik

The {ref}`Traefik charm <traefik-k8s-charm:index>` exposes
Juju applications to the outside of a Kubernetes cluster, without relying on the
ingress resource of Kubernetes.

If you want to make Synapse charm available to external clients, you need to
deploy the Traefik charm and integrate Synapse with it.

### Deploy the Traefik charm

```bash
juju deploy traefik-k8s --trust
```

Wait until Traefik is active:

```bash
juju wait-for application traefik-k8s --query='status=="active"' --timeout 10m
```

Configure `external_hostname` (same set for Synapse) and `routing_mode`:

```bash
juju config traefik-k8s external_hostname=juju.local
juju config traefik-k8s routing_mode=subdomain
```

Wait until Traefik has completed its configuration change:

```bash
juju wait-for application traefik-k8s --query='status=="active"' --timeout 10m
```

With these settings, the Synapse hostname will have the Juju model name
appended to the front like `synapse-tutorial-synapse.juju.local`. 

Provide integration between Synapse and Traefik:

```bash
juju integrate synapse traefik-k8s
```

Wait until Traefik and synapse have completed the integration request:

```bash
juju wait-for application synapse --query='status=="active"' --timeout 10m
juju wait-for application traefik-k8s --query='status=="active"' --timeout 10m
```

Now, you will need to go into your DNS settings and set the IP address of the
Traefik charm to the DNS entry you’re setting up. Getting the IP address can be
done using `juju status`.

<!-- SPREAD SKIP -->

```{terminal}
:output-only:

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

You can configure the resolution of `synapse-tutorial-synapse.juju.local` by adding an
"A" record with the **Unit** IP address "10.1.233.207" to the appropriate zone in your
DNS server's configuration. Save the changes and ensure that DNS caches are
flushed or DNS services are restarted if necessary. This will allow clients
querying your DNS server to resolve `synapse-tutorial-synapse.juju.local` to the
specified IP address. Note that it might take a few minutes for the DNS changes
to take effect.

In case you don’t have access to a DNS: The browser uses entries in the
`/etc/hosts` file to override what is returned by a DNS server. So, to resolve
it to your Traefik IP, open the `/etc/hosts` file and add the following line
accordingly:

```bash
TRAEFIK_UNIT_IP=$(juju status --format json | jq -r '.applications["traefik-k8s"].units | to_entries[0].value.address')
echo "$TRAEFIK_UNIT_IP synapse-tutorial-synapse.juju.local" | sudo tee -a /etc/hosts
```

Then verify access:

```bash
curl -H 'Host: synapse-tutorial-synapse.juju.local' http://synapse-tutorial-synapse.juju.local/
```

After that, visit `http://synapse-tutorial-synapse.juju.local` in your browser.
You should see: "It works! Synapse is running".

## Create a user

Create a user by running the following command:

```bash
juju run synapse/0 register-user username=alice admin=no
```

The action output includes `user-password: <password>`. Save that password for
the next step.

## Access via Element Desktop

Follow the [instructions](https://element.io/download) to
install Element Desktop.

Open Element and click **Sign in**. Click **Edit** and set the homeserver to
`synapse-tutorial-synapse.juju.local`.

Fill in the username and password from the previous step. You should then see
the welcome page.

## Clean up the Environment

Well done! You've successfully completed the Synapse tutorial. To remove the
model environment you created during this tutorial, use the following command.

<!-- SPREAD SKIP -->

```bash
juju destroy-model synapse-tutorial
```

<!-- SPREAD SKIP END -->

<!-- SPREAD
juju destroy-model synapse-tutorial --release-storage --no-prompt
-->
