# Deploy the Synapse charm for the first time (v2)

## What you'll do
- Deploy the Synapse charm.
- Integrate with the PostgreSQL K8s charm.
- Expose the Synapse charm by using the Traefik K8s charm.
- Create a user.
- Access your Synapse instance using the Element Desktop application.

Through the process, you'll verify the workload state, and log in to your
Synapse instance using the Element Desktop client.

## Requirements

- A working station, for example a laptop, with amd64 architecture.
- Juju 3 installed and bootstrapped to a MicroK8s controller. You can
  accomplish this process by using a [Multipass](https://multipass.run/) VM
  as outlined in this guide: [Set up your test environment](https://documentation.ubuntu.com/juju/3.6/howto/manage-your-juju-deployment/set-up-your-juju-deployment-local-testing-and-development/).

> When using a Multipass VM, replace IP addresses with the VM IP in steps that
> assume you're running locally. To get the VM IP, run
> `multipass info my-juju-vm`.

## Set up a tutorial model

To manage resources effectively and to separate this tutorial's workload from
your usual work, create a new model:

```bash
juju add-model synapse-tutorial
```

## Deploy the Synapse charm

Synapse requires a PostgreSQL integration.

```bash
juju deploy postgresql-k8s --trust
juju deploy synapse
```

Run `juju status` to see the current status of the deployment. The Synapse unit
should be in a `waiting` status.

Set the server name:

```bash
juju config synapse server_name=tutorial-synapse.juju.local
```

Provide the PostgreSQL relation:

```bash
juju integrate synapse:database postgresql-k8s
```

Wait for both applications to become active:

```bash
juju wait-for application synapse --query='status=="active"' --timeout 10m
juju wait-for application postgresql-k8s --query='status=="active"' --timeout 10m
```

## Integrate with Traefik

The [Traefik charm](https://github.com/canonical/traefik-k8s-operator) exposes
Juju applications to the outside of a Kubernetes cluster.

Deploy Traefik:

```bash
juju deploy traefik-k8s --trust
```

Configure `external_hostname` and `routing_mode`:

```bash
juju config traefik-k8s external_hostname=juju.local
juju config traefik-k8s routing_mode=subdomain
```

With these settings, the Synapse hostname includes the Juju model name, for
example: `synapse-tutorial-synapse.juju.local`.

Integrate Synapse and Traefik:

```bash
juju integrate synapse traefik-k8s
```

Wait for applications to settle:

```bash
juju wait-for application synapse --query='status=="active"' --timeout 10m
juju wait-for application traefik-k8s --query='status=="active"' --timeout 10m
```

Get the Traefik **unit** IP address (not the `traefik-k8s` application
address). Run:

```bash
juju status traefik-k8s
```

In the `Unit` section, copy the `Address` value of `traefik-k8s/0`, then add
it to `/etc/hosts`:

```bash
echo "<traefik-unit-ip> synapse-tutorial-synapse.juju.local" | sudo tee -a /etc/hosts
```

Then verify access:

```bash
curl -H 'Host: synapse-tutorial-synapse.juju.local' http://synapse-tutorial-synapse.juju.local/
```

After that, visit `http://synapse-tutorial-synapse.juju.local` in your browser.
You should see: "It works! Synapse is running".

## Create a user

Create a user:

```bash
juju run synapse/0 register-user username=alice admin=no
```

The action output includes `user-password: <password>`. Save that password for
the next step.

## Access Synapse using Element Desktop

Follow the [instructions](https://element.io/download) to install Element
Desktop.

Open Element and click **Sign in**. Click **Edit** and set the homeserver to
`synapse-tutorial-synapse.juju.local`.

Fill in the username and password from the previous step. You should then see
the welcome page.

## Clean up the environment

To remove the model created in this tutorial:

```bash
juju destroy-model synapse-tutorial
```
