<!-- markdownlint-disable -->

<a href="../src/charm_state.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `charm_state.py`
State of the Charm. 


---

<a href="../src/charm_state.py#L71"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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

<a href="../src/charm_state.py#L39"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `build_charm_state`

```python
build_charm_state() → CharmState
```

Build charm state. 

---

<a href="../src/charm_state.py#L43"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `get_charm`

```python
get_charm() → CharmBaseWithState
```

Return the current charm. 



**Returns:**
  The current charm 

---

<a href="../src/charm_state.py#L51"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `reconcile`

```python
reconcile(charm_state: 'CharmState') → None
```

Reconcile Synapse configuration. 



**Args:**
 
 - <b>`charm_state`</b>:  The charm state. 


---

## <kbd>class</kbd> `CharmConfigInvalidError`
Exception raised when a charm configuration is found to be invalid. 

Attrs:  msg (str): Explanation of the error. 

<a href="../src/charm_state.py#L134"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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
 - <b>`smtp_config`</b>:  smtp configuration. 
 - <b>`media_config`</b>:  media configuration. 
 - <b>`redis_config`</b>:  redis configuration. 
 - <b>`proxy`</b>:  proxy information. 
 - <b>`instance_map_config`</b>:  Instance map configuration with main and worker addresses. 
 - <b>`registration_secrets`</b>:  Registration secrets received via matrix-auth integration. 


---

#### <kbd>property</kbd> proxy

Get charm proxy information from juju charm environment. 



**Returns:**
  charm proxy information in the form of ProxyConfig. 



---

<a href="../src/charm_state.py#L382"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `from_charm`

```python
from_charm(
    charm: CharmBase,
    datasource: Optional[DatasourcePostgreSQL],
    smtp_config: Optional[SMTPConfiguration],
    media_config: Optional[MediaConfiguration],
    redis_config: Optional[RedisConfiguration],
    instance_map_config: Optional[Dict],
    registration_secrets: Optional[List]
) → CharmState
```

Initialize a new instance of the CharmState class from the associated charm. 



**Args:**
 
 - <b>`charm`</b>:  The charm instance associated with this state. 
 - <b>`datasource`</b>:  datasource information to be used by Synapse. 
 - <b>`smtp_config`</b>:  SMTP configuration to be used by Synapse. 
 - <b>`media_config`</b>:  Media configuration to be used by Synapse. 
 - <b>`redis_config`</b>:  Redis configuration to be used by Synapse. 
 - <b>`instance_map_config`</b>:  Instance map configuration with main and worker addresses. 
 - <b>`registration_secrets`</b>:  Registration secrets received via matrix-auth integration. 

Return: The CharmState instance created by the provided charm. 



**Raises:**
 
 - <b>`CharmConfigInvalidError`</b>:  if the charm configuration is invalid. 


---

## <kbd>class</kbd> `HasCharmWithState`
Protocol that defines a class that returns a CharmBaseWithState. 




---

<a href="../src/charm_state.py#L63"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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
 - <b>`block_non_admin_invites`</b>:  block_non_admin_invites config. 
 - <b>`enable_email_notifs`</b>:  enable_email_notifs config. 
 - <b>`enable_mjolnir`</b>:  enable_mjolnir config. 
 - <b>`enable_password_config`</b>:  enable_password_config config. 
 - <b>`enable_room_list_search`</b>:  enable_room_list_search config. 
 - <b>`federation_domain_whitelist`</b>:  federation_domain_whitelist config. 
 - <b>`invite_checker_blocklist_allowlist_url`</b>:  invite_checker_blocklist_allowlist_url config. 
 - <b>`invite_checker_policy_rooms`</b>:  invite_checker_policy_rooms config. 
 - <b>`ip_range_whitelist`</b>:  ip_range_whitelist config. 
 - <b>`limit_remote_rooms_complexity`</b>:  limit_remote_rooms_complexity config. 
 - <b>`notif_from`</b>:  defines the "From" address to use when sending emails. 
 - <b>`public_baseurl`</b>:  public_baseurl config. 
 - <b>`publish_rooms_allowlist`</b>:  publish_rooms_allowlist config. 
 - <b>`experimental_alive_check`</b>:  experimental_alive_check config. 
 - <b>`rc_joins_remote_burst_count`</b>:  rc_join burst_count config. 
 - <b>`rc_joins_remote_per_second`</b>:  rc_join per_second config. 
 - <b>`report_stats`</b>:  report_stats config. 
 - <b>`server_name`</b>:  server_name config. 
 - <b>`trusted_key_servers`</b>:  trusted_key_servers config. 
 - <b>`workers_ignore_list`</b>:  workers_ignore_list config. 




---

<a href="../src/charm_state.py#L218"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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

<a href="../src/charm_state.py#L252"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `roomids_to_list`

```python
roomids_to_list(value: str) → List[str]
```

Convert a comma separated list of rooms to list. 



**Args:**
 
 - <b>`value`</b>:  the input value. 



**Returns:**
 The string converted to list. 



**Raises:**
 
 - <b>`ValidationError`</b>:  if rooms is not as expected. 

---

<a href="../src/charm_state.py#L302"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `to_pebble_check`

```python
to_pebble_check(value: str) → Dict[str, Union[str, int]]
```

Convert the experimental_alive_check field to pebble check. 



**Args:**
 
 - <b>`value`</b>:  the input value. 



**Returns:**
 The pebble check. 



**Raises:**
 
 - <b>`ValidationError`</b>:  if experimental_alive_check is invalid. 

---

<a href="../src/charm_state.py#L237"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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

<a href="../src/charm_state.py#L277"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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


