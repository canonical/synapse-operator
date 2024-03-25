<!-- markdownlint-disable -->

<a href="../src/charm.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `charm.py`
Charm for Synapse on kubernetes. 

**Global Variables**
---------------
- **MAIN_UNIT_ID**


---

## <kbd>class</kbd> `SynapseCharm`
Charm the service. 

Attrs:  on: listen to Redis events. 

<a href="../src/charm.py#L51"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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

<a href="../src/charm.py#L104"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `build_charm_state`

```python
build_charm_state() → CharmState
```

Build charm state. 



**Returns:**
  The current charm state. 

---

<a href="../src/charm.py#L160"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `change_config`

```python
change_config(charm_state: CharmState) → None
```

Change configuration. 



**Args:**
 
 - <b>`charm_state`</b>:  Instance of CharmState 

---

<a href="../src/charm.py#L289"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `get_main_unit`

```python
get_main_unit() → Optional[str]
```

Get main unit. 



**Returns:**
  main unit if peer relation or self unit name. 

---

<a href="../src/charm.py#L127"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `instance_map`

```python
instance_map() → Dict
```

Build instance_map config. 



**Returns:**
  Instance map configuration as a dict. 

---

<a href="../src/charm.py#L119"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `is_main`

```python
is_main() → bool
```

Verify if this unit is the main. 



**Returns:**
 
 - <b>`bool`</b>:  true if is the main unit. 

---

<a href="../src/charm.py#L266"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `peer_units_total`

```python
peer_units_total() → int
```

Get peer units total. 



**Returns:**
  total of units in peer relation or None if there is no peer relation. 

---

<a href="../src/charm.py#L304"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `set_main_unit`

```python
set_main_unit(unit: str) → None
```

Create/Renew an admin access token and put it in the peer relation. 



**Args:**
 
 - <b>`unit`</b>:  Unit to be the main. 


