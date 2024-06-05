<!-- markdownlint-disable -->

<a href="../src/smtp_observer.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `smtp_observer.py`
The SMTP integrator relation observer. 



---

## <kbd>class</kbd> `SMTPObserver`
The SMTP relation observer. 

<a href="../src/smtp_observer.py#L39"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(charm: CharmBaseWithState)
```

Initialize the observer and register event handlers. 



**Args:**
 
 - <b>`charm`</b>:  The parent charm to attach the observer to. 


---

#### <kbd>property</kbd> model

Shortcut for more simple access the model. 



---

<a href="../src/smtp_observer.py#L56"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `get_charm`

```python
get_charm() → CharmBaseWithState
```

Return the current charm. 



**Returns:**
  The current charm 

---

<a href="../src/smtp_observer.py#L64"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `get_relation_as_smtp_conf`

```python
get_relation_as_smtp_conf() → Optional[SMTPConfiguration]
```

Get SMTP data from relation. 



**Returns:**
 
 - <b>`Dict`</b>:  Information needed for setting environment variables. 



**Raises:**
 
 - <b>`CharmConfigInvalidError`</b>:  If the SMTP configurations is not supported. 


