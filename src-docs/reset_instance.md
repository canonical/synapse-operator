<!-- markdownlint-disable -->

<a href="../src/actions/reset_instance.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `reset_instance`
Module to interact with Reset Instance action. 


---

<a href="../src/actions/reset_instance.py#L37"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `reset_instance`

```python
reset_instance(
    container: Container,
    charm_state: CharmState,
    datasource: Optional[DatasourcePostgreSQL]
) → None
```

Run reset instance action. 



**Args:**
 
 - <b>`container`</b>:  Container of the charm. 
 - <b>`charm_state`</b>:  charm state from the charm. 
 - <b>`datasource`</b>:  datasource to interact with the database. 



**Raises:**
 
 - <b>`ResetInstanceError`</b>:  if something goes wrong while resetting the instance. 


---

<a href="../src/actions/reset_instance.py#L21"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `ResetInstanceError`
Exception raised when something fails while running reset-instance. 

Attrs:  msg (str): Explanation of the error. 

<a href="../src/actions/reset_instance.py#L28"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(msg: str)
```

Initialize a new instance of the ResetInstanceError exception. 



**Args:**
 
 - <b>`msg`</b> (str):  Explanation of the error. 





