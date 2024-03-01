<!-- markdownlint-disable -->

<a href="../src/irc_bridge.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `irc_bridge.py`
Provide the IRC bridge class to represent the matrix-appservice-app plugin for Synapse. 

**Global Variables**
---------------
- **IRC_SERVICE_NAME**


---

## <kbd>class</kbd> `IRCBridgeObserver`
A class representing the IRC bridge plugin for Synapse application. 

See https://github.com/matrix-org/matrix-appservice-irc/ for more details about it. 

<a href="../src/irc_bridge.py#L42"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(charm: CharmBaseWithState) → None
```

Initialize a new instance of the IRC bridge class. 



**Args:**
 
 - <b>`charm`</b>:  The charm object that the IRC bridge instance belongs to. 
 - <b>`charm_state`</b>:  Instance of CharmState. 


---

#### <kbd>property</kbd> model

Shortcut for more simple access the model. 



---

<a href="../src/irc_bridge.py#L54"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `get_charm`

```python
get_charm() → CharmBaseWithState
```

Return the current charm. 



**Returns:**
  The charm object. 


---

## <kbd>class</kbd> `PEMCreateError`
An exception raised when the PEM file creation fails. 

<a href="../src/irc_bridge.py#L27"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(message: str)
```

Initialize a new instance of the PEMCreateError class. 



**Args:**
 
 - <b>`message`</b>:  The error message. 





