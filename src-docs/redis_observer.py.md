<!-- markdownlint-disable -->

<a href="../src/redis_observer.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `redis_observer.py`
The Redis agent relation observer. 



---

## <kbd>class</kbd> `RedisObserver`
The Redis relation observer. 


<a href="../src/redis_observer.py#L25"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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


<a href="../src/redis_observer.py#L38"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>


### <kbd>function</kbd> `get_charm`

```python
get_charm() → CharmBaseWithState
```

Return the current charm. 



**Returns:**
  The current charm 

---


<a href="../src/redis_observer.py#L46"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>


### <kbd>function</kbd> `get_relation_as_redis_conf`

```python
get_relation_as_redis_conf() → Optional[RedisConfiguration]
```

Get the hostname and port from the redis relation data. 



**Returns:**
  RedisConfiguration instance with the hostname and port of the related redis or None  if not found. 


