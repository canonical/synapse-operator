<!-- markdownlint-disable -->

<a href="../src/irc_bridge.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `irc_bridge.py`
Provide the IRC bridge class to represent the matrix-appservice-app plugin for Synapse. 

**Global Variables**
---------------
- **IRC_SERVICE_NAME**

---

<a href="../src/irc_bridge.py#L34"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `enable_irc_bridge`

```python
enable_irc_bridge(charm_state: CharmState, container: Container) → None
```

Enable irc service. 

The required steps to enable the IRC bridge are: 
 - Create the IRC bridge configuration file. 
 - Generate a PEM file for the IRC bridge. 



**Args:**
 
 - <b>`charm_state`</b>:  Instance of CharmState. 
 - <b>`container`</b>:  The container to enable the IRC bridge in. 


---

## <kbd>class</kbd> `PEMCreateError`
An exception raised when the PEM file creation fails. 

<a href="../src/irc_bridge.py#L25"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(message: str)
```

Initialize a new instance of the PEMCreateError class. 



**Args:**
 
 - <b>`message`</b>:  The error message. 





