<!-- markdownlint-disable -->

<a href="../src/charm_state.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `charm_state.py`
State of the Charm. 



---

## <kbd>class</kbd> `CharmConfigInvalidError`
Exception raised when a charm configuration is found to be invalid. 

Attrs:  msg (str): Explanation of the error. 

<a href="../src/charm_state.py#L35"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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
 - <b>`proxy`</b>:  proxy information. 


---

#### <kbd>property</kbd> proxy

Get charm proxy information from juju charm environment. 



**Returns:**
  charm proxy information in the form of ProxyConfig. 



---

<a href="../src/charm_state.py#L168"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `from_charm`

```python
from_charm(
    charm: CharmBase,
    datasource: Optional[DatasourcePostgreSQL],
    saml_config: Optional[SAMLConfiguration]
) → CharmState
```

Initialize a new instance of the CharmState class from the associated charm. 



**Args:**
 
 - <b>`charm`</b>:  The charm instance associated with this state. 
 - <b>`datasource`</b>:  datasource information to be used by Synapse. 
 - <b>`saml_config`</b>:  saml configuration to be used by Synapse. 

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
 - <b>`federation_domain_whitelist`</b>:  federation_domain_whitelist config. 
 - <b>`ip_range_whitelist`</b>:  ip_range_whitelist config. 
 - <b>`public_baseurl`</b>:  public_baseurl config. 
 - <b>`report_stats`</b>:  report_stats config. 
 - <b>`server_name`</b>:  server_name config. 
 - <b>`smtp_enable_tls`</b>:  enable tls while connecting to SMTP server. 
 - <b>`smtp_host`</b>:  SMTP host. 
 - <b>`smtp_notif_from`</b>:  defines the "From" address to use when sending emails. 
 - <b>`smtp_pass`</b>:  password to authenticate to SMTP host. 
 - <b>`smtp_port`</b>:  SMTP port. 
 - <b>`smtp_user`</b>:  username to authenticate to SMTP host. 




---

<a href="../src/charm_state.py#L102"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `set_default_smtp_notif_from`

```python
set_default_smtp_notif_from(
    smtp_notif_from: Optional[str],
    values: dict
) → Optional[str]
```

Set server_name as default value to smtp_notif_from. 



**Args:**
 
 - <b>`smtp_notif_from`</b>:  the smtp_notif_from current value. 
 - <b>`values`</b>:  values already defined. 



**Returns:**
 The default value for smtp_notif_from if not defined. 

---

<a href="../src/charm_state.py#L121"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `to_yes_or_no`

```python
to_yes_or_no(value: str) → str
```

Convert the report_stats field to yes or no. 



**Args:**
 
 - <b>`value`</b>:  the input value. 



**Returns:**
 The string converted to yes or no. 


