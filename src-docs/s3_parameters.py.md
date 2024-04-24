<!-- markdownlint-disable -->

<a href="../src/s3_parameters.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `s3_parameters.py`
Provides S3 Parameters configuration. 



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

<a href="../src/s3_parameters.py#L33"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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


