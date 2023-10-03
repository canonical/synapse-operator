<!-- markdownlint-disable -->

<a href="../src/actions/change_user_admin.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `change_user_admin`
Module to interact with Register User action. 


---

<a href="../src/actions/change_user_admin.py#L38"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `register_user`

```python
register_user(
    container: Container,
    username: str,
    admin: bool,
    server: str = '',
    admin_access_token: str = ''
) → User
```

Run register user action. 



**Args:**
 
 - <b>`container`</b>:  Container of the charm. 
 - <b>`username`</b>:  username to be registered. 
 - <b>`admin`</b>:  if user is admin. 
 - <b>`server`</b>:  to be used to create the user id. 
 - <b>`admin_access_token`</b>:  server admin access token to get user's access token if it exists. 



**Raises:**
 
 - <b>`RegisterUserError`</b>:  if something goes wrong while registering the user. 



**Returns:**
 User with password registered. 


---

<a href="../src/actions/change_user_admin.py#L21"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `RegisterUserError`
Exception raised when something fails while running register-user. 

Attrs:  msg (str): Explanation of the error. 

<a href="../src/actions/change_user_admin.py#L28"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(msg: str)
```

Initialize a new instance of the RegisterUserError exception. 



**Args:**
 
 - <b>`msg`</b> (str):  Explanation of the error. 





