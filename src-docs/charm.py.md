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

<a href="../src/charm.py#L52"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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

<a href="../src/charm.py#L107"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `build_charm_state`

```python
build_charm_state() → CharmState
```

Build charm state. 



**Returns:**
  The current charm state. 

---

<a href="../src/charm.py#L249"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `change_config`

```python
change_config(charm_state: CharmState) → None
```

Change configuration. 



**Args:**
 
 - <b>`charm_state`</b>:  Instance of CharmState 

---

<a href="../src/charm.py#L153"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `get_main_unit`

```python
get_main_unit() → str
```

Get main unit. 



**Returns:**
  main unit if main unit exists in peer relation data. 

---

<a href="../src/charm.py#L170"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `get_main_unit_address`

```python
get_main_unit_address() → str
```

Get main unit address. If main unit is None, use unit name. 



**Returns:**
  main unit address as unit-0.synapse-endpoints. 

---

<a href="../src/charm.py#L179"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `get_peer_unit_addresses`

```python
get_peer_unit_addresses() → list[str]
```

Get peer unit addresses. 



**Returns:**
 
 - <b>`set`</b>:  Addresses like  <unit-name>.<app-name>-endpoints.<model-name>.svc.cluster.local 

---

<a href="../src/charm.py#L133"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `get_unit_number`

```python
get_unit_number(unit_name: str = '') → str
```

Get unit number from unit name. 



**Args:**
 
 - <b>`unit_name`</b>:  unit name or address. E.g.: synapse/0 or synapse-0.synapse-endpoints. 



**Returns:**
 
 - <b>`Unit number. E.g.`</b>:  0 

---

<a href="../src/charm.py#L196"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `instance_map`

```python
instance_map() → Optional[Dict]
```

Build instance_map config. 



**Returns:**
  Instance map configuration as a dict or None if there is only one unit. 

---

<a href="../src/charm.py#L125"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `peer_units_total`

```python
peer_units_total() → int
```

Get peer units total. 



**Returns:**
  total of units in peer relation or None if there is no peer relation. 


