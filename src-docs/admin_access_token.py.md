<!-- markdownlint-disable -->

<a href="../src/admin_access_token.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `admin_access_token.py`
The Admin Access Token service. 

**Global Variables**
---------------
- **JUJU_HAS_SECRETS**
- **PEER_RELATION_NAME**
- **SECRET_ID**
- **SECRET_KEY**


---

## <kbd>class</kbd> `AdminAccessTokenService`
The Admin Access Token Service. 

Attrs:  _app: instance of Juju application.  _model: instance of Juju model. 

<a href="../src/admin_access_token.py#L34"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(app: Application, model: Model)
```

Initialize the service. 



**Args:**
 
 - <b>`app`</b>:  instance of Juju application. 
 - <b>`model`</b>:  instance of Juju model. 




---

<a href="../src/admin_access_token.py#L44"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `get`

```python
get(container: Container) → Optional[str]
```

Get an admin access token. 

If the admin token is not valid or it does not exist it creates one. 



**Args:**
 
 - <b>`container`</b>:  Workload container. 



**Returns:**
 admin access token or None if fails. 


