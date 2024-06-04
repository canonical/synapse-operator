<!-- markdownlint-disable -->

<a href="../src/database_observer.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `database_observer.py`
The Database agent relation observer. 



---

## <kbd>class</kbd> `DatabaseObserver`
The Database relation observer. 

<a href="../src/database_observer.py#L27"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(charm: CharmBaseWithState, relation_name: str) → None
```

Initialize the observer and register event handlers. 



**Args:**
 
 - <b>`charm`</b>:  The parent charm to attach the observer to. 
 - <b>`relation_name`</b>:  The name of the relation to observe. 


---

#### <kbd>property</kbd> model

Shortcut for more simple access the model. 



---

<a href="../src/database_observer.py#L46"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `get_charm`

```python
get_charm() → CharmBaseWithState
```

Return the current charm. 



**Returns:**
  The current charm 

---

<a href="../src/database_observer.py#L84"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `get_relation_as_datasource`

```python
get_relation_as_datasource() → Optional[DatasourcePostgreSQL]
```

Get database data from relation. 



**Returns:**
 
 - <b>`Dict`</b>:  Information needed for setting environment variables. 


