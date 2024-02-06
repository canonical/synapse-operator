<!-- markdownlint-disable -->

<a href="../src/user.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `user.py`
User class. 



---

## <kbd>class</kbd> `User`
Synapse user. 



**Attributes:**
 
 - <b>`username`</b>:  username to be registered. 
 - <b>`admin`</b>:  if user is an admin. 
 - <b>`password`</b>:  users password. 
 - <b>`access_token`</b>:  obtained when the user is registered. 

<a href="../src/user.py#L44"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(username: str, admin: bool) → None
```

Initialize the User. 



**Args:**
 
 - <b>`username`</b>:  username to be registered. 
 - <b>`admin`</b>:  if is admin. 




---

<a href="../src/user.py#L55"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `username_must_not_be_empty`

```python
username_must_not_be_empty(v: str) → str
```

Check if username is empty. 



**Args:**
 
 - <b>`v`</b>:  value received. 



**Raises:**
 
 - <b>`ValueError`</b>:  if username is empty 



**Returns:**
 username. 


