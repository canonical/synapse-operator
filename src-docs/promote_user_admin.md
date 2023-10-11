<!-- markdownlint-disable -->

<a href="../src/actions/promote_user_admin.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `promote_user_admin`
Module to interact with Promote User Admin action. 


---

<a href="../src/actions/promote_user_admin.py#L32"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `promote_user_admin`

```python
promote_user_admin(username: str, server: str, admin_access_token: str) → None
```

Run promote user admin action. 



**Args:**
 
 - <b>`username`</b>:  username to be promoted. 
 - <b>`server`</b>:  to be used to promote the user id. 
 - <b>`admin_access_token`</b>:  server admin access token to call API. 



**Raises:**
 
 - <b>`PromoteUserAdminError`</b>:  if something goes wrong while promoting the user to  be an admin. 


---

<a href="../src/actions/promote_user_admin.py#L16"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `PromoteUserAdminError`
Exception raised when something fails while running promote-user-admin. 

Attrs:  msg (str): Explanation of the error. 

<a href="../src/actions/promote_user_admin.py#L23"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(msg: str)
```

Initialize a new instance of the PromoteUserAdminError exception. 



**Args:**
 
 - <b>`msg`</b> (str):  Explanation of the error. 





