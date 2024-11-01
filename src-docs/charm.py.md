<!-- markdownlint-disable -->

<a href="../src/charm.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `charm.py`
Charm for Synapse on kubernetes. 

**Global Variables**
---------------
- **MAIN_UNIT_ID**
- **INGRESS_INTEGRATION_NAME**


---

## <kbd>class</kbd> `SynapseCharm`
Charm the service. 

Attrs:  on: listen to Redis events. 

<a href="../src/charm.py#L53"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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

<a href="../src/charm.py#L99"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `build_charm_state`

```python
build_charm_state() → CharmState
```

Build charm state. 



**Returns:**
  The current charm state. 

---

<a href="../src/charm.py#L333"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `get_main_unit`

```python
get_main_unit() → Optional[str]
```

Get main unit. 



**Returns:**
  main unit if main unit exists in peer relation data. 

---

<a href="../src/charm.py#L348"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `get_main_unit_address`

```python
get_main_unit_address() → str
```

Get main unit address. If main unit is None, use unit name. 



**Returns:**
  main unit address as unit-0.synapse-endpoints. 

---

<a href="../src/charm.py#L400"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `get_signing_key`

```python
get_signing_key() → Optional[str]
```

Get signing key from secret. 



**Returns:**
  Signing key as string or None if not found. 

---

<a href="../src/charm.py#L123"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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

<a href="../src/charm.py#L143"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `instance_map`

```python
instance_map() → Optional[Dict]
```

Build instance_map config. 



**Returns:**
  Instance map configuration as a dict or None if there is only one unit. 

---

<a href="../src/charm.py#L115"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `is_main`

```python
is_main() → bool
```

Verify if this unit is the main. 



**Returns:**
 
 - <b>`bool`</b>:  true if is the main unit. 

---

<a href="../src/charm.py#L309"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `peer_units_total`

```python
peer_units_total() → int
```

Get peer units total. 



**Returns:**
  total of units in peer relation or None if there is no peer relation. 

---

<a href="../src/charm.py#L186"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `reconcile`

```python
reconcile(charm_state: CharmState) → None
```

Reconcile Synapse configuration with charm state. 

This is the main entry for changes that require a restart. 



**Args:**
 
 - <b>`charm_state`</b>:  Instance of CharmState 

---

<a href="../src/charm.py#L360"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `set_main_unit`

```python
set_main_unit(unit: str) → None
```

Create/Renew an admin access token and put it in the peer relation. 



**Args:**
 
 - <b>`unit`</b>:  Unit to be the main. 

---

<a href="../src/charm.py#L376"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `set_signing_key`

```python
set_signing_key(signing_key: str) → None
```

Create secret with signing key content. 



**Args:**
 
 - <b>`signing_key`</b>:  signing key as string. 


