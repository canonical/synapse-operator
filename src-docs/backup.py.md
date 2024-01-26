<!-- markdownlint-disable -->

<a href="../src/backup.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `backup.py`
Provides backup functionality for Synapse. 


---

<a href="../src/backup.py#L267"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `encrypt_generator`

```python
encrypt_generator(
    inputstream: Iterable[bytes],
    password: str
) → Generator[bytes, NoneType, NoneType]
```

Encrypt an inputstream (iterator) and return another iterator. 

https://docs.aws.amazon.com/encryption-sdk/latest/developer-guide/python-example-code.html#python-example-streams 


---

<a href="../src/backup.py#L288"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `decrypt_generator`

```python
decrypt_generator(
    inputstream: Iterable[bytes],
    password: str
) → Generator[bytes, NoneType, NoneType]
```

Decrypt an inputstream (iterator) and return another iterator. 

https://docs.aws.amazon.com/encryption-sdk/latest/developer-guide/python-example-code.html#python-example-streams 


---

<a href="../src/backup.py#L308"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `tar_file_generator`

```python
tar_file_generator(
    files_to_tar: List[str],
    base_dir: str,
    open_func: Any = <built-in function open>
) → Generator[bytes, NoneType, NoneType]
```

Create a tar file with input files and yields the bytes. 

TODO files_to_tar relative to base_dir TODO should we get the files from pebble, using another open/stat/whatever 


---

<a href="../src/backup.py#L336"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `create_backup`

```python
create_backup(s3_parameters: S3Parameters, backup_name: str) → None
```

Create a new back up for Synapse. 



**Args:**
 
 - <b>`s3_parameters`</b>:  S3 parameters for the bucket to create the backup. 
 - <b>`backup_name`</b>:  Name for the backup. 


---

## <kbd>class</kbd> `BytesIOIterable`
Class that created a file like object from an iterable. 

<a href="../src/backup.py#L239"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(iterable: Iterable[bytes])
```

Initialize the object with the iterable. 




---

<a href="../src/backup.py#L244"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `read`

```python
read(size: int | None = -1) → bytes
```

Return up to size bytes from the input iterable. 


---

## <kbd>class</kbd> `S3Client`
S3 Client Wrapper around boto3 library. 

<a href="../src/backup.py#L132"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(s3_parameters: S3Parameters)
```

Initialize the S3 client. 



**Args:**
 
 - <b>`s3_parameters`</b>:  Parameter to configure the S3 connection. 




---

<a href="../src/backup.py#L172"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `can_use_bucket`

```python
can_use_bucket() → bool
```

Check if a bucket exists and is accessible in an S3 compatible object store. 



**Returns:**
  True if the bucket exists and is accessible 

---

<a href="../src/backup.py#L188"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `create_multipart_upload`

```python
create_multipart_upload(key: str) → _S3MultipartUpload
```

Create a Multipart upload. 

---

<a href="../src/backup.py#L193"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `stream_to_object`

```python
stream_to_object(inputstream: Iterable[bytes], key: str) → None
```

Streams an iterable to a S3 bucket using multipart upload. 


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

<a href="../src/backup.py#L57"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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


---

## <kbd>class</kbd> `StaticRandomMasterKeyProvider`
KeyProvider to store the password to use for encryption/decryption. 

<a href="../src/backup.py#L216"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(**kwargs: dict)
```

Initialize empty map of keys. 




---

<a href="../src/backup.py#L230"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `add_static_password`

```python
add_static_password(password: str) → None
```

Add the password to use for the encryption/decryption. 


