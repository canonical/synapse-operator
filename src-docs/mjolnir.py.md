<!-- markdownlint-disable -->

<a href="../src/mjolnir.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `mjolnir.py`
Provide the Mjolnir class to represent the Mjolnir plugin for Synapse. 

**Global Variables**
---------------
- **MJOLNIR_SERVICE_NAME**
- **USERNAME**


---

## <kbd>class</kbd> `Mjolnir`
A class representing the Mjolnir plugin for Synapse application. 

Mjolnir is a moderation tool for Matrix to be used to protect your server from malicious invites, spam messages etc. See https://github.com/matrix-org/mjolnir/ for more details about it. 

<a href="../src/mjolnir.py#L33"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(charm: CharmBaseWithState, token_service: AdminAccessTokenService)
```

Initialize a new instance of the Mjolnir class. 



**Args:**
 
 - <b>`charm`</b>:  The charm object that the Mjolnir instance belongs to. 
 - <b>`token_service`</b>:  Instance of Admin Access Token Service. 


---

#### <kbd>property</kbd> model

Shortcut for more simple access the model. 



---

<a href="../src/mjolnir.py#L153"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `enable_mjolnir`

```python
enable_mjolnir(charm_state: CharmState, admin_access_token: str) → None
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



**Args:**
 
 - <b>`charm_state`</b>:  Instance of CharmState. 
 - <b>`admin_access_token`</b>:  not empty admin access token. 

---

<a href="../src/mjolnir.py#L45"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `get_charm`

```python
get_charm() → CharmBaseWithState
```

Return the current charm. 



**Returns:**
  The current charm 

---

<a href="../src/mjolnir.py#L140"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `get_membership_room_id`

```python
get_membership_room_id(admin_access_token: str) → Optional[str]
```

Check if membership room exists. 



**Args:**
 
 - <b>`admin_access_token`</b>:  not empty admin access token. 



**Returns:**
 The room id or None if is not found. 


