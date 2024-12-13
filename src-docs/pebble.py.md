<!-- markdownlint-disable -->

<a href="../src/pebble.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `pebble.py`
Class to interact with pebble. 

**Global Variables**
---------------
- **MAS_CONFIGURATION_PATH**
- **MAS_PEBBLE_LAYER**
- **MAS_SERVICE_NAME**
- **STATS_EXPORTER_SERVICE_NAME**

---

<a href="../src/pebble.py#L50"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `check_synapse_alive`

```python
check_synapse_alive(charm_state: CharmState) → CheckDict
```

Return the Synapse container alive check. 



**Args:**
 
 - <b>`charm_state`</b>:  Instance of CharmState. 



**Returns:**
 
 - <b>`Dict`</b>:  check object converted to its dict representation. 


---

<a href="../src/pebble.py#L72"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `check_synapse_ready`

```python
check_synapse_ready() → CheckDict
```

Return the Synapse container ready check. 



**Returns:**
 
 - <b>`Dict`</b>:  check object converted to its dict representation. 


---

<a href="../src/pebble.py#L88"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `restart_synapse`

```python
restart_synapse(
    charm_state: CharmState,
    container: Container,
    is_main: bool = True
) → None
```

Restart Synapse service. 

This will force a restart even if its plan hasn't changed. 



**Args:**
 
 - <b>`charm_state`</b>:  Instance of CharmState 
 - <b>`container`</b>:  Synapse container. 
 - <b>`is_main`</b>:  if unit is main. 


---

<a href="../src/pebble.py#L110"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `check_nginx_ready`

```python
check_nginx_ready() → CheckDict
```

Return the Synapse NGINX container check. 



**Returns:**
 
 - <b>`Dict`</b>:  check object converted to its dict representation. 


---

<a href="../src/pebble.py#L123"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `check_mjolnir_ready`

```python
check_mjolnir_ready() → CheckDict
```

Return the Synapse Mjolnir service check. 



**Returns:**
 
 - <b>`Dict`</b>:  check object converted to its dict representation. 


---

<a href="../src/pebble.py#L139"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `restart_nginx`

```python
restart_nginx(container: Container, main_unit_address: str) → None
```

Restart Synapse NGINX service and regenerate configuration. 



**Args:**
 
 - <b>`container`</b>:  Charm container. 
 - <b>`main_unit_address`</b>:  Main unit address to be used in configuration. 


---

<a href="../src/pebble.py#L151"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `restart_federation_sender`

```python
restart_federation_sender(container: Container, charm_state: CharmState) → None
```

Restart Synapse federation sender service and regenerate configuration. 



**Args:**
 
 - <b>`container`</b>:  Charm container. 
 - <b>`charm_state`</b>:  Instance of CharmState. 


---

<a href="../src/pebble.py#L164"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `replan_mjolnir`

```python
replan_mjolnir(container: Container) → None
```

Replan Synapse Mjolnir service. 



**Args:**
 
 - <b>`container`</b>:  Charm container. 


---

<a href="../src/pebble.py#L174"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `replan_stats_exporter`

```python
replan_stats_exporter(container: Container, charm_state: CharmState) → None
```

Replan Synapse StatsExporter service. 



**Args:**
 
 - <b>`container`</b>:  Charm container. 
 - <b>`charm_state`</b>:  Instance of CharmState. 


---

<a href="../src/pebble.py#L201"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `replan_synapse_federation_sender`

```python
replan_synapse_federation_sender(
    container: Container,
    charm_state: CharmState
) → None
```

Replan Synapse Federation Sender service. 



**Args:**
 
 - <b>`container`</b>:  Charm container. 
 - <b>`charm_state`</b>:  Instance of CharmState. 


---

<a href="../src/pebble.py#L216"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `replan_mas`

```python
replan_mas(container: Container) → None
```

Replan Matrix Authentication Service. 



**Args:**
 
 - <b>`container`</b>:  Charm container. 


---

<a href="../src/pebble.py#L320"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `reconcile`

```python
reconcile(
    charm_state: CharmState,
    rendered_mas_configuration: str,
    synapse_msc3861_configuration: dict,
    container: Container,
    is_main: bool = True,
    unit_number: str = ''
) → None
```

Reconcile Synapse configuration with charm state. 

This is the main entry for changes that require a restart done via Pebble. 



**Args:**
 
 - <b>`charm_state`</b>:  Instance of CharmState 
 - <b>`rendered_mas_configuration`</b>:  Rendered MAS yaml configuration. 
 - <b>`synapse_msc3861_configuration`</b>:  Synapse's msc3861 configuration 
 - <b>`container`</b>:  Charm container. 
 - <b>`is_main`</b>:  if unit is main. 
 - <b>`unit_number`</b>:  unit number id to set the worker name. 



**Raises:**
 
 - <b>`PebbleServiceError`</b>:  if something goes wrong while interacting with Pebble. 


---

<a href="../src/pebble.py#L630"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `restart_mas`

```python
restart_mas(container: Container, rendered_mas_configuration: str) → None
```

Update MAS configuration and restart MAS. 



**Args:**
 
 - <b>`container`</b>:  The synapse container. 
 - <b>`rendered_mas_configuration`</b>:  YAML configuration for MAS. 


---

## <kbd>class</kbd> `PebbleServiceError`
Exception raised when something fails while interacting with Pebble. 

Attrs:  msg (str): Explanation of the error. 

<a href="../src/pebble.py#L41"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(msg: str)
```

Initialize a new instance of the PebbleServiceError exception. 



**Args:**
 
 - <b>`msg`</b> (str):  Explanation of the error. 





