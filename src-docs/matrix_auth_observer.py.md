<!-- markdownlint-disable -->

<a href="../src/matrix_auth_observer.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `matrix_auth_observer.py`
The Matrix Auth relation observer. 



---

## <kbd>class</kbd> `MatrixAuthObserver`
The Matrix Auth relation observer. 

<a href="../src/matrix_auth_observer.py#L22"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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

<a href="../src/matrix_auth_observer.py#L38"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `get_charm`

```python
get_charm() → CharmBaseWithState
```

Return the current charm. 



**Returns:**
  The current charm 

---

<a href="../src/matrix_auth_observer.py#L46"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `update_matrix_auth_integration`

```python
update_matrix_auth_integration(charm_state: CharmState) → None
```

Update matrix auth integration relation data. 



**Args:**
 
 - <b>`charm_state`</b>:  The charm state. 


