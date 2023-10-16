<!-- markdownlint-disable -->

<a href="../src/synapse/workload.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `workload`
Helper module used to manage interactions with Synapse. 

**Global Variables**
---------------
- **CHECK_ALIVE_NAME**
- **CHECK_MJOLNIR_READY_NAME**
- **CHECK_NGINX_READY_NAME**
- **CHECK_READY_NAME**
- **COMMAND_MIGRATE_CONFIG**
- **SYNAPSE_CONFIG_DIR**
- **MJOLNIR_CONFIG_PATH**
- **MJOLNIR_HEALTH_PORT**
- **MJOLNIR_SERVICE_NAME**
- **PROMETHEUS_TARGET_PORT**
- **SYNAPSE_COMMAND_PATH**
- **SYNAPSE_CONFIG_PATH**
- **SYNAPSE_CONTAINER_NAME**
- **SYNAPSE_NGINX_CONTAINER_NAME**
- **SYNAPSE_NGINX_PORT**
- **SYNAPSE_SERVICE_NAME**

---

<a href="../src/synapse/workload.py#L88"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `check_ready`

```python
check_ready() → CheckDict
```

Return the Synapse container ready check. 



**Returns:**
 
 - <b>`Dict`</b>:  check object converted to its dict representation. 


---

<a href="../src/synapse/workload.py#L101"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `check_alive`

```python
check_alive() → CheckDict
```

Return the Synapse container alive check. 



**Returns:**
 
 - <b>`Dict`</b>:  check object converted to its dict representation. 


---

<a href="../src/synapse/workload.py#L114"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `check_nginx_ready`

```python
check_nginx_ready() → CheckDict
```

Return the Synapse NGINX container check. 



**Returns:**
 
 - <b>`Dict`</b>:  check object converted to its dict representation. 


---

<a href="../src/synapse/workload.py#L127"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `check_mjolnir_ready`

```python
check_mjolnir_ready() → CheckDict
```

Return the Synapse Mjolnir service check. 



**Returns:**
 
 - <b>`Dict`</b>:  check object converted to its dict representation. 


---

<a href="../src/synapse/workload.py#L171"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `get_registration_shared_secret`

```python
get_registration_shared_secret(container: Container) → Optional[str]
```

Get registration_shared_secret from configuration file. 



**Args:**
 
 - <b>`container`</b>:  Container of the charm. 



**Returns:**
 registration_shared_secret value. 


---

<a href="../src/synapse/workload.py#L238"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `execute_migrate_config`

```python
execute_migrate_config(container: Container, charm_state: CharmState) → None
```

Run the Synapse command migrate_config. 



**Args:**
 
 - <b>`container`</b>:  Container of the charm. 
 - <b>`charm_state`</b>:  Instance of CharmState. 



**Raises:**
 
 - <b>`CommandMigrateConfigError`</b>:  something went wrong running migrate_config. 


---

<a href="../src/synapse/workload.py#L267"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `enable_metrics`

```python
enable_metrics(container: Container) → None
```

Change the Synapse configuration to enable metrics. 



**Args:**
 
 - <b>`container`</b>:  Container of the charm. 



**Raises:**
 
 - <b>`EnableMetricsError`</b>:  something went wrong enabling metrics. 


---

<a href="../src/synapse/workload.py#L291"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `enable_serve_server_wellknown`

```python
enable_serve_server_wellknown(container: Container) → None
```

Change the Synapse configuration to enable server wellknown file. 



**Args:**
 
 - <b>`container`</b>:  Container of the charm. 



**Raises:**
 
 - <b>`WorkloadError`</b>:  something went wrong enabling configuration. 


---

<a href="../src/synapse/workload.py#L328"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `create_mjolnir_config`

```python
create_mjolnir_config(
    container: Container,
    access_token: str,
    room_id: str
) → None
```

Create mjolnir configuration. 



**Args:**
 
 - <b>`container`</b>:  Container of the charm. 
 - <b>`access_token`</b>:  access token to be used by the Mjolnir. 
 - <b>`room_id`</b>:  management room id monitored by the Mjolnir. 



**Raises:**
 
 - <b>`CreateMjolnirConfigError`</b>:  something went wrong creating mjolnir config. 


---

<a href="../src/synapse/workload.py#L395"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `enable_saml`

```python
enable_saml(container: Container, charm_state: CharmState) → None
```

Change the Synapse configuration to enable SAML. 



**Args:**
 
 - <b>`container`</b>:  Container of the charm. 
 - <b>`charm_state`</b>:  Instance of CharmState. 



**Raises:**
 
 - <b>`EnableSAMLError`</b>:  something went wrong enabling SAML. 


---

<a href="../src/synapse/workload.py#L438"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `enable_smtp`

```python
enable_smtp(container: Container, charm_state: CharmState) → None
```

Change the Synapse configuration to enable SMTP. 



**Args:**
 
 - <b>`container`</b>:  Container of the charm. 
 - <b>`charm_state`</b>:  Instance of CharmState. 



**Raises:**
 
 - <b>`WorkloadError`</b>:  something went wrong enabling SMTP. 


---

<a href="../src/synapse/workload.py#L470"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `reset_instance`

```python
reset_instance(container: Container) → None
```

Erase data and config server_name. 



**Args:**
 
 - <b>`container`</b>:  Container of the charm. 



**Raises:**
 
 - <b>`PathError`</b>:  if somethings goes wrong while erasing the Synapse directory. 


---

<a href="../src/synapse/workload.py#L496"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `get_environment`

```python
get_environment(charm_state: CharmState) → Dict[str, str]
```

Generate a environment dictionary from the charm configurations. 



**Args:**
 
 - <b>`charm_state`</b>:  Instance of CharmState. 



**Returns:**
 A dictionary representing the Synapse environment variables. 


---

<a href="../src/synapse/workload.py#L38"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `WorkloadError`
Exception raised when something fails while interacting with workload. 

Attrs:  msg (str): Explanation of the error. 

<a href="../src/synapse/workload.py#L45"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(msg: str)
```

Initialize a new instance of the SynapseWorkloadError exception. 



**Args:**
 
 - <b>`msg`</b> (str):  Explanation of the error. 





---

<a href="../src/synapse/workload.py#L54"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `CommandMigrateConfigError`
Exception raised when a charm configuration is invalid. 

<a href="../src/synapse/workload.py#L45"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(msg: str)
```

Initialize a new instance of the SynapseWorkloadError exception. 



**Args:**
 
 - <b>`msg`</b> (str):  Explanation of the error. 





---

<a href="../src/synapse/workload.py#L58"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `ServerNameModifiedError`
Exception raised while checking configuration file. 

<a href="../src/synapse/workload.py#L45"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(msg: str)
```

Initialize a new instance of the SynapseWorkloadError exception. 



**Args:**
 
 - <b>`msg`</b> (str):  Explanation of the error. 





---

<a href="../src/synapse/workload.py#L62"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `EnableMetricsError`
Exception raised when something goes wrong while enabling metrics. 

<a href="../src/synapse/workload.py#L45"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(msg: str)
```

Initialize a new instance of the SynapseWorkloadError exception. 



**Args:**
 
 - <b>`msg`</b> (str):  Explanation of the error. 





---

<a href="../src/synapse/workload.py#L66"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `CreateMjolnirConfigError`
Exception raised when something goes wrong while creating mjolnir config. 

<a href="../src/synapse/workload.py#L45"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(msg: str)
```

Initialize a new instance of the SynapseWorkloadError exception. 



**Args:**
 
 - <b>`msg`</b> (str):  Explanation of the error. 





---

<a href="../src/synapse/workload.py#L70"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `EnableSAMLError`
Exception raised when something goes wrong while enabling SAML. 

<a href="../src/synapse/workload.py#L45"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(msg: str)
```

Initialize a new instance of the SynapseWorkloadError exception. 



**Args:**
 
 - <b>`msg`</b> (str):  Explanation of the error. 





---

<a href="../src/synapse/workload.py#L74"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `ExecResult`
A named tuple representing the result of executing a command. 



**Attributes:**
 
 - <b>`exit_code`</b>:  The exit status of the command (0 for success, non-zero for failure). 
 - <b>`stdout`</b>:  The standard output of the command as a string. 
 - <b>`stderr`</b>:  The standard error output of the command as a string. 





