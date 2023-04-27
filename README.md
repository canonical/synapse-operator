<!--
Avoid using this README file for information that is maintained or published elsewhere, e.g.:

* metadata.yaml > published on Charmhub
* documentation > published on (or linked to from) Charmhub
* detailed contribution guide > documentation or CONTRIBUTING.md

Use links instead.
-->

# matrix-main-operator

Charmhub package name: matrix-operator
More information: https://charmhub.io/matrix-operator

Describe your charm in one or two sentences.

## Taking this for a spin - terraform version (WIP)

Make sure you have a setup with juju and microk8s.
You need to have some environment variables set up
for the provider to work, reference [here](https://github.com/juju/terraform-provider-juju).
After that is done, you should be good to go with:

```shell
cd terraform/
terraform init
terraform plan
terraform apply -auto-approve
juju switch synapsium #or how you called your model
juju status
```

## Taking this for a spin - manual version

* build the charm with `charmcraft pack`

* build the nginx_rock

* deploy it in a model with `juju deploy ./synapse_ubuntu-22.04-amd64.charm --resource synapse-image=matrixdotorg/synapse:latest --resource synapse-nginx-image=localhost:32000/synapse-nginx:latest --trust`

* deploy redis-k8s with `juju deploy redis-k8s`

* relate to synapse with `juju relate synapse redis-k8s`

* deploy postgresql-k8s with `juju deploy postgresql-k8s`

* relate to synapse with `juju relate postgresql-k8s:db synapse`

* config the server name as the one used in traefik with `juju config synapse server_name=<model-name>-synapse.juju.local`

* deploy postgresql-k8s with `juju deploy traefik-k8s  traefik-synapse --trust`

* config external hostname in traefik with `juju config traefik-synapse external_hostname=juju.local`

* config route mode in traefik with `juju config traefik-synapse routing_mode=subdomain`

* relate to synapse with `juju relate synapse traefik-synapse`

* create a user with `juju run-action synapse/0 register-user username=alice password=hialice admin=no`

* Add the server name and Traefik IP in your /etc/hosts. Example:
`10.152.183.110 testing11-synapse.juju.local`

* login via element-desktop (server name = <model-name>-synapse.juju.local)

## TODO

* get the synapse server running with basic settings (defaults plus server name and report stats) - done

* get the server to use a postgresql backend - done

* get the server to be accessible via ingress - done

* be able to create a user (via config change at this point) - done

* deal with configuration changes consistently (merge existing with new)

* move config in a storage - done

* explore an SSO option for signup

* check on Redis option present in architecture - done

* see how charm behaves when scaling in/out - done/wip

* see how to disable users locally

* see how/when an SSO user is invalidated

* think about test cases for basic functionality

* look into using the new postgresql interface (the current one used is being deprecated) - done

* demo (spin up the charm with relations, configure two users, get them to chat via a client) - done

## Other resources

<!-- If your charm is documented somewhere else other than Charmhub, provide a link separately. -->

- [Read more](https://example.com)

- [Contributing](CONTRIBUTING.md) <!-- or link to other contribution documentation -->

- See the [Juju SDK documentation](https://juju.is/docs/sdk) for more information about developing and improving charms.
