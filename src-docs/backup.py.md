<!-- markdownlint-disable -->

<a href="../src/backup.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `backup.py`
Provides backup functionality for Synapse. 

**Global Variables**
---------------
- **AWS_COMMAND**
- **BACKUP_FILE_PATTERNS**
- **MEDIA_LOCAL_DIR_PATTERN**
- **S3_MAX_CONCURRENT_REQUESTS**
- **PASSPHRASE_FILE**
- **BASH_COMMAND**
- **BACKUP_ID_FORMAT**

---

<a href="../src/backup.py#L208"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `create_backup`

```python
create_backup(
    container: Container,
    s3_parameters: S3Parameters,
    passphrase: str
) → str
```

Create a backup for Synapse running it in the workload. 



**Args:**
 
 - <b>`container`</b>:  Synapse Container 
 - <b>`s3_parameters`</b>:  S3 parameters for the backup. 
 - <b>`passphrase`</b>:  Passphrase use to encrypt the backup. 



**Returns:**
 The backup key used for the backup. 



**Raises:**
 
 - <b>`BackupError`</b>:  If there was an error creating the backup. 


---

<a href="../src/backup.py#L256"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `restore_backup`

```python
restore_backup(
    container: Container,
    s3_parameters: S3Parameters,
    passphrase: str,
    backup_id: str
) → None
```

Restore a backup for Synapse overwriting the current data. 



**Args:**
 
 - <b>`container`</b>:  Synapse Container 
 - <b>`s3_parameters`</b>:  S3 parameters for the backup. 
 - <b>`passphrase`</b>:  Passphrase use to decrypt the backup. 
 - <b>`backup_id`</b>:  Name of the object in the backup. 



**Raises:**
 
 - <b>`BackupError`</b>:  If there was an error restoring the backup. 


---

## <kbd>class</kbd> `BackupError`
Generic backup Exception. 





---

## <kbd>class</kbd> `S3Backup`
Information about a backup file from S3. 



**Attributes:**
 
 - <b>`backup_id`</b>:  backup id 
 - <b>`last_modified`</b>:  last modified date in S3 
 - <b>`size`</b>:  size in bytes 





---

## <kbd>class</kbd> `S3Client`
S3 Client Wrapper around boto3 library. 

<a href="../src/backup.py#L73"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(s3_parameters: S3Parameters)
```

Initialize the S3 client. 



**Args:**
 
 - <b>`s3_parameters`</b>:  Parameter to configure the S3 connection. 




---

<a href="../src/backup.py#L113"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `can_use_bucket`

```python
can_use_bucket() → bool
```

Check if a bucket exists and is accessible in an S3 compatible object store. 



**Returns:**
  True if the bucket exists and is accessible 

---

<a href="../src/backup.py#L129"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `delete_backup`

```python
delete_backup(backup_id: str) → None
```

Delete a backup stored in S3 in the current s3 configuration. 



**Args:**
 
 - <b>`backup_id`</b>:  backup id to delete. 



**Raises:**
 
 - <b>`S3Error`</b>:  If there was an error deleting the backup. 

---

<a href="../src/backup.py#L145"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `exists_backup`

```python
exists_backup(backup_id: str) → bool
```

Check if a backup-id exists in S3. 



**Args:**
 
 - <b>`backup_id`</b>:  backup id to delete. 



**Returns:**
 True if the backup-id exists, False otherwise 



**Raises:**
 
 - <b>`S3Error`</b>:  If there was an error checking the backup. 

---

<a href="../src/backup.py#L168"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `list_backups`

```python
list_backups() → list[S3Backup]
```

List the backups stored in S3 in the current s3 configuration. 



**Returns:**
  list of backups. 


---

## <kbd>class</kbd> `S3Error`
Generic S3 Exception. 





