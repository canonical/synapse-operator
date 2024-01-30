<!-- markdownlint-disable -->

<a href="../src/synapse/admin.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `admin`
Helper module used to manage admin tasks involving Synapse API and Workload. 


---

<a href="../src/synapse/admin.py#L21"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `create_admin_user`

```python
create_admin_user(container: Container) → Optional[User]
```

Create admin user. 



**Args:**
 
 - <b>`container`</b>:  Container of the charm. 



**Returns:**
 Admin user with token to be used in Synapse API requests or None if fails. 


---

<a href="../src/synapse/admin.py#L43"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `create_user`

```python
create_user(
    container: Container,
    username: str,
    admin: bool = False,
    admin_access_token: Optional[str] = None,
    server: str = ''
) → Optional[User]
```

Create user by using the registration shared secret and generating token via API. 



**Args:**
 
 - <b>`container`</b>:  Container of the charm. 
 - <b>`username`</b>:  username to be registered. 
 - <b>`admin`</b>:  if user is admin. 
 - <b>`server`</b>:  to be used to create the user id. 
 - <b>`admin_access_token`</b>:  server admin access token to get user's access token if it exists. 



**Returns:**
 User or none if the creation fails. 


