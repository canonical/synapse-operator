<!-- markdownlint-disable -->

<a href="../src/charm_state.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `charm_state.py`
State of the Charm. 



---

## <kbd>class</kbd> `CharmConfigInvalidError`
Exception raised when a charm configuration is found to be invalid. 

Attrs:  msg (str): Explanation of the error. 

<a href="../src/charm_state.py#L33"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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

<a href="../src/charm_state.py#L166"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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
 
 - <b>`admin_access_token`</b>:  admin_access_token to configure Mjolnir and Stats Exporter. 
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

<a href="../src/charm_state.py#L98"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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

<a href="../src/charm_state.py#L117"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `to_yes_or_no`

```python
to_yes_or_no(value: str) → str
```

Convert the report_stats field to yes or no. 



**Args:**
 
 - <b>`value`</b>:  the input value. 



**Returns:**
 The string converted to yes or no. 


