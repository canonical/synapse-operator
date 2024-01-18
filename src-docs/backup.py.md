<!-- markdownlint-disable -->

<a href="../src/backup.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `backup.py`
Provides backup functionality for Synapse. 

**Global Variables**
---------------
- **S3_CANNOT_ACCESS_BUCKET**
- **S3_INVALID_CONFIGURATION**
- **BACK_UP_STATUS_MESSAGES**

---

<a href="../src/backup.py#L106"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `can_use_bucket`

```python
can_use_bucket(s3_parameters: S3Parameters) → bool
```

Check if a bucket exists and is accessible in an S3 compatible object store. 



**Args:**
 
 - <b>`s3_parameters`</b>:  S3 connection parameters 



**Returns:**
 True if the bucket exists and is accessible 


---

## <kbd>class</kbd> `S3Parameters`
Configuration for accessing S3 bucket. 



**Attributes:**
 
 - <b>`access_key`</b>:  AWS access key. 
 - <b>`secret_key`</b>:  AWS secret key. 
 - <b>`region`</b>:  The region to connect to the object storage. 
 - <b>`bucket`</b>:  The bucket name. 
 - <b>`endpoint`</b>:  The endpoint used to connect to the object storage. 
 - <b>`path`</b>:  The path inside the bucket to store objects. 
 - <b>`s3_uri_style`</b>:  The S3 protocol specific bucket path lookup type. 




---

<a href="../src/backup.py#L44"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `check_region_or_endpoint_set`

```python
check_region_or_endpoint_set(region: str, values: dict[str, Any]) → str
```

Validate that either that region or endpoint is set. 



**Args:**
 
 - <b>`region`</b>:  region attribute 
 - <b>`values`</b>:  all attributes in S3 configuration 



**Returns:**
 value of the region attribute 



**Raises:**
 
 - <b>`ValueError`</b>:  if the configuration is invalid. 


---

## <kbd>class</kbd> `SynapseBackup`
Class to manage Synapse backups over S3. 

<a href="../src/backup.py#L70"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(charm: CharmBase)
```

Initialize the backup object. 



**Args:**
 
 - <b>`charm`</b>:  The parent charm the backups are made for. 


---

#### <kbd>property</kbd> model

Shortcut for more simple access the model. 




