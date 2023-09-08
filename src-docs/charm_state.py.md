<!-- markdownlint-disable -->

<a href="../src/charm_state.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `charm_state.py`
State of the Charm. 

**Global Variables**
---------------
- **KNOWN_CHARM_CONFIG**


---

## <kbd>class</kbd> `CharmConfigInvalidError`
Exception raised when a charm configuration is found to be invalid. 

Attrs:  msg (str): Explanation of the error. 

<a href="../src/charm_state.py#L40"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(msg: str)
```

Initialize a new instance of the CharmConfigInvalidError exception. 



**Args:**
 
 - <b>`msg`</b> (str):  Explanation of the error. 





---

## <kbd>class</kbd> `CharmState`
State of the Charm. 

Attrs:  server_name: server_name config.  report_stats: report_stats config.  public_baseurl: public_baseurl config.  enable_mjolnir: enable_mjolnir config.  datasource: datasource information.  saml_config: saml configuration. 

<a href="../src/charm_state.py#L101"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(
    synapse_config: SynapseConfig,
    datasource: Optional[DatasourcePostgreSQL],
    saml_config: Optional[SAMLConfiguration]
) → None
```

Construct. 



**Args:**
 
 - <b>`synapse_config`</b>:  The value of the synapse_config charm configuration. 
 - <b>`datasource`</b>:  Datasource information. 
 - <b>`saml_config`</b>:  SAML configuration. 


---

#### <kbd>property</kbd> datasource

Return datasource. 



**Returns:**
  datasource or None. 

---

#### <kbd>property</kbd> enable_mjolnir

Return enable_mjolnir config. 



**Returns:**
 
 - <b>`bool`</b>:  enable_mjolnir config. 

---

#### <kbd>property</kbd> public_baseurl

Return public_baseurl config. 



**Returns:**
 
 - <b>`str`</b>:  public_baseurl config. 

---

#### <kbd>property</kbd> report_stats

Return report_stats config. 



**Returns:**
 
 - <b>`str`</b>:  report_stats config as yes or no. 

---

#### <kbd>property</kbd> saml_config

Return SAML configuration. 



**Returns:**
  SAMLConfiguration or None. 

---

#### <kbd>property</kbd> server_name

Return server_name config. 



**Returns:**
 
 - <b>`str`</b>:  server_name config. 



---

<a href="../src/charm_state.py#L173"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `from_charm`

```python
from_charm(charm: 'SynapseCharm') → CharmState
```

Initialize a new instance of the CharmState class from the associated charm. 



**Args:**
 
 - <b>`charm`</b>:  The charm instance associated with this state. 

Return: The CharmState instance created by the provided charm. 



**Raises:**
 
 - <b>`CharmConfigInvalidError`</b>:  if the charm configuration is invalid. 


---

## <kbd>class</kbd> `SynapseConfig`
Represent Synapse builtin configuration values. 

Attrs:  server_name: server_name config.  report_stats: report_stats config.  public_baseurl: public_baseurl config.  enable_mjolnir: enable_mjolnir config. 




---

<a href="../src/charm_state.py#L73"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `to_yes_or_no`

```python
to_yes_or_no(value: str) → str
```

Convert the report_stats field to yes or no. 



**Args:**
 
 - <b>`value`</b>:  the input value. 



**Returns:**
 The string converted to yes or no. 


