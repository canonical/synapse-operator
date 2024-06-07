<!-- markdownlint-disable -->

<a href="../src/media_observer.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `media_observer.py`
The media integrator relation observer. 

**Global Variables**
---------------
- **S3_INVALID_CONFIGURATION**
- **S3_CANNOT_ACCESS_BUCKET**


---

## <kbd>class</kbd> `MediaObserver`
The media relation observer. 

<a href="../src/media_observer.py#L28"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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

<a href="../src/media_observer.py#L42"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `get_charm`

```python
get_charm() → CharmBaseWithState
```

Return the current charm. 



**Returns:**
  The current charm 

---

<a href="../src/media_observer.py#L69"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `get_relation_as_media_conf`

```python
get_relation_as_media_conf() → Optional[MediaConfiguration]
```

Get Media data from relation. 



**Returns:**
 
 - <b>`Dict`</b>:  Information needed for setting environment variables. 


