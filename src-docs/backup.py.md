<!-- markdownlint-disable -->

<a href="../src/backup.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `backup.py`
Provides backup functionality for Synapse. 

**Global Variables**
---------------
- **AWS_COMMAND**
- **BACKUP_FILE_PATTERNS**
- **LOCAL_DIR_PATTERN**
- **S3_MAX_CONCURRENT_REQUESTS**
- **MEDIA_DIR**
- **PASSPHRASE_FILE**
- **BASH_COMMAND**

---

<a href="../src/backup.py#L155"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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

<a href="../src/backup.py#L174"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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

Build the command to execute the backup. 



**Args:**
 
 - <b>`s3_parameters`</b>:  S3 parameters. 
 - <b>`backup_key`</b>:  The name of the object to back up. 
 - <b>`backup_paths`</b>:  List of paths to back up. 
 - <b>`passphrase_file`</b>:  Passphrase to use to encrypt the backup file. 
 - <b>`expected_size`</b>:  expected size of the backup, so AWS S3 Client can calculate  a reasonable size for the upload parts. 



**Returns:**
 The backup command to execute. 


---

<a href="../src/backup.py#L205"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `calculate_size`

```python
calculate_size(container: Container, paths: Iterable[str]) → int
```

Return the combined size of all the paths given. 



**Args:**
 
 - <b>`container`</b>:  Container where to check the size of the paths. 
 - <b>`paths`</b>:  Paths to check. 



**Returns:**
 Total size in bytes. 


---

<a href="../src/backup.py#L224"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `prepare_container`

```python
prepare_container(
    container: Container,
    s3_parameters: S3Parameters,
    passphrase: str
) → None
```

Prepare container for create or restore backup. 

This means preparing the required aws configuration and gpg passphrase file. 



**Args:**
 
 - <b>`container`</b>:  Synapse Container. 
 - <b>`s3_parameters`</b>:  S3 parameters for the backup. 
 - <b>`passphrase`</b>:  Passphrase for the backup (used for gpg). 



**Raises:**
 
 - <b>`BackupError`</b>:  if there was an error preparing the configuration. 


---

<a href="../src/backup.py#L268"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `create_backup`

```python
create_backup(
    container: Container,
    s3_parameters: S3Parameters,
    backup_key: str,
    passphrase: str
) → None
```

Create a backup for Synapse running it in the workload. 



**Args:**
 
 - <b>`container`</b>:  Synapse Container 
 - <b>`s3_parameters`</b>:  S3 parameters for the backup. 
 - <b>`backup_key`</b>:  Name of the object in the backup. 
 - <b>`passphrase`</b>:  Passphrase use to encrypt the backup. 



**Raises:**
 
 - <b>`BackupError`</b>:  If there was an error creating the backup. 


---

<a href="../src/backup.py#L308"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `get_environment`

```python
get_environment(s3_parameters: S3Parameters) → Dict[str, str]
```

Get the environment variables for backup that configure aws S3 cli. 



**Args:**
 
 - <b>`s3_parameters`</b>:  S3 parameters. 



**Returns:**
 A dictionary with aws s3 configuration variables. 


---

## <kbd>class</kbd> `BackupError`
Generic backup Exception. 





---

## <kbd>class</kbd> `S3Client`
S3 Client Wrapper around boto3 library. 

<a href="../src/backup.py#L98"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(s3_parameters: S3Parameters)
```

Initialize the S3 client. 



**Args:**
 
 - <b>`s3_parameters`</b>:  Parameter to configure the S3 connection. 




---

<a href="../src/backup.py#L138"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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

<a href="../src/backup.py#L65"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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


