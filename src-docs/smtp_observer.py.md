<!-- markdownlint-disable -->

<a href="../src/smtp_observer.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `smtp_observer.py`
The SMTP integrator relation observer. 



---

## <kbd>class</kbd> `SMTPObserver`
The SMTP relation observer. 

Attrs:  _pebble_service: instance of pebble service. 

<a href="../src/smtp_observer.py#L40"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(charm: CharmBase)
```

Initialize the observer and register event handlers. 



**Args:**
 
 - <b>`charm`</b>:  The parent charm to attach the observer to. 


---

#### <kbd>property</kbd> model

Shortcut for more simple access the model. 



---

<a href="../src/smtp_observer.py#L57"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `get_relation_as_smtp_conf`

```python
get_relation_as_smtp_conf() → Optional[SMTPConfiguration]
```

Get SMTP data from relation. 



**Returns:**
 
 - <b>`Dict`</b>:  Information needed for setting environment variables. 


