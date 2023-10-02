<!-- markdownlint-disable -->

<a href="../src/database_observer.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `database_observer.py`
The Database agent relation observer. 



---

## <kbd>class</kbd> `DatabaseObserver`
The Database relation observer. 

Attrs:  _pebble_service: instance of pebble service. 

<a href="../src/database_observer.py#L34"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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

<a href="../src/database_observer.py#L112"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `get_database_name`

```python
get_database_name() → str
```

Get database name. 



**Raises:**
 
 - <b>`CharmDatabaseRelationNotFoundError`</b>:  if there is no relation. 



**Returns:**
 
 - <b>`str`</b>:  database name. 

---

<a href="../src/database_observer.py#L90"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `get_relation_as_datasource`

```python
get_relation_as_datasource() → Optional[DatasourcePostgreSQL]
```

Get database data from relation. 



**Returns:**
 
 - <b>`Dict`</b>:  Information needed for setting environment variables. 


