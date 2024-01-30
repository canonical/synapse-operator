<!-- markdownlint-disable -->

<a href="../src/backup.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `backup.py`
Provides backup functionality for Synapse. 

**Global Variables**
---------------
- **AWS_COMMAND**

---

<a href="../src/backup.py#L147"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `get_paths_to_backup`

```python
get_paths_to_backup(container: Container) → Iterable[str]
```

Get the list of paths that should be in a backup for Synapse. 



**Args:**
 
 - <b>`container`</b>:  Synapse Container. 



**Returns:**
 Iterable with the list of paths to backup. 


---

<a href="../src/backup.py#L168"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `build_backup_command`

```python
build_backup_command(
    s3_parameters: S3Parameters,
    backup_key: str,
    backup_paths: Iterable[str],
    passphrase_file: str,
    expected_size: int = 10000000000
) → List[str]
```

TODO. 



**Args:**
 
 - <b>`s3_parameters`</b>:  S3Parameters 
 - <b>`backup_key`</b>:  str 
 - <b>`backup_paths`</b>:  Iterable[str] 
 - <b>`passphrase_file`</b>:  str 
 - <b>`expected_size`</b>:  int = int(1e10) 



**Returns:**
 TODO 


---

<a href="../src/backup.py#L198"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `create_backup`

```python
create_backup(
    container: Container,
    s3_parameters: S3Parameters,
    backup_key: str,
    passphrase: str
) → None
```

TODO. 



**Args:**
 
 - <b>`container`</b>:  ops.Container 
 - <b>`s3_parameters`</b>:  S3Parameters 
 - <b>`backup_key`</b>:  str 
 - <b>`passphrase`</b>:  str 


---

<a href="../src/backup.py#L250"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `get_environment`

```python
get_environment(s3_parameters: S3Parameters) → Dict[str, str]
```

TODO. 



**Args:**
 
 - <b>`s3_parameters`</b>:  S3Parameters 



**Returns:**
 TODO 


---

## <kbd>class</kbd> `S3Client`
S3 Client Wrapper around boto3 library. 

<a href="../src/backup.py#L90"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(s3_parameters: S3Parameters)
```

Initialize the S3 client. 



**Args:**
 
 - <b>`s3_parameters`</b>:  Parameter to configure the S3 connection. 




---

<a href="../src/backup.py#L130"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `can_use_bucket`

```python
can_use_bucket() → bool
```

Check if a bucket exists and is accessible in an S3 compatible object store. 



**Returns:**
  True if the bucket exists and is accessible 


---

## <kbd>class</kbd> `S3Error`
Generic S3 Exception. 





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
 - <b>`s3_uri_style`</b>:  The S3 protocol specific bucket path lookup type. Can be "path" or "host". 
 - <b>`addressing_style`</b>:  S3 protocol addressing style, can be "path" or "virtual". 


---

#### <kbd>property</kbd> addressing_style

Translates s3_uri_style to AWS addressing_style. 



---

<a href="../src/backup.py#L56"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `check_endpoint_or_region_set`

```python
check_endpoint_or_region_set(endpoint: str, values: dict[str, Any]) → str
```

Validate that either region or endpoint is set. 



**Args:**
 
 - <b>`endpoint`</b>:  endpoint attribute 
 - <b>`values`</b>:  all attributes in S3 configuration 



**Returns:**
 value of the endpoint attribute 



**Raises:**
 
 - <b>`ValueError`</b>:  if the configuration is invalid. 


