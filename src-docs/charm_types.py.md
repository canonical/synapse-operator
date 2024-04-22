<!-- markdownlint-disable -->

<a href="../src/charm_types.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `charm_types.py`
Type definitions for the Synapse charm. 



---

## <kbd>class</kbd> `DatasourcePostgreSQL`
A named tuple representing a Datasource PostgreSQL. 



**Attributes:**
 
 - <b>`user`</b>:  User. 
 - <b>`password`</b>:  Password. 
 - <b>`host`</b>:  Host (IP or DNS without port or protocol). 
 - <b>`port`</b>:  Port. 
 - <b>`db`</b>:  Database name. 





---

## <kbd>class</kbd> `MediaConfiguration`
A named tuple representing media configuration. 



**Attributes:**
 
 - <b>`bucket`</b>:  The name of the bucket. 
 - <b>`region_name`</b>:  The region name. 
 - <b>`endpoint_url`</b>:  The endpoint URL. 
 - <b>`access_key_id`</b>:  The access key ID. 
 - <b>`secret_access_key`</b>:  The secret access key. 
 - <b>`prefix`</b>:  File path prefix for the media. 





---

## <kbd>class</kbd> `RedisConfiguration`
A named tuple representing Redis configuration. 



**Attributes:**
 
 - <b>`host`</b>:  The hostname of the Redis server. 
 - <b>`port`</b>:  The port on the Redis server. 





---

## <kbd>class</kbd> `SAMLConfiguration`
A named tuple representing a SAML configuration. 



**Attributes:**
 
 - <b>`entity_id`</b>:  SAML entity ID. 
 - <b>`metadata_url`</b>:  URL to the metadata. 





---

## <kbd>class</kbd> `SMTPConfiguration`
A named tuple representing SMTP configuration. 



**Attributes:**
 
 - <b>`host`</b>:  The hostname of the outgoing SMTP server. 
 - <b>`port`</b>:  The port on the mail server for outgoing SMTP. 
 - <b>`user`</b>:  Optional username for authentication. 
 - <b>`password`</b>:  Optional password for authentication. 
 - <b>`enable_tls`</b>:  If enabled, if the server supports TLS, it will be used. 
 - <b>`force_tls`</b>:  If this option is set to true, TLS is used from the start (Implicit TLS)  and the option require_transport_security is ignored. 
 - <b>`require_transport_security`</b>:  Set to true to require TLS transport security for SMTP. 





