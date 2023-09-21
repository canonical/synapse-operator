<!-- markdownlint-disable -->

<a href="../src/mjolnir.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `mjolnir.py`
Provide the Mjolnir class to represent the Mjolnir plugin for Synapse. 

**Global Variables**
---------------
- **MJOLNIR_MANAGEMENT_ROOM**
- **MJOLNIR_MEMBERSHIP_ROOM**
- **MJOLNIR_SERVICE_NAME**
- **PEER_RELATION_NAME**
- **SECRET_ID**
- **SECRET_KEY**
- **SYNAPSE_CONTAINER_NAME**
- **USERNAME**


---

## <kbd>class</kbd> `Mjolnir`
A class representing the Mjolnir plugin for Synapse application. 

Mjolnir is a moderation tool for Matrix to be used to protect your server from malicious invites, spam messages etc. See https://github.com/matrix-org/mjolnir/ for more details about it. 

<a href="../src/mjolnir.py#L40"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(charm: CharmBase, charm_state: CharmState)
```

Initialize a new instance of the Mjolnir class. 



**Args:**
 
 - <b>`charm`</b>:  The charm object that the Mjolnir instance belongs to. 
 - <b>`charm_state`</b>:  Instance of CharmState. 


---

#### <kbd>property</kbd> model

Shortcut for more simple access the model. 



---

<a href="../src/mjolnir.py#L92"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `create_admin_user`

```python
create_admin_user(container: Container) → User
```

Create an admin user. 



**Args:**
 
 - <b>`container`</b>:  Synapse container. 



**Returns:**
 
 - <b>`User`</b>:  admin user that was created. 

---

<a href="../src/mjolnir.py#L176"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `enable_mjolnir`

```python
enable_mjolnir() → None
```

Enable mjolnir service. 

The required steps to enable Mjolnir are: 
 - Get an admin access token. 
 - Check if the MJOLNIR_MEMBERSHIP_ROOM room is created. 
 -- Only users from there will be allowed to join the management room. 
 - Create Mjolnir user or get its access token if already exists. 
 - Create the management room or get its room id if already exists. 
 -- The management room will allow only members of MJOLNIR_MEMBERSHIP_ROOM room to join it. 
 - Make the Mjolnir user admin of this room. 
 - Create the Mjolnir configuration file. 
 - Override Mjolnir user rate limit. 
 - Finally, add Mjolnir pebble layer. 

---

<a href="../src/mjolnir.py#L158"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `get_admin_access_token`

```python
get_admin_access_token() → str
```

Get admin access token. 



**Returns:**
  admin access token. 

---

<a href="../src/mjolnir.py#L147"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `get_membership_room_id`

```python
get_membership_room_id() → Optional[str]
```

Check if membership room exists. 



**Returns:**
  The room id or None if is not found. 


