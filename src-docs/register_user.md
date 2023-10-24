<!-- markdownlint-disable -->

<a href="../src/actions/register_user.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `register_user`
Module to interact with Register User action. 


---

<a href="../src/actions/register_user.py#L39"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `register_user`

```python
register_user(
    container: Container,
    username: str,
    admin: bool,
    admin_access_token: Optional[str] = None,
    server: str = ''
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

<a href="../src/actions/register_user.py#L22"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `RegisterUserError`
Exception raised when something fails while running register-user. 

Attrs:  msg (str): Explanation of the error. 

<a href="../src/actions/register_user.py#L29"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(msg: str)
```

Initialize a new instance of the RegisterUserError exception. 



**Args:**
 
 - <b>`msg`</b> (str):  Explanation of the error. 





