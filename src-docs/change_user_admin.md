<!-- markdownlint-disable -->

<a href="../src/actions/change_user_admin.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `change_user_admin`
Module to interact with Change User Admin action. 


---

<a href="../src/actions/change_user_admin.py#L34"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `change_user_admin`

```python
change_user_admin(
    username: str,
    server: Optional[str],
    admin_access_token: Optional[str]
) → None
```

Run register user action. 



**Args:**
 
 - <b>`username`</b>:  username to be changed. 
 - <b>`server`</b>:  to be used to create the user id. 
 - <b>`admin_access_token`</b>:  server admin access token to call API. 



**Raises:**
 
 - <b>`ChangeUserAdminError`</b>:  if something goes wrong while changing the user to  be an admin. 


---

<a href="../src/actions/change_user_admin.py#L17"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `ChangeUserAdminError`
Exception raised when something fails while running change-user-admin. 

Attrs:  msg (str): Explanation of the error. 

<a href="../src/actions/change_user_admin.py#L24"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(msg: str)
```

Initialize a new instance of the ChangeUserAdminError exception. 



**Args:**
 
 - <b>`msg`</b> (str):  Explanation of the error. 





