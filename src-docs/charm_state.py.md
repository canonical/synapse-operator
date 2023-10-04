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

<a href="../src/charm_state.py#L45"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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




---

<a href="../src/charm_state.py#L139"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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

## <kbd>class</kbd> `SynapseConfig`
Represent Synapse builtin configuration values. 

Attrs:  server_name: server_name config.  report_stats: report_stats config.  public_baseurl: public_baseurl config.  enable_mjolnir: enable_mjolnir config.  smtp_enable_tls: enable tls while connecting to SMTP server.  smtp_host: SMTP host.  smtp_notif_from: defines the "From" address to use when sending emails.  smtp_pass: password to authenticate to SMTP host.  smtp_port: SMTP port.  smtp_user: username to autehtncate to SMTP host. 




---

<a href="../src/charm_state.py#L90"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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

<a href="../src/charm_state.py#L109"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `to_yes_or_no`

```python
to_yes_or_no(value: str) → str
```

Convert the report_stats field to yes or no. 



**Args:**
 
 - <b>`value`</b>:  the input value. 



**Returns:**
 The string converted to yes or no. 


