# How to deactivate a user

**Note:** This document applies only to Synapse channels `1/stable` and `1/edge`.

The Synapse charm provides an action called `anonymize-user`, which can also be
used to deactivate a user.

Keep in mind that using this action will also:

- Remove the user's display name
- Remove the user's avatar URL
- Mark the user as erased

You can trigger the action with a command like the following example:

The user is `@joe123:myserver.com`.

```
juju run synapse/0 anonymize-user username=joe123
```


If you prefer not to mark the user as erased and only deactivate them, you can
use the deactivate-account [API](https://element-hq.github.io/synapse/latest/admin_api/user_admin_api.html#deactivate-account) call instead:


```
$ curl -XPOST   -d '{"type":"m.login.password", "user":"myadmin", "password":"xxx"}' https://chat-server.myserver.com/_matrix/client/r0/login
# get the token
$ curl -XPOST 'https://chat.myserver.com/_synapse/admin/v1/deactivate/%40joe123%3Amyserver.com?access_token=...'
{"id_server_unbind_result":"success"}
```
