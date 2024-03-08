<!-- markdownlint-disable -->

<a href="../src/pebble.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `pebble.py`
Class to interact with pebble. 

**Global Variables**
---------------
- **STATS_EXPORTER_SERVICE_NAME**

---

<a href="../src/pebble.py#L37"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `restart_synapse`

```python
restart_synapse(charm_state: CharmState, container: Container) → None
```

Restart Synapse service. 

This will force a restart even if its plan hasn't changed. 



**Args:**
 
 - <b>`charm_state`</b>:  Instance of CharmState 
 - <b>`container`</b>:  Synapse container. 


---

<a href="../src/pebble.py#L54"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `replan_nginx`

```python
replan_nginx(container: Container) → None
```

Replan Synapse NGINX service. 



**Args:**
 
 - <b>`container`</b>:  Charm container. 


---

<a href="../src/pebble.py#L64"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `replan_mjolnir`

```python
replan_mjolnir(container: Container) → None
```

Replan Synapse Mjolnir service. 



**Args:**
 
 - <b>`container`</b>:  Charm container. 


---

<a href="../src/pebble.py#L74"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `replan_stats_exporter`

```python
replan_stats_exporter(container: Container, charm_state: CharmState) → None
```

Replan Synapse StatsExporter service. 



**Args:**
 
 - <b>`container`</b>:  Charm container. 
 - <b>`charm_state`</b>:  Instance of CharmState. 


---

<a href="../src/pebble.py#L100"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `change_config`

```python
change_config(charm_state: CharmState, container: Container) → None
```

Change the configuration. 



**Args:**
 
 - <b>`charm_state`</b>:  Instance of CharmState 
 - <b>`container`</b>:  Charm container. 



**Raises:**
 
 - <b>`PebbleServiceError`</b>:  if something goes wrong while interacting with Pebble. 


---

<a href="../src/pebble.py#L147"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `enable_redis`

```python
enable_redis(charm_state: CharmState, container: Container) → None
```

Enable Redis while receiving on_redis_relation_updated event. 



**Args:**
 
 - <b>`container`</b>:  Charm container. 
 - <b>`charm_state`</b>:  Instance of CharmState. 



**Raises:**
 
 - <b>`PebbleServiceError`</b>:  if something goes wrong while interacting with Pebble. 


---

<a href="../src/pebble.py#L165"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `enable_saml`

```python
enable_saml(charm_state: CharmState, container: Container) → None
```

Enable SAML while receiving on_saml_data_available event. 



**Args:**
 
 - <b>`charm_state`</b>:  Instance of CharmState 
 - <b>`container`</b>:  Charm container. 



**Raises:**
 
 - <b>`PebbleServiceError`</b>:  if something goes wrong while interacting with Pebble. 


---

<a href="../src/pebble.py#L183"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `enable_smtp`

```python
enable_smtp(charm_state: CharmState, container: Container) → None
```

Enable SMTP while receiving on_smtp_data_available event. 



**Args:**
 
 - <b>`charm_state`</b>:  Instance of CharmState 
 - <b>`container`</b>:  Charm container. 



**Raises:**
 
 - <b>`PebbleServiceError`</b>:  if something goes wrong while interacting with Pebble. 


---

<a href="../src/pebble.py#L201"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `reset_instance`

```python
reset_instance(charm_state: CharmState, container: Container) → None
```

Reset instance. 



**Args:**
 
 - <b>`charm_state`</b>:  Instance of CharmState 
 - <b>`container`</b>:  Charm container. 



**Raises:**
 
 - <b>`PebbleServiceError`</b>:  if something goes wrong while interacting with Pebble. 


---

## <kbd>class</kbd> `PebbleServiceError`
Exception raised when something fails while interacting with Pebble. 

Attrs:  msg (str): Explanation of the error. 

<a href="../src/pebble.py#L28"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(msg: str)
```

Initialize a new instance of the PebbleServiceError exception. 



**Args:**
 
 - <b>`msg`</b> (str):  Explanation of the error. 





