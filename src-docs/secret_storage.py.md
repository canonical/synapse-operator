<!-- markdownlint-disable -->

<a href="../src/secret_storage.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `secret_storage.py`
Helper module used to manage interactions with Synapse secrets. 

**Global Variables**
---------------
- **PEER_RELATION_NAME**
- **SECRET_ID**
- **SECRET_KEY**

---

<a href="../src/secret_storage.py#L83"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `get_admin_access_token`

```python
get_admin_access_token(charm: CharmBase) → str
```

Get admin access token. 



**Args:**
 
 - <b>`charm`</b>:  The charm object. 



**Returns:**
 admin access token. 



**Raises:**
 
 - <b>`AdminAccessTokenNotFoundError`</b>:  if admin access token is not found. 


---

## <kbd>class</kbd> `AdminAccessTokenNotFoundError`
Exception raised when there is not admin access token. 

Attrs:  msg (str): Explanation of the error. 

<a href="../src/secret_storage.py#L30"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(msg: str)
```

Initialize a new instance of the AdminAccessTokenNotFoundError exception. 



**Args:**
 
 - <b>`msg`</b> (str):  Explanation of the error. 





