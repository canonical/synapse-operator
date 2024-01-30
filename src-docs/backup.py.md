<!-- markdownlint-disable -->

<a href="../src/backup.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `backup.py`
Provides backup functionality for Synapse. 

**Global Variables**
---------------
- **TAR_ENCRYPTED_EXTENSION**
- **FILE_PATTERNS_TO_BACKUP**

---

<a href="../src/backup.py#L330"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `encrypt_generator`

```python
encrypt_generator(
    inputstream: Iterable[bytes],
    password: str
) → Generator[bytes, NoneType, NoneType]
```

Encrypt an inputstream (iterator) and return another iterator. 

https://docs.aws.amazon.com/encryption-sdk/latest/developer-guide/python-example-code.html#python-example-streams 



**Args:**
 
 - <b>`inputstream`</b>:  Input iterable to write bytes from 
 - <b>`password`</b>:  Password to use to encrypt 



**Yields:**
 Encrypted bytes 


---

<a href="../src/backup.py#L358"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `decrypt_generator`

```python
decrypt_generator(
    inputstream: Iterable[bytes],
    password: str
) → Generator[bytes, NoneType, NoneType]
```

Decrypt an inputstream (iterator) and return another iterator. 

https://docs.aws.amazon.com/encryption-sdk/latest/developer-guide/python-example-code.html#python-example-streams 



**Args:**
 
 - <b>`inputstream`</b>:  Input iterable to write bytes from 
 - <b>`password`</b>:  Password to use to decrypt 



**Yields:**
 Decrypted bytes 


---

<a href="../src/backup.py#L385"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `tar_file_generator`

```python
tar_file_generator(
    files_to_tar: List[str],
    base_dir: str,
    open_func: Any = <built-in function open>
) → Generator[bytes, NoneType, NoneType]
```

Create a tar file with input files and yields the bytes. 



**Args:**
 
 - <b>`files_to_tar`</b>:  List of file to include in the tar 
 - <b>`base_dir`</b>:  working directory for the tar 
 - <b>`open_func`</b>:  Alternative open function 



**Yields:**
 tar content 


---

<a href="../src/backup.py#L427"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `default_filenames_to_backup`

```python
default_filenames_to_backup(base_dir: str) → Any
```

Get a list of the filenames to backup in Synapse. 



**Args:**
 
 - <b>`base_dir`</b>:  Synapse data dir 



**Yields:**
 Name of the files to backup. 


---

<a href="../src/backup.py#L442"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `create_backup`

```python
create_backup(
    s3_parameters: S3Parameters,
    backup_name: str,
    password: str
) → None
```

Create a new back up for Synapse. 



**Args:**
 
 - <b>`s3_parameters`</b>:  S3 parameters for the bucket to create the backup. 
 - <b>`backup_name`</b>:  Name for the backup. The uploaded file will have an extension appended. 
 - <b>`password`</b>:  Password to use for the encrypted file. 


---

## <kbd>class</kbd> `BytesIOIterable`
Class that created a file like object from an iterable. 

<a href="../src/backup.py#L291"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(iterable: Iterable[bytes])
```

Initialize the object with the iterable. 



**Args:**
 
 - <b>`iterable`</b>:  Iterable to get the bytes from. 




---

<a href="../src/backup.py#L300"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `read`

```python
read(size: int | None = -1) → bytes
```

Return up to size bytes from the input iterable. 



**Args:**
 
 - <b>`size`</b>:  Up to the number of bytes to read. 



**Returns:**
 bytes read or empty for EOF. 


---

## <kbd>class</kbd> `S3Client`
S3 Client Wrapper around boto3 library. 



**Attributes:**
 
 - <b>`MIN_MULTIPART_SIZE`</b>:  minimum multipart size for S3 Multi part upload. 

<a href="../src/backup.py#L151"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(s3_parameters: S3Parameters)
```

Initialize the S3 client. 



**Args:**
 
 - <b>`s3_parameters`</b>:  Parameter to configure the S3 connection. 




---

<a href="../src/backup.py#L191"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `can_use_bucket`

```python
can_use_bucket() → bool
```

Check if a bucket exists and is accessible in an S3 compatible object store. 



**Returns:**
  True if the bucket exists and is accessible 

---

<a href="../src/backup.py#L207"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `create_multipart_upload`

```python
create_multipart_upload(key: str) → _S3MultipartUpload
```

Create a Multipart upload. 



**Args:**
 
 - <b>`key`</b>:  object name. 



**Returns:**
 New multi part upload object. 

---

<a href="../src/backup.py#L220"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `stream_to_object`

```python
stream_to_object(inputstream: Iterable[bytes], key: str) → None
```

Streams an iterable to a S3 bucket using multipart upload. 



**Args:**
 
 - <b>`inputstream`</b>:  Input iterable to get bytes from. 
 - <b>`key`</b>:  S3 Object name. 


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

<a href="../src/backup.py#L61"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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



**Attributes:**
 
 - <b>`master_key`</b>:  Only master key that has the password. 
 - <b>`provider_id`</b>:  Provider ID. 

<a href="../src/backup.py#L253"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(**kwargs: dict)
```

Initialize empty map of keys. 



**Args:**
 
 - <b>`kwargs`</b>:  dict 




---

<a href="../src/backup.py#L278"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `add_static_password`

```python
add_static_password(password: str) → None
```

Add the password to use for the encryption/decryption. 



**Args:**
 
 - <b>`password`</b>:  Password to use for the encryption. 


