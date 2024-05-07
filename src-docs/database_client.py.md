<!-- markdownlint-disable -->

<a href="../src/database_client.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `database_client.py`
The DatabaseClient class. 



---

## <kbd>class</kbd> `DatabaseClient`
A class representing the Synapse application. 

<a href="../src/database_client.py#L21"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(
    datasource: Optional[DatasourcePostgreSQL],
    alternative_database: str = ''
)
```

Initialize a new instance of the Synapse class. 



**Args:**
 
 - <b>`datasource`</b>:  datasource to use to connect. 
 - <b>`alternative_database`</b>:  database to connect to.  The default is to use the one provided by datasource. 



**Raises:**
 
 - <b>`CharmDatabaseRelationNotFoundError`</b>:  if there is no relation. 




---

<a href="../src/database_client.py#L107"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `erase`

```python
erase() → None
```

Erase database. 



**Raises:**
 
 - <b>`Error`</b>:  something went wrong while erasing the database. 

---

<a href="../src/database_client.py#L73"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `prepare`

```python
prepare() → None
```

Change database collate and ctype as required by Synapse. 



**Raises:**
 
 - <b>`Error`</b>:  something went wrong while preparing the database. 


