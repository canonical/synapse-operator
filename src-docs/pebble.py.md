<!-- markdownlint-disable -->

<a href="../src/pebble.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `pebble.py`
Class to interact with pebble. 



---

## <kbd>class</kbd> `PebbleService`
The charm pebble service manager. 

<a href="../src/pebble.py#L38"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(charm_state: CharmState)
```

Initialize the pebble service. 



**Args:**
 
 - <b>`charm_state`</b>:  Instance of CharmState. 




---

<a href="../src/pebble.py#L89"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `change_config`

```python
change_config(container: Container) → None
```

Change the configuration. 



**Args:**
 
 - <b>`container`</b>:  Charm container. 



**Raises:**
 
 - <b>`PebbleServiceError`</b>:  if something goes wrong while interacting with Pebble. 

---

<a href="../src/pebble.py#L132"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `enable_saml`

```python
enable_saml(container: Container) → None
```

Enable SAML while receiving on_saml_data_available event. 



**Args:**
 
 - <b>`container`</b>:  Charm container. 



**Raises:**
 
 - <b>`PebbleServiceError`</b>:  if something goes wrong while interacting with Pebble. 

---

<a href="../src/pebble.py#L148"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `enable_smtp`

```python
enable_smtp(container: Container) → None
```

Enable SMTP while receiving on_smtp_data_available event. 



**Args:**
 
 - <b>`container`</b>:  Charm container. 



**Raises:**
 
 - <b>`PebbleServiceError`</b>:  if something goes wrong while interacting with Pebble. 

---

<a href="../src/pebble.py#L79"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `replan_irc_bridge`

```python
replan_irc_bridge(container: Container) → None
```

Replan Synapse IRC bridge service. 



**Args:**
 
 - <b>`container`</b>:  Charm container. 

---

<a href="../src/pebble.py#L70"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `replan_mjolnir`

```python
replan_mjolnir(container: Container) → None
```

Replan Synapse Mjolnir service. 



**Args:**
 
 - <b>`container`</b>:  Charm container. 

---

<a href="../src/pebble.py#L61"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `replan_nginx`

```python
replan_nginx(container: Container) → None
```

Replan Synapse NGINX service. 



**Args:**
 
 - <b>`container`</b>:  Charm container. 

---

<a href="../src/pebble.py#L164"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `reset_instance`

```python
reset_instance(container: Container) → None
```

Reset instance. 



**Args:**
 
 - <b>`container`</b>:  Charm container. 



**Raises:**
 
 - <b>`PebbleServiceError`</b>:  if something goes wrong while interacting with Pebble. 

---

<a href="../src/pebble.py#L46"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `restart_synapse`

```python
restart_synapse(container: Container) → None
```

Restart Synapse service. 

This will force a restart even if its plan hasn't changed. 



**Args:**
 
 - <b>`container`</b>:  Synapse container. 


---

## <kbd>class</kbd> `PebbleServiceError`
Exception raised when something fails while interacting with Pebble. 

Attrs:  msg (str): Explanation of the error. 

<a href="../src/pebble.py#L26"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(msg: str)
```

Initialize a new instance of the PebbleServiceError exception. 



**Args:**
 
 - <b>`msg`</b> (str):  Explanation of the error. 





