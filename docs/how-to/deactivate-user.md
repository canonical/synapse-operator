# How to deactivate a user

[note]
This document applies only to Synapse channels `1/stable` and `1/edge`.
[/note]

The Synapse charm provides an action called `anonymize-user`, which can also be
used to deactivate a user.

Keep in mind that using this action will also:

- Remove the user's display name.
- Remove the user's avatar URL.
- Mark the user as erased.

You can trigger the action with a command like in the following example where the user is `@joe123:myserver.com`:

```
juju run synapse/0 anonymize-user username=joe123
```


If you prefer to only deactivate the user and not mark them as erased, you can
use the deactivate-account [API](https://element-hq.github.io/synapse/latest/admin_api/user_admin_api.html#deactivate-account) call instead:


```
curl -XPOST   -d '{"type":"m.login.password", "user":"myadmin", "password":"xxx"}' https://chat.myserver.com/_matrix/client/r0/login
```
Get the token:
```
curl -XPOST 'https://chat.myserver.com/_synapse/admin/v1/deactivate/%40joe123%3Amyserver.com?access_token=...'
```
If successful, the terminal output `{"id_server_unbind_result":"success"}`.
