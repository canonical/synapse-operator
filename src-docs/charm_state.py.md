<!-- markdownlint-disable -->

<a href="../src/charm_state.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `charm_state.py`
State of the Charm. 


---

<a href="../src/charm_state.py#L64"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `inject_charm_state`

```python
inject_charm_state(
    method: Callable[[~C, ~E, ForwardRef('CharmState')], NoneType]
) → Callable[[~C, ~E], NoneType]
```

Create a decorator that injects the argument charm_state to an observer hook. 

If the configuration is invalid, set the charm state to Blocked if it is a Hook or the event to failed if it is an Action and do not call the wrapped observer. 

This decorator can be used in a class that observes a hook/action and that defines de get_charm function to get a charm that implements CharmBaseWithState. 

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

<a href="../src/charm_state.py#L40"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `build_charm_state`

```python
build_charm_state() → CharmState
```

Build charm state. 

---

<a href="../src/charm_state.py#L44"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `get_charm`

```python
get_charm() → CharmBaseWithState
```

Return the current charm. 



**Returns:**
  The current charm 


---

## <kbd>class</kbd> `CharmConfigInvalidError`
Exception raised when a charm configuration is found to be invalid. 

Attrs:  msg (str): Explanation of the error. 

<a href="../src/charm_state.py#L127"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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
 - <b>`irc_bridge_datasource`</b>:  irc bridge datasource information. 
 - <b>`saml_config`</b>:  saml configuration. 
 - <b>`smtp_config`</b>:  smtp configuration. 
 - <b>`media_config`</b>:  media configuration. 
 - <b>`redis_config`</b>:  redis configuration. 
 - <b>`proxy`</b>:  proxy information. 
 - <b>`instance_map_config`</b>:  Instance map configuration with main and worker addresses. 
 - <b>`leader`</b>:  Is leader. 


---

#### <kbd>property</kbd> proxy

Get charm proxy information from juju charm environment. 



**Returns:**
  charm proxy information in the form of ProxyConfig. 



---

<a href="../src/charm_state.py#L306"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `from_charm`

```python
from_charm(
    charm: CharmBase,
    datasource: Optional[DatasourcePostgreSQL],
    irc_bridge_datasource: Optional[DatasourcePostgreSQL],
    saml_config: Optional[SAMLConfiguration],
    smtp_config: Optional[SMTPConfiguration],
    media_config: Optional[MediaConfiguration],
    redis_config: Optional[RedisConfiguration],
    instance_map_config: Optional[Dict],
    leader: bool
) → CharmState
```

Initialize a new instance of the CharmState class from the associated charm. 



**Args:**
 
 - <b>`charm`</b>:  The charm instance associated with this state. 
 - <b>`datasource`</b>:  datasource information to be used by Synapse. 
 - <b>`irc_bridge_datasource`</b>:  irc bridge datasource information to be used by Synapse. 
 - <b>`saml_config`</b>:  saml configuration to be used by Synapse. 
 - <b>`smtp_config`</b>:  SMTP configuration to be used by Synapse. 
 - <b>`media_config`</b>:  Media configuration to be used by Synapse. 
 - <b>`redis_config`</b>:  Redis configuration to be used by Synapse. 
 - <b>`instance_map_config`</b>:  Instance map configuration with main and worker addresses. 
 - <b>`leader`</b>:  is leader. 

Return: The CharmState instance created by the provided charm. 



**Raises:**
 
 - <b>`CharmConfigInvalidError`</b>:  if the charm configuration is invalid. 


---

## <kbd>class</kbd> `HasCharmWithState`
Protocol that defines a class that returns a CharmBaseWithState. 




---

<a href="../src/charm_state.py#L56"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `get_charm`

```python
get_charm() → CharmBaseWithState
```

Get the charm that can build a state. 


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
 - <b>`enable_email_notifs`</b>:  enable_email_notifs config. 
 - <b>`enable_irc_bridge`</b>:  creates a registration file in Synapse and starts an irc bridge app. 
 - <b>`irc_bridge_admins`</b>:  a comma separated list of user IDs who are admins of the IRC bridge. 
 - <b>`enable_mjolnir`</b>:  enable_mjolnir config. 
 - <b>`enable_password_config`</b>:  enable_password_config config. 
 - <b>`enable_room_list_search`</b>:  enable_room_list_search config. 
 - <b>`federation_domain_whitelist`</b>:  federation_domain_whitelist config. 
 - <b>`ip_range_whitelist`</b>:  ip_range_whitelist config. 
 - <b>`notif_from`</b>:  defines the "From" address to use when sending emails. 
 - <b>`public_baseurl`</b>:  public_baseurl config. 
 - <b>`publish_rooms_allowlist`</b>:  publish_rooms_allowlist config. 
 - <b>`report_stats`</b>:  report_stats config. 
 - <b>`server_name`</b>:  server_name config. 
 - <b>`trusted_key_servers`</b>:  trusted_key_servers config. 




---

<a href="../src/charm_state.py#L198"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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

<a href="../src/charm_state.py#L217"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `to_yes_or_no`

```python
to_yes_or_no(value: str) → str
```

Convert the report_stats field to yes or no. 



**Args:**
 
 - <b>`value`</b>:  the input value. 



**Returns:**
 The string converted to yes or no. 

---

<a href="../src/charm_state.py#L232"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `userids_to_list`

```python
userids_to_list(value: str) → List[str]
```

Convert a comma separated list of users to list. 



**Args:**
 
 - <b>`value`</b>:  the input value. 



**Returns:**
 The string converted to list. 



**Raises:**
 
 - <b>`ValidationError`</b>:  if user_id is not as expected. 


