<!-- markdownlint-disable -->

<a href="../src/charm.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `charm.py`
Charm for Synapse on kubernetes. 

**Global Variables**
---------------
- **JUJU_HAS_SECRETS**
- **PEER_RELATION_NAME**
- **SECRET_ID**
- **SECRET_KEY**


---

## <kbd>class</kbd> `SynapseCharm`
Charm the service. 

<a href="../src/charm.py#L48"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(*args: Any) → None
```

Construct. 



**Args:**
 
 - <b>`args`</b>:  class arguments. 


---

#### <kbd>property</kbd> app

Application that this unit is part of. 

---

#### <kbd>property</kbd> charm_dir

Root directory of the charm as it is running. 

---

#### <kbd>property</kbd> config

A mapping containing the charm's config and current values. 

---

#### <kbd>property</kbd> meta

Metadata of this charm. 

---

#### <kbd>property</kbd> model

Shortcut for more simple access the model. 

---

#### <kbd>property</kbd> unit

Unit that this execution is responsible for. 



---

<a href="../src/charm.py#L109"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `change_config`

```python
change_config() → None
```

Change configuration. 

---

<a href="../src/charm.py#L266"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `get_admin_access_token`

```python
get_admin_access_token() → Optional[str]
```

Get admin access token. 



**Returns:**
  admin access token or None if fails. 


