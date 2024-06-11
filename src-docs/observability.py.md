<!-- markdownlint-disable -->

<a href="../src/observability.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `observability.py`
Provide the Observability class to represent the observability stack for Synapse. 

**Global Variables**
---------------
- **CONTAINER_NAME**
- **LOG_PATHS**


---

## <kbd>class</kbd> `Observability`
A class representing the observability stack for Synapse application. 

<a href="../src/observability.py#L22"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(charm: CharmBase)
```

Initialize a new instance of the Observability class. 



**Args:**
 
 - <b>`charm`</b>:  The charm object that the Observability instance belongs to. 




---

<a href="../src/observability.py#L50"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `update_targets`

```python
update_targets(targets: List[str]) → None
```

Update prometheus targets. 



**Args:**
 
 - <b>`targets`</b>:  new target list. 


