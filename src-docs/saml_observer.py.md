<!-- markdownlint-disable -->

<a href="../src/saml_observer.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `saml_observer.py`
The SAML integrator relation observer. 



---

## <kbd>class</kbd> `SAMLObserver`
The SAML Integrator relation observer. 

Attrs:  _pebble_service: instance of pebble service. 

<a href="../src/saml_observer.py#L33"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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

<a href="../src/saml_observer.py#L72"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `get_relation_as_saml_conf`

```python
get_relation_as_saml_conf() → Optional[SAMLConfiguration]
```

Get SAML data from relation. 



**Returns:**
 
 - <b>`Dict`</b>:  Information needed for setting environment variables. 


