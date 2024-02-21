<!-- markdownlint-disable -->

<a href="../src/charm_state.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `charm_state.py`
State of the Charm. 


---

<a href="../src/charm_state.py#L39"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `inject_charm_state`

```python
inject_charm_state(
    method: Callable[[~C, ~E, ForwardRef('CharmState')], NoneType]
) → Callable[[~C, ~E], NoneType]
```

Create a decorator that injects the argument charm_state to an observer hook. 

If the configuration is invalid, it sets the state to Blocked and does not call the wrapped observer. 

This decorator can be used in an observer method of a CharmBaseWithState class or a class/instance that has an attribute _charm that points to a CharmBaseWithState instance. 

Because of https://github.com/canonical/operator/issues/1129, @functools.wraps cannot be used yet to have a properly created decorator. 



**Args:**
 
 - <b>`method`</b>:  observer method to wrap and inject the charm_state 



**Returns:**
 the function wrapper 


---

## <kbd>class</kbd> `CharmBaseWithState`
CharmBase than can build a CharmState. 


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

<a href="../src/charm_state.py#L30"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `build_charm_state`

```python
build_charm_state() → CharmState
```

Build charm state. 


---

## <kbd>class</kbd> `CharmConfigInvalidError`
Exception raised when a charm configuration is found to be invalid. 

Attrs:  msg (str): Explanation of the error. 

<a href="../src/charm_state.py#L101"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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



**Attributes:**
 
 - <b>`synapse_config`</b>:  synapse configuration. 
 - <b>`datasource`</b>:  datasource information. 
 - <b>`saml_config`</b>:  saml configuration. 
 - <b>`smtp_config`</b>:  smtp configuration. 
 - <b>`proxy`</b>:  proxy information. 


---

#### <kbd>property</kbd> proxy

Get charm proxy information from juju charm environment. 



**Returns:**
  charm proxy information in the form of ProxyConfig. 



---

<a href="../src/charm_state.py#L232"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `from_charm`

```python
from_charm(
    charm: CharmBase,
    datasource: Optional[DatasourcePostgreSQL],
    saml_config: Optional[SAMLConfiguration],
    smtp_config: Optional[SMTPConfiguration]
) → CharmState
```

Initialize a new instance of the CharmState class from the associated charm. 



**Args:**
 
 - <b>`charm`</b>:  The charm instance associated with this state. 
 - <b>`datasource`</b>:  datasource information to be used by Synapse. 
 - <b>`saml_config`</b>:  saml configuration to be used by Synapse. 
 - <b>`smtp_config`</b>:  SMTP configuration to be used by Synapse. 

Return: The CharmState instance created by the provided charm. 



**Raises:**
 
 - <b>`CharmConfigInvalidError`</b>:  if the charm configuration is invalid. 


---

## <kbd>class</kbd> `ProxyConfig`
Configuration for accessing Synapse through proxy. 



**Attributes:**
 
 - <b>`http_proxy`</b>:  The http proxy URL. 
 - <b>`https_proxy`</b>:  The https proxy URL. 
 - <b>`no_proxy`</b>:  Comma separated list of hostnames to bypass proxy. 





---

## <kbd>class</kbd> `SynapseConfig`
Represent Synapse builtin configuration values. 



**Attributes:**
 
 - <b>`allow_public_rooms_over_federation`</b>:  allow_public_rooms_over_federation config. 
 - <b>`enable_mjolnir`</b>:  enable_mjolnir config. 
 - <b>`enable_password_config`</b>:  enable_password_config config. 
 - <b>`enable_room_list_search`</b>:  enable_room_list_search config. 
 - <b>`federation_domain_whitelist`</b>:  federation_domain_whitelist config. 
 - <b>`ip_range_whitelist`</b>:  ip_range_whitelist config. 
 - <b>`notif_from`</b>:  defines the "From" address to use when sending emails. 
 - <b>`public_baseurl`</b>:  public_baseurl config. 
 - <b>`report_stats`</b>:  report_stats config. 
 - <b>`server_name`</b>:  server_name config. 
 - <b>`trusted_key_servers`</b>:  trusted_key_servers config. 




---

<a href="../src/charm_state.py#L164"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `get_default_notif_from`

```python
get_default_notif_from(notif_from: Optional[str], values: dict) → Optional[str]
```

Set server_name as default value to notif_from. 



**Args:**
 
 - <b>`notif_from`</b>:  the notif_from current value. 
 - <b>`values`</b>:  values already defined. 



**Returns:**
 The default value for notif_from if not defined. 

---

<a href="../src/charm_state.py#L183"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `to_yes_or_no`

```python
to_yes_or_no(value: str) → str
```

Convert the report_stats field to yes or no. 



**Args:**
 
 - <b>`value`</b>:  the input value. 



**Returns:**
 The string converted to yes or no. 


